# File Headers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a descriptive file-level header to every source file in the project capturing what the file does, how it fits in the overall FinSight architecture, and a summary of its main parts.

**Architecture:** Each file gets a language-appropriate block comment at the very top (before any imports). Headers are purely additive — no logic changes. All 5 task groups are fully independent and can be executed in parallel.

**Tech Stack:** Python docstrings (`"""`), TypeScript JSDoc (`/** */`)

---

## Header Format Standards

### Python files
```python
"""
<filename>

<One-sentence description of what this file does.>

Role in project:
    <1-2 sentences on how this file fits in the FinSight architecture — which layer
    it belongs to, what calls it, what it calls.>

Main parts:
    - <ClassName or function_name>: <what it does>
    - <ClassName or function_name>: <what it does>
"""
```

### TypeScript / TSX files
```typescript
/**
 * <filename>
 *
 * <One-sentence description of what this file does.>
 *
 * Role in project:
 *   <1-2 sentences on how this file fits in the FinSight architecture — which layer
 *   it belongs to, what calls it, what it calls.>
 *
 * Main parts:
 *   - <ComponentName or functionName>: <what it does>
 *   - <ComponentName or functionName>: <what it does>
 */
```

### Rules
- Header goes at the very top of the file, before any imports
- Python: use triple-double-quote docstring
- TypeScript: use JSDoc block comment
- `__init__.py` files that are empty or only have imports still get a one-liner header
- Do NOT modify any logic, imports, or existing code — header only
- Keep descriptions in plain English — no jargon without explanation

---

## Task A — Backend: core/ (infrastructure clients)

**Files to modify:**
- `backend/core/config.py`
- `backend/core/gemini_client.py`
- `backend/core/pinecone_store.py`
- `backend/core/redis_client.py`
- `backend/__init__.py`
- `backend/core/__init__.py`

- [ ] **Step 1: Add header to `backend/core/config.py`**
```python
"""
config.py

Centralised configuration for FinSight using pydantic-settings.

Role in project:
    Foundation layer. Loaded once at startup by every other backend module via
    `get_settings()`. Reads all secrets and tuneable parameters from the `.env`
    file so no values are ever hardcoded.

Main parts:
    - Settings: pydantic-settings model declaring 15+ typed env vars (API keys,
      model names, chunking params, retrieval params, output paths).
    - get_settings(): cached factory function — returns the singleton Settings
      instance, constructed once and reused across the application lifetime.
"""
```

- [ ] **Step 2: Add header to `backend/core/gemini_client.py`**
```python
"""
gemini_client.py

Thin wrapper around the Google Gemini embedding API used to convert text into
high-dimensional vectors for semantic search.

Role in project:
    Infrastructure layer. Called by `vector_retrieval.py` to embed document
    chunks at ingest time and to embed user queries at search time. Never used
    for generation — Claude handles all reasoning.

Main parts:
    - GeminiClient: singleton wrapper that initialises the Gemini SDK and
      exposes embed_text(), embed_query(), and embed_texts() (batch).
      All methods use task-type hints (retrieval_document vs retrieval_query)
      to improve embedding quality for asymmetric search.
"""
```

- [ ] **Step 3: Add header to `backend/core/pinecone_store.py`**
```python
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
    - get_pinecone_store(): module-level singleton factory — creates the store
      once and returns the same instance on every subsequent call.
"""
```

- [ ] **Step 4: Add header to `backend/core/redis_client.py`**
```python
"""
redis_client.py

Async Redis connection used for two purposes: LangGraph conversation
checkpointing and document metadata tracking.

Role in project:
    Infrastructure layer. Shared by the LangGraph orchestrator (session memory
    via langgraph-checkpoint-redis) and the documents API route (stores
    doc_id → metadata hashes). Performs a ping on startup to fail fast if
    Redis is unreachable.

Main parts:
    - get_redis_client(): returns the shared async Redis connection, creating
      it on first call. Ping-validates on creation.
    - close_redis_client(): graceful shutdown helper called from FastAPI
      lifespan teardown.
"""
```

- [ ] **Step 5: Add one-liner headers to `__init__.py` files**
```python
# backend/__init__.py
"""FinSight CFO Assistant — backend package root."""

# backend/core/__init__.py
"""Infrastructure layer: configuration, API clients (Gemini, Pinecone, Redis)."""
```

- [ ] **Step 6: Verify no logic was changed**
```bash
cd finsight-cfo
git diff --stat
```
Expected: only `backend/core/*.py` and `backend/__init__.py` show changes, all as insertions only.

- [ ] **Step 7: Commit**
```bash
git add backend/__init__.py backend/core/
git commit -m "docs: add file headers to backend/core infrastructure layer"
```

---

## Task B — Backend: agents/ (LangGraph orchestrator)

**Files to modify:**
- `backend/agents/orchestrator.py`
- `backend/agents/graph_state.py`
- `backend/agents/base_agent.py`
- `backend/agents/__init__.py`

