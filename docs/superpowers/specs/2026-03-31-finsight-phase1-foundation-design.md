# FinSight CFO Assistant — Phase 1: Foundation

**Master spec:** `CFO-Assistant/ceo-assistant-design-document.pdf`  
**Implementation strategy:** Sequenced by phase — each phase is planned and verified before the next begins.

---

## Scope

Phase 1 establishes the skeleton the entire system will be built on. No agent logic, no document parsing, no frontend. Just the infrastructure that every subsequent phase depends on.

**Deliverables:**
1. Project folder structure matching the spec (`finsight-cfo/backend/`, `frontend/`, etc.)
2. FastAPI server running on `localhost:8000` with a health check endpoint
3. `.env` configuration with `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` loaded via `python-dotenv`
4. Gemini API client wrapper (`google-generativeai` SDK, `models/gemini-embedding-001`, dimension=3072)
5. Pinecone client wrapper — connect to `finsight-index`, verify index exists on startup (replaces FAISS from master spec; Pinecone serverless removes local index file management)
6. Redis connection — Docker on `localhost:6379`, ping-verified on startup
7. Base agent class — abstract Python class all 6 agents will inherit from; defines `run()` interface and shared Claude client
8. MCP server scaffold — `financial_mcp_server.py` running via `mcp` SDK with all 25 tool signatures registered as stubs (raise `NotImplementedError`)
9. `requirements.txt` with all backend dependencies pinned

---

## Architecture

```
finsight-cfo/
├── backend/
│   ├── agents/
│   │   └── base_agent.py          # Abstract base class
│   ├── mcp_server/
│   │   ├── financial_mcp_server.py  # MCP server + all 25 tool stubs
│   │   └── tools/
│   │       ├── document_tools.py
│   │       ├── modeling_tools.py
│   │       ├── scenario_tools.py
│   │       ├── output_tools.py
│   │       └── memory_tools.py
│   ├── api/
│   │   ├── routes/
│   │   │   └── health.py
│   │   └── main.py                # FastAPI app, startup checks
│   ├── storage/
│   │   ├── faiss_index/           # Empty, created on init
│   │   └── outputs/               # Empty
│   ├── core/
│   │   ├── config.py              # pydantic-settings, loads .env, typed access
│   │   ├── gemini_client.py       # Gemini embedding client wrapper (gemini-embedding-001, dim=3072)
│   │   ├── pinecone_store.py      # Pinecone client wrapper, index connection + startup check
│   │   └── redis_client.py        # Redis connection + ping check (Docker localhost:6379)
│   ├── .env                       # Never committed
│   ├── .env.example               # Committed template
│   └── requirements.txt
└── frontend/                      # Empty scaffold (package.json only)
```

---

## Key Decisions

**Base agent class:** Holds the shared `anthropic.Anthropic()` client instance so it's initialized once. Defines `run(query: str, session_id: str) -> str` as an abstract method. All 6 agents inherit this — no duplicated SDK setup.

**MCP server stubs:** All 25 tools are registered with correct signatures and docstrings but raise `NotImplementedError`. This means the MCP server is runnable and discoverable from day 1, and each phase just fills in the stubs — no structural rewiring later.

**Startup validation:** FastAPI lifespan event checks Redis ping, FAISS index directory existence, and that both API keys are present in the environment. Server refuses to start if any check fails — no silent misconfiguration.

**Frontend scaffold:** Just `package.json` with React 18 + TypeScript + MUI v6 + Zustand + Axios dependencies listed. No components yet. Ensures `npm install` works before Phase 5.

---

## Success Criteria

Phase 1 is complete when:
- `GET /health` returns `{"status": "ok", "redis": true, "pinecone": true, "anthropic_key": true, "gemini_key": true}`
- MCP server starts and lists all 25 tools via `mcp list-tools` (or equivalent)
- `python -c "from agents.base_agent import BaseAgent"` imports without error
- `cd frontend && npm install` completes without errors
- No API keys appear in any committed file

---

## Out of Scope for Phase 1

- Document parsing or ingestion
- Any agent implementation beyond the base class
- Any MCP tool implementation (stubs only)
- Frontend components or pages
- Any Claude or Gemini API calls
