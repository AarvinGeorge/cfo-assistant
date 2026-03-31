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
        return [self.embed_text(t, task_type=task_type) for t in texts]
