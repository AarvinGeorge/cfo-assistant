# Spec: Storage Refactor with Multi-Tenant Scaffolding

**Status:** Pending user review
**Author:** Aarvin George + Claude (brainstorming session 2026-04-20)
**Sub-project:** 2 of 6 in the B′ plan (User → Workspace → Documents architecture)
**Predecessor incident:** ad-hoc Pinecone + Redis dual-store registry (origin of the orphan bug found 2026-04-20)
**Successor:** implementation plan via `superpowers:writing-plans` (next step after approval)

---

## 1. Context & Problem

### 1.1 The triggering incident

On 2026-04-20, `make stats` (a new operational tool) cross-referenced Pinecone vector counts with the Redis document registry and revealed:

| Source | Count |
|---|---|
| Pinecone vectors | 2,440 |
| Redis registry | 1 document, 1,220 chunks |
| **Delta** | **1,220 orphan vectors** |

Investigation showed the orphans were a duplicate copy of the registered EOG 10-K, ingested earlier with sloppy metadata (`type=General`, no fiscal year), then stranded when the Redis registry was wiped (likely via `docker rm redis-finsight`) and the user re-uploaded the document. The vectors survived because Pinecone is durable and external; the registry didn't.

### 1.2 Root causes (four orphan-creation pathways)

The single observed orphan was a symptom of a structural problem: the current design has **four distinct ways to create orphans**, all sharing one underlying flaw — **no transaction boundary between Pinecone and Redis**.

| # | Pathway | Trigger |
|---|---|---|
| 1 | Partial ingest | `embed_and_upsert` succeeds, then `register_document` fails (Redis down, crash, container wiped between calls) |
| 2 | Partial delete | Redis pipeline succeeds, then `index.delete()` fails or process crashes |
| 3 | Redis container recreation | `docker rm redis-finsight` — explicitly warned about in CLAUDE.md |
| 4 | Re-upload without dedup | User uploads same PDF twice → fresh UUID each time |

### 1.3 Active harm

Orphan vectors aren't dead weight. The RAG retrieval path (`semantic_search` in the orchestrator) queries Pinecone with no registry filter, so orphan chunks get returned alongside legitimate chunks — duplicating context, polluting the answer-generation prompt, and silently degrading answer quality. **This is a live RAG-quality issue, not just housekeeping.**

### 1.4 Why "evolve the architecture", not "patch the bug"

Per the systematic-debugging skill: when the same design produces multiple distinct failure modes (4 here), it's an architectural signal, not a one-more-fix signal. We're escalating to design-level redesign per Phase 4.5 of the debugging discipline.

---

## 2. Strategy — B′ (single-tenant refactor in multi-tenant-ready shape)

The user's broader vision (raised in the same session): scale to multiple users, each managing multiple companies. This naturally extends sub-project 2's scope.

We considered three approaches:

| Option | Description | Why we rejected/chose it |
|---|---|---|
| **A — Multi-tenant from day 1** | Bundle storage refactor + auth + projects + UI into one mega-spec | Rejected: 4-week unbroken scope, no incremental delivery, high stall risk |
| **B — Single-tenant Option A first, multi-tenant later** | Ship Pinecone-as-source-of-truth now, refactor again for tenancy | Rejected: requires refactoring every Pinecone call site twice |
| **B′ — Single-tenant refactor in multi-tenant-ready shape** | Drop Redis registry, switch to Pinecone-as-source-of-truth, **but** require `user_id` and `workspace_id` on every metadata write and namespace partition from day 1 (with hardcoded `"usr_default"` / `"wks_default"` until auth lands) | **Chosen.** Same effort as B, eliminates the second refactor when sub-project 3 (auth) ships |

**Net effect of B′:** today's behavior is unchanged for the single-user CFO. The data model is forward-compatible with the multi-tenant world. When sub-project 3 (auth) lands, the only change is "swap the hardcoded defaults for real values from the auth context" — a 5-line dependency change, not a re-architecture.

