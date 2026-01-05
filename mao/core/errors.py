"""Domain errors for MAO CLI.

This module re-exports errors from mao-common for backward compatibility.
New code should import directly from mao_common.errors.
"""

# Try to import from shared package, fall back to local definitions
try:
    from mao_common.errors import (
        MAOError,
        APIError,
        AuthenticationError,
        RateLimitError,
        TraceNotFoundError,
        DetectionNotFoundError,
        ValidationError,
    )
except ImportError:
    # Fallback for when mao-common is not installed
    from typing import Optional

    class MAOError(Exception):
        """Base MAO error."""
        pass

    class TraceNotFoundError(MAOError):
        """Trace not found."""

        def __init__(self, trace_id: str):
            self.trace_id = trace_id
            super().__init__(f"Trace '{trace_id}' not found")

    class DetectionNotFoundError(MAOError):
        """Detection not found."""

        def __init__(self, detection_id: str):
            self.detection_id = detection_id
            super().__init__(f"Detection '{detection_id}' not found")

    class APIError(MAOError):
        """API request error."""

        def __init__(self, status_code: int, message: str):
            self.status_code = status_code
            super().__init__(f"API Error {status_code}: {message}")

    class AuthenticationError(MAOError):
        """Authentication failed."""
        pass

    class ValidationError(MAOError):
        """Input validation failed."""
        pass

    class RateLimitError(MAOError):
        """Rate limit exceeded."""

        def __init__(self, retry_after: Optional[int] = None):
            self.retry_after = retry_after
            msg = "Rate limit exceeded"
            if retry_after:
                msg += f", retry after {retry_after}s"
            super().__init__(msg)


__all__ = [
    "MAOError",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "TraceNotFoundError",
    "DetectionNotFoundError",
    "ValidationError",
]
