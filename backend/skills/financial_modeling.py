"""
Financial Modeling Skill for FinSight CFO Assistant.

Provides quantitative engines for DCF models, ratio scorecards,
forecasts, and variance analyses.
"""

import re
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

import pandas as pd
import numpy as np

from backend.core.config import get_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_number(s: str) -> Optional[float]:
    """Parse a financial number string, returning None if not parseable."""
    try:
        cleaned = s.replace(",", "").strip()
        if not cleaned:
            return None
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# 1. Extract Financials
# ---------------------------------------------------------------------------

def extract_financials(chunks: list) -> dict:
    """
    Parse financial line items from retrieved RAG chunks into structured data.

    Scans chunk text for patterns like "Revenue: $1,234" or "Revenue | $1,234 | $1,100"
    and organizes them by section.

    Returns:
        {
            "line_items": [
                {"label": "Revenue", "value": 1234000, "period": "2024",
                 "section": "income_statement"},
                ...
            ],
            "sections_found": ["income_statement", "balance_sheet"],
            "chunk_count": 5
        }
    """
    line_items: List[dict] = []
    sections_found: set = set()

    for chunk in chunks:
        text = (chunk.get("text", "") if isinstance(chunk, dict)
                else getattr(chunk, "text", ""))
        metadata = (chunk.get("metadata", {}) if isinstance(chunk, dict)
                    else getattr(chunk, "metadata", {}))
        section = metadata.get("section", "general")
        period = metadata.get("fiscal_year", "")

        # Pattern 1: "Label: $1,234,567" or "Label: 1234567"
        for match in re.finditer(
            r'([A-Za-z][A-Za-z &/\-]+?):\s*\$?([\d,]+\.?\d*)', text
        ):
            label = match.group(1).strip()
            value = _parse_number(match.group(2))
            if value is not None:
                line_items.append({
                    "label": label,
                    "value": value,
                    "period": period,
                    "section": section,
                })
                sections_found.add(section)

        # Pattern 2: pipe-delimited table rows "Label | $1,234 | $1,100"
        for match in re.finditer(
            r'([A-Za-z][A-Za-z &/\-]+?)\s*\|\s*\$?([\d,]+\.?\d*)', text
        ):
            label = match.group(1).strip()
            value = _parse_number(match.group(2))
            if value is not None and label.lower() not in (
                "label", "item", "description"
            ):
                line_items.append({
                    "label": label,
                    "value": value,
                    "period": period,
                    "section": section,
                })
                sections_found.add(section)

    return {
        "line_items": line_items,
        "sections_found": list(sections_found),
        "chunk_count": len(chunks),
    }


# ---------------------------------------------------------------------------
# 2. DCF Model
# ---------------------------------------------------------------------------

