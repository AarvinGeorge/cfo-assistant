"""
test_documents_security.py

Tests that verify the document upload endpoint enforces filename sanitisation and file-size limits.

Role in project:
    Test suite — verifies the behaviour of backend.api.routes.documents upload security. Run with:
    pytest tests/test_documents_security.py -v

Coverage:
    - Path-traversal filenames (e.g. ../../etc/passwd.pdf) have directory components stripped on upload
    - Filenames that attempt to overwrite sensitive files (e.g. ../../../backend/.env.csv) are sanitised
    - Files exceeding 50 MB are rejected with HTTP 400 and a message containing "50MB"
    - Normal, well-formed uploads continue to succeed and return the expected doc_name and chunk_count
"""

import io
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from backend.api.main import app


def _make_chunk_mock(chunk_id: str = "chunk_abc123") -> MagicMock:
    """Return a MagicMock shaped like a Chunk dataclass."""
    chunk = MagicMock()
    chunk.chunk_id = chunk_id
    chunk.text = "test text"
    chunk.token_count = 10
    chunk.metadata = {"doc_id": "doc_test", "doc_type": "general"}
    return chunk


def _session_factory_mock() -> MagicMock:
    """Return a mock sessionmaker whose context-manager session finds no existing doc."""
    session_mock = MagicMock()
    session_mock.execute.return_value.scalar_one_or_none.return_value = None
    session_mock.add = MagicMock()
    session_mock.commit = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)

    factory_mock = MagicMock(return_value=session_mock)
    return factory_mock


def _pinecone_store_mock() -> MagicMock:
    """Return a mock PineconeStore with an index that accepts upsert/delete."""
    store = MagicMock()
    store.index = MagicMock()
    store.index.upsert = MagicMock()
    store.index.delete = MagicMock()
    return store


def _gemini_mock(num_chunks: int = 1) -> MagicMock:
    """Return a mock GeminiClient whose embed_texts returns float vectors."""
    gemini = MagicMock()
    gemini.embed_texts.return_value = [[0.1] * 10 for _ in range(num_chunks)]
    return gemini


@pytest.mark.asyncio
async def test_path_traversal_sanitized():
    """Crafted filename with ../ should have path components stripped."""
    file_content = b"%PDF-1.4 fake pdf content"
    chunk_mock = _make_chunk_mock()

    with patch("backend.api.routes.documents.parse_pdf") as mock_parse, \
         patch("backend.api.routes.documents.hierarchical_chunk", return_value=[chunk_mock]), \
         patch("backend.api.routes.documents.GeminiClient", return_value=_gemini_mock(1)), \
         patch("backend.api.routes.documents.get_session_factory", return_value=_session_factory_mock()), \
         patch("backend.api.routes.documents.get_pinecone_store", return_value=_pinecone_store_mock()), \
         patch("backend.api.routes.documents.StorageTransaction") as mock_tx_cls:
        mock_tx = MagicMock()
        mock_tx.__enter__ = MagicMock(return_value=mock_tx)
        mock_tx.__exit__ = MagicMock(return_value=False)
        mock_tx_cls.return_value = mock_tx

        mock_parse.return_value = {
            "pages": [{"page_number": 1, "text": "test", "tables": []}],
            "full_text": "test",
            "table_count": 0,
            "page_count": 1,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents/upload",
                files={"file": ("../../etc/passwd.pdf", io.BytesIO(file_content), "application/pdf")},
                data={"doc_type": "general"},
            )
    assert response.status_code == 200
    assert response.json()["doc_name"] == "passwd.pdf"


@pytest.mark.asyncio
async def test_dotdot_env_filename_sanitized():
    """Filename attempting to overwrite .env should be sanitized."""
    file_content = b"col1,col2\n1,2"
    chunk_mock = _make_chunk_mock()

    with patch("backend.api.routes.documents.parse_csv") as mock_parse, \
         patch("backend.api.routes.documents.hierarchical_chunk", return_value=[chunk_mock]), \
         patch("backend.api.routes.documents.GeminiClient", return_value=_gemini_mock(1)), \
         patch("backend.api.routes.documents.get_session_factory", return_value=_session_factory_mock()), \
         patch("backend.api.routes.documents.get_pinecone_store", return_value=_pinecone_store_mock()), \
         patch("backend.api.routes.documents.StorageTransaction") as mock_tx_cls:
        mock_tx = MagicMock()
        mock_tx.__enter__ = MagicMock(return_value=mock_tx)
        mock_tx.__exit__ = MagicMock(return_value=False)
        mock_tx_cls.return_value = mock_tx

        mock_parse.return_value = {
            "rows": [{"col1": "1", "col2": "2"}],
            "columns": ["col1", "col2"],
            "row_count": 1,
            "full_text": "1 2",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents/upload",
                files={"file": ("../../../backend/.env.csv", io.BytesIO(file_content), "text/csv")},
                data={"doc_type": "general"},
            )
    assert response.status_code == 200
    assert response.json()["doc_name"] == ".env.csv"


@pytest.mark.asyncio
async def test_oversized_file_rejected():
    """Files exceeding 50MB should be rejected."""
    # 50MB + 1 byte
    large_content = b"x" * (50 * 1024 * 1024 + 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/documents/upload",
            files={"file": ("big.pdf", io.BytesIO(large_content), "application/pdf")},
            data={"doc_type": "general"},
        )
    assert response.status_code == 400
    assert "50MB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_normal_upload_still_works():
    """Verify normal uploads are not broken by security changes."""
    file_content = b"%PDF-1.4 test content"
    chunks = [_make_chunk_mock(f"chunk_{i}") for i in range(5)]

    with patch("backend.api.routes.documents.parse_pdf") as mock_parse, \
         patch("backend.api.routes.documents.hierarchical_chunk", return_value=chunks), \
         patch("backend.api.routes.documents.GeminiClient", return_value=_gemini_mock(5)), \
         patch("backend.api.routes.documents.get_session_factory", return_value=_session_factory_mock()), \
         patch("backend.api.routes.documents.get_pinecone_store", return_value=_pinecone_store_mock()), \
         patch("backend.api.routes.documents.StorageTransaction") as mock_tx_cls:
        mock_tx = MagicMock()
        mock_tx.__enter__ = MagicMock(return_value=mock_tx)
        mock_tx.__exit__ = MagicMock(return_value=False)
        mock_tx_cls.return_value = mock_tx

        mock_parse.return_value = {
            "pages": [{"page_number": 1, "text": "revenue", "tables": []}],
            "full_text": "revenue",
            "table_count": 0,
            "page_count": 1,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents/upload",
                files={"file": ("quarterly_report.pdf", io.BytesIO(file_content), "application/pdf")},
                data={"doc_type": "10-K", "fiscal_year": "2024"},
            )
    assert response.status_code == 200
    body = response.json()
    assert body["doc_name"] == "quarterly_report.pdf"
    assert body["chunk_count"] == 5
