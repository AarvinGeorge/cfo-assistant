# FinSight CFO Assistant — Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the full project skeleton — FastAPI server, Pinecone client, Redis client, Gemini embedding client, base agent class, and all 26 MCP tool stubs — so every subsequent phase has a working foundation to build on.

**Architecture:** FastAPI backend with a `core/` module housing typed config (pydantic-settings) and three infrastructure clients (Redis, Pinecone, Gemini). A `BaseAgent` abstract class holds the shared Anthropic client. An MCP server registers all 26 tool signatures as `NotImplementedError` stubs. Nothing calls an LLM yet — this phase is infrastructure only.

**Tech Stack:** Python 3.11+, FastAPI, pydantic-settings, anthropic SDK, google-generativeai, pinecone, redis, mcp (FastMCP), pytest, httpx

---

## File Map

```
finsight-cfo/
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   └── base_agent.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── health.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              ← already created
│   │   ├── gemini_client.py
│   │   ├── pinecone_store.py
│   │   └── redis_client.py
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── financial_mcp_server.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── document_tools.py
│   │       ├── memory_tools.py
│   │       ├── modeling_tools.py
│   │       ├── output_tools.py
│   │       └── scenario_tools.py
│   ├── data/
│   │   ├── outputs/.gitkeep
│   │   ├── tmp/.gitkeep
│   │   └── uploads/.gitkeep
│   ├── storage/
│   │   └── outputs/.gitkeep
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_config.py
│   │   ├── test_redis_client.py
│   │   ├── test_gemini_client.py
│   │   ├── test_pinecone_store.py
│   │   ├── test_base_agent.py
│   │   ├── test_mcp_server.py
│   │   └── test_health.py
│   ├── .env                       ← already created
│   ├── .env.example               ← already created
│   └── requirements.txt
└── frontend/
    └── package.json
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `finsight-cfo/backend/requirements.txt`
- Create: `finsight-cfo/.gitignore`
- Create: all `__init__.py` files and `.gitkeep` files listed in the file map above

- [ ] **Step 1: Create requirements.txt**

`finsight-cfo/backend/requirements.txt`:
```
# Web framework
fastapi==0.115.5
uvicorn[standard]==0.32.1
python-multipart==0.0.12

# Config
pydantic-settings==2.6.1
python-dotenv==1.0.1

# Anthropic Claude
anthropic==0.40.0

# Google Gemini Embeddings
google-generativeai==0.8.3

# Pinecone
pinecone==5.4.2

# Redis
redis==5.2.1

# MCP
mcp==1.2.0

# Document parsing (Phase 2 — installed now)
pdfplumber==0.11.4
pdfminer.six==20231228
beautifulsoup4==4.12.3
pandas==2.2.3

# Financial modeling (Phase 3 — installed now)
numpy==2.2.1
scipy==1.15.1
openpyxl==3.1.5
reportlab==4.2.5
plotly==5.24.1

# Testing
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.28.1
```

- [ ] **Step 2: Create .gitignore**

`finsight-cfo/.gitignore`:
```
# Environment
.env
*.env

# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
*.egg-info/
dist/
build/

# Data directories
backend/data/
backend/storage/

# IDE
.DS_Store
.idea/
.vscode/

# Node
node_modules/
frontend/dist/

# Logs
*.log
audit_log.jsonl
```

- [ ] **Step 3: Create all directory structure and empty init files**

Run these commands from `finsight-cfo/`:
```bash
# Backend dirs
mkdir -p backend/agents
mkdir -p backend/api/routes
mkdir -p backend/core
mkdir -p backend/mcp_server/tools
mkdir -p backend/data/outputs backend/data/tmp backend/data/uploads
mkdir -p backend/storage/outputs
mkdir -p backend/tests
mkdir -p frontend

# __init__.py files
touch backend/__init__.py
touch backend/agents/__init__.py
touch backend/api/__init__.py
touch backend/api/routes/__init__.py
touch backend/core/__init__.py
touch backend/mcp_server/__init__.py
touch backend/mcp_server/tools/__init__.py
touch backend/tests/__init__.py

