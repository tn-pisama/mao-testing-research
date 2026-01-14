"""PISAMA Agent SDK Integration.

Provides hooks for Claude Agent SDK that connect to MAO's
detection infrastructure for real-time failure prevention.

Quick Start:
    from pisama_agent_sdk import pre_tool_use_hook, post_tool_use_hook
    from pisama_agent_sdk import configure_bridge

    # Optional: customize configuration
    configure_bridge(
        warning_threshold=40,
        block_threshold=60,
        timeout_ms=80,
    )

    # Register hooks with Agent SDK
    agent.hooks.pre_tool_use = pre_tool_use_hook
    agent.hooks.post_tool_use = post_tool_use_hook

Advanced Usage:
    from pisama_agent_sdk import DetectionBridge, BridgeConfig
    from pisama_agent_sdk.hooks import PreToolUseHook, PostToolUseHook

    # Custom configuration
    config = BridgeConfig(
        warning_threshold=30,
        block_threshold=50,
        detection_timeout_ms=60,
    )
    bridge = DetectionBridge(config=config)

    # Custom hooks
    pre_hook = PreToolUseHook(bridge=bridge)
    post_hook = PostToolUseHook(bridge=bridge)

    agent.hooks.pre_tool_use = pre_hook
    agent.hooks.post_tool_use = post_hook
"""

__version__ = "0.1.0"

# Hook functions (primary API)
from .hooks.pre_tool_use import pre_tool_use_hook, PreToolUseHook
from .hooks.post_tool_use import post_tool_use_hook, PostToolUseHook

# Configuration
from .bridge import configure_bridge, create_bridge, get_bridge
from .config import BridgeConfig, load_config

# Bridge (for advanced use)
from .bridge import DetectionBridge

# Types
from .types import BridgeResult, HookInput, HookContext, HookJSONOutput

# Matchers
from .hooks.matchers import (
    HookMatcher,
    ALL_TOOLS,
    FILE_TOOLS,
    SHELL_TOOLS,
    DANGEROUS_COMMANDS,
    AGENT_TOOLS,
    create_matcher,
)

# Session management
from .session import SessionManager, session_manager

__all__ = [
    # Version
    "__version__",
    # Hook functions
    "pre_tool_use_hook",
    "post_tool_use_hook",
    # Hook classes
    "PreToolUseHook",
    "PostToolUseHook",
    # Configuration
    "configure_bridge",
    "create_bridge",
    "get_bridge",
    "BridgeConfig",
    "load_config",
    # Bridge
    "DetectionBridge",
    # Types
    "BridgeResult",
    "HookInput",
    "HookContext",
    "HookJSONOutput",
    # Matchers
    "HookMatcher",
    "ALL_TOOLS",
    "FILE_TOOLS",
    "SHELL_TOOLS",
    "DANGEROUS_COMMANDS",
    "AGENT_TOOLS",
    "create_matcher",
    # Session
    "SessionManager",
    "session_manager",
]
