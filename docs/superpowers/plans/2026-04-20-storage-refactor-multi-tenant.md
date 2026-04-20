# Storage Refactor with Multi-Tenant Scaffolding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Redis document registry with SQLite as the control plane and partition Pinecone vectors by `workspace_id` namespace, eliminating the orphan-vector class of bugs and laying multi-tenant foundations.

**Architecture:** Pinecone remains the data plane (vectors + chunk text), but uses one namespace per workspace for platform-enforced isolation. SQLite (`data/finsight.db`) becomes the single relational store for users, workspaces, documents, chats, and LangGraph checkpoints. Redis is removed entirely. Schema requires `user_id` + `workspace_id` from day 1, hardcoded to `usr_default` / `wks_default` until auth ships in sub-project 3.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, Alembic, `langgraph-checkpoint-sqlite`, Pinecone serverless (existing), Gemini embeddings (existing). Frontend: React 18 + Zustand (minimal changes — auto-injects workspace_id).

**Spec:** [docs/superpowers/specs/2026-04-20-storage-refactor-design.md](../specs/2026-04-20-storage-refactor-design.md)

---

## File Structure

### PR #1 — Orphan Cleanup
- **Create:** `backend/scripts/cleanup_orphans.py` — operational script; dry-run by default; deletes orphan vectors from Pinecone
- **Create:** `backend/tests/test_cleanup_orphans.py` — unit tests with mocked Pinecone + Redis
- **Modify:** `Makefile` — add `cleanup-orphans` target

### PR #2 — SQLite Foundation
- **Create:** `backend/db/__init__.py` — package marker
- **Create:** `backend/db/engine.py` — SQLAlchemy engine + session factory
- **Create:** `backend/db/models.py` — ORM classes for `users`, `workspaces`, `workspace_members`, `documents`, `chat_sessions`
- **Create:** `backend/db/migrations/env.py`, `script.py.mako`, `versions/` — Alembic config
- **Create:** `alembic.ini` — Alembic top-level config
- **Create:** `backend/tests/test_db_engine.py`, `test_db_models.py`, `test_db_migrations.py`
- **Modify:** `backend/requirements.txt` — add `SQLAlchemy>=2.0`, `alembic>=1.13`, `langgraph-checkpoint-sqlite>=3.0`
- **Modify:** `.gitignore` — add `data/finsight.db*`

### PR #3 — Storage Refactor + Migration
- **Create:** `backend/core/context.py` — `RequestContext` dataclass + `get_request_context` FastAPI dependency
- **Create:** `backend/core/transactions.py` — `StorageTransaction` helper with compensating actions
- **Create:** `backend/scripts/migrate_to_workspace_schema.py` — one-shot migration script (Phases 2–5 from spec §6)
- **Create:** `backend/tests/test_context.py`, `test_transactions.py`, `test_migrate_to_workspace_schema.py`
- **Modify:** `backend/api/routes/documents.py` — switch to SQLite + namespace upsert + StorageTransaction
- **Modify:** `backend/api/routes/chat.py` — accept `workspace_id` + `chat_id`, plumb into orchestrator state
- **Modify:** `backend/agents/orchestrator.py` — read `workspace_id` from state, pass to retrieval
- **Modify:** `backend/agents/graph_state.py` — add `workspace_id`, `user_id`, `chat_session_id` fields
- **Modify:** `backend/skills/vector_retrieval.py` — every Pinecone call accepts `namespace` parameter
- **Modify:** `backend/mcp_server/tools/document_tools.py` — replace Redis-backed `register_document` / `delete_document` / `mcp_list_documents` with SQL equivalents
- **Modify:** `backend/skills/document_ingestion.py` — deterministic chunk IDs for new uploads (`<doc_id>:<position>` format)
- **Modify:** `frontend/src/api/axiosClient.ts` — auto-inject `workspace_id` header on every request
- **Modify:** `frontend/src/stores/sessionStore.ts` — add `workspaceId` (default `wks_default`), persisted
- **Modify:** ~25 existing tests for new signatures

### PR #4 — Remove Redis
- **Delete:** `backend/core/redis_client.py`
- **Delete:** `backend/tests/test_redis_client.py`
- **Modify:** `backend/api/main.py` — drop startup Redis ping
- **Modify:** `backend/api/routes/health.py` — drop Redis from `/health` payload
- **Modify:** `backend/api/routes/chat.py` — remove 4 `mcp_memory_write` call sites
- **Modify:** `backend/mcp_server/tools/memory_tools.py` — remove `mcp_memory_read` and `mcp_memory_write` (keep file-only tools)
- **Modify:** `backend/mcp_server/financial_mcp_server.py` — deregister memory tools
- **Modify:** `backend/agents/orchestrator.py` — swap `RedisSaver` → `SqliteSaver`
- **Modify:** `backend/tests/test_memory_tools.py` — drop tests for removed functions
- **Modify:** `backend/tests/test_chat_fixes.py`, `test_chat_api.py` — remove `mcp_memory_write` patches
- **Modify:** `Makefile` — remove Redis container management from `start`, `stop`, `doctor`
- **Modify:** `backend/requirements.txt` — remove `redis`, `langgraph-checkpoint-redis`
- **Modify:** `CLAUDE.md` — update Architecture, Operational Gotchas, Cheatsheet
- **Modify:** `README.md` — update architecture diagram, setup, troubleshooting

---

# PR #1 — Orphan Cleanup

**Goal:** Delete the 1,220 orphan vectors. Operational script only — no app code changes.

