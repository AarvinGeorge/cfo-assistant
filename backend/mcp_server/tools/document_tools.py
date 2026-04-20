"""
document_tools.py

MCP tool implementations for document search and retrieval operations.

Role in project:
    MCP layer — thin wrappers around vector_retrieval.py that expose
    document search capabilities as callable MCP tools. Claude invokes
    these during response generation to fetch cited source material.

Main parts:
    - mcp_search_documents(): semantic search across all indexed chunks.
    - mcp_get_document_list(): returns metadata for all ingested documents.
    - mcp_get_document_chunk(): fetches a specific chunk by ID.
    - mcp_citation_validator(): verifies that a [Source: ...] citation
      exists in the indexed documents before including it in a response.
    - mcp_get_fiscal_years(): returns all fiscal years present in the index.
"""

import json
import uuid
from typing import List, Dict, Any, Optional

from backend.core.config import get_settings
from backend.core.redis_client import get_redis_client
from backend.core.gemini_client import GeminiClient
from backend.core.pinecone_store import get_pinecone_store
from backend.skills.document_ingestion import parse_pdf, parse_csv, hierarchical_chunk, Chunk
from backend.skills.vector_retrieval import embed_and_upsert, semantic_search, RetrievedChunk


DOCS_REDIS_KEY = "finsight:documents"


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


def mcp_list_documents() -> list:
    """List all ingested documents with metadata. (Redis-backed; DEPRECATED after PR #4.)"""
    redis_client = get_redis_client()
    docs_json = redis_client.get(DOCS_REDIS_KEY)
    if not docs_json:
        return []
    return json.loads(docs_json)


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


def register_document(doc_metadata: dict, chunk_count: int) -> None:
    """Track an ingested document in Redis using a pipeline for atomicity."""
    redis_client = get_redis_client()

    with redis_client.pipeline() as pipe:
        pipe.watch(DOCS_REDIS_KEY)
        docs_json = redis_client.get(DOCS_REDIS_KEY)
        docs = json.loads(docs_json) if docs_json else []

        doc_entry = {
            **doc_metadata,
            "chunk_count": chunk_count,
            "status": "indexed",
        }

        existing_idx = next(
            (i for i, d in enumerate(docs) if d.get("doc_id") == doc_metadata.get("doc_id")),
            None,
        )
        if existing_idx is not None:
            docs[existing_idx] = doc_entry
        else:
            docs.append(doc_entry)

        pipe.multi()
        pipe.set(DOCS_REDIS_KEY, json.dumps(docs))
        pipe.execute()


def delete_document(doc_id: str) -> bool:
    """Remove a document from tracking list and vectors, using pipeline for atomicity."""
    redis_client = get_redis_client()

    with redis_client.pipeline() as pipe:
        pipe.watch(DOCS_REDIS_KEY)
        docs_json = redis_client.get(DOCS_REDIS_KEY)
        if not docs_json:
            return False

        docs = json.loads(docs_json)
        new_docs = [d for d in docs if d.get("doc_id") != doc_id]

        if len(new_docs) == len(docs):
            return False

        pipe.multi()
        pipe.set(DOCS_REDIS_KEY, json.dumps(new_docs))
        pipe.execute()

    # Delete vectors from Pinecone (outside pipeline — separate service)
    store = get_pinecone_store()
    store.index.delete(filter={"doc_id": doc_id}, namespace=store.namespace)

    return True
