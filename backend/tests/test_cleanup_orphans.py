"""
test_cleanup_orphans.py

Unit tests for the orphan cleanup script. Pinecone and Redis are mocked.
"""
import json
from unittest.mock import MagicMock
from backend.scripts.cleanup_orphans import find_orphan_doc_ids
from backend.scripts.cleanup_orphans import count_vectors_per_doc_id


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
    assert counts["doc_bbb"]["doc_name"] == "B.pdf"


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
