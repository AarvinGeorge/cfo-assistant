import json
import pytest
from unittest.mock import patch, MagicMock
from backend.mcp_server.tools.document_tools import (
    mcp_parse_pdf, mcp_parse_csv, mcp_embed_chunks,
    mcp_pinecone_search, mcp_list_documents,
    register_document, delete_document,
    DOCS_REDIS_KEY,
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


def _make_mock_redis_with_pipe():
    """Helper: returns (mock_redis, mock_pipe) with pipeline context manager wired up."""
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.__enter__ = MagicMock(return_value=mock_pipe)
    mock_pipe.__exit__ = MagicMock(return_value=False)
    mock_redis.pipeline.return_value = mock_pipe
    return mock_redis, mock_pipe


class TestDocumentTracking:
    def test_register_and_list(self):
        mock_redis, mock_pipe = _make_mock_redis_with_pipe()
        mock_redis.get.return_value = None
        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis):
            register_document({"doc_id": "abc", "doc_name": "test.pdf"}, chunk_count=10)
            # Verify set was called on the pipeline with correct JSON
            call_args = mock_pipe.set.call_args
            assert call_args[0][0] == DOCS_REDIS_KEY
            docs = json.loads(call_args[0][1])
            assert len(docs) == 1
            assert docs[0]["doc_id"] == "abc"
            assert docs[0]["chunk_count"] == 10

    def test_list_empty(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis):
            result = mcp_list_documents()
            assert result == []

    def test_list_with_docs(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps([{"doc_id": "abc", "doc_name": "test.pdf"}])
        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis):
            result = mcp_list_documents()
            assert len(result) == 1

    def test_delete_document(self):
        mock_redis, mock_pipe = _make_mock_redis_with_pipe()
        mock_redis.get.return_value = json.dumps([{"doc_id": "abc"}, {"doc_id": "def"}])
        mock_store = MagicMock()
        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis), \
             patch("backend.mcp_server.tools.document_tools.get_pinecone_store", return_value=mock_store):
            result = delete_document("abc")
            assert result is True
            stored = json.loads(mock_pipe.set.call_args[0][1])
            assert len(stored) == 1
            assert stored[0]["doc_id"] == "def"

    def test_delete_nonexistent(self):
        mock_redis, mock_pipe = _make_mock_redis_with_pipe()
        mock_redis.get.return_value = json.dumps([{"doc_id": "abc"}])
        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis):
            result = delete_document("xyz")
            assert result is False
