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
| Phase 6 — Output & Polish | 🚧 IN PROGRESS | Infra hardening done (SecretStr, `make doctor`, health-gated `make start`, log redirection, backend-unreachable modal); Excel/PDF export + cloud deployment remain |

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
- `sessionStore` — `themeMode`, `leftPanelOpen`, `rightPanelOpen`, `sessionId` *(persisted to localStorage key: `finsight-session`)*
- `chatStore` — messages, isStreaming, currentIntent, sendMessage(), clearChat()
- `documentStore` — documents list, loading, fetchDocuments(), uploadDocument(), deleteDocument()
- `dashboardStore` — KPI values (populated by 6 background chat queries), loading, lastUpdated
- `connectionStore` — `backendUnreachable` flag, updated bidirectionally by the axios response interceptor (set on ERR_NETWORK, cleared on any HTTP response)

**Design tokens** (`muiTheme.ts`):
- Dark bg: `#1C1C1E`, surface: `#2C2C2E`, elevated: `#3A3A3C`
- Accent: `#7c4dff`, favorable: `#00e676`, unfavorable/error: `#ff5252`, success: `#10B964`
- `action.selected` wired to elevated token (`#3A3A3C`)

**KPI queries** — 6 background `POST /chat` calls on `RightPanel` mount:
Revenue, Gross Margin, EBITDA, Net Income, Cash Balance, Cash Runway

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

## Backend API Surface (15 endpoints)

| Method | Path | Purpose | Request body |
|--------|------|---------|---|
| GET | `/health` | Service health (Redis, Pinecone, API keys) | — |
| POST | `/chat/` | Chat → full response (non-streaming) | `{"message": "...", "session_id": "..."}` ⚠ field is `message`, not `query` |
| POST | `/chat/stream` | Chat → SSE stream (token-level) | Same as `/chat/` |
| POST | `/documents/upload` | Upload + parse + chunk + embed + index | `multipart/form-data` with `file`, `doc_type`, `fiscal_year` |
| GET | `/documents/` | List all ingested documents | — |
| DELETE | `/documents/{doc_id}` | Delete document + vectors | — |
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
| 6 | Upsert | `backend/skills/vector_retrieval.py` | `embed_and_upsert` (41–85) | Batches of 100 to Pinecone; metadata includes chunk `text`; not transactional |
| 7 | Redis register | `backend/mcp_server/tools/document_tools.py` | `register_document` (104–130) | Single key `finsight:documents` as JSON array; `WATCH`/`MULTI` for atomicity |
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
│   ├── api/routes/      # FastAPI endpoints (incl. health.py)
│   ├── core/            # config.py (SecretStr + env-shadow strip), gemini_client.py,
│   │                    #   pinecone_store.py, redis_client.py
│   ├── skills/          # document_ingestion, vector_retrieval, financial_modeling,
│   │                    #   scenario_analysis
│   ├── mcp_server/      # financial_mcp_server.py + tools/
│   ├── tests/           # 229 unit + 23 integration tests
│   ├── .env             # Secrets (never committed — *.env is gitignored)
│   ├── .env.example     # Template with placeholder values
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── panels/  # LeftPanel.tsx, CenterPanel.tsx, RightPanel.tsx
│       │   ├── chat/    # ChatBubble.tsx, CitationChip.tsx, StreamingIndicator.tsx
│       │   └── common/  # BackendUnreachableModal.tsx (blocking modal on ERR_NETWORK)
│       ├── stores/      # sessionStore, chatStore, documentStore, dashboardStore,
│       │                #   connectionStore
│       ├── api/         # axiosClient.ts (baseURL: localhost:8000 + interceptor
│       │                #   that flips connectionStore.backendUnreachable)
│       ├── theme/       # muiTheme.ts (dark + light themes)
│       ├── types/       # index.ts
│       ├── App.tsx      # 3-panel shell + <BackendUnreachableModal /> at root
│       └── main.tsx     # React entry point
├── data/uploads/        # Uploaded documents (gitignored)
├── logs/                # backend.log + frontend.log (gitignored via *.log)
├── Makefile             # start / stop / status / doctor / install targets
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

**Daily path (recommended):**
```bash
make start     # Redis + backend (health-gated) + frontend, logs captured to logs/
make doctor    # diagnose any issue — Redis, port 8000, /health, port 5173, .env keys
make status    # quick one-shot snapshot
make stop      # terminate all three services
```

`make start` polls `GET /health` for up to 15 s before declaring the backend ready; if it fails to come up it tails the last 20 lines of `logs/backend.log` and exits non-zero. The old blind `sleep 2` is gone. Follow live logs with `tail -f logs/backend.log` / `tail -f logs/frontend.log`.

