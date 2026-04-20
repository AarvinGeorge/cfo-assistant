"""
graph_state.py

TypedDict definition for AgentState — the shared state object that flows
through every node in the LangGraph StateGraph.

Role in project:
    Agent layer — data contract. Every node in orchestrator.py reads from
    and writes to an AgentState instance. LangGraph uses this TypedDict to
    manage state transitions and checkpointing in Redis.

Main parts:
    - AgentState: TypedDict with fields for the conversation thread
      (session_id, messages), multi-tenant context (user_id, workspace_id,
      chat_session_id), routing (intent, requires_retrieval), retrieval
      results (retrieved_chunks, context_string), model outputs
      (model_result, scenario_result), and the final response (response,
      citations, stream_tokens).
"""
from typing import TypedDict, Annotated, Any, Optional
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """State schema for the FinSight CFO Assistant orchestrator graph."""

    # Conversation messages (LangChain message format)
    messages: Annotated[list, add_messages]

    # Current query being processed
    current_query: str

    # Classified intent
    intent: str  # "document_qa" | "financial_model" | "scenario_analysis" | "variance_analysis" | "kpi_summary" | "export_request" | "general_chat"

    # Retrieved context from RAG
    retrieved_chunks: list  # List of RetrievedChunk-like dicts
    formatted_context: str

    # Model/analysis outputs
    model_output: dict  # Output from financial modeling or scenario analysis

    # Agent response
    response: str

    # Session metadata
    session_id: str

    # Multi-tenant context (v1: hardcoded defaults; v2: from auth + workspace switcher)
    user_id: str           # who is asking (v1: "usr_default")
    workspace_id: str      # which workspace's Pinecone namespace to query (v1: "wks_default")
    chat_session_id: str   # the LangGraph thread_id = chat's SQLite session id

    # Audit
    citations: list  # Extracted citations from response
