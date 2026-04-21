# Spec: Workspace CRUD + UI Feature

**Status:** Pending user review
**Author:** Aarvin George + Claude (brainstorm 2026-04-20)
**Sub-project:** Multi-workspace MVP (was sub-project 4 of the broader roadmap)
**Predecessor:** Storage refactor w/ multi-tenant scaffolding (merged as PRs #4–#8)
**Figma:** [Workspace Switcher — MVP Sketch](https://www.figma.com/design/L9k0ZL0p6CGWBfuUOt31ec/?node-id=75-2) (approved)

---

## 1. Context & Goal

**Today:** storage is multi-tenant-ready (namespace per workspace, `RequestContext`, `StorageTransaction`). But there's only one hardcoded workspace (`wks_default`) and no UI for creating/switching between workspaces. The CFO story — "I advise multiple companies, each with their own context" — is blocked by the missing UI.

**Goal of this feature:** expose the existing multi-tenant primitives through a user-facing workspace switcher + create flow. After this ships, a CFO can create "Acme Corp" and "Beta Industries" as separate workspaces, upload docs into each, chat within each, and have complete data isolation between them — all from the UI.

**Non-goal:** auth (still single-user, hardcoded `usr_default`). That's a future sub-project.

---

## 2. Decisions Log

| # | Decision | Rationale |
|---|---|---|
| D1 | Switcher location: top of LeftPanel, above DOCUMENTS section | Primary navigation stays visible whenever LeftPanel is open; no header bar needed |
| D2 | Dropdown UX: standard click-to-toggle; active workspace shown with accent dot; "+ New Workspace" action at bottom of menu | Consistent with Slack / Linear / Notion — zero learning curve |
| D3 | Create modal fields: `name` (required), `description` (optional) | Minimum viable; avoids decision paralysis on colors/emoji/covers |
| D4 | **Auto-switch on create** | User's implicit intent after clicking Create is "…so I can use it." Saves a click, avoids "wait, did it save?" confusion |
| D5 | Archive / rename / delete — **deferred to v1.1** | v1.1 story; schema supports them already |
| D6 | Sharing — **deferred to v2** (auth must ship first) | Schema supports via `workspace_members`; behavior blocked on real auth |
| D7 | Workspace switch triggers re-fetch of docs, chats, KPIs | Simplest mental model: current workspace owns everything |
| D8 | Active `workspace_id` persisted to localStorage via `sessionStore` | Matches existing pattern; survives page reload |
| D9 | Bootstrap: if SQLite is empty, ensure `usr_default` + `wks_default` exist on first API request | Fresh-install safety; today's migration script seeded these but new clones don't run it |
| D10 | v1 limits: max workspace name 80 chars, description 500 chars; name required; workspace names not unique (user's discretion) | Keep schema simple; allow duplicates since v1 is single-user |

---

## 3. Architecture

### 3.1 Backend (3 new routes, all under `/workspaces`)

```
POST   /workspaces/           → create workspace; returns {id, name, description, status, created_at}
GET    /workspaces/           → list all non-archived workspaces for the current user
PATCH  /workspaces/{id}       → partial update (name, description, status)
```

All routes take `ctx: RequestContext = Depends(get_request_context)` — same pattern as documents + chat.

**DELETE is explicitly NOT in scope.** Use PATCH with `status=archived` instead (deferred UI, but the endpoint exists).

### 3.2 Data model

**No schema changes needed.** The `workspaces` table already has everything: `id`, `owner_id`, `name`, `description`, `status`, `created_at`, `updated_at`.

We add one Alembic data migration to seed defaults on fresh installs (D9):
```sql
INSERT OR IGNORE INTO users (id, display_name) VALUES ('usr_default', 'Local User');
INSERT OR IGNORE INTO workspaces (id, owner_id, name, status)
  VALUES ('wks_default', 'usr_default', 'Default Workspace', 'active');
INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role)
  VALUES ('wks_default', 'usr_default', 'owner');
```

`INSERT OR IGNORE` means this is idempotent — no-op on existing installs, seeds fresh ones.

### 3.3 Frontend

**New Zustand store:** `workspaceStore`
```typescript
interface WorkspaceStore {
  workspaces: Workspace[];         // list from GET /workspaces/
  loading: boolean;
  fetchWorkspaces: () => Promise<void>;
  createWorkspace: (name: string, description?: string) => Promise<Workspace>;
}
```

**New components:**
- `frontend/src/components/workspace/WorkspaceSwitcher.tsx` — the dropdown (three sub-states: closed / open / menu items)
- `frontend/src/components/workspace/CreateWorkspaceModal.tsx` — the create dialog
- Both placed in a new `components/workspace/` directory

**Store composition:**
- `sessionStore.workspaceId` remains the single source of truth for "active workspace"
- `workspaceStore.workspaces` is the list
- When `sessionStore.workspaceId` changes, the following auto-refetch:
  - `documentStore.fetchDocuments()`
  - `chatStore.clearChat()` (start fresh in new workspace)
  - `dashboardStore.refreshKPIs()`
- Wiring: a `useEffect` in `App.tsx` that watches `workspaceId` and triggers the three refetches

**Create flow (D4):**
1. User clicks "+ New Workspace" in dropdown → modal opens
2. User fills name (required) + description (optional) → clicks "Create workspace"
3. `POST /workspaces/` → receives `{id, name, ...}`
4. `workspaceStore.workspaces` is updated locally (optimistic append)
5. `sessionStore.workspaceId = newWorkspace.id` (triggers auto-refetch chain)
6. Modal closes
7. LeftPanel re-renders showing the empty new workspace + fresh chat state

### 3.4 Error handling

| Scenario | Behavior |
|---|---|
| Create with empty name | "Create" button disabled until name has content |
| Create with name > 80 chars | Input shows inline error; Create stays disabled |
| Network error during create | Modal stays open; error banner inside modal; user can retry or cancel |
| `GET /workspaces/` fails | `workspaceStore` shows error state; switcher shows "Error — retry" |
| Switch to nonexistent workspace | Backend returns 404 on /documents/; frontend catches + falls back to `wks_default` + shows toast |

---

## 4. Components & Interfaces

### 4.1 `WorkspaceSwitcher.tsx` (new)

**Responsibility:** render the switcher button + dropdown menu. Own only UI state (open/closed). Reads from `workspaceStore` + `sessionStore`. Writes `sessionStore.workspaceId` on selection.

**Props:** none (gets everything from stores).

**Depends on:** `workspaceStore`, `sessionStore`, `CreateWorkspaceModal` (rendered conditionally).

**Does NOT:** fetch workspaces (that's `workspaceStore.fetchWorkspaces`, called from `App.tsx` on mount).

### 4.2 `CreateWorkspaceModal.tsx` (new)

**Responsibility:** render the modal, manage form state locally, call `workspaceStore.createWorkspace` on submit.

**Props:**
```typescript
interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (workspace: Workspace) => void;  // parent handles auto-switch
}
```

**Depends on:** `workspaceStore` (for the create action), MUI Dialog components.

**Does NOT:** directly mutate `sessionStore.workspaceId`. That's the parent (`WorkspaceSwitcher`)'s job in `onCreated`.

### 4.3 `workspaceStore.ts` (new)

**Responsibility:** state + actions for the workspace list and create flow. No UI concerns.

### 4.4 Modifications to existing files

| File | Change |
|---|---|
| `frontend/src/components/panels/LeftPanel.tsx` | Import `<WorkspaceSwitcher />` at the top of the panel, above the documents section |
| `frontend/src/App.tsx` | Call `workspaceStore.fetchWorkspaces()` on mount; wire the `useEffect` that re-fetches downstream stores when `sessionStore.workspaceId` changes |
| `frontend/src/types/index.ts` | Export `Workspace` type matching backend shape |
| `backend/api/main.py` | Register new `workspaces_router` |

### 4.5 New backend files

| File | Responsibility |
|---|---|
| `backend/api/routes/workspaces.py` | FastAPI router with the 3 routes. Thin — delegates to SQLAlchemy queries directly. |
| `backend/db/migrations/versions/<n>_seed_defaults.py` | Alembic data migration for D9 bootstrap |
| `backend/tests/test_workspaces_api.py` | Unit tests for the 3 routes |

---

## 5. Success Criteria

A demo that hits all of the following is "done":

1. `make install` on a fresh clone brings up the app with `usr_default` + `wks_default` auto-seeded
2. LeftPanel shows "Default Workspace" in the switcher
3. Click switcher → dropdown shows "Default Workspace" with active dot and "+ New Workspace" action
4. Click "+ New Workspace" → modal opens
5. Type "Acme Corp" → Create button enables
6. Click Create → modal closes → LeftPanel now shows "Acme Corp" in switcher, zero documents, empty chat
7. Upload a PDF → it appears in Acme Corp's doc list
8. Switch to Default Workspace via dropdown → Acme's doc is NOT visible (workspace isolation verified)
9. Switch back to Acme → doc is there
10. Refresh the browser → Acme is still the active workspace (localStorage persistence)
11. `GET /workspaces/` returns both workspaces
12. All 242 existing unit tests + new tests pass
13. `make doctor` and `make stats` both green

---

## 6. Out of scope (deferred)

| Feature | Rationale for deferral |
|---|---|
| Archive workspace UI | Backend PATCH supports `status=archived`; no UI affordance in v1 |
| Rename workspace | Backend PATCH supports it; no UI (users recreate if unhappy) |
| Delete workspace | Destructive; needs confirmation flow; deferred to v1.1 |
| Multiple chats per workspace | Requires chat-sidebar UI; deferred to v1.1 |
| Sharing / workspace_members | Blocked on auth |
| Per-workspace colors / emoji / cover | Nice-to-have; v1.1 |
| Empty-state illustration when a workspace has 0 docs | Current "drop a file here" message is acceptable for MVP |
| Preventing name collisions | Allowed by design in v1; user takes responsibility |
| Search within workspace list | 4-workspace list doesn't need it. Revisit at 20+. |

---

## 7. Testing Strategy

| Layer | Approach |
|---|---|
| Backend routes | pytest unit tests with mocked SQLAlchemy session (fast); each route gets 3–4 tests (happy path, validation, not-found, auth-less defaults) |
| Alembic migration | Apply to a throwaway SQLite file; assert defaults exist |
| Frontend components | Zustand state logic via unit tests; component rendering via manual smoke test in browser (MVP speed — no Vitest setup yet) |
| End-to-end | Manual: run through the 13 success-criteria steps above |

---

## 8. Risks Accepted

| Risk | Mitigation |
|---|---|
| Workspace with duplicate name confuses user | UI shows `name + created date` if there are exact-match duplicates (deferred if we don't see duplicates in practice) |
| User creates 50 workspaces and dropdown gets unwieldy | We'll see — probably fine for MVP; add scroll / search in v1.1 if it becomes a problem |
| Race condition: user creates workspace + immediately switches | `createWorkspace` returns the new workspace; we use that return value directly to switch, not re-fetch. Safe. |
| Bootstrap data migration fails on schema mismatch | `INSERT OR IGNORE` is idempotent; worst case the migration is a no-op |

---

## 9. Open Questions

None. All major decisions resolved in brainstorming.

---

## 10. References

- `CLAUDE.md` — project source of truth
- Storage refactor spec: `docs/superpowers/specs/2026-04-20-storage-refactor-design.md`
- Figma: [Workspace Switcher MVP Sketch](https://www.figma.com/design/L9k0ZL0p6CGWBfuUOt31ec/?node-id=75-2)
- Implementation plan: TBD via `superpowers:writing-plans` after this spec is approved
