# CLAUDE.md — FinSight CFO Assistant

## Project Vision

FinSight is a locally-deployed, RAG-powered financial intelligence assistant for CFOs. It ingests financial documents (10-K/10-Q filings, income statements, balance sheets, cash flow statements, board reports, budgets), builds a semantic vector index, and deploys specialized AI agents to answer natural-language questions, generate financial models, run scenario analyses, and produce boardroom-ready outputs.

**Target user:** A Chief Financial Officer interacting through a clean, professional 3-panel web interface.

---

## Architecture

```
React + TypeScript Frontend (MUI v6) — 3-panel layout (no React Router)
        │ REST API + SSE
FastAPI Backend Server
  ├── LangGraph Orchestrator (StateGraph, 7 nodes)
  │     ├── classify_intent → conditional routing
  │     ├── rag_retrieve (Gemini embed → Pinecone → MMR rerank)
  │     ├── financial_model_node
  │     ├── scenario_analysis_node
  │     └── response_generator (citation validation)
  ├── Skills Layer
  │     ├── document_ingestion.py
  │     ├── vector_retrieval.py
  │     ├── financial_modeling.py
  │     └── scenario_analysis.py
  ├── MCP Server (26 registered tools)
  ├── API Routes
  │     ├── /workspaces/ (POST create, GET list, PATCH update)
  │     └── /kpis/ (GET with 24h SQLite cache → workspace_kpi_cache)
  └── Infrastructure
        ├── Pinecone (vector store, dim=3072, cosine; namespace per workspace)
        ├── SQLite (control plane: users, workspaces, documents, checkpoints,
        │           workspace_kpi_cache)
        └── Gemini (embeddings, gemini-embedding-001)
```

---

## Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | Python 3.13, FastAPI | conda env `finsight` |
| Agent Orchestration | LangGraph (StateGraph) | Avoids vendor lock-in, built-in checkpointing |
| LLM | claude-sonnet-4-6 | via `langchain-anthropic` |
| Embeddings | Gemini `gemini-embedding-001` | 3072 dimensions |
| Vector Store | Pinecone (serverless, cosine) | Replaced FAISS from original spec |
| Control Plane | SQLite (`data/finsight.db`) + SQLAlchemy 2.x + Alembic | Users, workspaces, documents, chat_sessions; schema via `alembic upgrade head` |
| LangGraph Checkpointer | `langgraph-checkpoint-sqlite` | `SqliteSaver` backed by same `data/finsight.db` file; no Docker required |
| Tool Protocol | MCP via `mcp` Python SDK (FastMCP) | 26 tools |
| Frontend | React 18 + TypeScript + Vite | No React Router — single App.tsx shell |
| UI Components | MUI v6 exclusively | No Tailwind, Bootstrap, or raw CSS |
| State Management | Zustand | 4 stores, sessionStore persisted to localStorage |
| HTTP Client | Axios (REST), native fetch (SSE) | |
| Charts | Plotly (react-plotly.js) | |
| Config | pydantic-settings + `.env` | |
| Package Management | conda (backend), npm (frontend) | NOT venv |

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 — Foundation | ✅ DONE | FastAPI scaffold, config, Pinecone/Gemini clients, MCP scaffold |
| Phase 2 — Ingestion & RAG | ✅ DONE | PDF/CSV parsing, hierarchical chunking, embedding, Pinecone upsert/search, MMR |
| Phase 3 — Financial Modeling | ✅ DONE | DCF, ratio scorecard, forecasting, variance, scenarios, covenants, runway |
| Phase 4 — Agent Integration | ✅ DONE | LangGraph orchestrator, intent routing, SqliteSaver checkpointing, SSE streaming |
| Phase 5 — Frontend | ✅ DONE | 3-panel NotebookLM-inspired layout (Sources \| Chat \| Studio), KPI dashboard |
| Phase 6 — Output & Polish | 🚧 IN PROGRESS | Infra hardening done (SecretStr, `make doctor`, health-gated `make start`, log redirection, backend-unreachable modal, SQLite control plane + multi-tenant scaffolding, Redis removed); workspace management UI, KPI cache layer, KPI response parser shipped; Excel/PDF export + cloud deployment remain |

---

## Key Constraints & Non-Negotiables

