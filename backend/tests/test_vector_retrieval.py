"""Tests for backend.skills.vector_retrieval."""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass, field
from typing import Dict, Any

from backend.skills.vector_retrieval import (
    RetrievedChunk,
    embed_and_upsert,
    semantic_search,
    mmr_rerank,
    format_retrieved_context,
    _cosine_similarity,
    _cosine_similarity_batch,
)
from backend.skills.document_ingestion import Chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id: str, text: str, token_count: int = 50, **meta) -> Chunk:
    return Chunk(chunk_id=chunk_id, text=text, token_count=token_count, metadata=meta)


def _mock_gemini():
    client = MagicMock()
    # Default: return 4-d vectors
    client.embed_texts.return_value = [[0.1, 0.2, 0.3, 0.4]]
    client.embed_query.return_value = [0.1, 0.2, 0.3, 0.4]
    return client


def _mock_store():
    store = MagicMock()
    store.namespace = "test-ns"
    store.index = MagicMock()
    return store


# ---------------------------------------------------------------------------
# embed_and_upsert tests
# ---------------------------------------------------------------------------

class TestEmbedAndUpsert:
    def test_basic_upsert(self):
        """Verify records are formatted correctly and upsert is called."""
        chunks = [
            _make_chunk("c1", "Hello world", 10, doc_id="d1", doc_name="test.pdf"),
            _make_chunk("c2", "Foo bar", 8, doc_id="d1", doc_name="test.pdf"),
        ]
        client = _mock_gemini()
        client.embed_texts.return_value = [[0.1, 0.2], [0.3, 0.4]]
        store = _mock_store()

        result = embed_and_upsert(chunks, gemini_client=client, store=store)

        assert result["upserted_count"] == 2
        assert result["doc_id"] == "d1"

        # Verify upsert was called once (< 100 chunks)
        store.index.upsert.assert_called_once()
        upsert_call = store.index.upsert.call_args
        vectors = upsert_call.kwargs["vectors"]
        assert len(vectors) == 2
        assert vectors[0]["id"] == "c1"
        assert vectors[0]["values"] == [0.1, 0.2]
        assert vectors[0]["metadata"]["text"] == "Hello world"
        assert vectors[0]["metadata"]["doc_id"] == "d1"
        assert vectors[0]["metadata"]["token_count"] == 10
        assert upsert_call.kwargs["namespace"] == "test-ns"

    def test_empty_chunks(self):
        """Empty chunks list returns zero count."""
        result = embed_and_upsert([])
        assert result == {"upserted_count": 0, "doc_id": None}

    def test_batching_150_chunks(self):
        """150 chunks should produce 2 upsert calls (batches of 100)."""
        chunks = [_make_chunk(f"c{i}", f"text {i}", 5, doc_id="d1") for i in range(150)]
        client = _mock_gemini()
        client.embed_texts.return_value = [[0.1, 0.2]] * 150
        store = _mock_store()

        result = embed_and_upsert(chunks, gemini_client=client, store=store)

        assert result["upserted_count"] == 150
        assert store.index.upsert.call_count == 2
        # First batch: 100, second batch: 50
        first_call_vectors = store.index.upsert.call_args_list[0].kwargs["vectors"]
        second_call_vectors = store.index.upsert.call_args_list[1].kwargs["vectors"]
        assert len(first_call_vectors) == 100
        assert len(second_call_vectors) == 50


# ---------------------------------------------------------------------------
# semantic_search tests
# ---------------------------------------------------------------------------

class TestSemanticSearch:
    @patch("backend.skills.vector_retrieval.get_settings")
    def test_basic_search(self, mock_settings):
        """Verify RetrievedChunk objects returned with text extracted from metadata."""
        mock_settings.return_value = MagicMock(default_top_k=5)
        client = _mock_gemini()
        client.embed_query.return_value = [0.1, 0.2, 0.3]
        store = _mock_store()
        store.index.query.return_value = {
            "matches": [
                {
                    "id": "c1",
                    "score": 0.95,
                    "metadata": {
                        "text": "Revenue grew 10%",
                        "token_count": 20,
                        "doc_name": "10-K.pdf",
                        "section": "Revenue",
                        "page": 5,
                    },
                },
                {
                    "id": "c2",
                    "score": 0.88,
                    "metadata": {
                        "text": "Net income declined",
                        "token_count": 15,
                        "doc_name": "10-K.pdf",
                        "section": "Income",
                        "page": 8,
                    },
                },
            ]
        }

        results = semantic_search("revenue growth", gemini_client=client, store=store)

        assert len(results) == 2
        assert isinstance(results[0], RetrievedChunk)
        assert results[0].chunk_id == "c1"
        assert results[0].text == "Revenue grew 10%"
        assert results[0].score == 0.95
        # text and token_count should be removed from metadata
        assert "text" not in results[0].metadata
        assert "token_count" not in results[0].metadata
        assert results[0].metadata["doc_name"] == "10-K.pdf"

        # Verify query call
        store.index.query.assert_called_once_with(
            vector=[0.1, 0.2, 0.3],
            top_k=5,
            include_metadata=True,
            namespace="test-ns",
            filter=None,
        )

    @patch("backend.skills.vector_retrieval.get_settings")
    def test_search_with_filter(self, mock_settings):
        """Verify filter is passed to index.query."""
        mock_settings.return_value = MagicMock(default_top_k=5)
        client = _mock_gemini()
        store = _mock_store()
        store.index.query.return_value = {"matches": []}

        filter_dict = {"doc_type": "10-K"}
        semantic_search("test", filter_dict=filter_dict, gemini_client=client, store=store)

        call_kwargs = store.index.query.call_args.kwargs
        assert call_kwargs["filter"] == {"doc_type": "10-K"}


