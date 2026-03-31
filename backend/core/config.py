from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Anthropic Claude ──────────────────────────────────────────────────────
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 4096
    claude_temperature: float = 0.2

    # ── Google Gemini Embeddings ──────────────────────────────────────────────
    google_api_key: str
    gemini_api_key: str
    gemini_embed_model: str = "models/gemini-embedding-001"
    gemini_embed_dimension: int = 3072

    # ── Pinecone Vector Store ─────────────────────────────────────────────────
    pinecone_api_key: str
    pinecone_index_name: str = "finsight-index"
    pinecone_namespace: str = "default"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # ── Chunking Parameters ───────────────────────────────────────────────────
    section_chunk_tokens: int = 512
    row_chunk_tokens: int = 128
    chunk_overlap_tokens: int = 64

    # ── Retrieval ─────────────────────────────────────────────────────────────
    default_top_k: int = 5
    mmr_lambda: float = 0.5
    mmr_fetch_k: int = 20

    # ── Output Paths ─────────────────────────────────────────────────────────
    output_dir: str = "data/outputs"
    temp_dir: str = "data/tmp"
    upload_dir: str = "data/uploads"

    # ── Additional API Keys ───────────────────────────────────────────────────
    openai_api_key: str = ""
    groq_api_key: str = ""
    grok_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