1. **Zero hallucination on numbers** — every financial figure traced to a retrieved chunk via `mcp_citation_validator`
2. **Citation enforcement** — every factual claim needs `[Source: doc_name, section, page]`
3. **MUI exclusively** — no Tailwind, Bootstrap, Chakra UI, or custom CSS frameworks
4. **Streaming responses** — all Claude responses stream via SSE; no waiting for full response
5. **Insufficient data flagging** — models check inputs and flag when data is insufficient
6. **Local-first** — everything on localhost; Pinecone is the only external service
7. **Audit trail** — `mcp_response_logger` and `mcp_intent_log` write to `audit_log.jsonl`
8. **Environment security** — API keys in `.env`, never hardcoded or committed. Every `*_api_key` field on the `Settings` model is typed as `pydantic.SecretStr` so tracebacks, log dumps, `print(settings)`, and repr() all render `SecretStr('**********')`. Call sites use `.get_secret_value()` only at the point of SDK client construction.
9. **File upload security** — filenames sanitized, 50MB limit, types: `.pdf .csv .txt .html`
10. **Empty-env-shadow protection** — `get_settings()` in `backend/core/config.py` calls `_strip_empty_shadow_env()` which deletes empty-string sensitive env vars from `os.environ` before pydantic reads. This prevents parent processes (e.g. Claude Code, which exports `ANTHROPIC_API_KEY=""` for security hygiene) from silently shadowing real values in `.env`. Non-empty env overrides still work — tested via `test_non_empty_env_still_overrides_dotenv`.
11. **KPI display safety** — KPI cards surface a parsed headline via `parse_kpi_response()` — never display raw Claude markdown in compact UI surfaces.

---

## Frontend: 3-Panel Layout (Phase 5)

No React Router. Single `App.tsx` shell with three collapsible panels:

```
┌─────────────────┬──────────────────────┬──────────────────┐
│  LeftPanel      │   CenterPanel        │  RightPanel      │
│  (Sources)      │   (Chat)             │  (Studio/KPIs)   │
│  280px / 48px   │   flex               │  340px / 48px    │
│  collapsed      │                      │  collapsed       │
└─────────────────┴──────────────────────┴──────────────────┘
```

**Panel responsibilities:**
- `LeftPanel` — document list, upload dialog, search filter → `documentStore`
- `CenterPanel` — chat messages, SSE streaming, input bar → `chatStore`
- `RightPanel` — 6 KPI cards, 4 Quick Action buttons → `dashboardStore` + `chatStore`
- `BackendUnreachableModal` — blocking modal rendered at the root of `App.tsx`, shown when the axios interceptor flips `connectionStore.backendUnreachable` (matches Figma Variant D)

**Zustand stores:**
- `sessionStore` — `themeMode`, `leftPanelOpen`, `rightPanelOpen`, `sessionId`, `workspaceId` *(persisted to localStorage key: `finsight-session`)*
- `chatStore` — messages, isStreaming, currentIntent, sendMessage(), clearChat()
- `documentStore` — documents list, loading, fetchDocuments(), uploadDocument(), deleteDocument()
- `dashboardStore` — KPI values (populated by `GET /kpis/`), status, cacheHit, computedAt, loading
- `connectionStore` — `backendUnreachable` flag, updated bidirectionally by the axios response interceptor (set on ERR_NETWORK, cleared on any HTTP response)
- `workspaceStore` — workspaces array, fetchWorkspaces(), createWorkspace(); creating auto-switches active workspace

**Design tokens** (`muiTheme.ts`):
- Dark bg: `#1C1C1E`, surface: `#2C2C2E`, elevated: `#3A3A3C`
- Accent: `#7c4dff`, favorable: `#00e676`, unfavorable/error: `#ff5252`, success: `#10B964`
- `action.selected` wired to elevated token (`#3A3A3C`)

**KPI queries** — `GET /kpis/` call on `RightPanel` mount (replaces 6 individual `POST /chat` calls); 24h SQLite cache means zero Claude calls on page refresh. Refresh button + "Updated N min ago" indicator shown. Empty workspace shows "Upload a document to see KPIs." Empty state fires zero Claude calls.
KPI keys: `revenue`, `gross_margin`, `ebitda`, `net_income`, `cash_balance`, `runway`

---

## Design Source of Truth (Figma)

All UI design decisions trace back to this Figma file. Any deviation between the live app and the file should be treated as drift to be reconciled.

