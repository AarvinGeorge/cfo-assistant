import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.core.config import get_settings
from backend.skills.document_ingestion import parse_pdf, parse_csv, hierarchical_chunk
from backend.skills.vector_retrieval import embed_and_upsert
from backend.mcp_server.tools.document_tools import (
    mcp_list_documents, register_document, delete_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("general"),
    fiscal_year: str = Form(""),
):
    """Upload a financial document, parse it, chunk it, embed it, and index it."""
    settings = get_settings()

    # Validate file type
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".csv", ".txt", ".html"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save uploaded file
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Parse based on type
    doc_id = str(uuid.uuid4())

    if ext == ".pdf":
        parsed = parse_pdf(str(file_path))
    elif ext == ".csv":
        parsed = parse_csv(str(file_path))
    else:
        raise HTTPException(status_code=400, detail=f"Parser not yet implemented for {ext}")

    # Build metadata
    doc_metadata = {
        "doc_id": doc_id,
        "doc_name": filename,
        "doc_type": doc_type,
        "fiscal_year": fiscal_year,
    }

    # Chunk
    chunks = hierarchical_chunk(parsed, doc_metadata)

    if not chunks:
        raise HTTPException(status_code=400, detail="No content could be extracted from the document")

    # Embed and upsert to Pinecone
    result = embed_and_upsert(chunks)

    # Track in Redis
    register_document(doc_metadata, chunk_count=result["upserted_count"])

    return {
        "doc_id": doc_id,
        "doc_name": filename,
        "doc_type": doc_type,
        "chunk_count": result["upserted_count"],
        "status": "indexed",
    }


@router.get("/")
async def list_documents():
    """List all ingested documents."""
    return mcp_list_documents()


@router.delete("/{doc_id}")
async def remove_document(doc_id: str):
    """Delete a document and its vectors."""
    deleted = delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {"status": "deleted", "doc_id": doc_id}
