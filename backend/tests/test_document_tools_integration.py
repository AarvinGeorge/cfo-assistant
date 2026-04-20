"""
test_document_tools_integration.py

Tests that verify the MCP document tool wrappers delegate correctly to
their underlying skills, and the SQLite-backed list_documents_sql
correctly scopes results by workspace.

Role in project:
    Test suite — verifies the behaviour of
    backend.mcp_server.tools.document_tools. Run with:
    pytest tests/test_document_tools_integration.py -v

Coverage:
    - mcp_parse_pdf and mcp_parse_csv each call the corresponding skill function exactly once
    - mcp_embed_chunks delegates to embed_and_upsert and handles both Chunk objects and plain dicts
    - mcp_pinecone_search returns serialisable results converted from RetrievedChunk dataclasses
    - list_documents_sql scopes to one workspace and hides non-indexed docs
"""

from unittest.mock import patch, MagicMock
from backend.mcp_server.tools.document_tools import (
    mcp_parse_pdf, mcp_parse_csv, mcp_embed_chunks, mcp_pinecone_search,
)


class TestMcpParsePdf:
    def test_calls_parse_pdf(self):
        with patch("backend.mcp_server.tools.document_tools.parse_pdf") as mock:
            mock.return_value = {"pages": [], "full_text": "", "table_count": 0, "page_count": 0}
            result = mcp_parse_pdf("/some/file.pdf")
            mock.assert_called_once_with("/some/file.pdf")
            assert result["page_count"] == 0


class TestMcpParseCsv:
    def test_calls_parse_csv(self):
        with patch("backend.mcp_server.tools.document_tools.parse_csv") as mock:
            mock.return_value = {"rows": [], "columns": [], "row_count": 0, "full_text": ""}
            result = mcp_parse_csv("/some/file.csv")
            mock.assert_called_once_with("/some/file.csv")


class TestMcpEmbedChunks:
    def test_delegates_to_embed_and_upsert(self):
        with patch("backend.mcp_server.tools.document_tools.embed_and_upsert") as mock:
            mock.return_value = {"upserted_count": 5, "doc_id": "abc"}
            from backend.skills.document_ingestion import Chunk
            chunks = [Chunk(chunk_id="1", text="test", token_count=1, metadata={"doc_id": "abc"})]
            result = mcp_embed_chunks(chunks)
            assert result["upserted_count"] == 5

    def test_handles_dict_chunks(self):
        with patch("backend.mcp_server.tools.document_tools.embed_and_upsert") as mock:
            mock.return_value = {"upserted_count": 2, "doc_id": "abc"}
            chunks = [{"text": "hello", "metadata": {"doc_id": "abc"}}]
            result = mcp_embed_chunks(chunks)
            assert result["upserted_count"] == 2


class TestMcpPineconeSearch:
    def test_returns_serializable_results(self):
        with patch("backend.mcp_server.tools.document_tools.semantic_search") as mock:
            from backend.skills.vector_retrieval import RetrievedChunk
            mock.return_value = [
                RetrievedChunk(chunk_id="1", text="revenue was 1M", score=0.95, metadata={"doc_name": "10k.pdf"})
            ]
            results = mcp_pinecone_search("what is revenue?", top_k=1)
            assert len(results) == 1
            assert results[0]["text"] == "revenue was 1M"
            assert results[0]["score"] == 0.95


# ── list_documents_sql (SQL-backed; replaces the deleted mcp_list_documents) ──


def test_list_documents_sql_returns_workspace_docs_only():
    """SQL-backed list filters to one workspace; doesn't leak across workspaces."""
    from backend.db.engine import create_engine_for_url, make_session_factory
    from backend.db.models import Base, User, Workspace, Document
    from backend.mcp_server.tools.document_tools import list_documents_sql

    engine = create_engine_for_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as s:
        s.add_all([
            User(id="usr_a", email="a@x.com", display_name="A"),
            Workspace(id="wks_a", owner_id="usr_a", name="A"),
            Workspace(id="wks_b", owner_id="usr_a", name="B"),
            Document(id="doc_1", workspace_id="wks_a", user_id="usr_a",
                     name="A.pdf", chunk_count=10, status="indexed"),
            Document(id="doc_2", workspace_id="wks_b", user_id="usr_a",
                     name="B.pdf", chunk_count=20, status="indexed"),
        ])
        s.commit()
        result = list_documents_sql("wks_a", s)

    assert len(result) == 1
    assert result[0]["doc_id"] == "doc_1"
    assert result[0]["chunk_count"] == 10


def test_list_documents_sql_hides_non_indexed_status():
    """Documents with status != 'indexed' should be excluded."""
    from backend.db.engine import create_engine_for_url, make_session_factory
    from backend.db.models import Base, User, Workspace, Document
    from backend.mcp_server.tools.document_tools import list_documents_sql

    engine = create_engine_for_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as s:
        s.add_all([
            User(id="usr_a", email=None, display_name="A"),
            Workspace(id="wks_a", owner_id="usr_a", name="A"),
            Document(id="doc_ok", workspace_id="wks_a", user_id="usr_a",
                     name="ok.pdf", chunk_count=5, status="indexed"),
            Document(id="doc_fail", workspace_id="wks_a", user_id="usr_a",
                     name="fail.pdf", chunk_count=0, status="failed"),
        ])
        s.commit()
        result = list_documents_sql("wks_a", s)

    assert len(result) == 1
    assert result[0]["doc_id"] == "doc_ok"
