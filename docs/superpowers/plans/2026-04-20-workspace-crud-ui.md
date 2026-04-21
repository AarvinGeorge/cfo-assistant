# Workspace CRUD + UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan. Tasks 1 (backend) and 2 (frontend) are INDEPENDENT and can be dispatched in PARALLEL — they touch no shared files. Task 3 is a manual smoke test run after both complete.

**Goal:** Ship the user-facing workspace switcher + create flow so a CFO can manage multiple companies from the UI.

**Architecture:** Three new FastAPI routes (`POST`, `GET`, `PATCH /workspaces/`) going through the existing `RequestContext` dependency; one Alembic data migration to seed defaults on fresh installs; new Zustand `workspaceStore` + two React components (`WorkspaceSwitcher`, `CreateWorkspaceModal`); wire-up in `LeftPanel` + `App.tsx` so workspace changes trigger re-fetch of docs/chats/KPIs.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, Alembic, React 18, TypeScript, MUI v6, Zustand. No new deps.

**Spec:** [docs/superpowers/specs/2026-04-20-workspace-crud-ui-design.md](../specs/2026-04-20-workspace-crud-ui-design.md)

---

## File Structure

### Backend (Task 1 — dispatch to Agent A)

| Action | Path | Purpose |
|---|---|---|
| **Create** | `backend/api/routes/workspaces.py` | FastAPI router with POST/GET/PATCH, thin SQLAlchemy queries |
| **Create** | `backend/db/migrations/versions/<rev>_seed_defaults.py` | Alembic data migration — idempotent insert of `usr_default` + `wks_default` |
| **Create** | `backend/tests/test_workspaces_api.py` | pytest for the 3 routes |
| **Create** | `backend/tests/test_seed_defaults_migration.py` | Verify data migration seeds correctly + is idempotent |
| **Modify** | `backend/api/main.py` | Register `workspaces_router` alongside existing routers |

### Frontend (Task 2 — dispatch to Agent B)

| Action | Path | Purpose |
|---|---|---|
| **Create** | `frontend/src/stores/workspaceStore.ts` | Zustand store: list + fetchWorkspaces + createWorkspace |
| **Create** | `frontend/src/components/workspace/WorkspaceSwitcher.tsx` | Dropdown button + menu; mounts inside LeftPanel |
| **Create** | `frontend/src/components/workspace/CreateWorkspaceModal.tsx` | MUI Dialog with name + description form |
| **Modify** | `frontend/src/types/index.ts` | Add `Workspace` interface |
| **Modify** | `frontend/src/components/panels/LeftPanel.tsx` | Render `<WorkspaceSwitcher />` at the top of the panel |
| **Modify** | `frontend/src/App.tsx` | On mount: fetch workspaces. Watch `sessionStore.workspaceId` → re-fetch docs/chats/KPIs |

### Manual smoke test (Task 3)

After Tasks 1 + 2 merge to main, walk through the 13 success criteria from spec §5 in the browser.

---

# Task 1: Backend — Workspace Routes + Seed Migration

> Single subagent dispatch. TDD throughout. ~8 commits.

## 1.1 — Alembic data migration for defaults

**Files:**
- Create: `backend/db/migrations/versions/<new_rev>_seed_defaults.py`
- Create: `backend/tests/test_seed_defaults_migration.py`

- [ ] **Step 1: Generate a blank Alembic revision**

Run:
```bash
cd /Users/aarvingeorge/Documents/Climb/Profile_Builder/side-quests/finsight-cfo
PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/alembic revision -m "seed default user and workspace"
```

Expected: a new file at `backend/db/migrations/versions/<rev>_seed_default_user_and_workspace.py` with a stub `upgrade()` / `downgrade()`.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_seed_defaults_migration.py`:

```python
"""
test_seed_defaults_migration.py

Verifies the Alembic data migration seeds usr_default + wks_default
idempotently on a fresh SQLite file.
"""
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.db.engine import create_engine_for_url


def _apply_all_migrations(db_path: Path) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")


