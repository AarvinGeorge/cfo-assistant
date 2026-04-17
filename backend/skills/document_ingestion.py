"""
document_ingestion.py

Parses uploaded financial documents and splits them into semantically
meaningful chunks ready for embedding and vector storage.

Role in project:
    Skills layer — document pipeline entry point. Called by the documents
    API route immediately after a file is saved to disk. Supports PDF
    (via pdfplumber), CSV (via pandas), plain text, and HTML
    (via BeautifulSoup). Produces Chunk objects consumed by
    vector_retrieval.py for embedding and upsert.

Main parts:
    - Chunk: dataclass holding chunk text, embedding vector slot, and
      metadata (doc_id, doc_name, doc_type, fiscal_year, section, page).
    - parse_pdf(): extracts full text and tables from a PDF using
      pdfplumber, with pdfminer.six as fallback.
    - parse_csv(): reads a CSV with pandas and serialises rows as text.
    - hierarchical_chunking(): splits parsed text into section-level
      chunks (512 tokens, 64-token overlap) and row-level chunks
      (128 tokens) for table content, using tiktoken for counting.
    - ingest_document(): top-level entry point that calls the right parser,
      chunks the output, and returns a list of Chunk objects.
"""

import uuid
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pdfplumber
import pandas as pd
import tiktoken

from backend.core.config import get_settings


@dataclass
class Chunk:
    chunk_id: str
    text: str
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    # metadata includes: doc_id, doc_name, doc_type, fiscal_year, section, page, chunk_type


def count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding (good proxy for Gemini tokenization)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def parse_pdf(file_path: str) -> Dict[str, Any]:
    """
    Extract text and tables from a PDF file.

    Returns:
        {
            "pages": [
                {
                    "page_number": 1,
                    "text": "full page text...",
                    "tables": [
                        [["Header1", "Header2"], ["val1", "val2"], ...]
                    ]
                },
                ...
            ],
            "full_text": "concatenated text of all pages",
            "table_count": 5,
            "page_count": 10
        }
    """
    pages = []
    full_text_parts = []
    table_count = 0

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            page_tables = page.extract_tables() or []

            # Normalize table values: strip whitespace, handle None
            cleaned_tables = []
            for table in page_tables:
                cleaned_table = []
                for row in table:
                    cleaned_row = [
                        _normalize_financial_value(cell) if cell else ""
                        for cell in row
                    ]
                    cleaned_table.append(cleaned_row)
                cleaned_tables.append(cleaned_table)

            table_count += len(cleaned_tables)
            full_text_parts.append(page_text)

            pages.append({
                "page_number": i + 1,
                "text": page_text,
                "tables": cleaned_tables,
            })

    return {
        "pages": pages,
        "full_text": "\n\n".join(full_text_parts),
        "table_count": table_count,
        "page_count": len(pages),
    }


def parse_csv(file_path: str) -> Dict[str, Any]:
    """
    Parse and normalize a CSV financial file.

    Returns:
        {
            "rows": [{"col1": "val1", "col2": "val2"}, ...],
            "columns": ["col1", "col2"],
            "row_count": 100,
            "full_text": "tabular representation as text"
        }
    """
    df = pd.read_csv(file_path)

    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]

    # Normalize financial values in all string columns
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(
            lambda x: _normalize_financial_value(str(x)) if pd.notna(x) else ""
        )

    rows = df.to_dict(orient="records")
    full_text = df.to_string(index=False)

    return {
        "rows": rows,
        "columns": list(df.columns),
        "row_count": len(rows),
        "full_text": full_text,
    }


def _normalize_financial_value(value: str) -> str:
    """Strip $, commas; handle parenthetical negatives like (1,234) -> -1234."""
    if not value or not isinstance(value, str):
        return value
    v = value.strip()
    # Handle accounting-style negatives: (1,234.56) -> -1234.56
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]
    # Remove $ and commas
    v = v.replace("$", "").replace(",", "").strip()
    return v


def hierarchical_chunk(
    parsed_doc: Dict[str, Any],
    doc_metadata: Dict[str, str],
) -> List[Chunk]:
    """
    Apply two-level chunking:
    - Section-level chunks (target ~512 tokens) for narrative text
    - Row-level chunks (target ~128 tokens) for individual financial line items from tables

    Args:
        parsed_doc: Output from parse_pdf() or parse_csv()
        doc_metadata: {
            "doc_id": "uuid",
            "doc_name": "filename.pdf",
            "doc_type": "10-K" | "income_statement" | "balance_sheet" | etc,
            "fiscal_year": "2024",
        }

    Returns:
        List of Chunk objects with rich metadata
    """
    settings = get_settings()
    chunks = []

    if "pages" in parsed_doc:
        # PDF document — process pages
        for page in parsed_doc["pages"]:
            page_num = page["page_number"]

            # Section-level chunks from narrative text
            if page["text"].strip():
                section_chunks = _split_text_into_chunks(
                    page["text"],
                    max_tokens=settings.section_chunk_tokens,
                    overlap_tokens=settings.chunk_overlap_tokens,
                )
                for i, text in enumerate(section_chunks):
                    chunks.append(Chunk(
                        chunk_id=str(uuid.uuid4()),
                        text=text,
                        token_count=count_tokens(text),
                        metadata={
                            **doc_metadata,
                            "page": page_num,
                            "chunk_type": "section",
                            "section": _detect_section(text),
                            "chunk_index": i,
                        },
                    ))

            # Row-level chunks from tables
            for table in page["tables"]:
                if len(table) < 2:
                    continue
                headers = table[0]
                for row_idx, row in enumerate(table[1:], start=1):
                    row_text = " | ".join(
                        f"{h}: {v}" for h, v in zip(headers, row) if v
                    )
                    if not row_text.strip():
                        continue
                    chunks.append(Chunk(
                        chunk_id=str(uuid.uuid4()),
                        text=row_text,
                        token_count=count_tokens(row_text),
                        metadata={
                            **doc_metadata,
                            "page": page_num,
                            "chunk_type": "row",
                            "section": _detect_section(
                                headers[0] if headers else ""
                            ),
                            "table_row": row_idx,
                        },
                    ))

    elif "rows" in parsed_doc:
        # CSV document — each row is a chunk
        for row_idx, row in enumerate(parsed_doc["rows"]):
            row_text = " | ".join(
                f"{k}: {v}" for k, v in row.items() if v
            )
            if not row_text.strip():
                continue
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                text=row_text,
                token_count=count_tokens(row_text),
                metadata={
                    **doc_metadata,
                    "page": 1,
                    "chunk_type": "row",
                    "section": "data",
                    "table_row": row_idx + 1,
                },
            ))

    return chunks


def _split_text_into_chunks(
    text: str, max_tokens: int, overlap_tokens: int
) -> List[str]:
    """Split text into chunks of approximately max_tokens with overlap."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        start += max_tokens - overlap_tokens
        if start >= len(tokens):
            break

    return chunks


def _detect_section(text: str) -> str:
    """Best-effort section detection from text content."""
    text_lower = text.lower().strip()
    section_keywords = {
        "revenue": "revenue",
        "income statement": "income_statement",
        "balance sheet": "balance_sheet",
        "cash flow": "cash_flow",
        "assets": "assets",
        "liabilities": "liabilities",
        "equity": "equity",
        "notes to": "notes",
        "risk factor": "risk_factors",
        "management discussion": "mda",
        "md&a": "mda",
        "executive summary": "executive_summary",
        "operating expense": "opex",
        "cost of": "cogs",
    }
    for keyword, section in section_keywords.items():
        if keyword in text_lower:
            return section
    return "general"