- [ ] **Step 1: Add header to `backend/agents/orchestrator.py`**
```python
"""
orchestrator.py

LangGraph StateGraph that routes every chat message through the correct
processing pipeline and streams the response back to the API layer.

Role in project:
    Agent layer — the brain of FinSight. Called by the `/chat` and
    `/chat/stream` route handlers. Receives an AgentState, runs it through
    7 nodes with conditional branching, and returns a fully populated state
    containing the assistant response and citations.

Main parts:
    - build_graph(): constructs and compiles the StateGraph with all nodes
      and conditional edges. Returns a compiled graph ready for invocation.
    - classify_intent node: uses Claude to classify the query into one of 7
      intent categories (document_qa, financial_model, scenario_analysis,
      general_chat, etc.).
    - rag_retrieve node: embeds the query via Gemini, searches Pinecone,
      and applies MMR reranking to return the top-5 most relevant chunks.
    - financial_model_node: extracts parameters from context and runs the
      appropriate financial model (DCF, ratios, forecast, or variance).
    - scenario_analysis_node: runs bull/base/bear scenarios, sensitivity
      tables, covenant stress tests, or runway calculations.
    - response_generator node: prompts Claude with retrieved context and
      model outputs to produce a cited, markdown-formatted answer.
    - response_extraction node: collects the full streamed response,
      extracts [Source: ...] citation tags, and runs citation validation.
"""
```

- [ ] **Step 2: Add header to `backend/agents/graph_state.py`**
```python
"""
graph_state.py

TypedDict definition for AgentState — the shared state object that flows
through every node in the LangGraph StateGraph.

Role in project:
    Agent layer — data contract. Every node in orchestrator.py reads from
    and writes to an AgentState instance. LangGraph uses this TypedDict to
    manage state transitions and checkpointing in Redis.

Main parts:
    - AgentState: TypedDict with fields for the conversation thread
      (session_id, messages), routing (intent, requires_retrieval),
      retrieval results (retrieved_chunks, context_string), model outputs
      (model_result, scenario_result), and the final response (response,
      citations, stream_tokens).
"""
```

- [ ] **Step 3: Add header to `backend/agents/base_agent.py`**
```python
"""
base_agent.py

Abstract base class defining the interface that all FinSight agent
implementations must conform to.

Role in project:
    Agent layer — currently unused in the active LangGraph flow (the
    orchestrator uses node functions, not class-based agents). Retained as
    an extension point for future specialised agent implementations that
    need shared lifecycle management.

Main parts:
    - BaseAgent: ABC with abstract methods run() and stream(), plus shared
      helpers for logging and error handling that subclasses can inherit.
"""
```

- [ ] **Step 4: Add one-liner header to `__init__.py`**
```python
# backend/agents/__init__.py
"""Agent layer: LangGraph StateGraph orchestrator and shared agent base class."""
```

- [ ] **Step 5: Verify and commit**
```bash
git diff --stat
git add backend/agents/
git commit -m "docs: add file headers to backend/agents layer"
```

---

## Task C — Backend: api/ routes

**Files to modify:**
- `backend/api/main.py`
- `backend/api/routes/chat.py`
- `backend/api/routes/documents.py`
- `backend/api/routes/health.py`
- `backend/api/routes/models.py`
- `backend/api/routes/scenarios.py`
- `backend/api/__init__.py`
- `backend/api/routes/__init__.py`

- [ ] **Step 1: Add header to `backend/api/main.py`**
```python
"""
main.py

FastAPI application factory — wires together all routers, configures CORS,
and manages service lifecycle (startup validation + graceful shutdown).

Role in project:
    HTTP entry point. This is the module Uvicorn loads:
    `uvicorn backend.api.main:app`. It registers all route prefixes, sets
    CORS policy to allow the Vite dev server at localhost:5173, and runs
    a health check on startup to confirm Redis, Pinecone, and API keys are
    reachable before accepting traffic.

Main parts:
    - app: the FastAPI instance with lifespan context manager.
    - lifespan(): async context that validates all external dependencies on
      startup and closes the Redis connection on shutdown.
    - Router registrations: /health, /chat, /documents, /models, /scenarios.
"""
```

- [ ] **Step 2: Add header to `backend/api/routes/chat.py`**
```python
"""
chat.py

FastAPI router handling all conversational endpoints — both blocking
(full response) and streaming (SSE token-by-token) chat modes.

Role in project:
    HTTP layer for the chat feature. Receives requests from the React
    CenterPanel via Axios (non-streaming) or native fetch (SSE). Delegates
    all intelligence to the LangGraph orchestrator and handles the mechanics
    of SSE framing and Redis checkpointer wiring.

Main parts:
    - POST /chat/: accepts a ChatRequest, runs the LangGraph graph to
      completion, and returns the full assistant response as JSON.
    - POST /chat/stream: accepts a ChatRequest and returns a
      StreamingResponse that pushes SSE events (intent, retrieval,
      response tokens, done) as the graph progresses.
"""
```

- [ ] **Step 3: Add header to `backend/api/routes/documents.py`**
```python
"""
documents.py

FastAPI router for document lifecycle management — upload, list, and delete.

Role in project:
    HTTP layer for the document ingestion pipeline. Called by the React
    LeftPanel. On upload, orchestrates the full ingest flow: save to disk →
    parse → chunk → embed → upsert to Pinecone → track in Redis.
    On delete, removes vectors from Pinecone and metadata from Redis.

Main parts:
    - POST /documents/upload: validates file (type, size, filename
      sanitisation), saves to UPLOAD_DIR, triggers ingest pipeline,
      and returns the new document's metadata.
    - GET /documents/: reads all doc metadata hashes from Redis and
      returns a list of DocumentRecord objects.
    - DELETE /documents/{doc_id}: deletes Pinecone vectors by doc_id
      filter and removes the Redis hash.
"""
```

