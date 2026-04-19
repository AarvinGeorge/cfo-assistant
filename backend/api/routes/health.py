"""
health.py

FastAPI router exposing a single GET /health endpoint that probes all
external dependencies and reports their status.

Role in project:
    Operational layer. Called by the Makefile make status command and
    by the FastAPI lifespan on startup. Returns a JSON object with
    individual pass/fail for Redis ping, Pinecone index reachability,
    and presence of required API keys.

Main parts:
    - GET /health: async handler that runs Redis ping, Pinecone describe_index,
      and env-var presence checks concurrently, returning a HealthResponse
      with per-service status and an overall healthy boolean.
"""
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
        "anthropic_key": bool(settings.anthropic_api_key.get_secret_value()),
        "gemini_key": bool(settings.gemini_api_key.get_secret_value()),
    }
