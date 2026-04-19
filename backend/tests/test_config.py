"""
test_config.py

Tests that verify the application settings loaded from the environment are correct and complete.

Role in project:
    Test suite — verifies the behaviour of backend.core.config. Run with:
    pytest tests/test_config.py -v

Coverage:
    - Anthropic, Gemini, and Pinecone API keys are present and correctly formatted
    - Claude model name, max_tokens, and temperature match expected defaults
    - Gemini embedding model name and vector dimension are correctly set
    - Document chunking parameters (section tokens, row tokens, overlap) match expected defaults
    - Retrieval parameters (top_k, MMR lambda, MMR fetch_k) match expected defaults
    - get_settings() is cached and returns the same instance on repeated calls
    - Empty OS env vars (e.g. Claude Code's ANTHROPIC_API_KEY="") do not shadow .env values
    - Non-empty OS env vars still override .env (standard pydantic-settings precedence preserved)
"""

import pytest
from backend.core.config import get_settings


def test_settings_loads_anthropic_key():
    settings = get_settings()
    assert settings.anthropic_api_key.get_secret_value() != ""
    assert settings.anthropic_api_key.get_secret_value().startswith("sk-ant-")


def test_settings_loads_gemini_key():
    settings = get_settings()
    assert settings.gemini_api_key.get_secret_value() != ""


def test_settings_loads_pinecone_key():
    settings = get_settings()
    assert settings.pinecone_api_key.get_secret_value() != ""
    assert settings.pinecone_index_name == "finsight-index"


def test_settings_claude_defaults():
    settings = get_settings()
    assert settings.claude_model == "claude-sonnet-4-6"
    assert settings.claude_max_tokens == 4096
    assert settings.claude_temperature == 0.2


def test_settings_embedding_defaults():
    settings = get_settings()
    assert settings.gemini_embed_model == "models/gemini-embedding-001"
    assert settings.gemini_embed_dimension == 3072


def test_settings_chunking_defaults():
    settings = get_settings()
    assert settings.section_chunk_tokens == 512
    assert settings.row_chunk_tokens == 128
    assert settings.chunk_overlap_tokens == 64


def test_settings_retrieval_defaults():
    settings = get_settings()
    assert settings.default_top_k == 5
    assert settings.mmr_lambda == 0.5
    assert settings.mmr_fetch_k == 20


def test_get_settings_is_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


# ─── Regression tests for Claude Code env-shadow (fixed 2026-04-19) ───────────
#
# Pydantic-settings precedence is OS env > .env file. When Claude Code (or any
# parent process) exports a sensitive var as an empty string, the empty string
# shadows the real value in backend/.env and the backend fails to start with
# "AssertionError: ANTHROPIC_API_KEY is not set in .env". get_settings() must
# strip empty sensitive vars from os.environ before constructing Settings.

def test_empty_anthropic_env_does_not_shadow_dotenv(monkeypatch):
    """Empty ANTHROPIC_API_KEY in os.environ must fall through to .env."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.anthropic_api_key.get_secret_value() != "", (
        "empty ANTHROPIC_API_KEY in os.environ should not shadow the .env value"
    )
    assert settings.anthropic_api_key.get_secret_value().startswith("sk-ant-")


def test_empty_gemini_env_does_not_shadow_dotenv(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.gemini_api_key.get_secret_value() != ""


def test_empty_pinecone_env_does_not_shadow_dotenv(monkeypatch):
    monkeypatch.setenv("PINECONE_API_KEY", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.pinecone_api_key.get_secret_value() != ""


def test_non_empty_env_still_overrides_dotenv(monkeypatch):
    """
    Guardrail: the fix must only strip *empty* overrides, not all overrides.
    Real non-empty env vars should still win over .env so production
    deployments (where secrets come from a secret manager injected via env)
    continue to work.
    """
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-override-for-test")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.claude_model == "claude-opus-override-for-test"
