"""
Tests for per-tenant rate limiting based on subscription tiers.
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.core.rate_limit import (
    RateLimiter,
    RateLimitResult,
    check_tenant_rate_limit,
)
from app.billing.constants import PlanTier, RATE_LIMITS, get_rate_limit


# =============================================================================
# Unit tests for RATE_LIMITS config
# =============================================================================


class TestRateLimitConfig:
    def test_rate_limits_defined_for_all_tiers(self):
        for tier in PlanTier:
            assert tier in RATE_LIMITS, f"Missing rate limit for {tier}"
            config = RATE_LIMITS[tier]
            assert "requests_per_minute" in config
            assert "window_seconds" in config

    def test_tier_ordering(self):
        """Higher tiers should have higher limits."""
        free = RATE_LIMITS[PlanTier.FREE]["requests_per_minute"]
        pro = RATE_LIMITS[PlanTier.PRO]["requests_per_minute"]
        team = RATE_LIMITS[PlanTier.TEAM]["requests_per_minute"]
        enterprise = RATE_LIMITS[PlanTier.ENTERPRISE]["requests_per_minute"]

        assert free < pro < team < enterprise

    def test_get_rate_limit_known_tier(self):
        config = get_rate_limit(PlanTier.PRO)
        assert config["requests_per_minute"] == 200

    def test_get_rate_limit_unknown_tier_defaults_to_free(self):
        config = get_rate_limit("nonexistent")
        assert config == RATE_LIMITS[PlanTier.FREE]

    def test_free_tier_limits(self):
        config = get_rate_limit(PlanTier.FREE)
        assert config["requests_per_minute"] == 30
        assert config["window_seconds"] == 60


# =============================================================================
# Unit tests for RateLimiter
# =============================================================================


class TestRateLimiterDetailed:
    def test_memory_limit_detailed_allows_under_limit(self):
        limiter = RateLimiter()
        result = limiter._check_memory_limit_detailed("test:key", 10, 60)
        assert result.allowed is True
        assert result.limit == 10
        assert result.remaining == 9

    def test_memory_limit_detailed_denies_at_limit(self):
        limiter = RateLimiter()
        # Fill up the limit
        for _ in range(10):
            limiter._check_memory_limit_detailed("test:key2", 10, 60)
        result = limiter._check_memory_limit_detailed("test:key2", 10, 60)
        assert result.allowed is False
        assert result.remaining == 0

    def test_memory_limit_detailed_resets_after_window(self):
        limiter = RateLimiter()
        # Fill up with a very short window
        for _ in range(5):
            limiter._check_memory_limit_detailed("test:key3", 5, 1)

        # Advance past window
        now = time.time()
        limiter._memory_store["test:key3"] = [now - 2 for _ in range(5)]

        result = limiter._check_memory_limit_detailed("test:key3", 5, 1)
        assert result.allowed is True

    def test_memory_limit_detailed_returns_reset_timestamp(self):
        limiter = RateLimiter()
        result = limiter._check_memory_limit_detailed("test:key4", 10, 60)
        now = int(time.time())
        assert result.reset_at >= now + 59  # Within 1 second tolerance
        assert result.reset_at <= now + 61


# =============================================================================
# Unit tests for tier caching
# =============================================================================


class TestTierCaching:
    @pytest.mark.asyncio
    async def test_get_tenant_tier_returns_none_without_redis(self):
        limiter = RateLimiter()
        tier = await limiter.get_tenant_tier("tenant-123")
        assert tier is None

    @pytest.mark.asyncio
    async def test_cache_and_get_tier_with_mock_redis(self):
        limiter = RateLimiter()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"pro")
        mock_redis.set = AsyncMock()
        limiter._redis = mock_redis

        tier = await limiter.get_tenant_tier("tenant-123")
        assert tier == "pro"
        mock_redis.get.assert_called_once_with("tenant_tier:tenant-123")

    @pytest.mark.asyncio
    async def test_cache_tenant_tier_with_mock_redis(self):
        limiter = RateLimiter()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        limiter._redis = mock_redis

        await limiter.cache_tenant_tier("tenant-123", "team", ttl=300)
        mock_redis.set.assert_called_once_with("tenant_tier:tenant-123", "team", ex=300)

    @pytest.mark.asyncio
    async def test_invalidate_tenant_tier_with_mock_redis(self):
        limiter = RateLimiter()
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        limiter._redis = mock_redis

        await limiter.invalidate_tenant_tier("tenant-123")
        mock_redis.delete.assert_called_once_with("tenant_tier:tenant-123")

    @pytest.mark.asyncio
    async def test_tier_cache_handles_redis_error_gracefully(self):
        from redis.exceptions import RedisError

        limiter = RateLimiter()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=RedisError("Connection lost"))
        limiter._redis = mock_redis

        # Should return None, not raise
        tier = await limiter.get_tenant_tier("tenant-123")
        assert tier is None


# =============================================================================
# Unit tests for check_tenant_rate_limit
# =============================================================================


class TestCheckTenantRateLimit:
    @pytest.mark.asyncio
    async def test_free_tier_uses_30_limit(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = PlanTier.FREE
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.get_tenant_tier = AsyncMock(return_value=None)
            mock_limiter.cache_tenant_tier = AsyncMock()
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=True, limit=30, remaining=29, reset_at=int(time.time()) + 60)
            )

            result = await check_tenant_rate_limit("tenant-free", mock_db)
            assert result.allowed is True
            assert result.limit == 30

            # Verify it was called with free tier limits
            mock_limiter.check_rate_limit_detailed.assert_called_once_with(
                "rate_limit:tenant:tenant-free", 30, 60
            )

    @pytest.mark.asyncio
    async def test_pro_tier_uses_200_limit(self):
        mock_db = AsyncMock()

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            # Cache hit: return pro tier
            mock_limiter.get_tenant_tier = AsyncMock(return_value="pro")
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=True, limit=200, remaining=199, reset_at=int(time.time()) + 60)
            )

            result = await check_tenant_rate_limit("tenant-pro", mock_db)
            assert result.limit == 200

    @pytest.mark.asyncio
    async def test_team_tier_uses_1000_limit(self):
        mock_db = AsyncMock()

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.get_tenant_tier = AsyncMock(return_value="team")
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=True, limit=1000, remaining=999, reset_at=int(time.time()) + 60)
            )

            result = await check_tenant_rate_limit("tenant-team", mock_db)
            assert result.limit == 1000

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_raises_429(self):
        mock_db = AsyncMock()

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.get_tenant_tier = AsyncMock(return_value="free")
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=False, limit=30, remaining=0, reset_at=int(time.time()) + 60)
            )

            with pytest.raises(HTTPException) as exc_info:
                await check_tenant_rate_limit("tenant-over-limit", mock_db)

            assert exc_info.value.status_code == 429
            assert "Rate limit exceeded" in exc_info.value.detail
            assert "X-RateLimit-Limit" in exc_info.value.headers
            assert exc_info.value.headers["X-RateLimit-Limit"] == "30"
            assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_429_includes_upgrade_message(self):
        mock_db = AsyncMock()

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.get_tenant_tier = AsyncMock(return_value="free")
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=False, limit=30, remaining=0, reset_at=int(time.time()) + 60)
            )

            with pytest.raises(HTTPException) as exc_info:
                await check_tenant_rate_limit("tenant-free", mock_db)

            assert "Upgrade" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_unknown_tenant_defaults_to_free(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No tenant found
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.get_tenant_tier = AsyncMock(return_value=None)
            mock_limiter.cache_tenant_tier = AsyncMock()
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=True, limit=30, remaining=29, reset_at=int(time.time()) + 60)
            )

            result = await check_tenant_rate_limit("unknown-tenant", mock_db)
            assert result.limit == 30

    @pytest.mark.asyncio
    async def test_tier_cache_hit_skips_db_query(self):
        mock_db = AsyncMock()

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.get_tenant_tier = AsyncMock(return_value="team")
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=True, limit=1000, remaining=999, reset_at=int(time.time()) + 60)
            )

            await check_tenant_rate_limit("cached-tenant", mock_db)

            # DB should NOT be queried since cache had a hit
            mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_enterprise_custom_override(self):
        mock_db = AsyncMock()
        # First call returns enterprise tier, second returns settings with override
        tier_result = MagicMock()
        tier_result.scalar_one_or_none.return_value = PlanTier.ENTERPRISE

        settings_result = MagicMock()
        settings_result.scalar_one_or_none.return_value = {
            "rate_limit_override": {"requests_per_minute": 50000, "window_seconds": 60}
        }

        mock_db.execute = AsyncMock(side_effect=[tier_result, settings_result])

        with patch("app.core.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.get_tenant_tier = AsyncMock(return_value=None)
            mock_limiter.cache_tenant_tier = AsyncMock()
            mock_limiter.check_rate_limit_detailed = AsyncMock(
                return_value=RateLimitResult(allowed=True, limit=50000, remaining=49999, reset_at=int(time.time()) + 60)
            )

            result = await check_tenant_rate_limit("enterprise-tenant", mock_db)

            # Should use custom limit from settings
            mock_limiter.check_rate_limit_detailed.assert_called_once_with(
                "rate_limit:tenant:enterprise-tenant", 50000, 60
            )


# =============================================================================
# Unit tests for RateLimitResult dataclass
# =============================================================================


class TestRateLimitResult:
    def test_result_fields(self):
        result = RateLimitResult(allowed=True, limit=100, remaining=50, reset_at=1700000000)
        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 50
        assert result.reset_at == 1700000000

    def test_result_denied(self):
        result = RateLimitResult(allowed=False, limit=100, remaining=0, reset_at=1700000000)
        assert result.allowed is False
        assert result.remaining == 0
