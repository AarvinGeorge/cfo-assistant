"""
config.py

Centralised configuration for FinSight using pydantic-settings.

Role in project:
    Foundation layer. Loaded once at startup by every other backend module via
    get_settings(). Reads all secrets and tuneable parameters from the .env
    file so no values are ever hardcoded.

Main parts:
    - _SENSITIVE_ENV_KEYS: frozenset of API-key env var names that must never
      be shadowed by an empty OS env var.
    - _strip_empty_shadow_env(): deletes empty sensitive vars from os.environ
      before Settings reads them, so .env values win when a parent process
      (e.g. Claude Code) exports an empty string like `ANTHROPIC_API_KEY=""`.
    - Settings: pydantic-settings model declaring typed env vars. All API keys
      are typed as SecretStr so assertion failures, log dumps, and repr() calls
      never print the real value — access via `.get_secret_value()` at the
      point of use (SDK client construction).
    - get_settings(): cached factory that strips empty shadow env vars and
      constructs the singleton Settings instance reused across the app.
"""
import os
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Every sensitive key that must not be shadowed by an empty OS env var.
# pydantic-settings is case-insensitive for env var matching, so we uppercase.
_SENSITIVE_ENV_KEYS = frozenset({
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "PINECONE_API_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "GROK_API_KEY",
})


def _strip_empty_shadow_env() -> None:
    """Remove empty-string sensitive env vars from os.environ.

    pydantic-settings precedence is OS env > .env file. When a parent process
    exports a key as "" (Claude Code does this for security hygiene), the
    empty string wins over the real value in .env and the backend fails to
    start. Stripping those empty entries restores the intuitive fallback
    behaviour while preserving normal override semantics for any non-empty
    env value (e.g. production deployments injecting real secrets).
    """
    for key in list(os.environ.keys()):
        if key.upper() in _SENSITIVE_ENV_KEYS and os.environ.get(key) == "":
            del os.environ[key]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Anthropic Claude ──────────────────────────────────────────────────────
    anthropic_api_key: SecretStr
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 4096
    claude_temperature: float = 0.2

    # ── Google Gemini Embeddings ──────────────────────────────────────────────
    google_api_key: SecretStr
    gemini_api_key: SecretStr
    gemini_embed_model: str = "models/gemini-embedding-001"
    gemini_embed_dimension: int = 3072

    # ── Pinecone Vector Store ─────────────────────────────────────────────────
    pinecone_api_key: SecretStr
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
    openai_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    grok_api_key: SecretStr = SecretStr("")


@lru_cache
def get_settings() -> Settings:
    _strip_empty_shadow_env()
    return Settings()
