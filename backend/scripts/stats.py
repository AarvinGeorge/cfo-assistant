"""
stats.py

CLI script that prints a cross-referenced snapshot of the two durable stores
(Pinecone + Redis) so orphaned vectors are visible at a glance.

Role in project:
    Operational tooling, invoked by `make stats`. Not imported by the runtime
    app. Reads from Pinecone (via PineconeStore singleton) and Redis (via
    the document registry key `finsight:documents`) and prints a formatted
    summary. Exits non-zero if the two sources disagree.

Main parts:
    - main(): entry point. Collects stats, prints the table, and exits with
      code 0 on match, 1 on mismatch (suitable for scripting).
    - _fmt_int(n): thousands-separator helper for readable large counts.
"""
from __future__ import annotations

import json
import sys

from backend.core.pinecone_store import get_pinecone_store
from backend.core.redis_client import get_redis_client
from backend.mcp_server.tools.document_tools import DOCS_REDIS_KEY


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def main() -> int:
    # ─── Pinecone ─────────────────────────────────────────────────────────
    store = get_pinecone_store()
    stats = store.index.describe_index_stats()
    total_vectors = int(stats.total_vector_count or 0)
    namespaces = dict(stats.namespaces) if stats.namespaces else {}

    # ─── Redis registry ───────────────────────────────────────────────────
    redis_client = get_redis_client()
    docs_raw = redis_client.get(DOCS_REDIS_KEY)
    docs = json.loads(docs_raw) if docs_raw else []
    registry_chunk_sum = sum(int(d.get("chunk_count", 0)) for d in docs)

    # ─── Print ────────────────────────────────────────────────────────────
    print("=== FinSight Stats ===")
    print()
    print(f"Pinecone index      : {store.index_name} (dim={store.dimension})")
    if namespaces:
        print("  Namespaces:")
        for ns, ns_stats in namespaces.items():
            ns_count = getattr(ns_stats, "vector_count", None)
            if ns_count is None and isinstance(ns_stats, dict):
                ns_count = ns_stats.get("vector_count", 0)
            label = ns if ns else "(default/unnamed)"
            print(f"    {label:<18}: {_fmt_int(int(ns_count or 0))} vectors")
    else:
        print("  Namespaces        : (none)")
    print(f"  Total vectors     : {_fmt_int(total_vectors)}")
    print()
    print(f"Redis registry      : {DOCS_REDIS_KEY}")
    if docs:
        print("  Documents:")
        for d in docs:
            tag = f"[{d.get('doc_type', '?')}, {d.get('fiscal_year') or '—'}]"
            name = d.get("doc_name", "<unnamed>")
            chunks = int(d.get("chunk_count", 0))
            print(f"    {tag:<18} {name:<40} {_fmt_int(chunks)} chunks")
    else:
        print("  Documents         : (none registered)")
    print(f"  Total documents   : {_fmt_int(len(docs))}")
    print(f"  Sum of chunk_count: {_fmt_int(registry_chunk_sum)}")
    print()

    # ─── Cross-check ──────────────────────────────────────────────────────
    if total_vectors == registry_chunk_sum:
        print(f"Cross-check         : ✅ vector count matches registry sum (0 orphans)")
        return 0

    delta = total_vectors - registry_chunk_sum
    if delta > 0:
        print(
            f"Cross-check         : ⚠️  Pinecone={_fmt_int(total_vectors)}  "
            f"Redis={_fmt_int(registry_chunk_sum)}  — "
            f"{_fmt_int(delta)} orphan vectors"
        )
        print(
            "                       Likely cause: document deleted from Redis but "
            "Pinecone delete failed,\n"
            "                       or Redis container was recreated after ingest "
            "(registry lost, vectors survived)."
        )
    else:
        print(
            f"Cross-check         : ⚠️  Pinecone={_fmt_int(total_vectors)}  "
            f"Redis={_fmt_int(registry_chunk_sum)}  — "
            f"{_fmt_int(-delta)} missing vectors"
        )
        print(
            "                       Likely cause: ingest partially failed (Redis "
            "registered the doc but\n"
            "                       Pinecone upsert didn't complete for all chunks)."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
