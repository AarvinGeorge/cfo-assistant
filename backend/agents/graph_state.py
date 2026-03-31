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

    # Audit
    citations: list  # Extracted citations from response
