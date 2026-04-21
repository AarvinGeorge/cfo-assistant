# Spec + Plan: Workspace KPI Cache (MVP)

**Status:** Approved inline — proceeding to implementation
**Author:** Aarvin George + Claude (2026-04-21, compressed MVP flow)

---

## Context

The RightPanel currently fires **6 `POST /chat/` calls on every mount** (KPI dashboard), each a full RAG + Claude pipeline = 12 Claude API calls per page load. Over a single day of dev testing this generated ~636 calls (~$9 in credits) silently. User now wants **SQLite caching + 24h TTL** so KPIs compute once per workspace and subsequent page loads serve from cache.

## Locked decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | TTL: 24 hours | Balances freshness vs cost; can be changed later |
| D2 | Cache invalidated on document upload/delete within the workspace | User's implicit expectation: fresh docs → fresh KPIs |
| D3 | Cache invalidated via manual "Refresh" button | User control |
| D4 | **If workspace has 0 documents: skip Claude entirely; show "Upload a document to see KPIs."** | Saves 12 credits per empty workspace. User's chosen option (a) |
| D5 | 6 KPI prompts move from frontend to backend (single source of truth) | Frontend sends one request; backend knows the 6 prompts |
| D6 | Frontend: replace 6 `/chat/` calls with 1 `/kpis/` call | Simpler, atomic, cache-friendly |
| D7 | "Updated N min ago" indicator below KPI cards | UX signal |

## Non-goals (v1.1)

- Per-KPI refresh (user can only refresh all 6 at once)
- Configurable TTL (hardcoded 24h)
- Background refresh (no cron; only lazy/manual invalidation)

---

## Data model

**New SQLite table `workspace_kpi_cache`** (via Alembic migration):

```sql
CREATE TABLE workspace_kpi_cache (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kpi_key      TEXT NOT NULL,       -- 'revenue' | 'gross_margin' | 'ebitda' | 'net_income' | 'cash_balance' | 'runway'
    response     TEXT NOT NULL,       -- Claude's markdown answer body
    citations    TEXT NOT NULL,       -- JSON-encoded list[str]
    computed_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (workspace_id, kpi_key)
);
```

**SQLAlchemy model `WorkspaceKpiCache`** added to `backend/db/models.py`.

## API surface

### `GET /kpis/?refresh=false`

**Query params:**
- `refresh` (bool, default `false`): if `true`, ignore existing cache and recompute

**Behavior:**
1. Read `ctx.workspace_id` from RequestContext
2. If the workspace has **zero** documents in the `documents` table → return `{"kpis": null, "status": "empty", "computed_at": null, "cache_hit": false}`
3. If not refresh and fresh cache exists for all 6 KPIs (age < 24h) → return cached values, `cache_hit: true`
4. Otherwise:
   - Invoke the orchestrator 6 times (one per KPI prompt)
   - Each call: direct in-process (not HTTP) — bypass the /chat/ route to avoid its overhead
   - Upsert all 6 results into `workspace_kpi_cache` table
   - Return the fresh values, `cache_hit: false`

**Response shape:**
```json
{
  "kpis": {
    "revenue":      {"response": "…", "citations": ["…"], "computed_at": "…"},
    "gross_margin": {...},
    "ebitda":       {...},
    "net_income":   {...},
    "cash_balance": {...},
    "runway":       {...}
  },
  "status": "ready",
  "computed_at": "2026-04-21T...",
  "cache_hit": true
}
```

When `status: "empty"`: `kpis: null`.

### Automatic invalidation hooks

In `backend/api/routes/documents.py`:
- After successful `upload_document` → `DELETE FROM workspace_kpi_cache WHERE workspace_id = ctx.workspace_id`
- After successful `delete_document` → same DELETE

## File structure

### Backend (Task A)

| Action | Path | Purpose |
|---|---|---|
| **Create** | `backend/db/migrations/versions/<rev>_workspace_kpi_cache.py` | Alembic migration for new table |
| **Modify** | `backend/db/models.py` | Add `WorkspaceKpiCache` model |
| **Create** | `backend/api/routes/kpis.py` | `GET /kpis/` route + the 6 KPI prompts + orchestrator-invoke logic |
| **Modify** | `backend/api/main.py` | Register `kpis_router` |
| **Modify** | `backend/api/routes/documents.py` | Add cache-invalidation DELETE after upload + delete |
| **Create** | `backend/tests/test_kpis_api.py` | Unit tests (Claude mocked): cache-hit returns cached, cache-miss computes + caches, empty workspace returns status=empty, invalidation on upload |

### Frontend (Task B)