- [ ] **Step 4: Add header to `backend/api/routes/health.py`**
```python
"""
health.py

FastAPI router exposing a single GET /health endpoint that probes all
external dependencies and reports their status.

Role in project:
    Operational layer. Called by the Makefile `make status` command and
    by the FastAPI lifespan on startup. Returns a JSON object with
    individual pass/fail for Redis ping, Pinecone index reachability,
    and presence of required API keys.

Main parts:
    - GET /health: async handler that runs Redis ping, Pinecone describe_index,
      and env-var presence checks concurrently, returning a HealthResponse
      with per-service status and an overall healthy boolean.
"""
```

- [ ] **Step 5: Add header to `backend/api/routes/models.py`**
```python
"""
models.py

FastAPI router exposing direct HTTP endpoints for the four financial
modeling capabilities: DCF valuation, ratio scorecard, forecasting,
and variance analysis.

Role in project:
    HTTP layer for the financial modeling skill. These endpoints are called
    by the React RightPanel Quick Actions and can also be invoked directly
    by the LangGraph financial_model_node. They are thin wrappers — all
    logic lives in `skills/financial_modeling.py`.

Main parts:
    - POST /models/dcf: runs a Discounted Cash Flow valuation given revenue
      projections, WACC, and terminal growth rate.
    - POST /models/ratios: computes a financial ratio scorecard from income
      statement and balance sheet figures.
    - POST /models/forecast: generates a 12-month revenue forecast using
      historical trends.
    - POST /models/variance: produces an actual-vs-budget variance analysis.
    - POST /models/save: persists any model output dict to a JSON file in
      the outputs directory.
"""
```

- [ ] **Step 6: Add header to `backend/api/routes/scenarios.py`**
```python
"""
scenarios.py

FastAPI router for scenario and stress-testing endpoints: bull/base/bear
scenarios, 2D sensitivity tables, covenant stress tests, and cash runway.

Role in project:
    HTTP layer for the scenario analysis skill. Mirrors the structure of
    models.py — thin route handlers that delegate to
    `skills/scenario_analysis.py`. Called by Quick Actions in the React
    RightPanel or directly by the LangGraph scenario_analysis_node.

Main parts:
    - POST /scenarios/run: runs a three-scenario matrix (bull/base/bear)
      against a set of financial assumptions.
    - POST /scenarios/sensitivity: builds a 2D sensitivity table varying
      two input parameters across a grid.
    - POST /scenarios/covenants: stress-tests financial covenant thresholds
      against projected figures.
    - POST /scenarios/runway: calculates months of cash runway given current
      burn rate and cash balance.
"""
```

- [ ] **Step 7: Add one-liner headers to `__init__.py` files**
```python
# backend/api/__init__.py
"""HTTP layer: FastAPI application factory and route registration."""

# backend/api/routes/__init__.py
"""FastAPI route handlers for chat, documents, models, scenarios, and health."""
```

- [ ] **Step 8: Verify and commit**
```bash
git diff --stat
git add backend/api/
git commit -m "docs: add file headers to backend/api routes layer"
```

---

## Task D — Backend: skills/ and mcp_server/

**Files to modify:**
- `backend/skills/document_ingestion.py`
- `backend/skills/vector_retrieval.py`
- `backend/skills/financial_modeling.py`
- `backend/skills/scenario_analysis.py`
- `backend/skills/__init__.py`
- `backend/mcp_server/financial_mcp_server.py`
- `backend/mcp_server/tools/document_tools.py`
- `backend/mcp_server/tools/memory_tools.py`
- `backend/mcp_server/tools/modeling_tools.py`
- `backend/mcp_server/tools/output_tools.py`
- `backend/mcp_server/tools/scenario_tools.py`
- `backend/mcp_server/__init__.py`
- `backend/mcp_server/tools/__init__.py`

- [ ] **Step 1: Add header to `backend/skills/document_ingestion.py`**
```python
"""
document_ingestion.py

Parses uploaded financial documents and splits them into semantically
meaningful chunks ready for embedding and vector storage.

Role in project:
    Skills layer — document pipeline entry point. Called by the documents
    API route immediately after a file is saved to disk. Supports PDF
    (via pdfplumber), CSV (via pandas), plain text, and HTML
    (via BeautifulSoup). Produces Chunk objects consumed by
    vector_retrieval.py for embedding and upsert.

Main parts:
    - Chunk: dataclass holding chunk text, embedding vector slot, and
      metadata (doc_id, doc_name, doc_type, fiscal_year, section, page).
    - parse_pdf(): extracts full text and tables from a PDF using
      pdfplumber, with pdfminer.six as fallback.
    - parse_csv(): reads a CSV with pandas and serialises rows as text.
    - hierarchical_chunking(): splits parsed text into section-level
      chunks (512 tokens, 64-token overlap) and row-level chunks
      (128 tokens) for table content, using tiktoken for counting.
    - ingest_document(): top-level entry point — calls the right parser,
      chunks the output, and returns a list of Chunk objects.
"""
```