- **File:** [FinSight CFO — 3-Panel Redesign](https://www.figma.com/design/L9k0ZL0p6CGWBfuUOt31ec/FinSight-CFO---3-Panel-Redesign)
- **File key:** `L9k0ZL0p6CGWBfuUOt31ec`
- **Workspace:** *Aarvin George's team* (Full/expert seat on account `tomgrg8@gmail.com`)
- **Pages:**
  - `Designs` — the shipped UI
    - `Main Layout` (id `2:2`) — 1440×900, the full 3-panel view
    - `Both Panels Collapsed` (id `3:2`) — rails collapsed state
    - `Design Tokens` (id `3:32`) — swatches (`#1C1C1E` bg, `#2C2C2E` surface, `#3A3A3C` elevated, `#7C4DFF` accent, `#F5F5F7` text primary, `#8E8E93` text secondary, `#10B964` success, `#FF5252` error)
  - `Phase 6 — Banner Variants` — exploration for the backend-unreachable UI (added 2026-04-19)
    - Variants A (non-dismissible top banner), B (dismissible top banner), C (snackbar), D (modal). **Variant D was shipped** as `BackendUnreachableModal.tsx`; A/B/C are archived as exploration.
- **Rule of thumb:** before creating a new component, check the file for existing variants or tokens. Before proposing a visual change, mock it in the file first so the diff is visible and token-correct.

---

## Backend API Surface (20 endpoints)

| Method | Path | Purpose | Request body |
|--------|------|---------|---|
| GET | `/health` | Service health (SQLite, Pinecone, API keys) | — |
| POST | `/chat/` | Chat → full response (non-streaming) | `{"message": "...", "session_id": "..."}` ⚠ field is `message`, not `query` |
| POST | `/chat/stream` | Chat → SSE stream (token-level) | Same as `/chat/` |
| POST | `/documents/upload` | Upload + parse + chunk + embed + index | `multipart/form-data` with `file`, `doc_type`, `fiscal_year` |
| GET | `/documents/` | List all ingested documents | — |
| DELETE | `/documents/{doc_id}` | Delete document + vectors; auto-invalidates KPI cache | — |
| GET | `/kpis/` | Get 6 KPI values; 24h SQLite cache, `?refresh=true` to bust | — |
| POST | `/models/dcf` | DCF valuation |
| POST | `/models/ratios` | Ratio scorecard |
| POST | `/models/forecast` | Forecast model |
| POST | `/models/variance` | Variance analysis |
| POST | `/models/save` | Persist model output |
| POST | `/scenarios/run` | Bull/base/bear scenarios |
| POST | `/scenarios/sensitivity` | 2D sensitivity table |
| POST | `/scenarios/covenants` | Covenant stress test |
| POST | `/scenarios/runway` | Cash runway |
| POST | `/workspaces/` | Create workspace (`wks_<8hex>` ID, scoped to owner) | `{"name": "...", "description": "..."}` |
| GET | `/workspaces/` | List workspaces for current user (excludes archived) | — |
| PATCH | `/workspaces/{id}` | Update workspace name / description / status | `{"name": "...", "description": "...", "status": "..."}` |

Backend: `PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000`

---

## Upload Pipeline (bird's-eye view)

Traces a document from the user's click in the upload dialog to a retrievable vector. Use this table for orientation; see `docs/superpowers/plans/` and `~/.claude/plans/squishy-crunching-truffle.md` for the deep dive.

| # | Stage | File | Function / lines | Key behaviour |
|---|---|---|---|---|
| 0 | UI trigger | `frontend/src/components/panels/LeftPanel.tsx` | `handleUpload` (62–76) | Dialog collects `file`, `doc_type`, `fiscal_year` → store |
| 1 | Store + HTTP | `frontend/src/stores/documentStore.ts` | `uploadDocument` (47–61) | `POST /documents/upload` as `multipart/form-data`; auto-refetches on success |
| 2 | FastAPI route | `backend/api/routes/documents.py` | `upload_document` (38–111) | Filename sanitize, 50 MB cap, ext whitelist (`.pdf .csv .txt .html`), writes to `data/uploads/` |
| 3 | Parse | `backend/skills/document_ingestion.py` | `parse_pdf` (55–111), `parse_csv` (114–145) | `pdfplumber` per-page text+tables; financial-value normalization (`$`/`,`/`(x)` → `-x`) |
| 4 | Hierarchical chunk | `backend/skills/document_ingestion.py` | `hierarchical_chunk` (161–258) | 512-token sections + 64-token overlap; 128-token row chunks; metadata: `doc_id, doc_name, doc_type, fiscal_year, page, chunk_type, section, chunk_index` |
| 5 | Embed | `backend/core/gemini_client.py` | `embed_texts` | **Single batch** call to `gemini-embedding-001`; returns `{"embedding": [[vec], ...]}` (singular key, list-of-lists); 3072-dim |
| 6 | Upsert | `backend/skills/vector_retrieval.py` | `embed_and_upsert` (41–85) | Batches of 100 to Pinecone namespace = `workspace_id`; chunk IDs are `<doc_id>:<NNNN>`; wrapped in `StorageTransaction` with compensating actions |
| 7 | SQLite register | `backend/db/models.py` + `backend/api/routes/documents.py` | `Document` ORM row | Writes document record to `data/finsight.db` via SQLAlchemy; atomically paired with Pinecone upsert inside `StorageTransaction` |
| 8 | Response + refetch | — | — | 200 returned → frontend `fetchDocuments()` → left panel repopulates |
| 9 | RAG read path | `backend/agents/orchestrator.py` | `rag_retrieve` (116–141) | Query embed → `semantic_search(top_k=8)` → `mmr_rerank(top_k=5)` → `format_retrieved_context` → Claude |

**Reference documents in this repo:**
- `~/.claude/plans/squishy-crunching-truffle.md` (user-level) — full debug playbook with 6-step layered strategy; produced 2026-04-17 during the upload-failure investigation
- `docs/superpowers/plans/2026-03-31-finsight-phase2-ingestion-rag.md` — original Phase 2 plan that designed this pipeline

---

## File Headers (all files — mandatory)

Every source file must begin with a language-appropriate header comment, placed before any imports:

**Python** — triple-double-quote docstring:
```python
"""
filename.py

One-sentence description of what this file does.

Role in project:
    1-2 sentences on how this file fits in the architecture — which layer it
    belongs to, what calls it, what it calls.

Main parts:
    - ClassName or function_name: what it does
    - ClassName or function_name: what it does
"""
```

**TypeScript/TSX** — JSDoc block comment:
```typescript
/**
 * filename.tsx
 *
 * One-sentence description of what this file does.
 *
 * Role in project:
 *   1-2 sentences on how this file fits in the architecture.
 *
 * Main parts:
 *   - ComponentName or functionName: what it does
 */
```

`__init__.py` and type declaration files get a one-liner docstring minimum. Every new file created must include this header.

**Maintenance rule (Claude's responsibility):**
- Whenever a file is modified, Claude must update its header to reflect any changes to functionality, main parts, or role in the project.
- This is enforced at the `verification-before-completion` step — before claiming any task is done, Claude must confirm that every file it touched has an accurate, up-to-date header.
- Stale headers are treated as a bug, not a cosmetic issue.

---

## File Structure (current)

```
finsight-cfo/
├── backend/
│   ├── agents/          # LangGraph orchestrator + graph_state.py + base_agent.py
│   ├── api/routes/      # FastAPI endpoints (incl. health.py, workspaces.py,
│   │                    #   kpis.py with KPI_PROMPTS + parse_kpi_response)
│   ├── core/            # config.py (SecretStr + env-shadow strip), gemini_client.py,
│   │                    #   pinecone_store.py, context.py (RequestContext),
│   │                    #   transactions.py (StorageTransaction)
│   ├── db/              # engine.py (SQLAlchemy + WAL), models.py (ORM incl.
│   │                    #   WorkspaceKpiCache), __init__.py, migrations/ (Alembic versions)
│   ├── skills/          # document_ingestion, vector_retrieval, financial_modeling,
│   │                    #   scenario_analysis
│   ├── mcp_server/      # financial_mcp_server.py + tools/
│   ├── scripts/         # migrate_to_workspace_schema.py, stats.py (SQLite-backed)
│   ├── tests/           # 282 unit tests (incl. test_kpi_response_parser.py — 17 tests)
│   ├── .env             # Secrets (never committed — *.env is gitignored)
│   ├── .env.example     # Template with placeholder values
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── panels/     # LeftPanel.tsx, CenterPanel.tsx, RightPanel.tsx
│       │   ├── chat/       # ChatBubble.tsx, CitationChip.tsx, StreamingIndicator.tsx
│       │   ├── common/     # BackendUnreachableModal.tsx (blocking modal on ERR_NETWORK)
│       │   └── workspace/  # WorkspaceSwitcher.tsx (MUI Button+Menu, accent dot),
│       │                   #   CreateWorkspaceModal.tsx (name + description form)
│       ├── stores/      # sessionStore, chatStore, documentStore, dashboardStore,
│       │                #   connectionStore, workspaceStore
│       ├── api/         # axiosClient.ts (baseURL: localhost:8000 + interceptor
│       │                #   that flips connectionStore.backendUnreachable)
│       ├── theme/       # muiTheme.ts (dark + light themes)
│       ├── types/       # index.ts
│       ├── App.tsx      # 3-panel shell + <BackendUnreachableModal /> at root
│       └── main.tsx     # React entry point
├── data/
│   ├── finsight.db      # SQLite control plane (gitignored)
│   └── uploads/         # {workspace_id}/{doc_id}.{ext} (gitignored);
│                        #   _pre_migration/ holds archived pre-refactor files
├── alembic.ini          # Alembic migration config
├── logs/                # backend.log + frontend.log (gitignored via *.log)
├── Makefile             # start / stop / status / doctor / stats / install targets
├── CLAUDE.md            # This file — project source of truth
└── README.md
```

---

## Coding Conventions

### Backend (Python)
- Type hints on all function signatures
- Pydantic models for all API request/response bodies
- Skills hold business logic — routes and MCP tools are thin wrappers
- No bare `except` — always catch specific exceptions
- `asyncio.to_thread()` for blocking calls in async handlers
- `StorageTransaction` for atomic writes spanning SQLite + Pinecone + disk; include compensating actions
- SQLAlchemy sessions via `get_db()` dependency — never raw SQL
- Test naming: `test_<what>_<condition>`

### Frontend (TypeScript/React)
- Functional components only, one per file
- MUI v6 exclusively — `sx` prop or `styled()`, no raw CSS
- Zustand for state — no prop drilling
- Axios for REST, native fetch for SSE
- TypeScript strict mode — no `any` except at external JSON boundaries
- `fetchDocuments()` called once in `App.tsx` — not in individual panels

### Git
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `perf:`, `test:`
- Never commit: `.env`, `node_modules/`, `__pycache__/`, `data/`, `storage/`

---

## Running the Project

**Daily path (recommended):**
```bash
make start     # backend (health-gated) + frontend, logs captured to logs/
make doctor    # diagnose any issue — SQLite db, port 8000, /health, port 5173, .env keys
make status    # quick one-shot snapshot
make stop      # terminate both services
make stats     # cross-reference Pinecone namespace counts vs. SQLite chunk_count sums
```

`make start` polls `GET /health` for up to 15 s before declaring the backend ready; if it fails to come up it tails the last 20 lines of `logs/backend.log` and exits non-zero. The old blind `sleep 2` is gone. Docker is not required. Follow live logs with `tail -f logs/backend.log` / `tail -f logs/frontend.log`.

**Manual path (if `make` isn't available):**
```bash
# Backend
conda activate finsight
alembic upgrade head              # creates data/finsight.db on first run
PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev   # localhost:5173
```

**Tests:**
```bash
conda run -n finsight pytest backend/tests/ -v -k "not integration"   # unit (282)
conda run -n finsight pytest backend/tests/ -v -m integration          # integration tests
```

---

## Decision Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-31 | Pinecone over FAISS | Serverless, no local index management |
| 2026-03-31 | conda over venv | User preference |
| 2026-03-31 | LangGraph over Anthropic Agent SDK | Avoid vendor lock-in |
| 2026-03-31 | Dark mode default + toggle | Modern SaaS aesthetic |
| 2026-04-12 | 3-panel layout over sidebar+pages | NotebookLM-inspired, no routing needed for single-context CFO tool |
| 2026-04-12 | React Router removed | Single App.tsx shell is sufficient, reduces bundle size |
| 2026-04-12 | fetchDocuments() in App.tsx only | Prevents duplicate API calls from LeftPanel + RightPanel mounting simultaneously |
| 2026-04-19 | Figma file `L9k0ZL0p6CGWBfuUOt31ec` is the design source of truth | Single canonical file; prevents drift and ensures every design decision is token-correct before it lands in code |
| 2026-04-17 | `fix(gemini)` `3a9925b` — batch embed reads `result["embedding"]` (singular) | `google-generativeai` 0.8.3 returns `{"embedding": [[vec], ...]}` with a singular key even for list content; existing tests mocked the plural key and masked the bug until a real 10-K upload hit it |
| 2026-04-19 | `fix(config)` `608d58f` — SecretStr for all API keys + `_strip_empty_shadow_env()` | A pytest assertion failure dumped plaintext keys into stdout; systemic fix via SecretStr prevents recurrence. Env-shadow strip fixes Claude Code subshells that export empty sensitive vars |
| 2026-04-19 | `feat(make)` `b5c5eb8` — `make doctor`, health-gated `make start`, log redirection | Old `sleep 2` silently declared success even when backend crashed; new target polls `/health` for 15 s and exits non-zero on failure. `conda run --no-capture-output` gives live log streaming |
| 2026-04-19 | `feat(frontend)` `dd09e20` — `BackendUnreachableModal` matching Figma Variant D | Users previously saw a generic "Upload failed" toast with no context; modal surfaces the real issue and offers a Retry button that probes `/health` |
| 2026-04-20 | PR #1 — orphan cleanup script (`cleanup_orphans.py`) | One-shot migration that deleted dangling Pinecone vectors with no matching SQLite document row; script then removed — no longer runnable or needed |
| 2026-04-20 | PR #2 — SQLite foundation (SQLAlchemy 2.x + Alembic) | Replaced Redis as the document registry; `data/finsight.db` holds users, workspaces, workspace_members, documents, chat_sessions; `alembic upgrade head` bootstraps the schema |
| 2026-04-20 | PR #3 — multi-tenant storage refactor (`StorageTransaction`, `RequestContext`, namespace-per-workspace) | Pinecone default namespace retired; each workspace gets `namespace = workspace_id` (`wks_default` in v1). `StorageTransaction` makes SQLite + Pinecone + disk writes atomic with compensating actions. `RequestContext(user_id, workspace_id)` threaded through every route via FastAPI dependency. File layout reorganized to `data/uploads/{workspace_id}/{doc_id}.{ext}` |
| 2026-04-20 | PR #4 — Redis removed; `SqliteSaver` adopted; `mcp_memory_write/read` deleted | No Docker required for local dev. `langgraph-checkpoint-sqlite` replaces `langgraph-checkpoint-redis`. Redundant MCP memory tools removed — LangGraph state is single source of truth for messages. `make start/stop/doctor/status` no longer mention Redis |
| 2026-04-20 | PR #5 — Workspace CRUD + UI (`POST/GET/PATCH /workspaces/`, `WorkspaceSwitcher`, `CreateWorkspaceModal`) | Multi-workspace support required isolated Pinecone namespaces per workspace. `RequestContext` dependency reused — no new middleware. Auto-switch-on-create UX closes the modal and re-renders all panels to the new workspace. Seeded-defaults Alembic migration (`16ece49d77a9`) handles fresh-clone bootstrap via `INSERT OR IGNORE`. Returns 404 (not 403) for workspaces owned by a different user to avoid leaking existence. |
| 2026-04-21 | PR #6 — KPI cache layer (`workspace_kpi_cache` SQLite table, `GET /kpis/`, 24h TTL, auto-invalidation on upload/delete) | Before this, 6 `POST /chat` calls on every page refresh triggered 12 Claude calls (~$9/day in dev). Cache short-circuits to `{status: "empty"}` for workspaces with 0 documents (0 Claude calls). Cache auto-invalidated on upload or document delete. `KPI_PROMPTS` kept short because long format instructions dominated Gemini embeddings → zero RAG chunks retrieved. |
| 2026-04-21 | PR #7 — KPI prose parser (`parse_kpi_response`, headline/period/note extraction) | KPI cards were rendering raw Claude markdown truncated at 120 chars. First attempt used format-instruction prompts (e.g. "respond with only the dollar amount") — broke RAG retrieval because the instruction tokens dominated the Gemini embedding and no relevant chunks were found. Pivoted to parse-on-read: store full Claude markdown, extract headline/period/note at read time via regex. Bails to `N/A` cleanly when no unit-qualified figure is found. |

## Known TODOs (Phase 6)

**Feature work remaining:**
- Excel/PDF export endpoints (`/models/export/xlsx`, `/models/export/pdf`) — unblocks the inert "Export Report" Studio button
- Cloud deployment (migrate secrets from `.env` to provider secret manager)

**Polish remaining:**
- `RightPanel.tsx` — migrate KPI Grid to `Grid2` (MUI v7 prep), currently `<Grid item xs={6}>`
- `dashboardStore.ts` — populate `change` and `favorable` from prior-period comparison query
- Add `aria-label` to icon-only buttons (collapsed panel rails)

**Infra hardening — ✅ DONE 2026-04-19 → 2026-04-20:**
- ~~SecretStr masking of all API keys~~
- ~~Empty-env-shadow filter in `get_settings()`~~
- ~~`make doctor` diagnostic target~~
- ~~Health-gated `make start` (replace blind `sleep 2`)~~
- ~~Log redirection to `logs/backend.log` + `logs/frontend.log`~~
- ~~Backend-unreachable modal dialog in frontend~~
- ~~SQLite control plane (SQLAlchemy + Alembic) replacing Redis document registry~~
- ~~Multi-tenant scaffolding (RequestContext, StorageTransaction, namespace-per-workspace)~~
- ~~Redis removed; Docker no longer required for local dev~~

**Workspace + KPI — ✅ DONE 2026-04-20 → 2026-04-21:**
- ~~Workspace CRUD + UI (POST/GET/PATCH /workspaces/, WorkspaceSwitcher, CreateWorkspaceModal)~~
- ~~KPI cache layer (workspace_kpi_cache, GET /kpis/, 24h TTL, auto-invalidation)~~
- ~~KPI response parser (parse_kpi_response, headline/period/note extraction)~~

---

## Operational Gotchas (lessons learned 2026-04-17 → 2026-04-19)

Durable knowledge harvested from a real debug-and-harden cycle. These are the things you'd otherwise only know by re-breaking the system.

### Backend startup & environment

- **Claude Code subshells export `ANTHROPIC_API_KEY=""`** (empty string) as a security measure. With the default pydantic-settings precedence (OS env > `.env`), this empty value silently shadows the real key and the backend fails to start with `AssertionError: ANTHROPIC_API_KEY is not set in .env`. Handled by `_strip_empty_shadow_env()` in `backend/core/config.py` which removes empty sensitive vars from `os.environ` before `Settings()` construction. Same protection now applies if any other parent process does the same thing.
- **`pydantic.SecretStr` is mandatory for every API-key field.** A plain `str` field will appear in clear text inside `repr(Settings)`, which pytest dumps on any assertion failure. Real-world consequence: seven keys leaked into a session transcript in the 2026-04-19 incident. SecretStr makes this class of leak impossible — `.get_secret_value()` is required only at the point of SDK construction.

### SQLite control plane

- **`data/finsight.db` is the single file** holding users, workspaces, workspace_members, documents, chat_sessions, and LangGraph checkpoints. WAL mode + foreign-key pragmas are enabled by the engine at startup.
- **Schema is managed by Alembic.** First-time setup: `alembic upgrade head`. To inspect the current migration state: `alembic current`. To reset entirely: `rm data/finsight.db && alembic upgrade head`.
- **Backups are a file copy.** `cp data/finsight.db backup.db` is sufficient; SQLite supports hot copies in WAL mode.
- **Not safe for multiple concurrent writers.** Fine for a single backend instance on localhost. When moving to cloud, migrate to Postgres (SQLAlchemy connection string swap + new Alembic migrations).
- **Docker is no longer required for local dev.** No container management, port mapping, or docker run needed.
- **After deleting `finsight.db`** (e.g., `make install` or manual reset), Pinecone vectors in `wks_default` namespace survive but the SQLite documents table is empty, so the Sources panel will show nothing. Re-upload documents or restore from backup to reconcile.

*Historical note (pre-2026-04-20):* Redis was used as the document registry (`finsight:documents` JSON array, `WATCH`/`MULTI` for atomicity) and for LangGraph checkpointing (`langgraph-checkpoint-redis`). Both are now replaced by SQLite. The Redis gotchas below in the decision log are kept for historical context only — Redis is no longer in the stack.

### Gemini embeddings (`google-generativeai` 0.8.3)

- **Batch embed responses use a *singular* key.** `genai.embed_content(content=[...])` returns `{"embedding": [[vec1], [vec2], ...]}` — same `"embedding"` key as single-text calls, value is list-of-lists. Historical mocks in `test_gemini_batch.py` used the (non-existent) plural `"embeddings"` key and masked this for months.
- **No client-side batching or retry in `embed_texts()`.** A 10-K produces ~1200 chunks; the whole list goes in one API call. Not a problem for filings we've tested, but if you ever add a larger document or get rate-limited, the fix is chunked batches of ~50 in `gemini_client.py`.

### Makefile / `make start`

- **`conda run --no-banner` is not supported on older conda versions** (pre-23.9). Use `conda run --no-capture-output` instead — it's older (conda 4.9+) and also solves the stdout-buffer-until-exit problem.
- **`conda run` without `--no-capture-output` buffers stdout**, so redirected logs (`> logs/backend.log`) appear empty while the process is running. This is not a broken redirect — the data is sitting in conda's subprocess buffer waiting for the child to exit.
- **The old `sleep 2` in `make start` was a silent-failure mask.** If uvicorn crashed during startup, `sleep 2` finished, make declared success, and the user saw a healthy frontend with a dead backend. Replaced with a 15-s `/health` polling loop that fails loudly on timeout.

### Frontend ergonomics

- **"Upload failed" with no detail means no HTTP response came back**, not a validation error. `LeftPanel.handleUpload` reads `err.response.data.detail`; when the response object doesn't exist (ERR_NETWORK), the fallback string is literal `"Upload failed"`. The `BackendUnreachableModal` now preempts this by detecting `ERR_NETWORK` in the axios interceptor and showing a targeted modal instead.
- **axios `response` interceptors run on 2xx AND errors.** The `connectionStore.backendUnreachable` flag is updated in both branches: cleared on any HTTP response (even 4xx/5xx — those prove the backend is alive), set only when `!error.response` or `error.code === 'ERR_NETWORK'`.

### Debugging discipline

- **`make doctor` first, always.** It surfaces the most common failure modes in < 2 seconds (SQLite db exists, port 8000, `/health`, port 5173, `.env` keys). Trying to diagnose without it wastes 20 minutes clicking around.
- **When a 500 comes back from `/documents/upload`, the stack trace lives in `logs/backend.log`.** The JSON error body is useless; the traceback is not.
- **Never share, screenshot, or paste `.env` contents or any `print(settings)` / `repr(settings)` output.** SecretStr now protects the latter, but discipline matters. Any Settings-like dict must explicitly `.get_secret_value()` the field — or better, leave the masked value in place.

### KPI cache invalidation

- **24h TTL + explicit invalidation.** `workspace_kpi_cache` rows are auto-deleted after successful `upload_document` or `remove_document` for that workspace. No manual cache flush is needed.
- **Cache hits fire zero Claude calls.** `GET /kpis/` returning `cache_hit: true` does not touch the LangGraph orchestrator. The `computedAt` timestamp tells you when the cache was last populated.
- **First view of a new workspace with documents costs ~12 Claude calls (~$0.30).** Cache is cold; the 6 KPI prompts each go through classify_intent + generate_response. Subsequent page refreshes within 24h are free.
- **Empty workspace fires zero Claude calls.** `GET /kpis/` short-circuits to `{status: "empty"}` when the workspace has 0 documents, before any LLM is invoked.
- **The parser is defensive.** `parse_kpi_response()` extracts headline/period/note from natural Claude markdown via regex. Format-instruction prompts were tried first (e.g. "respond with only the dollar amount") but they dominated the Gemini embedding for RAG retrieval — zero chunks were returned. Parse-on-read avoids this entirely.
- **If KPI cards show raw markdown**, hard-refresh the browser (Cmd+Shift+R) to pick up the latest frontend bundle.

### Deferred / known-unknowns

- **Chat responses occasionally report "N uncited claims"** from `mcp_citation_validator`. The main numbers are cited but detail-rows in markdown tables aren't individually tagged. Prompt-engineering fix, not a pipeline bug.
- **Legacy Pinecone vectors** (uploaded pre-refactor) use random UUID chunk IDs rather than the new `<doc_id>:<NNNN>` format. Both formats coexist and are queryable; no reindex required unless you need deterministic IDs throughout.

---

## Cheatsheet (common commands)

Commands worth muscle-memorising. All assume `cwd = finsight-cfo/`.

```bash
# ── Health & diagnostics ────────────────────────────────────────────────────
make doctor                                                 # first-line diagnosis
make status                                                 # quick snapshot
curl -sf http://localhost:8000/health | python3 -m json.tool

# ── Logs ────────────────────────────────────────────────────────────────────
tail -f logs/backend.log
tail -f logs/frontend.log

# ── Find / kill a process on a port ─────────────────────────────────────────
lsof -iTCP:8000 -sTCP:LISTEN                                # what owns 8000?
pkill -f 'uvicorn backend.api.main:app'                     # stop backend
pkill -f vite                                               # stop frontend

# ── SQLite (control plane) ───────────────────────────────────────────────────
sqlite3 data/finsight.db '.schema'                          # inspect full schema
sqlite3 data/finsight.db 'SELECT * FROM workspaces;'        # quick workspace query
sqlite3 data/finsight.db 'SELECT id, name, chunk_count FROM documents;'
alembic upgrade head                                        # apply pending migrations
alembic current                                             # show current migration head
cp data/finsight.db backup.db                               # manual backup
make stats                                                  # Pinecone + SQLite cross-check

# ── Smoke tests via curl ────────────────────────────────────────────────────
# Upload a document (useful when the UI is broken)
curl -s -X POST http://localhost:8000/documents/upload \
  -F "file=@/absolute/path/to/doc.pdf" \
  -F "doc_type=10-K" -F "fiscal_year=2025"

# Chat (remember: field is `message`, not `query`)
curl -s -X POST http://localhost:8000/chat/ \
  -H 'Content-Type: application/json' \
  -d '{"message":"What was total revenue?","session_id":"debug-01"}' \
  | python3 -m json.tool

# Workspaces
curl -s http://localhost:8000/workspaces/ | python3 -m json.tool

# KPIs (cache hit returns cache_hit: true and fires zero Claude calls)
curl -s http://localhost:8000/kpis/ | python3 -m json.tool
curl -s 'http://localhost:8000/kpis/?refresh=true' | python3 -m json.tool  # force refresh

# ── Tests ───────────────────────────────────────────────────────────────────
conda run -n finsight pytest backend/tests/ -v -k "not integration"   # 282 unit
conda run -n finsight pytest backend/tests/ -v -m integration          # integration tests

# ── Start backend directly (bypass make when debugging the Makefile itself) ─
PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/uvicorn \
  backend.api.main:app --port 8000
```

---

## Security Incidents

| Date | Incident | Scope | Remediation |
|------|----------|-------|-------------|
| 2026-04-19 | Plaintext API-key leak via pytest Settings dump | A monkeypatch-set empty `ANTHROPIC_API_KEY` triggered an assertion failure whose pytest output included the full `Settings(...)` repr — all 7 API keys (Anthropic, Gemini, Google, Pinecone, OpenAI, Groq, Grok) appeared in plaintext. Logged locally to this session's transcript at `~/.claude/projects/.../*.jsonl` (mode `600`, user-only). Also traversed Anthropic's API (normal trust boundary of using Claude Code). Not in git, not cloud-synced. | **Systemic fix shipped** as commit `608d58f`: all `*_api_key` fields typed as `SecretStr` so `repr(Settings)` now prints `SecretStr('**********')`. Regression tests added. **User action still pending**: rotate all 7 keys at the respective provider consoles to make the leaked values worthless; delete the session transcript file post-`/exit`. |
