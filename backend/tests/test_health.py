import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from backend.api.main import app


@pytest.mark.asyncio
async def test_health_returns_200():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert "status" in body
    assert "redis" in body
    assert "pinecone" in body
    assert "anthropic_key" in body
    assert "gemini_key" in body


@pytest.mark.asyncio
async def test_health_ok_when_all_services_up():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["redis"] is True
    assert body["pinecone"] is True
    assert body["anthropic_key"] is True
    assert body["gemini_key"] is True


@pytest.mark.asyncio
async def test_health_degraded_when_redis_down():
    with patch("backend.api.routes.health.ping_redis", return_value=False), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "degraded"
    assert body["redis"] is False


@pytest.mark.asyncio
async def test_health_degraded_when_pinecone_down():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = False
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "degraded"
    assert body["pinecone"] is False