- [ ] **Step 2: Add header to `backend/skills/vector_retrieval.py`**
```python
"""
vector_retrieval.py

Embeds text via Gemini and manages all read/write operations against the
Pinecone vector index.

Role in project:
    Skills layer — the semantic search engine. Called in two directions:
    by the document ingest pipeline (embed_and_upsert) to index new chunks,
    and by the LangGraph rag_retrieve node (semantic_search + mmr_rerank)
    to answer queries. Owns the Gemini ↔ Pinecone data flow.

Main parts:
    - embed_and_upsert(): takes a list of Chunk objects, batches them
      through Gemini embed_texts(), and upserts to Pinecone in groups of
      100.
    - semantic_search(): embeds a query string and runs a cosine similarity
      search against Pinecone, returning the top-k chunk metadata dicts.
    - mmr_rerank(): applies Maximal Marginal Relevance (lambda=0.5) to
      re-order results for diversity, reducing redundant chunks in context.
    - delete_document_vectors(): removes all Pinecone vectors associated
      with a given doc_id using metadata filter deletion.
"""
```

- [ ] **Step 3: Add header to `backend/skills/financial_modeling.py`**
```python
"""
financial_modeling.py

Implements the four core financial models: DCF valuation, ratio scorecard,
revenue forecasting, and variance analysis.

Role in project:
    Skills layer — financial computation engine. Called both by the
    /models/* API routes (direct HTTP invocation) and by the LangGraph
    financial_model_node (agent-driven invocation). All models validate
    their inputs and return a structured dict with the result and any
    data-insufficiency warnings, never silently producing unreliable output.

Main parts:
    - extract_financials(): parses structured financial figures out of a
      RAG context string using Claude, returning a FinancialData object.
    - build_dcf_model(): computes enterprise value via discounted cash
      flows given revenue projections, WACC, and terminal growth rate.
    - build_ratio_scorecard(): computes liquidity, profitability, leverage,
      and efficiency ratios from income statement and balance sheet inputs.
    - build_forecast_model(): projects 12-month revenue using linear
      regression on historical data points.
    - build_variance_analysis(): computes actual-vs-budget variance in
      absolute and percentage terms for each line item.
"""
```

- [ ] **Step 4: Add header to `backend/skills/scenario_analysis.py`**
```python
"""
scenario_analysis.py

Implements strategic what-if analysis: multi-scenario matrices,
sensitivity tables, covenant stress tests, and cash runway calculation.

Role in project:
    Skills layer — scenario planning engine. Companion to
    financial_modeling.py. Called by the /scenarios/* API routes and the
    LangGraph scenario_analysis_node. All outputs include assumption
    documentation so CFOs can present them with full transparency.

Main parts:
    - run_scenario_matrix(): generates bull, base, and bear case projections
      by applying percentage adjustments to a set of base assumptions.
    - build_sensitivity_table(): produces a 2D grid varying two parameters
      (e.g. revenue growth × margin) across configurable ranges.
    - stress_test_covenants(): checks projected figures against debt
      covenant thresholds and flags periods where covenants are at risk.
    - calculate_cash_runway(): computes months of remaining runway given
      current cash balance and monthly burn rate.
"""
```

- [ ] **Step 5: Add header to `backend/mcp_server/financial_mcp_server.py`**
```python
"""
financial_mcp_server.py

Registers all 26 FinSight financial tools with the MCP (Model Context
Protocol) server so Claude can call them as structured tool invocations.

Role in project:
    MCP layer — tool registration hub. Exposes the full capabilities of the
    skills layer (document search, financial modeling, scenario analysis,
    output generation, memory) as MCP tools. Claude can call these tools
    directly during generation, enabling richer, more structured responses
    than pure text generation.

Main parts:
    - FastMCP app instance: the MCP server object that tools are registered
      against.
    - Tool registrations (26 total): each @mcp.tool() decorator wires a
      Python function to an MCP tool name with a typed parameter schema.
      Tools are grouped by domain: document (5), modeling (6), scenario (5),
      output (5), memory/audit (5).
"""
```

