"""MAO Testing SDK exceptions.

This module re-exports errors from mao-common for backward compatibility.
New code should import directly from mao_common.errors.
"""

# Try to import from shared package, fall back to local definitions
try:
    from mao_common.errors import (
        MAOError,
        TracingError,
        ConfigError,
        ExportError,
    )
except ImportError:
    # Fallback for when mao-common is not installed
    class MAOError(Exception):
        """Base exception for MAO Testing SDK."""
        pass

    class TracingError(MAOError):
        """Error during tracing operations."""
        pass

    class ConfigError(MAOError):
        """Configuration error."""
        pass

    class ExportError(MAOError):
        """Error exporting trace data."""
        pass


__all__ = [
    "MAOError",
    "TracingError",
    "ConfigError",
    "ExportError",
]
