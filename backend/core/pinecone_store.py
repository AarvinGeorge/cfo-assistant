from functools import lru_cache
from pinecone import Pinecone
from backend.core.config import get_settings


class PineconeStore:
    def __init__(self):
        settings = get_settings()
        self.index_name = settings.pinecone_index_name
        self.namespace = settings.pinecone_namespace
        self.dimension = settings.gemini_embed_dimension

        pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index = pc.Index(self.index_name)

        stats = self._index.describe_index_stats()
        if stats.dimension != self.dimension:
            raise ValueError(
                f"Pinecone index dimension mismatch: "
                f"expected {self.dimension}, got {stats.dimension}. "
                f"Re-create the index with dimension={self.dimension}."
            )

    @property
    def index(self):
        return self._index

    def is_ready(self) -> bool:
        try:
            self._index.describe_index_stats()
            return True
        except Exception:
            return False


@lru_cache
def get_pinecone_store() -> PineconeStore:
    return PineconeStore()