| Action | Path | Purpose |
|---|---|---|
| **Modify** | `frontend/src/stores/dashboardStore.ts` | Replace 6-call pattern with single `/kpis/` call; add `forceRefresh` + `computed_at` + `status` (`loading`, `ready`, `empty`) |
| **Modify** | `frontend/src/components/panels/RightPanel.tsx` | Add Refresh button; show "Updated N min ago"; show "Upload a document to see KPIs." empty state |
| **Modify** | `frontend/src/types/index.ts` | Add `KpiResult` type matching backend |

---

## Implementation plan — subagent-ready

### Task A: Backend — dispatch to a single subagent

Steps (TDD discipline throughout):

**A1. Migration + model**
- Generate Alembic revision
- Write test that asserts the new table exists with correct columns
- Write the migration: `CREATE TABLE workspace_kpi_cache (...)` with the schema above
- Add `WorkspaceKpiCache` SQLAlchemy model to `backend/db/models.py`
- Run migration, verify
- Commit

**A2. Define the 6 KPI prompts + `GET /kpis/` route skeleton**
- Create `backend/api/routes/kpis.py` with:
  - `KPI_PROMPTS` constant: dict mapping `kpi_key` → prompt string
  - Route stub that returns empty dict for now
- Register in `main.py`
- Commit

**A3. Implement orchestrator invocation + caching**
- Write test: given a mock orchestrator that returns canned responses, calling `GET /kpis/` populates the cache table with 6 rows
- Implement: import the orchestrator's graph from `backend.agents.orchestrator`, build state with `workspace_id` from ctx, invoke for each prompt, write to cache
- Write test: calling `GET /kpis/` when cache is fresh returns cached values AND doesn't invoke the orchestrator (mock should have zero calls)
- Implement the cache-hit check
- Commit

**A4. Empty-workspace short-circuit**
- Write test: when the workspace has 0 documents, `GET /kpis/` returns `{status: "empty", kpis: null}` and orchestrator is NOT called
- Implement
- Commit

**A5. Cache invalidation on upload/delete**
- Write test: upload_document followed by GET /kpis/ triggers a fresh compute (cache was cleared)
- Modify `documents.py` routes to DELETE cache rows after successful upload/delete
- Commit

**A6. Live smoke test**
- Verify backend is running
- `curl http://localhost:8000/kpis/` → should return `empty` for any fresh workspace with no docs, OR cached for one with docs
- `curl http://localhost:8000/kpis/?refresh=true` → should re-compute (burns 12 Claude calls — only do this once)
- `curl http://localhost:8000/kpis/` again → should return `cache_hit: true` instantly

### Task B: Frontend — dispatch to a single subagent (in parallel with A)

**B1. Types**
- Add `KpiResult` type to `types/index.ts`

**B2. dashboardStore refactor**
- Remove the 6 `POST /chat/` calls
- Add single `GET /kpis/` call via axios
- Support `forceRefresh` param
- Track `status: 'loading' | 'ready' | 'empty'`, `computedAt: string | null`
- When store detects `status === 'empty'`, show empty UX in RightPanel

**B3. RightPanel update**
- Render "Upload a document to see KPIs." when `status === 'empty'`
- Render 6 KPI cards when `status === 'ready'`
- Add Refresh button that calls `dashboardStore.refreshKPIs()` (force=true)
- Show "Updated N min ago" with relative-time helper

**B4. Hook workspace-change into dashboardStore**
- `App.tsx` already re-calls `dashboardStore` actions when `workspaceId` changes (existing pattern)
- Verify the new `dashboardStore` is wired the same way

**B5. TypeScript clean check + commit each step**

---

## Success criteria (smoke test)

After both tasks land:

1. [ ] `make doctor` green, `pytest` passes (existing 255 + new ~10 = 265)
2. [ ] `GET /kpis/` on the current `wks_default` returns `cache_hit: false` first time (triggers 12 Claude calls, costs ~$0.30)
3. [ ] Second `GET /kpis/` within 24h returns `cache_hit: true` with **0 Claude calls** (verified by checking backend log)
4. [ ] Refreshing the frontend in browser 10 times triggers 0 new Claude calls (verified against audit_log.jsonl)
5. [ ] Upload a document → next `GET /kpis/` is a cache miss (auto-invalidated)
6. [ ] Create a new empty workspace → `GET /kpis/` returns `status: "empty"`, 0 Claude calls
7. [ ] Click Refresh button in UI → 12 Claude calls fire, KPI values update

---

## Out of scope

- Per-KPI manual refresh
- TTL configuration UI
- Background jobs / cron
- Workspace-share support (irrelevant until auth + multi-user lands)
