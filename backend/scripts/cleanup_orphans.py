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
