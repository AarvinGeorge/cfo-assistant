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
