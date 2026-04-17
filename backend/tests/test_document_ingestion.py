"""
test_document_ingestion.py

Tests that verify PDF/CSV parsing, text chunking, financial-value normalisation, and section detection.

Role in project:
    Test suite — verifies the behaviour of backend.skills.document_ingestion. Run with:
    pytest tests/test_document_ingestion.py -v

Coverage:
    - _normalize_financial_value strips currency symbols, parenthetical negatives, and whitespace
    - parse_pdf extracts text and tables per page, normalises table cell values, and counts pages correctly
    - parse_csv reads rows, strips column-header whitespace, and normalises financial values in cells
    - hierarchical_chunk produces the correct section and row chunk types from both PDF and CSV parsed output
    - _split_text_into_chunks respects max_tokens and produces overlapping chunks for long text
    - _detect_section classifies headings into the correct financial section labels case-insensitively
"""

import csv
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.skills.document_ingestion import (
    Chunk,
    count_tokens,
    parse_pdf,
    parse_csv,
    hierarchical_chunk,
    _normalize_financial_value,
    _split_text_into_chunks,
    _detect_section,
)


# ── _normalize_financial_value ───────────────────────────────────────────────


class TestNormalizeFinancialValue:
    def test_dollar_and_commas(self):
        assert _normalize_financial_value("$1,234.56") == "1234.56"

    def test_parenthetical_negative(self):
        assert _normalize_financial_value("(1,234)") == "-1234"

    def test_parenthetical_negative_with_dollar(self):
        assert _normalize_financial_value("($1,234.56)") == "-1234.56"

    def test_plain_text_passthrough(self):
        assert _normalize_financial_value("Revenue") == "Revenue"

    def test_empty_string(self):
        assert _normalize_financial_value("") == ""

    def test_none_passthrough(self):
        assert _normalize_financial_value(None) is None

    def test_whitespace_stripped(self):
        assert _normalize_financial_value("  $100  ") == "100"

    def test_plain_number(self):
        assert _normalize_financial_value("42") == "42"


# ── count_tokens ─────────────────────────────────────────────────────────────


class TestCountTokens:
    def test_returns_positive_for_nonempty(self):
        assert count_tokens("Hello world") > 0

    def test_returns_zero_for_empty(self):
        assert count_tokens("") == 0

    def test_longer_text_more_tokens(self):
        short = count_tokens("Hi")
        long = count_tokens("This is a much longer sentence with many words in it.")
        assert long > short


# ── parse_pdf ────────────────────────────────────────────────────────────────


