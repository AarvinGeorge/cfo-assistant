"""
test_kpi_response_parser.py

Verifies the parse_kpi_response helper extracts the headline / period /
note from a Claude-generated KPI response in the pipe-delimited format
`HEADLINE | PERIOD | NOTE`, and falls back gracefully when the response
is malformed.
"""
from backend.api.routes.kpis import parse_kpi_response


class TestWellFormedInput:
    def test_parses_simple_three_parts(self):
        r = parse_kpi_response("$22.6B | FY2025 | +13% YoY")
        assert r == {"headline": "$22.6B", "period": "FY2025", "note": "+13% YoY"}

    def test_strips_whitespace(self):
        r = parse_kpi_response("  $22.6B  |  FY2025  |  +13% YoY  ")
        assert r["headline"] == "$22.6B"
        assert r["period"] == "FY2025"
        assert r["note"] == "+13% YoY"

    def test_handles_percentage(self):
        r = parse_kpi_response("45.2% | FY2025 | Improved from 42.1%")
        assert r["headline"] == "45.2%"
        assert r["period"] == "FY2025"

    def test_handles_two_parts_only(self):
        r = parse_kpi_response("$22.6B | FY2025")
        assert r["headline"] == "$22.6B"
        assert r["period"] == "FY2025"
        assert r["note"] == ""

    def test_note_can_contain_commas_and_dollars(self):
        r = parse_kpi_response("18 months | As of Dec 31 2025 | Based on $180M cash, $10M/mo burn")
        assert r["headline"] == "18 months"
        assert r["note"].startswith("Based on $180M")


class TestMalformedInput:
    def test_extracts_line_from_markdown_preamble(self):
        """Claude might emit markdown before the pipe line; parser should find it."""
        text = (
            "## Revenue Analysis\n\n"
            "Based on the 10-K:\n\n"
            "$22.6B | FY2025 | +13% YoY\n"
        )
        r = parse_kpi_response(text)
        assert r["headline"] == "$22.6B"
        assert r["period"] == "FY2025"

    def test_fallback_when_no_pipes_present(self):
        text = "## EOG Resources\n\nThe company reported $22.6B in revenue."
        r = parse_kpi_response(text)
        # Must return something — don't raise
        assert "headline" in r
        assert r["headline"]  # non-empty
        # Should not be the markdown heading
        assert not r["headline"].startswith("#")

    def test_empty_string_returns_empty_fields(self):
        r = parse_kpi_response("")
        assert r == {"headline": "", "period": "", "note": ""}

    def test_insufficient_data_signal(self):
        r = parse_kpi_response("N/A | Insufficient data | 10-K does not split revenue by segment")
        assert r["headline"] == "N/A"
        assert r["period"] == "Insufficient data"

    def test_ignores_markdown_table_separator_lines(self):
        """A markdown table line like '|---|---|---|' should not be mistaken for a value."""
        text = (
            "| Year | Revenue | Change |\n"
            "|------|---------|--------|\n"
            "| 2024 | $20B    | —      |\n"
            "\n"
            "$22.6B | FY2025 | +13% YoY"
        )
        r = parse_kpi_response(text)
        assert r["headline"] == "$22.6B"
        assert r["period"] == "FY2025"


class TestRobustness:
    def test_very_long_headline_is_truncated_to_reasonable_size(self):
        long = "A" * 500
        r = parse_kpi_response(long)
        # Fallback path — headline should be bounded
        assert len(r["headline"]) <= 200

    def test_handles_multiline_response_with_pipe_line_at_end(self):
        text = "Some preamble.\n\nMore text.\n\n$22.6B | FY2025 | growth"
        r = parse_kpi_response(text)
        assert r["headline"] == "$22.6B"


class TestMarkdownProseExtraction:
    """The real-world input: Claude's natural markdown analysis.

    These tests drive the parser to extract a headline / period / note from
    realistic markdown like what generate_response() emits.
    """

    def test_extracts_dollar_amount_from_bullet_list(self):
        text = (
            "## EOG Resources — Revenue\n"
            "\n"
            "For the fiscal year ended **December 31, 2025**:\n"
            "- Total Operating Revenues: **$22,632 million**\n"
            "- Compared to $17,687 million in FY2024 (+28% YoY)\n"
        )
        r = parse_kpi_response(text)
        # Must surface the headline number, not the heading or the compare value
        assert "$22,632" in r["headline"] or "$22.6B" in r["headline"]
        # Period should mention the fiscal year
        assert "2025" in r["period"]

    def test_extracts_percentage(self):
        text = (
            "## Gross Margin Analysis\n"
            "\n"
            "Gross margin for FY2025 was **45.2%**, up from 42.1% in the prior year.\n"
        )
        r = parse_kpi_response(text)
        assert "45.2%" in r["headline"]
        assert "2025" in r["period"]

    def test_extracts_runway_in_months(self):
        text = (
            "## Cash Runway\n"
            "\n"
            "Based on $180M cash balance and a monthly burn of $10M, the runway is approximately **18 months**.\n"
        )
        r = parse_kpi_response(text, kpi_key="runway")
        assert "18" in r["headline"]
        assert "month" in r["headline"].lower() or "month" in r["note"].lower()

    def test_skips_comparison_values_for_headline(self):
        """When the response mentions two numbers (current + prior), headline takes the first."""
        text = (
            "Revenue was **$22.6B** in FY2025, compared to $17.7B in FY2024.\n"
        )
        r = parse_kpi_response(text)
        assert "22.6" in r["headline"]
        assert "2025" in r["period"]

    def test_insufficient_data_signal_from_prose(self):
        text = (
            "## Cash Runway\n"
            "\n"
            "The 10-K does not provide a monthly burn rate, so runway cannot be computed reliably.\n"
        )
        r = parse_kpi_response(text)
        # Parser should return something indicating no number was found
        assert r["headline"].upper().startswith("N/A") or r["headline"] == "—" or not any(c.isdigit() for c in r["headline"])
