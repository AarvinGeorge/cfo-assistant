# FinSight CFO Assistant

A RAG-powered multi-agent financial intelligence web application designed for Chief Financial Officers. Ingests financial documents (10-K/10-Q filings, income statements, balance sheets, cash flow statements, board reports, budgets), builds a semantic vector index, and deploys specialized AI agents to answer natural-language questions, generate financial models, run scenario analyses, and produce boardroom-ready outputs.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           React + TypeScript Frontend (MUI v6)          │
│  Dashboard │ Chat/Q&A │ Model Studio │ Document Manager │
└──────────────────────────┬──────────────────────────────┘
                           │ REST API + SSE
┌──────────────────────────▼──────────────────────────────┐
│                  FastAPI Backend Server                  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Orchestrator Agent                    │  │
│  │    (Intent classification, routing, memory)        │  │
│  └──────┬──────────┬──────────┬──────────────────────┘  │
│         │          │          │                          │
│   ┌─────▼──┐ ┌─────▼───┐ ┌───▼──────┐ ┌────────────┐  │
│   │  RAG   │ │Financial│ │Scenario  │ │  Output    │  │
│   │ Agent  │ │Modeling │ │Analysis  │ │Generation  │  │
│   │        │ │ Agent   │ │ Agent    │ │  Agent     │  │
│   └────────┘ └─────────┘ └──────────┘ └────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │        Custom MCP Server (26 financial tools)     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────┐ ┌───────────┐ ┌───────────────────┐  │
│  │   Pinecone   │ │   Redis   │ │   File Storage    │  │
│  │ (Embeddings) │ │ (Memory)  │ │ (Uploads/Output)  │  │
│  └──────────────┘ └───────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11+, FastAPI |
| Agent Orchestration | LangGraph (StateGraph with conditional routing) |
| Tool Protocol | MCP (Model Context Protocol) via `mcp` SDK |
| LLM | Anthropic Claude (claude-sonnet-4-6) |
| Embeddings | Google Gemini (`gemini-embedding-001`, 3072 dimensions) |
| Vector Store | Pinecone (serverless, cosine similarity) |
| Memory | Redis (Docker) |
| Frontend | React 18 + TypeScript + Material UI v6 |
| State Management | Zustand |
| Charts | Plotly |

## Prerequisites

- Python 3.11+ (via conda)
- Node.js 18+
- Docker (for Redis)
- API keys: Anthropic, Google Gemini, Pinecone

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/AarvinGeorge/cfo-assistant.git
cd cfo-assistant
cp backend/.env.example backend/.env
# Edit backend/.env and add your API keys
```

### 2. Create Pinecone index

In the [Pinecone console](https://app.pinecone.io), create an index:
- **Name:** `finsight-index`
- **Dimensions:** `3072`
- **Metric:** `cosine`
- **Type:** Serverless

### 3. Start Redis

```bash
docker run -d --name redis-finsight -p 6379:6379 redis:alpine
```

### 4. Install backend dependencies

```bash
conda create -n finsight python=3.13 -y
conda activate finsight
cd backend
pip install -r requirements.txt
```

### 5. Install frontend dependencies

```bash
cd frontend
npm install
```

### 6. Run the server

```bash
cd ..  # back to project root
PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000
```

### 7. Verify

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status": "ok", "redis": true, "pinecone": true, "anthropic_key": true, "gemini_key": true}
```

## Project Structure

```
finsight-cfo/
├── backend/
│   ├── agents/
│   │   └── base_agent.py          # Abstract base class for all 6 agents
│   ├── api/
│   │   ├── main.py                # FastAPI app with startup validation
│   │   └── routes/
│   │       ├── health.py          # /health endpoint
│   │       ├── documents.py       # /documents upload, list, delete
│   │       ├── chat.py            # /chat and /chat/stream (SSE)
│   │       ├── models.py          # /models DCF, ratios, forecast, variance
│   │       └── scenarios.py       # /scenarios run, sensitivity, covenants, runway
│   ├── core/
│   │   ├── config.py              # pydantic-settings, typed env access
│   │   ├── gemini_client.py       # Gemini embedding wrapper
│   │   ├── pinecone_store.py      # Pinecone client with dimension validation
│   │   └── redis_client.py        # Redis connection + ping check
│   ├── agents/
│   │   ├── base_agent.py          # Abstract base class
│   │   ├── graph_state.py         # LangGraph typed state schema
│   │   └── orchestrator.py        # StateGraph with intent routing + agent nodes
│   ├── skills/
│   │   ├── document_ingestion.py  # PDF/CSV parsing + hierarchical chunking
│   │   ├── vector_retrieval.py    # Semantic search + MMR reranking
│   │   ├── financial_modeling.py  # DCF, ratios, forecast, variance analysis
│   │   └── scenario_analysis.py   # Scenarios, sensitivity, covenants, runway
│   ├── mcp_server/
│   │   ├── financial_mcp_server.py # MCP server with 26 registered tools
│   │   └── tools/                  # Tool implementations by domain
│   ├── tests/                      # pytest suite (193 unit + 23 integration)
│   ├── .env.example
│   └── requirements.txt
└── frontend/
    ├── package.json               # React 18 + MUI v6 + Zustand + Plotly
    └── tsconfig.json
```

## Testing

```bash
cd backend

# Unit tests (no external services needed)
conda run -n finsight pytest tests/ -v -k "not integration"

# Integration tests (requires Redis + Pinecone + Gemini API keys)
conda run -n finsight pytest tests/ -v -m integration

# All tests
conda run -n finsight pytest tests/ -v
```

## Development Phases

- [x] **Phase 1 — Foundation:** Project scaffold, FastAPI, config, Pinecone/Redis/Gemini clients, BaseAgent, MCP server scaffold (26 tool stubs)
- [x] **Phase 2 — Ingestion & RAG:** PDF/CSV parsing, hierarchical chunking, Gemini embedding, Pinecone upsert/search, MMR reranking, /documents API
- [x] **Phase 3 — Financial Modeling:** DCF, ratio scorecard, forecasting, variance analysis, scenario/sensitivity/covenants/runway
- [x] **Phase 4 — Agent Integration:** LangGraph orchestrator with intent routing, 5 agent nodes, Redis checkpointing, SSE streaming chat, audit logging
- [ ] **Phase 5 — Frontend:** React + MUI pages (Dashboard, Chat, Documents, Models, Scenarios, Reports)
- [ ] **Phase 6 — Output & Polish:** Excel/PDF generation, packaging, documentation

## License

Private — not for redistribution.
