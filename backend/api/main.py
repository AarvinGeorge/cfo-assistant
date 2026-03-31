from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.core.config import get_settings
    from backend.core.redis_client import ping_redis
    settings = get_settings()

    assert settings.anthropic_api_key, "ANTHROPIC_API_KEY is not set in .env"
    assert settings.gemini_api_key, "GEMINI_API_KEY is not set in .env"
    assert settings.pinecone_api_key, "PINECONE_API_KEY is not set in .env"

    if not ping_redis():
        print("WARNING: Redis is not reachable. Start with: docker run -d --name redis-finsight -p 6379:6379 redis:alpine")

    yield


app = FastAPI(
    title="FinSight CFO Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
