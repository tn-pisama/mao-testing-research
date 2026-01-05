"""MAO Common - Shared utilities for MAO Testing Platform."""

from mao_common.errors import (
    MAOError,
    APIError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    TraceNotFoundError,
    DetectionNotFoundError,
    ValidationError,
    ConfigError,
    TracingError,
    ExportError,
    DetectionError,
    HealingError,
)

__all__ = [
    "MAOError",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "TraceNotFoundError",
    "DetectionNotFoundError",
    "ValidationError",
    "ConfigError",
    "TracingError",
    "ExportError",
    "DetectionError",
    "HealingError",
]

__version__ = "0.1.0"
