"""
MAST LLM Judge Model Configuration
===================================

Multi-provider model registry and tier selection for cost optimization.

Supported Providers:
- Anthropic (Claude models)
- Google (Gemini models)
- OpenAI (GPT/o-series models)

Migration Note (Jan 2026):
- Claude Haiku 3.5 deprecated Feb 2026
- Tier 1 migrated to Gemini 2.5 Flash-Lite (87% cost savings)
- Summarizer migrated to Gemini 2.5 Flash
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from ._dataclasses import ClaudeModelConfig, JudgeCostTracker


class ModelProvider(Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENAI = "openai"


@dataclass
class ModelConfig:
    """Provider-agnostic model configuration."""
    model_id: str
    provider: ModelProvider
    input_price_per_1m: float
    output_price_per_1m: float
    context_window: int = 200000
    supports_thinking: bool = False
    thinking_price_per_1m: float = 0.0
    thinking_budget: int = 0
    deprecated: bool = False
    deprecation_date: Optional[str] = None
    replacement_model: Optional[str] = None


# =============================================================================
# Multi-Provider Model Registry
# =============================================================================

MODELS: Dict[str, ModelConfig] = {
    # -------------------------------------------------------------------------
    # TIER 1: Low-stakes / Simple Detection (F3, F7, F11, F12)
    # Primary: Gemini 2.5 Flash-Lite ($0.10/$0.40) - 87% cheaper than Haiku 3.5
    # -------------------------------------------------------------------------
    "gemini-flash-lite": ModelConfig(
        model_id="gemini-2.5-flash-lite",
        provider=ModelProvider.GOOGLE,
        input_price_per_1m=0.10,
        output_price_per_1m=0.40,
        context_window=1000000,
    ),
    "gpt-4o-mini": ModelConfig(
        model_id="gpt-4o-mini",
        provider=ModelProvider.OPENAI,
        input_price_per_1m=0.15,
        output_price_per_1m=0.60,
        context_window=128000,
    ),
    "haiku-4.5": ModelConfig(
        model_id="claude-haiku-4-5-20251001",
        provider=ModelProvider.ANTHROPIC,
        input_price_per_1m=1.00,
        output_price_per_1m=5.00,
        context_window=200000,
    ),

    # -------------------------------------------------------------------------
    # TIER 2: Default / Moderate Complexity (F1, F2, F4, F5, F10, F13)
    # Primary: Claude Sonnet 4 ($3/$15) or o3 ($2/$8) for cost optimization
    # -------------------------------------------------------------------------
    "o3": ModelConfig(
        model_id="o3",
        provider=ModelProvider.OPENAI,
        input_price_per_1m=2.00,
        output_price_per_1m=8.00,
        context_window=200000,
        supports_thinking=True,
    ),
    "gpt-4o": ModelConfig(
        model_id="gpt-4o",
        provider=ModelProvider.OPENAI,
        input_price_per_1m=2.50,
        output_price_per_1m=10.00,
        context_window=128000,
    ),
    "sonnet-4": ModelConfig(
        model_id="claude-sonnet-4-20250514",
        provider=ModelProvider.ANTHROPIC,
        input_price_per_1m=3.00,
        output_price_per_1m=15.00,
        context_window=200000,
    ),
    "gemini-flash": ModelConfig(
        model_id="gemini-2.5-flash",
        provider=ModelProvider.GOOGLE,
        input_price_per_1m=0.15,
        output_price_per_1m=0.60,
        context_window=1000000,
    ),

    # -------------------------------------------------------------------------
    # TIER 3: High-stakes / Complex Reasoning (F6, F8, F9, F14)
    # Primary: Claude Sonnet 4 + Thinking ($3/$15 + $10/1M thinking)
    # -------------------------------------------------------------------------
    "sonnet-4-thinking": ModelConfig(
        model_id="claude-sonnet-4-20250514",
        provider=ModelProvider.ANTHROPIC,
        input_price_per_1m=3.00,
        output_price_per_1m=15.00,
        thinking_price_per_1m=10.00,
        supports_thinking=True,
        thinking_budget=32000,
        context_window=200000,
    ),
    "o3-mini-high": ModelConfig(
        model_id="o3-mini",
        provider=ModelProvider.OPENAI,
        input_price_per_1m=1.10,
        output_price_per_1m=4.40,
        context_window=200000,
        supports_thinking=True,
    ),

    # -------------------------------------------------------------------------
    # PREMIUM: Opus 4.5 for critical analysis
    # -------------------------------------------------------------------------
    "opus-4.5": ModelConfig(
        model_id="claude-opus-4-5-20251101",
        provider=ModelProvider.ANTHROPIC,
        input_price_per_1m=5.00,  # Updated from $15 (Jan 2026 price)
        output_price_per_1m=25.00,  # Updated from $75
        context_window=200000,
    ),
    "opus-4.5-thinking": ModelConfig(
        model_id="claude-opus-4-5-20251101",
        provider=ModelProvider.ANTHROPIC,
        input_price_per_1m=5.00,
        output_price_per_1m=25.00,
        thinking_price_per_1m=10.00,
        supports_thinking=True,
        thinking_budget=16000,
        context_window=200000,
    ),

    # -------------------------------------------------------------------------
    # DEPRECATED: Haiku 3.5 - DO NOT USE (Feb 2026 sunset)
    # -------------------------------------------------------------------------
    "haiku-3.5": ModelConfig(
        model_id="claude-3-5-haiku-20241022",
        provider=ModelProvider.ANTHROPIC,
        input_price_per_1m=0.80,
        output_price_per_1m=4.00,
        context_window=200000,
        deprecated=True,
        deprecation_date="2026-02",
        replacement_model="gemini-flash-lite",
    ),
    "sonnet-3.5": ModelConfig(
        model_id="claude-3-5-sonnet-20241022",
        provider=ModelProvider.ANTHROPIC,
        input_price_per_1m=3.00,
        output_price_per_1m=15.00,
        context_window=200000,
        deprecated=True,
        deprecation_date="2026-06",
        replacement_model="sonnet-4",
    ),
}


# Legacy compatibility: ClaudeModelConfig format for existing code
CLAUDE_MODELS: Dict[str, ClaudeModelConfig] = {
    "opus-4.5": ClaudeModelConfig(
        model_id="claude-opus-4-5-20251101",
        input_price_per_1m=5.0,
        output_price_per_1m=25.0,
        context_window=200000,
    ),
    "opus-4.5-thinking": ClaudeModelConfig(
        model_id="claude-opus-4-5-20251101",
        input_price_per_1m=5.0,
        output_price_per_1m=25.0,
        thinking_price_per_1m=10.0,
        use_extended_thinking=True,
        thinking_budget=16000,
        context_window=200000,
    ),
    "sonnet-4": ClaudeModelConfig(
        model_id="claude-sonnet-4-20250514",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        context_window=200000,
    ),
    "sonnet-4-thinking": ClaudeModelConfig(
        model_id="claude-sonnet-4-20250514",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        thinking_price_per_1m=10.0,
        use_extended_thinking=True,
        thinking_budget=32000,
        context_window=200000,
    ),
    # Haiku 4.5 as Tier 1 Claude fallback
    "haiku-4.5": ClaudeModelConfig(
        model_id="claude-haiku-4-5-20251001",
        input_price_per_1m=1.0,
        output_price_per_1m=5.0,
        context_window=200000,
    ),
    # DEPRECATED - will be removed Feb 2026
    "haiku-3.5": ClaudeModelConfig(
        model_id="claude-3-5-haiku-20241022",
        input_price_per_1m=0.80,
        output_price_per_1m=4.0,
        context_window=200000,
    ),
}

# =============================================================================
# 3-Tier Model Selection for Cost Optimization
# =============================================================================
# Benchmark results (claude_comparison_20260111): All achieve 97%+ accuracy
#
# MIGRATION (Jan 2026): Haiku 3.5 deprecated Feb 2026
# - Tier 1 now uses Gemini 2.5 Flash-Lite (87% cost savings)
# - Claude Haiku 4.5 available as premium fallback

# Tier 1: Low-stakes - gemini-flash-lite at $0.00025/judgment (87% cheaper than haiku-3.5)
LOW_STAKES_MODEL_KEY = "gemini-flash-lite"
LOW_STAKES_CLAUDE_FALLBACK = "haiku-4.5"  # If Gemini unavailable

# Tier 2: Default - sonnet-4 provides 97.1% accuracy
DEFAULT_MODEL_KEY = "sonnet-4"
DEFAULT_COST_OPTIMIZED = "o3"  # 33% cheaper alternative

# Tier 3: High-stakes - sonnet-4-thinking for complex reasoning
HIGH_STAKES_MODEL_KEY = "sonnet-4-thinking"

from app.core.mast_constants import HIGH_STAKES_FAILURE_MODES, LOW_STAKES_FAILURE_MODES

# Default tier (sonnet-4): F1, F2, F4, F5, F10, F13 - moderate complexity


def get_model_for_failure_mode(failure_mode: str, cost_optimized: bool = False) -> str:
    """
    Select optimal model based on failure mode complexity (3-tier).

    Tier 1 (Low-stakes): gemini-flash-lite for F3, F7, F11, F12
        - $0.00025/judgment (87% cheaper than deprecated haiku-3.5)
        - High pattern accuracy, simple behavioral checks

    Tier 2 (Default): sonnet-4 for F1, F2, F4, F5, F10, F13
        - $0.0048/judgment, 97.1% accuracy
        - Or o3 at $0.0032/judgment when cost_optimized=True

    Tier 3 (High-stakes): sonnet-4-thinking for F6, F8, F9, F14
        - $0.0163/judgment, 99.0% accuracy
        - Complex semantic analysis with extended thinking

    Args:
        failure_mode: MAST failure mode code (e.g., "F6", "F8")
        cost_optimized: Use cheaper alternatives where available

    Returns:
        Model key to use for detection
    """
    mode = failure_mode.upper()

    if mode in HIGH_STAKES_FAILURE_MODES:
        return HIGH_STAKES_MODEL_KEY
    elif mode in LOW_STAKES_FAILURE_MODES:
        return LOW_STAKES_MODEL_KEY
    else:
        # Default tier - optionally use cost-optimized model
        if cost_optimized:
            return DEFAULT_COST_OPTIMIZED
        return DEFAULT_MODEL_KEY


def get_model_config(model_key: str) -> ModelConfig:
    """Get configuration for a model by key.

    Args:
        model_key: Key from MODELS registry

    Returns:
        ModelConfig for the model

    Raises:
        KeyError: If model_key not found
    """
    config = MODELS.get(model_key)
    if config is None:
        raise KeyError(f"Unknown model: {model_key}. Available: {list(MODELS.keys())}")

    if config.deprecated:
        import warnings
        warnings.warn(
            f"Model '{model_key}' is deprecated (sunset: {config.deprecation_date}). "
            f"Use '{config.replacement_model}' instead.",
            DeprecationWarning,
            stacklevel=2
        )

    return config


def get_recommended_models_by_tier() -> dict:
    """Get recommended models for each tier with cost comparison.

    Returns:
        Dict with tier info and model recommendations
    """
    return {
        "tier_1_low_stakes": {
            "primary": "gemini-flash-lite",
            "fallback": "haiku-4.5",
            "cost_per_1m_input": 0.10,
            "failure_modes": list(LOW_STAKES_FAILURE_MODES),
        },
        "tier_2_default": {
            "primary": "sonnet-4",
            "cost_optimized": "o3",
            "cost_per_1m_input": 3.00,
            "failure_modes": ["F1", "F2", "F4", "F5", "F10", "F13"],
        },
        "tier_3_high_stakes": {
            "primary": "sonnet-4-thinking",
            "cost_per_1m_input": 3.00,
            "thinking_cost_per_1m": 10.00,
            "failure_modes": list(HIGH_STAKES_FAILURE_MODES),
        },
    }


# Global cost tracker
_cost_tracker = JudgeCostTracker()


def get_cost_tracker() -> JudgeCostTracker:
    """Get the global cost tracker."""
    return _cost_tracker


def reset_cost_tracker():
    """Reset the global cost tracker."""
    global _cost_tracker
    _cost_tracker = JudgeCostTracker()
