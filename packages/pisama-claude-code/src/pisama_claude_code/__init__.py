"""PISAMA Claude Code Adapter.

This package provides Claude Code integration for the PISAMA agent forensics platform.
It implements the PlatformAdapter interface for:
- Trace capture from Claude Code hooks
- Real-time detection during tool calls
- Fix injection via stderr and MCP
- Enforcement and blocking
"""

from pisama_claude_code.adapter import ClaudeCodeAdapter
from pisama_claude_code.trace_converter import TraceConverter
from pisama_claude_code.storage import TraceStorage

__all__ = [
    "ClaudeCodeAdapter",
    "TraceConverter",
    "TraceStorage",
]

__version__ = "1.0.0"