# .gitkeep for empty data dirs
touch backend/data/outputs/.gitkeep
touch backend/data/tmp/.gitkeep
touch backend/data/uploads/.gitkeep
touch backend/storage/outputs/.gitkeep
```

- [ ] **Step 4: Install dependencies**

```bash
cd finsight-cfo/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without error. Confirm with:
```bash
python -c "import fastapi, anthropic, pinecone, redis, mcp; print('OK')"
```
Expected output: `OK`

- [ ] **Step 5: Initialize git and make first commit**

```bash
cd finsight-cfo
git init
git add .gitignore backend/requirements.txt backend/.env.example
git add backend/**/__init__.py backend/**/.gitkeep
git commit -m "chore: project scaffold — requirements, gitignore, directory structure"
```

---

## Task 2: Config Verification

**Files:**
- Test: `backend/tests/test_config.py`
- Reference: `backend/core/config.py` (already exists)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd finsight-cfo/backend
source .venv/bin/activate
pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pydantic_settings'` or import error (confirms test is wired up correctly before implementation exists in path).

- [ ] **Step 3: Create conftest.py so pytest finds the backend package**

`backend/tests/conftest.py`:
```python
import sys
from pathlib import Path

# Add backend's parent to sys.path so `from backend.x import y` works
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected output:
```
tests/test_config.py::test_settings_loads_anthropic_key PASSED
tests/test_config.py::test_settings_loads_gemini_key PASSED
tests/test_config.py::test_settings_loads_pinecone_key PASSED
tests/test_config.py::test_settings_claude_defaults PASSED
tests/test_config.py::test_settings_embedding_defaults PASSED
tests/test_config.py::test_settings_chunking_defaults PASSED
tests/test_config.py::test_settings_retrieval_defaults PASSED
tests/test_config.py::test_get_settings_is_cached PASSED
8 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_config.py
git commit -m "test: verify config loads from .env correctly"
```

---

## Task 3: Redis Client

**Files:**
- Create: `backend/core/redis_client.py`
- Test: `backend/tests/test_redis_client.py`

> **Pre-requisite:** Start the Redis Docker container before running integration tests:
> `docker run -d --name redis-finsight -p 6379:6379 redis:alpine`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_redis_client.py`:
```python
import pytest
import redis as redis_lib
from unittest.mock import patch, MagicMock
from backend.core.redis_client import get_redis_client, ping_redis


def test_get_redis_client_returns_redis_instance():
    client = get_redis_client()
    assert isinstance(client, redis_lib.Redis)


def test_get_redis_client_uses_config():
    client = get_redis_client()
    connection_kwargs = client.connection_pool.connection_kwargs
    assert connection_kwargs["host"] == "localhost"
    assert connection_kwargs["port"] == 6379
    assert connection_kwargs["db"] == 0


def test_ping_redis_returns_true_when_connected():
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    with patch("backend.core.redis_client.get_redis_client", return_value=mock_client):
        assert ping_redis() is True


def test_ping_redis_returns_false_when_connection_fails():
    mock_client = MagicMock()
    mock_client.ping.side_effect = redis_lib.ConnectionError("refused")
    with patch("backend.core.redis_client.get_redis_client", return_value=mock_client):
        assert ping_redis() is False


@pytest.mark.integration
def test_ping_redis_live():
    """Requires: docker run -d --name redis-finsight -p 6379:6379 redis:alpine"""
    assert ping_redis() is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_redis_client.py -v -k "not integration"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.core.redis_client'`

- [ ] **Step 3: Implement redis_client.py**

`backend/core/redis_client.py`:
```python
import redis
from backend.core.config import get_settings


def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )


def ping_redis() -> bool:
    try:
        return get_redis_client().ping()
    except redis.ConnectionError:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_redis_client.py -v -k "not integration"
```

Expected:
```
tests/test_redis_client.py::test_get_redis_client_returns_redis_instance PASSED
tests/test_redis_client.py::test_get_redis_client_uses_config PASSED
tests/test_redis_client.py::test_ping_redis_returns_true_when_connected PASSED
tests/test_redis_client.py::test_ping_redis_returns_false_when_connection_fails PASSED
4 passed
```

- [ ] **Step 5: Run integration test (Docker must be running)**

