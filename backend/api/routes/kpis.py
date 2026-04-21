"""
kpis.py

FastAPI router for the workspace KPI dashboard. Replaces the frontend's
previous pattern of firing 6 separate POST /chat/ calls on RightPanel
mount — now returns all 6 KPIs in one call, with SQLite-backed caching.

Role in project:
    HTTP layer for the KPI dashboard. Reads from and writes to the
    workspace_kpi_cache SQLite table. On cache miss, invokes the
    LangGraph orchestrator directly (in-process, not over HTTP) for
    each of the 6 canonical KPI prompts and stores the results.

Main parts:
    - KPI_PROMPTS: canonical prompts for the 6 KPIs. Every prompt includes
      the structured-output instruction that forces Claude to respond with
      a single "HEADLINE | PERIOD | NOTE" line (see KPI_FORMAT_INSTRUCTION).
    - parse_kpi_response(text): extracts {headline, period, note} from a
      Claude response. Handles well-formed pipe-delimited lines, markdown
      preambles, and falls back gracefully on malformed input.
    - CACHE_TTL: 24-hour cache window; entries older than this are stale.
    - GET /kpis/: returns cached or freshly-computed KPIs for the current
      workspace. Skips compute entirely if the workspace has zero documents.
      Response shape includes parsed headline/period/note per KPI so the
      frontend can render dashboard cards directly.
    - invalidate_workspace_cache(session, workspace_id): called by documents.py
      on upload/delete to clear stale entries.
    - _compute_kpis(ctx): invokes the LangGraph orchestrator for each of the
      6 prompts; separated so tests can monkeypatch it without touching the
      full graph.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.orm import Session

from backend.core.context import RequestContext, get_request_context
from backend.db.engine import get_session_factory
from backend.db.models import Document, WorkspaceKpiCache


router = APIRouter(prefix="/kpis", tags=["kpis"])


# IMPORTANT: Keep prompts SHORT and semantically focused. These strings are
# embedded by Gemini for RAG retrieval — any extra text (format instructions,
# boilerplate) dilutes the embedding and causes retrieval to miss relevant
# chunks. Format enforcement happens downstream via parse_kpi_response(), which
# extracts headline/period/note from Claude's natural markdown response.
KPI_PROMPTS: dict[str, str] = {
    "revenue":      "What was the total revenue in the most recent fiscal year?",
    "gross_margin": "What was the gross margin percentage in the most recent fiscal year?",
    "ebitda":       "What was EBITDA in the most recent fiscal year?",
    "net_income":   "What was net income in the most recent fiscal year?",
    "cash_balance": "What was the cash and cash equivalents balance at the most recent balance sheet date?",
    "runway":       "Estimate cash runway in months based on the latest cash balance and recent burn rate.",
}

CACHE_TTL = timedelta(hours=24)


# ── parser regex toolkit ─────────────────────────────────────────────────

# Match a line with 2–3 pipe-delimited parts (for rare cases where Claude
# emits the structured format anyway, or tests seed it directly). First part
# must contain a digit/%/$ so we don't mistake markdown table headers.
_PIPE_LINE_RE = re.compile(
    r'^\s*([^\|\n]*?[A-Za-z0-9%$][^\|\n]*?)\s*\|\s*([^\|\n]+?)(?:\s*\|\s*([^\|\n]*?))?\s*$',
    re.MULTILINE,
)

# Prominent dollar amounts: $22.6B, $22,632M, $22,632 million, $1.5 trillion
_DOLLAR_RE = re.compile(
    r'\$\s*([\d,]+(?:\.\d+)?)\s*(trillion|billion|million|thousand|[KMBT])?',
    re.IGNORECASE,
)

# Percentages: 45.2%, 45%, +13%
_PERCENT_RE = re.compile(r'([+-]?\d+(?:\.\d+)?)\s*%')

# Month counts for runway: 18 months, 24 mo, etc.
_MONTHS_RE = re.compile(r'(\d+(?:\.\d+)?)\s+months?\b', re.IGNORECASE)

# Fiscal period indicators. Alternation is order-sensitive — the longer
# "fiscal year ended ..." pattern is listed first so it wins against a bare
# "FY2024" comparison-year reference later in the same response.
_PERIOD_RE = re.compile(
    r'(?:fiscal\s+year\s+ended\s+[^\n]{0,40}?(\d{4})'   # fiscal year ended December 31, 2025
    r'|(Q[1-4]\s+\d{4})'                                 # Q3 2025
    r'|(?:FY|fiscal\s+year\s+)(\d{4}))',                 # FY2025 / fiscal year 2025
    re.IGNORECASE,
)

# Change indicators. Require a % sign to avoid matching date fragments
# like "2026-04-21" (which naïve regex would treat as `-04` change).
# Matches "+13% YoY", "-2.5%", "up 13%", "down 2.5%".
_CHANGE_RE = re.compile(
    r'(?<![\d\w])([+-]?\d+(?:\.\d+)?%(?:\s+YoY)?)'  # +13% YoY, -2.5%
    r'|((?:up|down)\s+\d+(?:\.\d+)?%)',              # up 13%, down 2.5%
    re.IGNORECASE,
)

# Phrases signaling the data is not determinable. Used by _is_insufficient
# to short-circuit the parser to an N/A headline instead of surfacing
# tangential numbers Claude may have listed for context.
_INSUFFICIENT_PHRASES = (
    "does not provide",
    "does not contain",
    "not explicitly",
    "not unambiguously",
    "not clearly",
    "insufficient",
    "cannot be computed",
    "cannot be determined",
    "not disclosed",
    "not reported",
    "unable to",
    "no data",
    "not available",
)

_MARKDOWN_PREFIXES = ("#", ">", "-", "*", "|")


def _shorten_dollar_amount(raw_num: str, unit: str | None) -> str:
    """Normalize '$22,632 million' → '$22.6B'; '$180' → '$180'."""
    try:
        n = float(raw_num.replace(",", ""))
    except ValueError:
        return f"${raw_num}" + (f" {unit}" if unit else "")

    # Apply unit multiplier
    mul = 1.0
    if unit:
        u = unit.lower()
        if u in ("k", "thousand"):    mul = 1e3
        elif u in ("m", "million"):   mul = 1e6
        elif u in ("b", "billion"):   mul = 1e9
        elif u in ("t", "trillion"):  mul = 1e12
    n *= mul

    # Pick a human-readable scale
    if n >= 1e9:
        return f"${n / 1e9:.1f}B"
    if n >= 1e6:
        return f"${n / 1e6:.0f}M"
    if n >= 1e3:
        return f"${n / 1e3:.0f}K"
    return f"${n:.0f}"


def _pick_best_dollar_match(text: str) -> str | None:
    """Among all $ amounts, prefer ones with explicit units (million / B / etc.).

    Without a unit, a number like 5,127 is ambiguous ($5K vs $5B). If ANY
    match in the response has a unit, use it; that's usually the prominent
    headline value. Falls back to the first match otherwise.
    """
    matches = list(_DOLLAR_RE.finditer(text))
    if not matches:
        return None
    # First, try to find a match with an explicit unit
    for m in matches:
        if m.group(2):
            return _shorten_dollar_amount(m.group(1), m.group(2))
    # All matches are unit-less. Take the first, but assume financial
    # context ≥ 4 digits means millions (industry convention).
    m = matches[0]
    raw_num = m.group(1).replace(",", "")
    try:
        n = float(raw_num)
    except ValueError:
        return f"${m.group(1)}"
    if n >= 1000:
        # Interpret as millions in financial filings context
        return _shorten_dollar_amount(m.group(1), "million")
    return _shorten_dollar_amount(m.group(1), None)


def _extract_headline(text: str, kpi_key: str | None = None) -> str:
    """Find the single most prominent number in the response.

    Default precedence: dollar > percentage > month count.
    For kpi_key='runway', months takes priority (cash balance + burn
    rate are incidentals; the headline is the runway duration).
    For kpi_key='gross_margin', percentage takes priority.
    """
    if kpi_key == "runway":
        order = ("months", "dollar", "percent")
    elif kpi_key == "gross_margin":
        order = ("percent", "dollar", "months")
    else:
        order = ("dollar", "percent", "months")

    for kind in order:
        if kind == "dollar":
            best = _pick_best_dollar_match(text)
            if best:
                return best
        elif kind == "percent":
            m = _PERCENT_RE.search(text)
            if m:
                val = m.group(1)
                if val.startswith("+"):
                    return f"+{val.lstrip('+')}%"
                return f"{val}%"
        elif kind == "months":
            m = _MONTHS_RE.search(text)
            if m:
                num = m.group(1).rstrip(".0") or "0"
                return f"{num} months"
    return ""


def _extract_period(text: str) -> str:
    """Find the fiscal period. Returns 'FY2025' / 'Q3 2025' / '' if none."""
    m = _PERIOD_RE.search(text)
    if not m:
        return ""
    if m.group(1):  # fiscal year ended December 31, 2025
        return f"FY{m.group(1)}"
    if m.group(2):  # Q3 2025
        return m.group(2).upper()
    if m.group(3):  # FY2025 / fiscal year 2025
        return f"FY{m.group(3)}"
    return ""


def _extract_note(text: str) -> str:
    """Find a change/comparison indicator. Returns '+13% YoY' or '' if none."""
    m = _CHANGE_RE.search(text)
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


def _is_insufficient(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _INSUFFICIENT_PHRASES)


def parse_kpi_response(text: str, kpi_key: str | None = None) -> dict:
    """Extract {headline, period, note} from a Claude KPI response.

    Two code paths:
    1. If the response contains a "HEADLINE | PERIOD | NOTE" pipe line
       (structured format), use it directly.
    2. Otherwise — the common case — extract from natural markdown prose:
       find the most prominent dollar / percentage / month number, the
       fiscal period, and any change indicator.

    The optional `kpi_key` biases headline precedence (e.g. "runway"
    prefers months over dollar amounts that appear earlier in the text).

    Always returns a dict with the three keys; never raises.
    """
    if not text or not text.strip():
        return {"headline": "", "period": "", "note": ""}

    # Strip markdown bold/italic markers that would break regex patterns
    # (they appear around values like **December 31, 2025** or **$22.6B**).
    clean = text.replace("**", "").replace("__", "")

    # Path 1: structured pipe-delimited format (rare; useful for direct tests)
    for match in _PIPE_LINE_RE.finditer(clean):
        headline = match.group(1).strip()
        period = match.group(2).strip()
        note = (match.group(3) or "").strip()
        if re.search(r"[\d$%]", headline) or headline.upper().startswith("N/A"):
            return {"headline": headline, "period": period, "note": note}

    # Path 2: extract from prose.
    # Special case: when the prose signals insufficient data AND the available
    # dollar matches are all unit-less (likely tangential reference numbers,
    # like Total Assets listed while discussing cash balance), surface N/A
    # rather than a misleading headline. If any dollar match has an explicit
    # unit (e.g. "$11,100 million"), that number IS the reliable answer —
    # often a derived figure — and we use it.
    dollar_matches = list(_DOLLAR_RE.finditer(clean))
    any_unit = any(m.group(2) for m in dollar_matches)
    if _is_insufficient(clean) and not any_unit:
        lower = clean.lower()
        for phrase, msg in (
            ("not explicitly",      "Not explicitly reported"),
            ("not unambiguously",   "Not clearly identifiable"),
            ("not clearly",         "Not clearly identifiable"),
            ("does not provide",    "Data not provided in filing"),
            ("does not contain",    "Data not in filing"),
            ("not disclosed",       "Not disclosed"),
            ("not reported",        "Not reported"),
            ("insufficient",        "Insufficient data in filing"),
            ("cannot be computed",  "Cannot be computed"),
            ("cannot be determined","Cannot be determined"),
            ("unable to",           "Unable to determine"),
            ("no data",             "No data available"),
            ("not available",       "Not available"),
        ):
            if phrase in lower:
                return {"headline": "N/A", "period": _extract_period(clean), "note": msg}
        return {"headline": "N/A", "period": "", "note": "Data not disclosed"}

    headline = _extract_headline(clean, kpi_key=kpi_key)
    period = _extract_period(clean)
    note = _extract_note(clean)

    if headline:
        return {"headline": headline, "period": period, "note": note}

    # No number found — flag as insufficient data if prose signals it
    if _is_insufficient(text):
        # Map the first matching phrase to a clean short message, avoiding
        # the earlier bug where arbitrary slicing produced broken mid-word text.
        lower = text.lower()
        for phrase, msg in (
            ("not explicitly",      "Not explicitly reported"),
            ("does not provide",    "Data not provided in filing"),
            ("not disclosed",       "Not disclosed"),
            ("not reported",        "Not reported"),
            ("insufficient",        "Insufficient data in filing"),
            ("cannot be computed",  "Cannot be computed"),
            ("cannot be determined","Cannot be determined"),
            ("unable to",           "Unable to determine"),
            ("no data",             "No data available"),
            ("not available",       "Not available"),
        ):
            if phrase in lower:
                return {"headline": "N/A", "period": "", "note": msg}
        return {"headline": "N/A", "period": "", "note": "Data not disclosed"}

    # Final fallback: first non-markdown line, bounded length
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(_MARKDOWN_PREFIXES):
            return {"headline": stripped[:200], "period": "", "note": ""}

    return {"headline": text.strip()[:200], "period": "", "note": ""}


class KpiEntry(BaseModel):
    response: str           # raw Claude response (kept for debugging / fallback)
    citations: list[str]
    computed_at: datetime
    headline: str           # parsed from response via parse_kpi_response
    period: str             # parsed from response via parse_kpi_response
    note: str               # parsed from response via parse_kpi_response


class KpisResponse(BaseModel):
    kpis: Optional[dict[str, KpiEntry]]
    status: str  # "ready" | "empty"
    computed_at: Optional[datetime]
    cache_hit: bool


def invalidate_workspace_cache(session: Session, workspace_id: str) -> int:
    """Delete all KPI cache entries for a workspace. Returns rows deleted."""
    result = session.execute(
        sql_delete(WorkspaceKpiCache).where(WorkspaceKpiCache.workspace_id == workspace_id)
    )
    session.commit()
    return result.rowcount or 0


@router.get("/", response_model=KpisResponse)
def get_kpis(
    refresh: bool = Query(False, description="If true, ignore cache and recompute"),
    ctx: RequestContext = Depends(get_request_context),
) -> KpisResponse:
    """Return cached or freshly-computed KPIs for the caller's workspace.

    Short-circuits with status="empty" when no documents are present so the
    frontend can show a helpful placeholder without burning any Claude credits.
    Accepts ?refresh=true to force a recompute even when the cache is fresh.
    """
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        # 1. Empty workspace short-circuit
        doc_count = session.execute(
            select(Document).where(Document.workspace_id == ctx.workspace_id)
        ).all()
        if not doc_count:
            return KpisResponse(kpis=None, status="empty", computed_at=None, cache_hit=False)

        # 2. Cache-hit check
        if not refresh:
            cached_rows = session.execute(
                select(WorkspaceKpiCache).where(WorkspaceKpiCache.workspace_id == ctx.workspace_id)
            ).scalars().all()
            by_key = {r.kpi_key: r for r in cached_rows}
            cutoff = datetime.utcnow() - CACHE_TTL
            all_fresh = (
                len(by_key) == len(KPI_PROMPTS)
                and all(r.computed_at > cutoff for r in by_key.values())
            )
            if all_fresh:
                return KpisResponse(
                    kpis={
                        k: _entry_from_cache(by_key[k])
                        for k in KPI_PROMPTS
                    },
                    status="ready",
                    computed_at=max(r.computed_at for r in by_key.values()),
                    cache_hit=True,
                )

        # 3. Cache miss → compute all 6 via orchestrator
        kpi_entries = _compute_kpis(ctx)

        # 4. Upsert into cache: delete old rows, insert new ones
        session.execute(
            sql_delete(WorkspaceKpiCache).where(WorkspaceKpiCache.workspace_id == ctx.workspace_id)
        )
        for key, entry in kpi_entries.items():
            session.add(WorkspaceKpiCache(
                workspace_id=ctx.workspace_id,
                kpi_key=key,
                response=entry.response,
                citations=json.dumps(entry.citations),
                computed_at=entry.computed_at,
            ))
        session.commit()

        latest = max((e.computed_at for e in kpi_entries.values()), default=None)
        return KpisResponse(
            kpis=kpi_entries,
            status="ready",
            computed_at=latest,
            cache_hit=False,
        )


def _compute_kpis(ctx: RequestContext) -> dict[str, KpiEntry]:
    """Invoke the LangGraph orchestrator for each of the 6 KPI prompts.

    Separated from get_kpis() so tests can monkeypatch this function instead
    of having to mock the full LangGraph graph. Each invocation uses
    checkpointer=None (no state persistence) since KPI queries are stateless
    one-shots; this also avoids SQLite locking issues during test runs.
    """
    from backend.agents.orchestrator import build_graph
    from langchain_core.messages import HumanMessage

    graph = build_graph(checkpointer=None)
    now = datetime.utcnow()
    out: dict[str, KpiEntry] = {}
    for key, prompt in KPI_PROMPTS.items():
        state = {
            "messages": [HumanMessage(content=prompt)],
            "current_query": prompt,
            "user_id": ctx.user_id,
            "workspace_id": ctx.workspace_id,
            "chat_session_id": f"kpi_{key}_{ctx.workspace_id}",
            "intent": "document_qa",
            "retrieved_chunks": [],
            "formatted_context": "",
            "model_output": {},
            "response": "",
            "session_id": f"kpi_{key}_{ctx.workspace_id}",
            "citations": [],
        }
        result = graph.invoke(state)
        response_text = result.get("response", "")
        parsed = parse_kpi_response(response_text, kpi_key=key)
        out[key] = KpiEntry(
            response=response_text,
            citations=result.get("citations", []),
            computed_at=now,
            headline=parsed["headline"],
            period=parsed["period"],
            note=parsed["note"],
        )
    return out


def _entry_from_cache(row: WorkspaceKpiCache) -> KpiEntry:
    """Construct a KpiEntry from a cache row, re-parsing the response text.

    Re-parsing on read (instead of storing parsed fields in the table) keeps
    the cache schema simple and means prompt/parser improvements take effect
    on the next fetch without a migration — any existing markdown-style
    cached responses (from before the prompt-format change) get the parser's
    fallback treatment.
    """
    parsed = parse_kpi_response(row.response, kpi_key=row.kpi_key)
    return KpiEntry(
        response=row.response,
        citations=json.loads(row.citations),
        computed_at=row.computed_at,
        headline=parsed["headline"],
        period=parsed["period"],
        note=parsed["note"],
    )
