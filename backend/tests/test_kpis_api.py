"""
test_kpis_api.py

Tests for the GET /kpis/ endpoint. The LangGraph orchestrator is
monkeypatched via _compute_kpis so no actual Claude calls are made;
we verify caching logic, empty-workspace short-circuit, force-refresh,
and stale-cache recompute.

Role in project:
    Test suite — covers the KPI cache route in isolation. Uses an
    in-memory SQLite fixture with StaticPool (same pattern as
    test_workspaces_api.py) so all connections share the same database.

Main parts:
    - test_client fixture: in-memory SQLite + seeded user/workspace +
      monkeypatched session factory.
    - _mock_compute_kpis: returns canned KpiEntry objects without calling
      any external service.
    - test_empty_workspace_returns_empty_status: verifies the short-circuit
      path when no documents are in the workspace.
    - test_cache_miss_invokes_orchestrator_and_writes_cache: verifies that
      on a cold cache the orchestrator is called and results are persisted.
    - test_cache_hit_skips_orchestrator: verifies the second request reads
      from cache without calling the orchestrator.
    - test_force_refresh_bypasses_cache: verifies ?refresh=true forces a
      recompute even when the cache is fresh.
    - test_stale_cache_triggers_recompute: verifies that entries older than
      24 hours are treated as cache misses.
"""
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from backend.api.main import app
from backend.db.engine import create_engine_for_url, make_session_factory, get_session_factory
from backend.db.models import (
    Base, User, Workspace, WorkspaceMember, Document, WorkspaceKpiCache,
)
from backend.api.routes.kpis import KPI_PROMPTS, KpiEntry


