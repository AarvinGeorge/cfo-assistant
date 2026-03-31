from backend.skills.scenario_analysis import (
    run_scenario_matrix,
    build_sensitivity_table,
    stress_test_covenants,
    calculate_cash_runway,
)


def mcp_run_scenarios(base_model: dict, assumptions: dict) -> dict:
    """Run bull/base/bear scenario engine across defined assumption sets."""
    return run_scenario_matrix(base_model, assumptions)


def mcp_sensitivity_matrix(model: dict, var1: str, var2: str, var1_range: list = None, var2_range: list = None) -> dict:
    """Generate 2D sensitivity table for any two input variables."""
    if var1_range is None:
        base_v1 = model.get(var1, 0.10)
        var1_range = [round(base_v1 + i * 0.01, 4) for i in range(-2, 3)]
    if var2_range is None:
        base_v2 = model.get(var2, 0.03)
        var2_range = [round(base_v2 + i * 0.005, 4) for i in range(-2, 3)]
    return build_sensitivity_table(model, var1, var1_range, var2, var2_range)


def mcp_covenant_check(model: dict, thresholds: dict) -> dict:
    """Evaluate model outputs against user-defined covenant thresholds."""
    return stress_test_covenants(model, thresholds)


def mcp_runway_calc(cash_balance: float, burn_scenarios: list) -> dict:
    """Compute cash runway under multiple burn rate assumptions."""
    return calculate_cash_runway(cash_balance, burn_scenarios)