---

## 3. Decisions Log

| # | Decision | Rationale |
|---|---|---|
| D1 | Hierarchy: `User → Workspace → Documents` (flat workspaces, user labels each) | Matches Notion/Linear pattern; user-flexible labeling |
| D2 | Sharing model: solo workspaces in v1, designed for sharing in v2 (10% extra upfront, ~80% saved later) | Avoids re-architecture when sharing lands; sharing is a separate product decision |
| D3 | Pinecone partitioning: **namespace per workspace** | Defense-in-depth — Pinecone enforces workspace isolation at the platform level; missing app filter cannot leak data |
| D4 | Control plane: **SQLite** (single file at `data/finsight.db`) | Local-first, zero ops, real transactions, easy migration to Postgres via SQLAlchemy when going cloud |
| D5 | LangGraph checkpointer: `SqliteSaver` (replaces `RedisSaver`) | Consolidates state in one file; eliminates Redis from the stack |
| D6 | Drop Redis entirely | The exact service that caused the orphan disaster; no longer needed once SqliteSaver replaces RedisSaver |
| D7 | Workspace deletion: **archive only** in v1 (no permanent delete) | Eliminates accidental data loss; permanent delete is deferred to v1.1 if ever needed |
| D8 | Documents owned by workspace, **shared across N chats per workspace** | NotebookLM/ChatGPT-Projects/Claude-Projects pattern; avoids re-upload friction across analyses |
| D9 | Each chat is its own LangGraph thread (`thread_id = chat_session_id`) | Independent conversation contexts within a workspace |
| D10 | New workspace auto-creates a default first chat ("Untitled Chat") | Better first-use UX; no empty-state weirdness |

---

## 4. Data Model

### 4.1 Hierarchy

```
User
 └── Workspace                           (e.g. "Acme Corp")
      ├── Documents (N)                  (uploaded PDFs, shared across all chats)
      └── Chats (N)                      (independent conversation threads)
            └── LangGraph thread state   (per-chat checkpoints)
```

A workspace is a fully isolated context: its documents, chats, and Pinecone vectors are inaccessible to any other workspace (Pinecone-namespace-enforced).

### 4.2 Pinecone schema (data plane)

**Index:** `finsight-index` (unchanged — dim=3072, metric=cosine)
**Namespace:** literally the `workspace_id` string (e.g. `wks_acme`)
**Vector ID:** `doc_<uuid8>:<chunk_index>` — deterministic from doc_id + chunk index (replaces current random UUIDs)

**Metadata (per vector):**
```json
{
  "user_id":      "usr_default",        // v1: hardcoded; v2: real user
  "workspace_id": "wks_default",        // v1: hardcoded; v2: real workspace
  "doc_id":       "doc_<uuid8>",
  "doc_name":     "EOG-10K.pdf",        // original filename for citations
  "doc_type":     "10-K",
  "fiscal_year":  "2025",
  "page":          12,
  "chunk_type":   "section",            // "section" | "row" | "table"
  "section":      "MD&A",
  "chunk_index":   0,
  "text":         "<chunk text>",
  "token_count":   498
}
```

`user_id` and `workspace_id` are **required** on every upsert (defensive metadata even though namespace already partitions). They are NOT used as query filters — namespace handles that.

### 4.3 SQLite schema (control plane)

**File:** `data/finsight.db` (gitignored)
**ORM:** SQLAlchemy with Alembic for migrations

