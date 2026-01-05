"""Shared error definitions for MAO Testing Platform.

This module provides base exception classes used across all MAO components:
- mao (CLI)
- sdk (Python SDK)
- backend (API server)
- pisama-core (detection library)
"""

from typing import Optional


class MAOError(Exception):
    """Base exception for all MAO errors."""
    pass


# === API Errors ===

class APIError(MAOError):
    """API request error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"API Error {status_code}: {message}")


class AuthenticationError(MAOError):
    """Authentication failed."""
    pass


class RateLimitError(MAOError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(msg)


# === Resource Errors ===

class NotFoundError(MAOError):
    """Base class for resource not found errors."""
    pass


class TraceNotFoundError(NotFoundError):
    """Trace not found."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        super().__init__(f"Trace '{trace_id}' not found")


class DetectionNotFoundError(NotFoundError):
    """Detection not found."""

    def __init__(self, detection_id: str):
        self.detection_id = detection_id
        super().__init__(f"Detection '{detection_id}' not found")


# === Validation Errors ===

class ValidationError(MAOError):
    """Input validation failed."""
    pass


class ConfigError(MAOError):
    """Configuration error."""
    pass


# === Operation Errors ===

class TracingError(MAOError):
    """Error during tracing operations."""
    pass


class ExportError(MAOError):
    """Error exporting trace data."""
    pass


class DetectionError(MAOError):
    """Error during failure detection."""
    pass


class HealingError(MAOError):
    """Error during self-healing operations."""
    pass
