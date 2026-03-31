def mcp_parse_pdf(file_path: str) -> str:
    """Extract text and tables from a PDF file."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_parse_csv(file_path: str) -> str:
    """Parse and normalize CSV financial data into structured rows."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_embed_chunks(chunks: list) -> list:
    """Embed text chunks via Gemini Embeddings and return vectors."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_pinecone_upsert(vectors: list, metadata: list) -> dict:
    """Store embedding vectors with metadata in Pinecone index."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_pinecone_search(query_vector: list, top_k: int = 5) -> list:
    """Semantic similarity search on Pinecone index."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_list_documents() -> list:
    """List all ingested documents with metadata."""
    raise NotImplementedError("Implemented in Phase 2")