```sql
CREATE TABLE users (
    id              TEXT PRIMARY KEY,        -- usr_<uuid8>
    email           TEXT UNIQUE,
    display_name    TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workspaces (
    id              TEXT PRIMARY KEY,        -- wks_<uuid8>
    owner_id        TEXT NOT NULL REFERENCES users(id),
    name            TEXT NOT NULL,           -- user-given, e.g. "Acme M&A"
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'active',  -- active | archived
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_workspaces_owner_status ON workspaces(owner_id, status);

CREATE TABLE workspace_members (
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id),
    role            TEXT NOT NULL DEFAULT 'owner',  -- owner | editor | viewer (v2)
    added_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE documents (
    id              TEXT PRIMARY KEY,        -- doc_<uuid8>; same as Pinecone metadata
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id),  -- uploader, for audit
    name            TEXT NOT NULL,           -- original filename
    doc_type        TEXT,
    fiscal_year     TEXT,
    file_hash       TEXT,                    -- SHA-256 of file bytes (for dedup)
    chunk_count     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'indexed',  -- indexed | failed
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_workspace_file_hash ON documents(workspace_id, file_hash);

CREATE TABLE chat_sessions (
    id              TEXT PRIMARY KEY,        -- ses_<uuid8>; equals LangGraph thread_id
    user_id         TEXT NOT NULL REFERENCES users(id),
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title           TEXT,                    -- "Untitled Chat" by default
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP
);
CREATE INDEX idx_chat_sessions_workspace_recent
    ON chat_sessions(workspace_id, last_message_at DESC);
```

LangGraph's `SqliteSaver` manages its own tables (`checkpoints`, `writes`) inside the same `data/finsight.db` file.

### 4.4 File storage layout

```
data/uploads/{workspace_id}/{doc_id}.{ext}
```

- **Eliminates filename collisions** — two `Q3.pdf` uploads to different workspaces are physically distinct files
- **Workspace deletion** = `rm -rf data/uploads/{workspace_id}/` (unused in v1 since archive-only, but the structure supports it)
- **Original filename** preserved in `documents.name`

### 4.5 ID format

Typed prefixes for grep-friendliness and copy-paste safety:

| Type | Format | Example |
|---|---|---|
| User | `usr_<8 hex chars>` | `usr_a7b2c8d9` |
| Workspace | `wks_<8 hex chars>` | `wks_a7b2c8d9` |
| Document | `doc_<8 hex chars>` | `doc_a7b2c8d9` |
| Chat session | `ses_<8 hex chars>` | `ses_a7b2c8d9` |
| Pinecone vector | `<doc_id>:<chunk_index>` | `doc_a7b2c8d9:0042` |

Generated via `f"{prefix}_{uuid.uuid4().hex[:8]}"`.

---

## 5. Operations

### 5.1 RequestContext

Every request enters through a FastAPI dependency that yields:

```python
@dataclass(frozen=True)
class RequestContext:
    user_id:      str   # v1: "usr_default"; v2: from JWT
    workspace_id: str   # v1: "wks_default"; v2: from auth + URL/header
```

Routes consume it via `Depends(get_request_context)`. **Routes don't change between v1 and v2** — only the dependency implementation.

### 5.2 StorageTransaction helper

A context-manager that tracks compensating actions and runs them on exception. Eliminates the Pinecone+Redis-style drift by construction.

```python
class StorageTransaction:
    """Tracks compensating actions; rolls back on exception."""
    def __init__(self):
        self._undo: list[Callable] = []

    def add_file_write(self, dst_path: Path, data: bytes): ...
    def add_pinecone_upsert(self, store, vectors, namespace): ...
    def add_pinecone_delete(self, store, filter_dict, namespace): ...
    def add_sql(self, session, statement): ...

    def __enter__(self): return self
    def __exit__(self, exc_type, *_):
        if exc_type:
            for undo in reversed(self._undo):
                try: undo()
                except Exception: pass  # best-effort cleanup
            return False
```

If the SQL insert fails after Pinecone upsert succeeds, the upsert's compensating delete runs — no orphans by construction.

### 5.3 Upload pipeline

