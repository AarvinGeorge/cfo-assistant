import io
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from backend.api.main import app


@pytest.mark.asyncio
async def test_path_traversal_sanitized():
    """Crafted filename with ../ should have path components stripped."""
    file_content = b"%PDF-1.4 fake pdf content"
    with patch("backend.api.routes.documents.parse_pdf") as mock_parse, \
         patch("backend.api.routes.documents.hierarchical_chunk", return_value=[MagicMock()]), \
         patch("backend.api.routes.documents.embed_and_upsert", return_value={"upserted_count": 1}), \
         patch("backend.api.routes.documents.register_document"):
        mock_parse.return_value = {"pages": [{"page_number": 1, "text": "test", "tables": []}], "full_text": "test", "table_count": 0, "page_count": 1}
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
    with patch("backend.api.routes.documents.parse_csv") as mock_parse, \
         patch("backend.api.routes.documents.hierarchical_chunk", return_value=[MagicMock()]), \
         patch("backend.api.routes.documents.embed_and_upsert", return_value={"upserted_count": 1}), \
         patch("backend.api.routes.documents.register_document"):
        mock_parse.return_value = {"rows": [{"col1": "1", "col2": "2"}], "columns": ["col1", "col2"], "row_count": 1, "full_text": "1 2"}
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
    with patch("backend.api.routes.documents.parse_pdf") as mock_parse, \
         patch("backend.api.routes.documents.hierarchical_chunk", return_value=[MagicMock()]), \
         patch("backend.api.routes.documents.embed_and_upsert", return_value={"upserted_count": 5}), \
         patch("backend.api.routes.documents.register_document"):
        mock_parse.return_value = {"pages": [{"page_number": 1, "text": "revenue", "tables": []}], "full_text": "revenue", "table_count": 0, "page_count": 1}
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
