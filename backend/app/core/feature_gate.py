"""Feature gate decorator for enterprise features.

This module provides decorators and utilities to gate enterprise features
behind feature flags, returning HTTP 402 (Payment Required) when a feature
is not enabled for the current deployment.

Usage:
    @require_enterprise("chaos_engineering")
    async def run_chaos_experiment(...):
        # Only accessible when chaos_engineering is enabled
        pass
"""
from functools import wraps
from typing import Callable, Any

from fastapi import HTTPException, status

from app.config import get_settings


class FeatureNotEnabledError(HTTPException):
    """Exception raised when an enterprise feature is not enabled."""

    def __init__(self, feature: str):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "feature_not_enabled",
                "feature": feature,
                "message": f"The '{feature}' feature requires an enterprise subscription. "
                           f"Contact sales@pisama.io to upgrade.",
                "upgrade_url": "https://pisama.io/pricing"
            }
        )


def require_enterprise(feature: str) -> Callable:
    """Decorator to require an enterprise feature flag.

    Args:
        feature: The feature flag name (e.g., 'chaos_engineering', 'ml_detection')

    Returns:
        Decorator that checks the feature flag before executing the function.

    Raises:
        FeatureNotEnabledError: If the feature is not enabled (HTTP 402)

    Example:
        @router.post("/chaos/inject")
        @require_enterprise("chaos_engineering")
        async def inject_chaos(request: ChaosRequest):
            # This endpoint only works with enterprise
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            settings = get_settings()
            if not settings.features.is_enabled(feature):
                raise FeatureNotEnabledError(feature)
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            settings = get_settings()
            if not settings.features.is_enabled(feature):
                raise FeatureNotEnabledError(feature)
            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether function is async
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper

    return decorator


def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled.

    Args:
        feature: The feature flag name

    Returns:
        True if the feature is enabled, False otherwise
    """
    settings = get_settings()
    return settings.features.is_enabled(feature)


def is_enterprise_enabled() -> bool:
    """Check if enterprise mode is enabled (master switch).

    Returns:
        True if enterprise features are enabled, False otherwise
    """
    settings = get_settings()
    return settings.features.enterprise_enabled


# Feature flag constants for type safety
class Features:
    """Feature flag constants for use with require_enterprise decorator."""
    ML_DETECTION = "ml_detection"
    OTEL_INGESTION = "otel_ingestion"
    CHAOS_ENGINEERING = "chaos_engineering"
    TRACE_REPLAY = "trace_replay"
    REGRESSION_TESTING = "regression_testing"
    ADVANCED_EVALS = "advanced_evals"
    AUDIT_LOGGING = "audit_logging"
