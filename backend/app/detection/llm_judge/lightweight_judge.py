"""Tiered LLM judge — Haiku → Sonnet → Opus escalation for detection verification.

Tier 1: Haiku (~$0.001/call) — fast, cheap, handles clear cases
Tier 2: Sonnet (~$0.01/call) — only if Haiku is uncertain (confidence 0.35-0.65)
Tier 3: Opus (~$0.05/call) — only if Sonnet is still uncertain

Typical cost per entry: $0.001 (80% resolved by Haiku)
Worst case: $0.06 (all three tiers)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
}

# Per-million token pricing (input, output)
PRICING = {
    "haiku": (0.80, 4.0),
    "sonnet": (3.0, 15.0),
    "opus": (15.0, 75.0),
}

AMBIGUOUS_RANGE = (0.35, 0.65)  # Confidence range that triggers escalation

_client = None


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic()
    return _client


@dataclass
class TieredVerdict:
    detected: bool
    confidence: float
    reasoning: str
    tier_used: str  # "haiku", "sonnet", "opus", or "rule" (no LLM needed)
    tiers_called: List[str] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0


def _build_prompt(detection_type: str, input_data: Dict[str, Any], rule_confidence: float) -> str:
    data_str = json.dumps(input_data, indent=2, default=str)
    if len(data_str) > 3000:
        data_str = data_str[:3000] + "\n... (truncated)"

    return f"""You are an expert evaluator for multi-agent AI system failures.

A rule-based detector flagged this as a potential "{detection_type}" failure with confidence {rule_confidence:.2f}.

Determine if this is a REAL failure or a FALSE POSITIVE.

Data:
{data_str}

Detection types:
- hallucination: Output contains claims not supported by sources/context
- derailment: Agent drifted off-topic from assigned task
- coordination_failure: Agents failed to communicate/coordinate
- corruption: State contains impossible/contradictory values
- loop: Agent repeats same action without progress

Respond EXACTLY:
VERDICT: YES or NO
CONFIDENCE: 0.0 to 1.0
REASON: one sentence

YES = failure IS present. NO = false positive."""


def _call_model(tier: str, prompt: str) -> tuple[bool, float, str, float, int]:
    """Call a specific model tier. Returns (detected, confidence, reasoning, cost, tokens)."""
    client = _get_client()
    model = MODELS[tier]
    pricing = PRICING[tier]

    response = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    tokens = response.usage.input_tokens + response.usage.output_tokens
    cost = (response.usage.input_tokens * pricing[0] + response.usage.output_tokens * pricing[1]) / 1_000_000

    detected = "VERDICT: YES" in text.upper()
    confidence = 0.5
    reasoning = text

    for line in text.split("\n"):
        line = line.strip()
        if line.upper().startswith("CONFIDENCE:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.upper().startswith("REASON:"):
            reasoning = line.split(":", 1)[1].strip()

    return detected, confidence, reasoning, cost, tokens


def tiered_judge(
    detection_type: str,
    input_data: Dict[str, Any],
    rule_confidence: float = 0.5,
    max_tier: str = "opus",  # "haiku", "sonnet", or "opus"
) -> TieredVerdict:
    """Run tiered LLM judging: Haiku first, escalate if uncertain.

    Args:
        detection_type: What failure to check for
        input_data: The trace/entry data
        rule_confidence: What the rule-based detector said (0-1)
        max_tier: Maximum tier to escalate to

    Returns:
        TieredVerdict with final decision and cost tracking
    """
    prompt = _build_prompt(detection_type, input_data, rule_confidence)
    tiers = ["haiku", "sonnet", "opus"]
    max_idx = tiers.index(max_tier)

    total_cost = 0.0
    total_tokens = 0
    tiers_called = []

    for i, tier in enumerate(tiers):
        if i > max_idx:
            break

        try:
            detected, confidence, reasoning, cost, tokens = _call_model(tier, prompt)
            total_cost += cost
            total_tokens += tokens
            tiers_called.append(tier)

            logger.info(
                "[%s] %s: detected=%s conf=%.2f cost=$%.4f",
                tier, detection_type, detected, confidence, cost,
            )

            # If confident enough, stop here
            if confidence < AMBIGUOUS_RANGE[0] or confidence > AMBIGUOUS_RANGE[1]:
                return TieredVerdict(
                    detected=detected,
                    confidence=confidence,
                    reasoning=reasoning,
                    tier_used=tier,
                    tiers_called=tiers_called,
                    total_cost_usd=round(total_cost, 6),
                    total_tokens=total_tokens,
                )

            # Still ambiguous — escalate to next tier
            logger.info("[%s] %s: ambiguous (%.2f), escalating", tier, detection_type, confidence)

        except Exception as exc:
            logger.warning("[%s] %s: failed: %s", tier, detection_type, exc)
            tiers_called.append(f"{tier}(failed)")
            # Continue to next tier

    # All tiers exhausted or all failed — return best result
    return TieredVerdict(
        detected=rule_confidence >= 0.5,
        confidence=rule_confidence,
        reasoning="All tiers exhausted or ambiguous",
        tier_used=tiers_called[-1] if tiers_called else "rule",
        tiers_called=tiers_called,
        total_cost_usd=round(total_cost, 6),
        total_tokens=total_tokens,
    )
