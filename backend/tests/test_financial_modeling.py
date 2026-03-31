"""
Tests for backend.skills.financial_modeling
"""

import json
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.skills.financial_modeling import (
    _parse_number,
    extract_financials,
    build_dcf_model,
    build_ratio_scorecard,
    build_forecast_model,
    build_variance_analysis,
    store_model,
)


# ======================================================================
# _parse_number
# ======================================================================

class TestParseNumber:
    def test_plain_integer(self):
        assert _parse_number("1234") == 1234.0

    def test_with_commas(self):
        assert _parse_number("1,234,567.89") == 1234567.89

    def test_empty_string(self):
        assert _parse_number("") is None

    def test_whitespace_only(self):
        assert _parse_number("   ") is None

    def test_non_numeric(self):
        assert _parse_number("abc") is None

    def test_decimal(self):
        assert _parse_number("99.5") == 99.5


# ======================================================================
# extract_financials
# ======================================================================

class TestExtractFinancials:
    def test_colon_pattern(self):
        chunks = [
            {
                "text": "Revenue: $1,234,567\nCOGS: $800,000",
                "metadata": {
                    "section": "income_statement",
                    "fiscal_year": "2024",
                },
            }
        ]
        result = extract_financials(chunks)
        assert result["chunk_count"] == 1
        assert "income_statement" in result["sections_found"]
        labels = [li["label"] for li in result["line_items"]]
        assert "Revenue" in labels
        assert "COGS" in labels
        rev = next(
            li for li in result["line_items"] if li["label"] == "Revenue"
        )
        assert rev["value"] == 1234567.0
        assert rev["period"] == "2024"

    def test_pipe_pattern(self):
        chunks = [
            {
                "text": "Revenue | 1234 | 1100\nExpenses | 500 | 480",
                "metadata": {"section": "income_statement"},
            }
        ]
        result = extract_financials(chunks)
        labels = [li["label"] for li in result["line_items"]]
        assert "Revenue" in labels
        assert "Expenses" in labels

    def test_pipe_skips_header_rows(self):
        chunks = [
            {
                "text": "Label | 2024 | 2023\nRevenue | 1000 | 900",
                "metadata": {},
            }
        ]
        result = extract_financials(chunks)
        labels = [li["label"] for li in result["line_items"]]
        assert "Label" not in labels

    def test_empty_chunks(self):
        result = extract_financials([])
        assert result["line_items"] == []
        assert result["sections_found"] == []
        assert result["chunk_count"] == 0

    def test_chunk_without_financials(self):
        chunks = [{"text": "This is a plain paragraph.", "metadata": {}}]
        result = extract_financials(chunks)
        assert result["line_items"] == []

    def test_default_section(self):
        chunks = [{"text": "Revenue: $500", "metadata": {}}]
        result = extract_financials(chunks)
        assert result["line_items"][0]["section"] == "general"


# ======================================================================
# build_dcf_model
# ======================================================================

class TestBuildDCFModel:
    @pytest.fixture
    def base_inputs(self):
        return {
            "revenue": 1_000_000,
            "ebit": 200_000,
            "tax_rate": 0.25,
            "da": 50_000,
            "capex": 80_000,
            "nwc_change": 10_000,
            "wacc": 0.10,
            "terminal_growth": 0.03,
            "projection_years": 5,
            "revenue_growth": 0.05,
        }

    def test_basic_dcf_positive_ev(self, base_inputs):
        result = build_dcf_model(base_inputs)
        assert result["enterprise_value"] > 0
        assert len(result["projections"]) == 5
        assert result["warnings"] == []

    def test_projection_count(self, base_inputs):
        base_inputs["projection_years"] = 3
        result = build_dcf_model(base_inputs)
        assert len(result["projections"]) == 3

    def test_wacc_lte_terminal_growth_warning(self, base_inputs):
        base_inputs["wacc"] = 0.02
        base_inputs["terminal_growth"] = 0.03
        result = build_dcf_model(base_inputs)
        assert any("WACC" in w for w in result["warnings"])
        assert result["terminal_value"] == 0

    def test_capex_exceeds_revenue_warning(self, base_inputs):
        base_inputs["capex"] = 2_000_000
        result = build_dcf_model(base_inputs)
        assert any("CapEx" in w for w in result["warnings"])

    def test_implied_share_price(self, base_inputs):
        base_inputs["shares_outstanding"] = 100_000
        base_inputs["net_debt"] = 50_000
        result = build_dcf_model(base_inputs)
        assert result["implied_share_price"] is not None
        assert result["implied_share_price"] > 0

    def test_equity_value_equals_ev_minus_net_debt(self, base_inputs):
        base_inputs["net_debt"] = 200_000
        result = build_dcf_model(base_inputs)
        assert result["equity_value"] == pytest.approx(
            result["enterprise_value"] - 200_000, rel=1e-6
        )

    def test_no_shares_gives_none_price(self, base_inputs):
        result = build_dcf_model(base_inputs)
        assert result["implied_share_price"] is None

    def test_revenue_grows_each_year(self, base_inputs):
        result = build_dcf_model(base_inputs)
        revenues = [p["revenue"] for p in result["projections"]]
        for i in range(1, len(revenues)):
            assert revenues[i] > revenues[i - 1]

    def test_assumptions_stored(self, base_inputs):
        result = build_dcf_model(base_inputs)
        assert result["assumptions"]["wacc"] == 0.10
        assert result["assumptions"]["projection_years"] == 5


