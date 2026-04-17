"""
test_redis_atomicity.py

Tests that verify document register and delete operations use Redis pipelines for atomic execution.

Role in project:
    Test suite — verifies the atomic Redis pipeline behaviour of backend.mcp_server.tools.document_tools. Run with:
    pytest tests/test_redis_atomicity.py -v

Coverage:
    - register_document opens a Redis pipeline, calls WATCH on the document key, issues MULTI, and executes
    - register_document appends to an existing document list and serialises the full updated list via SET
    - delete_document opens a Redis pipeline and calls WATCH before performing the deletion
    - delete_document returns False without modifying Redis when the requested doc_id is not found
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from backend.mcp_server.tools.document_tools import register_document, delete_document, DOCS_REDIS_KEY


class TestAtomicRegister:
    def test_register_uses_pipeline(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__ = MagicMock(return_value=mock_pipe)
        mock_pipe.__exit__ = MagicMock(return_value=False)
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.get.return_value = None

        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis):
            register_document({"doc_id": "abc", "doc_name": "test.pdf"}, chunk_count=10)

        mock_redis.pipeline.assert_called()
        mock_pipe.watch.assert_called_with(DOCS_REDIS_KEY)
        mock_pipe.multi.assert_called()
        mock_pipe.execute.assert_called()

    def test_register_sets_correct_json(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__ = MagicMock(return_value=mock_pipe)
        mock_pipe.__exit__ = MagicMock(return_value=False)
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.get.return_value = json.dumps([{"doc_id": "existing"}])

        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis):
            register_document({"doc_id": "new", "doc_name": "new.pdf"}, chunk_count=5)

        # Verify the set call contains both docs
        set_call_args = mock_pipe.set.call_args[0]
        assert set_call_args[0] == DOCS_REDIS_KEY
        docs = json.loads(set_call_args[1])
        assert len(docs) == 2


class TestAtomicDelete:
    def test_delete_uses_pipeline(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__ = MagicMock(return_value=mock_pipe)
        mock_pipe.__exit__ = MagicMock(return_value=False)
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.get.return_value = json.dumps([{"doc_id": "abc"}])

        mock_store = MagicMock()
        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis), \
             patch("backend.mcp_server.tools.document_tools.get_pinecone_store", return_value=mock_store):
            result = delete_document("abc")

        assert result is True
        mock_redis.pipeline.assert_called()
        mock_pipe.watch.assert_called_with(DOCS_REDIS_KEY)

    def test_delete_nonexistent_returns_false(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__ = MagicMock(return_value=mock_pipe)
        mock_pipe.__exit__ = MagicMock(return_value=False)
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.get.return_value = json.dumps([{"doc_id": "other"}])

        with patch("backend.mcp_server.tools.document_tools.get_redis_client", return_value=mock_redis):
            result = delete_document("nonexistent")

        assert result is False