**Manual path (if `make` isn't available):**
```bash
# Redis (docker must map the host port — see Operational Gotchas)
docker run -d --name redis-finsight -p 6379:6379 redis:alpine

# Backend
conda activate finsight
PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev   # localhost:5173
```

**Tests:**
```bash
conda run -n finsight pytest backend/tests/ -v -k "not integration"   # unit (229)
conda run -n finsight pytest backend/tests/ -v -m integration          # integration (23)
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

## Known TODOs (Phase 6)

**Feature work remaining:**
- Excel/PDF export endpoints (`/models/export/xlsx`, `/models/export/pdf`) — unblocks the inert "Export Report" Studio button
- Cloud deployment (migrate secrets from `.env` to provider secret manager)

**Polish remaining:**
- `RightPanel.tsx` — migrate KPI Grid to `Grid2` (MUI v7 prep), currently `<Grid item xs={6}>`
- `dashboardStore.ts` — populate `change` and `favorable` from prior-period comparison query
- Add `aria-label` to icon-only buttons (collapsed panel rails)

**Infra hardening — ✅ DONE 2026-04-19:**
- ~~SecretStr masking of all API keys~~
- ~~Empty-env-shadow filter in `get_settings()`~~
- ~~`make doctor` diagnostic target~~
- ~~Health-gated `make start` (replace blind `sleep 2`)~~
- ~~Log redirection to `logs/backend.log` + `logs/frontend.log`~~
- ~~Backend-unreachable modal dialog in frontend~~

---

## Operational Gotchas (lessons learned 2026-04-17 → 2026-04-19)

Durable knowledge harvested from a real debug-and-harden cycle. These are the things you'd otherwise only know by re-breaking the system.

### Backend startup & environment

- **Claude Code subshells export `ANTHROPIC_API_KEY=""`** (empty string) as a security measure. With the default pydantic-settings precedence (OS env > `.env`), this empty value silently shadows the real key and the backend fails to start with `AssertionError: ANTHROPIC_API_KEY is not set in .env`. Handled by `_strip_empty_shadow_env()` in `backend/core/config.py` which removes empty sensitive vars from `os.environ` before `Settings()` construction. Same protection now applies if any other parent process does the same thing.
- **`pydantic.SecretStr` is mandatory for every API-key field.** A plain `str` field will appear in clear text inside `repr(Settings)`, which pytest dumps on any assertion failure. Real-world consequence: seven keys leaked into a session transcript in the 2026-04-19 incident. SecretStr makes this class of leak impossible — `.get_secret_value()` is required only at the point of SDK construction.

### Redis in docker

- **The container must expose port 6379 to the host** via `-p 6379:6379` at `docker run` time. `docker start <existing-container>` cannot add a port mapping retroactively — if the container was created without `-p`, you must `docker rm` and `docker run` again. A container with `Ports: 6379/tcp` (no `->`) in `docker ps` output is a silent failure mode: `/health` returns `redis:false` while the container looks "Up". Symptoms: chat responses fail, `fetchDocuments()` returns nothing, but no obvious error.
- **Redis takes ~1–2 s to accept connections after `docker start`.** During this window, the backend's lifespan handler logs `WARNING: Redis is not reachable` but still boots. Subsequent requests succeed. Don't mistake a transient cold-start warning for a real outage.

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

- **`make doctor` first, always.** It surfaces the five most common failure modes in < 2 seconds (Redis, port 8000, `/health`, port 5173, `.env` keys). Trying to diagnose without it wastes 20 minutes clicking around.
- **When a 500 comes back from `/documents/upload`, the stack trace lives in `logs/backend.log`.** The JSON error body is useless; the traceback is not.
- **Never share, screenshot, or paste `.env` contents or any `print(settings)` / `repr(settings)` output.** SecretStr now protects the latter, but discipline matters. Any Settings-like dict must explicitly `.get_secret_value()` the field — or better, leave the masked value in place.

### Deferred / known-unknowns

- **Chat responses occasionally report "N uncited claims"** from `mcp_citation_validator`. The main numbers are cited but detail-rows in markdown tables aren't individually tagged. Prompt-engineering fix, not a pipeline bug.
- **Redis container state is ephemeral across container recreation.** Pinecone vectors survive but the `finsight:documents` registry does not, so after a `docker rm` + `docker run` cycle, the Sources panel will be empty even if the underlying vectors are queryable. Re-upload the document to restore the registry entry.

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

# ── Redis (docker) ──────────────────────────────────────────────────────────
docker ps --filter name=redis-finsight --format 'Ports: {{.Ports}}'   # MUST show 0.0.0.0:6379->6379/tcp
docker exec redis-finsight redis-cli PING                   # expect: PONG
# If port mapping is missing (no ->), rebuild cleanly:
docker stop redis-finsight && docker rm redis-finsight && \
  docker run -d --name redis-finsight -p 6379:6379 redis:alpine

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

# ── Tests ───────────────────────────────────────────────────────────────────
conda run -n finsight pytest backend/tests/ -v -k "not integration"   # 229 unit
conda run -n finsight pytest backend/tests/ -v -m integration          # 23 integration

# ── Start backend directly (bypass make when debugging the Makefile itself) ─
PYTHONPATH=. /Users/aarvingeorge/miniconda3/envs/finsight/bin/uvicorn \
  backend.api.main:app --port 8000
```

---

## Security Incidents

| Date | Incident | Scope | Remediation |
|------|----------|-------|-------------|
| 2026-04-19 | Plaintext API-key leak via pytest Settings dump | A monkeypatch-set empty `ANTHROPIC_API_KEY` triggered an assertion failure whose pytest output included the full `Settings(...)` repr — all 7 API keys (Anthropic, Gemini, Google, Pinecone, OpenAI, Groq, Grok) appeared in plaintext. Logged locally to this session's transcript at `~/.claude/projects/.../*.jsonl` (mode `600`, user-only). Also traversed Anthropic's API (normal trust boundary of using Claude Code). Not in git, not cloud-synced. | **Systemic fix shipped** as commit `608d58f`: all `*_api_key` fields typed as `SecretStr` so `repr(Settings)` now prints `SecretStr('**********')`. Regression tests added. **User action still pending**: rotate all 7 keys at the respective provider consoles to make the leaked values worthless; delete the session transcript file post-`/exit`. |
