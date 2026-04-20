"""
test_health.py

Tests that verify the /health endpoint correctly reflects the status of all dependent services.

Role in project:
    Test suite — verifies the behaviour of backend.api.routes.health. Run with:
    pytest tests/test_health.py -v

Coverage:
    - /health returns HTTP 200 and includes status, pinecone, anthropic_key, gemini_key fields
    - /health no longer reports Redis (removed in PR #4)
    - status is "ok" when Pinecone is reachable
    - status is "degraded" when Pinecone is unreachable
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from backend.api.main import app


@pytest.mark.asyncio
async def test_health_returns_200():
    with patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape():
    with patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert "status" in body
    assert "pinecone" in body
    assert "anthropic_key" in body
    assert "gemini_key" in body
    assert "redis" not in body, "Redis field should be gone after PR #4"


@pytest.mark.asyncio
async def test_health_ok_when_pinecone_up():
    with patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["pinecone"] is True
    assert body["anthropic_key"] is True
    assert body["gemini_key"] is True


@pytest.mark.asyncio
async def test_health_degraded_when_pinecone_down():
    with patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = False
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "degraded"
    assert body["pinecone"] is False
