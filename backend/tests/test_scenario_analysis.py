"""
Tests for backend.skills.scenario_analysis
"""

import math
import pytest

from backend.skills.scenario_analysis import (
    define_scenarios,
    run_scenario_matrix,
    build_sensitivity_table,
    calculate_break_even,
    calculate_cash_runway,
    stress_test_covenants,
)

BASE_INPUTS = {
    "revenue": 1_000_000,
    "ebit": 150_000,
    "tax_rate": 0.25,
    "da": 20_000,
    "capex": 30_000,
    "nwc_change": 5_000,
    "wacc": 0.10,
    "terminal_growth": 0.03,
    "projection_years": 5,
    "revenue_growth": 0.08,
    "ebit_margin": 0.15,
    "shares_outstanding": 100_000,
    "net_debt": 50_000,
}


# ======================================================================
# define_scenarios
# ======================================================================

class TestDefineScenarios:
    def test_returns_bull_base_bear(self):
        result = define_scenarios(BASE_INPUTS)
        assert "bull" in result
        assert "base" in result
        assert "bear" in result

    def test_all_scenarios_are_valid_input_dicts(self):
        result = define_scenarios(BASE_INPUTS)
        required_keys = {"revenue", "wacc", "terminal_growth", "revenue_growth", "ebit_margin"}
        for scenario_name, inputs in result.items():
            assert required_keys.issubset(inputs.keys()), f"{scenario_name} missing keys"

    def test_scenarios_have_different_values(self):
        result = define_scenarios(BASE_INPUTS)
        assert result["bull"]["revenue_growth"] > result["base"]["revenue_growth"]
        assert result["bear"]["revenue_growth"] < result["base"]["revenue_growth"]
        assert result["bull"]["wacc"] < result["base"]["wacc"]
        assert result["bear"]["wacc"] > result["base"]["wacc"]

    def test_custom_assumptions_override_defaults(self):
        custom = {"revenue_growth": {"bull": 0.20, "bear": 0.01}}
        result = define_scenarios(BASE_INPUTS, assumptions=custom)
        assert result["bull"]["revenue_growth"] == 0.20
        assert result["bear"]["revenue_growth"] == 0.01


# ======================================================================
# run_scenario_matrix
# ======================================================================

class TestRunScenarioMatrix:
    def test_returns_three_scenarios_with_comparison(self):
        result = run_scenario_matrix(BASE_INPUTS)
        assert "scenarios" in result
        assert "comparison" in result
        assert "assumptions_used" in result
        for name in ("bull", "base", "bear"):
            assert name in result["scenarios"]
            assert name in result["comparison"]["enterprise_value"]

    def test_bull_ev_gt_base_gt_bear(self):
        result = run_scenario_matrix(BASE_INPUTS)
        ev = result["comparison"]["enterprise_value"]
        assert ev["bull"] > ev["base"] > ev["bear"], (
            f"Expected bull ({ev['bull']}) > base ({ev['base']}) > bear ({ev['bear']})"
        )

    def test_each_scenario_has_dcf_keys(self):
        result = run_scenario_matrix(BASE_INPUTS)
        for name in ("bull", "base", "bear"):
            dcf = result["scenarios"][name]
            assert "projections" in dcf
            assert "enterprise_value" in dcf
            assert "equity_value" in dcf


# ======================================================================
# build_sensitivity_table
# ======================================================================

class TestBuildSensitivityTable:
    def test_table_dimensions(self):
        var1_range = [0.08, 0.09, 0.10, 0.11, 0.12]
        var2_range = [0.01, 0.02, 0.03, 0.04]
        result = build_sensitivity_table(
            BASE_INPUTS, "wacc", var1_range, "terminal_growth", var2_range
        )
        table = result["table"]
        assert len(table) == len(var1_range)
        for row in table:
            assert len(row) == len(var2_range)

    def test_base_value_returned(self):
        result = build_sensitivity_table(
            BASE_INPUTS,
            "wacc", [0.09, 0.10, 0.11],
            "terminal_growth", [0.02, 0.03, 0.04],
        )
        assert "base_value" in result
        assert isinstance(result["base_value"], float)
        assert result["base_value"] > 0

    def test_output_metric_label(self):
        result = build_sensitivity_table(
            BASE_INPUTS,
            "wacc", [0.09, 0.10],
            "terminal_growth", [0.02, 0.03],
            output_metric="equity_value",
        )
        assert result["output_metric"] == "equity_value"


# ======================================================================
# calculate_break_even
# ======================================================================

