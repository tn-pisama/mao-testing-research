"""Platform adapters for PISAMA.

Adapters provide the interface between pisama-core and specific
agent platforms (Claude Code, LangGraph, etc.).
"""

from pisama_core.adapters.base import PlatformAdapter, InjectionResult

__all__ = ["PlatformAdapter", "InjectionResult"]
