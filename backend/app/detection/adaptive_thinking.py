"""Adaptive Thinking Variance Detection.

Detects issues with Claude's adaptive thinking mode (early 2026).
Thresholds calibrated against real Claude pricing and behavior:
- Normal extended thinking: 5-15x thinking/output ratio
- Opus 4.6 with extended thinking: $0.15-0.40 per call normally
- Max effort legitimately takes 2-3 minutes

EXPERIMENTAL: Based on early data. Will improve with production traces.
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
    # Normal extended thinking is 5-15x. Flag at 20x+ (FinTech report: 40% cost
    # drop switching to adaptive = previous ratio was ~25-30x on routine queries)
    if thinking_tokens > 0 and output_tokens > 0:
        ratio = thinking_tokens / output_tokens
        if ratio > 20:
            scores.append(min(1.0, (ratio - 20) / 30))  # Gradual: 20x=0, 50x=1.0

    # 2. Underthinking: low effort + near-empty output
    # Short answers are valid. Only flag truly empty responses.
    if effort_level == "low" and output_tokens > 0 and output_tokens < 20:
        scores.append(0.5)

    # 3. Cost spike — Opus 4.6 with extended thinking can cost $0.40 normally.
    # Flag at $1.00+ (clearly anomalous for a single call).
    if cost_usd > 1.00:
        scores.append(min(1.0, cost_usd / 2.0))
    # High cost at low effort = likely misconfigured
    elif cost_usd > 0.50 and effort_level in ("low", "medium"):
        scores.append(0.6)

    # 4. Timeout risk — max effort legitimately takes 2-3 min.
    # Flag at 3 min+ (180s). Non-max effort should be faster.
    if latency_ms > 180000:  # 3 minutes
        scores.append(min(1.0, latency_ms / 300000))
    elif latency_ms > 90000 and effort_level not in ("high", "max"):
        scores.append(0.4)  # Slow for non-intensive effort

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
