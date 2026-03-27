"""Adaptive Thinking Variance Detection.

Detects issues with Claude's adaptive thinking mode (early 2026):
- Overthinking: thinking_tokens >> output_tokens (wasted compute)
- Underthinking: low effort + minimal output (quality risk)
- Cost spikes: single call exceeding budget
- Timeout risk: extreme latency from max effort

Based on Claude Adaptive Thinking (replaces binary extended thinking).
"""

from typing import Tuple

def detect(
    effort_level: str = "high",
    thinking_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    prompt: str = "",
    output: str = "",
) -> Tuple[bool, float]:
    scores = []

    # 1. Overthinking: thinking >> output
    if thinking_tokens > 0 and output_tokens > 0:
        ratio = thinking_tokens / output_tokens
        if ratio > 10:
            scores.append(min(1.0, ratio / 20))

    # 2. Underthinking: low effort + tiny output
    if effort_level in ("low", "medium") and output_tokens > 0 and output_tokens < 50:
        scores.append(0.6)
    if effort_level == "low" and output and len(output.split()) < 10:
        scores.append(0.5)

    # 3. Cost spike
    if cost_usd > 0.50:
        scores.append(min(1.0, cost_usd / 1.0))
    elif cost_usd > 0.20 and effort_level in ("low", "medium"):
        scores.append(0.6)  # High cost for low effort = misconfigured

    # 4. Timeout risk
    if latency_ms > 120000:  # 2 minutes
        scores.append(min(1.0, latency_ms / 180000))
    elif latency_ms > 60000 and effort_level != "max":
        scores.append(0.5)  # Slow for non-max effort

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
