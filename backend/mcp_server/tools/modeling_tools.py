from backend.skills.financial_modeling import (
    extract_financials,
    build_dcf_model,
    build_ratio_scorecard,
    build_forecast_model,
    build_variance_analysis,
    store_model,
)


def mcp_extract_financials(chunks: list) -> dict:
    """Parse financial line items from RAG chunks into clean DataFrames."""
    return extract_financials(chunks)


def mcp_run_dcf(inputs: dict) -> dict:
    """Execute DCF model computation with given assumptions."""
    return build_dcf_model(inputs)


def mcp_run_ratios(statements: dict) -> dict:
    """Compute financial ratio scorecard from statement DataFrames."""
    return build_ratio_scorecard(statements)


def mcp_run_forecast(historical_series: dict, horizon: int = 3) -> dict:
    """Run time-series revenue/expense forecasting."""
    return build_forecast_model(historical_series, horizon)


def mcp_run_variance(actuals: dict, budget: dict) -> dict:
    """Execute actuals vs. budget variance analysis."""
    return build_variance_analysis(actuals, budget)


def mcp_store_model(model_data: dict, model_name: str) -> str:
    """Persist generated model DataFrames to local storage."""
    return store_model(model_data, model_name)
