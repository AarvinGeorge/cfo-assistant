"""
main.py

FastAPI application factory — wires together all routers, configures CORS,
and manages service lifecycle (startup validation and graceful shutdown).

Role in project:
    HTTP entry point. This is the module Uvicorn loads:
    uvicorn backend.api.main:app. It registers all route prefixes, sets
    CORS policy to allow the Vite dev server at localhost:5173, and runs
    a health check on startup to confirm Redis, Pinecone, and API keys are
    reachable before accepting traffic.

Main parts:
    - app: the FastAPI instance with lifespan context manager.
    - lifespan(): async context that validates all external dependencies on
      startup and closes the Redis connection on shutdown.
    - Router registrations: /health, /chat, /documents, /models, /scenarios.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes.health import router as health_router
from backend.api.routes.documents import router as documents_router
from backend.api.routes.models import router as models_router
from backend.api.routes.scenarios import router as scenarios_router
from backend.api.routes.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.core.config import get_settings
    from backend.core.redis_client import ping_redis
    settings = get_settings()

    assert settings.anthropic_api_key.get_secret_value(), "ANTHROPIC_API_KEY is not set in .env"
    assert settings.gemini_api_key.get_secret_value(), "GEMINI_API_KEY is not set in .env"
    assert settings.pinecone_api_key.get_secret_value(), "PINECONE_API_KEY is not set in .env"

    if not ping_redis():
        print("WARNING: Redis is not reachable. Start with: docker run -d --name redis-finsight -p 6379:6379 redis:alpine")

    yield


app = FastAPI(
    title="FinSight CFO Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(models_router)
app.include_router(scenarios_router)
app.include_router(chat_router)
