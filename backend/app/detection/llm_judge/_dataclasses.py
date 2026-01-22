"""
MAST LLM Judge Dataclasses
==========================

Data structures for judgment results, cost tracking, and model configuration.

Version: 2.0 (Jan 2026)
- Added multi-provider support (Anthropic, Google, OpenAI)
- Added provider-level cost tracking
"""

from dataclasses import dataclass, field
from typing import Dict

from ._enums import MASTFailureMode


@dataclass
class JudgmentResult:
    """Result from LLM judge evaluation."""
    failure_mode: MASTFailureMode
    verdict: str  # YES, NO, UNCERTAIN
    confidence: float
    reasoning: str
    raw_response: str
    model_used: str
    tokens_used: int
    cost_usd: float
    cached: bool = False
    latency_ms: int = 0
    provider: str = "anthropic"  # anthropic, google, openai


@dataclass
class JudgeCostTracker:
    """Tracks cumulative costs for LLM judge calls with per-tier and per-provider breakdown."""
    total_calls: int = 0
    cached_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Per-tier tracking (legacy, maintained for backward compatibility)
    haiku_calls: int = 0
    haiku_cost: float = 0.0
    sonnet_calls: int = 0
    sonnet_cost: float = 0.0
    sonnet_thinking_calls: int = 0
    sonnet_thinking_cost: float = 0.0

    # Per-provider tracking (Jan 2026)
    anthropic_calls: int = 0
    anthropic_cost: float = 0.0
    google_calls: int = 0
    google_cost: float = 0.0
    openai_calls: int = 0
    openai_cost: float = 0.0

    # Tier 1 specific (gemini-flash-lite / haiku-4.5)
    tier1_calls: int = 0
    tier1_cost: float = 0.0

    # Tier 2 specific (sonnet-4 / o3)
    tier2_calls: int = 0
    tier2_cost: float = 0.0

    # Tier 3 specific (sonnet-4-thinking)
    tier3_calls: int = 0
    tier3_cost: float = 0.0

    def record(self, result: JudgmentResult):
        self.total_calls += 1
        if result.cached:
            self.cached_calls += 1
        else:
            self.total_tokens += result.tokens_used
            self.total_cost_usd += result.cost_usd

            # Track per-provider costs
            provider = result.provider.lower() if hasattr(result, 'provider') else "anthropic"
            if provider == "google":
                self.google_calls += 1
                self.google_cost += result.cost_usd
            elif provider == "openai":
                self.openai_calls += 1
                self.openai_cost += result.cost_usd
            else:
                self.anthropic_calls += 1
                self.anthropic_cost += result.cost_usd

            # Track per-tier costs (legacy + new)
            model = result.model_used.lower()

            # Tier 1: flash-lite, gpt-4o-mini, haiku
            if "flash-lite" in model or "4o-mini" in model or "haiku" in model:
                self.tier1_calls += 1
                self.tier1_cost += result.cost_usd
                # Legacy tracking
                self.haiku_calls += 1
                self.haiku_cost += result.cost_usd

            # Tier 3: thinking models
            elif "thinking" in model or "extended" in model:
                self.tier3_calls += 1
                self.tier3_cost += result.cost_usd
                # Legacy tracking
                self.sonnet_thinking_calls += 1
                self.sonnet_thinking_cost += result.cost_usd

            # Tier 2: everything else (sonnet, o3, gpt-4o, flash)
            else:
                self.tier2_calls += 1
                self.tier2_cost += result.cost_usd
                # Legacy tracking
                self.sonnet_calls += 1
                self.sonnet_cost += result.cost_usd

    def get_tier_summary(self) -> dict:
        """Get cost breakdown by tier (legacy format)."""
        return {
            "haiku": {"calls": self.haiku_calls, "cost": self.haiku_cost},
            "sonnet": {"calls": self.sonnet_calls, "cost": self.sonnet_cost},
            "sonnet_thinking": {"calls": self.sonnet_thinking_calls, "cost": self.sonnet_thinking_cost},
            "total": {"calls": self.total_calls, "cost": self.total_cost_usd},
        }

    def get_provider_summary(self) -> dict:
        """Get cost breakdown by provider."""
        return {
            "anthropic": {"calls": self.anthropic_calls, "cost": self.anthropic_cost},
            "google": {"calls": self.google_calls, "cost": self.google_cost},
            "openai": {"calls": self.openai_calls, "cost": self.openai_cost},
            "total": {"calls": self.total_calls, "cost": self.total_cost_usd},
        }

    def get_full_summary(self) -> dict:
        """Get complete cost breakdown by tier and provider."""
        return {
            "by_tier": {
                "tier_1_low_stakes": {"calls": self.tier1_calls, "cost": self.tier1_cost},
                "tier_2_default": {"calls": self.tier2_calls, "cost": self.tier2_cost},
                "tier_3_high_stakes": {"calls": self.tier3_calls, "cost": self.tier3_cost},
            },
            "by_provider": self.get_provider_summary(),
            "totals": {
                "calls": self.total_calls,
                "cached_calls": self.cached_calls,
                "tokens": self.total_tokens,
                "cost_usd": self.total_cost_usd,
            }
        }


@dataclass
class ClaudeModelConfig:
    """Configuration for a Claude model variant."""
    model_id: str
    input_price_per_1m: float
    output_price_per_1m: float
    thinking_price_per_1m: float = 0.0
    use_extended_thinking: bool = False
    thinking_budget: int = 0  # Max thinking tokens (0 = disabled)
    context_window: int = 200000