@pytest.fixture
def test_client(monkeypatch):
    """FastAPI test client backed by an in-memory SQLite database.

    Uses StaticPool so the in-memory db is shared across all connections
    opened by route handlers during the test. Seeds the default user,
    workspace, and workspace membership required by get_request_context().
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    # Seed default user + workspace + member
    with SessionLocal() as s:
        s.add(User(id="usr_default", email=None, display_name="Local User"))
        s.add(Workspace(id="wks_default", owner_id="usr_default", name="Default"))
        s.add(WorkspaceMember(workspace_id="wks_default", user_id="usr_default", role="owner"))
        s.commit()

    monkeypatch.setattr("backend.db.engine.get_session_factory", lambda: SessionLocal)
    monkeypatch.setattr("backend.api.routes.kpis.get_session_factory", lambda: SessionLocal, raising=False)
    monkeypatch.setattr("backend.api.routes.documents.get_session_factory", lambda: SessionLocal, raising=False)
    get_session_factory.cache_clear()
    return TestClient(app), SessionLocal


def _mock_compute_kpis(ctx):
    """Returns canned KpiEntry objects without calling Claude."""
    now = datetime.utcnow()
    return {
        key: KpiEntry(
            response=f"Mock {key}: $100M",
            citations=[f"mock-source-{key}.pdf"],
            computed_at=now,
        )
        for key in KPI_PROMPTS
    }


def test_empty_workspace_returns_empty_status(test_client, monkeypatch):
    """An empty workspace must return status='empty' without invoking the orchestrator."""
    client, _ = test_client
    call_count = [0]

    def tracking_compute(ctx):
        call_count[0] += 1
        return _mock_compute_kpis(ctx)

    monkeypatch.setattr("backend.api.routes.kpis._compute_kpis", tracking_compute)

    resp = client.get("/kpis/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "empty"
    assert body["kpis"] is None
    assert body["cache_hit"] is False
    assert call_count[0] == 0, "Empty workspace must not invoke orchestrator"


def test_cache_miss_invokes_orchestrator_and_writes_cache(test_client, monkeypatch):
    """Cold cache: orchestrator called once, all 6 rows written to SQLite."""
    client, SessionLocal = test_client
    # Seed a document so the workspace is non-empty
    with SessionLocal() as s:
        s.add(Document(id="doc_1", workspace_id="wks_default", user_id="usr_default",
                       name="test.pdf", chunk_count=10, status="indexed"))
        s.commit()

    call_count = [0]

    def tracking_compute(ctx):
        call_count[0] += 1
        return _mock_compute_kpis(ctx)

    monkeypatch.setattr("backend.api.routes.kpis._compute_kpis", tracking_compute)

    resp = client.get("/kpis/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["cache_hit"] is False
    assert len(body["kpis"]) == 6
    assert call_count[0] == 1

    # All 6 rows persisted in SQLite
    with SessionLocal() as s:
        rows = s.query(WorkspaceKpiCache).filter_by(workspace_id="wks_default").all()
        assert len(rows) == 6


def test_cache_hit_skips_orchestrator(test_client, monkeypatch):
    """Warm cache: second request reads from SQLite, orchestrator not called."""
    client, SessionLocal = test_client
    with SessionLocal() as s:
        s.add(Document(id="doc_1", workspace_id="wks_default", user_id="usr_default",
                       name="test.pdf", chunk_count=10, status="indexed"))
        s.commit()

    call_count = [0]

    def tracking_compute(ctx):
        call_count[0] += 1
        return _mock_compute_kpis(ctx)

    monkeypatch.setattr("backend.api.routes.kpis._compute_kpis", tracking_compute)

    # First call: cache miss → compute
    resp1 = client.get("/kpis/")
    assert resp1.json()["cache_hit"] is False
    assert call_count[0] == 1

    # Second call: cache hit → no compute
    resp2 = client.get("/kpis/")
    assert resp2.json()["cache_hit"] is True
    assert call_count[0] == 1, "Second call must not invoke orchestrator"
    assert len(resp2.json()["kpis"]) == 6


def test_force_refresh_bypasses_cache(test_client, monkeypatch):
    """?refresh=true forces recompute even when the cache is fresh."""
    client, SessionLocal = test_client
    with SessionLocal() as s:
        s.add(Document(id="doc_1", workspace_id="wks_default", user_id="usr_default",
                       name="test.pdf", chunk_count=10, status="indexed"))
        s.commit()

    call_count = [0]

    def tracking_compute(ctx):
        call_count[0] += 1
        return _mock_compute_kpis(ctx)

    monkeypatch.setattr("backend.api.routes.kpis._compute_kpis", tracking_compute)

    # Warm up cache
    client.get("/kpis/")
    assert call_count[0] == 1

    # Force refresh: should recompute despite fresh cache
    resp = client.get("/kpis/?refresh=true")
    assert resp.json()["cache_hit"] is False
    assert call_count[0] == 2


def test_stale_cache_triggers_recompute(test_client, monkeypatch):
    """Cache entries older than 24h are treated as a miss and recomputed."""
    client, SessionLocal = test_client
    stale_time = datetime.utcnow() - timedelta(hours=25)

    with SessionLocal() as s:
        s.add(Document(id="doc_1", workspace_id="wks_default", user_id="usr_default",
                       name="test.pdf", chunk_count=10, status="indexed"))
        # Pre-seed stale cache rows (25 hours old — past the 24h TTL)
        for key in KPI_PROMPTS:
            s.add(WorkspaceKpiCache(
                workspace_id="wks_default",
                kpi_key=key,
                response="old stale value",
                citations="[]",
                computed_at=stale_time,
            ))
        s.commit()

    call_count = [0]

    def tracking_compute(ctx):
        call_count[0] += 1
        return _mock_compute_kpis(ctx)

    monkeypatch.setattr("backend.api.routes.kpis._compute_kpis", tracking_compute)

    resp = client.get("/kpis/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cache_hit"] is False, "Stale cache must not return cache_hit=True"
    assert call_count[0] == 1, "Stale cache must trigger orchestrator call"
    # Fresh values replace stale ones
    for entry in body["kpis"].values():
        assert entry["response"] != "old stale value"
