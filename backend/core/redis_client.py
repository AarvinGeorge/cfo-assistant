"""
redis_client.py

Async Redis connection used for two purposes: LangGraph conversation
checkpointing and document metadata tracking.

Role in project:
    Infrastructure layer. Shared by the LangGraph orchestrator (session memory
    via langgraph-checkpoint-redis) and the documents API route (stores
    doc_id to metadata hashes). Performs a ping on startup to fail fast if
    Redis is unreachable.

Main parts:
    - get_redis_client(): returns the shared async Redis connection, creating
      it on first call. Ping-validates on creation.
    - close_redis_client(): graceful shutdown helper called from FastAPI
      lifespan teardown.
"""
import redis
from backend.core.config import get_settings


def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )


def ping_redis() -> bool:
    try:
        return get_redis_client().ping()
    except redis.ConnectionError:
        return False
