"""
test_kpi_cache_invalidation.py

Unit tests for the KPI cache invalidation logic. Verifies that
invalidate_workspace_cache() correctly deletes cache rows for the
target workspace and leaves other workspaces untouched.

Role in project:
    Test suite — covers the cache invalidation helper that is called by
    the upload and delete document routes. Uses a raw SQLAlchemy session
    backed by in-memory SQLite rather than a full FastAPI test client, so
    there is no dependency on Gemini, Pinecone, or the file system.

Main parts:
    - db_session fixture: in-memory SQLite with all ORM tables created and
      two workspaces + their KPI cache rows seeded.
    - test_invalidate_removes_all_rows_for_workspace: confirms that all 6
      cache rows for the target workspace are deleted.
    - test_invalidate_leaves_other_workspaces_intact: confirms isolation —
      cache rows for a different workspace are not deleted.
    - test_invalidate_returns_row_count: confirms the return value equals
      the number of deleted rows.
    - test_invalidate_on_empty_cache_is_safe: confirms calling invalidate
      on a workspace with no cache rows does not raise.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend.db.engine import make_session_factory
from backend.db.models import Base, User, Workspace, WorkspaceMember, WorkspaceKpiCache
from backend.api.routes.kpis import KPI_PROMPTS, invalidate_workspace_cache

from datetime import datetime


@pytest.fixture
def db_session():
    """In-memory SQLite session with two workspaces and KPI cache rows seeded."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    with SessionLocal() as s:
        s.add(User(id="usr_default", email=None, display_name="Local User"))
        s.add(Workspace(id="wks_a", owner_id="usr_default", name="Workspace A"))
        s.add(Workspace(id="wks_b", owner_id="usr_default", name="Workspace B"))
        s.add(WorkspaceMember(workspace_id="wks_a", user_id="usr_default", role="owner"))
        s.add(WorkspaceMember(workspace_id="wks_b", user_id="usr_default", role="owner"))

        now = datetime.utcnow()
        for key in KPI_PROMPTS:
            s.add(WorkspaceKpiCache(
                workspace_id="wks_a",
                kpi_key=key,
                response=f"a-{key}",
                citations="[]",
                computed_at=now,
            ))
            s.add(WorkspaceKpiCache(
                workspace_id="wks_b",
                kpi_key=key,
                response=f"b-{key}",
                citations="[]",
                computed_at=now,
            ))
        s.commit()

    yield SessionLocal


def test_invalidate_removes_all_rows_for_workspace(db_session):
    """All 6 cache rows for wks_a are deleted; wks_b is untouched."""
    SessionLocal = db_session
    with SessionLocal() as s:
        deleted = invalidate_workspace_cache(s, "wks_a")

    assert deleted == len(KPI_PROMPTS)

    with SessionLocal() as s:
        remaining_a = s.query(WorkspaceKpiCache).filter_by(workspace_id="wks_a").count()
        remaining_b = s.query(WorkspaceKpiCache).filter_by(workspace_id="wks_b").count()

    assert remaining_a == 0
    assert remaining_b == len(KPI_PROMPTS)


def test_invalidate_leaves_other_workspaces_intact(db_session):
    """Invalidating wks_b does not affect wks_a rows."""
    SessionLocal = db_session
    with SessionLocal() as s:
        invalidate_workspace_cache(s, "wks_b")

    with SessionLocal() as s:
        remaining_a = s.query(WorkspaceKpiCache).filter_by(workspace_id="wks_a").count()

    assert remaining_a == len(KPI_PROMPTS)


def test_invalidate_returns_row_count(db_session):
    """Return value equals the number of rows deleted."""
    SessionLocal = db_session
    with SessionLocal() as s:
        count = invalidate_workspace_cache(s, "wks_a")

    assert count == len(KPI_PROMPTS)


def test_invalidate_on_empty_cache_is_safe(db_session):
    """Calling invalidate when no cache rows exist must not raise."""
    SessionLocal = db_session
    # First invalidation clears the rows
    with SessionLocal() as s:
        invalidate_workspace_cache(s, "wks_a")

    # Second invalidation on an already-empty cache must be a no-op
    with SessionLocal() as s:
        count = invalidate_workspace_cache(s, "wks_a")

    assert count == 0
