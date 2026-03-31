import pytest
from unittest.mock import patch, MagicMock
from backend.core.gemini_client import GeminiClient


def test_gemini_client_initializes():
    client = GeminiClient()
    assert client.model == "models/gemini-embedding-001"
    assert client.dimension == 3072


def test_embed_text_returns_list_of_floats():
    mock_result = {"embedding": [0.1] * 3072}
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = mock_result
        client = GeminiClient()
        result = client.embed_text("test input")
    assert isinstance(result, list)
    assert len(result) == 3072
    assert all(isinstance(v, float) for v in result)


def test_embed_text_calls_correct_model():
    mock_result = {"embedding": [0.0] * 3072}
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = mock_result
        client = GeminiClient()
        client.embed_text("financial query")
        mock_genai.embed_content.assert_called_once_with(
            model="models/gemini-embedding-001",
            content="financial query",
            task_type="retrieval_document",
        )


def test_embed_texts_batch_returns_list_of_embeddings():
    mock_result = {"embeddings": [[0.1] * 3072, [0.1] * 3072]}
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = mock_result
        client = GeminiClient()
        results = client.embed_texts(["text one", "text two"])
    assert len(results) == 2
    assert all(len(r) == 3072 for r in results)


@pytest.mark.integration
def test_embed_text_live():
    """Requires GEMINI_API_KEY in .env"""
    client = GeminiClient()
    result = client.embed_text("What is the gross margin?")
    assert len(result) == 3072
    assert isinstance(result[0], float)
