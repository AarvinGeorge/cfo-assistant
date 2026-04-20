"""
stats.py

CLI script that prints a cross-referenced snapshot of Pinecone (vectors)
and SQLite (control plane documents table) so orphan vectors are visible
at a glance.

Role in project:
    Operational tooling, invoked by `make stats`. Not imported by the
    runtime app. Reads from Pinecone (vector counts per namespace) and
    SQLite (documents table via SQLAlchemy) and prints a formatted
    summary. Exits non-zero if any namespace's vector count doesn't
    match the sum of its registered documents' chunk counts (orphan
    detection). After PR #4 there should never be orphans because
    StorageTransaction wraps every write atomically.

Main parts:
    - main(): entry point. Collects stats, prints the table, and exits
      with code 0 on clean cross-check, 1 on mismatch.
    - _fmt_int(n): thousands-separator helper.
"""
from __future__ import annotations

import sys
from collections import defaultdict


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def main() -> int:
    from backend.core.pinecone_store import get_pinecone_store
    from backend.db.engine import get_session_factory
    from backend.db.models import Document, Workspace

    # ── Pinecone ──────────────────────────────────────────────────────────
    store = get_pinecone_store()
    stats = store.index.describe_index_stats()
    total_vectors = int(stats.total_vector_count or 0)
    namespaces: dict[str, int] = {}
    for ns, ns_stats in (stats.namespaces or {}).items():
        count = getattr(ns_stats, "vector_count", None)
        if count is None and isinstance(ns_stats, dict):
            count = ns_stats.get("vector_count", 0)
        namespaces[ns] = int(count or 0)

    # ── SQLite ────────────────────────────────────────────────────────────
    SessionLocal = get_session_factory()
    ws_chunk_sum: dict[str, int] = defaultdict(int)
    workspaces: dict[str, Workspace] = {}
    docs_by_ws: dict[str, list[Document]] = defaultdict(list)

    with SessionLocal() as session:
        for ws in session.query(Workspace).all():
            workspaces[ws.id] = ws
        for doc in session.query(Document).filter(Document.status == "indexed").all():
            docs_by_ws[doc.workspace_id].append(doc)
            ws_chunk_sum[doc.workspace_id] += int(doc.chunk_count or 0)

    # ── Print ─────────────────────────────────────────────────────────────
    print("=== FinSight Stats ===")
    print()
    print(f"Pinecone index      : {store.index_name} (dim={store.dimension})")
    if namespaces:
        print("  Namespaces:")
        for ns, cnt in sorted(namespaces.items()):
            label = ns if ns else "(default/unnamed)"
            print(f"    {label:<18}: {_fmt_int(cnt)} vectors")
    else:
        print("  Namespaces        : (none)")
    print(f"  Total vectors     : {_fmt_int(total_vectors)}")
    print()

    print("SQLite control plane: data/finsight.db")
    if workspaces:
        print("  Workspaces:")
        for ws_id, ws in sorted(workspaces.items()):
            docs = docs_by_ws.get(ws_id, [])
            chunks = ws_chunk_sum.get(ws_id, 0)
            print(f"    {ws_id:<18} name={ws.name!r:<26} docs={len(docs)} chunks={_fmt_int(chunks)}")
            for d in docs:
                tag = f"[{d.doc_type or '?'}, {d.fiscal_year or '—'}]"
                print(f"      - {d.id[:16]}.. {tag:<14} {d.name[:40]:<40} {_fmt_int(d.chunk_count)} chunks")
    else:
        print("  Workspaces        : (none)")
    print(f"  Total workspaces  : {_fmt_int(len(workspaces))}")
    total_sql_chunks = sum(ws_chunk_sum.values())
    print(f"  Sum of chunks     : {_fmt_int(total_sql_chunks)}")
    print()

    # ── Cross-check: each namespace's vector count should match the SQLite
    # sum for the matching workspace_id ─────────────────────────────────────
    fails = 0
    print("Cross-check         :")
    for ns, vec_count in sorted(namespaces.items()):
        sql_count = ws_chunk_sum.get(ns, 0)
        has_ws = ns in workspaces
        if vec_count == sql_count:
            status = "✅"
        else:
            status = "⚠️ "
            fails += 1
        print(
            f"  {status} ns={ns!r:<18} pinecone={_fmt_int(vec_count):<10} "
            f"sqlite_workspace_chunks={_fmt_int(sql_count):<10} "
            f"{'(workspace registered)' if has_ws else '(no matching workspace!)'}"
        )

    if fails == 0:
        print()
        print("  All namespaces match their SQLite workspace chunk sum.")
        return 0
    print()
    print(f"  {fails} mismatch(es). Investigate orphan vectors or unregistered workspaces.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
