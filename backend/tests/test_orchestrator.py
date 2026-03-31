"""Tests for the LangGraph orchestrator and graph state."""

import sys
from pathlib import Path
from typing import get_type_hints
from unittest.mock import patch, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agents.graph_state import AgentState
from backend.agents.orchestrator import (
    build_graph,
    classify_intent,
    generate_response,
    post_rag_route,
    rag_retrieve,
    route_by_intent,
)


# ── 1. AgentState schema ─────────────────────────────────────────────────────


def test_agent_state_has_expected_keys():
    """Verify all expected keys exist in the AgentState TypedDict."""
    hints = get_type_hints(AgentState, include_extras=True)
    expected_keys = {
        "messages",
        "current_query",
        "intent",
        "retrieved_chunks",
        "formatted_context",
        "model_output",
        "response",
        "session_id",
        "citations",
    }
    assert expected_keys == set(hints.keys())


# ── 2. classify_intent with valid response ───────────────────────────────────


def test_classify_intent_returns_valid_intent():
    """Mock the LLM and verify classify_intent returns a valid intent string."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="document_qa")

    state = {"current_query": "What was Q3 revenue?"}

    with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm):
        result = classify_intent(state)

    assert result["intent"] == "document_qa"
    mock_llm.invoke.assert_called_once()


# ── 3. classify_intent with invalid response ─────────────────────────────────


def test_classify_intent_falls_back_to_general_chat():
    """Verify fallback to general_chat when LLM returns invalid intent."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="some_random_stuff")

    state = {"current_query": "Tell me a joke"}

    with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm):
        result = classify_intent(state)

    assert result["intent"] == "general_chat"


# ── 4. route_by_intent ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "intent,expected_route",
    [
        ("document_qa", "rag_retrieve"),
        ("kpi_summary", "rag_retrieve"),
        ("financial_model", "rag_then_model"),
        ("scenario_analysis", "rag_then_scenario"),
        ("variance_analysis", "rag_then_scenario"),
        ("export_request", "generate_response"),
        ("general_chat", "generate_response"),
    ],
)
def test_route_by_intent(intent, expected_route):
    """Test each intent maps to the correct routing target."""
    state = {"intent": intent}
    assert route_by_intent(state) == expected_route


def test_route_by_intent_defaults_to_generate_response():
    """Missing intent should default to generate_response."""
    state = {}
    assert route_by_intent(state) == "generate_response"


# ── 5. rag_retrieve with mocked search ───────────────────────────────────────


def test_rag_retrieve_returns_chunks_and_context():
    """Mock semantic_search and mmr_rerank, verify chunks and context are set."""
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = "c1"
    mock_chunk.text = "Revenue was $10M"
    mock_chunk.score = 0.95
    mock_chunk.metadata = {"source": "annual_report.pdf"}

    with patch(
        "backend.agents.orchestrator.semantic_search", return_value=[mock_chunk]
    ) as mock_search, patch(
        "backend.agents.orchestrator.mmr_rerank", return_value=[mock_chunk]
    ) as mock_rerank, patch(
        "backend.agents.orchestrator.format_retrieved_context",
        return_value="[1] Revenue was $10M",
    ):
        state = {"current_query": "What was revenue?"}
        result = rag_retrieve(state)

    assert len(result["retrieved_chunks"]) == 1
    assert result["retrieved_chunks"][0]["chunk_id"] == "c1"
    assert result["retrieved_chunks"][0]["text"] == "Revenue was $10M"
    assert result["formatted_context"] == "[1] Revenue was $10M"
    mock_search.assert_called_once_with("What was revenue?", top_k=8)
    mock_rerank.assert_called_once()


# ── 6. rag_retrieve with no documents ────────────────────────────────────────


def test_rag_retrieve_graceful_fallback():
    """Verify graceful fallback when semantic_search raises an exception."""
    with patch(
        "backend.agents.orchestrator.semantic_search",
        side_effect=Exception("No index"),
    ):
        state = {"current_query": "What was revenue?"}
        result = rag_retrieve(state)

    assert result["retrieved_chunks"] == []
    assert result["formatted_context"] == "No documents have been ingested yet."


# ── 7. generate_response ─────────────────────────────────────────────────────


def test_generate_response_extracts_citations():
    """Mock LLM, verify response text and citations are extracted."""
    mock_llm = MagicMock()
    response_text = (
        "Revenue was $10M [Source: annual_report.pdf, Income Statement, p.5] "
        "and EBITDA was $3M [Source: annual_report.pdf, Summary, p.2]."
    )
    mock_llm.invoke.return_value = AIMessage(content=response_text)

    state = {
        "current_query": "What was revenue?",
        "intent": "document_qa",
        "formatted_context": "Revenue context here",
        "model_output": {},
    }

    with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm):
        result = generate_response(state)

    assert result["response"] == response_text
    assert len(result["citations"]) == 2
    assert "annual_report.pdf, Income Statement, p.5" in result["citations"]
    assert "annual_report.pdf, Summary, p.2" in result["citations"]
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)


# ── 8. build_graph compiles ───────────────────────────────────────────────────


def test_build_graph_compiles():
    """Verify the graph compiles without errors (no checkpointer needed)."""
    graph = build_graph(checkpointer=None)
    assert graph is not None


# ── 9. build_graph has expected nodes ─────────────────────────────────────────


def test_build_graph_has_expected_nodes():
    """Verify all expected nodes are present in the compiled graph."""
    graph = build_graph(checkpointer=None)
    node_names = set(graph.get_graph().nodes.keys())
    expected_nodes = {
        "classify_intent",
        "rag_retrieve",
        "financial_model",
        "scenario_analysis",
        "generate_response",
    }
    # LangGraph adds __start__ and __end__ nodes
    assert expected_nodes.issubset(node_names)


# ── 10. post_rag_route ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "intent,expected_route",
    [
        ("financial_model", "financial_model"),
        ("scenario_analysis", "scenario_analysis"),
        ("variance_analysis", "scenario_analysis"),
        ("document_qa", "generate_response"),
        ("kpi_summary", "generate_response"),
        ("general_chat", "generate_response"),
    ],
)
def test_post_rag_route(intent, expected_route):
    """Test routing after RAG for each intent type."""
    state = {"intent": intent}
    assert post_rag_route(state) == expected_route


def test_post_rag_route_defaults_to_generate_response():
    """Missing intent defaults to generate_response."""
    state = {}
    assert post_rag_route(state) == "generate_response"