# ---------------------------------------------------------------------------
# mmr_rerank tests
# ---------------------------------------------------------------------------

class TestMMRRerank:
    @patch("backend.skills.vector_retrieval.get_settings")
    def test_diverse_selection(self, mock_settings):
        """MMR should select diverse results, not just top-scoring ones."""
        mock_settings.return_value = MagicMock(default_top_k=2, mmr_lambda=0.5)

        # Create candidates: c0 and c1 are very similar, c2 is different
        candidates = [
            RetrievedChunk(chunk_id="c0", text="A", score=0.95, metadata={}),
            RetrievedChunk(chunk_id="c1", text="B", score=0.90, metadata={}),
            RetrievedChunk(chunk_id="c2", text="C", score=0.85, metadata={}),
        ]

        client = _mock_gemini()
        # Query vector
        query_vec = [1.0, 0.0, 0.0, 0.0]
        client.embed_query.return_value = query_vec
        # c0 and c1 are nearly identical and close to query; c2 is orthogonal
        client.embed_texts.return_value = [
            [0.95, 0.05, 0.0, 0.0],   # c0: very similar to query
            [0.93, 0.07, 0.0, 0.0],   # c1: very similar to c0 and query
            [0.1, 0.0, 0.9, 0.0],     # c2: different direction
        ]

        result = mmr_rerank("test query", candidates, top_k=2, gemini_client=client)

        assert len(result) == 2
        # First pick should be c0 (highest relevance)
        assert result[0].chunk_id == "c0"
        # Second pick should be c2 (diverse) rather than c1 (redundant)
        assert result[1].chunk_id == "c2"

    @patch("backend.skills.vector_retrieval.get_settings")
    def test_fewer_candidates_than_top_k(self, mock_settings):
        """When fewer candidates than top_k, return all candidates."""
        mock_settings.return_value = MagicMock(default_top_k=10, mmr_lambda=0.5)

        candidates = [
            RetrievedChunk(chunk_id="c0", text="A", score=0.9, metadata={}),
            RetrievedChunk(chunk_id="c1", text="B", score=0.8, metadata={}),
        ]

        result = mmr_rerank("test", candidates, top_k=10)
        assert len(result) == 2
        assert result[0].chunk_id == "c0"
        assert result[1].chunk_id == "c1"


# ---------------------------------------------------------------------------
# format_retrieved_context tests
# ---------------------------------------------------------------------------

class TestFormatRetrievedContext:
    def test_format_with_chunks(self):
        """Verify formatted output includes source citations."""
        chunks = [
            RetrievedChunk(
                chunk_id="c1",
                text="Revenue grew 10%.",
                score=0.95,
                metadata={"doc_name": "AAPL-10K.pdf", "section": "Revenue", "page": 5},
            ),
            RetrievedChunk(
                chunk_id="c2",
                text="Net income was $50B.",
                score=0.88,
                metadata={"doc_name": "AAPL-10K.pdf", "section": "Income", "page": 12},
            ),
        ]

        output = format_retrieved_context(chunks)

        assert "--- Context 1" in output
        assert "--- Context 2" in output
        assert "[Source: AAPL-10K.pdf, Revenue, p.5]" in output
        assert "[Source: AAPL-10K.pdf, Income, p.12]" in output
        assert "Revenue grew 10%." in output
        assert "Net income was $50B." in output

    def test_format_empty_list(self):
        """Empty list returns sentinel string."""
        assert format_retrieved_context([]) == "No relevant context found."

    def test_format_missing_metadata(self):
        """Missing metadata fields fall back to defaults."""
        chunks = [RetrievedChunk(chunk_id="c1", text="Some text", score=0.9, metadata={})]
        output = format_retrieved_context(chunks)
        assert "[Source: unknown, unknown, p.?]" in output


# ---------------------------------------------------------------------------
# _cosine_similarity tests
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = np.array([1.0, 2.0, 3.0])
        assert _cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 2.0])
        assert _cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# _cosine_similarity_batch tests
# ---------------------------------------------------------------------------

class TestCosineSimilarityBatch:
    def test_batch_matches_individual(self):
        query = np.array([1.0, 0.5, 0.0])
        candidates = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 0.5, 0.0],
        ])

        batch_result = _cosine_similarity_batch(query, candidates)

        for i in range(len(candidates)):
            individual = _cosine_similarity(query, candidates[i])
            assert batch_result[i] == pytest.approx(individual, abs=1e-7)

    def test_batch_zero_candidates(self):
        query = np.array([1.0, 0.0])
        candidates = np.array([[0.0, 0.0], [1.0, 0.0]])
        result = _cosine_similarity_batch(query, candidates)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(1.0)
