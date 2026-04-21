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
    - KPI_PROMPTS: canonical prompts for the 6 KPIs (revenue, gross_margin,
      ebitda, net_income, cash_balance, runway).
    - CACHE_TTL: 24-hour cache window; entries older than this are stale.
    - GET /kpis/: returns cached or freshly-computed KPIs for the current
      workspace. Skips compute entirely if the workspace has zero documents.
    - invalidate_workspace_cache(session, workspace_id): called by documents.py
      on upload/delete to clear stale entries.
    - _compute_kpis(ctx): invokes the LangGraph orchestrator for each of the
      6 prompts; separated so tests can monkeypatch it without touching the
      full graph.
"""
from __future__ import annotations

import json
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


KPI_PROMPTS: dict[str, str] = {
    "revenue":      "What was the total revenue in the most recent fiscal year? Include the dollar amount and the period.",
    "gross_margin": "What was the gross margin percentage in the most recent fiscal year? Include the calculation if possible.",
    "ebitda":       "What was EBITDA in the most recent fiscal year? Include the dollar amount and the period.",
    "net_income":   "What was net income in the most recent fiscal year? Include the dollar amount and the period.",
    "cash_balance": "What was the cash and cash equivalents balance at the most recent balance sheet date? Include the amount and date.",
    "runway":       "Based on the latest cash balance and recent burn rate, estimate the cash runway in months. Show the calculation.",
}

CACHE_TTL = timedelta(hours=24)


class KpiEntry(BaseModel):
    response: str
    citations: list[str]
    computed_at: datetime


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
                        k: KpiEntry(
                            response=by_key[k].response,
                            citations=json.loads(by_key[k].citations),
                            computed_at=by_key[k].computed_at,
                        )
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
        out[key] = KpiEntry(
            response=result.get("response", ""),
            citations=result.get("citations", []),
            computed_at=now,
        )
    return out