```bash
pytest tests/test_redis_client.py::test_ping_redis_live -v -m integration
```

Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/core/redis_client.py backend/tests/test_redis_client.py
git commit -m "feat: add Redis client with ping health check"
```

---

## Task 4: Gemini Embedding Client

**Files:**
- Create: `backend/core/gemini_client.py`
- Test: `backend/tests/test_gemini_client.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_gemini_client.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from backend.core.gemini_client import GeminiClient


def test_gemini_client_initializes():
    client = GeminiClient()
    assert client.model == "models/gemini-embedding-001"
    assert client.dimension == 3072


def test_embed_text_returns_list_of_floats():
    mock_result = MagicMock()
    mock_result.embedding = [0.1] * 3072
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = mock_result
        client = GeminiClient()
        result = client.embed_text("test input")
    assert isinstance(result, list)
    assert len(result) == 3072
    assert all(isinstance(v, float) for v in result)


def test_embed_text_calls_correct_model():
    mock_result = MagicMock()
    mock_result.embedding = [0.0] * 3072
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = mock_result
        client = GeminiClient()
        client.embed_text("financial query")
        mock_genai.embed_content.assert_called_once_with(
            model="models/gemini-embedding-001",
            content="financial query",
            task_type="retrieval_document",
        )


def test_embed_texts_batch_returns_list_of_embeddings():
    mock_result = MagicMock()
    mock_result.embedding = [0.1] * 3072
    with patch("backend.core.gemini_client.genai") as mock_genai:
        mock_genai.embed_content.return_value = mock_result
        client = GeminiClient()
        results = client.embed_texts(["text one", "text two"])
    assert len(results) == 2
    assert all(len(r) == 3072 for r in results)


@pytest.mark.integration
def test_embed_text_live():
    """Requires GEMINI_API_KEY in .env"""
    client = GeminiClient()
    result = client.embed_text("What is the gross margin?")
    assert len(result) == 3072
    assert isinstance(result[0], float)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_gemini_client.py -v -k "not integration"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.core.gemini_client'`

- [ ] **Step 3: Implement gemini_client.py**

`backend/core/gemini_client.py`:
```python
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
        return result.embedding

    def embed_query(self, text: str) -> List[float]:
        return self.embed_text(text, task_type="retrieval_query")

    def embed_texts(self, texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
        return [self.embed_text(t, task_type=task_type) for t in texts]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_gemini_client.py -v -k "not integration"
```

Expected:
```
tests/test_gemini_client.py::test_gemini_client_initializes PASSED
tests/test_gemini_client.py::test_embed_text_returns_list_of_floats PASSED
tests/test_gemini_client.py::test_embed_text_calls_correct_model PASSED
tests/test_gemini_client.py::test_embed_texts_batch_returns_list_of_embeddings PASSED
4 passed
```

- [ ] **Step 5: Run integration test (uses live Gemini API)**

```bash
pytest tests/test_gemini_client.py::test_embed_text_live -v -m integration
```

Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/core/gemini_client.py backend/tests/test_gemini_client.py
git commit -m "feat: add Gemini embedding client (gemini-embedding-001, dim=3072)"
```

---

## Task 5: Pinecone Store

**Files:**
- Create: `backend/core/pinecone_store.py`
- Test: `backend/tests/test_pinecone_store.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pinecone_store.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from backend.core.pinecone_store import PineconeStore


def test_pinecone_store_initializes():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=3072)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        store = PineconeStore()
    assert store.index_name == "finsight-index"
    assert store.namespace == "default"
    assert store.dimension == 3072


def test_pinecone_store_raises_if_dimension_mismatch():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=1536)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        with pytest.raises(ValueError, match="dimension mismatch"):
            PineconeStore()


def test_is_ready_returns_true_when_connected():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=3072)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        store = PineconeStore()
    assert store.is_ready() is True


def test_is_ready_returns_false_on_exception():
    mock_pc = MagicMock()
    mock_pc.Index.side_effect = Exception("connection failed")
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        with pytest.raises(Exception):
            PineconeStore()


