import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from fastapi import Depends, HTTPException, Request, status

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


@dataclass
class RateLimitResult:
    """Result of a rate limit check with metadata for response headers."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: int  # Unix timestamp when the window resets


class RateLimiter:
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._memory_store: Dict[str, list] = {}

    async def connect(self):
        if not _REDIS_AVAILABLE:
            return
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                max_connections=50,  # M6: Explicit pool size
                decode_responses=True,
            )

    async def close(self):
        if self._redis:
            await self._redis.close()


    def _check_memory_limit(self, key: str, limit: int, window: int) -> bool:
        """In-memory fallback rate limiter when Redis is unavailable.

        Fails closed: returns False (deny) when limit is exceeded.
        """
        now = time.time()
        cutoff = now - window

        # Safety valve: evict oldest entries if store grows too large (LRU-style)
        if len(self._memory_store) > 10000:
            # Remove 20% oldest keys by earliest timestamp
            sorted_keys = sorted(
                self._memory_store.keys(),
                key=lambda k: min(self._memory_store[k]) if self._memory_store[k] else 0,
            )
            for k in sorted_keys[:2000]:
                del self._memory_store[k]

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

    def _check_memory_limit_detailed(self, key: str, limit: int, window: int) -> RateLimitResult:
        """In-memory fallback that returns full rate limit metadata."""
        now = time.time()
        cutoff = now - window

        if len(self._memory_store) > 10000:
            self._memory_store.clear()

        timestamps = self._memory_store.get(key, [])
        timestamps = [t for t in timestamps if t > cutoff]

        reset_at = int(now) + window
        count = len(timestamps)

        if count >= limit:
            self._memory_store[key] = timestamps
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
            )

        timestamps.append(now)
        self._memory_store[key] = timestamps
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=max(0, limit - len(timestamps)),
            reset_at=reset_at,
        )

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

    async def check_rate_limit_detailed(self, key: str, limit: int, window: int) -> RateLimitResult:
        """Check rate limit and return full metadata for response headers."""
        try:
            await self.connect()
        except RedisError as e:
            logger.warning(f"Redis connection failed, using in-memory fallback: {e}")
            return self._check_memory_limit_detailed(key, limit, window)

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
            reset_at = current_time + window

            return RateLimitResult(
                allowed=request_count <= limit,
                limit=limit,
                remaining=max(0, limit - request_count),
                reset_at=reset_at,
            )
        except RedisError as e:
            logger.warning(f"Redis operation failed, using in-memory fallback: {e}")
            return self._check_memory_limit_detailed(key, limit, window)

    async def get_remaining(self, key: str, limit: int = None) -> int:
        await self.connect()
        limit = limit or settings.rate_limit_requests
        count = await self._redis.zcard(key)
        return max(0, limit - count)

    # --- Tenant tier caching ---

    async def get_tenant_tier(self, tenant_id: str) -> Optional[str]:
        """Get cached tenant plan tier from Redis."""
        if not self._redis:
            try:
                await self.connect()
            except RedisError:
                return None
        if not self._redis:
            return None
        try:
            tier = await self._redis.get(f"tenant_tier:{tenant_id}")
            if tier:
                return tier.decode() if isinstance(tier, bytes) else tier
        except RedisError as e:
            logger.warning(f"Redis get_tenant_tier failed: {e}")
        return None

    async def cache_tenant_tier(self, tenant_id: str, tier: str, ttl: int = None):
        """Cache tenant plan tier in Redis."""
        if ttl is None:
            ttl = settings.tenant_tier_cache_ttl_seconds
        if not self._redis:
            try:
                await self.connect()
            except RedisError:
                return
        if not self._redis:
            return
        try:
            await self._redis.set(f"tenant_tier:{tenant_id}", tier, ex=ttl)
        except RedisError as e:
            logger.warning(f"Redis cache_tenant_tier failed: {e}")

    async def invalidate_tenant_tier(self, tenant_id: str):
        """Invalidate cached tier (called on plan changes)."""
        if not self._redis:
            try:
                await self.connect()
            except RedisError:
                return
        if not self._redis:
            return
        try:
            await self._redis.delete(f"tenant_tier:{tenant_id}")
        except RedisError as e:
            logger.warning(f"Redis invalidate_tenant_tier failed: {e}")


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


async def check_tenant_rate_limit(tenant_id: str, db) -> RateLimitResult:
    """Check rate limit for a tenant based on their subscription tier."""
    from app.billing.constants import PlanTier, get_rate_limit
    from sqlalchemy import select
    from app.storage.models import Tenant

    # 1. Check Redis cache for tier
    tier = await rate_limiter.get_tenant_tier(tenant_id)

    # 2. Cache miss -> query DB and cache
    if tier is None:
        result = await db.execute(
            select(Tenant.plan).where(Tenant.id == tenant_id)
        )
        row = result.scalar_one_or_none()
        tier = row if row else PlanTier.FREE
        await rate_limiter.cache_tenant_tier(tenant_id, tier)

    # 3. Get rate limit config for this tier
    rate_config = get_rate_limit(tier)
    limit = rate_config["requests_per_minute"]
    window = rate_config["window_seconds"]

    # 4. Enterprise custom override
    if tier == PlanTier.ENTERPRISE:
        tenant_result = await db.execute(
            select(Tenant.settings).where(Tenant.id == tenant_id)
        )
        tenant_settings = tenant_result.scalar_one_or_none()
        if tenant_settings and isinstance(tenant_settings, dict):
            override = tenant_settings.get("rate_limit_override")
            if override:
                limit = override.get("requests_per_minute", limit)
                window = override.get("window_seconds", window)

    # 5. Check the rate limit
    key = f"rate_limit:tenant:{tenant_id}"
    result = await rate_limiter.check_rate_limit_detailed(key, limit, window)

    # 6. Deny if exceeded
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Upgrade your plan for higher limits.",
            headers={
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_at),
                "Retry-After": str(max(1, result.reset_at - int(time.time()))),
            },
        )

    return result


async def require_tenant_rate_limit(
    request: Request,
    credentials=Depends(None),  # Placeholder - wired in main.py
    db=Depends(None),  # Placeholder - wired in main.py
) -> RateLimitResult:
    """FastAPI dependency that enforces per-tenant rate limits.

    NOTE: This function is not used directly as a dependency.
    Instead, use the tenant_rate_limit_dependency() factory in main.py.
    """
    raise NotImplementedError("Use tenant_rate_limit_dependency() factory instead")
