import re

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.agents.graph_state import AgentState
from backend.core.config import get_settings
from backend.skills.vector_retrieval import (
    semantic_search,
    mmr_rerank,
    format_retrieved_context,
)
from backend.skills.financial_modeling import (
    extract_financials,
    build_dcf_model,
    build_ratio_scorecard,
    build_forecast_model,
    build_variance_analysis,
)
from backend.skills.scenario_analysis import (
    run_scenario_matrix,
    build_sensitivity_table,
    calculate_cash_runway,
    stress_test_covenants,
)


def get_llm():
    settings = get_settings()
    return ChatAnthropic(
        model=settings.claude_model,
        api_key=settings.anthropic_api_key,
        max_tokens=settings.claude_max_tokens,
        temperature=settings.claude_temperature,
    )


# ── Node: Classify Intent ─────────────────────────────────────────────────────


def classify_intent(state: AgentState) -> dict:
    """Classify user query into an intent category using Claude."""
    llm = get_llm()

    query = state["current_query"]

    classification_prompt = SystemMessage(
        content="""You are an intent classifier for a CFO financial assistant. Classify the user's query into exactly one of these categories:

- document_qa: Questions about financial documents, performance, specific figures, trends
- financial_model: Requests to build DCF models, ratio analysis, forecasts
- scenario_analysis: What-if analysis, sensitivity, runway, covenant checks
- variance_analysis: Comparing actuals vs budget, period-over-period comparisons
- kpi_summary: Requests for KPI dashboards, key metrics overview
- export_request: Requests to generate reports, export to Excel/PDF
- general_chat: General questions, greetings, help requests

Respond with ONLY the category name, nothing else."""
    )

    response = llm.invoke([classification_prompt, HumanMessage(content=query)])
    intent = response.content.strip().lower().replace(" ", "_")

    # Validate intent
    valid_intents = {
        "document_qa",
        "financial_model",
        "scenario_analysis",
        "variance_analysis",
        "kpi_summary",
        "export_request",
        "general_chat",
    }
    if intent not in valid_intents:
        intent = "general_chat"

    return {"intent": intent}


# ── Node: RAG Retrieval ───────────────────────────────────────────────────────


def rag_retrieve(state: AgentState) -> dict:
    """Retrieve relevant document chunks for the query."""
    query = state["current_query"]

    try:
        candidates = semantic_search(query, top_k=8)
        reranked = mmr_rerank(query, candidates, top_k=5)

        chunks_as_dicts = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "score": c.score,
                "metadata": c.metadata,
            }
            for c in reranked
        ]
        context = format_retrieved_context(reranked)
    except Exception:
        chunks_as_dicts = []
        context = "No documents have been ingested yet."

    return {
        "retrieved_chunks": chunks_as_dicts,
        "formatted_context": context,
    }


# ── Node: Financial Modeling ──────────────────────────────────────────────────


def financial_model_node(state: AgentState) -> dict:
    """Use Claude to interpret the query and run appropriate financial model."""
    llm = get_llm()
    query = state["current_query"]
    context = state.get("formatted_context", "")

    # Ask Claude to determine model type and extract parameters
    model_prompt = SystemMessage(
        content=f"""You are a financial modeling assistant. Based on the user's query and the available financial data, determine which model to run and extract the parameters.

Available models:
1. DCF (requires: revenue, ebit, wacc, terminal_growth)
2. Ratio Scorecard (requires: income_statement and balance_sheet data)
3. Forecast (requires: historical_series with at least 2 years)
4. Variance Analysis (requires: actuals and budget dicts)

Available financial context:
{context}

Respond with a JSON object:
{{"model_type": "dcf|ratios|forecast|variance", "parameters": {{...extracted parameters...}}, "explanation": "brief explanation of what you're computing"}}

If you cannot extract sufficient parameters from the context, respond with:
{{"model_type": "insufficient_data", "missing": ["list of what's needed"], "explanation": "what's missing"}}"""
    )

    response = llm.invoke([model_prompt, HumanMessage(content=query)])

    return {
        "model_output": {"type": "financial_model", "llm_response": response.content},
    }


# ── Node: Scenario Analysis ──────────────────────────────────────────────────


