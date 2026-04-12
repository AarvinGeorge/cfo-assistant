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
  └── Infrastructure
        ├── Pinecone (vector store, dim=3072, cosine)
        ├── Redis (session memory + document tracking)
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
| Memory | Redis (Docker) + LangGraph checkpointer | `langgraph-checkpoint-redis` |
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
| Phase 1 — Foundation | ✅ DONE | FastAPI scaffold, config, Pinecone/Redis/Gemini clients, MCP scaffold |
| Phase 2 — Ingestion & RAG | ✅ DONE | PDF/CSV parsing, hierarchical chunking, embedding, Pinecone upsert/search, MMR |
| Phase 3 — Financial Modeling | ✅ DONE | DCF, ratio scorecard, forecasting, variance, scenarios, covenants, runway |
| Phase 4 — Agent Integration | ✅ DONE | LangGraph orchestrator, intent routing, Redis checkpointing, SSE streaming |
| Phase 5 — Frontend | ✅ DONE | 3-panel NotebookLM-inspired layout (Sources \| Chat \| Studio), KPI dashboard |
| Phase 6 — Output & Polish | ❌ NOT STARTED | Excel/PDF export, advanced UI pages, cloud deployment |

---

## Key Constraints & Non-Negotiables

1. **Zero hallucination on numbers** — every financial figure traced to a retrieved chunk via `mcp_citation_validator`
2. **Citation enforcement** — every factual claim needs `[Source: doc_name, section, page]`
3. **MUI exclusively** — no Tailwind, Bootstrap, Chakra UI, or custom CSS frameworks
4. **Streaming responses** — all Claude responses stream via SSE; no waiting for full response
5. **Insufficient data flagging** — models check inputs and flag when data is insufficient
6. **Local-first** — everything on localhost; Pinecone is the only external service
7. **Audit trail** — `mcp_response_logger` and `mcp_intent_log` write to `audit_log.jsonl`
8. **Environment security** — API keys in `.env`, never hardcoded or committed
9. **File upload security** — filenames sanitized, 50MB limit, types: `.pdf .csv .txt .html`

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

**Zustand stores:**
- `sessionStore` — `themeMode`, `leftPanelOpen`, `rightPanelOpen`, `sessionId` *(persisted to localStorage key: `finsight-session`)*
- `chatStore` — messages, isStreaming, currentIntent, sendMessage(), clearChat()
- `documentStore` — documents list, loading, fetchDocuments(), uploadDocument(), deleteDocument()
- `dashboardStore` — KPI values (populated by 6 background chat queries), loading, lastUpdated

**Design tokens** (`muiTheme.ts`):
- Dark bg: `#1C1C1E`, surface: `#2C2C2E`, elevated: `#3A3A3C`
- Accent: `#7c4dff`, favorable: `#00e676`, unfavorable: `#ff5252`
- `action.selected` wired to elevated token (`#3A3A3C`)

**KPI queries** — 6 background `POST /chat` calls on `RightPanel` mount:
Revenue, Gross Margin, EBITDA, Net Income, Cash Balance, Cash Runway

---

## Backend API Surface (15 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Service health (Redis, Pinecone, API keys) |
| POST | `/chat/` | Chat → full response (non-streaming) |
| POST | `/chat/stream` | Chat → SSE stream (token-level) |
| POST | `/documents/upload` | Upload + parse + chunk + embed + index |
| GET | `/documents/` | List all ingested documents |
| DELETE | `/documents/{doc_id}` | Delete document + vectors |
| POST | `/models/dcf` | DCF valuation |
| POST | `/models/ratios` | Ratio scorecard |
| POST | `/models/forecast` | Forecast model |
| POST | `/models/variance` | Variance analysis |
| POST | `/models/save` | Persist model output |
| POST | `/scenarios/run` | Bull/base/bear scenarios |
| POST | `/scenarios/sensitivity` | 2D sensitivity table |
| POST | `/scenarios/covenants` | Covenant stress test |
| POST | `/scenarios/runway` | Cash runway |

Backend: `PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000`

---

## File Structure (current)

```
finsight-cfo/
├── backend/
│   ├── agents/          # LangGraph orchestrator + graph_state.py
│   ├── api/routes/      # FastAPI endpoints
│   ├── core/            # config.py, gemini_client.py, pinecone_store.py, redis_client.py
│   ├── skills/          # document_ingestion, vector_retrieval, financial_modeling, scenario_analysis
│   ├── mcp_server/      # financial_mcp_server.py + tools/
│   ├── tests/           # 224 unit + 23 integration tests
│   ├── .env             # Secrets (never committed)
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── panels/  # LeftPanel.tsx, CenterPanel.tsx, RightPanel.tsx
│       │   └── chat/    # ChatBubble.tsx, CitationChip.tsx, StreamingIndicator.tsx
│       ├── stores/      # sessionStore, chatStore, documentStore, dashboardStore
│       ├── api/         # axiosClient.ts (baseURL: localhost:8000)
│       ├── theme/       # muiTheme.ts (dark + light themes)
│       ├── types/       # index.ts
│       ├── App.tsx      # 3-panel shell (LEFT_W=280, RIGHT_W=340, COLLAPSED_W=48)
│       └── main.tsx     # React entry point
├── data/uploads/        # Uploaded documents
├── CLAUDE.md
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
- Redis pipelines for atomic read-modify-write ops
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

```bash
# Redis
docker start redis-finsight

# Backend
conda activate finsight
PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev   # localhost:5173

# Tests
conda run -n finsight pytest tests/ -v -k "not integration"   # unit (224)
conda run -n finsight pytest tests/ -v -m integration          # integration (23)
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

## Known TODOs (Phase 6)

- `RightPanel.tsx` — migrate KPI Grid to `Grid2` (MUI v7 prep), currently `<Grid item xs={6}>`
- `dashboardStore.ts` — populate `change` and `favorable` from prior-period comparison query
- Add `aria-label` to icon-only buttons (collapsed panel rails)
- Excel/PDF export endpoints
- Cloud deployment
