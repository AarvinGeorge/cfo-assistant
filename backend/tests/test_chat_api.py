"""
test_chat_api.py

Tests that exercise the /chat and /chat/stream FastAPI endpoints end-to-end.

Role in project:
    Test suite — verifies the behaviour of backend.api.routes.chat. Run with:
    pytest tests/test_chat_api.py -v

Coverage:
    - /chat/ returns HTTP 200 and the expected response shape (session_id, response, intent, citations)
    - Auto-generated session IDs are non-empty; caller-supplied session IDs are echoed back unchanged
    - /chat/stream returns a text/event-stream content type with at least "session" and "done" SSE events
    - Graph invocation and all MCP side-effect helpers (memory_write, intent_log, response_logger) are mocked
    - workspace_id and user_id from RequestContext are passed through to the graph state
    - thread_id in the LangGraph config is set to chat_session_id (not the legacy session_id)
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from langchain_core.messages import AIMessage
from backend.api.main import app


def _mock_graph_invoke(input_state, config=None):
    """Mock graph.invoke that returns a realistic response."""
    return {
        "messages": [AIMessage(content="Revenue was $10M. [Source: 10-K, revenue, p.5]")],
        "current_query": input_state.get("current_query", ""),
        "intent": "document_qa",
        "retrieved_chunks": [{"text": "Revenue: $10M", "score": 0.95}],
        "formatted_context": "Context...",
        "model_output": {},
        "response": "Revenue was $10M. [Source: 10-K, revenue, p.5]",
        "citations": ["10-K, revenue, p.5"],
        "session_id": "test-session",
    }


def _mock_graph_stream(input_state, config=None, stream_mode="updates"):
    """Mock graph.stream that yields node updates."""
    yield {"classify_intent": {"intent": "document_qa"}}
    yield {"rag_retrieve": {"retrieved_chunks": [{"text": "data"}], "formatted_context": "ctx"}}
    yield {"generate_response": {"response": "The answer is 42.", "citations": [], "messages": [AIMessage(content="The answer is 42.")]}}


@pytest.fixture
def mock_graph():
    mock = MagicMock()
    mock.invoke = _mock_graph_invoke
    mock.stream = _mock_graph_stream
    return mock


@pytest.mark.asyncio
async def test_chat_returns_200(mock_graph):
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"), \
         patch("backend.api.routes.chat.mcp_memory_write"), \
         patch("backend.api.routes.chat.mcp_intent_log"), \
         patch("backend.api.routes.chat.mcp_response_logger"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/", json={"message": "What is revenue?"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_response_shape(mock_graph):
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"), \
         patch("backend.api.routes.chat.mcp_memory_write"), \
         patch("backend.api.routes.chat.mcp_intent_log"), \
         patch("backend.api.routes.chat.mcp_response_logger"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/", json={"message": "What is revenue?"})
    body = response.json()
    assert "session_id" in body
    assert "response" in body
    assert "intent" in body
    assert "citations" in body


@pytest.mark.asyncio
async def test_chat_generates_session_id(mock_graph):
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"), \
         patch("backend.api.routes.chat.mcp_memory_write"), \
         patch("backend.api.routes.chat.mcp_intent_log"), \
         patch("backend.api.routes.chat.mcp_response_logger"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/", json={"message": "hello"})
    body = response.json()
    assert len(body["session_id"]) > 0


@pytest.mark.asyncio
async def test_chat_uses_provided_session_id(mock_graph):
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"), \
         patch("backend.api.routes.chat.mcp_memory_write"), \
         patch("backend.api.routes.chat.mcp_intent_log"), \
         patch("backend.api.routes.chat.mcp_response_logger"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/", json={"message": "hello", "session_id": "my-session"})
    body = response.json()
    assert body["session_id"] == "my-session"


@pytest.mark.asyncio
async def test_chat_stream_returns_sse(mock_graph):
    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"), \
         patch("backend.api.routes.chat.mcp_memory_write"), \
         patch("backend.api.routes.chat.mcp_intent_log"), \
         patch("backend.api.routes.chat.mcp_response_logger"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/stream", json={"message": "What is revenue?"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Parse SSE events
    events = []
    for line in response.text.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    # Should have session, intent, retrieval, response, done events
    event_types = [e["type"] for e in events]
    assert "session" in event_types
    assert "done" in event_types


@pytest.mark.asyncio
async def test_chat_passes_workspace_id_to_orchestrator(mock_graph):
    """The chat route's invocation should include workspace_id='wks_default' and
    user_id='usr_default' in the graph state, and thread_id should be derived from
    chat_session_id (not the legacy session_id)."""
    captured = {}
    original_invoke = mock_graph.invoke

    def capturing_invoke(state, config=None):
        captured["state"] = state
        captured["config"] = config
        return original_invoke(state, config)

    mock_graph.invoke = capturing_invoke

    with patch("backend.api.routes.chat.build_graph", return_value=mock_graph), \
         patch("backend.api.routes.chat.get_checkpointer"), \
         patch("backend.api.routes.chat.mcp_memory_write"), \
         patch("backend.api.routes.chat.mcp_intent_log"), \
         patch("backend.api.routes.chat.mcp_response_logger"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat/", json={"message": "hi", "session_id": "test-session"})

    assert response.status_code == 200
    assert captured["state"]["workspace_id"] == "wks_default"
    assert captured["state"]["user_id"] == "usr_default"
    assert captured["state"]["chat_session_id"].startswith("ses_default_")
    assert captured["config"]["configurable"]["thread_id"].startswith("ses_default_")