- [ ] **Step 6: Add headers to MCP tool files**
```python
# backend/mcp_server/tools/document_tools.py
"""
document_tools.py

MCP tool implementations for document search and retrieval operations.

Role in project:
    MCP layer — thin wrappers around vector_retrieval.py that expose
    document search capabilities as callable MCP tools. Claude invokes
    these during response generation to fetch cited source material.

Main parts:
    - mcp_search_documents(): semantic search across all indexed chunks.
    - mcp_get_document_list(): returns metadata for all ingested documents.
    - mcp_get_document_chunk(): fetches a specific chunk by ID.
    - mcp_citation_validator(): verifies that a [Source: ...] citation
      exists in the indexed documents before including it in a response.
    - mcp_get_fiscal_years(): returns all fiscal years present in the index.
"""

# backend/mcp_server/tools/memory_tools.py
"""
memory_tools.py

MCP tool implementations for conversation memory and audit logging.

Role in project:
    MCP layer — wrappers around Redis operations that give Claude structured
    access to session history and the ability to write audit log entries.
    Ensures every interaction is traceable for compliance purposes.

Main parts:
    - mcp_get_conversation_history(): retrieves prior messages for the
      current session thread from the LangGraph Redis checkpointer.
    - mcp_response_logger(): writes assistant responses to audit_log.jsonl.
    - mcp_intent_log(): records the classified intent for each query.
"""

# backend/mcp_server/tools/modeling_tools.py
"""
modeling_tools.py

MCP tool implementations wrapping the four financial modeling capabilities.

Role in project:
    MCP layer — delegates to financial_modeling.py. Allows Claude to
    trigger DCF, ratio, forecast, and variance models as structured tool
    calls during response generation rather than as separate API requests.

Main parts:
    - mcp_run_dcf(): calls build_dcf_model() with Claude-extracted params.
    - mcp_run_ratios(): calls build_ratio_scorecard().
    - mcp_run_forecast(): calls build_forecast_model().
    - mcp_run_variance(): calls build_variance_analysis().
    - mcp_extract_financials(): calls extract_financials() to parse figures
      from a RAG context string.
    - mcp_save_model_output(): persists model results to the outputs dir.
"""

# backend/mcp_server/tools/output_tools.py
"""
output_tools.py

MCP tool implementations for generating boardroom-ready output artefacts
(Excel workbooks, PDF reports, Plotly charts).

Role in project:
    MCP layer — output generation. Called by Claude when a user requests
    an export or a visual. Wraps openpyxl (Excel), reportlab (PDF), and
    Plotly (charts) behind simple MCP tool interfaces.

Main parts:
    - mcp_export_excel(): serialises a model output dict into a formatted
      .xlsx workbook saved to the outputs directory.
    - mcp_export_pdf(): renders a PDF report from a model output dict.
    - mcp_generate_chart(): creates an interactive Plotly chart from
      structured financial data.
    - mcp_get_output_list(): returns available output files.
    - mcp_read_output(): reads a previously saved output file.
"""

# backend/mcp_server/tools/scenario_tools.py
"""
scenario_tools.py

MCP tool implementations wrapping the four scenario analysis capabilities.

Role in project:
    MCP layer — delegates to scenario_analysis.py. Allows Claude to
    trigger scenario and stress-test computations as structured tool
    calls during response generation.

Main parts:
    - mcp_run_scenarios(): calls run_scenario_matrix() for bull/base/bear.
    - mcp_run_sensitivity(): calls build_sensitivity_table().
    - mcp_stress_covenants(): calls stress_test_covenants().
    - mcp_calculate_runway(): calls calculate_cash_runway().
    - mcp_scenario_summary(): formats scenario results into a markdown
      summary table suitable for direct inclusion in a CFO response.
"""
```

- [ ] **Step 7: Add one-liner headers to `__init__.py` files**
```python
# backend/skills/__init__.py
"""Skills layer: document ingestion, vector retrieval, financial modeling, scenario analysis."""

# backend/mcp_server/__init__.py
"""MCP server layer: registers 26 financial tools for Claude tool-calling."""

# backend/mcp_server/tools/__init__.py
"""MCP tool implementations grouped by domain: documents, modeling, scenarios, output, memory."""
```

- [ ] **Step 8: Verify and commit**
```bash
git diff --stat
git add backend/skills/ backend/mcp_server/
git commit -m "docs: add file headers to backend/skills and mcp_server layers"
```

---

## Task E — Backend: tests/

**Files to modify:** All 20 test files in `backend/tests/`

- [ ] **Step 1: Add headers to test files** (read each file first, then add appropriate header)

Pattern for test file headers:
```python
"""
test_<module>.py

Unit/integration tests for <module being tested>.

Role in project:
    Test suite — verifies the behaviour of <module>. Run with:
    `pytest tests/test_<module>.py -v`

Coverage:
    - <what scenario 1 tests>
    - <what scenario 2 tests>
    - <what scenario 3 tests>
"""
```

Files and their one-line coverage descriptions:
- `conftest.py` — shared fixtures (mock Pinecone, Redis, Gemini clients; sample documents)
- `test_base_agent.py` — BaseAgent ABC interface and lifecycle methods
- `test_chat_api.py` — `/chat` and `/chat/stream` endpoint request/response contracts
- `test_chat_fixes.py` — regression tests for chat bug fixes (citation handling, SSE framing)
- `test_config.py` — Settings loading from env vars and defaults
- `test_dcf_scaling.py` — DCF model output scaling and edge cases (zero WACC, negative growth)
- `test_document_ingestion.py` — PDF/CSV parsing, chunking correctness, metadata assignment
- `test_document_tools_integration.py` — MCP document tools end-to-end with live Pinecone
- `test_documents_security.py` — filename sanitisation, size limits, unsupported type rejection
- `test_financial_modeling.py` — all four financial models (DCF, ratios, forecast, variance)
- `test_gemini_batch.py` — Gemini batch embedding correctness and error handling
- `test_gemini_client.py` — GeminiClient embed_text, embed_query, embed_texts methods
- `test_health.py` — /health endpoint response structure and dependency checks
- `test_mcp_server.py` — MCP tool registration and invocation via FastMCP
- `test_memory_tools.py` — audit log writing and conversation history retrieval
- `test_modeling_tools_integration.py` — MCP modeling tools end-to-end
- `test_orchestrator.py` — LangGraph graph construction and node routing logic
- `test_orchestrator_modeling.py` — orchestrator financial model node integration
- `test_pinecone_store.py` — PineconeStore init, dimension validation, singleton behaviour
- `test_redis_atomicity.py` — Redis pipeline atomicity for document tracking operations
- `test_redis_client.py` — Redis connection, ping, and graceful shutdown
- `test_scenario_analysis.py` — all four scenario functions (matrix, sensitivity, covenants, runway)
- `test_vector_retrieval.py` — embed_and_upsert, semantic_search, MMR reranking, delete