def scenario_node(state: AgentState) -> dict:
    """Handle scenario analysis, sensitivity, runway, and covenant queries."""
    llm = get_llm()
    query = state["current_query"]
    context = state.get("formatted_context", "")

    scenario_prompt = SystemMessage(
        content=f"""You are a scenario analysis assistant. Based on the user's query and available data, determine the analysis type.

Available analyses:
1. Scenario Matrix (bull/base/bear cases)
2. Sensitivity Table (vary two inputs)
3. Cash Runway (cash balance / burn rate)
4. Covenant Check (test against thresholds)

Available financial context:
{context}

Respond with a JSON object describing the analysis to run and the parameters extracted from context."""
    )

    response = llm.invoke([scenario_prompt, HumanMessage(content=query)])

    return {
        "model_output": {"type": "scenario_analysis", "llm_response": response.content},
    }


# ── Node: Generate Response ───────────────────────────────────────────────────


def generate_response(state: AgentState) -> dict:
    """Generate the final CFO-ready response with citations."""
    llm = get_llm()
    query = state["current_query"]
    intent = state.get("intent", "general_chat")
    context = state.get("formatted_context", "")
    model_output = state.get("model_output", {})

    system_content = """You are FinSight, an AI financial assistant for a Chief Financial Officer.

Rules:
1. Every numerical claim MUST include a citation: [Source: document_name, section, page]
2. Be precise with numbers — never round without stating you've rounded
3. If data is insufficient, explicitly say so rather than guessing
4. Format responses professionally — use tables for comparisons, bullet points for lists
5. Flag any caveats or assumptions clearly"""

    user_content_parts = [f"Query: {query}"]

    if context and context != "No documents have been ingested yet.":
        user_content_parts.append(f"\nRetrieved Financial Context:\n{context}")

    if model_output:
        user_content_parts.append(f"\nModel/Analysis Output:\n{model_output}")

    user_content_parts.append(f"\nIntent: {intent}")
    user_content_parts.append("\nProvide a clear, cited, CFO-appropriate response.")

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content="\n".join(user_content_parts)),
    ]

    response = llm.invoke(messages)
    response_text = response.content

    # Extract citations from response
    citations = re.findall(r"\[Source: ([^\]]+)\]", response_text)

    return {
        "response": response_text,
        "citations": citations,
        "messages": [AIMessage(content=response_text)],
    }


# ── Routing Logic ─────────────────────────────────────────────────────────────


def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate agent node based on classified intent."""
    intent = state.get("intent", "general_chat")

    if intent in ("document_qa", "kpi_summary"):
        return "rag_retrieve"
    elif intent == "financial_model":
        return "rag_then_model"
    elif intent in ("scenario_analysis", "variance_analysis"):
        return "rag_then_scenario"
    elif intent == "export_request":
        return "generate_response"
    else:  # general_chat
        return "generate_response"


def post_rag_route(state: AgentState) -> str:
    """Route after RAG retrieval based on original intent."""
    intent = state.get("intent", "general_chat")
    if intent == "financial_model":
        return "financial_model"
    elif intent in ("scenario_analysis", "variance_analysis"):
        return "scenario_analysis"
    else:
        return "generate_response"


# ── Build the Graph ───────────────────────────────────────────────────────────


def build_graph(checkpointer=None):
    """Build and compile the orchestrator StateGraph."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("rag_retrieve", rag_retrieve)
    builder.add_node("financial_model", financial_model_node)
    builder.add_node("scenario_analysis", scenario_node)
    builder.add_node("generate_response", generate_response)

    # Entry point
    builder.set_entry_point("classify_intent")

    # Conditional routing after intent classification
    builder.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "rag_retrieve": "rag_retrieve",
            "rag_then_model": "rag_retrieve",
            "rag_then_scenario": "rag_retrieve",
            "generate_response": "generate_response",
        },
    )

    # After RAG retrieval, route based on original intent
    builder.add_conditional_edges(
        "rag_retrieve",
        post_rag_route,
        {
            "financial_model": "financial_model",
            "scenario_analysis": "scenario_analysis",
            "generate_response": "generate_response",
        },
    )

    # After modeling/scenario, always generate response
    builder.add_edge("financial_model", "generate_response")
    builder.add_edge("scenario_analysis", "generate_response")

    # End after response generation
    builder.add_edge("generate_response", END)

    # Compile with checkpointer
    return builder.compile(checkpointer=checkpointer)


def get_checkpointer():
    """Create a Redis-backed checkpointer for conversation persistence."""
    settings = get_settings()
    redis_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
    return RedisSaver.from_conn_string(redis_url)


def get_compiled_graph():
    """Get the compiled graph with Redis checkpointer."""
    checkpointer = get_checkpointer()
    return build_graph(checkpointer=checkpointer)
