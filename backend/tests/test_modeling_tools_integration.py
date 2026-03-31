import pytest
from unittest.mock import patch
from backend.mcp_server.tools.modeling_tools import (
    mcp_extract_financials, mcp_run_dcf, mcp_run_ratios,
    mcp_run_forecast, mcp_run_variance, mcp_store_model,
)
from backend.mcp_server.tools.scenario_tools import (
    mcp_run_scenarios, mcp_sensitivity_matrix,
    mcp_covenant_check, mcp_runway_calc,
)


class TestModelingTools:
    def test_mcp_run_dcf_delegates(self):
        result = mcp_run_dcf({
            "revenue": 1_000_000, "ebit": 150_000,
            "wacc": 0.10, "terminal_growth": 0.03,
            "projection_years": 3, "revenue_growth": 0.05,
        })
        assert "enterprise_value" in result
        assert "projections" in result
        assert len(result["projections"]) == 3

    def test_mcp_run_ratios_delegates(self):
        result = mcp_run_ratios({
            "income_statement": {"revenue": 1000, "gross_profit": 600, "ebitda": 200, "ebit": 150, "net_income": 100, "cogs": 400, "interest_expense": 20},
            "balance_sheet": {"current_assets": 500, "current_liabilities": 300, "total_assets": 2000, "total_equity": 800, "total_debt": 400, "cash": 100, "inventory": 150, "accounts_receivable": 120, "accounts_payable": 80},
        })
        assert "ratios" in result
        assert "liquidity" in result["ratios"]

    def test_mcp_run_forecast_delegates(self):
        result = mcp_run_forecast({"revenue": [100, 110, 121, 133]}, horizon=2)
        assert "projections" in result
        assert len(result["projections"]["revenue"]["forecast"]) == 2

    def test_mcp_run_variance_delegates(self):
        result = mcp_run_variance(
            {"revenue": 1000, "cogs": 600},
            {"revenue": 1100, "cogs": 580},
        )
        assert "variances" in result

    def test_mcp_extract_financials_delegates(self):
        chunks = [{"text": "Revenue: $1,234,567", "metadata": {"section": "income_statement", "fiscal_year": "2024"}}]
        result = mcp_extract_financials(chunks)
        assert "line_items" in result
        assert len(result["line_items"]) > 0

    def test_mcp_store_model_delegates(self, tmp_path):
        with patch("backend.skills.financial_modeling.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            path = mcp_store_model({"test": "data"}, "test_model")
            assert path.endswith(".json")


class TestScenarioTools:
    def test_mcp_run_scenarios_delegates(self):
        result = mcp_run_scenarios(
            {"revenue": 1_000_000, "ebit": 150_000, "wacc": 0.10, "terminal_growth": 0.03, "revenue_growth": 0.05, "ebit_margin": 0.15, "projection_years": 3},
            None,
        )
        assert "scenarios" in result
        assert "bull" in result["scenarios"]
        assert "bear" in result["scenarios"]

    def test_mcp_sensitivity_matrix_delegates(self):
        result = mcp_sensitivity_matrix(
            {"revenue": 1_000_000, "ebit": 150_000, "wacc": 0.10, "terminal_growth": 0.03, "revenue_growth": 0.05, "ebit_margin": 0.15, "projection_years": 3},
            "wacc", "terminal_growth",
            [0.08, 0.10, 0.12], [0.02, 0.03, 0.04],
        )
        assert "table" in result
        assert len(result["table"]) == 3
        assert len(result["table"][0]) == 3

    def test_mcp_runway_calc_delegates(self):
        result = mcp_runway_calc(12_000_000, [{"name": "Current", "monthly_burn": 500_000}])
        assert result["scenarios"][0]["runway_months"] == 24.0

    def test_mcp_covenant_check_delegates(self):
        ratios_result = {
            "ratios": {
                "leverage": [{"name": "Interest Coverage", "value": 5.0}, {"name": "Debt-to-Equity", "value": 1.5}],
                "liquidity": [{"name": "Current Ratio", "value": 2.0}],
            }
        }
        result = mcp_covenant_check(ratios_result, {"min_interest_coverage": 3.0})
        assert "covenants" in result