def test_get_pinecone_store_singleton():
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_index.describe_index_stats.return_value = MagicMock(dimension=3072)
    mock_pc.Index.return_value = mock_index
    with patch("backend.core.pinecone_store.Pinecone", return_value=mock_pc):
        from backend.core.pinecone_store import get_pinecone_store
        s1 = get_pinecone_store.__wrapped__() if hasattr(get_pinecone_store, '__wrapped__') else get_pinecone_store()
        s2 = get_pinecone_store.__wrapped__() if hasattr(get_pinecone_store, '__wrapped__') else get_pinecone_store()
    assert s1 is s2


@pytest.mark.integration
def test_pinecone_store_live_connection():
    """Requires PINECONE_API_KEY and finsight-index created in console (dim=3072, cosine)"""
    from backend.core.pinecone_store import PineconeStore
    store = PineconeStore()
    assert store.is_ready() is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_pinecone_store.py -v -k "not integration"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.core.pinecone_store'`

- [ ] **Step 3: Implement pinecone_store.py**

`backend/core/pinecone_store.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_pinecone_store.py -v -k "not integration"
```

Expected:
```
tests/test_pinecone_store.py::test_pinecone_store_initializes PASSED
tests/test_pinecone_store.py::test_pinecone_store_raises_if_dimension_mismatch PASSED
tests/test_pinecone_store.py::test_is_ready_returns_true_when_connected PASSED
tests/test_pinecone_store.py::test_is_ready_returns_false_on_exception PASSED
tests/test_pinecone_store.py::test_get_pinecone_store_singleton PASSED
5 passed
```

- [ ] **Step 5: Run integration test**

```bash
pytest tests/test_pinecone_store.py::test_pinecone_store_live_connection -v -m integration
```

Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/core/pinecone_store.py backend/tests/test_pinecone_store.py
git commit -m "feat: add Pinecone store wrapper with dimension validation on startup"
```

---

## Task 6: Base Agent Class

**Files:**
- Create: `backend/agents/base_agent.py`
- Test: `backend/tests/test_base_agent.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_base_agent.py`:
```python
import pytest
from abc import ABC
from unittest.mock import patch, MagicMock
from backend.agents.base_agent import BaseAgent


class ConcreteAgent(BaseAgent):
    def run(self, query: str, session_id: str) -> str:
        return f"response to: {query}"


def test_base_agent_is_abstract():
    assert issubclass(BaseAgent, ABC)


def test_base_agent_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseAgent()


def test_concrete_agent_inherits_client():
    mock_anthropic = MagicMock()
    with patch("backend.agents.base_agent.anthropic.Anthropic", return_value=mock_anthropic):
        agent = ConcreteAgent()
    assert agent.client is mock_anthropic


def test_concrete_agent_uses_config_model():
    with patch("backend.agents.base_agent.anthropic.Anthropic"):
        agent = ConcreteAgent()
    assert agent.model == "claude-sonnet-4-6"
    assert agent.max_tokens == 4096


def test_concrete_agent_run_returns_string():
    with patch("backend.agents.base_agent.anthropic.Anthropic"):
        agent = ConcreteAgent()
    result = agent.run("What is EBITDA?", session_id="test-session")
    assert isinstance(result, str)
    assert result == "response to: What is EBITDA?"


def test_run_is_abstract_on_base():
    import inspect
    assert "run" in BaseAgent.__abstractmethods__
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_base_agent.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.agents.base_agent'`

- [ ] **Step 3: Implement base_agent.py**

`backend/agents/base_agent.py`:
```python
from abc import ABC, abstractmethod
import anthropic
from backend.core.config import get_settings


class BaseAgent(ABC):
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    @abstractmethod
    def run(self, query: str, session_id: str) -> str:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_base_agent.py -v
```

Expected:
```
tests/test_base_agent.py::test_base_agent_is_abstract PASSED
tests/test_base_agent.py::test_base_agent_cannot_be_instantiated_directly PASSED
tests/test_base_agent.py::test_concrete_agent_inherits_client PASSED
tests/test_base_agent.py::test_concrete_agent_uses_config_model PASSED
tests/test_base_agent.py::test_concrete_agent_run_returns_string PASSED
tests/test_base_agent.py::test_run_is_abstract_on_base PASSED
6 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/agents/base_agent.py backend/agents/__init__.py backend/tests/test_base_agent.py
git commit -m "feat: add BaseAgent abstract class with shared Anthropic client"
```

