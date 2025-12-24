import time
from typing import Optional
from fastapi import HTTPException, Request, status
from redis import asyncio as aioredis
from app.config import get_settings

settings = get_settings()


class RateLimiter:
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        if self._redis is None:
            self._redis = await aioredis.from_url(self.redis_url)
    
    async def close(self):
        if self._redis:
            await self._redis.close()
    
    async def check_rate_limit(self, key: str, limit: int = None, window: int = None) -> bool:
        await self.connect()
        
        limit = limit or settings.rate_limit_requests
        window = window or settings.rate_limit_window_seconds
        
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
