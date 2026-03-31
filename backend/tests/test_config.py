import pytest
from backend.core.config import get_settings


def test_settings_loads_anthropic_key():
    settings = get_settings()
    assert settings.anthropic_api_key != ""
    assert settings.anthropic_api_key.startswith("sk-ant-")


def test_settings_loads_gemini_key():
    settings = get_settings()
    assert settings.gemini_api_key != ""


def test_settings_loads_pinecone_key():
    settings = get_settings()
    assert settings.pinecone_api_key != ""
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
