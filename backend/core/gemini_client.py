"""
gemini_client.py

Thin wrapper around the Google Gemini embedding API used to convert text into
high-dimensional vectors for semantic search.

Role in project:
    Infrastructure layer. Called by vector_retrieval.py to embed document
    chunks at ingest time and to embed user queries at search time. Never used
    for generation — Claude handles all reasoning.

Main parts:
    - GeminiClient: singleton wrapper that initialises the Gemini SDK and
      exposes embed_text(), embed_query(), and embed_texts() (batch).
      All methods use task-type hints (retrieval_document vs retrieval_query)
      to improve embedding quality for asymmetric search.
"""
from typing import List
import google.generativeai as genai
from backend.core.config import get_settings


class GeminiClient:
    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self.model = settings.gemini_embed_model
        self.dimension = settings.gemini_embed_dimension

    def embed_text(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        result = genai.embed_content(
            model=self.model,
            content=text,
            task_type=task_type,
        )
        return result["embedding"]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_text(text, task_type="retrieval_query")

    def embed_texts(self, texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
        """Embed multiple texts in a single API call using batch embedding."""
        result = genai.embed_content(
            model=self.model,
            content=texts,
            task_type=task_type,
        )
        return result["embeddings"]