```
POST /documents/upload  (file, doc_type, fiscal_year)
  │
  ├─ ctx = (user_id, workspace_id) from RequestContext
  ├─ file_hash = sha256(file_bytes)
  │
  ├─ DEDUP CHECK:
  │     SELECT id FROM documents WHERE workspace_id = ? AND file_hash = ?
  │   ↓ found? return existing doc_id (idempotent)
  │
  ├─ Parse + chunk (unchanged from current code)
  ├─ Embed via Gemini (unchanged from current code)
  │
  └─ StorageTransaction:
       1. Move file → data/uploads/{workspace_id}/{doc_id}.{ext}
       2. INSERT INTO documents (...)
       3. Pinecone upsert into namespace = workspace_id
       COMMIT (or rollback all three on any exception)
```

### 5.4 List documents

```python
@router.get("/documents/")
def list_documents(ctx: RequestContext = Depends(get_request_context)):
    return db.execute("""
        SELECT id, name, doc_type, fiscal_year, chunk_count, created_at
        FROM documents
        WHERE workspace_id = ? AND status = 'indexed'
        ORDER BY created_at DESC
    """, (ctx.workspace_id,)).fetchall()
```

~5ms even at thousands of documents. Replaces the current Redis JSON-blob read.

### 5.5 Query / RAG

**Today:** `index.query(vector=..., namespace="default", filter={...})`
**After:** `index.query(vector=..., namespace=ctx.workspace_id)`

The orchestrator's `rag_retrieve` node passes the workspace_id from the agent state into the retrieval skill. Cross-workspace leakage is platform-impossible because namespaces are isolated.

### 5.6 Delete document

```python
@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, ctx: RequestContext = Depends(...)):
    # Access check: doc must belong to caller's workspace
    doc = db.query("SELECT * FROM documents WHERE id=? AND workspace_id=?",
                   (doc_id, ctx.workspace_id)).fetchone()
    if not doc:
        raise HTTPException(404)

    with StorageTransaction() as tx:
        tx.add_sql(session, delete(Document).where(Document.id == doc_id))
        tx.add_pinecone_delete(store, {"doc_id": doc_id}, namespace=ctx.workspace_id)
        tx.add_file_delete(Path(f"data/uploads/{ctx.workspace_id}/{doc_id}.{ext}"))
```

Past chat messages keep their text (citations degrade to "source no longer available").

### 5.7 Chat session lifecycle

| Event | Behavior |
|---|---|
| New workspace created | A default `chat_sessions` row is auto-inserted (title="Untitled Chat") |
| User clicks "+ New Chat" in UI | New `chat_sessions` row inserted, immediately becomes active |
| User selects a past chat | LangGraph resumes that thread (thread_id = chat_session_id) |
| User sends first message in untitled chat | Title auto-generated from first message (truncated to 60 chars) |
| User renames chat | `UPDATE chat_sessions SET title = ?` |
| User deletes chat | `DELETE FROM chat_sessions WHERE id = ?` + LangGraph cleanup of that thread's checkpoints |
| Workspace archived | Its chats become read-only (frontend disables input) |

### 5.8 Workspace lifecycle

| Event | Behavior |
|---|---|
| Created | `INSERT INTO workspaces` + auto-create default chat + Pinecone namespace materialises on first upsert (no explicit "create namespace" call needed) |
| Archived | `UPDATE workspaces SET status='archived'`. Disappears from switcher. All data preserved. Recoverable forever. |
| Unarchived | `UPDATE workspaces SET status='active'`. Reappears in switcher. |
| Permanent delete | **NOT in v1.** Deferred to v1.1 if ever needed. |

---

## 6. Cleanup + Migration

### 6.1 Pre-flight audit (every phase starts here)

```bash
make stats   # must show: Pinecone=2440, Redis=1220, 1220 orphan vectors
```

If state has drifted (new uploads since the audit), abort and re-plan.

### 6.2 Phase 1 — Orphan cleanup (PR #1, before refactor)

**Script:** `backend/scripts/cleanup_orphans.py`

```bash
make cleanup-orphans            # dry-run by default
make cleanup-orphans APPLY=1    # actually delete
```

