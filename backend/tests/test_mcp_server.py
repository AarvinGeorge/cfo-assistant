import pytest
from backend.mcp_server.financial_mcp_server import mcp

EXPECTED_TOOLS = {
    "mcp_parse_pdf",
    "mcp_parse_csv",
    "mcp_embed_chunks",
    "mcp_pinecone_upsert",
    "mcp_pinecone_search",
    "mcp_list_documents",
    "mcp_extract_financials",
    "mcp_run_dcf",
    "mcp_run_ratios",
    "mcp_run_forecast",
    "mcp_run_variance",
    "mcp_store_model",
    "mcp_run_scenarios",
    "mcp_sensitivity_matrix",
    "mcp_covenant_check",
    "mcp_runway_calc",
    "mcp_citation_validator",
    "mcp_response_logger",
    "mcp_export_trigger",
    "mcp_memory_read",
    "mcp_memory_write",
    "mcp_intent_log",
    "mcp_render_excel",
    "mcp_render_pdf",
    "mcp_render_chart",
    "mcp_file_serve",
}


def test_all_tools_are_registered():
    registered = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert registered == EXPECTED_TOOLS, (
        f"Missing tools: {EXPECTED_TOOLS - registered}\n"
        f"Extra tools: {registered - EXPECTED_TOOLS}"
    )


def test_tool_count():
    registered = list(mcp._tool_manager.list_tools())
    assert len(registered) == 26


def test_remaining_stubs_raise_not_implemented():
    """Verify Phase 4/6 tool stubs still raise NotImplementedError."""
    from backend.mcp_server.tools import (
        output_tools, memory_tools,
    )

    stub_calls = [
        lambda: output_tools.mcp_render_excel({}, {}),
        lambda: output_tools.mcp_render_pdf({}, [], {}),
        lambda: output_tools.mcp_render_chart({}, "bar", {}),
        lambda: output_tools.mcp_file_serve("test.xlsx"),
        lambda: memory_tools.mcp_memory_read("sess1"),
        lambda: memory_tools.mcp_memory_write("sess1", {}),
        lambda: memory_tools.mcp_intent_log("sess1", "query", "text"),
        lambda: memory_tools.mcp_citation_validator("text"),
        lambda: memory_tools.mcp_response_logger("sess1", "q", "r", []),
        lambda: memory_tools.mcp_export_trigger("sess1", "pdf", "model1"),
    ]

    for call in stub_calls:
        with pytest.raises(NotImplementedError):
            call()
