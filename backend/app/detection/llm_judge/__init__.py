"""
LLM Judge Package
=================

MAST Failure Mode detection using Claude models.
Provides backward-compatible re-exports from the original mast_llm_judge.py.

Usage:
    from app.detection.llm_judge import MASTLLMJudge, MASTFailureMode

    judge = MASTLLMJudge()
    result = judge.evaluate(
        failure_mode=MASTFailureMode.F1,
        task="Build a REST API",
        trace_summary="Agent started by..."
    )
"""

# Enums
from ._enums import MASTFailureMode

# Dataclasses
from ._dataclasses import (
    JudgmentResult,
    JudgeCostTracker,
    ClaudeModelConfig,
)

# Model configuration and selection
from ._models import (
    CLAUDE_MODELS,
    LOW_STAKES_MODEL_KEY,
    DEFAULT_MODEL_KEY,
    HIGH_STAKES_MODEL_KEY,
    LOW_STAKES_FAILURE_MODES,
    HIGH_STAKES_FAILURE_MODES,
    get_model_for_failure_mode,
    get_cost_tracker,
    reset_cost_tracker,
)

# Prompts and definitions
from ._prompts import (
    MAST_FAILURE_DEFINITIONS,
    CHAIN_OF_THOUGHT_PROMPTS,
    KNOWLEDGE_AUGMENTED_MODES,
)

# Core classes
from .judge import MASTLLMJudge
from .detector import FullLLMDetector

__all__ = [
    # Enums
    "MASTFailureMode",
    # Dataclasses
    "JudgmentResult",
    "JudgeCostTracker",
    "ClaudeModelConfig",
    # Model configuration
    "CLAUDE_MODELS",
    "LOW_STAKES_MODEL_KEY",
    "DEFAULT_MODEL_KEY",
    "HIGH_STAKES_MODEL_KEY",
    "LOW_STAKES_FAILURE_MODES",
    "HIGH_STAKES_FAILURE_MODES",
    "get_model_for_failure_mode",
    "get_cost_tracker",
    "reset_cost_tracker",
    # Prompts
    "MAST_FAILURE_DEFINITIONS",
    "CHAIN_OF_THOUGHT_PROMPTS",
    "KNOWLEDGE_AUGMENTED_MODES",
    # Core classes
    "MASTLLMJudge",
    "FullLLMDetector",
]
