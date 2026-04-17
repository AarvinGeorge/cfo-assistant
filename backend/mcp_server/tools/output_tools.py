"""
output_tools.py

MCP tool implementations for generating boardroom-ready output artefacts
(Excel workbooks, PDF reports, Plotly charts).

Role in project:
    MCP layer — output generation. Called by Claude when a user requests
    an export or a visual. Wraps openpyxl (Excel), reportlab (PDF), and
    Plotly (charts) behind simple MCP tool interfaces.

Main parts:
    - mcp_export_excel(): serialises a model output dict into a formatted
      .xlsx workbook saved to the outputs directory.
    - mcp_export_pdf(): renders a PDF report from a model output dict.
    - mcp_generate_chart(): creates an interactive Plotly chart from
      structured financial data.
    - mcp_get_output_list(): returns available output files.
    - mcp_read_output(): reads a previously saved output file.
"""


def mcp_render_excel(model_dataframes: dict, metadata: dict) -> str:
    """Generate formatted Excel workbook from model DataFrames."""
    raise NotImplementedError("Implemented in Phase 6")


def mcp_render_pdf(content: dict, charts: list, metadata: dict) -> str:
    """Generate formatted PDF report."""
    raise NotImplementedError("Implemented in Phase 6")


def mcp_render_chart(dataframe: dict, chart_type: str, config: dict) -> dict:
    """Generate Plotly chart JSON for rendering in the frontend."""
    raise NotImplementedError("Implemented in Phase 6")


def mcp_file_serve(file_path: str) -> str:
    """Register generated file with FastAPI static server and return download URL."""
    raise NotImplementedError("Implemented in Phase 6")
