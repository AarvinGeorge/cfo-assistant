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
