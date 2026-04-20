"""
test_chat_fixes.py

Tests that verify secure error handling in the SSE streaming chat endpoint.

Role in project:
    Test suite — verifies the behaviour of backend.api.routes.chat SSE error paths. Run with:
    pytest tests/test_chat_fixes.py -v

Coverage:
    - SSE error events must not leak internal details such as Redis URLs, hostnames, or passwords
    - Error events must always surface a generic user-friendly message to the caller
    - The synchronous /chat/ endpoint continues to work correctly after async streaming changes were introduced
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from langchain_core.messages import AIMessage
from backend.api.main import app


def _mock_graph_invoke(input_state, config=None):
    return {
        "messages": [AIMessage(content="test response")],
        "current_query": input_state.get("current_query", ""),
        "intent": "general_chat",
        "retrieved_chunks": [],
        "formatted_context": "",
        "model_output": {},
        "response": "test response",
        "citations": [],
        "session_id": "test",
    }


def _mock_graph_stream_error(input_state, config=None, stream_mode="updates"):
    raise ValueError("Internal error: database connection to redis://localhost:6379 failed with password=secret123")


@pytest.mark.asyncio
async def test_sse_error_does_not_leak_internals():
    """SSE error events should not contain internal details like URLs or passwords."""
    mock_graph = MagicMock()
    mock_graph.stream = _mock_graph_stream_error
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/stream", json={"message": "hello"})

    events = []
    for line in response.text.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) > 0, "Expected at least one error event"
    for event in error_events:
        msg = event.get("message", "")
        assert "redis" not in msg.lower(), f"Error leaks 'redis': {msg}"
        assert "password" not in msg.lower(), f"Error leaks 'password': {msg}"
        assert "localhost" not in msg.lower(), f"Error leaks 'localhost': {msg}"
        assert "internal error" in msg.lower() or "try again" in msg.lower()


@pytest.mark.asyncio
async def test_sse_generic_error_message():
    """SSE errors should return a generic user-friendly message."""
    mock_graph = MagicMock()
    mock_graph.stream = _mock_graph_stream_error
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/stream", json={"message": "hello"})

    events = []
    for line in response.text.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    error_events = [e for e in events if e.get("type") == "error"]
    assert error_events[0]["message"] == "An internal error occurred. Please try again."


@pytest.mark.asyncio
async def test_chat_sync_endpoint_still_works():
    """The /chat endpoint should still work after async changes."""
    mock_graph = MagicMock()
    mock_graph.invoke = _mock_graph_invoke
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"), \
         patch("backend.api.routes.chat.mcp_intent_log"), \
         patch("backend.api.routes.chat.mcp_response_logger"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/", json={"message": "test"})
    assert response.status_code == 200
    assert response.json()["response"] == "test response"
