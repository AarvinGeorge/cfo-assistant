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
    - count_vectors_per_doc_id(): for a given set of doc_ids, returns per-doc
      vector counts and display metadata (doc_name) for dry-run summaries.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


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


if __name__ == "__main__":
    sys.exit(main())