def test_migration_seeds_default_user_and_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        _apply_all_migrations(db_path)

        engine = create_engine_for_url(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            users = conn.execute(text("SELECT id FROM users WHERE id='usr_default'")).fetchall()
            workspaces = conn.execute(text("SELECT id FROM workspaces WHERE id='wks_default'")).fetchall()
            members = conn.execute(
                text("SELECT workspace_id, user_id, role FROM workspace_members "
                     "WHERE workspace_id='wks_default' AND user_id='usr_default'")
            ).fetchall()

        assert len(users) == 1
        assert len(workspaces) == 1
        assert len(members) == 1
        assert members[0][2] == "owner"


def test_migration_is_idempotent():
    """Running upgrade twice should not fail or create duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        _apply_all_migrations(db_path)

        # Manually re-run the data migration's SQL by just running upgrade again is a no-op
        # (alembic_version tracks what's applied). To exercise idempotency, downgrade -1 then upgrade.
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")

        engine = create_engine_for_url(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            users = conn.execute(text("SELECT COUNT(*) FROM users WHERE id='usr_default'")).scalar()
            workspaces = conn.execute(text("SELECT COUNT(*) FROM workspaces WHERE id='wks_default'")).scalar()

        assert users == 1, "Idempotency broken: duplicate user row"
        assert workspaces == 1, "Idempotency broken: duplicate workspace row"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_seed_defaults_migration.py -v
```
Expected: `test_migration_seeds_default_user_and_workspace` FAILS because the migration stub doesn't seed anything yet.

- [ ] **Step 4: Write the migration**

Open the Alembic file created in Step 1 (find it via `ls -t backend/db/migrations/versions/ | head -1`). Replace its body with:

```python
"""seed default user and workspace

Revision ID: <keep whatever alembic generated>
Revises: <keep whatever alembic generated>
Create Date: <keep whatever alembic generated>

"""
from typing import Sequence, Union

from alembic import op


# Keep the auto-generated revision / down_revision / branch_labels / depends_on as-is.

def upgrade() -> None:
    op.execute(
        "INSERT OR IGNORE INTO users (id, email, display_name, created_at) "
        "VALUES ('usr_default', NULL, 'Local User', CURRENT_TIMESTAMP)"
    )
    op.execute(
        "INSERT OR IGNORE INTO workspaces "
        "(id, owner_id, name, description, status, created_at, updated_at) "
        "VALUES ('wks_default', 'usr_default', 'Default Workspace', "
        "'Auto-created on first install', 'active', "
        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    op.execute(
        "INSERT OR IGNORE INTO workspace_members "
        "(workspace_id, user_id, role, added_at) "
        "VALUES ('wks_default', 'usr_default', 'owner', CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    # Only remove the seed rows if they look untouched (best-effort)
    op.execute("DELETE FROM workspace_members WHERE workspace_id='wks_default' AND user_id='usr_default'")
    op.execute("DELETE FROM workspaces WHERE id='wks_default'")
    op.execute("DELETE FROM users WHERE id='usr_default'")
```

Do NOT modify the revision / down_revision / branch_labels / depends_on variables — keep whatever Alembic generated.

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_seed_defaults_migration.py -v
```
Expected: 2 PASS.

- [ ] **Step 6: Re-apply migration to the real DB to ensure idempotency**

Run:
```bash
cd /Users/aarvingeorge/Documents/Climb/Profile_Builder/side-quests/finsight-cfo
PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/alembic upgrade head
```
Expected: Either "Running upgrade <prev> -> <new>, seed default user and workspace" on first run, or "no migrations to apply" on re-runs. Either way, existing data is untouched because of `INSERT OR IGNORE`.

- [ ] **Step 7: Commit**

```bash
git add backend/db/migrations/versions/*seed_default* backend/tests/test_seed_defaults_migration.py
git commit -m "feat(db): Alembic data migration to seed usr_default + wks_default

Idempotent via INSERT OR IGNORE. Ensures fresh clones have the default
user + workspace that the app expects, without breaking existing
installs that already have these rows (e.g., from the earlier
migrate_to_workspace_schema.py one-shot).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 1.2 — POST /workspaces/ route

**Files:**
- Create: `backend/api/routes/workspaces.py`
- Create: `backend/tests/test_workspaces_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_workspaces_api.py`:

```python
"""
test_workspaces_api.py

Tests for the workspace CRUD routes. Uses an in-memory SQLite fixture
so the runtime database is never touched.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.api.main import app
from backend.db.engine import create_engine_for_url, make_session_factory, get_session_factory
from backend.db.models import Base, User


@pytest.fixture
def test_client(monkeypatch):
    """FastAPI test client wired to an in-memory SQLite db with seeded default user."""
    engine = create_engine_for_url("sqlite:///:memory:")
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_workspaces_api.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.api.routes.workspaces'` (or 404 if the router returns nothing).

- [ ] **Step 3: Create the router with POST**

Create `backend/api/routes/workspaces.py`:

```python
"""
workspaces.py

FastAPI router for workspace CRUD — create, list, partial update.

Role in project:
    HTTP layer for workspace management. Called by the frontend
    WorkspaceSwitcher component. Every route goes through the
    RequestContext dependency so the caller is identified (v1:
    hardcoded usr_default).

Main parts:
    - POST /workspaces/: create a workspace owned by the requesting user.
    - GET /workspaces/: list workspaces the user owns (non-archived).
    - PATCH /workspaces/{id}: update name / description / status.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.context import RequestContext, get_request_context
from backend.db.engine import get_session_factory
from backend.db.models import Workspace, WorkspaceMember


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(..., description="User-given workspace name")
    description: Optional[str] = Field(None, description="Optional description")


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


def _new_workspace_id() -> str:
    return f"wks_{uuid.uuid4().hex[:8]}"


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceResponse:
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workspace name is required")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="Workspace name must be 80 characters or less")

    description = (payload.description or "").strip() or None
    if description and len(description) > 500:
        raise HTTPException(status_code=400, detail="Description must be 500 characters or less")

    SessionLocal = get_session_factory()
    workspace_id = _new_workspace_id()
    with SessionLocal() as session:
        w = Workspace(
            id=workspace_id,
            owner_id=ctx.user_id,
            name=name,
            description=description,
            status="active",
        )
        m = WorkspaceMember(workspace_id=workspace_id, user_id=ctx.user_id, role="owner")
        session.add_all([w, m])
        session.commit()
        session.refresh(w)
        return WorkspaceResponse(
            id=w.id, name=w.name, description=w.description,
            status=w.status, created_at=w.created_at, updated_at=w.updated_at,
        )
```

- [ ] **Step 4: Register the router in main.py**

In `backend/api/main.py`, find the other router imports (e.g., `from backend.api.routes.health import router as health_router`) and add:

```python
from backend.api.routes.workspaces import router as workspaces_router
```

Find the `app.include_router(...)` calls and add:

```python
app.include_router(workspaces_router)
```

- [ ] **Step 5: Run tests to verify POST passes (other tests may still fail)**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_workspaces_api.py::test_post_workspaces_creates_workspace backend/tests/test_workspaces_api.py::test_post_workspaces_requires_name backend/tests/test_workspaces_api.py::test_post_workspaces_rejects_empty_name backend/tests/test_workspaces_api.py::test_post_workspaces_rejects_name_over_80_chars -v
```
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/workspaces.py backend/api/main.py backend/tests/test_workspaces_api.py
git commit -m "feat(api): POST /workspaces/ route to create workspaces

Validates name (required, 1-80 chars) and description (optional, <=500 chars).
Generates wks_<uuid8> IDs. Creates Workspace + WorkspaceMember rows
atomically via SQLAlchemy session. Returns WorkspaceResponse shape.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 1.3 — GET /workspaces/ route

**Files:**
- Modify: `backend/api/routes/workspaces.py`
- Modify: `backend/tests/test_workspaces_api.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_workspaces_api.py`:

```python
def test_get_workspaces_returns_user_workspaces(test_client):
    # Create two workspaces
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

    # Archive via PATCH (will be tested separately; route must exist by now for this to work)
    test_client.patch(f"/workspaces/{archived_id}", json={"status": "archived"})

    resp = test_client.get("/workspaces/")
    names = {w["name"] for w in resp.json()}
    assert "Keep" in names
    assert "Archive Me" not in names


def test_get_workspaces_scoped_to_current_user(test_client):
    # Create one workspace for usr_default
    test_client.post("/workspaces/", json={"name": "Mine"})
    # Manually insert a workspace for a different user directly into SQLite
    # (simulates what would happen with real auth)
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
```

- [ ] **Step 2: Run the first new test to verify it fails**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_workspaces_api.py::test_get_workspaces_returns_user_workspaces -v
```
Expected: FAIL with 405 Method Not Allowed (POST exists but GET doesn't).

- [ ] **Step 3: Add GET route to workspaces.py**

Append to `backend/api/routes/workspaces.py`:

```python
@router.get("/", response_model=list[WorkspaceResponse])
def list_workspaces(
    ctx: RequestContext = Depends(get_request_context),
) -> list[WorkspaceResponse]:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        rows = session.execute(
            select(Workspace)
            .where(Workspace.owner_id == ctx.user_id)
            .where(Workspace.status != "archived")
            .order_by(Workspace.created_at.asc())
        ).scalars().all()
        return [
            WorkspaceResponse(
                id=w.id, name=w.name, description=w.description,
                status=w.status, created_at=w.created_at, updated_at=w.updated_at,
            )
            for w in rows
        ]
```

- [ ] **Step 4: Run the GET + scoping tests (archived test still needs PATCH, will re-run later)**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_workspaces_api.py::test_get_workspaces_returns_user_workspaces backend/tests/test_workspaces_api.py::test_get_workspaces_scoped_to_current_user -v
```
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/workspaces.py backend/tests/test_workspaces_api.py
git commit -m "feat(api): GET /workspaces/ route to list user's workspaces

Returns active workspaces (excludes archived) owned by the current
user from the RequestContext. Ordered by created_at ascending so the
UI dropdown lists oldest-first.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 1.4 — PATCH /workspaces/{id} route

**Files:**
- Modify: `backend/api/routes/workspaces.py`
- Modify: `backend/tests/test_workspaces_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_workspaces_api.py`:

```python
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
    # Insert a workspace owned by a different user
    from backend.db.engine import get_session_factory
    from backend.db.models import User, Workspace
    SL = get_session_factory()
    with SL() as s:
        s.add(User(id="usr_other", email=None, display_name="Other"))
        s.add(Workspace(id="wks_other_owned", owner_id="usr_other", name="Other's", status="active"))
        s.commit()

    resp = test_client.patch("/workspaces/wks_other_owned", json={"name": "hijack attempt"})
    assert resp.status_code == 404  # behaves as "not found" for isolation
```

- [ ] **Step 2: Run the first test to verify it fails**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_workspaces_api.py::test_patch_workspaces_updates_name -v
```
Expected: FAIL with 405 Method Not Allowed.

- [ ] **Step 3: Add PATCH route + payload model**

Append to `backend/api/routes/workspaces.py` (the `WorkspaceUpdate` model goes near `WorkspaceCreate` at the top):

```python
class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # "active" | "archived"
```

And the route at the bottom:

```python
@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceResponse:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        w = session.execute(
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .where(Workspace.owner_id == ctx.user_id)
        ).scalar_one_or_none()
        if w is None:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="Workspace name cannot be empty")
            if len(name) > 80:
                raise HTTPException(status_code=400, detail="Workspace name must be 80 characters or less")
            w.name = name

        if payload.description is not None:
            desc = payload.description.strip() or None
            if desc and len(desc) > 500:
                raise HTTPException(status_code=400, detail="Description must be 500 characters or less")
            w.description = desc

        if payload.status is not None:
            if payload.status not in ("active", "archived"):
                raise HTTPException(status_code=400, detail="status must be 'active' or 'archived'")
            w.status = payload.status

        w.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(w)
        return WorkspaceResponse(
            id=w.id, name=w.name, description=w.description,
            status=w.status, created_at=w.created_at, updated_at=w.updated_at,
        )
```

- [ ] **Step 4: Run all workspace API tests**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/test_workspaces_api.py -v
```
Expected: all 11 tests PASS (4 POST + 3 GET + 4 PATCH).

- [ ] **Step 5: Run the full suite to verify no regressions**

Run:
```bash
/Users/aarvingeorge/miniconda3/envs/finsight/bin/pytest backend/tests/ -q -k "not integration"
```
Expected: 253+ PASS (242 prior + 2 migration + 11 workspace routes = 255 total).

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/workspaces.py backend/tests/test_workspaces_api.py
git commit -m "feat(api): PATCH /workspaces/{id} route for name/description/status

Supports partial updates. Enforces same validation rules as POST.
Returns 404 (not 403) for workspaces owned by a different user, to
avoid leaking existence. Updates updated_at timestamp on every change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 1.5 — Live smoke test the backend

- [ ] **Step 1: Apply migrations + verify defaults exist**

Run:
```bash
cd /Users/aarvingeorge/Documents/Climb/Profile_Builder/side-quests/finsight-cfo
PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/alembic upgrade head
```
Expected: migration runs (or is no-op if already applied).

- [ ] **Step 2: Verify the live backend picked up the new router (uvicorn auto-reload)**

Run:
```bash
curl -sf http://localhost:8000/workspaces/ | python3 -m json.tool
```
Expected: JSON array with at least `{"id": "wks_default", "name": "Default Workspace", ...}`.

- [ ] **Step 3: Create a test workspace via curl**

Run:
```bash
curl -sf -X POST http://localhost:8000/workspaces/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "Smoke Test Workspace", "description": "Delete me"}' \
  | python3 -m json.tool
```
Expected: 201-style response with the new workspace. **Note the returned `id`.**

- [ ] **Step 4: Archive the test workspace (cleanup)**

Using the id from step 3, run:
```bash
curl -sf -X PATCH http://localhost:8000/workspaces/<id_from_step_3> \
  -H 'Content-Type: application/json' \
  -d '{"status": "archived"}' \
  | python3 -m json.tool
```
Expected: status field is "archived".

- [ ] **Step 5: Verify it's gone from the list**

Run:
```bash
curl -sf http://localhost:8000/workspaces/ | python3 -m json.tool
```
Expected: only `wks_default` — the smoke-test workspace is excluded (archived).

## Task 1 — Done criteria

- [ ] All 11 `test_workspaces_api.py` tests pass
- [ ] Both `test_seed_defaults_migration.py` tests pass
- [ ] Full unit suite has 0 failures
- [ ] Live smoke test round-trip works (create → archive → disappears from GET)
- [ ] 4 commits on main: 1 migration, 1 POST, 1 GET, 1 PATCH

---

# Task 2: Frontend — Workspace Switcher + Create Modal

> Single subagent dispatch. No TDD framework (Vitest not set up yet); verification is manual smoke in browser. ~5 commits. Parallel-safe with Task 1.

## 2.1 — Workspace type definition

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add the Workspace type**

Read the current file first:
```bash
cat frontend/src/types/index.ts
```

Append (or insert alongside other interfaces — check file for conventions):

```typescript
export interface Workspace {
  id: string
  name: string
  description: string | null
  status: 'active' | 'archived'
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/aarvingeorge/Documents/Climb/Profile_Builder/side-quests/finsight-cfo
git add frontend/src/types/index.ts
git commit -m "feat(frontend): add Workspace interface matching backend shape

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 2.2 — workspaceStore (Zustand)

**Files:**
- Create: `frontend/src/stores/workspaceStore.ts`

- [ ] **Step 1: Create the store**

Create `frontend/src/stores/workspaceStore.ts`:

```typescript
/**
 * workspaceStore.ts
 *
 * Zustand store managing the list of workspaces and workspace creation.
 * The "active workspace" is NOT tracked here — that's sessionStore.workspaceId,
 * which is persisted to localStorage.
 *
 * Role in project:
 *   Workspace feature state. Owned by WorkspaceSwitcher. fetchWorkspaces()
 *   is called once on mount from App.tsx to populate the dropdown.
 *
 * Main parts:
 *   - WorkspaceState: workspaces array, loading flag, error string.
 *   - fetchWorkspaces(): GET /workspaces/ and populates the store.
 *   - createWorkspace(): POST /workspaces/ and appends to the local list,
 *     returning the new workspace so callers can auto-switch.
 */
import { create } from 'zustand'
import axiosClient from '../api/axiosClient'
import { Workspace } from '../types'

interface WorkspaceState {
  workspaces: Workspace[]
  loading: boolean
  error: string | null
  fetchWorkspaces: () => Promise<void>
  createWorkspace: (name: string, description?: string) => Promise<Workspace>
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaces: [],
  loading: false,
  error: null,

  fetchWorkspaces: async () => {
    set({ loading: true, error: null })
    try {
      const res = await axiosClient.get<Workspace[]>('/workspaces/')
      set({ workspaces: res.data, loading: false })
    } catch (err: any) {
      set({
        workspaces: [],
        loading: false,
        error: err?.message ?? 'Failed to load workspaces',
      })
    }
  },

  createWorkspace: async (name: string, description?: string) => {
    const res = await axiosClient.post<Workspace>('/workspaces/', {
      name,
      description: description || null,
    })
    const newWorkspace = res.data
    set({ workspaces: [...get().workspaces, newWorkspace] })
    return newWorkspace
  },
}))
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/aarvingeorge/Documents/Climb/Profile_Builder/side-quests/finsight-cfo
git add frontend/src/stores/workspaceStore.ts
git commit -m "feat(frontend): workspaceStore with fetchWorkspaces + createWorkspace

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 2.3 — CreateWorkspaceModal component

**Files:**
- Create: `frontend/src/components/workspace/CreateWorkspaceModal.tsx`

- [ ] **Step 1: Create the component**

First create the directory:
```bash
mkdir -p frontend/src/components/workspace
```

Then create `frontend/src/components/workspace/CreateWorkspaceModal.tsx`:

```tsx
/**
 * CreateWorkspaceModal.tsx
 *
 * MUI Dialog that creates a new workspace.
 *
 * Role in project:
 *   Rendered by WorkspaceSwitcher when the user clicks "+ New Workspace".
 *   Calls workspaceStore.createWorkspace on submit; invokes onCreated
 *   callback so the parent can auto-switch to the new workspace.
 *
 * Main parts:
 *   - Props: open, onClose, onCreated (Workspace => void)
 *   - Local form state: name, description, submitting flag, error string
 *   - Validation: name required, max 80 chars; description max 500
 */
import { useState } from 'react'
import {
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
  TextField, Button, Alert,
} from '@mui/material'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { Workspace } from '../../types'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (workspace: Workspace) => void
}

export function CreateWorkspaceModal({ open, onClose, onCreated }: Props) {
  const createWorkspace = useWorkspaceStore((s) => s.createWorkspace)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const trimmedName = name.trim()
  const nameInvalid = trimmedName.length === 0 || trimmedName.length > 80
  const descInvalid = description.length > 500
  const canSubmit = !nameInvalid && !descInvalid && !submitting

  const handleClose = () => {
    if (submitting) return
    setName('')
    setDescription('')
    setError(null)
    onClose()
  }

  const handleSubmit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const newWorkspace = await createWorkspace(trimmedName, description.trim() || undefined)
      onCreated(newWorkspace)
      setName('')
      setDescription('')
      onClose()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to create workspace')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle>Create new workspace</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2, fontSize: 12 }}>
          A workspace is a company or deal context. Documents and conversations are scoped to it.
        </DialogContentText>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField
          autoFocus
          fullWidth
          required
          label="Name"
          placeholder="e.g. Acme Corp"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && canSubmit) handleSubmit() }}
          inputProps={{ maxLength: 80 }}
          helperText={nameInvalid && trimmedName.length > 80 ? 'Max 80 characters' : ' '}
          error={trimmedName.length > 80}
          sx={{ mb: 2 }}
        />
        <TextField
          fullWidth
          label="Description (optional)"
          placeholder="e.g. FY26 audit + M&A review"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          rows={2}
          inputProps={{ maxLength: 500 }}
          helperText={descInvalid ? 'Max 500 characters' : ' '}
          error={descInvalid}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>Cancel</Button>
        <Button onClick={handleSubmit} disabled={!canSubmit} variant="contained">
          {submitting ? 'Creating…' : 'Create workspace'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/aarvingeorge/Documents/Climb/Profile_Builder/side-quests/finsight-cfo
git add frontend/src/components/workspace/CreateWorkspaceModal.tsx
git commit -m "feat(frontend): CreateWorkspaceModal with validation + auto-switch callback

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 2.4 — WorkspaceSwitcher component

**Files:**
- Create: `frontend/src/components/workspace/WorkspaceSwitcher.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/workspace/WorkspaceSwitcher.tsx`:

```tsx
/**
 * WorkspaceSwitcher.tsx
 *
 * Dropdown button + menu rendered at the top of LeftPanel. Shows the
 * active workspace name with a chevron; click to open a menu listing
 * all workspaces plus a "+ New Workspace" action.
 *
 * Role in project:
 *   Primary navigation for the multi-workspace UX. Reads from
 *   workspaceStore (list) + sessionStore (active id). Writes to
 *   sessionStore.setWorkspaceId on selection. Renders
 *   CreateWorkspaceModal conditionally.
 *
 * Main parts:
 *   - Button with current workspace name + chevron
 *   - MUI Menu with workspace items (active shows accent dot)
 *   - Divider + "+ New Workspace" action at the bottom
 *   - Renders CreateWorkspaceModal; auto-switches to new workspace on create
 */
import { useState, useRef, MouseEvent } from 'react'
import {
  Button, Menu, MenuItem, Divider, ListItemIcon, ListItemText, Box, Typography,
} from '@mui/material'
import CircleIcon from '@mui/icons-material/FiberManualRecord'
import AddIcon from '@mui/icons-material/Add'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import { useSessionStore } from '../../stores/sessionStore'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { CreateWorkspaceModal } from './CreateWorkspaceModal'
import { Workspace } from '../../types'

export function WorkspaceSwitcher() {
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const loading = useWorkspaceStore((s) => s.loading)
  const workspaceId = useSessionStore((s) => s.workspaceId)
  const setWorkspaceId = useSessionStore((s) => s.setWorkspaceId)

  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const activeWorkspace = workspaces.find((w) => w.id === workspaceId)
  const activeLabel = activeWorkspace?.name ?? (loading ? 'Loading…' : 'Default Workspace')

  const openMenu = (e: MouseEvent<HTMLButtonElement>) => setMenuAnchor(e.currentTarget)
  const closeMenu = () => setMenuAnchor(null)

  const handleSelect = (id: string) => {
    setWorkspaceId(id)
    closeMenu()
  }

  const handleOpenCreate = () => {
    closeMenu()
    setModalOpen(true)
  }

  const handleCreated = (newWorkspace: Workspace) => {
    // D4: auto-switch to the new workspace
    setWorkspaceId(newWorkspace.id)
  }

  return (
    <>
      <Button
        ref={buttonRef}
        onClick={openMenu}
        fullWidth
        variant="outlined"
        endIcon={<KeyboardArrowDownIcon />}
        sx={{
          justifyContent: 'space-between',
          textTransform: 'none',
          bgcolor: 'background.paper',
          borderColor: Boolean(menuAnchor) ? 'primary.main' : 'divider',
          color: 'text.primary',
          py: 1,
          px: 1.5,
          '&:hover': { borderColor: 'primary.main' },
        }}
      >
        <Typography noWrap sx={{ fontWeight: 500 }}>{activeLabel}</Typography>
      </Button>

      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={closeMenu}
        PaperProps={{
          sx: { minWidth: buttonRef.current?.offsetWidth ?? 240, mt: 0.5 },
        }}
      >
        {workspaces.map((w) => {
          const isActive = w.id === workspaceId
          return (
            <MenuItem key={w.id} onClick={() => handleSelect(w.id)} selected={isActive}>
              <ListItemIcon sx={{ minWidth: 24 }}>
                {isActive
                  ? <CircleIcon sx={{ fontSize: 8, color: 'primary.main' }} />
                  : <Box sx={{ width: 8 }} />}
              </ListItemIcon>
              <ListItemText primary={w.name} />
            </MenuItem>
          )
        })}
        <Divider />
        <MenuItem onClick={handleOpenCreate} sx={{ color: 'primary.main' }}>
          <ListItemIcon sx={{ minWidth: 24 }}>
            <AddIcon fontSize="small" sx={{ color: 'primary.main' }} />
          </ListItemIcon>
          <ListItemText primary="New Workspace" primaryTypographyProps={{ fontWeight: 500 }} />
        </MenuItem>
      </Menu>

      <CreateWorkspaceModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={handleCreated}
      />
    </>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/aarvingeorge/Documents/Climb/Profile_Builder/side-quests/finsight-cfo
git add frontend/src/components/workspace/WorkspaceSwitcher.tsx
git commit -m "feat(frontend): WorkspaceSwitcher dropdown with list + create flow

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 2.5 — Mount in LeftPanel + wire App.tsx refetches

**Files:**
- Modify: `frontend/src/components/panels/LeftPanel.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add the switcher to the top of LeftPanel**

Read the current file:
```bash
cat frontend/src/components/panels/LeftPanel.tsx
```

Find the opening `Box` / container that renders the panel content (when `leftPanelOpen` is true). Near the top of that container — BEFORE the documents section — add the import and the component:

In the imports:
```typescript
import { WorkspaceSwitcher } from '../workspace/WorkspaceSwitcher'
```

In the JSX, inside the expanded-panel container, add as the FIRST child:
```tsx
<Box sx={{ p: 2, pb: 1 }}>
  <WorkspaceSwitcher />
</Box>
```

If there's already padding on the container, adjust so the switcher sits above the existing content without introducing double-padding.

- [ ] **Step 2: Wire App.tsx to fetch workspaces on mount and watch workspaceId**

Read the current file:
```bash
cat frontend/src/App.tsx
```

Add imports:
```typescript
import { useWorkspaceStore } from './stores/workspaceStore'
```

Inside the `App` component function body, add a `useEffect` to fetch workspaces on mount (place it alongside the existing effects that fetch documents/KPIs):

```tsx
const fetchWorkspaces = useWorkspaceStore((s) => s.fetchWorkspaces)
const fetchDocuments = useDocumentStore((s) => s.fetchDocuments)
const clearChat = useChatStore((s) => s.clearChat)
const refreshKPIs = useDashboardStore((s) => s.refreshKPIs)  // if this doesn't exist, use whatever the existing dashboard-load call is named
const workspaceId = useSessionStore((s) => s.workspaceId)

useEffect(() => {
  fetchWorkspaces()
}, [fetchWorkspaces])

useEffect(() => {
  // Re-load everything that's scoped to the current workspace when it changes
  fetchDocuments()
  clearChat()
  // If dashboard has a refresh action, call it here; otherwise it auto-refetches via its own mount effect
}, [workspaceId, fetchDocuments, clearChat])
```

**Note:** reuse whatever names exist in your `chatStore` and `dashboardStore`. If `refreshKPIs` doesn't exist, look for whatever action triggers the 6 KPI queries — call that. If the dashboard re-fetches on its own mount, no extra wiring needed there.

- [ ] **Step 3: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

If you get errors about `refreshKPIs` not existing on `dashboardStore`, check the actual store and swap the name to match. Remove the call entirely if the dashboard doesn't expose a refresh action — the component mount effect handles it.

- [ ] **Step 4: Smoke-test in the browser**

Run (in one terminal, already running probably):
```bash
make start  # or let the existing one continue
```

Open http://localhost:5173:
- [ ] LeftPanel top shows "Default Workspace" in a dropdown button
- [ ] Click the button → menu opens showing "Default Workspace" with an accent dot
- [ ] "+ New Workspace" item visible at the bottom of the menu
- [ ] Click "+ New Workspace" → modal opens
- [ ] Type "Test MVP" → click Create workspace
- [ ] Modal closes, switcher now shows "Test MVP", Sources panel is empty
- [ ] Click the switcher again → menu shows both workspaces with "Test MVP" as active
- [ ] Click "Default Workspace" → Sources panel re-populates with the EOG 10-K
- [ ] Refresh the browser → whichever workspace was last active is still active

- [ ] **Step 5: Clean up the test workspace (optional)**

Via curl:
```bash
curl -sf http://localhost:8000/workspaces/ | python3 -m json.tool
# find the Test MVP id, then:
curl -sf -X PATCH http://localhost:8000/workspaces/<test_mvp_id> \
  -H 'Content-Type: application/json' -d '{"status":"archived"}'
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/panels/LeftPanel.tsx frontend/src/App.tsx
git commit -m "feat(frontend): mount WorkspaceSwitcher in LeftPanel + wire refetches

App.tsx fetches workspaces on mount. When sessionStore.workspaceId
changes (user switches workspace), documents refetch and chat clears
so the user sees a fresh context for the new workspace.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 2 — Done criteria

- [ ] TypeScript compiles cleanly (`npx tsc --noEmit`)
- [ ] Browser smoke test passes all 8 sub-steps above
- [ ] Workspace selection persists across page refresh
- [ ] Switching workspaces clears chat + refetches documents
- [ ] 5 commits on main

---

# Task 3: End-to-End Smoke Test (manual, after 1+2 merge)

Work through the spec's 13 success criteria (spec §5). This is manual — no automation.

- [ ] **1. Defaults seed on fresh install**

Run:
```bash
rm -f data/finsight.db*
PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/alembic upgrade head
```
Then:
```bash
PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/python -c "
from backend.db.engine import get_session_factory
from backend.db.models import User, Workspace, WorkspaceMember
with get_session_factory()() as s:
    print('users=', s.query(User).count())
    print('workspaces=', s.query(Workspace).count())
    print('members=', s.query(WorkspaceMember).count())
"
```
Expected: `users=1 workspaces=1 members=1`.

**⚠ Destructive if run on production data. Only do this after backing up `data/finsight.db`.** Skip this step and rely on the data migration running on its own if you don't want a fresh-wipe test.

- [ ] **2–13. Walk through the remaining spec §5 success criteria in the browser.**

The success criteria cover: switcher visible, dropdown opens, modal opens, create works, switching isolates docs, isolation is bidirectional, refresh persists, `GET /workspaces/` returns both, tests still pass, `make doctor` + `make stats` green.

- [ ] **Last step: run `make doctor` and `make stats`**

```bash
make doctor
make stats
```
Expected: all green, no orphans, workspace count matches.

## Task 3 — Done criteria

- [ ] All 13 success-criteria items pass
- [ ] `make doctor` ✅
- [ ] `make stats` ✅ no orphans

---

## Self-Review Notes

Reviewing the plan against the spec:

**Spec §1 (Context/Goal)** → covered by Task 1+2 shipping the 3 routes + UI switcher.

**Spec §2 (10 decisions)** → D1 (location) in Task 2.5; D2 (modal fields) in Task 2.3; D3 (modal+dropdown UX) in Task 2.4; D4 (auto-switch on create) in Task 2.4's `handleCreated`; D5 (archive/rename/delete deferred) not in any task — correct; D6 (sharing deferred) not in any task — correct; D7 (switch triggers re-fetch) in Task 2.5 App.tsx useEffect; D8 (persisted workspaceId) already in existing sessionStore — no code change needed; D9 (bootstrap seed) in Task 1.1; D10 (80/500 limits, non-unique names) enforced in Task 1.2 + 1.4 validation.

**Spec §3 (architecture)** — §3.1 routes in Task 1.2-1.4; §3.2 schema unchanged + migration in 1.1; §3.3 stores + components in Task 2; §3.4 error handling in Task 2.3's modal + Task 1's validation.

**Spec §4 (components/interfaces)** — §4.1 WorkspaceSwitcher in 2.4; §4.2 CreateWorkspaceModal in 2.3; §4.3 workspaceStore in 2.2; §4.4 modifications in 2.5 + 1.2.

**Spec §5 (13 success criteria)** — covered in Task 3 manual walk-through.

**Placeholder scan:** no TBDs or "similar to Task N" shortcuts. Every code step has full code.

**Type consistency:** `Workspace` interface identical across types/index.ts, workspaceStore, CreateWorkspaceModal, WorkspaceSwitcher. `WorkspaceCreate`/`WorkspaceResponse`/`WorkspaceUpdate` Pydantic models in workspaces.py match frontend usage.

No gaps identified.
