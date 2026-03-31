# CLAUDE.md — FinSight CFO Assistant

## Project Vision

FinSight is a locally-deployed, RAG-powered financial intelligence assistant for Chief Financial Officers. It ingests financial documents (10-K/10-Q filings, income statements, balance sheets, cash flow statements, board reports, budgets), builds a semantic vector index, and deploys specialized AI agents to answer natural-language questions, generate financial models, run scenario analyses, and produce boardroom-ready outputs.

This is not a generic chatbot. It is a domain-specific financial intelligence layer that gives the CFO instant, cited, model-backed answers: cash runway, covenant compliance, margin trends, variance analysis, and strategic planning.

**Target user:** A Chief Financial Officer who interacts through a clean, professional web interface.

---

## Architecture

```
React + TypeScript Frontend (MUI v6)
        │ REST API + SSE
FastAPI Backend Server
  ├── LangGraph Orchestrator (StateGraph)
  │     ├── Intent Classifier → Conditional Routing
  │     ├── RAG Agent Node
  │     ├── Financial Modeling Node
  │     ├── Scenario Analysis Node
  │     └── Response Generator (with citation validation)
  ├── Skills Layer (business logic)
  │     ├── document_ingestion.py
  │     ├── vector_retrieval.py
  │     ├── financial_modeling.py
  │     └── scenario_analysis.py
  ├── MCP Server (26 registered tools)
  └── Infrastructure
        ├── Pinecone (vector store, dim=3072, cosine)
        ├── Redis (session memory + document tracking)
        └── Gemini (embeddings)
```

---

## Tech Stack (Actual — not the original spec)

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | Python 3.13, FastAPI | conda env `finsight` |
| Agent Orchestration | **LangGraph** (StateGraph) | Chosen over hand-rolled agents to avoid vendor lock-in |
| LLM | Anthropic Claude (claude-sonnet-4-6) | via `langchain-anthropic` |
| Embeddings | Google Gemini `gemini-embedding-001` | 3072 dimensions |
| Vector Store | **Pinecone** (serverless, cosine) | Replaced FAISS from original spec |
| Memory | Redis (Docker) + LangGraph checkpointer | Session memory via `langgraph-checkpoint-redis` |
| Tool Protocol | MCP via `mcp` Python SDK (FastMCP) | 26 tools registered |
| Frontend | React 18 + TypeScript + Vite | |
| UI Components | MUI v6 — exclusively | No Tailwind, Bootstrap, Chakra, or custom CSS frameworks |
| State Management | Zustand | |
| HTTP Client | Axios (REST), native fetch (SSE) | |
| Charts | Plotly (react-plotly.js) | |
| Config | pydantic-settings + `.env` | |
| Package Management | conda (backend), npm (frontend) | NOT venv — user prefers conda |

### Deviations from Original Design Document

- **Pinecone replaces FAISS** — serverless, no local index management
- **LangGraph replaces hand-rolled orchestration** — avoids vendor lock-in, built-in checkpointing
- **`langchain-anthropic` replaces direct `anthropic` SDK** — required for LangGraph ChatAnthropic integration
- **Gemini `gemini-embedding-001` replaces `text-embedding-004`** — user's choice, 3072 dim
- **`_compute_single_ratio` removed** — was dead code, prior-period comparison not yet needed

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1 — Foundation** | DONE | Project scaffold, FastAPI, config, Pinecone/Redis/Gemini clients, BaseAgent, MCP server scaffold |
| **Phase 2 — Ingestion & RAG** | DONE | PDF/CSV parsing, hierarchical chunking, Gemini embedding, Pinecone upsert/search, MMR reranking |
| **Phase 3 — Financial Modeling** | DONE | DCF, ratio scorecard, forecasting, variance analysis, scenario/sensitivity/covenants/runway |
| **Phase 4 — Agent Integration** | DONE | LangGraph orchestrator, intent routing, 5 agent nodes, Redis checkpointing, SSE streaming, audit logging |
| **Code Review Fixes** | DONE | 4 critical + 7 important issues fixed (security, financial correctness, orchestrator wiring, async) |
| **Phase 5 — Frontend** | DONE | React + MUI MVP: Dashboard (KPI cards), Chat (SSE streaming + citations), Documents (DataGrid + upload) |
| **Phase 6 — Output & Polish** | NOT STARTED | Excel/PDF generation, packaging, final polish |

---

## Key Constraints & Non-Negotiables