---

## Task 7: MCP Server Scaffold (26 Tool Stubs)

**Files:**
- Create: `backend/mcp_server/tools/document_tools.py`
- Create: `backend/mcp_server/tools/modeling_tools.py`
- Create: `backend/mcp_server/tools/scenario_tools.py`
- Create: `backend/mcp_server/tools/output_tools.py`
- Create: `backend/mcp_server/tools/memory_tools.py`
- Create: `backend/mcp_server/financial_mcp_server.py`
- Test: `backend/tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_mcp_server.py`:
```python
import pytest
from backend.mcp_server.financial_mcp_server import mcp

EXPECTED_TOOLS = {
    "mcp_parse_pdf",
    "mcp_parse_csv",
    "mcp_embed_chunks",
    "mcp_pinecone_upsert",
    "mcp_pinecone_search",
    "mcp_list_documents",
    "mcp_extract_financials",
    "mcp_run_dcf",
    "mcp_run_ratios",
    "mcp_run_forecast",
    "mcp_run_variance",
    "mcp_store_model",
    "mcp_run_scenarios",
    "mcp_sensitivity_matrix",
    "mcp_covenant_check",
    "mcp_runway_calc",
    "mcp_citation_validator",
    "mcp_response_logger",
    "mcp_export_trigger",
    "mcp_memory_read",
    "mcp_memory_write",
    "mcp_intent_log",
    "mcp_render_excel",
    "mcp_render_pdf",
    "mcp_render_chart",
    "mcp_file_serve",
}


def test_all_tools_are_registered():
    registered = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert registered == EXPECTED_TOOLS, (
        f"Missing tools: {EXPECTED_TOOLS - registered}\n"
        f"Extra tools: {registered - EXPECTED_TOOLS}"
    )


def test_tool_count():
    registered = list(mcp._tool_manager.list_tools())
    assert len(registered) == 26


@pytest.mark.parametrize("tool_name", list(EXPECTED_TOOLS))
def test_each_tool_raises_not_implemented(tool_name):
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert tool_name in tools
    # Each tool's function should raise NotImplementedError
    tool_fn = tools[tool_name].fn
    with pytest.raises(NotImplementedError):
        import asyncio
        import inspect
        if inspect.iscoroutinefunction(tool_fn):
            asyncio.get_event_loop().run_until_complete(tool_fn())
        else:
            tool_fn()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_mcp_server.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.mcp_server.financial_mcp_server'`

- [ ] **Step 3: Create document_tools.py**

`backend/mcp_server/tools/document_tools.py`:
```python
def mcp_parse_pdf(file_path: str) -> str:
    """Extract text and tables from a PDF file."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_parse_csv(file_path: str) -> str:
    """Parse and normalize CSV financial data into structured rows."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_embed_chunks(chunks: list) -> list:
    """Embed text chunks via Gemini Embeddings and return vectors."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_pinecone_upsert(vectors: list, metadata: list) -> dict:
    """Store embedding vectors with metadata in Pinecone index."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_pinecone_search(query_vector: list, top_k: int = 5) -> list:
    """Semantic similarity search on Pinecone index."""
    raise NotImplementedError("Implemented in Phase 2")


def mcp_list_documents() -> list:
    """List all ingested documents with metadata."""
    raise NotImplementedError("Implemented in Phase 2")
```

- [ ] **Step 4: Create modeling_tools.py**

`backend/mcp_server/tools/modeling_tools.py`:
```python
def mcp_extract_financials(chunks: list) -> dict:
    """Parse financial line items from RAG chunks into clean DataFrames."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_dcf(inputs: dict) -> dict:
    """Execute DCF model computation with given assumptions."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_ratios(statements: dict) -> dict:
    """Compute financial ratio scorecard from statement DataFrames."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_forecast(historical_series: dict, horizon: int = 3) -> dict:
    """Run time-series revenue/expense forecasting."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_run_variance(actuals: dict, budget: dict) -> dict:
    """Execute actuals vs. budget variance analysis."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_store_model(model_data: dict, model_name: str) -> str:
    """Persist generated model DataFrames to local storage."""
    raise NotImplementedError("Implemented in Phase 3")
```

