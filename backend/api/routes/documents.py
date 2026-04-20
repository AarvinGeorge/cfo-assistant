"""
documents.py

FastAPI router for document lifecycle management — upload, list, and delete.

Role in project:
    HTTP layer for the document ingestion pipeline. Uses the multi-tenant
    storage stack:
      - RequestContext carries (user_id, workspace_id) from auth
      - StorageTransaction atomically writes to SQLite + Pinecone + disk
      - Documents live in Pinecone namespace=workspace_id and under
        data/uploads/{workspace_id}/{doc_id}.{ext} on disk
      - SQLite Document rows are the UI source of truth
    File hash dedup prevents re-embedding the same file within a workspace.

Main parts:
    - POST /documents/upload: parse+chunk+embed; transactional write.
      Returns existing doc_id if file_hash already present in workspace.
    - GET /documents/: SQL query against Document table scoped to workspace.
    - DELETE /documents/{doc_id}: transactional remove from all three stores.
"""
import hashlib
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy import select, delete as sql_delete

from backend.core.config import get_settings
from backend.core.context import RequestContext, get_request_context
from backend.core.gemini_client import GeminiClient
from backend.core.pinecone_store import get_pinecone_store
from backend.core.transactions import StorageTransaction
from backend.db.engine import get_session_factory
from backend.db.models import Document
from backend.mcp_server.tools.document_tools import list_documents_sql
from backend.skills.document_ingestion import parse_pdf, parse_csv, hierarchical_chunk

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("general"),
    fiscal_year: str = Form(""),
    ctx: RequestContext = Depends(get_request_context),
):
    """Upload, parse, chunk, embed — transactional across SQLite + Pinecone + disk."""
    # Validate filename + extension
    raw_filename = file.filename or "unknown"
    filename = Path(raw_filename).name
    if not filename or filename in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".csv", ".txt", ".html"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Read + size check
    MAX_FILE_SIZE = 50 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    file_hash = hashlib.sha256(contents).hexdigest()

    # Dedup check: same hash already in this workspace?
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        existing = session.execute(
            select(Document).where(
                Document.workspace_id == ctx.workspace_id,
                Document.file_hash == file_hash,
            )
        ).scalar_one_or_none()
        if existing:
            return {
                "doc_id": existing.id,
                "doc_name": existing.name,
                "doc_type": existing.doc_type,
                "chunk_count": existing.chunk_count,
                "status": "already_indexed",
            }

    # Parse via temp file (parsers expect a path)
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    try:
        if ext == ".pdf":
            with NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name
            try:
                parsed = parse_pdf(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        elif ext == ".csv":
            with NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name
            try:
                parsed = parse_csv(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        else:
            raise HTTPException(status_code=400, detail=f"Parser not implemented for {ext}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse document: {str(e)}")

    # Chunk
    doc_metadata = {
        "doc_id": doc_id,
        "doc_name": filename,
        "doc_type": doc_type,
        "fiscal_year": fiscal_year,
        "user_id": ctx.user_id,
        "workspace_id": ctx.workspace_id,
    }
    chunks = hierarchical_chunk(parsed, doc_metadata)
    if not chunks:
        raise HTTPException(status_code=400, detail="No content could be extracted")

    # Embed via Gemini (out-of-transaction; network call, not durable yet)
    gemini = GeminiClient()
    texts = [c.text for c in chunks]
    vectors_floats = gemini.embed_texts(texts)

    # Build Pinecone records (metadata includes text + token_count for retrieval)
    pinecone_records = []
    for chunk, vec in zip(chunks, vectors_floats):
        md = dict(chunk.metadata)
        md["text"] = chunk.text
        md["token_count"] = chunk.token_count
        pinecone_records.append({"id": chunk.chunk_id, "values": vec, "metadata": md})

    # Transactional write across all 3 stores
    settings = get_settings()
    upload_dir = Path(settings.upload_dir) / ctx.workspace_id
    file_path = upload_dir / f"{doc_id}{ext}"
    store = get_pinecone_store()

    try:
        with SessionLocal() as session, StorageTransaction() as tx:
            tx.add_file_write(file_path, contents)
            # Pinecone upserts in batches of 100
            for i in range(0, len(pinecone_records), 100):
                tx.add_pinecone_upsert(
                    store.index,
                    pinecone_records[i:i + 100],
                    namespace=ctx.workspace_id,
                )
            session.add(Document(
                id=doc_id,
                workspace_id=ctx.workspace_id,
                user_id=ctx.user_id,
                name=filename,
                doc_type=doc_type,
                fiscal_year=fiscal_year,
                file_hash=file_hash,
                chunk_count=len(chunks),
                status="indexed",
            ))
            session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    return {
        "doc_id": doc_id,
        "doc_name": filename,
        "doc_type": doc_type,
        "chunk_count": len(chunks),
        "status": "indexed",
    }


@router.get("/")
async def list_documents(ctx: RequestContext = Depends(get_request_context)):
    """List documents in the caller's workspace (SQLite-backed)."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        return list_documents_sql(ctx.workspace_id, session)


@router.delete("/{doc_id}")
async def remove_document(
    doc_id: str,
    ctx: RequestContext = Depends(get_request_context),
):
    """Transactional delete from SQLite + Pinecone + disk."""
    SessionLocal = get_session_factory()
    store = get_pinecone_store()
    settings = get_settings()

    with SessionLocal() as session:
        doc = session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.workspace_id == ctx.workspace_id,
            )
        ).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        ext = Path(doc.name).suffix.lower()
        file_path = Path(settings.upload_dir) / ctx.workspace_id / f"{doc_id}{ext}"

        try:
            with StorageTransaction() as tx:
                session.execute(sql_delete(Document).where(Document.id == doc_id))
                tx.add_pinecone_delete_by_filter(
                    store.index, {"doc_id": doc_id}, namespace=ctx.workspace_id
                )
                tx.add_file_delete(file_path)
                session.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

    return {"status": "deleted", "doc_id": doc_id}