# ======================================================================
# build_ratio_scorecard
# ======================================================================

class TestBuildRatioScorecard:
    @pytest.fixture
    def full_statements(self):
        return {
            "income_statement": {
                "revenue": 1_000_000,
                "cogs": 600_000,
                "gross_profit": 400_000,
                "ebitda": 250_000,
                "ebit": 200_000,
                "net_income": 120_000,
                "interest_expense": 20_000,
            },
            "balance_sheet": {
                "total_assets": 2_000_000,
                "current_assets": 500_000,
                "cash": 100_000,
                "inventory": 150_000,
                "total_liabilities": 800_000,
                "current_liabilities": 300_000,
                "total_debt": 400_000,
                "total_equity": 1_200_000,
                "accounts_receivable": 200_000,
                "accounts_payable": 100_000,
            },
            "cash_flow": {"operating_cash_flow": 180_000},
        }

    def test_all_categories_present(self, full_statements):
        result = build_ratio_scorecard(full_statements)
        assert "liquidity" in result["ratios"]
        assert "profitability" in result["ratios"]
        assert "leverage" in result["ratios"]
        assert "efficiency" in result["ratios"]

    def test_current_ratio(self, full_statements):
        result = build_ratio_scorecard(full_statements)
        cr = next(
            r for r in result["ratios"]["liquidity"]
            if r["name"] == "Current Ratio"
        )
        expected = 500_000 / 300_000
        assert cr["value"] == pytest.approx(expected, rel=1e-3)

    def test_gross_margin(self, full_statements):
        result = build_ratio_scorecard(full_statements)
        gm = next(
            r for r in result["ratios"]["profitability"]
            if r["name"] == "Gross Margin"
        )
        expected = 400_000 / 1_000_000
        assert gm["value"] == pytest.approx(expected, rel=1e-3)

    def test_zero_divisor_warning(self):
        stmts = {
            "income_statement": {"revenue": 0, "gross_profit": 0},
            "balance_sheet": {"current_assets": 100, "current_liabilities": 0},
        }
        result = build_ratio_scorecard(stmts)
        assert any("divisor is zero" in w for w in result["warnings"])

    def test_empty_statements(self):
        result = build_ratio_scorecard({})
        # All values should be None
        for category_ratios in result["ratios"].values():
            for ratio in category_ratios:
                assert ratio["value"] is None
        assert len(result["warnings"]) > 0

    def test_interest_coverage(self, full_statements):
        result = build_ratio_scorecard(full_statements)
        ic = next(
            r for r in result["ratios"]["leverage"]
            if r["name"] == "Interest Coverage"
        )
        assert ic["value"] == pytest.approx(200_000 / 20_000, rel=1e-3)

    def test_dso_in_days(self, full_statements):
        result = build_ratio_scorecard(full_statements)
        dso = next(
            r for r in result["ratios"]["efficiency"]
            if r["name"] == "DSO"
        )
        expected = (200_000 / 1_000_000) * 365
        assert dso["value"] == pytest.approx(expected, rel=1e-2)


# ======================================================================
# build_forecast_model
# ======================================================================

