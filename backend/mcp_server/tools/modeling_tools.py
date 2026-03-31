def mcp_extract_financials(chunks: list) -> dict:
    """Parse financial line items from RAG chunks into clean DataFrames."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_dcf(inputs: dict) -> dict:
    """Execute DCF model computation with given assumptions."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_ratios(statements: dict) -> dict:
    """Compute financial ratio scorecard from statement DataFrames."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_forecast(historical_series: dict, horizon: int = 3) -> dict:
    """Run time-series revenue/expense forecasting."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_variance(actuals: dict, budget: dict) -> dict:
    """Execute actuals vs. budget variance analysis."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_store_model(model_data: dict, model_name: str) -> str:
    """Persist generated model DataFrames to local storage."""
    raise NotImplementedError("Implemented in Phase 3")