Algorithm:
1. Scan all Pinecone vector IDs in `namespace=default`, fetch metadata in batches of 100
2. Group by `metadata.doc_id` → set of distinct doc_ids in Pinecone
3. Read `finsight:documents` from Redis → set of registered doc_ids
4. Orphans = Pinecone set − Redis set
5. For each orphan: `index.delete(filter={"doc_id": X}, namespace="default")` + audit log entry

Safety: dry-run default; APPLY required to delete; per-run audit log to `logs/cleanup_audit_<timestamp>.jsonl`; pre/post state checks.

After PR #1: `make stats` shows `0 orphans`.

### 6.3 Phase 2 — Pinecone namespace migration (in refactor PR)

Move 1,220 surviving vectors from `namespace=default` → `namespace=wks_default`, adding `user_id="usr_default"` and `workspace_id="wks_default"` to metadata.

```
1. fetch all vectors from namespace=default (vectors + metadata)
2. enrich metadata with user_id + workspace_id
3. regenerate vector IDs from random UUIDs to deterministic format:
     new_id = f"{metadata.doc_id}:{int(metadata.chunk_index):04d}"
4. upsert into namespace=wks_default in batches of 100 (with new IDs)
5. verify namespace=wks_default count == 1220
6. ONLY THEN delete the old namespace=default
```

The ID regeneration aligns existing vectors with the new convention (§4.5). `chunk_index` is already present in current metadata so reconstruction is deterministic.

Cost: ~$0.50 in Pinecone API calls. No Gemini re-embedding (vectors reused).

Rollback: until step 5, the old namespace still has all data. Steps 1–4 are non-destructive.

### 6.4 Phase 3 — SQLite seed (in refactor PR)

```sql
INSERT INTO users (id, email, display_name) VALUES ('usr_default', NULL, 'Local User');

INSERT INTO workspaces (id, owner_id, name, description, status)
VALUES ('wks_default', 'usr_default', 'Default Workspace',
        'Created during migration on 2026-04-20', 'active');

INSERT INTO workspace_members (workspace_id, user_id, role)
VALUES ('wks_default', 'usr_default', 'owner');

INSERT INTO documents (id, workspace_id, user_id, name, doc_type, fiscal_year,
                       file_hash, chunk_count, status)
VALUES ('doc_cee10473', 'wks_default', 'usr_default',
        'EOG (EOG Resources Inc.)  (10-K) 2026-02-24.pdf',
        '10-K', '2025', '<sha256>', 1220, 'indexed');

INSERT INTO chat_sessions (id, user_id, workspace_id, title)
VALUES ('ses_default', 'usr_default', 'wks_default', 'Untitled Chat');
```

Migration script computes `<sha256>` from file on disk; doc_id matches existing Pinecone metadata.

### 6.5 Phase 4 — Disk reorganization (in refactor PR)

```
BEFORE                                   AFTER
data/uploads/                            data/uploads/
├── EOG ... 2026-02-24.pdf       ─►     └── wks_default/
├── EOG ... _.pdf                            └── doc_cee10473.pdf
├── big.pdf
├── passwd.pdf                          data/uploads/_pre_migration/
├── quarterly_report.pdf                ├── EOG ... _.pdf
├── test.pdf                            ├── big.pdf
└── .env.csv                            ├── passwd.pdf
                                         ├── quarterly_report.pdf
                                         ├── test.pdf
                                         └── .env.csv
```

Six unrelated/test files moved to `_pre_migration/` (recoverable but out of active path). User can delete `_pre_migration/` whenever ready.

### 6.6 Phase 5 — Verification

```
✅ Pre-flight: 0 orphans (Phase 1 ran cleanly)
✅ SQLite: 1 user, 1 workspace, 1 member, 1 document, 1 chat_session
✅ Pinecone: namespace=wks_default has 1220 vectors
✅ Pinecone: namespace=default has 0 vectors
✅ Disk: data/uploads/wks_default/doc_cee10473.pdf exists; sha256 matches documents.file_hash
✅ Old code paths fail loudly (Redis client removed, finsight:documents references gone)
✅ Tests pass (229 unit + 23 integration, updated for new signatures)
✅ make doctor passes (Redis no longer expected)
```

