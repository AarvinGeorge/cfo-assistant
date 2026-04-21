"""
test_workspaces_api.py

Tests for the workspace CRUD routes. Uses an in-memory SQLite fixture
so the runtime database is never touched.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend.api.main import app
from backend.db.engine import create_engine_for_url, make_session_factory, get_session_factory
from backend.db.models import Base, User


@pytest.fixture
def test_client(monkeypatch):
    """FastAPI test client wired to an in-memory SQLite db with seeded default user.

    Uses StaticPool so all connections share the same in-memory database,
    which is required for SQLite :memory: to work across multiple connections
    opened by the route handlers.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as s:
        s.add(User(id="usr_default", email=None, display_name="Local User"))
        s.commit()

    # Patch get_session_factory so routes use this in-memory db
    monkeypatch.setattr(
        "backend.db.engine.get_session_factory",
        lambda: SessionLocal,
    )
    monkeypatch.setattr(
        "backend.api.routes.workspaces.get_session_factory",
        lambda: SessionLocal,
        raising=False,
    )
    # Clear lru_cache so our monkeypatch is seen
    get_session_factory.cache_clear()

    return TestClient(app)


def test_post_workspaces_creates_workspace(test_client):
    resp = test_client.post("/workspaces/", json={"name": "Acme Corp", "description": "FY26 audit"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Acme Corp"
    assert body["description"] == "FY26 audit"
    assert body["status"] == "active"
    assert body["id"].startswith("wks_")
    assert "created_at" in body


def test_post_workspaces_requires_name(test_client):
    resp = test_client.post("/workspaces/", json={"description": "no name"})
    assert resp.status_code == 422  # FastAPI validation error


def test_post_workspaces_rejects_empty_name(test_client):
    resp = test_client.post("/workspaces/", json={"name": "  ", "description": ""})
    assert resp.status_code == 400
    assert "name" in resp.json()["detail"].lower()


def test_post_workspaces_rejects_name_over_80_chars(test_client):
    resp = test_client.post("/workspaces/", json={"name": "X" * 81})
    assert resp.status_code == 400


def test_get_workspaces_returns_user_workspaces(test_client):
    test_client.post("/workspaces/", json={"name": "Acme Corp"})
    test_client.post("/workspaces/", json={"name": "Beta Industries"})

    resp = test_client.get("/workspaces/")
    assert resp.status_code == 200
    body = resp.json()
    names = {w["name"] for w in body}
    assert "Acme Corp" in names
    assert "Beta Industries" in names


def test_get_workspaces_excludes_archived(test_client):
    r1 = test_client.post("/workspaces/", json={"name": "Keep"})
    r2 = test_client.post("/workspaces/", json={"name": "Archive Me"})
    archived_id = r2.json()["id"]

    test_client.patch(f"/workspaces/{archived_id}", json={"status": "archived"})

    resp = test_client.get("/workspaces/")
    names = {w["name"] for w in resp.json()}
    assert "Keep" in names
    assert "Archive Me" not in names


def test_get_workspaces_scoped_to_current_user(test_client):
    test_client.post("/workspaces/", json={"name": "Mine"})
    from backend.db.engine import get_session_factory
    from backend.db.models import User, Workspace
    SL = get_session_factory()
    with SL() as s:
        s.add(User(id="usr_other", email=None, display_name="Other"))
        s.add(Workspace(id="wks_other", owner_id="usr_other", name="Other's", status="active"))
        s.commit()

    resp = test_client.get("/workspaces/")
    ids = {w["id"] for w in resp.json()}
    assert "wks_other" not in ids  # isolation


def test_patch_workspaces_updates_name(test_client):
    r = test_client.post("/workspaces/", json={"name": "Old"})
    wid = r.json()["id"]

    resp = test_client.patch(f"/workspaces/{wid}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


def test_patch_workspaces_archives(test_client):
    r = test_client.post("/workspaces/", json={"name": "Archive Me"})
    wid = r.json()["id"]

    resp = test_client.patch(f"/workspaces/{wid}", json={"status": "archived"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_patch_workspaces_not_found(test_client):
    resp = test_client.patch("/workspaces/wks_nonexistent", json={"name": "x"})
    assert resp.status_code == 404


def test_patch_workspaces_rejects_other_users_workspace(test_client):
    from backend.db.engine import get_session_factory
    from backend.db.models import User, Workspace
    SL = get_session_factory()
    with SL() as s:
        s.add(User(id="usr_other", email=None, display_name="Other"))
        s.add(Workspace(id="wks_other_owned", owner_id="usr_other", name="Other's", status="active"))
        s.commit()

    resp = test_client.patch("/workspaces/wks_other_owned", json={"name": "hijack attempt"})
    assert resp.status_code == 404
