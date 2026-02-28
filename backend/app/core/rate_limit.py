import time
import logging
from typing import Dict, Optional
from fastapi import HTTPException, Request, status

try:
    from redis import asyncio as aioredis
    from redis.exceptions import RedisError
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    aioredis = None

    class RedisError(Exception):
        """Stub for when redis is not installed."""
        pass

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class RateLimiter:
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._memory_store: Dict[str, list] = {}
    
    async def connect(self):
        if not _REDIS_AVAILABLE:
            return
        if self._redis is None:
            self._redis = await aioredis.from_url(self.redis_url)
    
    async def close(self):
        if self._redis:
            await self._redis.close()
    

    def _check_memory_limit(self, key: str, limit: int, window: int) -> bool:
        """In-memory fallback rate limiter when Redis is unavailable.
        
        Fails closed: returns False (deny) when limit is exceeded.
        """
        now = time.time()
        cutoff = now - window

        # Safety valve: clear entire store if it grows too large
        if len(self._memory_store) > 10000:
            self._memory_store.clear()

        # Get or create the timestamp list for this key
        timestamps = self._memory_store.get(key, [])

        # Remove expired entries
        timestamps = [t for t in timestamps if t > cutoff]

        # Check if limit is already reached (fail closed)
        if len(timestamps) >= limit:
            self._memory_store[key] = timestamps
            return False

        # Record the new request
        timestamps.append(now)
        self._memory_store[key] = timestamps
        return True

    async def check_rate_limit(self, key: str, limit: int = None, window: int = None) -> bool:
        try:
            await self.connect()
        except RedisError as e:
            logger.warning(f"Redis connection failed, using in-memory fallback: {e}")
            return self._check_memory_limit(key, limit or settings.rate_limit_requests, window or settings.rate_limit_window_seconds)
        
        limit = limit or settings.rate_limit_requests
        window = window or settings.rate_limit_window_seconds
        
        try:
            current_time = int(time.time())
            window_start = current_time - window
            
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.zcard(key)
            pipe.expire(key, window)
            
            results = await pipe.execute()
            request_count = results[2]
            
            return request_count <= limit
        except RedisError as e:
            logger.warning(f"Redis operation failed, using in-memory fallback: {e}")
            return self._check_memory_limit(key, limit, window)
    
    async def get_remaining(self, key: str, limit: int = None) -> int:
        await self.connect()
        limit = limit or settings.rate_limit_requests
        count = await self._redis.zcard(key)
        return max(0, limit - count)


rate_limiter = RateLimiter()


async def check_rate_limit(request: Request, tenant_id: str):
    key = f"rate_limit:{tenant_id}"
    allowed = await rate_limiter.check_rate_limit(key)
    
    if not allowed:
        remaining = await rate_limiter.get_remaining(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again later.",
            headers={"X-RateLimit-Remaining": str(remaining)},
        )
