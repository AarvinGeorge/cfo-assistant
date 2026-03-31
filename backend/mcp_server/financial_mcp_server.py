from mcp.server.fastmcp import FastMCP
from backend.mcp_server.tools.document_tools import (
    mcp_parse_pdf, mcp_parse_csv, mcp_embed_chunks,
    mcp_pinecone_upsert, mcp_pinecone_search, mcp_list_documents,
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
    mcp_memory_read, mcp_memory_write, mcp_intent_log,
    mcp_citation_validator, mcp_response_logger, mcp_export_trigger,
)

mcp = FastMCP("finsight-financial-tools")

# ── Document tools ────────────────────────────────────────────────────────────
mcp.tool()(mcp_parse_pdf)
mcp.tool()(mcp_parse_csv)
mcp.tool()(mcp_embed_chunks)
mcp.tool()(mcp_pinecone_upsert)
mcp.tool()(mcp_pinecone_search)
mcp.tool()(mcp_list_documents)

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

# ── Memory & audit tools ──────────────────────────────────────────────────────
mcp.tool()(mcp_memory_read)
mcp.tool()(mcp_memory_write)
mcp.tool()(mcp_intent_log)
mcp.tool()(mcp_citation_validator)
mcp.tool()(mcp_response_logger)
mcp.tool()(mcp_export_trigger)


if __name__ == "__main__":
    mcp.run()