1. **Zero hallucination on numbers** — Every financial figure must be traceable to a retrieved chunk. The `mcp_citation_validator` runs on every response.
2. **Citation enforcement** — Every factual claim needs `[Source: doc_name, section, page]`. The response generator appends warnings for uncited claims.
3. **MUI exclusively** — No Tailwind, Bootstrap, Chakra UI, or custom CSS frameworks. All UI from MUI v6.
4. **Streaming responses** — All Claude responses stream to frontend via SSE. No waiting for full response before display.
5. **Insufficient data flagging** — Every financial model checks inputs and flags when data is insufficient rather than silently producing unreliable output.
6. **Local-first** — Everything runs on localhost. No cloud deployment. Pinecone is the only external service.
7. **Audit trail** — `mcp_response_logger` and `mcp_intent_log` write every interaction to `audit_log.jsonl`.
8. **Environment security** — API keys in `.env`, loaded via pydantic-settings. Never hardcoded or committed.
9. **Professional output quality** — All outputs must be boardroom-ready. The CFO should be able to present them directly.
10. **File upload security** — Filenames sanitized (path traversal prevention), 50MB size limit, supported types only (.pdf, .csv, .txt, .html).

---

## Backend API Surface (13 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Service health check (Redis, Pinecone, API keys) |
| POST | `/chat/` | Chat message → full response (non-streaming) |
| POST | `/chat/stream` | Chat message → SSE stream (token-level updates) |
| POST | `/documents/upload` | Upload + parse + chunk + embed + index a document |
| GET | `/documents/` | List all ingested documents |
| DELETE | `/documents/{doc_id}` | Delete document + vectors |
| POST | `/models/dcf` | Run DCF model |
| POST | `/models/ratios` | Run ratio scorecard |
| POST | `/models/forecast` | Run forecast model |
| POST | `/models/variance` | Run variance analysis |
| POST | `/models/save` | Persist model output to JSON |
| POST | `/scenarios/run` | Run bull/base/bear scenarios |
| POST | `/scenarios/sensitivity` | Build 2D sensitivity table |
| POST | `/scenarios/covenants` | Stress test covenant thresholds |
| POST | `/scenarios/runway` | Calculate cash runway |

Backend runs at: `PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000`

---

## Frontend Design Decisions (Phase 5 MVP)

### Scope
- **3 pages for MVP:** Dashboard, Chat, Documents
- Model Studio, Scenario Planner, Reports deferred to Phase 6 or later
- APIs for models/scenarios remain accessible from the Chat interface

### Visual Style
- **Dark mode default** with light/dark toggle (persisted to localStorage)
- **Purple accent** (`#7c4dff`), green for favorable (`#00e676`), red for unfavorable (`#ff5252`)
- Modern SaaS aesthetic (Notion/Linear feel), rounded corners (12px)
- Inter or system font stack

### Layout
- Persistent collapsible sidebar (240px expanded / 64px collapsed)
- Sidebar: FinSight logo, 3 nav items, theme toggle at bottom
- Main content area fills remaining width
- React Router: `/dashboard`, `/chat`, `/documents` (root redirects to `/dashboard`)

### Page Designs

**Dashboard (`/dashboard`):**
- 6 KPI cards (Revenue, Gross Margin, EBITDA, Net Income, Cash Balance, Runway)
- KPIs auto-populated by firing background `/chat` queries after documents are ingested
- Cached in `dashboardStore` to avoid re-fetching on navigation
- Skeleton loading while queries in flight
- Empty state when no documents: "Upload financial documents to populate KPIs"
- Quick-action buttons: Ask a Question, Upload Documents

**Chat (`/chat`):**
- Full-height chat with message bubbles (assistant left, user right)
- Markdown rendering for assistant messages (tables, lists, bold)
- Inline citation chips: `[Source: ...]` rendered as purple MUI Chips
- SSE streaming via native fetch (not Axios)
- Thinking indicator updated by SSE event types (classifying → retrieving → generating)
- Session persistence via LangGraph checkpointer (thread_id in localStorage)
- "New Chat" button resets session

**Documents (`/documents`):**
- Header with title + "+ Upload" button
- Search input for client-side filtering
- MUI DataGrid: Name, Type, Year, Chunks, Status, Actions (delete with confirmation)
- Upload dialog: file picker, doc_type dropdown, fiscal_year field
- Progress indicator during upload processing