If any check fails: refactor PR doesn't merge.

### 6.7 Rollback strategy

| Phase | Rollback |
|---|---|
| 1 (cleanup) | Cannot un-delete vectors. But pre-flight verifies orphan status before deleting; deleted vectors were duplicates, no info loss. |
| 2 (Pinecone migration) | Until step 5, old namespace `default` still has everything. Re-run after fixing. |
| 3 (SQLite seed) | `rm data/finsight.db` and re-run. |
| 4 (Disk reorg) | Files in `_pre_migration/` can be moved back. |
| 5 (Verification) | If any check fails before merge, no changes ship. |
| Post-merge issues | Revert PR #3. Old code is still in git history. |

---

## 7. PR Sequence

### 7.1 Overview

```
[design spec] ──► [PR #1: cleanup] ──► [PR #2: SQLite foundation]
                                            │
                                            ▼
                                       [PR #3: refactor + migration]
                                            │
                                            ▼
                                       [PR #4: remove Redis]
```

Each downstream PR gated on the previous one passing CI and user review.

### 7.2 PR #1 — Orphan cleanup

| | |
|---|---|
| **Goal** | Remove 1,220 orphan vectors |
| **Touches** | `backend/scripts/cleanup_orphans.py` (new), `Makefile` (new target), `backend/tests/test_cleanup_orphans.py` (new) |
| **Size** | ~100 lines including tests |
| **Risk** | Low — operational script, no app code |
| **Verify** | `make cleanup-orphans` (dry run) → review output → `make cleanup-orphans APPLY=1` → `make stats` shows 0 orphans → 229+23 tests pass |
| **Rollback** | Deleted vectors are gone (but were duplicates) |

### 7.3 PR #2 — SQLite foundation

| | |
|---|---|
| **Goal** | Introduce SQLite + new schema **alongside** existing Redis-based code |
| **Touches** | New: `backend/core/db.py`, `backend/db/schema.py`, `backend/db/migrations/`, `data/finsight.db` (gitignored), `requirements.txt` (+SQLAlchemy, +alembic, +langgraph-checkpoint-sqlite), tests |
| **Size** | ~400 lines + tests |
| **Risk** | Very low — purely additive |
| **Verify** | `alembic upgrade head` succeeds; new tests pass; old tests still pass; `make start` boots normally |
| **Rollback** | Delete `data/finsight.db` and revert |

### 7.4 PR #3 — Storage refactor + migration

| | |
|---|---|
| **Goal** | Switch all read/write paths to new schema; run data migration |
| **Touches** | New: `backend/core/context.py`, `backend/core/transactions.py`, `backend/scripts/migrate_to_workspace_schema.py`. Modified: `backend/api/routes/documents.py`, `backend/api/routes/chat.py`, `backend/agents/orchestrator.py`, `backend/skills/vector_retrieval.py`, `backend/mcp_server/tools/document_tools.py`. Frontend: `axiosClient.ts`, `chatStore.ts`, `documentStore.ts` (auto-inject `workspace_id="wks_default"`). Tests: ~30 updated, new tests for context + transactions + migration |
| **Size** | ~1,200 lines, ~30 files |
| **Risk** | Medium — every read/write path |
| **Verify** | Migration runs cleanly; all tests pass; manual smoke (upload + query); `make stats` shows `Pinecone[wks_default]=1220`, `SQLite documents=1` |
| **Rollback** | Revert PR; data state recoverable (Pinecone old namespace kept until success; SQLite file deletable) |

### 7.5 PR #4 — Remove Redis

