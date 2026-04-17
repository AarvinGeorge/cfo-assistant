"""
pinecone_store.py

Singleton accessor for the Pinecone serverless vector index that stores all
document chunk embeddings.

Role in project:
    Infrastructure layer. Owned by the vector retrieval skill and called
    during both document ingest (upsert) and chat query (search). Validates
    index dimension on startup to catch misconfiguration early.

Main parts:
    - PineconeStore: initialises the Pinecone client, resolves the index by
      name from config, and exposes the raw index handle for upsert/query ops.
    - get_pinecone_store(): module-level singleton factory that creates the
      store once and returns the same instance on every subsequent call.
"""
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