### Component Architecture
- **Page-first build** — shared shell (theme + sidebar + Axios) first, then pages end-to-end
- **Organic component library** — extract reusable components into `components/common/` as they naturally emerge across pages (not speculated upfront)

### Zustand Stores
- `sessionStore` — session_id, theme mode, sidebar collapsed state
- `chatStore` — messages, isStreaming, currentIntent, sendMessage(), clearChat()
- `documentStore` — documents list, loading, fetchDocuments(), uploadDocument(), deleteDocument()
- `dashboardStore` — KPI values, loading, lastUpdated, fetchKPIs()

---

## File Structure

```
finsight-cfo/
├── backend/
│   ├── agents/                  # LangGraph orchestrator + state
│   ├── api/routes/              # FastAPI endpoints
│   ├── core/                    # Config, clients (Gemini, Pinecone, Redis)
│   ├── skills/                  # Business logic (parsing, retrieval, modeling, scenarios)
│   ├── mcp_server/tools/        # MCP tool implementations
│   ├── tests/                   # 224 unit + 23 integration tests
│   ├── .env                     # Secrets (never committed)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/               # Dashboard.tsx, Chat.tsx, DocumentManager.tsx
│   │   ├── components/
│   │   │   ├── layout/          # Sidebar.tsx, TopBar.tsx
│   │   │   ├── chat/            # ChatBubble.tsx, CitationChip.tsx, StreamingIndicator.tsx
│   │   │   └── common/          # Extracted reusable components (grows organically)
│   │   ├── stores/              # Zustand stores
│   │   ├── api/                 # axiosClient.ts
│   │   ├── theme/               # muiTheme.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── tsconfig.json
├── CLAUDE.md                    # This file
└── README.md
```

---

## Coding Conventions

### Backend (Python)
- **Type hints everywhere** — all function signatures typed
- **pydantic models** for all API request/response bodies
- **Skills hold business logic** — MCP tools are thin wrappers, API routes are thin wrappers
- **No bare except** — always catch specific exceptions or log with `logger.exception()`
- **Async at boundaries** — `asyncio.to_thread()` for blocking calls in async handlers
- **Redis pipelines** for any read-modify-write operations (atomic document tracking)
- **Test naming:** `test_<what>_<condition>` (e.g., `test_dcf_warns_when_wacc_below_terminal`)

### Frontend (TypeScript/React)
- **Functional components only** — no class components
- **MUI v6 exclusively** — all styling via MUI `sx` prop or `styled()`. No raw CSS files.
- **Zustand for state** — one store per domain, no prop drilling
- **Axios for REST, native fetch for SSE** — Axios doesn't handle SSE well
- **TypeScript strict mode** — no `any` types except when interfacing with external JSON
- **Component files:** one component per file, named export matching filename

### Git
- **Conventional commits:** `feat:`, `fix:`, `chore:`, `docs:`, `perf:`, `test:`
- **Never commit:** `.env`, `node_modules/`, `__pycache__/`, `backend/data/`, `backend/storage/`
- **Never force push to main**

---

## Running the Project

### Prerequisites
- Python 3.11+ via conda
- Node.js 18+
- Docker (for Redis)
- API keys: Anthropic, Google Gemini, Pinecone

### Start Services
```bash
# Redis
docker start redis-finsight  # or: docker run -d --name redis-finsight -p 6379:6379 redis:alpine

# Backend
cd finsight-cfo
conda activate finsight
PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000

# Frontend (when built)
cd frontend
npm run dev
```

### Run Tests
```bash
cd backend
conda run -n finsight pytest tests/ -v -k "not integration"     # unit tests (224)
conda run -n finsight pytest tests/ -v -m integration           # integration tests (23)
```

---

## Decision Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-31 | Pinecone over FAISS | Serverless, no local index management |
| 2026-03-31 | conda over venv | User preference |
| 2026-03-31 | LangGraph over Anthropic Agent SDK | Avoid vendor lock-in |
| 2026-03-31 | MVP: 3 pages (Dashboard, Chat, Documents) | Ship working UI faster, other pages later |
| 2026-03-31 | Dark mode default + toggle | Modern SaaS aesthetic, user choice |
| 2026-03-31 | Inline citation chips | Keep CFO's eye on source without breaking flow |
| 2026-03-31 | KPIs via background chat queries | No dedicated KPI endpoint needed, leverages existing RAG |
| 2026-03-31 | Page-first build + organic component library | See working UI sooner, extract components as they emerge |