def build_dcf_model(inputs: dict) -> dict:
    """
    Build a Discounted Cash Flow model.

    Args:
        inputs: {
            "revenue": float,
            "ebit": float,
            "tax_rate": float,          # e.g. 0.25
            "da": float,               # Depreciation & Amortization
            "capex": float,
            "nwc_change": float,
            "wacc": float,             # e.g. 0.10
            "terminal_growth": float,  # e.g. 0.03
            "projection_years": int,
            "revenue_growth": float,
            "ebit_margin": float,      # optional
            "shares_outstanding": float,  # optional
            "net_debt": float,         # optional
        }

    Returns dict with projections, terminal value, enterprise/equity value,
    implied share price, assumptions, and warnings.
    """
    revenue = inputs["revenue"]
    ebit = inputs["ebit"]
    tax_rate = inputs.get("tax_rate", 0.25)
    da = inputs.get("da", 0)
    capex = inputs.get("capex", 0)
    nwc_change = inputs.get("nwc_change", 0)
    wacc = inputs["wacc"]
    terminal_growth = inputs["terminal_growth"]
    projection_years = inputs.get("projection_years", 5)
    revenue_growth = inputs.get("revenue_growth", 0.05)
    ebit_margin = inputs.get(
        "ebit_margin", ebit / revenue if revenue else 0
    )
    shares = inputs.get("shares_outstanding")
    net_debt = inputs.get("net_debt", 0)

    warnings: List[str] = []

    # Guardrails
    if wacc <= terminal_growth:
        warnings.append(
            f"WACC ({wacc:.1%}) must exceed terminal growth "
            f"({terminal_growth:.1%}). "
            "Terminal value calculation is mathematically invalid."
        )
    if capex > revenue:
        warnings.append(
            f"CapEx ({capex:,.0f}) exceeds revenue ({revenue:,.0f}). "
            "Verify inputs."
        )
    if projection_years < 1 or projection_years > 20:
        warnings.append(
            f"Projection years ({projection_years}) outside typical "
            "range 1-20."
        )

    # Build year-by-year projections
    projections = []
    current_revenue = revenue

    for year in range(1, projection_years + 1):
        proj_revenue = current_revenue * (1 + revenue_growth)
        proj_ebit = proj_revenue * ebit_margin
        nopat = proj_ebit * (1 - tax_rate)
        fcf = nopat + da - capex - nwc_change
        discount_factor = (1 + wacc) ** year
        discounted_fcf = fcf / discount_factor

        projections.append({
            "year": year,
            "revenue": round(proj_revenue, 2),
            "ebit": round(proj_ebit, 2),
            "nopat": round(nopat, 2),
            "fcf": round(fcf, 2),
            "discount_factor": round(discount_factor, 4),
            "discounted_fcf": round(discounted_fcf, 2),
        })

        current_revenue = proj_revenue

    # Terminal value (Gordon Growth Model)
    if wacc > terminal_growth:
        terminal_fcf = projections[-1]["fcf"] * (1 + terminal_growth)
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        discounted_tv = terminal_value / ((1 + wacc) ** projection_years)
    else:
        terminal_value = 0
        discounted_tv = 0

    # Enterprise and equity value
    sum_discounted_fcf = sum(p["discounted_fcf"] for p in projections)
    enterprise_value = sum_discounted_fcf + discounted_tv
    equity_value = enterprise_value - net_debt

    implied_share_price = None
    if shares and shares > 0:
        implied_share_price = round(equity_value / shares, 2)

    return {
        "projections": projections,
        "terminal_value": round(terminal_value, 2),
        "discounted_terminal_value": round(discounted_tv, 2),
        "sum_discounted_fcf": round(sum_discounted_fcf, 2),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "implied_share_price": implied_share_price,
        "assumptions": {
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "revenue_growth": revenue_growth,
            "ebit_margin": ebit_margin,
            "tax_rate": tax_rate,
            "projection_years": projection_years,
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 3. Ratio Scorecard
# ---------------------------------------------------------------------------

def _compute_single_ratio(statements: dict, category: str, name: str):
    """Helper for prior period ratio computation -- simplified version."""
    return None


def build_ratio_scorecard(statements: dict) -> dict:
    """
    Compute financial ratios across four categories:
    liquidity, profitability, leverage, efficiency.

    Args:
        statements: dict with keys income_statement, balance_sheet,
                    cash_flow, prior_period (optional), benchmarks (optional)

    Returns dict with ratios grouped by category plus warnings.
    """
    inc = statements.get("income_statement", {})
    bs = statements.get("balance_sheet", {})
    cf = statements.get("cash_flow", {})
    prior = statements.get("prior_period", {})
    benchmarks = statements.get("benchmarks", {})

    warnings: List[str] = []

    def safe_div(a, b, label=""):
        if b is None or b == 0:
            if label:
                warnings.append(
                    f"Cannot compute {label}: divisor is zero or missing"
                )
            return None
        if a is None:
            if label:
                warnings.append(
                    f"Cannot compute {label}: numerator is missing"
                )
            return None
        return round(a / b, 4)

    def status(value, benchmark_key):
        """Determine green/yellow/red based on benchmark proximity."""
        if value is None:
            return "gray"
        bench = benchmarks.get(benchmark_key)
        if bench is None:
            return "neutral"
        diff = abs(value - bench) / max(abs(bench), 0.001)
        if diff < 0.1:
            return "green"
        elif diff < 0.25:
            return "yellow"
        return "red"

    # ── Liquidity ─────────────────────────────────────────────────────────
    liquidity = []

    current_ratio = safe_div(
        bs.get("current_assets"), bs.get("current_liabilities"),
        "Current Ratio"
    )
    liquidity.append({
        "name": "Current Ratio", "value": current_ratio,
        "benchmark": benchmarks.get("current_ratio"),
        "status": status(current_ratio, "current_ratio"),
    })

    quick_assets = None
    if (bs.get("current_assets") is not None
            and bs.get("inventory") is not None):
        quick_assets = bs["current_assets"] - bs["inventory"]
    quick_ratio = safe_div(
        quick_assets, bs.get("current_liabilities"), "Quick Ratio"
    )
    liquidity.append({
        "name": "Quick Ratio", "value": quick_ratio,
        "benchmark": benchmarks.get("quick_ratio"),
        "status": status(quick_ratio, "quick_ratio"),
    })

    cash_ratio = safe_div(
        bs.get("cash"), bs.get("current_liabilities"), "Cash Ratio"
    )
    liquidity.append({
        "name": "Cash Ratio", "value": cash_ratio,
        "benchmark": benchmarks.get("cash_ratio"),
        "status": status(cash_ratio, "cash_ratio"),
    })

    # ── Profitability ─────────────────────────────────────────────────────
    profitability = []

    gross_margin = safe_div(
        inc.get("gross_profit"), inc.get("revenue"), "Gross Margin"
    )
    profitability.append({
        "name": "Gross Margin", "value": gross_margin,
        "benchmark": benchmarks.get("gross_margin"),
        "status": status(gross_margin, "gross_margin"),
    })

    ebitda_margin = safe_div(
        inc.get("ebitda"), inc.get("revenue"), "EBITDA Margin"
    )
    profitability.append({
        "name": "EBITDA Margin", "value": ebitda_margin,
        "benchmark": benchmarks.get("ebitda_margin"),
        "status": status(ebitda_margin, "ebitda_margin"),
    })

    net_margin = safe_div(
        inc.get("net_income"), inc.get("revenue"), "Net Margin"
    )
    profitability.append({
        "name": "Net Margin", "value": net_margin,
        "benchmark": benchmarks.get("net_margin"),
        "status": status(net_margin, "net_margin"),
    })

    roe = safe_div(
        inc.get("net_income"), bs.get("total_equity"), "ROE"
    )
    profitability.append({
        "name": "ROE", "value": roe,
        "benchmark": benchmarks.get("roe"),
        "status": status(roe, "roe"),
    })

    roa = safe_div(
        inc.get("net_income"), bs.get("total_assets"), "ROA"
    )
    profitability.append({
        "name": "ROA", "value": roa,
        "benchmark": benchmarks.get("roa"),
        "status": status(roa, "roa"),
    })

    invested_capital = None
    if (bs.get("total_equity") is not None
            and bs.get("total_debt") is not None):
        invested_capital = bs["total_equity"] + bs["total_debt"]
    nopat = (
        inc.get("ebit", 0) * (1 - 0.25)
        if inc.get("ebit") is not None else None
    )
    roic = safe_div(nopat, invested_capital, "ROIC")
    profitability.append({
        "name": "ROIC", "value": roic,
        "benchmark": benchmarks.get("roic"),
        "status": status(roic, "roic"),
    })

    # ── Leverage ──────────────────────────────────────────────────────────
    leverage = []

    de_ratio = safe_div(
        bs.get("total_debt"), bs.get("total_equity"), "Debt-to-Equity"
    )
    leverage.append({
        "name": "Debt-to-Equity", "value": de_ratio,
        "benchmark": benchmarks.get("debt_to_equity"),
        "status": status(de_ratio, "debt_to_equity"),
    })

    net_debt_val = (bs.get("total_debt", 0) or 0) - (bs.get("cash", 0) or 0)
    net_debt_ebitda = safe_div(
        net_debt_val, inc.get("ebitda"), "Net Debt/EBITDA"
    )
    leverage.append({
        "name": "Net Debt/EBITDA", "value": net_debt_ebitda,
        "benchmark": benchmarks.get("net_debt_ebitda"),
        "status": status(net_debt_ebitda, "net_debt_ebitda"),
    })

    interest_coverage = safe_div(
        inc.get("ebit"), inc.get("interest_expense"), "Interest Coverage"
    )
    leverage.append({
        "name": "Interest Coverage", "value": interest_coverage,
        "benchmark": benchmarks.get("interest_coverage"),
        "status": status(interest_coverage, "interest_coverage"),
    })

    # ── Efficiency ────────────────────────────────────────────────────────
    efficiency = []

    asset_turnover = safe_div(
        inc.get("revenue"), bs.get("total_assets"), "Asset Turnover"
    )
    efficiency.append({
        "name": "Asset Turnover", "value": asset_turnover,
        "benchmark": benchmarks.get("asset_turnover"),
        "status": status(asset_turnover, "asset_turnover"),
    })

    inv_turnover = safe_div(
        inc.get("cogs"), bs.get("inventory"), "Inventory Turnover"
    )
    efficiency.append({
        "name": "Inventory Turnover", "value": inv_turnover,
        "benchmark": benchmarks.get("inventory_turnover"),
        "status": status(inv_turnover, "inventory_turnover"),
    })

    dso = safe_div(
        bs.get("accounts_receivable"), inc.get("revenue"), "DSO"
    )
    if dso is not None:
        dso = round(dso * 365, 1)
    efficiency.append({
        "name": "DSO", "value": dso,
        "benchmark": benchmarks.get("dso"),
        "status": status(dso, "dso"),
    })

    dpo = safe_div(bs.get("accounts_payable"), inc.get("cogs"), "DPO")
    if dpo is not None:
        dpo = round(dpo * 365, 1)
    efficiency.append({
        "name": "DPO", "value": dpo,
        "benchmark": benchmarks.get("dpo"),
        "status": status(dpo, "dpo"),
    })

    return {
        "ratios": {
            "liquidity": liquidity,
            "profitability": profitability,
            "leverage": leverage,
            "efficiency": efficiency,
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 4. Forecast Model
# ---------------------------------------------------------------------------

def build_forecast_model(
    historical_series: dict, horizon: int = 3
) -> dict:
    """
    Project revenue and expense line items forward.

    Args:
        historical_series: {"revenue": [100, 110, 121, 133], ...}
        horizon: Number of years to project (1-5)

    Returns dict with projections per line item including forecast,
    method, CAGR, confidence intervals, and warnings.
    """
    warnings: List[str] = []
    projections: Dict[str, dict] = {}

    for label, values in historical_series.items():
        if not values or len(values) < 2:
            warnings.append(
                f"Insufficient data for {label}: need at least 2 data "
                f"points, got {len(values) if values else 0}"
            )
            continue

        if len(values) < 3:
            warnings.append(
                f"Only {len(values)} years of data for {label}. "
                "Forecast reliability is low."
            )

        values = [float(v) for v in values]

        # Choose method based on data characteristics
        if len(values) >= 3 and all(v > 0 for v in values):
            # CAGR-based projection
            cagr = (values[-1] / values[0]) ** (
                1 / (len(values) - 1)
            ) - 1
            forecast = []
            last = values[-1]
            for _ in range(horizon):
                last = last * (1 + cagr)
                forecast.append(round(last, 2))
            method = "cagr"

            # Confidence intervals (+-1 std dev of historical growth)
            growth_rates = [
                (values[i] / values[i - 1]) - 1
                for i in range(1, len(values))
            ]
            std_growth = (
                float(np.std(growth_rates))
                if len(growth_rates) > 1
                else cagr * 0.2
            )

            upper = []
            lower = []
            for yr in range(1, horizon + 1):
                u = values[-1] * (1 + cagr + std_growth) ** yr
                l = values[-1] * (1 + max(cagr - std_growth, -0.5)) ** yr
                upper.append(round(u, 2))
                lower.append(round(l, 2))

        else:
            # Linear regression fallback
            x = np.arange(len(values))
            coeffs = np.polyfit(x, values, 1)
            slope, intercept = coeffs[0], coeffs[1]
            forecast = [
                round(slope * (len(values) + i) + intercept, 2)
                for i in range(horizon)
            ]
            method = "linear"
            cagr = None

            fitted = slope * x + intercept
            residuals = np.array(values) - fitted
            std_res = float(np.std(residuals))
            upper = [round(f + std_res, 2) for f in forecast]
            lower = [round(f - std_res, 2) for f in forecast]

        projections[label] = {
            "historical": values,
            "forecast": forecast,
            "method": method,
            "cagr": round(cagr, 4) if cagr is not None else None,
            "confidence_upper": upper,
            "confidence_lower": lower,
        }

    if any(
        len(v) < 3
        for v in historical_series.values()
        if v
    ):
        warnings.append(
            "Fewer than 3 years of historical data. "
            "Forecast reliability is limited."
        )

    return {
        "projections": projections,
        "horizon": horizon,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 5. Variance Analysis
# ---------------------------------------------------------------------------

def build_variance_analysis(actuals: dict, budget: dict) -> dict:
    """
    Compare actuals vs budget/prior period.

    Args:
        actuals: {"revenue": 1000, "cogs": 600, ...}
        budget:  {"revenue": 1100, "cogs": 580, ...}

    Returns dict with per-line variance, favorable flag, totals, warnings.
    """
    warnings: List[str] = []
    variances: List[dict] = []

    # Revenue-type items: higher actual is favorable
    revenue_items = {
        "revenue", "income", "sales", "gain", "profit",
        "gross_profit", "net_income", "ebitda", "ebit",
    }

    all_labels = set(actuals.keys()) | set(budget.keys())

    only_actuals = set(actuals.keys()) - set(budget.keys())
    only_budget = set(budget.keys()) - set(actuals.keys())
    if only_actuals:
        warnings.append(
            f"Line items in actuals but not in budget: "
            f"{', '.join(sorted(only_actuals))}"
        )
    if only_budget:
        warnings.append(
            f"Line items in budget but not in actuals: "
            f"{', '.join(sorted(only_budget))}"
        )

    for label in sorted(all_labels):
        actual_val = actuals.get(label)
        budget_val = budget.get(label)

        if actual_val is None or budget_val is None:
            continue

        actual_val = float(actual_val)
        budget_val = float(budget_val)

        variance = actual_val - budget_val
        variance_pct = (
            variance / abs(budget_val) if budget_val != 0 else None
        )

        is_revenue_type = any(kw in label.lower() for kw in revenue_items)
        if is_revenue_type:
            favorable = variance >= 0
        else:
            favorable = variance <= 0

        variances.append({
            "label": label,
            "actual": actual_val,
            "budget": budget_val,
            "variance": round(variance, 2),
            "variance_pct": (
                round(variance_pct, 4) if variance_pct is not None else None
            ),
            "favorable": favorable,
        })

    total_favorable = sum(1 for v in variances if v["favorable"])
    total_unfavorable = len(variances) - total_favorable

    return {
        "variances": variances,
        "total_favorable": total_favorable,
        "total_unfavorable": total_unfavorable,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Storage Helper
# ---------------------------------------------------------------------------

def store_model(model_data: dict, model_name: str) -> str:
    """
    Persist model output to local JSON storage.

    Returns the file path where the model was saved.
    """
    settings = get_settings()
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())[:8]
    filename = f"{model_name}_{file_id}.json"
    file_path = output_dir / filename

    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    with open(file_path, "w") as f:
        json.dump(model_data, f, indent=2, default=convert)

    return str(file_path)