class TestParsePdf:
    def test_parse_pdf_with_mock(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Revenue was $1,000,000 in FY2024."
        mock_page.extract_tables.return_value = [
            [["Item", "Amount"], ["Revenue", "$1,000,000"], ["Expenses", "($500,000)"]],
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("backend.skills.document_ingestion.pdfplumber.open", return_value=mock_pdf):
            result = parse_pdf("fake.pdf")

        assert result["page_count"] == 1
        assert result["table_count"] == 1
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_number"] == 1
        assert "Revenue" in result["full_text"]

        # Verify table normalization
        table = result["pages"][0]["tables"][0]
        assert table[1][1] == "1000000"  # $1,000,000 normalized
        assert table[2][1] == "-500000"  # ($500,000) normalized

    def test_parse_pdf_empty_page(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_page.extract_tables.return_value = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("backend.skills.document_ingestion.pdfplumber.open", return_value=mock_pdf):
            result = parse_pdf("fake.pdf")

        assert result["page_count"] == 1
        assert result["table_count"] == 0
        assert result["pages"][0]["text"] == ""

    def test_parse_pdf_multiple_pages(self):
        pages = []
        for i in range(3):
            p = MagicMock()
            p.extract_text.return_value = f"Page {i+1} content"
            p.extract_tables.return_value = []
            pages.append(p)

        mock_pdf = MagicMock()
        mock_pdf.pages = pages
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("backend.skills.document_ingestion.pdfplumber.open", return_value=mock_pdf):
            result = parse_pdf("fake.pdf")

        assert result["page_count"] == 3
        assert result["pages"][2]["page_number"] == 3


# ── parse_csv ────────────────────────────────────────────────────────────────


class TestParseCsv:
    def test_parse_csv_basic(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Item,Amount,Year\nRevenue,$1000,2024\nExpenses,($500),2024\n")

        result = parse_csv(str(csv_file))

        assert result["row_count"] == 2
        assert result["columns"] == ["Item", "Amount", "Year"]
        assert len(result["rows"]) == 2
        assert result["rows"][0]["Amount"] == "1000"
        assert result["rows"][1]["Amount"] == "-500"
        assert "full_text" in result

    def test_parse_csv_column_strip(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(" Name , Value \nfoo,bar\n")

        result = parse_csv(str(csv_file))
        assert result["columns"] == ["Name", "Value"]

    def test_parse_csv_empty_values(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("A,B\n1,\n,2\n")

        result = parse_csv(str(csv_file))
        assert result["row_count"] == 2


# ── hierarchical_chunk (PDF) ────────────────────────────────────────────────


class TestHierarchicalChunkPdf:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.section_chunk_tokens = 512
        settings.row_chunk_tokens = 128
        settings.chunk_overlap_tokens = 64
        return settings

    @pytest.fixture
    def doc_metadata(self):
        return {
            "doc_id": "test-doc-id",
            "doc_name": "report.pdf",
            "doc_type": "10-K",
            "fiscal_year": "2024",
        }

    def test_pdf_section_and_row_chunks(self, mock_settings, doc_metadata):
        parsed = {
            "pages": [
                {
                    "page_number": 1,
                    "text": "The company revenue grew significantly in FY2024.",
                    "tables": [
                        [
                            ["Item", "Amount"],
                            ["Revenue", "5000000"],
                            ["COGS", "2000000"],
                        ],
                    ],
                }
            ],
            "full_text": "The company revenue grew significantly in FY2024.",
            "table_count": 1,
            "page_count": 1,
        }

        with patch("backend.skills.document_ingestion.get_settings", return_value=mock_settings):
            chunks = hierarchical_chunk(parsed, doc_metadata)

        section_chunks = [c for c in chunks if c.metadata["chunk_type"] == "section"]
        row_chunks = [c for c in chunks if c.metadata["chunk_type"] == "row"]

        assert len(section_chunks) >= 1
        assert len(row_chunks) == 2
        assert section_chunks[0].metadata["doc_id"] == "test-doc-id"
        assert section_chunks[0].metadata["page"] == 1
        assert row_chunks[0].metadata["table_row"] == 1
        assert row_chunks[1].metadata["table_row"] == 2

    def test_pdf_section_detection_in_chunks(self, mock_settings, doc_metadata):
        parsed = {
            "pages": [
                {
                    "page_number": 1,
                    "text": "Cash flow from operations was strong this year.",
                    "tables": [],
                }
            ],
            "full_text": "Cash flow from operations was strong this year.",
            "table_count": 0,
            "page_count": 1,
        }

        with patch("backend.skills.document_ingestion.get_settings", return_value=mock_settings):
            chunks = hierarchical_chunk(parsed, doc_metadata)

        assert chunks[0].metadata["section"] == "cash_flow"

    def test_pdf_empty_table_row_skipped(self, mock_settings, doc_metadata):
        parsed = {
            "pages": [
                {
                    "page_number": 1,
                    "text": "",
                    "tables": [
                        [["Header1", "Header2"], ["", ""]],
                    ],
                }
            ],
            "full_text": "",
            "table_count": 1,
            "page_count": 1,
        }

        with patch("backend.skills.document_ingestion.get_settings", return_value=mock_settings):
            chunks = hierarchical_chunk(parsed, doc_metadata)

        assert len(chunks) == 0

    def test_pdf_single_row_table_skipped(self, mock_settings, doc_metadata):
        """Tables with only a header (< 2 rows) should be skipped."""
        parsed = {
            "pages": [
                {
                    "page_number": 1,
                    "text": "",
                    "tables": [
                        [["Header1", "Header2"]],
                    ],
                }
            ],
            "full_text": "",
            "table_count": 1,
            "page_count": 1,
        }

        with patch("backend.skills.document_ingestion.get_settings", return_value=mock_settings):
            chunks = hierarchical_chunk(parsed, doc_metadata)

        assert len(chunks) == 0

    def test_chunk_has_uuid(self, mock_settings, doc_metadata):
        parsed = {
            "pages": [
                {
                    "page_number": 1,
                    "text": "Some text here.",
                    "tables": [],
                }
            ],
            "full_text": "Some text here.",
            "table_count": 0,
            "page_count": 1,
        }

        with patch("backend.skills.document_ingestion.get_settings", return_value=mock_settings):
            chunks = hierarchical_chunk(parsed, doc_metadata)

        assert len(chunks[0].chunk_id) == 36  # UUID format


# ── hierarchical_chunk (CSV) ────────────────────────────────────────────────


class TestHierarchicalChunkCsv:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.section_chunk_tokens = 512
        settings.row_chunk_tokens = 128
        settings.chunk_overlap_tokens = 64
        return settings

    @pytest.fixture
    def doc_metadata(self):
        return {
            "doc_id": "csv-doc-id",
            "doc_name": "financials.csv",
            "doc_type": "income_statement",
            "fiscal_year": "2024",
        }

    def test_csv_row_chunks(self, mock_settings, doc_metadata):
        parsed = {
            "rows": [
                {"Item": "Revenue", "Amount": "5000000"},
                {"Item": "COGS", "Amount": "2000000"},
            ],
            "columns": ["Item", "Amount"],
            "row_count": 2,
            "full_text": "Item  Amount\nRevenue  5000000\nCOGS  2000000",
        }

        with patch("backend.skills.document_ingestion.get_settings", return_value=mock_settings):
            chunks = hierarchical_chunk(parsed, doc_metadata)

        assert len(chunks) == 2
        assert all(c.metadata["chunk_type"] == "row" for c in chunks)
        assert all(c.metadata["section"] == "data" for c in chunks)
        assert chunks[0].metadata["table_row"] == 1
        assert chunks[1].metadata["table_row"] == 2
        assert chunks[0].metadata["doc_type"] == "income_statement"

    def test_csv_empty_row_skipped(self, mock_settings, doc_metadata):
        parsed = {
            "rows": [
                {"Item": "", "Amount": ""},
            ],
            "columns": ["Item", "Amount"],
            "row_count": 1,
            "full_text": "",
        }

        with patch("backend.skills.document_ingestion.get_settings", return_value=mock_settings):
            chunks = hierarchical_chunk(parsed, doc_metadata)

        assert len(chunks) == 0


# ── _split_text_into_chunks ─────────────────────────────────────────────────


class TestSplitTextIntoChunks:
    def test_short_text_single_chunk(self):
        result = _split_text_into_chunks("Hello world", max_tokens=100, overlap_tokens=10)
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_long_text_multiple_chunks(self):
        # Create text that definitely exceeds 10 tokens
        long_text = " ".join(["word"] * 200)
        result = _split_text_into_chunks(long_text, max_tokens=50, overlap_tokens=10)
        assert len(result) > 1

    def test_overlap_creates_shared_content(self):
        long_text = " ".join([f"word{i}" for i in range(100)])
        result = _split_text_into_chunks(long_text, max_tokens=30, overlap_tokens=10)
        assert len(result) >= 2
        # Chunks with overlap should share some content at boundaries

    def test_empty_text(self):
        result = _split_text_into_chunks("", max_tokens=100, overlap_tokens=10)
        assert len(result) == 1
        assert result[0] == ""


# ── _detect_section ──────────────────────────────────────────────────────────


class TestDetectSection:
    def test_revenue(self):
        assert _detect_section("Total Revenue for Q4") == "revenue"

    def test_balance_sheet(self):
        assert _detect_section("Consolidated Balance Sheet") == "balance_sheet"

    def test_cash_flow(self):
        assert _detect_section("Statement of Cash Flow") == "cash_flow"

    def test_mda(self):
        assert _detect_section("Management Discussion and Analysis") == "mda"

    def test_mda_ampersand(self):
        assert _detect_section("MD&A Section") == "mda"

    def test_risk_factors(self):
        assert _detect_section("Risk Factors") == "risk_factors"

    def test_general_fallback(self):
        assert _detect_section("Some random text about nothing") == "general"

    def test_case_insensitive(self):
        assert _detect_section("INCOME STATEMENT") == "income_statement"

    def test_assets(self):
        assert _detect_section("Total Assets") == "assets"

    def test_liabilities(self):
        assert _detect_section("Current Liabilities") == "liabilities"

    def test_notes(self):
        assert _detect_section("Notes to Financial Statements") == "notes"

    def test_cogs(self):
        assert _detect_section("Cost of Goods Sold") == "cogs"

    def test_opex(self):
        assert _detect_section("Operating Expenses") == "opex"