- [ ] **Step 2: Verify and commit**
```bash
git diff --stat
git add backend/tests/
git commit -m "docs: add file headers to backend/tests suite"
```

---

## Task F — Frontend: all TypeScript / TSX files

**Files to modify:**
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api/axiosClient.ts`
- `frontend/src/types/index.ts`
- `frontend/src/theme/muiTheme.ts`
- `frontend/src/stores/sessionStore.ts`
- `frontend/src/stores/chatStore.ts`
- `frontend/src/stores/documentStore.ts`
- `frontend/src/stores/dashboardStore.ts`
- `frontend/src/components/panels/LeftPanel.tsx`
- `frontend/src/components/panels/CenterPanel.tsx`
- `frontend/src/components/panels/RightPanel.tsx`
- `frontend/src/components/chat/ChatBubble.tsx`
- `frontend/src/components/chat/CitationChip.tsx`
- `frontend/src/components/chat/StreamingIndicator.tsx`
- `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Add header to `frontend/src/main.tsx`**
```typescript
/**
 * main.tsx
 *
 * React application entry point — mounts the Root component into the DOM.
 *
 * Role in project:
 *   Top-level bootstrap. Vite loads this file first. It wraps the App
 *   component in MUI ThemeProvider and CssBaseline, reading the active
 *   theme from sessionStore so the correct theme is applied on first paint
 *   (no flash of wrong theme).
 *
 * Main parts:
 *   - Root: functional component that reads themeMode from sessionStore and
 *     passes the matching MUI theme (darkTheme or lightTheme) to ThemeProvider.
 *   - ReactDOM.createRoot: mounts Root into #root div in index.html.
 */
```

- [ ] **Step 2: Add header to `frontend/src/App.tsx`**
```typescript
/**
 * App.tsx
 *
 * Root layout component — renders the 3-panel shell that contains the
 * entire FinSight UI.
 *
 * Role in project:
 *   Single authoritative layout. There is no React Router — App.tsx IS the
 *   application. It owns the panel width calculations, collapse transitions,
 *   and the single fetchDocuments() call that populates LeftPanel on mount.
 *
 * Main parts:
 *   - LEFT_W / RIGHT_W / COLLAPSED_W: module-level constants (280 / 340 / 48px)
 *     used for panel sizing and CSS transitions.
 *   - App: reads leftPanelOpen and rightPanelOpen from sessionStore, renders
 *     three flex children — LeftPanel, CenterPanel, RightPanel — with width
 *     transitions driven by panel state.
 */
```

- [ ] **Step 3: Add header to `frontend/src/api/axiosClient.ts`**
```typescript
/**
 * axiosClient.ts
 *
 * Pre-configured Axios instance used for all REST API calls to the FastAPI
 * backend.
 *
 * Role in project:
 *   Shared HTTP client. Imported by every Zustand store that needs to make
 *   API requests. Sets baseURL to http://localhost:8000 and default headers.
 *   Note: SSE streaming uses native fetch, not this client, because Axios
 *   does not support streaming responses.
 *
 * Main parts:
 *   - api: Axios instance with baseURL, Content-Type header, and 30s timeout.
 */
```

- [ ] **Step 4: Add header to `frontend/src/types/index.ts`**
```typescript
/**
 * types/index.ts
 *
 * Shared TypeScript interfaces and enums used across the entire frontend.
 *
 * Role in project:
 *   Type contract layer. All API response shapes, store state shapes, and
 *   component prop types are defined here so the compiler catches mismatches
 *   between the backend API surface and frontend usage.
 *
 * Main parts:
 *   - Document: shape of a document record returned by GET /documents/.
 *   - ChatMessage: a single message in the conversation (role, content, citations).
 *   - Citation: a parsed [Source: ...] reference with doc name and section.
 *   - KPIValue: a single KPI card value (label, value, format, change, favorable).
 *   - StreamEvent: discriminated union of SSE event types emitted by /chat/stream.
 *   - Intent: enum of the 7 intent categories the orchestrator classifies into.
 */
```

- [ ] **Step 5: Add header to `frontend/src/theme/muiTheme.ts`**
```typescript
/**
 * muiTheme.ts
 *
 * MUI v6 theme definitions for FinSight — dark and light variants with
 * a shared design token set.
 *
 * Role in project:
 *   Visual foundation. Consumed by main.tsx ThemeProvider. All colours,
 *   typography, spacing, and component overrides are defined here so the
 *   rest of the application uses semantic tokens (primary.main, action.selected)
 *   rather than hardcoded hex values.
 *
 * Main parts:
 *   - designTokens: raw colour values for dark and light modes (bg, surface,
 *     elevated, accent, favorable, unfavorable).
 *   - darkTheme: MUI theme with dark palette wired to designTokens, including
 *     action.selected set to elevated (#3A3A3C) for active state consistency.
 *   - lightTheme: MUI theme with light palette counterpart.
 */
```

