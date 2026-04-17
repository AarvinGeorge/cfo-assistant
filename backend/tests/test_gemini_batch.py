"""
test_gemini_batch.py

Tests that verify the GeminiClient sends multiple texts as a single batched embedding API call.

Role in project:
    Test suite — verifies the batch embedding behaviour of backend.core.gemini_client. Run with:
    pytest tests/test_gemini_batch.py -v

Coverage:
    - embed_texts issues exactly one API call for a list of multiple texts (not N individual calls)
    - The entire list is passed as the content argument to genai.embed_content
    - A single-item list is handled correctly via the batch path
    - Each returned embedding vector has the expected 3072 dimensions
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.core.gemini_client import GeminiClient


def test_embed_texts_uses_batch_api():
    """embed_texts should make one API call for multiple texts, not N calls."""
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = {"embeddings": [[0.1] * 3072, [0.2] * 3072, [0.3] * 3072]}
        client = GeminiClient()
        results = client.embed_texts(["text1", "text2", "text3"])

    # Should be exactly 1 call (batch), not 3
    assert mock_genai.embed_content.call_count == 1
    # Should pass the list as content
    call_args = mock_genai.embed_content.call_args
    assert call_args[1]["content"] == ["text1", "text2", "text3"]
    assert len(results) == 3


def test_embed_texts_single_item():
    """Single item should still work via batch."""
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = {"embeddings": [[0.1] * 3072]}
        client = GeminiClient()
        results = client.embed_texts(["single text"])

    assert len(results) == 1
    assert len(results[0]) == 3072


def test_embed_texts_returns_correct_dimensions():
    """Each embedding should be 3072-dimensional."""
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = {"embeddings": [[0.5] * 3072, [0.6] * 3072]}
        client = GeminiClient()
        results = client.embed_texts(["a", "b"])

    for vec in results:
        assert len(vec) == 3072