| | |
|---|---|
| **Goal** | Remove Redis from the stack entirely |
| **Touches** | Removed: `backend/core/redis_client.py` and all imports; `redis` and `langgraph-checkpoint-redis` from requirements; Redis from `Makefile` and `make doctor`. Modified: orchestrator switches `RedisSaver` → `SqliteSaver`; `CLAUDE.md` and `README.md` updated |
| **Size** | ~150 lines, mostly deletions |
| **Risk** | Low if PR #3 verified solid |
| **Verify** | `make doctor` passes without Redis; chat sessions persist across `make stop && make start`; integration tests pass |
| **Rollback** | Revert; Redis comes back |

### 7.6 Timeline (rough)

| When | Capability |
|---|---|
| After PR #1 (~1 day) | RAG quality healthy. `make stats` clean. |
| After PR #2 (~1 day) | Schema in place, nothing user-visible. |
| After PR #3 (~2-3 days) | Multi-tenant-ready storage active. App behaves identically to user. SQLite is source of truth. Foundation for sub-project 3. |
| After PR #4 (~0.5 day) | Single-service backend. Orphan-bug-class structurally impossible. |

---

## 8. Out of Scope

Explicitly punted to future sub-projects (each its own brainstorm + spec + plan):

| Sub-project | Description |
|---|---|
| 3 — Auth | Replace hardcoded `usr_default` with real users via JWT-based auth (provider TBD: Clerk / Auth0 / Supabase / custom) |
| 4 — Workspace management | API + UI for creating, renaming, listing, archiving workspaces |
| 5 — UI overhaul | Workspace switcher, scoped panels, chat sidebar; **Figma mockups before code** per project rule |
| 6 — Per-chat document filter (v1.1) | UI toggle to scope a chat's RAG retrieval to a subset of workspace documents |
| 7 — Permanent workspace delete (v1.1+) | If ever needed; gated behind a confirmation modal |
| 8 — Cross-workspace search (v2) | "Research mode" that queries across a user's workspaces |
| 9 — Workspace sharing (v2) | Multi-user `workspace_members` with roles (owner/editor/viewer); invite flow; per-role access checks. The schema (`workspace_members`) and the `access_check(user, workspace) → bool` abstraction land in this spec; the *behaviour* of allowing N members lands in v2. |

---

## 9. Success Criteria

The refactor is complete when **all** of the following are true:

1. `make stats` reports 0 orphans
2. SQLite is the source of truth for users, workspaces, documents, chats
3. Every Pinecone call uses `namespace = workspace_id` (no namespace="default" anywhere)
4. Every Pinecone metadata write includes both `user_id` and `workspace_id`
5. Redis is no longer in `requirements.txt`, the Makefile, or any code path
6. `make doctor` passes without expecting Redis
7. Existing functional tests (229 unit + 23 integration) pass after migration
8. New tests cover: `RequestContext` resolution, `StorageTransaction` rollback, document dedup, multi-tenant query isolation
9. Manual smoke test: upload a new document, ask a question, get a cited answer scoped to the default workspace
10. CLAUDE.md and README.md updated to reflect new architecture

---

## 10. Risks & Open Questions

### Risks accepted

| Risk | Mitigation |
|---|---|
| Migration script bug strands data | Rollback plan per phase; non-destructive until final verification |
| SQLite single-writer limit | Acceptable for one backend process; switch to Postgres in cloud (Phase 6+) |
| LangGraph SqliteSaver performance vs Redis | Negligible at single-CFO scale; <50ms per turn |
| Frontend hardcoded `wks_default` until sub-project 3 | Acceptable; trivial to swap in real value when auth lands |

### Open questions

None. All major design decisions are resolved (see Decisions Log §3).

---

## 11. References

- `CLAUDE.md` — project source of truth, includes the operational gotchas and cheatsheet
- `README.md` — current architecture (will be updated in PR #4)
- `~/.claude/projects/.../memory/MEMORY.md` — feedback memories (Figma-first, SecretStr, playback-before-execute)
- Brainstorming session transcript: this session's chat history (2026-04-20)
- Investigation findings: in-session orphan investigation that triggered this refactor
- Future implementation plan: TBD via `superpowers:writing-plans` after this spec is approved
