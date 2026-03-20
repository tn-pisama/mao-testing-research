from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis import asyncio as aioredis

from app.storage.database import get_db
from app.config import get_settings
from app.api.v1.schemas import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()

_startup_complete = False


def mark_startup_complete():
    global _startup_complete
    _startup_complete = True


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
    
    redis_status = "healthy"
    try:
        redis = await aioredis.from_url(settings.redis_url)
        await redis.ping()
        await redis.close()
    except Exception:
        redis_status = "unhealthy"
    
    overall = "healthy" if db_status == "healthy" else "degraded"
    
    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        version="0.1.0",
    )