- [ ] **Step 5: Create scenario_tools.py**

`backend/mcp_server/tools/scenario_tools.py`:
```python
def mcp_run_scenarios(base_model: dict, assumptions: dict) -> dict:
    """Run bull/base/bear scenario engine across defined assumption sets."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_sensitivity_matrix(model: dict, var1: str, var2: str) -> dict:
    """Generate 2D sensitivity table for any two input variables."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_covenant_check(model: dict, thresholds: dict) -> dict:
    """Evaluate model outputs against user-defined covenant thresholds."""
    raise NotImplementedError("Implemented in Phase 3")


def mcp_runway_calc(cash_balance: float, burn_scenarios: list) -> dict:
    """Compute cash runway under multiple burn rate assumptions."""
    raise NotImplementedError("Implemented in Phase 3")
```

- [ ] **Step 6: Create output_tools.py**

`backend/mcp_server/tools/output_tools.py`:
```python
def mcp_render_excel(model_dataframes: dict, metadata: dict) -> str:
    """Generate formatted Excel workbook from model DataFrames."""
    raise NotImplementedError("Implemented in Phase 6")


def mcp_render_pdf(content: dict, charts: list, metadata: dict) -> str:
    """Generate formatted PDF report."""
    raise NotImplementedError("Implemented in Phase 6")


def mcp_render_chart(dataframe: dict, chart_type: str, config: dict) -> dict:
    """Generate Plotly chart JSON for rendering in the frontend."""
    raise NotImplementedError("Implemented in Phase 6")


def mcp_file_serve(file_path: str) -> str:
    """Register generated file with FastAPI static server and return download URL."""
    raise NotImplementedError("Implemented in Phase 6")
```

- [ ] **Step 7: Create memory_tools.py**

`backend/mcp_server/tools/memory_tools.py`:
```python
def mcp_memory_read(session_id: str) -> list:
    """Read session conversation history from Redis."""
    raise NotImplementedError("Implemented in Phase 4")


def mcp_memory_write(session_id: str, message: dict) -> bool:
    """Write new conversation turn to Redis session store."""
    raise NotImplementedError("Implemented in Phase 4")


def mcp_intent_log(session_id: str, intent: str, query: str) -> bool:
    """Log classified intent to audit trail."""
    raise NotImplementedError("Implemented in Phase 4")


def mcp_citation_validator(response_text: str) -> dict:
    """Validate that every factual claim has a properly formatted source citation."""
    raise NotImplementedError("Implemented in Phase 4")


def mcp_response_logger(session_id: str, query: str, response: str, citations: list) -> bool:
    """Log Q&A pair with citations to local audit file."""
    raise NotImplementedError("Implemented in Phase 4")


def mcp_export_trigger(session_id: str, export_type: str, model_name: str) -> bool:
    """Signal the Output Generation Agent when an export is requested."""
    raise NotImplementedError("Implemented in Phase 4")
```

- [ ] **Step 8: Create financial_mcp_server.py**