- [ ] **Step 6: Add headers to store files**
```typescript
// frontend/src/stores/sessionStore.ts
/**
 * sessionStore.ts
 *
 * Zustand store for global session state — theme mode, panel visibility,
 * and session ID. Persisted to localStorage.
 *
 * Role in project:
 *   Global UI state. The only store persisted between page reloads (key:
 *   "finsight-session"). Controls the 3-panel layout and the active MUI
 *   theme. Read by App.tsx (panel widths), main.tsx (theme), and the
 *   chat store (session ID for LangGraph thread continuity).
 *
 * Main parts:
 *   - SessionState: interface with themeMode, leftPanelOpen, rightPanelOpen,
 *     sessionId, and their toggle/setter actions.
 *   - useSessionStore: Zustand store with Immer-style setters and Zustand
 *     persist middleware writing to localStorage.
 */

// frontend/src/stores/chatStore.ts
/**
 * chatStore.ts
 *
 * Zustand store managing all chat state — message history, streaming
 * status, and the SSE connection lifecycle.
 *
 * Role in project:
 *   Chat feature state. Owned by CenterPanel (renders messages, input) and
 *   read by RightPanel (Quick Action buttons call sendMessage()). Uses
 *   native fetch (not Axios) to consume the SSE stream from POST /chat/stream,
 *   dispatching partial tokens into the in-progress assistant message as they
 *   arrive.
 *
 * Main parts:
 *   - ChatState: messages array, isStreaming flag, currentIntent string.
 *   - sendMessage(): opens an SSE connection, processes event types (intent,
 *     retrieval, response, done), and appends/updates the assistant message.
 *   - clearChat(): resets messages and generates a new sessionId.
 */

// frontend/src/stores/documentStore.ts
/**
 * documentStore.ts
 *
 * Zustand store managing the list of ingested documents and document
 * lifecycle operations (fetch, upload, delete).
 *
 * Role in project:
 *   Document feature state. Owned by LeftPanel (renders the doc list, upload
 *   dialog). fetchDocuments() is called once on mount from App.tsx to
 *   populate the list without redundant calls from individual panels.
 *
 * Main parts:
 *   - DocumentState: documents array, loading flag, uploadLoading flag, error.
 *   - fetchDocuments(): GET /documents/ and populates the store.
 *   - uploadDocument(): multipart POST /documents/upload with file, doc_type,
 *     and fiscal_year, then refetches the list.
 *   - deleteDocument(): DELETE /documents/{doc_id} then refetches the list.
 */

// frontend/src/stores/dashboardStore.ts
/**
 * dashboardStore.ts
 *
 * Zustand store for the RightPanel KPI dashboard — fetches 6 financial
 * metrics by firing background chat queries and parsing the responses.
 *
 * Role in project:
 *   KPI data layer. Called by RightPanel on mount. Uses the existing
 *   POST /chat endpoint (non-streaming) with hardcoded natural-language
 *   questions to extract key metrics from ingested documents without
 *   requiring a dedicated KPI endpoint.
 *
 * Main parts:
 *   - KPI_QUERIES: 6 hardcoded questions (revenue, gross margin, EBITDA,
 *     net income, cash balance, runway).
 *   - fetchKPIs(): fires all 6 queries in parallel and stores parsed results.
 *   - parseKPIResponse(): extracts the numeric value from a chat response
 *     and formats it as currency ($5.2M), percentage (45.3%), or months.
 *   - TODO: populate change and favorable fields once prior-period comparison
 *     queries are implemented.
 */
```

- [ ] **Step 7: Add headers to panel components**
```typescript
// frontend/src/components/panels/LeftPanel.tsx
/**
 * LeftPanel.tsx
 *
 * Left panel of the 3-panel layout — the Sources panel where users manage
 * financial documents.
 *
 * Role in project:
 *   Document management UI. Reads from documentStore (document list, upload
 *   state) and renders the list of ingested files with type chips, status
 *   indicators, and hover-reveal delete buttons. Collapses to a 48px icon
 *   rail showing only the upload button.
 *
 * Main parts:
 *   - LeftPanel: main component with expanded/collapsed render paths.
 *   - renderUploadDialog(): MUI Dialog for file picker, doc_type dropdown,
 *     and fiscal_year field.
 *   - renderSnackbar(): success/error feedback after upload (rendered in
 *     both expanded and collapsed states to avoid silent failures).
 *   - Document list: maps documents to ListItem rows with DocumentTypeChip,
 *     status dot, and delete IconButton.
 */

// frontend/src/components/panels/CenterPanel.tsx
/**
 * CenterPanel.tsx
 *
 * Centre panel of the 3-panel layout — the Chat panel where users
 * converse with FinSight.
 *
 * Role in project:
 *   Primary interaction surface. Reads from chatStore (messages, streaming
 *   state) and sessionStore (session ID). Renders the conversation history
 *   using ChatBubble components, shows a StreamingIndicator while a response
 *   is in-flight, and provides the message input bar with send button.
 *
 * Main parts:
 *   - CenterPanel: manages auto-scroll to latest message, input state, and
 *     submit handler that calls chatStore.sendMessage().
 *   - Message list: maps chatStore.messages to ChatBubble + CitationChip rows.
 *   - Input bar: MUI TextField with conditional send button styling (active
 *     only when input is non-empty and not streaming).
 *   - StreamingIndicator: shown below the last message while isStreaming=true.
 */

// frontend/src/components/panels/RightPanel.tsx
/**
 * RightPanel.tsx
 *
 * Right panel of the 3-panel layout — the Studio panel showing live KPI
 * cards and quick-action shortcuts.
 *
 * Role in project:
 *   CFO dashboard surface. Reads from dashboardStore (KPI values, loading
 *   state) and chatStore (sendMessage for Quick Actions). Fires fetchKPIs()
 *   on mount to populate cards from indexed documents. Collapses to a 48px
 *   icon rail.
 *
 * Main parts:
 *   - RightPanel: expanded/collapsed render paths.
 *   - KPI grid: 6 cards (Revenue, Gross Margin, EBITDA, Net Income, Cash
 *     Balance, Runway) in a 2-column MUI Grid with skeleton loaders.
 *   - Quick Actions: 4 MUI Buttons (DCF Model, Scenario Analysis, Forecast
 *     Revenue, Export Report) that call sendMessage() with preset prompts.
 *   - TODO: migrate Grid to Grid2 for MUI v7 compatibility.
 */
```

