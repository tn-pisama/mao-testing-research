"""
MAST LLM Judge Dataclasses
==========================

Data structures for judgment results, cost tracking, and model configuration.
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


@dataclass
class JudgeCostTracker:
    """Tracks cumulative costs for LLM judge calls with per-tier breakdown."""
    total_calls: int = 0
    cached_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    # Per-tier tracking for cost analysis
    haiku_calls: int = 0
    haiku_cost: float = 0.0
    sonnet_calls: int = 0
    sonnet_cost: float = 0.0
    sonnet_thinking_calls: int = 0
    sonnet_thinking_cost: float = 0.0

    def record(self, result: JudgmentResult):
        self.total_calls += 1
        if result.cached:
            self.cached_calls += 1
        else:
            self.total_tokens += result.tokens_used
            self.total_cost_usd += result.cost_usd
            # Track per-tier costs
            model = result.model_used.lower()
            if "haiku" in model:
                self.haiku_calls += 1
                self.haiku_cost += result.cost_usd
            elif "thinking" in model or "extended" in model:
                self.sonnet_thinking_calls += 1
                self.sonnet_thinking_cost += result.cost_usd
            else:
                self.sonnet_calls += 1
                self.sonnet_cost += result.cost_usd

    def get_tier_summary(self) -> dict:
        """Get cost breakdown by tier."""
        return {
            "haiku": {"calls": self.haiku_calls, "cost": self.haiku_cost},
            "sonnet": {"calls": self.sonnet_calls, "cost": self.sonnet_cost},
            "sonnet_thinking": {"calls": self.sonnet_thinking_calls, "cost": self.sonnet_thinking_cost},
            "total": {"calls": self.total_calls, "cost": self.total_cost_usd},
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
