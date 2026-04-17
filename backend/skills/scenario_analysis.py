"""
scenario_analysis.py

Implements strategic what-if analysis: multi-scenario matrices,
sensitivity tables, covenant stress tests, and cash runway calculation.

Role in project:
    Skills layer — scenario planning engine. Companion to
    financial_modeling.py. Called by the /scenarios/* API routes and the
    LangGraph scenario_analysis_node. All outputs include assumption
    documentation so CFOs can present them with full transparency.

Main parts:
    - run_scenario_matrix(): generates bull, base, and bear case projections
      by applying percentage adjustments to a set of base assumptions.
    - build_sensitivity_table(): produces a 2D grid varying two parameters
      (e.g. revenue growth x margin) across configurable ranges.
    - stress_test_covenants(): checks projected figures against debt
      covenant thresholds and flags periods where covenants are at risk.
    - calculate_cash_runway(): computes months of remaining runway given
      current cash balance and monthly burn rate.
"""

from typing import Dict, List, Any, Optional
import numpy as np
from backend.skills.financial_modeling import build_dcf_model


def define_scenarios(base_inputs: dict, assumptions: dict = None) -> dict:
    """
    Define bull/base/bear scenario assumption sets.

    Args:
        base_inputs: The base-case DCF inputs dict
        assumptions: Optional overrides for scenario ranges. If not provided,
                     uses sensible defaults (±20% for revenue growth, ±200bps for margins, etc.)
                     Format: {"revenue_growth": {"bull": 0.15, "bear": 0.02}, ...}

    Returns:
        {
            "bull": {full DCF inputs dict with optimistic assumptions},
            "base": {original inputs},
            "bear": {full DCF inputs dict with pessimistic assumptions},
        }
    """
    base = dict(base_inputs)

    if assumptions is None:
        assumptions = {}

    # Default adjustments if not provided
    rg = base.get("revenue_growth", 0.05)
    em = base.get("ebit_margin", 0.15)
    wacc = base.get("wacc", 0.10)
    tg = base.get("terminal_growth", 0.03)

    bull_inputs = dict(base)
    bull_inputs.update({
        "revenue_growth": assumptions.get("revenue_growth", {}).get("bull", rg * 1.4),
        "ebit_margin": assumptions.get("ebit_margin", {}).get("bull", em * 1.15),
        "wacc": assumptions.get("wacc", {}).get("bull", wacc - 0.01),
        "terminal_growth": assumptions.get("terminal_growth", {}).get("bull", tg + 0.005),
    })

    bear_inputs = dict(base)
    bear_inputs.update({
        "revenue_growth": assumptions.get("revenue_growth", {}).get("bear", rg * 0.4),
        "ebit_margin": assumptions.get("ebit_margin", {}).get("bear", em * 0.85),
        "wacc": assumptions.get("wacc", {}).get("bear", wacc + 0.02),
        "terminal_growth": assumptions.get("terminal_growth", {}).get("bear", tg - 0.005),
    })

    return {
        "bull": bull_inputs,
        "base": base,
        "bear": bear_inputs,
    }


def run_scenario_matrix(base_inputs: dict, assumptions: dict = None) -> dict:
    """
    Run DCF model across bull/base/bear scenarios.

    Returns:
        {
            "scenarios": {
                "bull": {dcf result},
                "base": {dcf result},
                "bear": {dcf result},
            },
            "comparison": {
                "enterprise_value": {"bull": X, "base": Y, "bear": Z},
                "equity_value": {"bull": X, "base": Y, "bear": Z},
                "implied_share_price": {"bull": X, "base": Y, "bear": Z},
            },
            "assumptions_used": {scenario definitions},
        }
    """
    scenarios_def = define_scenarios(base_inputs, assumptions)

    results = {}
    for name, inputs in scenarios_def.items():
        results[name] = build_dcf_model(inputs)

    comparison = {
        "enterprise_value": {k: v["enterprise_value"] for k, v in results.items()},
        "equity_value": {k: v["equity_value"] for k, v in results.items()},
        "implied_share_price": {k: v.get("implied_share_price") for k, v in results.items()},
    }

    return {
        "scenarios": results,
        "comparison": comparison,
        "assumptions_used": scenarios_def,
    }


def build_sensitivity_table(
    base_inputs: dict,
    var1: str,
    var1_range: list,
    var2: str,
    var2_range: list,
    output_metric: str = "enterprise_value",
) -> dict:
    """
    Build a 2D sensitivity table varying two inputs across ranges.

    Args:
        base_inputs: Base DCF inputs
        var1: First variable name (e.g., "wacc")
        var1_range: List of values for var1 (e.g., [0.08, 0.09, 0.10, 0.11, 0.12])
        var2: Second variable name (e.g., "terminal_growth")
        var2_range: List of values for var2 (e.g., [0.01, 0.02, 0.03, 0.04])
        output_metric: Which DCF output to show (default: "enterprise_value")

    Returns:
        {
            "var1": "wacc",
            "var2": "terminal_growth",
            "var1_values": [0.08, 0.09, 0.10, 0.11, 0.12],
            "var2_values": [0.01, 0.02, 0.03, 0.04],
            "table": [[ev_0_0, ev_0_1, ...], [ev_1_0, ev_1_1, ...], ...],
            "base_value": current_ev,
            "output_metric": "enterprise_value",
        }
    """
    table = []

    for v1 in var1_range:
        row = []
        for v2 in var2_range:
            inputs = dict(base_inputs)
            inputs[var1] = v1
            inputs[var2] = v2

            result = build_dcf_model(inputs)
            row.append(round(result.get(output_metric, 0), 2))
        table.append(row)

    base_result = build_dcf_model(base_inputs)

    return {
        "var1": var1,
        "var2": var2,
        "var1_values": var1_range,
        "var2_values": var2_range,
        "table": table,
        "base_value": round(base_result.get(output_metric, 0), 2),
        "output_metric": output_metric,
    }


