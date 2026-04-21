# FinSight CFO Assistant

A locally-deployed, RAG-powered financial intelligence assistant for CFOs. Ingests financial documents (10-K/10-Q filings, income statements, balance sheets, cash flow statements, board reports, budgets), builds a semantic vector index, and deploys specialized AI agents to answer natural-language questions, generate financial models, run scenario analyses, and produce boardroom-ready outputs — with every number citation-traced to the source chunk.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React 18 + TypeScript + MUI v6 — 3-panel shell (no routing)    │
│     Sources (Left)  │  Chat (Center)  │  Studio/KPIs (Right)    │
│     BackendUnreachableModal at root (flips on ERR_NETWORK)      │
└───────────────────────────────┬─────────────────────────────────┘
                        REST + SSE
┌───────────────────────────────▼───────────────────────────────── ┐
│                  FastAPI Backend (Python 3.13)                   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │   LangGraph Orchestrator — 7-node StateGraph               │  │
│  │                                                            │  │
│  │   classify_intent → route_by_intent                        │  │
│  │      ├─ rag_retrieve (Gemini embed → Pinecone → MMR)       │  │
│  │      ├─ financial_model  (DCF, ratios, forecast, variance) │  │
│  │      ├─ scenario_analysis (bull/base/bear, sensitivity,    │  │
│  │      │                     covenants, runway)              │  │
│  │      └─ generate_response (citation-validated markdown)    │  │
│  │                                                            │  │
│  │   SqliteSaver checkpointer per session_id                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │ 
│  │  Skills Layer: ingestion · retrieval · modeling · scenarios│  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  MCP Server (26 tools: citation validator, audit logger…)  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────┐  ┌───────────────────┐  ┌─────────────┐    │
│  │  Pinecone        │  │  SQLite           │  │  File Store │    │
│  │  (3072-dim,      │  │  (data/finsight   │  │  data/      │    │
│  │   cosine;        │  │   .db: workspaces,│  │  uploads/   │    │
│  │   namespace per  │  │   documents, chkp)│  │  {wks}/{doc}│    │
│  │   workspace)     │  └───────────────────┘  └─────────────┘    │
│  └──────────────────┘                                            │
└──────────────────────────────────────────────────────────────────┘
```

API surface: `/health` · `/chat/` · `/chat/stream` · `/documents/*` · `/workspaces/*` · `/kpis/` · `/models/*` · `/scenarios/*`

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.13, FastAPI |
| Agent Orchestration | LangGraph (StateGraph, conditional routing, SqliteSaver checkpoint) |
| LLM | Anthropic Claude `claude-sonnet-4-6` (via `langchain-anthropic`) |
| Embeddings | Google Gemini `gemini-embedding-001` (3072-dim) |
| Vector Store | Pinecone (serverless, cosine; namespace per workspace) |
| Control Plane | SQLite (`data/finsight.db`) + SQLAlchemy 2.x + Alembic |
| Tool Protocol | MCP via `mcp` SDK (FastMCP) — 26 tools |
| Frontend | React 18 + TypeScript + Vite + MUI v6 |
| State | Zustand (5 stores; `sessionStore` persisted to localStorage) |
| Transport | Axios (REST), native fetch (SSE) |
| Charts | Plotly (`react-plotly.js`) |
| Config | `pydantic-settings` with `SecretStr` for all API keys |
| Env mgmt | conda (backend), npm (frontend) |

## Capabilities (current)

- **Document ingestion** — PDF/CSV/TXT/HTML up to 50 MB; hierarchical chunking (512-token sections + 64-token overlap, 128-token row chunks) with financial-value normalization (`$1,234` / `(42)` → `1234` / `-42`)
- **Semantic retrieval** — query embedding → Pinecone top-8 → MMR rerank → top-5 context chunks
- **Financial modeling** — DCF valuation, ratio scorecard, forecast model, variance analysis
- **Scenario analysis** — bull/base/bear, 2D sensitivity tables, covenant stress tests, cash runway
- **Streaming chat** — token-level SSE, citation validation on every factual claim, audit logging to `audit_log.jsonl`
- **3-panel UI** — collapsible Sources / Chat / Studio panels, 6 KPI cards (Revenue, Gross Margin, EBITDA, Net Income, Cash Balance, Runway), 4 Quick Action buttons
- **Multi-workspace support** — create/switch/archive workspaces; Pinecone namespace per workspace guarantees document isolation
- **KPI dashboard with SQLite caching** — 24h TTL, auto-invalidation on document upload/delete, 0 Claude calls on cache hits
- **KPI headline parser** — regex-extracts clean `$X.XB · FYxxxx · ±X%` from Claude's full markdown analysis for compact card display
- **Operational resilience** — health-gated startup, `make doctor` diagnostics, backend-unreachable modal, `SecretStr`-masked config, empty-env-shadow protection against parent shells that export `ANTHROPIC_API_KEY=""`

## Prerequisites

- **Python 3.13** via conda
- **Node.js 18+**
- **API keys:** Anthropic, Google Gemini, Pinecone

## Quick Start

```bash
git clone https://github.com/AarvinGeorge/cfo-assistant.git
cd cfo-assistant
cp backend/.env.example backend/.env    # then add your API keys

# Create Pinecone index in the console:
#   name: finsight-index, dim: 3072, metric: cosine, type: serverless

make install    # conda env + pip install + alembic upgrade head + npm install
make start      # backend (health-gated) + frontend — no Docker required
```

`make start` polls `GET /health` for up to 15 s before declaring the backend ready. If it fails to come up, the last 20 lines of `logs/backend.log` are tailed and make exits non-zero — so silent failures are impossible.

Open **http://localhost:5173**.

### Daily workflow

```bash
make start     # bring everything up
make status    # one-shot snapshot
make doctor    # diagnose any issue (SQLite db, port 8000, /health, port 5173, .env keys, env binary + PATH shadow)
make stop      # terminate all services
tail -f logs/backend.log logs/frontend.log
```

## Manual Setup (fallback if `make` isn't available)

```bash
# 1. Backend
conda create -n finsight python=3.13 -y
conda activate finsight
pip install -r backend/requirements.txt
alembic upgrade head                       # creates data/finsight.db
PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend && npm install && npm run dev   # localhost:5173

# 3. Verify
curl -sf http://localhost:8000/health | python3 -m json.tool
# → {"status": "ok", "sqlite": true, "pinecone": true, "anthropic_key": true, "gemini_key": true}
```

## Testing

```bash
# Unit tests (282 tests, no external services)
conda run -n finsight pytest backend/tests/ -v -k "not integration"

# Integration tests (requires Pinecone + live API keys)
conda run -n finsight pytest backend/tests/ -v -m integration
```

## Project Structure

```
finsight-cfo/
├── backend/
│   ├── agents/
│   │   ├── base_agent.py          # Abstract base class
│   │   ├── graph_state.py         # AgentState TypedDict for LangGraph
│   │   └── orchestrator.py        # 7-node StateGraph + intent routing
│   ├── api/
│   │   ├── main.py                # FastAPI app with startup validation
│   │   └── routes/                # health · documents · chat · models · scenarios
│   │                              #   workspaces · kpis (KPI_PROMPTS, parse_kpi_response)
│   ├── core/
│   │   ├── config.py              # SecretStr Settings + empty-env-shadow strip
│   │   ├── context.py             # RequestContext (user_id, workspace_id) dependency
│   │   ├── transactions.py        # StorageTransaction (atomic SQLite+Pinecone+disk)
│   │   ├── gemini_client.py       # Gemini embedding wrapper (batch singular key)
│   │   └── pinecone_store.py      # Pinecone client with dim validation + namespace support
│   ├── db/
│   │   ├── engine.py              # SQLAlchemy engine (WAL + foreign keys)
│   │   ├── models.py              # ORM: User, Workspace, Document, ChatSession,
│   │   │                          #   WorkspaceKpiCache
│   │   └── migrations/            # Alembic version scripts
│   ├── skills/
│   │   ├── document_ingestion.py  # PDF/CSV parsing + hierarchical chunking
│   │   ├── vector_retrieval.py    # Semantic search + MMR reranking
│   │   ├── financial_modeling.py  # DCF, ratios, forecast, variance
│   │   └── scenario_analysis.py   # Scenarios, sensitivity, covenants, runway
│   ├── mcp_server/
│   │   ├── financial_mcp_server.py # 26 registered tools
│   │   └── tools/                  # Tool implementations by domain
│   ├── scripts/
│   │   ├── migrate_to_workspace_schema.py  # One-time data migration
│   │   └── stats.py                        # Pinecone + SQLite cross-reference
│   ├── tests/                      # 282 unit tests
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── panels/            # LeftPanel · CenterPanel · RightPanel
│       │   ├── chat/              # ChatBubble · CitationChip · StreamingIndicator
│       │   ├── common/            # BackendUnreachableModal (Figma Variant D)
│       │   └── workspace/         # WorkspaceSwitcher · CreateWorkspaceModal
│       ├── stores/                # sessionStore · chatStore · documentStore
│       │                          #   dashboardStore · connectionStore · workspaceStore
│       ├── api/axiosClient.ts     # interceptor flips connectionStore on ERR_NETWORK
│       ├── theme/muiTheme.ts      # dark + light themes with design tokens
│       ├── App.tsx                # 3-panel shell + <BackendUnreachableModal />
│       └── main.tsx
├── data/
│   ├── finsight.db                # SQLite control plane (gitignored)
│   └── uploads/                   # {workspace_id}/{doc_id}.{ext} (gitignored)
├── alembic.ini                    # Alembic migration config
├── logs/                          # backend.log + frontend.log (gitignored)
├── Makefile                       # start / stop / status / doctor / stats / install
├── CLAUDE.md                      # Project source of truth (architecture, conventions,
│                                  #   operational gotchas, decision log)
└── README.md                      # This file
```

## Development Phases

- [x] **Phase 1 — Foundation:** FastAPI scaffold, config, Pinecone/Gemini clients, MCP scaffold (26 tool stubs)
- [x] **Phase 2 — Ingestion & RAG:** PDF/CSV parsing, hierarchical chunking, embedding, Pinecone upsert/search, MMR reranking
- [x] **Phase 3 — Financial Modeling:** DCF, ratio scorecard, forecasting, variance, scenarios, covenants, runway
- [x] **Phase 4 — Agent Integration:** LangGraph orchestrator, intent routing, SqliteSaver checkpointing, SSE streaming, audit logging
- [x] **Phase 5 — Frontend:** 3-panel NotebookLM-inspired layout (Sources │ Chat │ Studio), KPI dashboard, backend-unreachable modal
- [ ] **Phase 6 — Output & Polish (in progress):**
  - [x] SecretStr masking + empty-env-shadow protection
  - [x] `make doctor` diagnostic target
  - [x] Health-gated `make start` (replaces blind `sleep 2`)
  - [x] Log redirection to `logs/backend.log` + `logs/frontend.log`
  - [x] Backend-unreachable modal dialog
  - [x] SQLite control plane (SQLAlchemy + Alembic) — document registry, LangGraph checkpoints
  - [x] Multi-tenant scaffolding (RequestContext, StorageTransaction, namespace-per-workspace)
  - [x] Redis removed — no Docker required for local dev
  - [x] Multi-workspace CRUD + UI (`POST/GET/PATCH /workspaces/`, WorkspaceSwitcher, CreateWorkspaceModal)
  - [x] KPI cache layer (`workspace_kpi_cache`, `GET /kpis/`, 24h TTL, auto-invalidation)
  - [x] KPI response parser (`parse_kpi_response`, headline/period/note extraction)
  - [ ] Excel/PDF export endpoints (`/models/export/xlsx`, `/models/export/pdf`)
  - [ ] Cloud deployment (secrets → provider secret manager)

## Troubleshooting

When something's off, run **`make doctor`** first. It checks the most common failure modes in under 2 seconds: SQLite db exists, finsight env binary (and PATH shadow), port 8000, `/health`, port 5173, `.env` keys.

Common pitfalls (see `CLAUDE.md` § *Operational Gotchas* for the full list):

- **`data/finsight.db` missing** → run `alembic upgrade head` (or `make install`) to create the schema. The Sources panel will be empty until documents are uploaded.
- **Backend crashes on `ModuleNotFoundError: No module named 'fastapi'`** → a system-Python `uvicorn` is shadowing the conda env on PATH. The Makefile pins the absolute path (`$HOME/miniconda3/envs/finsight/bin/uvicorn`), so `make start` is safe; `make doctor` flags the shadow informationally.
- **`ANTHROPIC_API_KEY is not set` even though `.env` has it** → a parent shell exported `ANTHROPIC_API_KEY=""`. `_strip_empty_shadow_env()` in `backend/core/config.py` handles this.
- **"Upload failed" with no detail in the UI** → a network-level failure (backend unreachable). The `BackendUnreachableModal` should surface this; if it doesn't, check `logs/backend.log`.
- **Chat responses flag "N uncited claims"** → prompt-engineering issue in markdown table rows, not a pipeline bug. Main figures are cited; detail rows aren't individually tagged.
- **Sources panel empty after deleting `finsight.db`** → Pinecone vectors survive but the documents table does not. Re-upload documents or restore from a backup (`cp backup.db data/finsight.db`).
- **KPI cards show raw markdown** → hard-refresh the browser (Cmd+Shift+R) to pick up the latest frontend bundle.

## Security

- API keys live in `backend/.env` (gitignored); **never** committed or hardcoded.
- All `*_api_key` fields on the `Settings` model are typed as `pydantic.SecretStr` so tracebacks, `repr(settings)`, and log dumps all render `SecretStr('**********')`. Real values are accessed only via `.get_secret_value()` at SDK-client construction sites.
- Uploaded filenames are sanitized; extension whitelist is `.pdf .csv .txt .html`; size cap is 50 MB.
- Audit trail of every intent classification and response is written to `audit_log.jsonl`.

## Further reading

- **`CLAUDE.md`** — authoritative architecture reference, coding conventions, decision log, and operational gotchas harvested from real debug cycles.
- **`docs/superpowers/plans/`** — phase-by-phase implementation plans.

## License

Private — not for redistribution.
