"""
memory_tools.py

MCP tool implementations for audit logging and citation validation.

Role in project:
    MCP layer — file-only tools exposed to Claude for compliance and
    quality gates. Conversation memory itself is managed by LangGraph's
    SqliteSaver checkpointer (PR #4); this module no longer handles
    message persistence.

Main parts:
    - mcp_response_logger(): writes assistant responses to audit_log.jsonl.
    - mcp_intent_log(): records the classified intent for each query.
    - mcp_citation_validator(): checks every numerical claim has a source.
    - mcp_export_trigger(): signals the output-generation agent.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from backend.core.config import get_settings

AUDIT_LOG_FILE = "audit_log.jsonl"


def mcp_intent_log(session_id: str, intent: str, query: str) -> bool:
    """Log classified intent to audit trail."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "intent_classification",
        "session_id": session_id,
        "intent": intent,
        "query": query,
    }
    _append_audit_log(entry)
    return True


def mcp_citation_validator(response_text: str) -> dict:
    """
    Validate that every numerical claim in a response has a source citation.

    Looks for numbers (currency, percentages, plain numbers) and checks if
    they're followed by a [Source: ...] citation within the same paragraph.

    Returns:
        {
            "valid": bool,
            "total_claims": int,
            "cited_claims": int,
            "uncited_claims": int,
            "uncited_numbers": [list of uncited numerical claims],
            "citations_found": [list of citation strings],
        }
    """
    # Find all citations
    citations = re.findall(r'\[Source: ([^\]]+)\]', response_text)

    # Find numerical claims (currency, percentages, large numbers)
    number_pattern = r'(?:\$[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?%|(?<!\[)(?<!\w)[\d,]{4,}(?:\.\d+)?(?!\w)(?!\]))'
    numbers_found = re.findall(number_pattern, response_text)

    # Check which numbers appear near a citation (within same paragraph)
    paragraphs = response_text.split('\n\n')
    uncited = []
    cited_count = 0

    for para in paragraphs:
        para_numbers = re.findall(number_pattern, para)
        para_citations = re.findall(r'\[Source:', para)

        if para_numbers and not para_citations:
            uncited.extend(para_numbers)
        elif para_numbers:
            cited_count += len(para_numbers)

    total_claims = len(numbers_found)
    uncited_count = len(uncited)

    return {
        "valid": uncited_count == 0 or total_claims == 0,
        "total_claims": total_claims,
        "cited_claims": cited_count,
        "uncited_claims": uncited_count,
        "uncited_numbers": uncited[:10],  # cap at 10
        "citations_found": citations,
    }


def mcp_response_logger(session_id: str, query: str, response: str, citations: list) -> bool:
    """Log Q&A pair with citations to local audit file for CFO compliance."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "qa_response",
        "session_id": session_id,
        "query": query,
        "response_length": len(response),
        "response_preview": response[:500],
        "citations": citations,
        "citation_count": len(citations),
    }
    _append_audit_log(entry)
    return True


def mcp_export_trigger(session_id: str, export_type: str, model_name: str) -> bool:
    """Signal the Output Generation Agent when an export is requested."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "export_request",
        "session_id": session_id,
        "export_type": export_type,
        "model_name": model_name,
    }
    _append_audit_log(entry)
    # In Phase 6, this will trigger the actual output generation
    return True


def _append_audit_log(entry: dict) -> None:
    """Append a JSON entry to the audit log file."""
    settings = get_settings()
    log_dir = Path(settings.output_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / AUDIT_LOG_FILE

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
