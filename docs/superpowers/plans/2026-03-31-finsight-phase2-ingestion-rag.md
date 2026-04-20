# FinSight Phase 2: Ingestion & RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the document ingestion pipeline and RAG retrieval system — parse PDFs/CSVs, chunk with rich metadata, embed via Gemini, store in Pinecone, and retrieve with MMR reranking.

**Architecture:** Two skill modules (`document_ingestion.py` for parsing/chunking, `vector_retrieval.py` for search/reranking) provide the business logic. The MCP tool stubs in `document_tools.py` become thin wrappers calling these skills. Document metadata is tracked in Redis as a simple JSON list.

**Tech Stack:** pdfplumber, pandas, tiktoken (for token counting), Gemini embeddings (existing client), Pinecone (existing store), Redis (existing client)

---

## File Map

```
backend/
├── skills/
│   ├── __init__.py
│   ├── document_ingestion.py    # PDF/CSV parsing + hierarchical chunking
│   └── vector_retrieval.py      # Semantic search + MMR reranking
├── mcp_server/tools/
│   └── document_tools.py        # MODIFY: replace stubs with real implementations
├── api/routes/
│   └── documents.py             # NEW: upload + list endpoints
├── api/main.py                  # MODIFY: add documents router
└── tests/
    ├── test_document_ingestion.py
    ├── test_vector_retrieval.py
    └── test_document_tools_integration.py
```
