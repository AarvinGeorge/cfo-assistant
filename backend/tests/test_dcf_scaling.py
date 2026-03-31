import pytest
from backend.skills.financial_modeling import build_dcf_model, build_ratio_scorecard


class TestDCFScaling:
    BASE_INPUTS = {
        "revenue": 1_000_000,
        "ebit": 150_000,
        "tax_rate": 0.25,
        "da": 20_000,       # 2% of revenue
        "capex": 30_000,    # 3% of revenue
        "nwc_change": 5_000, # 0.5% of revenue
        "wacc": 0.10,
        "terminal_growth": 0.03,
        "projection_years": 5,
        "revenue_growth": 0.10,
        "ebit_margin": 0.15,
    }

    def test_capex_scales_with_revenue(self):
        result = build_dcf_model(self.BASE_INPUTS)
        yr1 = result["projections"][0]
        yr5 = result["projections"][4]
        yr1_capex_pct = yr1["capex"] / yr1["revenue"]
        yr5_capex_pct = yr5["capex"] / yr5["revenue"]
        assert abs(yr1_capex_pct - yr5_capex_pct) < 0.001

    def test_da_scales_with_revenue(self):
        result = build_dcf_model(self.BASE_INPUTS)
        yr1 = result["projections"][0]
        yr5 = result["projections"][4]
        yr1_da_pct = yr1["da"] / yr1["revenue"]
        yr5_da_pct = yr5["da"] / yr5["revenue"]
        assert abs(yr1_da_pct - yr5_da_pct) < 0.001

    def test_nwc_scales_with_revenue(self):
        result = build_dcf_model(self.BASE_INPUTS)
        yr1 = result["projections"][0]
        yr5 = result["projections"][4]
        yr1_nwc_pct = yr1["nwc_change"] / yr1["revenue"]
        yr5_nwc_pct = yr5["nwc_change"] / yr5["revenue"]
        assert abs(yr1_nwc_pct - yr5_nwc_pct) < 0.001

    def test_fcf_grows_proportionally(self):
        result = build_dcf_model(self.BASE_INPUTS)
        yr1 = result["projections"][0]
        yr5 = result["projections"][4]
        revenue_ratio = yr5["revenue"] / yr1["revenue"]
        fcf_ratio = yr5["fcf"] / yr1["fcf"]
        # Should be within 5% of each other since all components scale equally
        assert abs(revenue_ratio - fcf_ratio) / revenue_ratio < 0.05

    def test_projections_include_da_capex_nwc(self):
        result = build_dcf_model(self.BASE_INPUTS)
        for p in result["projections"]:
            assert "da" in p
            assert "capex" in p
            assert "nwc_change" in p

    def test_zero_revenue_no_crash(self):
        inputs = {**self.BASE_INPUTS, "revenue": 0, "ebit": 0}
        result = build_dcf_model(inputs)
        assert result["enterprise_value"] is not None


class TestROICTaxRate:
    def test_roic_uses_provided_tax_rate(self):
        result = build_ratio_scorecard({
            "income_statement": {
                "revenue": 1000, "ebit": 200, "net_income": 120,
                "gross_profit": 500, "ebitda": 250, "cogs": 500,
                "interest_expense": 20,
            },
            "balance_sheet": {
                "total_equity": 500, "total_debt": 300,
                "current_assets": 400, "current_liabilities": 200,
                "total_assets": 1500, "cash": 100, "inventory": 100,
                "accounts_receivable": 80, "accounts_payable": 60,
            },
            "tax_rate": 0.30,
        })
        roic = None
        for r in result["ratios"]["profitability"]:
            if r["name"] == "ROIC":
                roic = r["value"]
        # ROIC = EBIT * (1 - 0.30) / (equity + debt) = 200 * 0.70 / 800 = 0.175
        assert roic is not None
        assert abs(roic - 0.175) < 0.001

    def test_roic_defaults_to_25_when_no_tax_rate(self):
        result = build_ratio_scorecard({
            "income_statement": {
                "revenue": 1000, "ebit": 200, "net_income": 120,
                "gross_profit": 500, "ebitda": 250, "cogs": 500,
                "interest_expense": 20,
            },
            "balance_sheet": {
                "total_equity": 500, "total_debt": 300,
                "current_assets": 400, "current_liabilities": 200,
                "total_assets": 1500, "cash": 100, "inventory": 100,
                "accounts_receivable": 80, "accounts_payable": 60,
            },
        })
        roic = None
        for r in result["ratios"]["profitability"]:
            if r["name"] == "ROIC":
                roic = r["value"]
        # ROIC = EBIT * (1 - 0.25) / (equity + debt) = 200 * 0.75 / 800 = 0.1875
        assert roic is not None
        assert abs(roic - 0.1875) < 0.001
