import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from backend.core.config import get_settings
from backend.core.gemini_client import GeminiClient
from backend.core.pinecone_store import get_pinecone_store


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


def embed_and_upsert(chunks: list, gemini_client: GeminiClient = None, store=None) -> dict:
    """
    Embed chunks via Gemini and upsert to Pinecone.

    Args:
        chunks: List of Chunk objects (from document_ingestion.py)
        gemini_client: GeminiClient instance (creates new if None)
        store: PineconeStore instance (uses singleton if None)

    Returns:
        {"upserted_count": N, "doc_id": "..."}
    """
    if not chunks:
        return {"upserted_count": 0, "doc_id": None}

    if gemini_client is None:
        gemini_client = GeminiClient()
    if store is None:
        store = get_pinecone_store()

    # Embed all chunk texts
    texts = [c.text for c in chunks]
    vectors = gemini_client.embed_texts(texts)

    # Prepare Pinecone upsert records
    records = []
    for chunk, vector in zip(chunks, vectors):
        # Pinecone metadata values must be strings, numbers, booleans, or lists of strings
        metadata = {k: v for k, v in chunk.metadata.items()}
        metadata["text"] = chunk.text  # store text in metadata for retrieval
        metadata["token_count"] = chunk.token_count
        records.append({
            "id": chunk.chunk_id,
            "values": vector,
            "metadata": metadata,
        })

    # Upsert in batches of 100 (Pinecone limit)
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        store.index.upsert(vectors=batch, namespace=store.namespace)

    doc_id = chunks[0].metadata.get("doc_id") if chunks else None
    return {"upserted_count": len(records), "doc_id": doc_id}


def semantic_search(
    query: str,
    top_k: int = None,
    filter_dict: Optional[Dict[str, Any]] = None,
    gemini_client: GeminiClient = None,
    store=None,
) -> List[RetrievedChunk]:
    """
    Embed the query and run cosine similarity search against Pinecone.

    Args:
        query: Natural language query
        top_k: Number of results (defaults to config.default_top_k)
        filter_dict: Optional Pinecone metadata filter (e.g., {"doc_type": "10-K"})
        gemini_client: GeminiClient instance
        store: PineconeStore instance

    Returns:
        List of RetrievedChunk objects sorted by score descending
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.default_top_k
    if gemini_client is None:
        gemini_client = GeminiClient()
    if store is None:
        store = get_pinecone_store()

    query_vector = gemini_client.embed_query(query)

    results = store.index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
        namespace=store.namespace,
        filter=filter_dict,
    )

    retrieved = []
    for match in results.get("matches", []):
        metadata = match.get("metadata", {})
        text = metadata.pop("text", "")
        metadata.pop("token_count", 0)
        retrieved.append(RetrievedChunk(
            chunk_id=match["id"],
            text=text,
            score=match["score"],
            metadata=metadata,
        ))

    return retrieved


def mmr_rerank(
    query: str,
    candidates: List[RetrievedChunk],
    top_k: int = None,
    lambda_param: float = None,
    gemini_client: GeminiClient = None,
) -> List[RetrievedChunk]:
    """
    Apply Maximal Marginal Relevance to balance relevance and diversity.

    MMR = lambda * sim(query, doc) - (1 - lambda) * max(sim(doc, selected_docs))

    Args:
        query: The original query
        candidates: Retrieved chunks to rerank
        top_k: Number of results after reranking
        lambda_param: Balance factor (1.0 = pure relevance, 0.0 = pure diversity)
        gemini_client: For embedding

    Returns:
        Reranked list of RetrievedChunk
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.default_top_k
    if lambda_param is None:
        lambda_param = settings.mmr_lambda

    if len(candidates) <= top_k:
        return candidates

    if gemini_client is None:
        gemini_client = GeminiClient()

    # Embed query and all candidate texts
    query_vec = np.array(gemini_client.embed_query(query))
    candidate_vecs = np.array(gemini_client.embed_texts([c.text for c in candidates]))

    # Compute query-candidate similarities
    query_sims = _cosine_similarity_batch(query_vec, candidate_vecs)

    # Greedy MMR selection
    selected_indices = []
    remaining_indices = list(range(len(candidates)))

    for _ in range(top_k):
        if not remaining_indices:
            break

        best_idx = None
        best_score = float("-inf")

        for idx in remaining_indices:
            relevance = query_sims[idx]

            # Max similarity to already selected
            if selected_indices:
                selected_vecs = candidate_vecs[selected_indices]
                redundancy = max(
                    _cosine_similarity(candidate_vecs[idx], sv)
                    for sv in selected_vecs
                )
            else:
                redundancy = 0.0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * redundancy

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected_indices.append(best_idx)
        remaining_indices.remove(best_idx)

    return [candidates[i] for i in selected_indices]


def format_retrieved_context(chunks: List[RetrievedChunk]) -> str:
    """
    Format retrieved chunks into a structured context block for injection
    into Claude prompts, including source citations.
    """
    if not chunks:
        return "No relevant context found."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.metadata
        source = (
            f"[Source: {meta.get('doc_name', 'unknown')}, "
            f"{meta.get('section', 'unknown')}, "
            f"p.{meta.get('page', '?')}]"
        )
        parts.append(f"--- Context {i} {source} ---\n{chunk.text}")

    return "\n\n".join(parts)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _cosine_similarity_batch(query: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a query and batch of candidates."""
    dot_products = candidates @ query
    norms = np.linalg.norm(candidates, axis=1) * np.linalg.norm(query)
    norms = np.where(norms == 0, 1, norms)
    return dot_products / norms