class TestCalculateBreakEven:
    def test_converges_for_equity_value(self):
        """With known inputs, break-even on equity_value should converge."""
        result = calculate_break_even(
            BASE_INPUTS,
            target_metric="equity_value",
            search_var="wacc",
            search_range=(0.01, 5.0),
            tolerance=5000,
        )
        assert result["converged"] is True
        assert result["break_even_value"] is not None
        assert result["search_var"] == "wacc"
        assert result["target_metric"] == "equity_value"

    def test_break_even_value_is_reasonable(self):
        """Break-even WACC for equity_value should be some high rate."""
        result = calculate_break_even(
            BASE_INPUTS,
            target_metric="equity_value",
            search_var="wacc",
            search_range=(0.01, 5.0),
            tolerance=5000,
        )
        # The break-even WACC should be higher than the base WACC
        assert result["break_even_value"] > BASE_INPUTS["wacc"]


# ======================================================================
# calculate_cash_runway
# ======================================================================

class TestCalculateCashRunway:
    def test_basic_runway_calculation(self):
        """12M cash / 500K burn = 24 months."""
        result = calculate_cash_runway(
            cash_balance=12_000_000,
            burn_scenarios=[{"name": "Current", "monthly_burn": 500_000}],
        )
        assert result["cash_balance"] == 12_000_000
        assert len(result["scenarios"]) == 1
        assert result["scenarios"][0]["runway_months"] == 24.0
        assert result["critical"] is False

    def test_critical_flag_high_burn(self):
        """When burn is so high runway < 6 months, critical should be True."""
        result = calculate_cash_runway(
            cash_balance=2_000_000,
            burn_scenarios=[{"name": "Crisis", "monthly_burn": 500_000}],
        )
        assert result["scenarios"][0]["runway_months"] == 4.0
        assert result["critical"] is True

    def test_zero_burn_infinite_runway(self):
        """Zero or negative burn should yield infinite runway."""
        result = calculate_cash_runway(
            cash_balance=5_000_000,
            burn_scenarios=[{"name": "Profitable", "monthly_burn": 0}],
        )
        assert result["scenarios"][0]["runway_months"] == float("inf")
        assert result["scenarios"][0]["runway_date_approx"] == "N/A (positive cash flow)"
        assert result["critical"] is False

    def test_negative_burn_infinite_runway(self):
        """Negative burn (generating cash) should yield infinite runway."""
        result = calculate_cash_runway(
            cash_balance=5_000_000,
            burn_scenarios=[{"name": "Cash Positive", "monthly_burn": -100_000}],
        )
        assert result["scenarios"][0]["runway_months"] == float("inf")


# ======================================================================
# stress_test_covenants
# ======================================================================

class TestStressTestCovenants:
    def _make_model_result(self, interest_coverage=5.0, debt_to_equity=1.5,
                           current_ratio=2.0, net_debt_ebitda=3.0):
        """Helper to build a mock ratio scorecard result."""
        return {
            "ratios": {
                "leverage": [
                    {"name": "Interest Coverage", "value": interest_coverage},
                    {"name": "Debt-to-Equity", "value": debt_to_equity},
                    {"name": "Net Debt/EBITDA", "value": net_debt_ebitda},
                ],
                "liquidity": [
                    {"name": "Current Ratio", "value": current_ratio},
                ],
            }
        }

    def test_all_pass(self):
        model = self._make_model_result(
            interest_coverage=5.0, debt_to_equity=1.5,
            current_ratio=2.0, net_debt_ebitda=3.0,
        )
        thresholds = {
            "min_interest_coverage": 3.0,
            "max_debt_to_equity": 2.0,
            "min_current_ratio": 1.2,
            "max_net_debt_ebitda": 4.0,
        }
        result = stress_test_covenants(model, thresholds)
        assert result["all_pass"] is True
        assert len(result["breaches"]) == 0
        assert all(c["status"] == "pass" for c in result["covenants"])

    def test_breach_case(self):
        model = self._make_model_result(
            interest_coverage=2.0,  # below min of 3.0
            debt_to_equity=3.0,     # above max of 2.0
            current_ratio=2.0,
            net_debt_ebitda=3.0,
        )
        thresholds = {
            "min_interest_coverage": 3.0,
            "max_debt_to_equity": 2.0,
            "min_current_ratio": 1.2,
            "max_net_debt_ebitda": 4.0,
        }
        result = stress_test_covenants(model, thresholds)
        assert result["all_pass"] is False
        assert "min_interest_coverage" in result["breaches"]
        assert "max_debt_to_equity" in result["breaches"]

    def test_unknown_when_ratio_data_missing(self):
        """When model_result has no ratios, covenants should be 'unknown'."""
        model = {}  # no ratios at all
        thresholds = {
            "min_interest_coverage": 3.0,
            "max_debt_to_equity": 2.0,
        }
        result = stress_test_covenants(model, thresholds)
        assert result["all_pass"] is False
        assert all(c["status"] == "unknown" for c in result["covenants"])
        assert len(result["breaches"]) == 2  # both unavailable