def calculate_break_even(
    base_inputs: dict,
    target_metric: str,
    search_var: str,
    search_range: tuple = (0.0, 1.0),
    tolerance: float = 1000,
) -> dict:
    """
    Find the input value at which a target metric reaches zero (binary search).

    Args:
        base_inputs: Base DCF inputs
        target_metric: The metric to zero out (e.g., "equity_value", "fcf" from last projection year)
        search_var: Input variable to vary (e.g., "revenue_growth")
        search_range: (min, max) for binary search
        tolerance: How close to zero is "break even"

    Returns:
        {
            "break_even_value": float,
            "search_var": str,
            "target_metric": str,
            "converged": bool,
        }
    """
    low, high = search_range
    converged = False
    result_value = None

    for _ in range(50):  # max iterations
        mid = (low + high) / 2
        inputs = dict(base_inputs)
        inputs[search_var] = mid

        result = build_dcf_model(inputs)

        if target_metric == "fcf":
            metric_value = result["projections"][-1]["fcf"] if result["projections"] else 0
        else:
            metric_value = result.get(target_metric, 0)

        if abs(metric_value) < tolerance:
            converged = True
            result_value = mid
            break

        if metric_value > 0:
            # Need to decrease the metric -- depends on which var we're searching
            if search_var in ("revenue_growth", "ebit_margin", "terminal_growth"):
                high = mid  # reducing growth reduces value
            else:
                low = mid  # increasing wacc reduces value
        else:
            if search_var in ("revenue_growth", "ebit_margin", "terminal_growth"):
                low = mid
            else:
                high = mid

    if not converged:
        result_value = (low + high) / 2

    return {
        "break_even_value": round(result_value, 6) if result_value is not None else None,
        "search_var": search_var,
        "target_metric": target_metric,
        "converged": converged,
    }


def calculate_cash_runway(cash_balance: float, burn_scenarios: list) -> dict:
    """
    Project months of runway under multiple cash burn scenarios.

    Args:
        cash_balance: Current cash balance
        burn_scenarios: [
            {"name": "Current", "monthly_burn": 500000},
            {"name": "Reduced", "monthly_burn": 350000},
            {"name": "Worst Case", "monthly_burn": 750000},
        ]

    Returns:
        {
            "cash_balance": float,
            "scenarios": [
                {"name": "Current", "monthly_burn": 500000, "runway_months": 24.0, "runway_date_approx": "2028-03"},
                ...
            ],
            "critical": bool,  # True if any scenario < 6 months
        }
    """
    from datetime import datetime, timedelta

    now = datetime.now()
    results = []
    critical = False

    for scenario in burn_scenarios:
        name = scenario["name"]
        burn = scenario["monthly_burn"]

        if burn <= 0:
            runway_months = float("inf")
            runway_date = "N/A (positive cash flow)"
        else:
            runway_months = round(cash_balance / burn, 1)
            runway_date = (now + timedelta(days=runway_months * 30.44)).strftime("%Y-%m")

        if isinstance(runway_months, float) and runway_months < 6:
            critical = True

        results.append({
            "name": name,
            "monthly_burn": burn,
            "runway_months": runway_months,
            "runway_date_approx": runway_date,
        })

    return {
        "cash_balance": cash_balance,
        "scenarios": results,
        "critical": critical,
    }


def stress_test_covenants(model_result: dict, covenant_thresholds: dict) -> dict:
    """
    Test whether financial projections breach debt covenant thresholds.

    Args:
        model_result: Output from build_dcf_model or build_ratio_scorecard
        covenant_thresholds: {
            "min_interest_coverage": 3.0,
            "max_debt_to_equity": 2.0,
            "min_current_ratio": 1.2,
            "max_net_debt_ebitda": 4.0,
        }

    Returns:
        {
            "covenants": [
                {"name": "Interest Coverage", "threshold": 3.0, "actual": 4.5, "status": "pass"},
                {"name": "Debt-to-Equity", "threshold": 2.0, "actual": 1.8, "status": "pass"},
                ...
            ],
            "all_pass": bool,
            "breaches": [...names of failed covenants...],
        }
    """
    covenants = []
    breaches = []

    # Extract ratios from model result if it has them
    ratios = {}
    if "ratios" in model_result:
        for category, ratio_list in model_result["ratios"].items():
            for r in ratio_list:
                ratios[r["name"].lower().replace(" ", "_").replace("/", "_")] = r["value"]

    # Check each covenant
    covenant_checks = {
        "min_interest_coverage": ("interest_coverage", "min"),
        "max_debt_to_equity": ("debt-to-equity", "max"),
        "min_current_ratio": ("current_ratio", "min"),
        "max_net_debt_ebitda": ("net_debt_ebitda", "max"),
    }

    for covenant_key, (ratio_key, direction) in covenant_checks.items():
        if covenant_key not in covenant_thresholds:
            continue

        threshold = covenant_thresholds[covenant_key]
        actual = ratios.get(ratio_key)

        if actual is None:
            status = "unknown"
            breaches.append(f"{covenant_key} (data unavailable)")
        elif direction == "min" and actual < threshold:
            status = "breach"
            breaches.append(covenant_key)
        elif direction == "max" and actual > threshold:
            status = "breach"
            breaches.append(covenant_key)
        else:
            status = "pass"

        covenants.append({
            "name": covenant_key,
            "threshold": threshold,
            "actual": actual,
            "direction": direction,
            "status": status,
        })

    return {
        "covenants": covenants,
        "all_pass": len(breaches) == 0,
        "breaches": breaches,
    }