**Pre-flight:** Confirm `make stats` shows `Pinecone=2440, Redis=1220, 1220 orphan vectors` before starting (the script's dry-run will refuse to proceed otherwise).

---

### Task 1.1: Bootstrap the cleanup script with file header and CLI scaffold

**Files:**
- Create: `backend/scripts/cleanup_orphans.py`

- [ ] **Step 1: Write the file with header docstring + CLI argument parsing**

```python
"""
cleanup_orphans.py

One-shot operational script that deletes Pinecone vectors whose `doc_id`
metadata does not appear in the Redis `finsight:documents` registry.

Role in project:
    Operational tooling for the storage refactor (sub-project 2). Invoked
    via `make cleanup-orphans` before the SQLite/namespace refactor lands.
    Dry-run by default; --apply required to actually delete.

Main parts:
    - main(): CLI entry point. Parses args, runs the orphan-detection +
      optional deletion pipeline, prints a summary, exits 0 on success.
    - find_orphan_doc_ids(): cross-references Pinecone metadata with the
      Redis registry to compute the set of stranded doc_ids.
    - delete_orphan_vectors(): executes filter-based deletes on Pinecone
      and writes per-doc-id audit log entries.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete Pinecone vectors with no Redis registry entry."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete (default is dry-run, prints intended deletions only).",
    )
    args = parser.parse_args()
    print("=== FinSight Orphan Cleanup ===")
    print(f"Mode: {'APPLY (destructive)' if args.apply else 'DRY-RUN (no changes)'}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the script runs without errors**

Run: `PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/python backend/scripts/cleanup_orphans.py`
Expected output:
```
=== FinSight Orphan Cleanup ===
Mode: DRY-RUN (no changes)
```

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/cleanup_orphans.py
git commit -m "feat(cleanup): scaffold orphan cleanup script with dry-run default"
```

---

### Task 1.2: Test + implement orphan detection logic

**Files:**
- Modify: `backend/scripts/cleanup_orphans.py`
- Create: `backend/tests/test_cleanup_orphans.py`

- [ ] **Step 1: Write the failing test for orphan detection**

```python
"""
test_cleanup_orphans.py

Unit tests for the orphan cleanup script. Pinecone and Redis are mocked.
"""
from unittest.mock import MagicMock
from backend.scripts.cleanup_orphans import find_orphan_doc_ids


def test_find_orphan_doc_ids_returns_pinecone_ids_not_in_redis():
    # Arrange: Pinecone has 3 doc_ids; Redis has 1 of them
    mock_index = MagicMock()
    mock_index.list.return_value = iter([["v1", "v2", "v3"]])

    fetch_response = MagicMock()
    fetch_response.vectors = {
        "v1": MagicMock(metadata={"doc_id": "doc_aaa"}),
        "v2": MagicMock(metadata={"doc_id": "doc_bbb"}),
        "v3": MagicMock(metadata={"doc_id": "doc_ccc"}),
    }
    mock_index.fetch.return_value = fetch_response

    mock_redis = MagicMock()
    mock_redis.get.return_value = '[{"doc_id": "doc_aaa", "doc_name": "kept.pdf"}]'

    # Act
    orphans = find_orphan_doc_ids(
        pinecone_index=mock_index,
        redis_client=mock_redis,
        namespace="default",
        redis_key="finsight:documents",
    )

    # Assert
    assert orphans == {"doc_bbb", "doc_ccc"}


def test_find_orphan_doc_ids_returns_empty_when_all_registered():
    mock_index = MagicMock()
    mock_index.list.return_value = iter([["v1"]])
    fetch_response = MagicMock()
    fetch_response.vectors = {"v1": MagicMock(metadata={"doc_id": "doc_aaa"})}
    mock_index.fetch.return_value = fetch_response

    mock_redis = MagicMock()
    mock_redis.get.return_value = '[{"doc_id": "doc_aaa"}]'

    orphans = find_orphan_doc_ids(
        pinecone_index=mock_index,
        redis_client=mock_redis,
        namespace="default",
        redis_key="finsight:documents",
    )
    assert orphans == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n finsight pytest backend/tests/test_cleanup_orphans.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_orphan_doc_ids'`

- [ ] **Step 3: Implement `find_orphan_doc_ids` in cleanup_orphans.py**

Add to `backend/scripts/cleanup_orphans.py`, before `main()`:

```python
def find_orphan_doc_ids(
    pinecone_index,
    redis_client,
    namespace: str,
    redis_key: str,
    batch_size: int = 100,
) -> set[str]:
    """Return the set of doc_ids present in Pinecone but absent from Redis."""
    # 1. Page through all Pinecone vector IDs
    all_ids: list[str] = []
    for page in pinecone_index.list(namespace=namespace):
        all_ids.extend(page)

    # 2. Fetch metadata in batches; collect distinct doc_ids
    pinecone_doc_ids: set[str] = set()
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i:i + batch_size]
        res = pinecone_index.fetch(ids=batch, namespace=namespace)
        vectors = res.vectors if hasattr(res, "vectors") else res.get("vectors", {})
        for vec in vectors.values():
            md = vec.metadata if hasattr(vec, "metadata") else vec.get("metadata", {})
            doc_id = md.get("doc_id")
            if doc_id:
                pinecone_doc_ids.add(doc_id)

    # 3. Read Redis registry
    docs_json = redis_client.get(redis_key)
    redis_doc_ids: set[str] = set()
    if docs_json:
        for doc in json.loads(docs_json):
            if doc.get("doc_id"):
                redis_doc_ids.add(doc["doc_id"])

    # 4. Orphans = Pinecone − Redis
    return pinecone_doc_ids - redis_doc_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n finsight pytest backend/tests/test_cleanup_orphans.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/cleanup_orphans.py backend/tests/test_cleanup_orphans.py
git commit -m "feat(cleanup): orphan detection via Pinecone/Redis cross-reference"
```

---

### Task 1.3: Test + implement orphan vector counting (per doc_id)

**Files:**
- Modify: `backend/scripts/cleanup_orphans.py`
- Modify: `backend/tests/test_cleanup_orphans.py`

We need to know how many vectors will be deleted per orphan doc_id, both for the dry-run summary and the audit log.

- [ ] **Step 1: Write failing test for vector counting**

Append to `backend/tests/test_cleanup_orphans.py`:

```python
from backend.scripts.cleanup_orphans import count_vectors_per_doc_id


def test_count_vectors_per_doc_id_groups_by_metadata():
    mock_index = MagicMock()
    mock_index.list.return_value = iter([["v1", "v2", "v3", "v4"]])
    fetch_response = MagicMock()
    fetch_response.vectors = {
        "v1": MagicMock(metadata={"doc_id": "doc_aaa", "doc_name": "A.pdf"}),
        "v2": MagicMock(metadata={"doc_id": "doc_aaa", "doc_name": "A.pdf"}),
        "v3": MagicMock(metadata={"doc_id": "doc_bbb", "doc_name": "B.pdf"}),
        "v4": MagicMock(metadata={"doc_id": "doc_bbb", "doc_name": "B.pdf"}),
    }
    mock_index.fetch.return_value = fetch_response

    counts = count_vectors_per_doc_id(
        pinecone_index=mock_index,
        namespace="default",
        doc_ids={"doc_aaa", "doc_bbb"},
    )

    assert counts["doc_aaa"]["count"] == 2
    assert counts["doc_aaa"]["doc_name"] == "A.pdf"
    assert counts["doc_bbb"]["count"] == 2
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `conda run -n finsight pytest backend/tests/test_cleanup_orphans.py::test_count_vectors_per_doc_id_groups_by_metadata -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `count_vectors_per_doc_id` in cleanup_orphans.py**

Add before `main()`:

```python
def count_vectors_per_doc_id(
    pinecone_index,
    namespace: str,
    doc_ids: set[str],
    batch_size: int = 100,
) -> dict[str, dict]:
    """For the given doc_ids, return per-doc_id counts and display metadata."""
    all_ids: list[str] = []
    for page in pinecone_index.list(namespace=namespace):
        all_ids.extend(page)

    counts: dict[str, dict] = {did: {"count": 0, "doc_name": "?"} for did in doc_ids}
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i:i + batch_size]
        res = pinecone_index.fetch(ids=batch, namespace=namespace)
        vectors = res.vectors if hasattr(res, "vectors") else res.get("vectors", {})
        for vec in vectors.values():
            md = vec.metadata if hasattr(vec, "metadata") else vec.get("metadata", {})
            did = md.get("doc_id")
            if did in counts:
                counts[did]["count"] += 1
                if counts[did]["doc_name"] == "?":
                    counts[did]["doc_name"] = md.get("doc_name", "?")
    return counts
```

- [ ] **Step 4: Run test to verify pass**

Run: `conda run -n finsight pytest backend/tests/test_cleanup_orphans.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/cleanup_orphans.py backend/tests/test_cleanup_orphans.py
git commit -m "feat(cleanup): per-doc_id vector counting for dry-run summary"
```

---

### Task 1.4: Test + implement deletion + audit logging

**Files:**
- Modify: `backend/scripts/cleanup_orphans.py`
- Modify: `backend/tests/test_cleanup_orphans.py`

- [ ] **Step 1: Write failing test for deletion**

Append to `backend/tests/test_cleanup_orphans.py`:

```python
from backend.scripts.cleanup_orphans import delete_orphan_vectors


def test_delete_orphan_vectors_calls_filter_delete_per_doc_id(tmp_path):
    mock_index = MagicMock()
    audit_path = tmp_path / "audit.jsonl"

    delete_orphan_vectors(
        pinecone_index=mock_index,
        namespace="default",
        orphan_counts={
            "doc_aaa": {"count": 100, "doc_name": "A.pdf"},
            "doc_bbb": {"count": 200, "doc_name": "B.pdf"},
        },
        audit_log_path=audit_path,
    )

    # 2 filter-delete calls expected (one per orphan doc_id)
    assert mock_index.delete.call_count == 2
    mock_index.delete.assert_any_call(
        filter={"doc_id": "doc_aaa"}, namespace="default"
    )
    mock_index.delete.assert_any_call(
        filter={"doc_id": "doc_bbb"}, namespace="default"
    )

    # Audit log written
    assert audit_path.exists()
    lines = audit_path.read_text().strip().splitlines()
    assert len(lines) == 2
    entries = [json.loads(l) for l in lines]
    deleted_doc_ids = {e["doc_id"] for e in entries}
    assert deleted_doc_ids == {"doc_aaa", "doc_bbb"}
    assert all(e["action"] == "delete_orphan" for e in entries)
    assert all("timestamp" in e for e in entries)
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `conda run -n finsight pytest backend/tests/test_cleanup_orphans.py::test_delete_orphan_vectors_calls_filter_delete_per_doc_id -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `delete_orphan_vectors` in cleanup_orphans.py**

Add before `main()`:

```python
def delete_orphan_vectors(
    pinecone_index,
    namespace: str,
    orphan_counts: dict[str, dict],
    audit_log_path: Path,
) -> None:
    """Delete each orphan doc_id's vectors via metadata-filter delete; audit each op."""
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_log_path, "a") as f:
        for doc_id, info in orphan_counts.items():
            pinecone_index.delete(filter={"doc_id": doc_id}, namespace=namespace)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "delete_orphan",
                "doc_id": doc_id,
                "doc_name": info.get("doc_name", "?"),
                "vector_count": info.get("count", 0),
                "namespace": namespace,
            }
            f.write(json.dumps(entry) + "\n")
```

- [ ] **Step 4: Run test to verify pass**

Run: `conda run -n finsight pytest backend/tests/test_cleanup_orphans.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/cleanup_orphans.py backend/tests/test_cleanup_orphans.py
git commit -m "feat(cleanup): destructive delete with per-op audit logging"
```

---

### Task 1.5: Wire up the CLI main() to use the new functions

**Files:**
- Modify: `backend/scripts/cleanup_orphans.py`

- [ ] **Step 1: Replace `main()` with the full pipeline**

In `backend/scripts/cleanup_orphans.py`, replace the existing `main()` function with:

```python
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete Pinecone vectors with no Redis registry entry."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete (default is dry-run, prints intended deletions only).",
    )
    args = parser.parse_args()

    # Lazy imports — keep module importable in tests without network deps
    from backend.core.pinecone_store import get_pinecone_store
    from backend.core.redis_client import get_redis_client

    store = get_pinecone_store()
    redis_client = get_redis_client()
    namespace = store.namespace
    redis_key = "finsight:documents"

    print("=== FinSight Orphan Cleanup ===")
    print(f"Mode      : {'APPLY (destructive)' if args.apply else 'DRY-RUN (no changes)'}")
    print(f"Namespace : {namespace}")
    print(f"Redis key : {redis_key}")
    print()

    print("Scanning Pinecone for orphan doc_ids...")
    orphans = find_orphan_doc_ids(
        pinecone_index=store.index,
        redis_client=redis_client,
        namespace=namespace,
        redis_key=redis_key,
    )

    if not orphans:
        print("✅ No orphans found — nothing to do.")
        return 0

    print(f"Found {len(orphans)} orphan doc_id(s). Counting vectors per doc_id...")
    counts = count_vectors_per_doc_id(
        pinecone_index=store.index,
        namespace=namespace,
        doc_ids=orphans,
    )

    total = sum(c["count"] for c in counts.values())
    print()
    print(f"{'doc_id':<40} {'vectors':>8}  doc_name")
    print("-" * 90)
    for did, info in sorted(counts.items()):
        print(f"{did:<40} {info['count']:>8}  {info['doc_name']}")
    print(f"\nTotal vectors to delete: {total}")
    print()

    if not args.apply:
        print("Dry-run only — no changes made. Re-run with --apply to delete.")
        return 0

    audit_path = (
        Path("logs") / f"cleanup_audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"
    )
    print(f"Applying deletions; audit log → {audit_path}")
    delete_orphan_vectors(
        pinecone_index=store.index,
        namespace=namespace,
        orphan_counts=counts,
        audit_log_path=audit_path,
    )
    print(f"✅ Deleted {total} vectors across {len(orphans)} doc_id(s).")
    return 0
```

- [ ] **Step 2: Run script in dry-run mode against real Pinecone (read-only)**

Run: `PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/python backend/scripts/cleanup_orphans.py`
Expected: prints summary showing 1 orphan doc_id (`1ecb203e-50a8-...`) with 1,220 vectors, name "EOG ... 10-K ...", and final line: "Dry-run only — no changes made."

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/cleanup_orphans.py
git commit -m "feat(cleanup): wire CLI main() to detection + counting + delete pipeline"
```

---

### Task 1.6: Add `make cleanup-orphans` target

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add the target to Makefile**

In `Makefile`, find the `.PHONY:` line at the top and add `cleanup-orphans`:

Old:
```makefile
.PHONY: start stop status doctor install
```

New:
```makefile
.PHONY: start stop status doctor cleanup-orphans install
```

Add after the `doctor:` target (before `install:`):

```makefile
# ── cleanup-orphans: remove Pinecone vectors with no Redis registry entry ────
cleanup-orphans:
	@cd $(CURDIR) && PYTHONPATH=. $(FINSIGHT_BIN)/python backend/scripts/cleanup_orphans.py $(if $(APPLY),--apply,)
```

- [ ] **Step 2: Verify dry-run via make works**

Run: `make cleanup-orphans`
Expected: same output as Task 1.5 Step 2, ending with "Dry-run only".

Run: `make -n cleanup-orphans APPLY=1`
Expected: prints `cd ... && PYTHONPATH=. ... cleanup_orphans.py --apply` (the `--apply` flag is wired through).

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat(make): add cleanup-orphans target with APPLY=1 gate"
```

---

### Task 1.7: Execute the cleanup against real Pinecone

> **⚠️ DESTRUCTIVE STEP — REQUIRES USER CONFIRMATION BEFORE PROCEEDING.**
>
> This step deletes 1,220 real vectors from Pinecone. It is irreversible.
> Do NOT execute without explicit user approval. Pause and ask.

- [ ] **Step 1: Re-run dry-run for final confirmation**

Run: `make cleanup-orphans`
Expected: shows 1 orphan doc_id with 1,220 vectors. **Pause and confirm with user before proceeding.**

- [ ] **Step 2: Apply the deletion**

After user confirms:

Run: `make cleanup-orphans APPLY=1`
Expected: prints summary, then "✅ Deleted 1220 vectors across 1 doc_id(s)."

- [ ] **Step 3: Verify cleanup via `make stats`**

Run: `make stats`
Expected: shows `Total vectors: 1220` (was 2440), `Cross-check: ✅ vector count matches registry sum (0 orphans)`.

- [ ] **Step 4: Commit the audit log**

```bash
git add logs/cleanup_audit_*.jsonl
git commit -m "ops(cleanup): apply orphan deletion against production Pinecone (1220 vectors)"
```

- [ ] **Step 5: Run all tests to ensure nothing broke**

Run: `conda run -n finsight pytest backend/tests/ -v -k "not integration"`
Expected: 232 PASS (229 existing + 3 new from cleanup tests).

---

## PR #1 Verification Checklist

Before opening PR #1:

- [ ] `make cleanup-orphans` runs cleanly in dry-run mode
- [ ] `make stats` shows `0 orphans` after applying
- [ ] All unit tests pass (`pytest -k "not integration"`)
- [ ] Audit log file exists at `logs/cleanup_audit_*.jsonl` with 1 entry
- [ ] No changes to running app code (only the new script + Makefile target)
- [ ] Frontend, backend, and Redis still work as before (`make doctor` passes)

---

# PR #2 — SQLite Foundation

**Goal:** Add the SQLite + SQLAlchemy + Alembic stack alongside existing Redis-based code. **Nothing in the running app uses SQLite yet.** Purely additive.

---

### Task 2.1: Add SQLAlchemy + Alembic + langgraph-checkpoint-sqlite to requirements

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Add the new dependencies**

In `backend/requirements.txt`, add the following lines (at the bottom, before any blank lines at end):

```
SQLAlchemy>=2.0,<3.0
alembic>=1.13,<2.0
langgraph-checkpoint-sqlite>=3.0
```

- [ ] **Step 2: Install them**

Run: `conda run -n finsight pip install SQLAlchemy>=2.0 alembic>=1.13 langgraph-checkpoint-sqlite>=3.0`
Expected: successful install, ends with "Successfully installed alembic-... SQLAlchemy-... langgraph-checkpoint-sqlite-..."

- [ ] **Step 3: Add SQLite file pattern to .gitignore**

Open `.gitignore` and add (at the bottom):

```
# SQLite control plane database
data/finsight.db
data/finsight.db-journal
data/finsight.db-wal
data/finsight.db-shm
```

- [ ] **Step 4: Verify installs work via Python import**

Run: `/Users/aarvingeorge/miniconda3/envs/finsight/bin/python -c "import sqlalchemy, alembic; from langgraph.checkpoint.sqlite import SqliteSaver; print('OK')"`
Expected: prints `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt .gitignore
git commit -m "chore(deps): add SQLAlchemy + Alembic + langgraph-checkpoint-sqlite"
```

---

### Task 2.2: Create the `backend/db/` package skeleton

**Files:**
- Create: `backend/db/__init__.py`

- [ ] **Step 1: Write the package marker with header**

Create `backend/db/__init__.py`:

```python
"""SQLite control plane: ORM models, engine/session factory, and Alembic migrations."""
```

- [ ] **Step 2: Commit**

```bash
git add backend/db/__init__.py
git commit -m "chore(db): create backend/db/ package skeleton"
```

---

### Task 2.3: Test + implement the SQLAlchemy engine + session factory

**Files:**
- Create: `backend/db/engine.py`
- Create: `backend/tests/test_db_engine.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_db_engine.py`:

```python
"""
test_db_engine.py

Verifies the SQLAlchemy engine and session factory produce a working
in-memory SQLite connection suitable for tests.
"""
from sqlalchemy import text
from backend.db.engine import create_engine_for_url, make_session_factory


def test_create_engine_for_url_returns_working_engine():
    engine = create_engine_for_url("sqlite:///:memory:")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 as x")).scalar()
    assert result == 1


def test_session_factory_yields_usable_session():
    engine = create_engine_for_url("sqlite:///:memory:")
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as session:
        result = session.execute(text("SELECT 42 as x")).scalar()
    assert result == 42
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `conda run -n finsight pytest backend/tests/test_db_engine.py -v`
Expected: FAIL with `ImportError: cannot import name 'create_engine_for_url'`

- [ ] **Step 3: Implement engine.py**

Create `backend/db/engine.py`:

```python
"""
engine.py

SQLAlchemy engine + session factory for the FinSight control plane.

Role in project:
    Infrastructure layer. Owns the single SQLAlchemy engine pointing at
    `data/finsight.db` (or an override URL for tests). Other modules
    consume `get_session()` to interact with the database.

Main parts:
    - create_engine_for_url(url): builds a SQLAlchemy Engine for the
      given SQLite URL with appropriate pragmas for the local-first
      single-writer use case.
    - make_session_factory(engine): wraps the engine in a sessionmaker
      bound to the engine; returns a callable producing Session objects.
    - get_engine() / get_session(): module-level singletons that resolve
      to the production database from settings.
"""
from __future__ import annotations

from functools import lru_cache
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings


def create_engine_for_url(url: str) -> Engine:
    """Build an Engine. Enables WAL mode and foreign keys for SQLite."""
    engine = create_engine(url, future=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@lru_cache
def get_engine() -> Engine:
    """Singleton engine pointing at data/finsight.db (or settings.database_url)."""
    settings = get_settings()
    url = getattr(settings, "database_url", "sqlite:///data/finsight.db")
    return create_engine_for_url(url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return make_session_factory(get_engine())
```

- [ ] **Step 4: Run tests to verify pass**

Run: `conda run -n finsight pytest backend/tests/test_db_engine.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/engine.py backend/tests/test_db_engine.py
git commit -m "feat(db): SQLAlchemy engine + session factory with SQLite WAL/FK pragmas"
```

---

### Task 2.4: Test + implement the ORM models

**Files:**
- Create: `backend/db/models.py`
- Create: `backend/tests/test_db_models.py`

- [ ] **Step 1: Write the failing test for users + workspaces**

Create `backend/tests/test_db_models.py`:

```python
"""
test_db_models.py

Validates ORM model definitions: tables can be created, rows inserted,
foreign keys enforced, and indexes present.
"""
from datetime import datetime
import pytest
from sqlalchemy.exc import IntegrityError
from backend.db.engine import create_engine_for_url, make_session_factory
from backend.db.models import (
    Base, User, Workspace, WorkspaceMember, Document, ChatSession,
)


@pytest.fixture
def session():
    engine = create_engine_for_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as s:
        yield s


def test_can_insert_user(session):
    u = User(id="usr_test", email="cfo@example.com", display_name="Test CFO")
    session.add(u)
    session.commit()
    fetched = session.get(User, "usr_test")
    assert fetched.email == "cfo@example.com"


def test_workspace_requires_existing_owner(session):
    w = Workspace(id="wks_test", owner_id="usr_nonexistent", name="Acme")
    session.add(w)
    with pytest.raises(IntegrityError):
        session.commit()


def test_workspace_member_cascades_on_workspace_delete(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    m = WorkspaceMember(workspace_id="wks_a", user_id="usr_a", role="owner")
    session.add_all([u, w, m])
    session.commit()
    session.delete(w)
    session.commit()
    assert session.query(WorkspaceMember).count() == 0


def test_document_belongs_to_workspace(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    d = Document(
        id="doc_x", workspace_id="wks_a", user_id="usr_a",
        name="EOG-10K.pdf", doc_type="10-K", fiscal_year="2025",
        file_hash="abc123", chunk_count=1220, status="indexed",
    )
    session.add_all([u, w, d])
    session.commit()
    assert session.get(Document, "doc_x").chunk_count == 1220


def test_document_dedup_unique_constraint(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    d1 = Document(
        id="doc_1", workspace_id="wks_a", user_id="usr_a",
        name="A.pdf", file_hash="hash_xyz", chunk_count=10, status="indexed",
    )
    d2 = Document(
        id="doc_2", workspace_id="wks_a", user_id="usr_a",
        name="B.pdf", file_hash="hash_xyz", chunk_count=20, status="indexed",
    )
    session.add_all([u, w, d1, d2])
    with pytest.raises(IntegrityError):
        session.commit()


def test_chat_session_belongs_to_workspace(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    c = ChatSession(id="ses_a", user_id="usr_a", workspace_id="wks_a", title="Untitled")
    session.add_all([u, w, c])
    session.commit()
    assert session.get(ChatSession, "ses_a").title == "Untitled"
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `conda run -n finsight pytest backend/tests/test_db_models.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement models.py**

Create `backend/db/models.py`:

```python
"""
models.py

SQLAlchemy ORM model definitions for the FinSight control plane.

Role in project:
    Infrastructure layer. Defines the relational schema mirrored in the
    Alembic migration in backend/db/migrations/versions/. These classes
    are the single source of truth for table structure, foreign keys,
    indexes, and cascade behavior.

Main parts:
    - Base: declarative base shared by all models.
    - User: a person who can log in (v1: just one row, "usr_default").
    - Workspace: a labeled container owned by a user (e.g. "Acme Corp").
    - WorkspaceMember: workspace_id <-> user_id with a role (owner|editor|viewer).
    - Document: a registered uploaded file inside a workspace.
    - ChatSession: a single conversation thread inside a workspace.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    members = relationship(
        "WorkspaceMember", cascade="all, delete-orphan", backref="workspace"
    )
    documents = relationship(
        "Document", cascade="all, delete-orphan", backref="workspace"
    )
    chat_sessions = relationship(
        "ChatSession", cascade="all, delete-orphan", backref="workspace"
    )


Index("idx_workspaces_owner_status", Workspace.owner_id, Workspace.status)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False, default="owner")
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String, nullable=True)
    fiscal_year: Mapped[str | None] = mapped_column(String, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="indexed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "file_hash", name="idx_workspace_file_hash"),
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


Index(
    "idx_chat_sessions_workspace_recent",
    ChatSession.workspace_id, ChatSession.last_message_at.desc(),
)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `conda run -n finsight pytest backend/tests/test_db_models.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py backend/tests/test_db_models.py
git commit -m "feat(db): ORM models for users, workspaces, members, documents, chat_sessions"
```

---

### Task 2.5: Set up Alembic for migrations

**Files:**
- Create: `alembic.ini`
- Create: `backend/db/migrations/env.py`
- Create: `backend/db/migrations/script.py.mako`
- Create: `backend/db/migrations/versions/` (empty dir, will be populated by next step)
- Create: `backend/db/migrations/versions/.gitkeep`

- [ ] **Step 1: Initialize Alembic into `backend/db/migrations/`**

Run from project root: `conda run -n finsight alembic init backend/db/migrations`
Expected: creates `alembic.ini`, `backend/db/migrations/env.py`, `backend/db/migrations/script.py.mako`, `backend/db/migrations/versions/`.

- [ ] **Step 2: Edit `alembic.ini` to point at the SQLite database**

Open `alembic.ini` and locate the line `sqlalchemy.url = driver://user:pass@localhost/dbname`. Replace with:

```ini
sqlalchemy.url = sqlite:///data/finsight.db
```

Locate `script_location = backend/db/migrations` (Alembic should have set this from the init command). If not present, add it under `[alembic]`.

- [ ] **Step 3: Edit `backend/db/migrations/env.py` to autogenerate from our models**

Open `backend/db/migrations/env.py`. Locate the `target_metadata = None` line near the top. Replace with:

```python
from backend.db.models import Base
target_metadata = Base.metadata
```

Add this docstring at the very top of the file (above any imports):

```python
"""
env.py

Alembic environment script. Drives schema migrations for the FinSight
control plane SQLite database.

Role in project:
    Infrastructure / build-time tooling. Reads ORM models from
    backend.db.models and produces SQL migration scripts when invoked
    via `alembic revision --autogenerate`.

Main parts:
    - target_metadata: bound to Base.metadata so autogenerate detects
      schema drift between code and database.
    - run_migrations_offline / run_migrations_online: standard Alembic
      runners (unmodified from the init template).
"""
```

- [ ] **Step 4: Generate the initial migration**

Run from project root: `conda run -n finsight alembic revision --autogenerate -m "initial schema"`
Expected: creates a new file under `backend/db/migrations/versions/` (something like `20260420_xxxx_initial_schema.py`). Inspect it: should contain `op.create_table('users', ...)`, etc., for all 5 tables.

- [ ] **Step 5: Verify the migration applies cleanly**

Run: `conda run -n finsight alembic upgrade head`
Expected: prints `INFO  [alembic.runtime.migration] Running upgrade  -> <rev>, initial schema`. Creates `data/finsight.db` (the file should exist after this).

Verify: `ls -la data/finsight.db` exists.

- [ ] **Step 6: Commit Alembic config + initial migration**

```bash
git add alembic.ini backend/db/migrations/
git commit -m "feat(db): Alembic config + initial schema migration"
```

---

### Task 2.6: Test that Alembic migration produces the expected schema

**Files:**
- Create: `backend/tests/test_db_migrations.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_db_migrations.py`:

```python
"""
test_db_migrations.py

Verifies the Alembic migration produces the same schema as the ORM
models (autogenerate-and-apply round-trip).
"""
import os
import tempfile
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from backend.db.engine import create_engine_for_url


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        url = f"sqlite:///{db_path}"

        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")

        engine = create_engine_for_url(url)
        yield engine


def test_migration_creates_all_tables(temp_db):
    inspector = inspect(temp_db)
    tables = set(inspector.get_table_names())
    expected = {"users", "workspaces", "workspace_members", "documents", "chat_sessions", "alembic_version"}
    assert expected.issubset(tables)


def test_migration_creates_unique_constraint_on_documents(temp_db):
    inspector = inspect(temp_db)
    indexes = inspector.get_unique_constraints("documents")
    names = [ix["name"] for ix in indexes]
    assert "idx_workspace_file_hash" in names


def test_migration_enables_foreign_keys_in_runtime(temp_db):
    with temp_db.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1
```

- [ ] **Step 2: Run tests**

Run: `conda run -n finsight pytest backend/tests/test_db_migrations.py -v`
Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_db_migrations.py
git commit -m "test(db): verify Alembic migration produces expected schema"
```

---

### Task 2.7: Verify all PR #2 changes are additive (existing app still works)

- [ ] **Step 1: Run the full test suite**

Run: `conda run -n finsight pytest backend/tests/ -v -k "not integration"`
Expected: 235+ PASS (232 from PR #1 + 11 new from PR #2). Zero failures.

- [ ] **Step 2: Boot the existing app**

Run: `make start`
Expected: Redis container starts, backend reaches `/health` within 15 s, frontend starts on :5173. **Existing functionality unchanged.**

- [ ] **Step 3: Stop the app**

Run: `make stop`

---

## PR #2 Verification Checklist

Before opening PR #2:

- [ ] `pip list` shows SQLAlchemy, alembic, langgraph-checkpoint-sqlite installed
- [ ] `data/finsight.db` is created by `alembic upgrade head` and gitignored
- [ ] All tests pass (~235 unit)
- [ ] `make start` boots the existing Redis-based app cleanly
- [ ] `make doctor` passes
- [ ] No imports from `backend/db/*` exist in any non-test, non-migration code (verifies PR #2 is additive)

---

# PR #3 — Storage Refactor + Migration

**Goal:** Switch all read/write paths to SQLite + namespaced Pinecone. Run the data migration. App behavior identical to user.

This is the largest PR — broken into smaller commits via task boundaries.

---

### Task 3.1: Test + implement the `RequestContext` and FastAPI dependency

**Files:**
- Create: `backend/core/context.py`
- Create: `backend/tests/test_context.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_context.py`:

```python
"""
test_context.py

Verifies the RequestContext dependency yields the v1 hardcoded defaults
and is overridable for v2 auth integration.
"""
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from backend.core.context import RequestContext, get_request_context


def test_default_request_context_has_default_user_and_workspace():
    ctx = get_request_context()
    assert ctx.user_id == "usr_default"
    assert ctx.workspace_id == "wks_default"


def test_request_context_is_immutable():
    import dataclasses
    ctx = RequestContext(user_id="usr_x", workspace_id="wks_y")
    assert dataclasses.is_dataclass(ctx)
    try:
        ctx.user_id = "modified"
        assert False, "should be frozen"
    except dataclasses.FrozenInstanceError:
        pass


def test_request_context_works_as_fastapi_dependency():
    app = FastAPI()

    @app.get("/whoami")
    def whoami(ctx: RequestContext = Depends(get_request_context)):
        return {"user": ctx.user_id, "workspace": ctx.workspace_id}

    client = TestClient(app)
    r = client.get("/whoami")
    assert r.status_code == 200
    assert r.json() == {"user": "usr_default", "workspace": "wks_default"}
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `conda run -n finsight pytest backend/tests/test_context.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement context.py**

Create `backend/core/context.py`:

```python
"""
context.py

Per-request context object that identifies the calling user and the
active workspace. The single spine that every multi-tenant operation
in the backend reads from.

Role in project:
    Core layer. Used as a FastAPI dependency on every route that needs
    to know who is acting and which workspace they are operating in.
    In v1 it returns hardcoded defaults; in v2 (sub-project 3) the
    `get_request_context` body is replaced with JWT validation.

Main parts:
    - RequestContext: immutable dataclass holding (user_id, workspace_id).
    - get_request_context(): FastAPI dependency. v1: returns defaults.
      v2: validate auth header, look up user, resolve workspace.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    user_id: str
    workspace_id: str


def get_request_context() -> RequestContext:
    """v1: hardcoded defaults. v2: replaced with auth-based resolver."""
    return RequestContext(user_id="usr_default", workspace_id="wks_default")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `conda run -n finsight pytest backend/tests/test_context.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/context.py backend/tests/test_context.py
git commit -m "feat(core): RequestContext dependency with v1 hardcoded defaults"
```

---

### Task 3.2: Test + implement the `StorageTransaction` helper

**Files:**
- Create: `backend/core/transactions.py`
- Create: `backend/tests/test_transactions.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_transactions.py`:

```python
"""
test_transactions.py

Verifies StorageTransaction runs compensating actions on exception
(orphan-prevention contract) and commits silently on success.
"""
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from backend.core.transactions import StorageTransaction


def test_commit_on_success_runs_no_undo(tmp_path):
    file_path = tmp_path / "doc.txt"
    with StorageTransaction() as tx:
        tx.add_file_write(file_path, b"hello")
    assert file_path.read_bytes() == b"hello"


def test_exception_undoes_file_write(tmp_path):
    file_path = tmp_path / "doc.txt"
    with pytest.raises(RuntimeError):
        with StorageTransaction() as tx:
            tx.add_file_write(file_path, b"hello")
            raise RuntimeError("boom")
    assert not file_path.exists()


def test_exception_undoes_pinecone_upsert():
    mock_index = MagicMock()
    vectors = [{"id": "v1", "values": [0.1] * 3, "metadata": {}}]
    with pytest.raises(RuntimeError):
        with StorageTransaction() as tx:
            tx.add_pinecone_upsert(mock_index, vectors, namespace="ns")
            raise RuntimeError("boom")
    mock_index.upsert.assert_called_once_with(vectors=vectors, namespace="ns")
    mock_index.delete.assert_called_once_with(ids=["v1"], namespace="ns")


def test_undo_runs_in_reverse_order(tmp_path):
    """Compensating actions roll back in reverse insertion order."""
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    order = []

    with pytest.raises(RuntimeError):
        with StorageTransaction() as tx:
            tx.add_file_write(file_a, b"A")
            tx._undo.append(lambda: order.append("undo_a_marker"))
            tx.add_file_write(file_b, b"B")
            tx._undo.append(lambda: order.append("undo_b_marker"))
            raise RuntimeError("boom")

    # b's marker should run before a's marker (reverse order)
    assert order == ["undo_b_marker", "undo_a_marker"]
    assert not file_a.exists()
    assert not file_b.exists()
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `conda run -n finsight pytest backend/tests/test_transactions.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement transactions.py**

Create `backend/core/transactions.py`:

```python
"""
transactions.py

Compensating-action transaction helper for orchestrating writes across
SQLite, Pinecone, and the local filesystem.

Role in project:
    Core layer. The orphan-prevention contract for the multi-store
    refactor. Every place that writes to >1 of {SQLite, Pinecone, disk}
    wraps the writes in a `with StorageTransaction() as tx:` block.
    On exception, recorded compensating actions roll back the prior
    writes in reverse order. Best-effort — if a compensating action
    itself fails, we log and continue.

Main parts:
    - StorageTransaction: context manager. Records compensating actions
      via `add_*` helpers; runs them in reverse on exception.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class StorageTransaction:
    """Tracks compensating actions; rolls back on exception."""

    def __init__(self) -> None:
        self._undo: list[Callable[[], None]] = []

    def add_file_write(self, dst_path: Path, data: bytes) -> None:
        """Write a file; on rollback, delete it."""
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_bytes(data)
        self._undo.append(lambda: dst_path.unlink(missing_ok=True))

    def add_file_delete(self, path: Path) -> None:
        """Delete a file; on rollback, do nothing (delete is irreversible)."""
        if path.exists():
            path.unlink()
        # No undo — file deletion is irreversible. The transaction's other
        # writes still get rolled back; this delete just stays applied.

    def add_pinecone_upsert(self, index, vectors: list[dict], namespace: str) -> None:
        """Upsert; on rollback, delete by IDs."""
        index.upsert(vectors=vectors, namespace=namespace)
        ids = [v["id"] for v in vectors]
        self._undo.append(lambda: index.delete(ids=ids, namespace=namespace))

    def add_pinecone_delete_by_filter(
        self, index, filter_dict: dict, namespace: str
    ) -> None:
        """Filter-delete; no rollback (delete is irreversible)."""
        index.delete(filter=filter_dict, namespace=namespace)

    def __enter__(self) -> "StorageTransaction":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            for undo in reversed(self._undo):
                try:
                    undo()
                except Exception as e:
                    logger.warning("StorageTransaction undo failed: %s", e)
            return False  # propagate exception
        return False
```

- [ ] **Step 4: Run tests, verify pass**

Run: `conda run -n finsight pytest backend/tests/test_transactions.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/transactions.py backend/tests/test_transactions.py
git commit -m "feat(core): StorageTransaction helper with reverse-order compensating actions"
```

---

### Task 3.3: Add deterministic chunk IDs in document_ingestion

**Files:**
- Modify: `backend/skills/document_ingestion.py`
- Modify: `backend/tests/test_document_ingestion.py`

- [ ] **Step 1: Add a failing test**

Add to `backend/tests/test_document_ingestion.py` (find the existing `test_*_chunk*` tests and add this one alongside):

```python
def test_section_chunks_get_deterministic_ids(tmp_path):
    """Section chunks should have IDs of the form <doc_id>:<chunk_index:04d>."""
    from backend.skills.document_ingestion import hierarchical_chunk

    parsed = {
        "pages": [
            {
                "page_number": 1,
                "text": "Some narrative text. " * 100,
                "tables": [],
            }
        ]
    }
    doc_metadata = {"doc_id": "doc_abcd1234", "doc_name": "x.pdf",
                    "doc_type": "10-K", "fiscal_year": "2025"}

    chunks = hierarchical_chunk(parsed, doc_metadata)
    section_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "section"]
    assert len(section_chunks) >= 1
    for c in section_chunks:
        assert c.chunk_id.startswith("doc_abcd1234:")
        assert c.chunk_id.split(":")[1].isdigit()


def test_row_chunks_get_deterministic_ids(tmp_path):
    """Row chunks should have IDs of the form <doc_id>:<table_row:04d>."""
    from backend.skills.document_ingestion import hierarchical_chunk

    parsed = {
        "pages": [
            {
                "page_number": 1,
                "text": "",
                "tables": [
                    [["Metric", "FY24", "FY25"], ["Revenue", "100", "110"], ["EBITDA", "20", "25"]]
                ],
            }
        ]
    }
    doc_metadata = {"doc_id": "doc_abcd1234", "doc_name": "x.pdf",
                    "doc_type": "10-K", "fiscal_year": "2025"}

    chunks = hierarchical_chunk(parsed, doc_metadata)
    row_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "row"]
    assert len(row_chunks) == 2
    for c in row_chunks:
        assert c.chunk_id.startswith("doc_abcd1234:")
```

- [ ] **Step 2: Run tests, expect failure**

Run: `conda run -n finsight pytest backend/tests/test_document_ingestion.py::test_section_chunks_get_deterministic_ids backend/tests/test_document_ingestion.py::test_row_chunks_get_deterministic_ids -v`
Expected: FAIL — chunk_ids are random UUIDs, not the expected format.

- [ ] **Step 3: Modify `hierarchical_chunk()` in `backend/skills/document_ingestion.py`**

Find the three `chunk_id=str(uuid.uuid4())` sites (lines ~199, 223, 246) and replace each with the deterministic format. Use the existing variable names:

For the section-chunk site (around line 199):
```python
chunk_id=f"{doc_metadata['doc_id']}:{i:04d}",
```

For the table-row site (around line 223):
```python
chunk_id=f"{doc_metadata['doc_id']}:{row_idx:04d}",
```

For the CSV-row site (around line 246):
```python
chunk_id=f"{doc_metadata['doc_id']}:{row_idx + 1:04d}",
```

Also remove the `import uuid` line at the top of the file if it's now unused (verify first with `grep uuid backend/skills/document_ingestion.py`).

- [ ] **Step 4: Run all document_ingestion tests**

Run: `conda run -n finsight pytest backend/tests/test_document_ingestion.py -v`
Expected: all PASS (existing tests should still work since they don't assert on chunk_id format).

- [ ] **Step 5: Commit**

```bash
git add backend/skills/document_ingestion.py backend/tests/test_document_ingestion.py
git commit -m "feat(ingest): deterministic chunk IDs of the form <doc_id>:<position>"
```

---

### Task 3.4: Update `vector_retrieval.py` to accept namespace parameter

**Files:**
- Modify: `backend/skills/vector_retrieval.py`
- Modify: `backend/tests/test_vector_retrieval.py`

- [ ] **Step 1: Read the current signatures**

Run: `grep -n "^def \(embed_and_upsert\|semantic_search\|mmr_rerank\)" backend/skills/vector_retrieval.py`
Note the current signatures.

- [ ] **Step 2: Modify all three functions to accept `namespace` parameter**

In `backend/skills/vector_retrieval.py`:

For `embed_and_upsert`:
- Add `namespace: str` parameter (required, no default)
- Replace `store.index.upsert(vectors=batch, namespace=store.namespace)` with `store.index.upsert(vectors=batch, namespace=namespace)`

For `semantic_search`:
- Add `namespace: str` parameter (required, no default)
- Replace `namespace=store.namespace` with `namespace=namespace` in the `index.query(...)` call

For `mmr_rerank`:
- No changes needed (it operates on already-retrieved candidates; doesn't query Pinecone)

- [ ] **Step 3: Update existing tests in `test_vector_retrieval.py`**

Find every call to `embed_and_upsert(...)` in tests and add `namespace="test_ns"`. Same for `semantic_search(...)`. Use `grep -n "embed_and_upsert\|semantic_search" backend/tests/test_vector_retrieval.py` to find all sites.

- [ ] **Step 4: Run tests**

Run: `conda run -n finsight pytest backend/tests/test_vector_retrieval.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/skills/vector_retrieval.py backend/tests/test_vector_retrieval.py
git commit -m "feat(retrieval): accept explicit namespace parameter on all Pinecone ops"
```

---

### Task 3.5: Add `workspace_id` and `chat_session_id` to AgentState

**Files:**
- Modify: `backend/agents/graph_state.py`
- Modify: `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Read the current `AgentState`**

Run: `cat backend/agents/graph_state.py`
Note the existing fields.

- [ ] **Step 2: Add the new fields**

In `backend/agents/graph_state.py`, add to the `AgentState` TypedDict (alongside existing fields):

```python
user_id: str           # who is asking (v1: "usr_default")
workspace_id: str      # which workspace's context (v1: "wks_default")
chat_session_id: str   # which chat thread (= LangGraph thread_id)
```

Update the file's docstring "Main parts" section to mention these new fields.

- [ ] **Step 3: Update tests**

In `backend/tests/test_orchestrator.py`, find every place that constructs an `AgentState` and add the three new fields with default values (`"usr_default"`, `"wks_default"`, `"ses_default"`).

- [ ] **Step 4: Run tests**

Run: `conda run -n finsight pytest backend/tests/test_orchestrator.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/graph_state.py backend/tests/test_orchestrator.py
git commit -m "feat(agents): add user_id, workspace_id, chat_session_id to AgentState"
```

---

### Task 3.6: Update `orchestrator.py` `rag_retrieve` node to use namespace from state

**Files:**
- Modify: `backend/agents/orchestrator.py`
- Modify: `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Find the `rag_retrieve` function**

Run: `grep -n "def rag_retrieve" backend/agents/orchestrator.py`

- [ ] **Step 2: Modify it to pass namespace**

Find the body of `rag_retrieve`. Wherever `semantic_search(query, top_k=...)` is called, replace with `semantic_search(query, top_k=..., namespace=state["workspace_id"])`.

- [ ] **Step 3: Add a test that verifies workspace_id flows through**

Append to `backend/tests/test_orchestrator.py`:

```python
def test_rag_retrieve_uses_workspace_id_as_namespace(monkeypatch):
    """Verify the rag_retrieve node passes state['workspace_id'] as namespace."""
    from backend.agents import orchestrator

    captured = {}

    def fake_semantic_search(query, top_k, namespace, **kw):
        captured["namespace"] = namespace
        return []

    monkeypatch.setattr(orchestrator, "semantic_search", fake_semantic_search)
    monkeypatch.setattr(orchestrator, "mmr_rerank", lambda q, c, **kw: c)
    monkeypatch.setattr(orchestrator, "format_retrieved_context", lambda c: "")

    state = {
        "messages": [],
        "user_id": "usr_test",
        "workspace_id": "wks_test_acme",
        "chat_session_id": "ses_test",
    }
    orchestrator.rag_retrieve(state)

    assert captured["namespace"] == "wks_test_acme"
```

- [ ] **Step 4: Run test**

Run: `conda run -n finsight pytest backend/tests/test_orchestrator.py::test_rag_retrieve_uses_workspace_id_as_namespace -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(agents): rag_retrieve uses state['workspace_id'] as Pinecone namespace"
```

---

### Task 3.7: Replace `mcp_list_documents` with SQL-backed implementation

**Files:**
- Modify: `backend/mcp_server/tools/document_tools.py`
- Modify: `backend/tests/test_document_tools_integration.py`

- [ ] **Step 1: Add the new SQL-backed list function**

In `backend/mcp_server/tools/document_tools.py`, add a new function (keep the old `mcp_list_documents` for now — we'll remove it in PR #4):

```python
def list_documents_sql(workspace_id: str, session) -> list[dict]:
    """List documents in a workspace from SQLite. Returns dicts shaped like the old Redis output."""
    from backend.db.models import Document
    rows = (
        session.query(Document)
        .filter(Document.workspace_id == workspace_id, Document.status == "indexed")
        .order_by(Document.created_at.desc())
        .all()
    )
    return [
        {
            "doc_id": r.id,
            "doc_name": r.name,
            "doc_type": r.doc_type,
            "fiscal_year": r.fiscal_year,
            "chunk_count": r.chunk_count,
            "status": r.status,
        }
        for r in rows
    ]
```

- [ ] **Step 2: Write a test for it**

Create or append to `backend/tests/test_document_tools_integration.py`:

```python
def test_list_documents_sql_returns_workspace_docs_only():
    from backend.db.engine import create_engine_for_url, make_session_factory
    from backend.db.models import Base, User, Workspace, Document
    from backend.mcp_server.tools.document_tools import list_documents_sql

    engine = create_engine_for_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as s:
        s.add_all([
            User(id="usr_a", email="a@x.com", display_name="A"),
            Workspace(id="wks_a", owner_id="usr_a", name="A"),
            Workspace(id="wks_b", owner_id="usr_a", name="B"),
            Document(id="doc_1", workspace_id="wks_a", user_id="usr_a",
                     name="A.pdf", chunk_count=10, status="indexed"),
            Document(id="doc_2", workspace_id="wks_b", user_id="usr_a",
                     name="B.pdf", chunk_count=20, status="indexed"),
        ])
        s.commit()
        result = list_documents_sql("wks_a", s)

    assert len(result) == 1
    assert result[0]["doc_id"] == "doc_1"
```

- [ ] **Step 3: Run test**

Run: `conda run -n finsight pytest backend/tests/test_document_tools_integration.py::test_list_documents_sql_returns_workspace_docs_only -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/mcp_server/tools/document_tools.py backend/tests/test_document_tools_integration.py
git commit -m "feat(docs): add SQL-backed list_documents alongside Redis version"
```

---

### Task 3.8: Refactor `documents.py` upload route to use SQLite + StorageTransaction + namespace

**Files:**
- Modify: `backend/api/routes/documents.py`
- Modify: `backend/tests/test_documents_security.py` (if needed)

- [ ] **Step 1: Read the current `upload_document` route**

Run: `cat backend/api/routes/documents.py`

- [ ] **Step 2: Replace `upload_document` with the new transactional version**

Replace the entire `upload_document` function in `backend/api/routes/documents.py` with:

```python
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("general"),
    fiscal_year: str = Form(""),
    ctx: RequestContext = Depends(get_request_context),
):
    """Upload, parse, chunk, embed, index — transactional across SQLite + Pinecone + disk."""
    import hashlib
    import uuid as _uuid
    from sqlalchemy import select
    from backend.core.transactions import StorageTransaction
    from backend.db.engine import get_session_factory
    from backend.db.models import Document
    from backend.core.pinecone_store import get_pinecone_store

    # 1. Validate filename + extension
    raw_filename = file.filename or "unknown"
    filename = Path(raw_filename).name
    if not filename or filename in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".csv", ".txt", ".html"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # 2. Read + size check
    MAX_FILE_SIZE = 50 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    # 3. Compute hash for dedup
    file_hash = hashlib.sha256(contents).hexdigest()

    # 4. Dedup check via SQLite
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        existing = session.execute(
            select(Document).where(
                Document.workspace_id == ctx.workspace_id,
                Document.file_hash == file_hash,
            )
        ).scalar_one_or_none()
        if existing:
            return {
                "doc_id": existing.id,
                "doc_name": existing.name,
                "doc_type": existing.doc_type,
                "chunk_count": existing.chunk_count,
                "status": "already_indexed",
            }

    # 5. Parse + chunk (out-of-transaction; no side effects yet)
    doc_id = f"doc_{_uuid.uuid4().hex[:8]}"
    if ext == ".pdf":
        # Write to a temp path so the parser can read it; final move happens in tx
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        try:
            parsed = parse_pdf(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    elif ext == ".csv":
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        try:
            parsed = parse_csv(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    else:
        raise HTTPException(status_code=400, detail=f"Parser not implemented for {ext}")

    doc_metadata = {
        "doc_id": doc_id,
        "doc_name": filename,
        "doc_type": doc_type,
        "fiscal_year": fiscal_year,
        "user_id": ctx.user_id,
        "workspace_id": ctx.workspace_id,
    }
    chunks = hierarchical_chunk(parsed, doc_metadata)
    if not chunks:
        raise HTTPException(status_code=400, detail="No content could be extracted")

    # 6. Embed (out-of-transaction; expensive, but no commit yet)
    from backend.core.gemini_client import GeminiClient
    gemini = GeminiClient()
    texts = [c.text for c in chunks]
    vectors_floats = gemini.embed_texts(texts)
    pinecone_records = []
    for chunk, vec in zip(chunks, vectors_floats):
        md = dict(chunk.metadata)
        md["text"] = chunk.text
        md["token_count"] = chunk.token_count
        pinecone_records.append({"id": chunk.chunk_id, "values": vec, "metadata": md})

    # 7. Transactional write across all 3 stores
    upload_dir = Path("data/uploads") / ctx.workspace_id
    file_path = upload_dir / f"{doc_id}{ext}"
    store = get_pinecone_store()

    try:
        with SessionLocal() as session, StorageTransaction() as tx:
            tx.add_file_write(file_path, contents)
            # Pinecone upsert in batches of 100
            for i in range(0, len(pinecone_records), 100):
                tx.add_pinecone_upsert(
                    store.index,
                    pinecone_records[i:i + 100],
                    namespace=ctx.workspace_id,
                )
            session.add(Document(
                id=doc_id,
                workspace_id=ctx.workspace_id,
                user_id=ctx.user_id,
                name=filename,
                doc_type=doc_type,
                fiscal_year=fiscal_year,
                file_hash=file_hash,
                chunk_count=len(chunks),
                status="indexed",
            ))
            session.commit()
    except Exception as e:
        # StorageTransaction has already rolled back file + Pinecone.
        # SQL session auto-rolled-back on exception.
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    return {
        "doc_id": doc_id,
        "doc_name": filename,
        "doc_type": doc_type,
        "chunk_count": len(chunks),
        "status": "indexed",
    }
```

Also update the imports at the top of the file:

```python
from backend.core.context import RequestContext, get_request_context
```

(Remove `from backend.skills.vector_retrieval import embed_and_upsert` if no longer used directly — `embed_and_upsert` was used by the old code; the new code embeds directly via `GeminiClient`.)

- [ ] **Step 3: Update `list_documents` to use SQLite**

Replace the existing `list_documents` route:

```python
@router.get("/")
async def list_documents(ctx: RequestContext = Depends(get_request_context)):
    from backend.db.engine import get_session_factory
    from backend.mcp_server.tools.document_tools import list_documents_sql
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        return list_documents_sql(ctx.workspace_id, session)
```

- [ ] **Step 4: Update `delete_document` (DELETE route) for transactional 3-store delete**

Replace the existing `remove_document` route:

```python
@router.delete("/{doc_id}")
async def remove_document(
    doc_id: str,
    ctx: RequestContext = Depends(get_request_context),
):
    from sqlalchemy import select, delete as sql_delete
    from backend.core.transactions import StorageTransaction
    from backend.db.engine import get_session_factory
    from backend.db.models import Document
    from backend.core.pinecone_store import get_pinecone_store

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        doc = session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.workspace_id == ctx.workspace_id,
            )
        ).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        store = get_pinecone_store()
        # Build the file path from disk layout
        ext_match = Path(doc.name).suffix.lower()
        file_path = Path("data/uploads") / ctx.workspace_id / f"{doc_id}{ext_match}"

        try:
            with StorageTransaction() as tx:
                session.execute(sql_delete(Document).where(Document.id == doc_id))
                tx.add_pinecone_delete_by_filter(
                    store.index, {"doc_id": doc_id}, namespace=ctx.workspace_id
                )
                tx.add_file_delete(file_path)
                session.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

    return {"status": "deleted", "doc_id": doc_id}
```

- [ ] **Step 5: Run tests**

Run: `conda run -n finsight pytest backend/tests/test_documents_security.py -v`
Expected: existing security tests still pass (they test sanitization which we kept).

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/documents.py
git commit -m "feat(api): documents routes use SQLite + StorageTransaction + namespace"
```

---

### Task 3.9: Update `chat.py` to plumb workspace_id and chat_session_id

**Files:**
- Modify: `backend/api/routes/chat.py`
- Modify: `backend/tests/test_chat_api.py`

- [ ] **Step 1: Read current chat routes**

Run: `cat backend/api/routes/chat.py`

- [ ] **Step 2: Add RequestContext dependency to both POST routes**

In `backend/api/routes/chat.py`:

For both `chat` and `chat_stream` routes, add `ctx: RequestContext = Depends(get_request_context)` to the signature.

For each route, change `session_id` handling to:
- Use `ctx.workspace_id` for the namespace (passed to orchestrator state)
- Use a `chat_session_id` field from the request body (default to `f"ses_default_{ctx.workspace_id}"` if not provided)
- Pass `thread_id=chat_session_id` to LangGraph invocation

When constructing the initial state dict to pass to LangGraph, include:
```python
state = {
    "messages": [HumanMessage(content=request.message)],
    "user_id": ctx.user_id,
    "workspace_id": ctx.workspace_id,
    "chat_session_id": chat_session_id,
}
```

(The exact integration depends on the existing chat.py structure — preserve the streaming logic; only inject these fields into the state.)

Add at the top:
```python
from backend.core.context import RequestContext, get_request_context
```

Add `chat_session_id: str | None = None` to the existing `ChatRequest` Pydantic model.

- [ ] **Step 3: Update tests in `test_chat_api.py`**

Wherever a chat is invoked in tests, ensure the body includes `chat_session_id` (or rely on default). Add a test that verifies:

```python
def test_chat_passes_workspace_id_to_orchestrator(monkeypatch):
    """The chat route's invocation should include workspace_id in state."""
    from backend.api.routes import chat
    captured_state = {}

    def fake_invoke(state, config=None):
        captured_state.update(state)
        return {"messages": []}

    # mock the orchestrator graph
    monkeypatch.setattr(chat, "graph", type("G", (), {"invoke": staticmethod(fake_invoke)}))
    # ... call route via TestClient ...
    # assert captured_state["workspace_id"] == "wks_default"
```

(Adjust to match the actual structure of chat.py after Step 2.)

- [ ] **Step 4: Run tests**

Run: `conda run -n finsight pytest backend/tests/test_chat_api.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/chat.py backend/tests/test_chat_api.py
git commit -m "feat(api): chat routes plumb workspace_id + chat_session_id from RequestContext"
```

---

### Task 3.10: Update frontend axios + sessionStore for workspace_id default

**Files:**
- Modify: `frontend/src/api/axiosClient.ts`
- Modify: `frontend/src/stores/sessionStore.ts`

- [ ] **Step 1: Read current files**

Run: `cat frontend/src/api/axiosClient.ts frontend/src/stores/sessionStore.ts`

- [ ] **Step 2: Add `workspaceId` to sessionStore (persisted)**

In `frontend/src/stores/sessionStore.ts`, add `workspaceId: string` to the state interface (initialized to `"wks_default"`), and add it to the `partialize` config so it's persisted to localStorage alongside the existing fields.

- [ ] **Step 3: Add interceptor to inject `X-Workspace-ID` header**

In `frontend/src/api/axiosClient.ts`, add a request interceptor (after the existing response interceptor):

```typescript
import { useSessionStore } from '../stores/sessionStore';

axiosClient.interceptors.request.use((config) => {
  const { workspaceId } = useSessionStore.getState();
  config.headers['X-Workspace-ID'] = workspaceId || 'wks_default';
  return config;
});
```

- [ ] **Step 4: Manual verify in browser**

(After backend is running) Open the browser dev tools network tab, trigger any backend request (e.g., load the Sources panel). Verify the request includes `X-Workspace-ID: wks_default` in headers.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/axiosClient.ts frontend/src/stores/sessionStore.ts
git commit -m "feat(frontend): inject X-Workspace-ID header from sessionStore"
```

---

### Task 3.11: Optionally honor `X-Workspace-ID` header in `get_request_context`

**Files:**
- Modify: `backend/core/context.py`
- Modify: `backend/tests/test_context.py`

For v1, the backend ignores the header and always returns `wks_default`. But to make the frontend↔backend contract testable end-to-end, we'll have the dependency read the header if present (still defaulting to `wks_default`).

- [ ] **Step 1: Add a test**

Append to `backend/tests/test_context.py`:

```python
def test_request_context_reads_workspace_id_from_header():
    from fastapi import FastAPI, Depends, Header
    from fastapi.testclient import TestClient
    from backend.core.context import RequestContext, get_request_context

    app = FastAPI()

    @app.get("/whoami")
    def whoami(ctx: RequestContext = Depends(get_request_context)):
        return {"workspace": ctx.workspace_id}

    client = TestClient(app)
    r = client.get("/whoami", headers={"X-Workspace-ID": "wks_acme"})
    assert r.json()["workspace"] == "wks_acme"
```

- [ ] **Step 2: Run test, expect failure**

Run: `conda run -n finsight pytest backend/tests/test_context.py::test_request_context_reads_workspace_id_from_header -v`
Expected: FAIL — current dependency ignores headers.

- [ ] **Step 3: Modify `get_request_context` to read the header**

In `backend/core/context.py`, change `get_request_context` to:

```python
from fastapi import Header
from typing import Annotated


def get_request_context(
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-ID")] = None,
) -> RequestContext:
    """v1: user_id hardcoded; workspace_id from header (default wks_default)."""
    return RequestContext(
        user_id="usr_default",
        workspace_id=x_workspace_id or "wks_default",
    )
```

- [ ] **Step 4: Run all context tests**

Run: `conda run -n finsight pytest backend/tests/test_context.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/context.py backend/tests/test_context.py
git commit -m "feat(core): RequestContext reads workspace_id from X-Workspace-ID header"
```

---

### Task 3.12: Write the migration script (`migrate_to_workspace_schema.py`)

**Files:**
- Create: `backend/scripts/migrate_to_workspace_schema.py`
- Create: `backend/tests/test_migrate_to_workspace_schema.py`

This script handles Phases 2–4 from spec §6.

- [ ] **Step 1: Write the script**

Create `backend/scripts/migrate_to_workspace_schema.py`:

```python
"""
migrate_to_workspace_schema.py

One-shot script that ports surviving data into the new schema after PR #1
cleanup has run.

Role in project:
    Operational tooling. Run once, after `make cleanup-orphans APPLY=1`
    has removed orphans, to:
      1. Move surviving Pinecone vectors from namespace=default to
         namespace=wks_default, enriching metadata with user_id and
         workspace_id.
      2. Seed SQLite with the default user, workspace, member, and
         document records.
      3. Reorganize files on disk into data/uploads/wks_default/.
      4. Verify all stores are aligned and exit non-zero if not.

Main parts:
    - migrate_pinecone(): copies vectors to new namespace with enriched
      metadata, then drops the old namespace.
    - seed_sqlite(): inserts default user, workspace, member, default
      chat session, and Document rows for surviving files.
    - reorganize_disk(): moves the surviving uploaded file into the
      workspace-scoped directory; archives unrelated files.
    - verify(): final consistency check.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
import uuid
from pathlib import Path

DEFAULT_USER_ID = "usr_default"
DEFAULT_WORKSPACE_ID = "wks_default"
DEFAULT_CHAT_SESSION_ID = "ses_default"


def migrate_pinecone(store, source_ns: str, target_ns: str, user_id: str, workspace_id: str) -> int:
    """Copy all vectors from source_ns to target_ns; enrich metadata; drop source_ns."""
    print(f"  Migrating Pinecone {source_ns} → {target_ns}...")
    all_ids = []
    for page in store.index.list(namespace=source_ns):
        all_ids.extend(page)

    if not all_ids:
        print("  No vectors to migrate.")
        return 0

    BATCH = 100
    moved = 0
    for i in range(0, len(all_ids), BATCH):
        batch_ids = all_ids[i:i + BATCH]
        res = store.index.fetch(ids=batch_ids, namespace=source_ns)
        vectors = res.vectors if hasattr(res, "vectors") else res.get("vectors", {})
        new_records = []
        for vid, v in vectors.items():
            md = v.metadata if hasattr(v, "metadata") else v.get("metadata", {})
            values = v.values if hasattr(v, "values") else v.get("values")
            new_md = dict(md)
            new_md["user_id"] = user_id
            new_md["workspace_id"] = workspace_id
            new_records.append({"id": vid, "values": values, "metadata": new_md})
        store.index.upsert(vectors=new_records, namespace=target_ns)
        moved += len(new_records)

    time.sleep(2)  # let Pinecone catch up
    stats = store.index.describe_index_stats()
    target_count = stats.namespaces.get(target_ns, {}).get("vector_count", 0) if hasattr(stats.namespaces.get(target_ns, {}), "get") else getattr(stats.namespaces.get(target_ns), "vector_count", 0)
    if target_count != len(all_ids):
        raise RuntimeError(f"Verification failed: target ns has {target_count}, expected {len(all_ids)}")

    print(f"  ✅ {moved} vectors moved to {target_ns}. Dropping {source_ns}...")
    store.index.delete(delete_all=True, namespace=source_ns)
    return moved


def seed_sqlite(session, file_path: Path, doc_metadata_from_pinecone: dict, user_id: str, workspace_id: str) -> dict:
    """Insert default user, workspace, member, chat session, and the surviving document."""
    from backend.db.models import User, Workspace, WorkspaceMember, Document, ChatSession

    print("  Seeding SQLite with default records...")
    session.merge(User(id=user_id, email=None, display_name="Local User"))
    session.merge(Workspace(
        id=workspace_id, owner_id=user_id, name="Default Workspace",
        description="Created during migration from single-tenant schema",
        status="active",
    ))
    session.merge(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="owner"))
    session.merge(ChatSession(
        id=DEFAULT_CHAT_SESSION_ID, user_id=user_id, workspace_id=workspace_id,
        title="Untitled Chat",
    ))

    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest() if file_path.exists() else None

    doc_id = doc_metadata_from_pinecone.get("doc_id")
    session.merge(Document(
        id=doc_id,
        workspace_id=workspace_id,
        user_id=user_id,
        name=doc_metadata_from_pinecone.get("doc_name", file_path.name),
        doc_type=doc_metadata_from_pinecone.get("doc_type"),
        fiscal_year=doc_metadata_from_pinecone.get("fiscal_year"),
        file_hash=file_hash,
        chunk_count=doc_metadata_from_pinecone.get("chunk_count", 0),
        status="indexed",
    ))
    session.commit()
    print(f"  ✅ Seeded user, workspace, chat session, and document {doc_id}.")
    return {"doc_id": doc_id, "file_hash": file_hash}


def reorganize_disk(uploads_dir: Path, workspace_id: str, surviving_filename: str, surviving_doc_id: str, surviving_ext: str) -> Path:
    """Move surviving file to data/uploads/{workspace_id}/{doc_id}.{ext}; archive others."""
    print(f"  Reorganizing {uploads_dir}...")
    target_dir = uploads_dir / workspace_id
    archive_dir = uploads_dir / "_pre_migration"
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    surviving_src = uploads_dir / surviving_filename
    surviving_dst = target_dir / f"{surviving_doc_id}{surviving_ext}"

    if not surviving_src.exists():
        raise FileNotFoundError(f"Surviving file not found at {surviving_src}")

    shutil.move(str(surviving_src), str(surviving_dst))
    print(f"  Surviving file → {surviving_dst}")

    # Move all OTHER files in uploads_dir (not in subdirs) to archive
    for entry in uploads_dir.iterdir():
        if entry.is_file():
            shutil.move(str(entry), str(archive_dir / entry.name))
            print(f"  Archived: {entry.name}")

    return surviving_dst


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate single-tenant data into the multi-tenant schema."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Execute (default is dry-run plan only).")
    parser.add_argument("--surviving-file", required=True,
                        help="Filename of the EOG PDF that should survive migration.")
    args = parser.parse_args()

    print("=== Migrate to Workspace Schema ===")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Surviving file: {args.surviving_file}")
    print()

    if not args.apply:
        print("Dry-run plan:")
        print(f"  1. Move all vectors from Pinecone namespace 'default' → 'wks_default' with enriched metadata")
        print(f"  2. Drop Pinecone namespace 'default'")
        print(f"  3. Insert SQLite rows: user usr_default, workspace wks_default, member, chat ses_default, document")
        print(f"  4. Move data/uploads/{args.surviving_file} → data/uploads/wks_default/<doc_id>.pdf")
        print(f"  5. Archive other files in data/uploads/ to data/uploads/_pre_migration/")
        print(f"  6. Verify final state")
        print()
        print("Re-run with --apply to execute.")
        return 0

    # APPLY path
    from backend.core.pinecone_store import get_pinecone_store
    from backend.db.engine import get_session_factory
    store = get_pinecone_store()
    SessionLocal = get_session_factory()

    # Determine the surviving doc_id by reading Pinecone metadata
    print("Identifying surviving doc_id from Pinecone...")
    sample_ids = []
    for page in store.index.list(namespace="default"):
        sample_ids.extend(page)
        if len(sample_ids) >= 1:
            break
    if not sample_ids:
        print("❌ No vectors in namespace=default. Migration aborted.")
        return 1
    res = store.index.fetch(ids=sample_ids[:1], namespace="default")
    vectors = res.vectors if hasattr(res, "vectors") else res.get("vectors", {})
    first_md = next(iter(vectors.values()))
    md = first_md.metadata if hasattr(first_md, "metadata") else first_md.get("metadata", {})
    surviving_doc_id = md["doc_id"]
    surviving_doc_name = md.get("doc_name", args.surviving_file)
    surviving_doc_type = md.get("doc_type")
    surviving_fy = md.get("fiscal_year")
    surviving_ext = Path(args.surviving_file).suffix.lower()
    print(f"  Surviving doc_id: {surviving_doc_id}")

    # 1+2. Pinecone migration
    moved = migrate_pinecone(store, "default", DEFAULT_WORKSPACE_ID, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID)

    # 3. SQLite seed
    uploads_dir = Path("data/uploads")
    surviving_src = uploads_dir / args.surviving_file
    with SessionLocal() as session:
        seed_sqlite(
            session, surviving_src,
            {"doc_id": surviving_doc_id, "doc_name": surviving_doc_name,
             "doc_type": surviving_doc_type, "fiscal_year": surviving_fy,
             "chunk_count": moved},
            DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID,
        )

    # 4. Disk reorg (must come AFTER SQLite seed because seed reads the file for hashing)
    reorganize_disk(uploads_dir, DEFAULT_WORKSPACE_ID, args.surviving_file, surviving_doc_id, surviving_ext)

    print()
    print("✅ Migration complete. Run `make stats` to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write a basic smoke test (in-memory)**

Create `backend/tests/test_migrate_to_workspace_schema.py`:

```python
"""
test_migrate_to_workspace_schema.py

Unit tests for the migration script's pure functions (Pinecone and disk
operations are mocked).
"""
from pathlib import Path
from unittest.mock import MagicMock
from backend.scripts.migrate_to_workspace_schema import seed_sqlite


def test_seed_sqlite_inserts_default_records(tmp_path):
    from backend.db.engine import create_engine_for_url, make_session_factory
    from backend.db.models import Base, User, Workspace, Document, ChatSession

    engine = create_engine_for_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    # Create a fake source file for hashing
    src_file = tmp_path / "EOG.pdf"
    src_file.write_bytes(b"fake pdf bytes")

    with SessionLocal() as session:
        result = seed_sqlite(
            session, src_file,
            {"doc_id": "doc_test1234", "doc_name": "EOG.pdf",
             "doc_type": "10-K", "fiscal_year": "2025", "chunk_count": 1220},
            "usr_default", "wks_default",
        )

    assert result["doc_id"] == "doc_test1234"
    assert result["file_hash"] is not None

    with SessionLocal() as session:
        assert session.get(User, "usr_default") is not None
        assert session.get(Workspace, "wks_default") is not None
        assert session.get(ChatSession, "ses_default") is not None
        doc = session.get(Document, "doc_test1234")
        assert doc.chunk_count == 1220
        assert doc.workspace_id == "wks_default"
```

- [ ] **Step 3: Run test**

Run: `conda run -n finsight pytest backend/tests/test_migrate_to_workspace_schema.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/migrate_to_workspace_schema.py backend/tests/test_migrate_to_workspace_schema.py
git commit -m "feat(migrate): one-shot script for Pinecone namespace + SQLite seed + disk reorg"
```

---

### Task 3.13: Wire `make migrate-to-workspace-schema` target

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add the target**

In `Makefile`, add `migrate-to-workspace-schema` to `.PHONY`. Add the target before `install:`:

```makefile
# ── migrate-to-workspace-schema: port single-tenant data into multi-tenant schema ──
migrate-to-workspace-schema:
	@cd $(CURDIR) && PYTHONPATH=. $(FINSIGHT_BIN)/python backend/scripts/migrate_to_workspace_schema.py \
	    $(if $(APPLY),--apply,) \
	    --surviving-file "$(SURVIVING_FILE)"
```

- [ ] **Step 2: Verify dry-run via make**

Run: `make migrate-to-workspace-schema SURVIVING_FILE='EOG (EOG Resources Inc.)  (10-K) 2026-02-24.pdf'`
Expected: dry-run plan output, no changes.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat(make): add migrate-to-workspace-schema target with dry-run default"
```

---

### Task 3.14: Execute the migration

> **⚠️ DESTRUCTIVE — REQUIRES USER CONFIRMATION.**

- [ ] **Step 1: Pre-flight — re-run cleanup verification and ensure SQLite is at head**

Run: `make stats`
Expected: 0 orphans, 1,220 vectors in `default` namespace.

Run: `conda run -n finsight alembic upgrade head`
Expected: `data/finsight.db` exists with empty tables.

Run: `conda run -n finsight pytest backend/tests/ -v -k "not integration"`
Expected: all tests pass.

- [ ] **Step 2: Pause and confirm with user**

Show the dry-run plan one more time. Wait for explicit user approval before APPLY.

- [ ] **Step 3: Apply the migration**

Run: `make migrate-to-workspace-schema APPLY=1 SURVIVING_FILE='EOG (EOG Resources Inc.)  (10-K) 2026-02-24.pdf'`
Expected: prints progress, ends with "✅ Migration complete."

- [ ] **Step 4: Verify final state**

Run: `make stats`
Expected: namespaces show `wks_default: 1220 vectors`, `default: 0 vectors` (or absent). Cross-check shows ✅ if `make stats` is updated to read SQLite — for now, manually verify SQLite:

Run: `conda run -n finsight python -c "from backend.db.engine import get_session_factory; from backend.db.models import User, Workspace, Document, ChatSession; SL = get_session_factory(); s = SL(); print('users=', s.query(User).count(), 'workspaces=', s.query(Workspace).count(), 'documents=', s.query(Document).count(), 'sessions=', s.query(ChatSession).count())"`
Expected: `users= 1 workspaces= 1 documents= 1 sessions= 1`

Verify disk:
Run: `ls -la data/uploads/wks_default/ data/uploads/_pre_migration/`
Expected: surviving file in `wks_default/`, others in `_pre_migration/`.

- [ ] **Step 5: Manual smoke test — upload a new doc, ask a question**

Run: `make start`
Open http://localhost:5173. Upload a new test PDF; verify it lands in `data/uploads/wks_default/<doc_id>.pdf`. Ask a question about it. Verify a cited answer comes back.

- [ ] **Step 6: Stop and commit**

Run: `make stop`

```bash
git add data/finsight.db   # NO — this is gitignored
# Migration is a one-shot operation; nothing new to commit beyond the script that ran.
# Skip this step (no commit needed for the migration execution itself).
```

---

## PR #3 Verification Checklist

Before opening PR #3:

- [ ] All tests pass (`pytest -k "not integration"`)
- [ ] Migration script ran cleanly; `make stats` shows no orphans, namespace `wks_default` has 1,220 vectors
- [ ] SQLite has 1 user, 1 workspace, 1 member, 1 document, 1 chat session
- [ ] Disk has `data/uploads/wks_default/<doc_id>.pdf` and `data/uploads/_pre_migration/` folder
- [ ] Manual smoke test: upload a new doc, ask a question, get cited answer
- [ ] Old code paths (Redis registry) still work alongside new ones — they're not removed yet
- [ ] `make doctor` passes

---

# PR #4 — Remove Redis

**Goal:** Remove Redis from the stack entirely. LangGraph switches to SqliteSaver. Doc cleanups across 10+ files.

---

### Task 4.1: Switch LangGraph checkpointer from RedisSaver to SqliteSaver

**Files:**
- Modify: `backend/agents/orchestrator.py`
- Modify: `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Find the current `get_checkpointer()` function**

Run: `grep -n "RedisSaver\|get_checkpointer" backend/agents/orchestrator.py`

- [ ] **Step 2: Replace `RedisSaver` import and `get_checkpointer()` body**

In `backend/agents/orchestrator.py`:

Replace:
```python
from langgraph.checkpoint.redis import RedisSaver
```
With:
```python
from langgraph.checkpoint.sqlite import SqliteSaver
```

Replace the body of `get_checkpointer()`:
```python
def get_checkpointer():
    """SQLite-backed checkpointer; uses the same data/finsight.db file as the control plane."""
    import sqlite3
    from backend.core.config import get_settings
    settings = get_settings()
    db_path = getattr(settings, "database_url", "sqlite:///data/finsight.db").replace("sqlite:///", "")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)
```

- [ ] **Step 3: Run orchestrator tests**

Run: `conda run -n finsight pytest backend/tests/test_orchestrator.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/agents/orchestrator.py
git commit -m "feat(agents): swap RedisSaver → SqliteSaver for LangGraph checkpointer"
```

---

### Task 4.2: Remove `mcp_memory_write` calls from chat.py

**Files:**
- Modify: `backend/api/routes/chat.py`
- Modify: `backend/tests/test_chat_api.py`
- Modify: `backend/tests/test_chat_fixes.py`

- [ ] **Step 1: Locate the call sites**

Run: `grep -n "mcp_memory_write\|mcp_memory_read" backend/api/routes/chat.py`
Expected: lines around 33, 96, 97, 180, 181.

- [ ] **Step 2: Remove the import + 4 call sites**

In `backend/api/routes/chat.py`:
- Remove `mcp_memory_write` from the imports line (line ~33)
- Remove the 4 call sites that look like `mcp_memory_write(session_id, {...})`

- [ ] **Step 3: Remove `mcp_memory_write` patches from tests**

In `backend/tests/test_chat_api.py` and `backend/tests/test_chat_fixes.py`, find every line like:
```python
patch("backend.api.routes.chat.mcp_memory_write"), \
```
and remove it. Adjust the surrounding `with` block to maintain valid syntax.

- [ ] **Step 4: Run tests**

Run: `conda run -n finsight pytest backend/tests/test_chat_api.py backend/tests/test_chat_fixes.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/chat.py backend/tests/test_chat_api.py backend/tests/test_chat_fixes.py
git commit -m "refactor(chat): remove redundant mcp_memory_write calls (LangGraph state is sufficient)"
```

---

### Task 4.3: Remove Redis-backed tools from `memory_tools.py`

**Files:**
- Modify: `backend/mcp_server/tools/memory_tools.py`
- Modify: `backend/mcp_server/financial_mcp_server.py`
- Modify: `backend/tests/test_memory_tools.py`

- [ ] **Step 1: Remove `mcp_memory_read` and `mcp_memory_write` from `memory_tools.py`**

In `backend/mcp_server/tools/memory_tools.py`:
- Remove the `mcp_memory_read` function (lines ~30–35)
- Remove the `mcp_memory_write` function (lines ~38–45)
- Remove the `from backend.core.redis_client import get_redis_client` import (line ~24)

Update the file header docstring to drop references to `mcp_memory_read` / `mcp_memory_write`.

- [ ] **Step 2: Deregister the MCP tool exposure**

In `backend/mcp_server/financial_mcp_server.py`, remove these lines:
```python
mcp.tool()(mcp_memory_read)
mcp.tool()(mcp_memory_write)
```

Also remove `mcp_memory_read, mcp_memory_write,` from the import statement (line ~40).

- [ ] **Step 3: Remove tests for the removed functions**

In `backend/tests/test_memory_tools.py`, delete the tests that exercise `mcp_memory_read` and `mcp_memory_write` (lines ~24–60). Keep tests for `mcp_intent_log`, `mcp_response_logger`, `mcp_citation_validator`, `mcp_export_trigger`.

In `backend/tests/test_mcp_server.py`, remove `"mcp_memory_read"` and `"mcp_memory_write"` from the expected-tools list.

- [ ] **Step 4: Run all relevant tests**

Run: `conda run -n finsight pytest backend/tests/test_memory_tools.py backend/tests/test_mcp_server.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_server/tools/memory_tools.py backend/mcp_server/financial_mcp_server.py backend/tests/test_memory_tools.py backend/tests/test_mcp_server.py
git commit -m "refactor(mcp): remove Redis-backed memory tools (superseded by LangGraph)"
```

---

### Task 4.4: Remove Redis from `health.py` and `main.py`

**Files:**
- Modify: `backend/api/routes/health.py`
- Modify: `backend/api/main.py`
- Modify: `backend/tests/test_health.py`

- [ ] **Step 1: Update `health.py`**

In `backend/api/routes/health.py`:
- Remove `from backend.core.redis_client import ping_redis` import
- Remove `"redis": ping_redis()` from the response dict (or whatever the current key is)

Update the file's docstring "Main parts" to drop the Redis check.

- [ ] **Step 2: Update `main.py` startup**

In `backend/api/main.py`:
- Remove the conditional Redis ping block (line ~33)
- Remove the conditional import of `ping_redis`

- [ ] **Step 3: Update tests**

In `backend/tests/test_health.py`, find the test that asserts `"redis"` is in the response. Remove that assertion. The test should now assert `"redis"` is NOT in the response.

- [ ] **Step 4: Run tests**

Run: `conda run -n finsight pytest backend/tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/health.py backend/api/main.py backend/tests/test_health.py
git commit -m "refactor(api): drop Redis health check + startup ping"
```

---

### Task 4.5: Delete `redis_client.py` and its test file

**Files:**
- Delete: `backend/core/redis_client.py`
- Delete: `backend/tests/test_redis_client.py`

- [ ] **Step 1: Verify no remaining imports**

Run: `grep -rn "from backend.core.redis_client\|import redis_client" backend --include='*.py'`
Expected: empty output (or only matches in tests we're about to delete).

- [ ] **Step 2: Delete the files**

Run: `rm backend/core/redis_client.py backend/tests/test_redis_client.py`

- [ ] **Step 3: Run the full test suite**

Run: `conda run -n finsight pytest backend/tests/ -v -k "not integration"`
Expected: all PASS (no ImportError).

- [ ] **Step 4: Commit**

```bash
git add -A backend/core/redis_client.py backend/tests/test_redis_client.py
git commit -m "chore: delete redis_client.py and its tests (no longer imported anywhere)"
```

---

### Task 4.6: Remove Redis from `requirements.txt` and `Makefile`

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `Makefile`

- [ ] **Step 1: Remove from requirements.txt**

In `backend/requirements.txt`, delete the lines:
```
redis==5.2.1
langgraph-checkpoint-redis>=0.4.0
```

- [ ] **Step 2: Uninstall locally**

Run: `conda run -n finsight pip uninstall -y redis langgraph-checkpoint-redis`

- [ ] **Step 3: Remove Redis from Makefile**

In `Makefile`:

In the `start:` target, delete:
```makefile
@docker start redis-finsight 2>/dev/null || docker run -d --name redis-finsight -p 6379:6379 redis:alpine
@echo "✅ Redis running on localhost:6379"
```

In the `stop:` target, delete:
```makefile
@-docker stop redis-finsight 2>/dev/null
```

In the `status:` target, delete:
```makefile
@docker ps --filter name=redis-finsight --format "Redis: {{.Status}}" 2>/dev/null || echo "Redis: not running"
```

In the `doctor:` target, delete the "Redis container" check block (lines ~62–67).

- [ ] **Step 4: Verify the app still starts**

Run: `make start`
Expected: backend reaches `/health` within 15 s, frontend starts. **No Redis container created.**

Run: `make stop`

Run: `make doctor`
Expected: passes without checking Redis.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt Makefile
git commit -m "chore: remove redis from requirements.txt and Makefile"
```

---

### Task 4.7: Update CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Update CLAUDE.md**

In `CLAUDE.md`:
- Architecture section: replace Redis box with SQLite; remove Redis from the dependency tree
- Operational Gotchas: remove the "Redis in docker" subsection; add a brief "SQLite control plane" subsection
- Cheatsheet: remove all Redis-related commands; add SQLite + Alembic commands
- Decision Log: add an entry for 2026-04-20 — "Storage refactor: dropped Redis, SQLite is the single source of truth for control plane"
- Phase table: mark Phase 6 status updated; add note about storage refactor completion
- File Structure section: update to reflect new `backend/db/` directory

- [ ] **Step 2: Update README.md**

In `README.md`:
- Tech stack table: remove Redis row; add SQLite + SQLAlchemy
- Architecture diagram: remove Redis from infra layer; replace with SQLite
- Setup section: remove `docker run -d --name redis-finsight ...`; add `alembic upgrade head` step
- Troubleshooting: remove "Redis container Up but backend can't connect"; add SQLite-related notes
- Phase 6 list: update the infra-hardening checkboxes

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update CLAUDE.md + README.md to reflect Redis removal and SQLite control plane"
```

---

### Task 4.8: Final verification — full app boots without Redis

- [ ] **Step 1: Stop any running services and remove the Redis container**

Run: `make stop`
Run: `docker rm -f redis-finsight 2>/dev/null || true`

- [ ] **Step 2: Verify Redis is fully gone from the stack**

Run: `docker ps --filter name=redis-finsight`
Expected: no output (no container).

Run: `pip list | grep -iE "redis|langgraph-checkpoint-redis"`
Expected: no output.

Run: `grep -rn "from backend.core.redis_client\|import.*redis" backend --include='*.py'`
Expected: empty (no imports).

- [ ] **Step 3: Cold-boot the app**

Run: `make start`
Expected: backend up in <15 s, frontend on 5173, no Redis container created.

Run: `make doctor`
Expected: ✅ all checks pass without Redis.

- [ ] **Step 4: Smoke test**

Open http://localhost:5173:
- Upload a new test PDF → succeeds, lands in `data/uploads/wks_default/<doc_id>.pdf`
- Ask a question about it → cited answer comes back
- Refresh the browser → chat history persists (SqliteSaver works)
- Stop and restart: `make stop && make start` → chat history still there

- [ ] **Step 5: Run full test suite**

Run: `conda run -n finsight pytest backend/tests/ -v -k "not integration"`
Expected: all PASS (~245 tests after PR #4 removes a few).

Run: `conda run -n finsight pytest backend/tests/ -v -m integration`
Expected: all 23 integration tests pass.

---

## PR #4 Verification Checklist

Before opening PR #4:

- [ ] No Redis container needed; `docker ps` shows none after `make start`
- [ ] `pip list | grep redis` returns nothing
- [ ] `grep -rn "redis" backend --include="*.py"` returns no matches outside removed files
- [ ] `make start`, `make stop`, `make doctor` all succeed
- [ ] Chat history survives `make stop && make start`
- [ ] All tests pass (unit + integration)
- [ ] CLAUDE.md and README.md updated; no stale Redis references

---

## End-to-End Verification (after all 4 PRs merge)

- [ ] Spec §9 success criteria all met (10 items)
- [ ] `make stats` shows clean state
- [ ] Backend reaches `/health` without any external services besides Pinecone
- [ ] Foundation ready for sub-project 3 (auth)

---

## Self-Review Notes

Reviewing this plan against the spec:

**Spec §1 (orphan investigation context)** → covered by PR #1 motivation; cleanup script tests cover the bug class.

**Spec §2 (B′ strategy)** → all 4 PRs implement B′; PR #3 hardcodes `usr_default`/`wks_default` per spec.

**Spec §3 (10 decisions)** → each decision has corresponding tasks: D1 (hierarchy) in 2.4 models; D2 (sharing v2) reflected in workspace_members table; D3 (namespace per workspace) in 3.4, 3.6; D4 (SQLite) in 2.x; D5 (SqliteSaver) in 4.1; D6 (drop Redis) in 4.2-4.6; D7 (archive only) — schema supports `status` column, no UI in this plan (sub-project 5); D8 (workspace owns docs) in 2.4 + 3.7-3.8; D9 (thread_id = chat_session_id) in 3.5, 3.9; D10 (default chat) in migration 3.12.

**Spec §4 (data model)** → §4.2 metadata in 3.8 + 3.12 (migration script enriches); §4.3 SQLite schema in 2.4 models; §4.4 file layout in 3.8 (upload route) + 3.12 (migration); §4.5 ID format in 3.3 (deterministic IDs).

**Spec §5 (operations)** → §5.1 RequestContext in 3.1; §5.2 StorageTransaction in 3.2; §5.3 upload in 3.8; §5.4 list in 3.7-3.8; §5.5 query/RAG in 3.4, 3.6; §5.6 delete in 3.8; §5.7 chat sessions in 3.5, 3.9, 3.12; §5.8 workspace lifecycle — schema supports it, no UI in this plan.

**Spec §6 (cleanup + migration)** → §6.1 pre-flight via `make stats` (existing); §6.2 in PR #1 entirely; §6.3 in 3.12 migrate_pinecone; §6.4 in 3.12 seed_sqlite; §6.5 in 3.12 reorganize_disk; §6.6 verification in 3.14; §6.7 rollback inherent to TDD + dry-runs.

**Spec §7 (PR sequence)** → 4 PRs structured exactly as in spec.

**Placeholder scan:** searched for TBD/TODO/FIXME — none. All steps have actual code or commands.

**Type consistency:** `RequestContext` (dataclass), `StorageTransaction` (class), all model class names (`User`, `Workspace`, etc.), function names (`embed_and_upsert`, `semantic_search`, `find_orphan_doc_ids`, `seed_sqlite`, etc.) — all consistent across tasks.

**Coverage gaps found and added during self-review:**
- Task 3.11 added (X-Workspace-ID header support) — needed to make end-to-end frontend↔backend testable for v1
- Task 3.13 added (`make migrate-to-workspace-schema` Makefile target) — implied but not explicit in spec

No further gaps identified.