class TestBuildForecastModel:
    def test_basic_forecast_length(self):
        data = {"revenue": [100, 110, 121, 133]}
        result = build_forecast_model(data, horizon=3)
        assert len(result["projections"]["revenue"]["forecast"]) == 3

    def test_cagr_calculation(self):
        # [100, 110, 121] => CAGR ~ 0.1
        data = {"revenue": [100, 110, 121]}
        result = build_forecast_model(data, horizon=1)
        cagr = result["projections"]["revenue"]["cagr"]
        assert cagr == pytest.approx(0.1, abs=0.005)
        assert result["projections"]["revenue"]["method"] == "cagr"

    def test_fewer_than_3_warning(self):
        data = {"revenue": [100, 110]}
        result = build_forecast_model(data, horizon=2)
        assert any("Only 2" in w for w in result["warnings"])

    def test_fewer_than_2_skipped(self):
        data = {"revenue": [100]}
        result = build_forecast_model(data, horizon=2)
        assert "revenue" not in result["projections"]
        assert any("Insufficient" in w for w in result["warnings"])

    def test_empty_values_skipped(self):
        data = {"revenue": []}
        result = build_forecast_model(data, horizon=2)
        assert "revenue" not in result["projections"]

    def test_confidence_intervals_present(self):
        data = {"revenue": [100, 110, 121, 133]}
        result = build_forecast_model(data, horizon=3)
        proj = result["projections"]["revenue"]
        assert len(proj["confidence_upper"]) == 3
        assert len(proj["confidence_lower"]) == 3

    def test_linear_fallback_with_negatives(self):
        data = {"net_change": [-10, -5, 0, 5]}
        result = build_forecast_model(data, horizon=2)
        proj = result["projections"]["net_change"]
        assert proj["method"] == "linear"
        assert proj["cagr"] is None

    def test_horizon_respected(self):
        data = {"revenue": [100, 200, 300]}
        result = build_forecast_model(data, horizon=5)
        assert len(result["projections"]["revenue"]["forecast"]) == 5
        assert result["horizon"] == 5


# ======================================================================
# build_variance_analysis
# ======================================================================

class TestBuildVarianceAnalysis:
    def test_revenue_favorable(self):
        actuals = {"revenue": 1200}
        budget = {"revenue": 1100}
        result = build_variance_analysis(actuals, budget)
        rev = result["variances"][0]
        assert rev["favorable"] is True
        assert rev["variance"] == 100

    def test_cost_favorable_when_lower(self):
        actuals = {"cogs": 550}
        budget = {"cogs": 600}
        result = build_variance_analysis(actuals, budget)
        cogs = result["variances"][0]
        assert cogs["favorable"] is True
        assert cogs["variance"] == -50

    def test_cost_unfavorable_when_higher(self):
        actuals = {"cogs": 650}
        budget = {"cogs": 600}
        result = build_variance_analysis(actuals, budget)
        assert result["variances"][0]["favorable"] is False

    def test_variance_pct(self):
        actuals = {"revenue": 1100}
        budget = {"revenue": 1000}
        result = build_variance_analysis(actuals, budget)
        assert result["variances"][0]["variance_pct"] == pytest.approx(
            0.1, rel=1e-3
        )

    def test_mismatched_labels_warning(self):
        actuals = {"revenue": 100, "bonus": 50}
        budget = {"revenue": 100, "misc": 30}
        result = build_variance_analysis(actuals, budget)
        assert any("actuals but not in budget" in w for w in result["warnings"])
        assert any("budget but not in actuals" in w for w in result["warnings"])

    def test_totals(self):
        actuals = {"revenue": 1200, "cogs": 550, "opex": 250}
        budget = {"revenue": 1100, "cogs": 600, "opex": 200}
        result = build_variance_analysis(actuals, budget)
        assert result["total_favorable"] + result["total_unfavorable"] == 3

    def test_zero_budget_gives_none_pct(self):
        actuals = {"revenue": 100}
        budget = {"revenue": 0}
        result = build_variance_analysis(actuals, budget)
        assert result["variances"][0]["variance_pct"] is None


# ======================================================================
# store_model
# ======================================================================

class TestStoreModel:
    def test_save_and_load(self, tmp_path):
        mock_settings = MagicMock()
        mock_settings.output_dir = str(tmp_path / "outputs")

        with patch(
            "backend.skills.financial_modeling.get_settings",
            return_value=mock_settings,
        ):
            data = {"enterprise_value": 1_234_567, "warnings": []}
            path = store_model(data, "dcf_model")

            assert Path(path).exists()
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["enterprise_value"] == 1_234_567

    def test_filename_contains_model_name(self, tmp_path):
        mock_settings = MagicMock()
        mock_settings.output_dir = str(tmp_path / "outputs")

        with patch(
            "backend.skills.financial_modeling.get_settings",
            return_value=mock_settings,
        ):
            path = store_model({"test": True}, "ratio_scorecard")
            assert "ratio_scorecard" in Path(path).name
