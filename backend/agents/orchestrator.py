"""
orchestrator.py

LangGraph StateGraph that routes every chat message through the correct
processing pipeline and streams the response back to the API layer.

Role in project:
    Agent layer — the brain of FinSight. Called by the /chat and
    /chat/stream route handlers. Receives an AgentState, runs it through
    7 nodes with conditional branching, and returns a fully populated state
    containing the assistant response and citations.

Main parts:
    - build_graph(): constructs and compiles the StateGraph with all nodes
      and conditional edges. Returns a compiled graph ready for invocation.
    - classify_intent node: uses Claude to classify the query into one of 7
      intent categories (document_qa, financial_model, scenario_analysis,
      general_chat, etc.).
    - rag_retrieve node: embeds the query via Gemini, searches Pinecone,
      and applies MMR reranking to return the top-5 most relevant chunks.
    - financial_model_node: extracts parameters from context and runs the
      appropriate financial model (DCF, ratios, forecast, or variance).
    - scenario_analysis_node: runs bull/base/bear scenarios, sensitivity
      tables, covenant stress tests, or runway calculations.
    - response_generator node: prompts Claude with retrieved context and
      model outputs to produce a cited, markdown-formatted answer.
    - response_extraction node: collects the full streamed response,
      extracts [Source: ...] citation tags, and runs citation validation.
"""
import json
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
from backend.mcp_server.tools.memory_tools import mcp_citation_validator


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
    """Use Claude to extract parameters, then run the actual financial model."""
    llm = get_llm()
    query = state["current_query"]
    context = state.get("formatted_context", "")

    model_prompt = SystemMessage(
        content=f"""You are a financial modeling assistant. Based on the user's query and the available financial data, determine which model to run and extract the parameters.

Available models:
1. DCF (requires: revenue, ebit, wacc, terminal_growth)
2. Ratio Scorecard (requires: income_statement and balance_sheet data as nested dicts)
3. Forecast (requires: historical_series dict with lists of values)
4. Variance Analysis (requires: actuals and budget dicts)

Available financial context:
{context}

Respond with ONLY a valid JSON object (no markdown, no explanation outside JSON):
{{"model_type": "dcf|ratios|forecast|variance", "parameters": {{...extracted parameters...}}, "explanation": "brief explanation"}}

If you cannot extract sufficient parameters, respond with:
{{"model_type": "insufficient_data", "missing": ["list of what's needed"], "explanation": "what's missing"}}"""
    )

    response = llm.invoke([model_prompt, HumanMessage(content=query)])

    try:
        # Strip any markdown code fences Claude might add
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {"model_output": {"type": "error", "message": "Could not parse model parameters from context", "raw": response.content}}

    model_type = parsed.get("model_type", "insufficient_data")
    params = parsed.get("parameters", {})
    explanation = parsed.get("explanation", "")

    if model_type == "insufficient_data":
        return {"model_output": {"type": "insufficient_data", "missing": parsed.get("missing", []), "explanation": explanation}}

    try:
        if model_type == "dcf":
            result = build_dcf_model(params)
        elif model_type == "ratios":
            result = build_ratio_scorecard(params)
        elif model_type == "forecast":
            historical = params.get("historical_series", params)
            horizon = params.get("horizon", 3)
            result = build_forecast_model(historical, horizon)
        elif model_type == "variance":
            result = build_variance_analysis(params.get("actuals", {}), params.get("budget", {}))
        else:
            return {"model_output": {"type": "unknown", "raw": response.content}}
    except Exception as e:
        return {"model_output": {"type": "error", "message": f"Model execution failed: {str(e)}", "params_attempted": params}}

    return {"model_output": {"type": model_type, "result": result, "explanation": explanation}}


# ── Node: Scenario Analysis ──────────────────────────────────────────────────


def scenario_node(state: AgentState) -> dict:
    """Use Claude to extract parameters, then run the actual scenario analysis."""
    llm = get_llm()
    query = state["current_query"]
    context = state.get("formatted_context", "")

    scenario_prompt = SystemMessage(
        content=f"""You are a scenario analysis assistant. Based on the user's query and available data, determine the analysis type and extract parameters.

Available analyses:
1. Scenario Matrix - needs base_inputs dict with: revenue, ebit, wacc, terminal_growth, revenue_growth, ebit_margin, projection_years
2. Sensitivity Table - needs base_inputs dict plus var1, var2 names and ranges
3. Cash Runway - needs cash_balance (float) and burn_scenarios (list of {{name, monthly_burn}})
4. Covenant Check - needs model_result (with ratios) and thresholds dict

Available financial context:
{context}

Respond with ONLY a valid JSON object:
{{"analysis_type": "scenario_matrix|sensitivity|runway|covenant", "parameters": {{...}}, "explanation": "brief explanation"}}

If insufficient data:
{{"analysis_type": "insufficient_data", "missing": [...], "explanation": "..."}}"""
    )

    response = llm.invoke([scenario_prompt, HumanMessage(content=query)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {"model_output": {"type": "error", "message": "Could not parse scenario parameters"}}

    analysis_type = parsed.get("analysis_type", "insufficient_data")
    params = parsed.get("parameters", {})
    explanation = parsed.get("explanation", "")

    if analysis_type == "insufficient_data":
        return {"model_output": {"type": "insufficient_data", "missing": parsed.get("missing", []), "explanation": explanation}}

    try:
        if analysis_type == "scenario_matrix":
            result = run_scenario_matrix(params.get("base_inputs", params), params.get("assumptions"))
        elif analysis_type == "sensitivity":
            result = build_sensitivity_table(
                params.get("base_inputs", params),
                params.get("var1", "wacc"),
                params.get("var1_range", [0.08, 0.09, 0.10, 0.11, 0.12]),
                params.get("var2", "terminal_growth"),
                params.get("var2_range", [0.01, 0.02, 0.03, 0.04, 0.05]),
            )
        elif analysis_type == "runway":
            result = calculate_cash_runway(params.get("cash_balance", 0), params.get("burn_scenarios", []))
        elif analysis_type == "covenant":
            result = stress_test_covenants(params.get("model_result", {}), params.get("thresholds", {}))
        else:
            return {"model_output": {"type": "unknown"}}
    except Exception as e:
        return {"model_output": {"type": "error", "message": f"Analysis failed: {str(e)}"}}

    return {"model_output": {"type": analysis_type, "result": result, "explanation": explanation}}


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

    # Validate citations
    validation = mcp_citation_validator(response_text)
    if not validation["valid"] and validation["uncited_claims"] > 0:
        response_text += f"\n\n⚠️ Note: {validation['uncited_claims']} numerical claim(s) may lack source citations."

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