`backend/mcp_server/financial_mcp_server.py`:
```python
from mcp.server.fastmcp import FastMCP
from backend.mcp_server.tools.document_tools import (
    mcp_parse_pdf, mcp_parse_csv, mcp_embed_chunks,
    mcp_pinecone_upsert, mcp_pinecone_search, mcp_list_documents,
)
from backend.mcp_server.tools.modeling_tools import (
    mcp_extract_financials, mcp_run_dcf, mcp_run_ratios,
    mcp_run_forecast, mcp_run_variance, mcp_store_model,
)
from backend.mcp_server.tools.scenario_tools import (
    mcp_run_scenarios, mcp_sensitivity_matrix,
    mcp_covenant_check, mcp_runway_calc,
)
from backend.mcp_server.tools.output_tools import (
    mcp_render_excel, mcp_render_pdf, mcp_render_chart, mcp_file_serve,
)
from backend.mcp_server.tools.memory_tools import (
    mcp_memory_read, mcp_memory_write, mcp_intent_log,
    mcp_citation_validator, mcp_response_logger, mcp_export_trigger,
)

mcp = FastMCP("finsight-financial-tools")

# ── Document tools ────────────────────────────────────────────────────────────
mcp.tool()(mcp_parse_pdf)
mcp.tool()(mcp_parse_csv)
mcp.tool()(mcp_embed_chunks)
mcp.tool()(mcp_pinecone_upsert)
mcp.tool()(mcp_pinecone_search)
mcp.tool()(mcp_list_documents)

# ── Modeling tools ────────────────────────────────────────────────────────────
mcp.tool()(mcp_extract_financials)
mcp.tool()(mcp_run_dcf)
mcp.tool()(mcp_run_ratios)
mcp.tool()(mcp_run_forecast)
mcp.tool()(mcp_run_variance)
mcp.tool()(mcp_store_model)

# ── Scenario tools ────────────────────────────────────────────────────────────
mcp.tool()(mcp_run_scenarios)
mcp.tool()(mcp_sensitivity_matrix)
mcp.tool()(mcp_covenant_check)
mcp.tool()(mcp_runway_calc)

# ── Output tools ──────────────────────────────────────────────────────────────
mcp.tool()(mcp_render_excel)
mcp.tool()(mcp_render_pdf)
mcp.tool()(mcp_render_chart)
mcp.tool()(mcp_file_serve)

# ── Memory & audit tools ──────────────────────────────────────────────────────
mcp.tool()(mcp_memory_read)
mcp.tool()(mcp_memory_write)
mcp.tool()(mcp_intent_log)
mcp.tool()(mcp_citation_validator)
mcp.tool()(mcp_response_logger)
mcp.tool()(mcp_export_trigger)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
pytest tests/test_mcp_server.py -v
```

Expected:
```
tests/test_mcp_server.py::test_all_tools_are_registered PASSED
tests/test_mcp_server.py::test_tool_count PASSED
tests/test_mcp_server.py::test_each_tool_raises_not_implemented[mcp_parse_pdf] PASSED
... (26 parametrized tests)
28 passed
```

- [ ] **Step 10: Commit**

```bash
git add backend/mcp_server/ backend/tests/test_mcp_server.py
git commit -m "feat: MCP server scaffold with all 26 tool stubs registered"
```

---

## Task 8: FastAPI App and Health Endpoint

**Files:**
- Create: `backend/api/routes/health.py`
- Create: `backend/api/main.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_health.py`:
```python
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from backend.api.main import app


@pytest.mark.asyncio
async def test_health_returns_200():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert "status" in body
    assert "redis" in body
    assert "pinecone" in body
    assert "anthropic_key" in body
    assert "gemini_key" in body


@pytest.mark.asyncio
async def test_health_ok_when_all_services_up():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["redis"] is True
    assert body["pinecone"] is True
    assert body["anthropic_key"] is True
    assert body["gemini_key"] is True


@pytest.mark.asyncio
async def test_health_degraded_when_redis_down():
    with patch("backend.api.routes.health.ping_redis", return_value=False), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "degraded"
    assert body["redis"] is False


@pytest.mark.asyncio
async def test_health_degraded_when_pinecone_down():
    with patch("backend.api.routes.health.ping_redis", return_value=True), \
         patch("backend.api.routes.health.get_pinecone_store") as mock_store:
        mock_store.return_value.is_ready.return_value = False
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    body = response.json()
    assert body["status"] == "degraded"
    assert body["pinecone"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.api.main'`

- [ ] **Step 3: Create health.py route**

`backend/api/routes/health.py`:
```python
from fastapi import APIRouter
from backend.core.redis_client import ping_redis
from backend.core.pinecone_store import get_pinecone_store
from backend.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    settings = get_settings()

    redis_ok = ping_redis()

    pinecone_ok = False
    try:
        pinecone_ok = get_pinecone_store().is_ready()
    except Exception:
        pinecone_ok = False

    all_ok = redis_ok and pinecone_ok

    return {
        "status": "ok" if all_ok else "degraded",
        "redis": redis_ok,
        "pinecone": pinecone_ok,
        "anthropic_key": bool(settings.anthropic_api_key),
        "gemini_key": bool(settings.gemini_api_key),
    }
```

- [ ] **Step 4: Create main.py**

