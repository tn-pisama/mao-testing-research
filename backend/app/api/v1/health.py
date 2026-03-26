import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis import asyncio as aioredis

from app.storage.database import get_db
from app.config import get_settings
from app.api.v1.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])
settings = get_settings()

_startup_complete = False


def mark_startup_complete():
    global _startup_complete
    _startup_complete = True


@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response, db: AsyncSession = Depends(get_db)):
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Health check: database unreachable: %s", e)
        db_status = "unhealthy"

    redis_status = "healthy"
    try:
        redis = await aioredis.from_url(settings.redis_url)
        await redis.ping()
        await redis.close()
    except Exception as e:
        logger.error("Health check: Redis unreachable: %s", e)
        redis_status = "unhealthy"

    if db_status != "healthy":
        overall = "unhealthy"
        response.status_code = 503
    elif redis_status != "healthy":
        overall = "degraded"
    else:
        overall = "healthy"

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        version="0.1.0",
    )
