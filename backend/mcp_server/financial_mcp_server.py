"""
financial_mcp_server.py

Registers all 26 FinSight financial tools with the MCP (Model Context
Protocol) server so Claude can call them as structured tool invocations.

Role in project:
    MCP layer — tool registration hub. Exposes the full capabilities of the
    skills layer (document search, financial modeling, scenario analysis,
    output generation, memory) as MCP tools. Claude can call these tools
    directly during generation, enabling richer, more structured responses
    than pure text generation.

Main parts:
    - FastMCP app instance: the MCP server object that tools are registered
      against.
    - Tool registrations (26 total): each @mcp.tool() decorator wires a
      Python function to an MCP tool name with a typed parameter schema.
      Tools are grouped by domain: document (5), modeling (6), scenario (5),
      output (5), memory and audit (5).
"""

from mcp.server.fastmcp import FastMCP
from backend.mcp_server.tools.document_tools import (
    mcp_parse_pdf, mcp_parse_csv, mcp_embed_chunks,
    mcp_pinecone_upsert, mcp_pinecone_search,
)
from backend.mcp_server.tools.modeling_tools import (
    mcp_extract_financials, mcp_run_dcf, mcp_run_ratios,
    mcp_run_forecast, mcp_run_variance, mcp_store_model,
)
from backend.mcp_server.tools.scenario_tools import (
    mcp_run_scenarios, mcp_sensitivity_matrix,
    mcp_covenant_check, mcp_runway_calc,
)
from backend.mcp_server.tools.output_tools import (
    mcp_render_excel, mcp_render_pdf, mcp_render_chart, mcp_file_serve,
)
from backend.mcp_server.tools.memory_tools import (
    mcp_intent_log,
    mcp_citation_validator, mcp_response_logger, mcp_export_trigger,
)

mcp = FastMCP("finsight-financial-tools")

# ── Document tools ────────────────────────────────────────────────────────────
mcp.tool()(mcp_parse_pdf)
mcp.tool()(mcp_parse_csv)
mcp.tool()(mcp_embed_chunks)
mcp.tool()(mcp_pinecone_upsert)
mcp.tool()(mcp_pinecone_search)

# ── Modeling tools ────────────────────────────────────────────────────────────
mcp.tool()(mcp_extract_financials)
mcp.tool()(mcp_run_dcf)
mcp.tool()(mcp_run_ratios)
mcp.tool()(mcp_run_forecast)
mcp.tool()(mcp_run_variance)
mcp.tool()(mcp_store_model)

# ── Scenario tools ────────────────────────────────────────────────────────────
mcp.tool()(mcp_run_scenarios)
mcp.tool()(mcp_sensitivity_matrix)
mcp.tool()(mcp_covenant_check)
mcp.tool()(mcp_runway_calc)

# ── Output tools ──────────────────────────────────────────────────────────────
mcp.tool()(mcp_render_excel)
mcp.tool()(mcp_render_pdf)
mcp.tool()(mcp_render_chart)
mcp.tool()(mcp_file_serve)

# ── Audit + validation tools (memory is LangGraph SqliteSaver's job) ──────────
mcp.tool()(mcp_intent_log)
mcp.tool()(mcp_citation_validator)
mcp.tool()(mcp_response_logger)
mcp.tool()(mcp_export_trigger)


if __name__ == "__main__":
    mcp.run()
