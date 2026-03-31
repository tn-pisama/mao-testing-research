"""Pisama -- Multi-agent failure detection for production AI systems.

Example:
    import pisama

    result = pisama.analyze("trace.json")
    for issue in result.issues:
        print(f"[{issue.type}] {issue.summary}")
"""

__version__ = "0.1.0"

from pisama._analyze import AnalyzeResult, Issue, analyze, async_analyze
from pisama._loader import load_trace

__all__ = [
    "__version__",
    "analyze",
    "async_analyze",
    "load_trace",
    "AnalyzeResult",
    "Issue",
]