- [ ] **Step 8: Add headers to chat sub-components**
```typescript
// frontend/src/components/chat/ChatBubble.tsx
/**
 * ChatBubble.tsx
 *
 * Renders a single chat message as a styled bubble — user messages on the
 * right, assistant messages on the left with markdown support.
 *
 * Role in project:
 *   Presentational component. Used by CenterPanel to render each message in
 *   the conversation history. Assistant messages are rendered with
 *   react-markdown + remark-gfm to support tables, lists, and bold text
 *   from Claude's financial analysis responses.
 *
 * Main parts:
 *   - ChatBubble: accepts a ChatMessage prop and renders the appropriate
 *     bubble layout, background colour, and alignment.
 *   - Markdown renderer: configured with remark-gfm for GitHub Flavored
 *     Markdown, with MUI Typography overrides for table and list styling.
 */

// frontend/src/components/chat/CitationChip.tsx
/**
 * CitationChip.tsx
 *
 * Renders a [Source: ...] citation reference as a compact MUI Chip,
 * keeping source attribution visible without breaking reading flow.
 *
 * Role in project:
 *   Citation UI. Used by CenterPanel to render inline citations extracted
 *   from assistant messages. Each chip shows the document name and section;
 *   clicking it could be extended in Phase 6 to scroll the LeftPanel to
 *   the referenced document.
 *
 * Main parts:
 *   - CitationChip: accepts a Citation object (doc_name, section, page) and
 *     renders a small purple MUI Chip with a link icon.
 */

// frontend/src/components/chat/StreamingIndicator.tsx
/**
 * StreamingIndicator.tsx
 *
 * Animated indicator shown while the assistant is generating a response,
 * with a label that updates to reflect the current pipeline stage.
 *
 * Role in project:
 *   Streaming UX feedback. Shown by CenterPanel below the message list
 *   whenever chatStore.isStreaming is true. Reads currentIntent from
 *   chatStore to display contextual labels (Classifying... / Retrieving...
 *   / Generating...) that mirror the LangGraph node progression.
 *
 * Main parts:
 *   - StreamingIndicator: renders three animated dots with a stage label
 *     derived from the current SSE event type.
 */
```

- [ ] **Step 9: Add header to `vite-env.d.ts`**
```typescript
/**
 * vite-env.d.ts
 *
 * Vite client type declarations — makes import.meta.env typed in TypeScript.
 *
 * Role in project:
 *   Build tooling types. Auto-generated by Vite. Do not modify manually.
 */
```

- [ ] **Step 10: Verify and commit**
```bash
git diff --stat
git add frontend/src/
git commit -m "docs: add file headers to all frontend TypeScript/TSX files"
```

---

## Final Step — Update CLAUDE.md and MEMORY.md

- [ ] **Step 1: Add file header convention to CLAUDE.md coding conventions**

Add under `## Coding Conventions`:
```markdown
### File Headers (all files)
Every source file must begin with a language-appropriate header comment:
- **Python**: triple-double-quote docstring before any imports
- **TypeScript/TSX**: JSDoc block comment (`/** */`) before any imports

Header must include:
1. Filename
2. One-sentence description of what the file does
3. "Role in project" — how it fits in the architecture (1-2 sentences)
4. "Main parts" — bullet list of key classes/functions/components with descriptions
```

- [ ] **Step 2: Update MEMORY.md**

Add to `~/.claude/projects/-Users-aarvingeorge-Documents-Climb-Profile-Builder-side-quests/memory/MEMORY.md`:
```markdown
- [File headers required](feedback_file_headers.md) — every source file must have a descriptive header (filename, one-sentence summary, role in project, main parts)
```

- [ ] **Step 3: Final commit**
```bash
git add CLAUDE.md
git commit -m "docs: add file header convention to CLAUDE.md coding standards"
git push origin main
```
