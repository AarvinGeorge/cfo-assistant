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
