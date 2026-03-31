from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

from backend.skills.scenario_analysis import (
    run_scenario_matrix,
    build_sensitivity_table,
    stress_test_covenants,
    calculate_cash_runway,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class ScenarioRequest(BaseModel):
    base_inputs: Dict[str, Any]
    assumptions: Optional[Dict[str, Any]] = None


class SensitivityRequest(BaseModel):
    base_inputs: Dict[str, Any]
    var1: str
    var1_range: List[float]
    var2: str
    var2_range: List[float]
    output_metric: str = "enterprise_value"


class CovenantRequest(BaseModel):
    model_result: Dict[str, Any]
    thresholds: Dict[str, float]


class RunwayRequest(BaseModel):
    cash_balance: float
    burn_scenarios: List[Dict[str, Any]]


@router.post("/run")
async def run_scenarios(request: ScenarioRequest):
    return run_scenario_matrix(request.base_inputs, request.assumptions)


@router.post("/sensitivity")
async def sensitivity(request: SensitivityRequest):
    return build_sensitivity_table(
        request.base_inputs, request.var1, request.var1_range,
        request.var2, request.var2_range, request.output_metric,
    )


@router.post("/covenants")
async def covenants(request: CovenantRequest):
    return stress_test_covenants(request.model_result, request.thresholds)


@router.post("/runway")
async def runway(request: RunwayRequest):
    return calculate_cash_runway(request.cash_balance, request.burn_scenarios)
