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
