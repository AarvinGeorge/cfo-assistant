"""
models.py

FastAPI router exposing direct HTTP endpoints for the four financial
modeling capabilities: DCF valuation, ratio scorecard, forecasting,
and variance analysis.

Role in project:
    HTTP layer for the financial modeling skill. These endpoints are called
    by the React RightPanel Quick Actions and can also be invoked directly
    by the LangGraph financial_model_node. They are thin wrappers — all
    logic lives in skills/financial_modeling.py.

Main parts:
    - POST /models/dcf: runs a Discounted Cash Flow valuation given revenue
      projections, WACC, and terminal growth rate.
    - POST /models/ratios: computes a financial ratio scorecard from income
      statement and balance sheet figures.
    - POST /models/forecast: generates a 12-month revenue forecast using
      historical trends.
    - POST /models/variance: produces an actual-vs-budget variance analysis.
    - POST /models/save: persists any model output dict to a JSON file in
      the outputs directory.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

from backend.skills.financial_modeling import (
    build_dcf_model,
    build_ratio_scorecard,
    build_forecast_model,
    build_variance_analysis,
    store_model,
)

router = APIRouter(prefix="/models", tags=["models"])


class DCFRequest(BaseModel):
    revenue: float
    ebit: float
    wacc: float
    terminal_growth: float
    tax_rate: float = 0.25
    da: float = 0
    capex: float = 0
    nwc_change: float = 0
    projection_years: int = 5
    revenue_growth: float = 0.05
    ebit_margin: Optional[float] = None
    shares_outstanding: Optional[float] = None
    net_debt: float = 0


class RatioRequest(BaseModel):
    income_statement: Dict[str, Any]
    balance_sheet: Dict[str, Any]
    cash_flow: Dict[str, Any] = {}
    prior_period: Dict[str, Any] = {}
    benchmarks: Dict[str, Any] = {}


class ForecastRequest(BaseModel):
    historical_series: Dict[str, List[float]]
    horizon: int = 3


class VarianceRequest(BaseModel):
    actuals: Dict[str, float]
    budget: Dict[str, float]


@router.post("/dcf")
async def run_dcf(request: DCFRequest):
    inputs = request.model_dump(exclude_none=True)
    if "ebit_margin" not in inputs:
        inputs["ebit_margin"] = inputs["ebit"] / inputs["revenue"] if inputs["revenue"] else 0
    return build_dcf_model(inputs)


@router.post("/ratios")
async def run_ratios(request: RatioRequest):
    return build_ratio_scorecard(request.model_dump())


@router.post("/forecast")
async def run_forecast(request: ForecastRequest):
    return build_forecast_model(request.historical_series, request.horizon)


@router.post("/variance")
async def run_variance(request: VarianceRequest):
    return build_variance_analysis(request.actuals, request.budget)


@router.post("/save")
async def save_model(model_data: dict, model_name: str = "model"):
    path = store_model(model_data, model_name)
    return {"path": path, "status": "saved"}
