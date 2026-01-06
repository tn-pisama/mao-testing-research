"""MAO Testing SDK - Multi-Agent Orchestration failure detection."""

from .tracer import MAOTracer
from .session import TraceSession
from .span import Span
from .config import MAOConfig
from .errors import MAOError, TracingError, ConfigError

__version__ = "0.1.0"
__all__ = [
    "MAOTracer",
    "TraceSession",
    "Span",
    "MAOConfig",
    "MAOError",
    "TracingError",
    "ConfigError",
]
