"""Inverted LLM Judge Prompts for Tiered Detection
===================================================

Instead of asking "Is this a failure?" (which triggers conservative LLM bias
toward saying NO), we ask "Is this CORRECT?" -- now a NO means failure detected,
exploiting the same conservative bias in our favor.

Validated on real golden dataset entries (2026-03-23). Six detectors showed
significant F1 improvement over rule-based detection:
  - retrieval_quality: +0.759
  - grounding:         +0.489
  - derailment:        +0.349
  - hallucination:     +0.218
  - convergence:       +0.147
  - specification:     +0.088
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic client (lazy init)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from anthropic import Anthropic
            _client = Anthropic()
        except Exception as e:
            logger.warning("Cannot create Anthropic client: %s", e)
            raise
    return _client


HAIKU_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Inverted prompt templates: "Is this CORRECT?" -- INCORRECT means failure
# ---------------------------------------------------------------------------

INVERTED_PROMPTS: Dict[str, str] = {
    "hallucination": """Evaluate this agent output for factual accuracy.

Sources provided:
{sources}

Agent output:
{output}

Is the agent's output factually accurate and fully supported by the sources? Does it contain ONLY information that can be verified from the provided sources?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "grounding": """Evaluate whether this agent output is properly grounded.

Source documents:
{source_documents}

Agent output:
{agent_output}

Is every factual claim in the output directly supported by the source documents?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "specification": """Evaluate whether this task specification matches the user's intent.

User's intent: {user_intent}

Task specification: {task_specification}

Does the specification accurately capture what the user asked for, without adding unrequested scope or missing key requirements?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "derailment": """Evaluate whether this agent stayed on task.

Task: {task}

Agent output: {output}

Did the agent address the assigned task? Is the output relevant to what was asked?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "convergence": """Evaluate these optimization metrics.

Metrics: {metrics}
Direction: {direction}
Window: {window_size}

Are these metrics showing healthy progress in the desired direction?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "withholding": """Evaluate whether this agent is sharing all relevant information.

Agent's internal state (what it knows):
{internal_state}

Agent's output (what it communicated):
{agent_output}

Did the agent share all critical findings, errors, warnings, and important details from its internal state? Is the output a fair and complete representation of what the agent discovered?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "retrieval_quality": """Evaluate this retrieval result.

Query: {query}
Retrieved documents: {retrieved_documents}
Agent output: {agent_output}

Are the retrieved documents relevant to the query? Did the retrieval serve the agent's needs?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",
}

# The 6 detectors where inverted prompting outperforms MAST prompts
INVERTED_DETECTORS = set(INVERTED_PROMPTS.keys())


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_value(value: Any) -> str:
    """Format a single value for prompt substitution."""
    if isinstance(value, dict):
        if "content" in value:
            return str(value["content"])[:800]
        return json.dumps(value, indent=2)[:800]
    return str(value)[:800]


def _format_prompt(det_name: str, input_data: Dict[str, Any]) -> str:
    """Format an inverted prompt by substituting fields from input_data."""
    template = INVERTED_PROMPTS[det_name]
    formatted = template
    for key, value in input_data.items():
        placeholder = "{" + key + "}"
        if placeholder not in formatted:
            continue
        if isinstance(value, list):
            parts = []
            for i, item in enumerate(value[:10]):
                parts.append(f"[{i+1}] {_format_value(item)}")
            value_str = "\n".join(parts)
        elif isinstance(value, dict):
            value_str = _format_value(value)
        else:
            value_str = str(value)[:1000]
        formatted = formatted.replace(placeholder, value_str)

    # Remove any unfilled placeholders
    formatted = re.sub(r"\{[a-z_]+\}", "[not provided]", formatted)
    return formatted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_inverted_judge(
    detector_type: str,
    input_data: Dict[str, Any],
    model: Optional[str] = None,
) -> Tuple[bool, float, int]:
    """Run the inverted LLM judge for a detector.

    Asks "Is this CORRECT?" instead of "Is this a failure?" to exploit
    conservative LLM bias in our favor.

    Args:
        detector_type: Detector name (e.g. "hallucination", "grounding")
        input_data: The entry's input_data dict with detector-specific fields
        model: Override model (default: Haiku 4.5)

    Returns:
        (detected, cost_usd, tokens_used) -- detected=True if INCORRECT
        (failure found). Caller sets confidence to 0.80 for judge decisions.

    Raises:
        ValueError: If detector_type has no inverted prompt
        Exception: On API errors (caller should catch)
    """
    if detector_type not in INVERTED_PROMPTS:
        raise ValueError(
            f"No inverted prompt for '{detector_type}'. "
            f"Available: {sorted(INVERTED_PROMPTS.keys())}"
        )

    prompt = _format_prompt(detector_type, input_data)
    client = _get_client()
    use_model = model or HAIKU_MODEL

    response = client.messages.create(
        model=use_model,
        max_tokens=500,
        timeout=60.0,
        messages=[{"role": "user", "content": prompt}],
    )

    answer = response.content[0].text.strip()
    last_line = answer.strip().split("\n")[-1].strip().upper()

    # INVERTED: "INCORRECT" means failure detected
    detected = "INCORRECT" in last_line

    cost_usd = (
        response.usage.input_tokens * (1 / 1_000_000)
        + response.usage.output_tokens * (5 / 1_000_000)
    )
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    logger.debug(
        "Inverted judge %s: %s (cost=$%.4f, tokens=%d)",
        detector_type, "INCORRECT" if detected else "CORRECT",
        cost_usd, tokens_used,
    )

    return detected, cost_usd, tokens_used
