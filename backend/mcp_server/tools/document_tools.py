"""
document_tools.py

MCP tool implementations for document search and retrieval operations.

Role in project:
    MCP layer — thin wrappers around vector_retrieval.py that expose
    document search capabilities as callable MCP tools. Claude invokes
    these during response generation to fetch cited source material.
    The document registry (list/create/delete) has moved to SQLite in
    PR #3/#4; see `list_documents_sql()` below and the routes in
    backend/api/routes/documents.py for the authoritative paths.

Main parts:
    - mcp_parse_pdf / mcp_parse_csv: parser wrappers.
    - mcp_embed_chunks / mcp_pinecone_upsert: legacy single-tenant embed
      helpers (callable via MCP but not used internally; will need
      workspace_id plumbing before being suitable for multi-tenant use).
    - mcp_pinecone_search: semantic search wrapper.
    - list_documents_sql(workspace_id, session): SQL-backed list used by
      the /documents GET route.
"""

import uuid
from typing import List, Dict, Any, Optional

from backend.core.config import get_settings
from backend.core.gemini_client import GeminiClient
from backend.core.pinecone_store import get_pinecone_store
from backend.skills.document_ingestion import parse_pdf, parse_csv, hierarchical_chunk, Chunk
from backend.skills.vector_retrieval import embed_and_upsert, semantic_search, RetrievedChunk


def mcp_parse_pdf(file_path: str) -> dict:
    """Extract text and tables from a PDF file."""
    return parse_pdf(file_path)


def mcp_parse_csv(file_path: str) -> dict:
    """Parse and normalize CSV financial data into structured rows."""
    return parse_csv(file_path)


def mcp_embed_chunks(chunks: list) -> dict:
    """Embed text chunks via Gemini Embeddings and upsert to Pinecone."""
    # chunks can be list of Chunk objects or list of dicts
    if chunks and isinstance(chunks[0], dict):
        chunks = [
            Chunk(
                chunk_id=c.get("chunk_id", str(uuid.uuid4())),
                text=c["text"],
                token_count=c.get("token_count", 0),
                metadata=c.get("metadata", {}),
            )
            for c in chunks
        ]
    result = embed_and_upsert(chunks)
    return result


def mcp_pinecone_upsert(vectors: list, metadata: list) -> dict:
    """Store pre-computed embedding vectors with metadata in Pinecone index."""
    store = get_pinecone_store()
    records = []
    for i, (vec, meta) in enumerate(zip(vectors, metadata)):
        records.append({
            "id": meta.get("chunk_id", str(uuid.uuid4())),
            "values": vec,
            "metadata": meta,
        })

    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        store.index.upsert(vectors=batch, namespace=store.namespace)

    return {"upserted_count": len(records)}


def mcp_pinecone_search(query: str, top_k: int = 5, filter_dict: dict = None) -> list:
    """Semantic similarity search on Pinecone index."""
    results = semantic_search(query=query, top_k=top_k, filter_dict=filter_dict)
    return [
        {
            "chunk_id": r.chunk_id,
            "text": r.text,
            "score": r.score,
            "metadata": r.metadata,
        }
        for r in results
    ]


def list_documents_sql(workspace_id: str, session) -> list[dict]:
    """
    List documents in a workspace from SQLite.

    Returns dicts shaped identically to the legacy Redis-backed
    `mcp_list_documents()` output so frontend callers don't change.
    """
    from backend.db.models import Document

    rows = (
        session.query(Document)
        .filter(Document.workspace_id == workspace_id, Document.status == "indexed")
        .order_by(Document.created_at.desc())
        .all()
    )
    return [
        {
            "doc_id": r.id,
            "doc_name": r.name,
            "doc_type": r.doc_type,
            "fiscal_year": r.fiscal_year,
            "chunk_count": r.chunk_count,
            "status": r.status,
        }
        for r in rows
    ]


