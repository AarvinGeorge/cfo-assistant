import pytest
from unittest.mock import patch, MagicMock
from backend.core.pinecone_store import PineconeStore


def test_pinecone_store_initializes():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=3072)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        store = PineconeStore()
    assert store.index_name == "finsight-index"
    assert store.namespace == "default"
    assert store.dimension == 3072


def test_pinecone_store_raises_if_dimension_mismatch():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=1536)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        with pytest.raises(ValueError, match="dimension mismatch"):
            PineconeStore()


def test_is_ready_returns_true_when_connected():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=3072)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        store = PineconeStore()
    assert store.is_ready() is True


def test_is_ready_returns_false_on_exception():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=3072)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        store = PineconeStore()
    # Now make subsequent describe_index_stats fail
    store._index.describe_index_stats.side_effect = Exception("connection lost")
    assert store.is_ready() is False


@pytest.mark.integration
def test_pinecone_store_live_connection():
    """Requires PINECONE_API_KEY and finsight-index created in console (dim=3072, cosine)"""
    store = PineconeStore()
    assert store.is_ready() is True
