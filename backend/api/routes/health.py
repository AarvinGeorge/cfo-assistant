"""
health.py

FastAPI router exposing a single GET /health endpoint that probes all
external dependencies and reports their status.

Role in project:
    Operational layer. Called by the Makefile's `make status` command and
    by the frontend's connection watcher. Returns a JSON object with
    individual pass/fail for Pinecone index reachability and presence of
    required API keys. (SQLite is in-process and always available; its
    health is implicitly checked by any route that queries it.)

Main parts:
    - GET /health: async handler that runs Pinecone describe_index and
      env-var presence checks, returning a dict with per-service status
      and an overall healthy flag.
"""
from fastapi import APIRouter
from backend.core.pinecone_store import get_pinecone_store
from backend.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    settings = get_settings()

    pinecone_ok = False
    try:
        pinecone_ok = get_pinecone_store().is_ready()
    except Exception:
        pinecone_ok = False

    all_ok = pinecone_ok

    return {
        "status": "ok" if all_ok else "degraded",
        "pinecone": pinecone_ok,
        "anthropic_key": bool(settings.anthropic_api_key.get_secret_value()),
        "gemini_key": bool(settings.gemini_api_key.get_secret_value()),
    }
