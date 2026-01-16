"""
MAST LLM Judge Model Configuration
===================================

Claude model registry and tier selection for cost optimization.
"""

from typing import Dict

from ._dataclasses import ClaudeModelConfig, JudgeCostTracker


# All Claude models to benchmark for performance vs cost
CLAUDE_MODELS: Dict[str, ClaudeModelConfig] = {
    # Opus 4.5 - Highest quality, most expensive
    "opus-4.5": ClaudeModelConfig(
        model_id="claude-opus-4-5-20251101",
        input_price_per_1m=15.0,
        output_price_per_1m=75.0,
        context_window=200000,
    ),
    # Opus 4.5 with extended thinking - Best for complex reasoning
    "opus-4.5-thinking": ClaudeModelConfig(
        model_id="claude-opus-4-5-20251101",
        input_price_per_1m=15.0,
        output_price_per_1m=75.0,
        thinking_price_per_1m=10.0,
        use_extended_thinking=True,
        thinking_budget=16000,
        context_window=200000,
    ),
    # Sonnet 4 - Balanced performance/cost
    "sonnet-4": ClaudeModelConfig(
        model_id="claude-sonnet-4-20250514",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        context_window=200000,
    ),
    # Sonnet 4 with extended thinking - 32K budget for complex MAST analysis
    "sonnet-4-thinking": ClaudeModelConfig(
        model_id="claude-sonnet-4-20250514",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        thinking_price_per_1m=10.0,
        use_extended_thinking=True,
        thinking_budget=32000,  # Increased from 16K for F6/F8/F9/F13/F14 analysis
        context_window=200000,
    ),
    # Sonnet 3.5 - Previous generation, good balance
    "sonnet-3.5": ClaudeModelConfig(
        model_id="claude-3-5-sonnet-20241022",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        context_window=200000,
    ),
    # Haiku 3.5 - Fast and cheap
    "haiku-3.5": ClaudeModelConfig(
        model_id="claude-3-5-haiku-20241022",
        input_price_per_1m=0.80,
        output_price_per_1m=4.0,
        context_window=200000,
    ),
}

# 3-Tier Model Selection for Cost Optimization
# Benchmark results (claude_comparison_20260111): All achieve 97%+ accuracy

# Low-stakes model - haiku-3.5 at $0.0011/judgment (5x cheaper than sonnet)
LOW_STAKES_MODEL_KEY = "haiku-3.5"

# Default model - sonnet-4 provides 97.1% accuracy at 80% lower cost than opus
DEFAULT_MODEL_KEY = "sonnet-4"

# High-stakes model for critical failure modes - achieves 99.0% accuracy
HIGH_STAKES_MODEL_KEY = "sonnet-4-thinking"

# Low-stakes modes - high pattern accuracy, simple behavioral checks
# Based on benchmark: 100% accuracy with pattern-based detection
LOW_STAKES_FAILURE_MODES = {"F3", "F7", "F11", "F12"}

# High-stakes modes - complex semantic analysis required
# Based on benchmark results: these modes have higher complexity and ambiguity
# Updated to include zero-F1 modes that need chain-of-thought reasoning
HIGH_STAKES_FAILURE_MODES = {"F6", "F8", "F9", "F13", "F14"}

# Default tier (sonnet-4): F1, F2, F4, F5, F10 - moderate complexity


def get_model_for_failure_mode(failure_mode: str) -> str:
    """
    Select optimal model based on failure mode complexity (3-tier).

    Tier 1 (Low-stakes): haiku-3.5 for F3, F7, F11, F12, F14
        - $0.0011/judgment, 97.1% accuracy
        - High pattern accuracy, simple behavioral checks

    Tier 2 (Default): sonnet-4 for F1, F2, F4, F5, F10, F13
        - $0.0048/judgment, 97.1% accuracy
        - Moderate semantic complexity

    Tier 3 (High-stakes): sonnet-4-thinking for F6, F8, F9
        - $0.0163/judgment, 99.0% accuracy
        - Complex semantic analysis with extended thinking

    Args:
        failure_mode: MAST failure mode code (e.g., "F6", "F8")

    Returns:
        Model key to use for detection
    """
    mode = failure_mode.upper()
    if mode in HIGH_STAKES_FAILURE_MODES:
        return HIGH_STAKES_MODEL_KEY
    elif mode in LOW_STAKES_FAILURE_MODES:
        return LOW_STAKES_MODEL_KEY
    return DEFAULT_MODEL_KEY


# Global cost tracker
_cost_tracker = JudgeCostTracker()


def get_cost_tracker() -> JudgeCostTracker:
    """Get the global cost tracker."""
    return _cost_tracker


def reset_cost_tracker():
    """Reset the global cost tracker."""
    global _cost_tracker
    _cost_tracker = JudgeCostTracker()