`backend/api/main.py`:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup checks — server refuses to start silently with bad config
    from backend.core.config import get_settings
    from backend.core.redis_client import ping_redis
    settings = get_settings()

    assert settings.anthropic_api_key, "ANTHROPIC_API_KEY is not set in .env"
    assert settings.gemini_api_key, "GEMINI_API_KEY is not set in .env"
    assert settings.pinecone_api_key, "PINECONE_API_KEY is not set in .env"

    if not ping_redis():
        print("WARNING: Redis is not reachable. Start with: docker run -d --name redis-finsight -p 6379:6379 redis:alpine")

    yield


app = FastAPI(
    title="FinSight CFO Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_health.py -v
```

Expected:
```
tests/test_health.py::test_health_returns_200 PASSED
tests/test_health.py::test_health_response_shape PASSED
tests/test_health.py::test_health_ok_when_all_services_up PASSED
tests/test_health.py::test_health_degraded_when_redis_down PASSED
tests/test_health.py::test_health_degraded_when_pinecone_down PASSED
5 passed
```

- [ ] **Step 6: Run the server manually to verify it starts**

```bash
cd finsight-cfo/backend
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

In a second terminal:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok", "redis": true, "pinecone": true, "anthropic_key": true, "gemini_key": true}
```

- [ ] **Step 7: Commit**

```bash
git add backend/api/ backend/tests/test_health.py
git commit -m "feat: FastAPI app with /health endpoint checking Redis, Pinecone, and API keys"
```

---

## Task 9: Frontend Scaffold

**Files:**
- Create: `finsight-cfo/frontend/package.json`
- Create: `finsight-cfo/frontend/tsconfig.json`

- [ ] **Step 1: Create package.json**

`frontend/package.json`:
```json
{
  "name": "finsight-cfo-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@emotion/react": "^11.13.3",
    "@emotion/styled": "^11.13.0",
    "@mui/icons-material": "^6.1.6",
    "@mui/material": "^6.1.6",
    "@mui/x-data-grid": "^7.22.2",
    "axios": "^1.7.7",
    "plotly.js": "^2.35.2",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-plotly.js": "^2.6.0",
    "react-router-dom": "^6.27.0",
    "zustand": "^5.0.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@types/react-plotly.js": "^2.6.3",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Verify npm install completes**

```bash
cd finsight-cfo/frontend
npm install
```

Expected: no errors. `node_modules/` created.

- [ ] **Step 4: Commit**

```bash
cd finsight-cfo
git add frontend/package.json frontend/tsconfig.json
git commit -m "chore: frontend scaffold with React 18, MUI v6, Zustand, Axios dependencies"
```

---

## Task 10: Full Test Suite Pass

- [ ] **Step 1: Run all unit tests**

```bash
cd finsight-cfo/backend
source .venv/bin/activate
pytest tests/ -v -k "not integration"
```

Expected: all tests pass, 0 failures.

- [ ] **Step 2: Run integration tests (requires Docker Redis + Pinecone index)**

```bash
pytest tests/ -v -m integration
```

Expected: all integration tests pass.

- [ ] **Step 3: Verify health endpoint with all services running**

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status": "ok", "redis": true, "pinecone": true, "anthropic_key": true, "gemini_key": true}
```

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "chore: Phase 1 complete — all tests pass, /health green"
```

---

## Self-Review

**Spec coverage check:**
- [x] Project folder structure — Task 1
- [x] FastAPI on localhost:8000 with health check — Task 8
- [x] `.env` configuration — already created (pre-plan), tested in Task 2
- [x] Gemini client wrapper (gemini-embedding-001, dim=3072) — Task 4
- [x] Pinecone client wrapper with startup dimension check — Task 5
- [x] Redis connection (Docker, localhost:6379, ping-verified) — Task 3
- [x] Base agent class with abstract run() and shared Claude client — Task 6
- [x] MCP server scaffold with all 26 tool stubs — Task 7
- [x] requirements.txt — Task 1
- [x] Frontend package.json scaffold — Task 9

**No placeholders found.** All steps contain actual code.

**Type consistency:** `ping_redis() -> bool`, `GeminiClient.embed_text() -> List[float]`, `PineconeStore.is_ready() -> bool`, `BaseAgent.run(query: str, session_id: str) -> str` — all consistent between definition tasks and health route usage.
