"""Ad-hoc scorer generation and execution service.

Generates custom LLM-as-judge evaluators from natural language descriptions.
Users describe a quality concern, and this service creates a structured
evaluation prompt that can be run against traces.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Model pricing per million tokens
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
}

MODEL_ALIASES = {
    "sonnet-4": "claude-sonnet-4-20250514",
    "haiku-4.5": "claude-haiku-4-5-20251001",
}


GENERATION_SYSTEM_PROMPT = """You are an expert in evaluating AI agent quality.
Given a natural language description of a quality concern, generate a structured evaluation scorer.

Respond with a JSON object containing:
{
    "name": "Short name for this scorer (3-5 words)",
    "prompt_template": "A detailed evaluation prompt that an LLM judge will use to score traces. Include specific criteria, what to look for, and scoring guidelines. The prompt should reference {task}, {trace_summary}, {key_events}, and {agent_interactions} as template variables.",
    "scoring_criteria": ["criterion1", "criterion2", ...],
    "scoring_rubric": "1 = Very Poor: ... 2 = Poor: ... 3 = Adequate: ... 4 = Good: ... 5 = Excellent: ..."
}"""


EVALUATION_TEMPLATE = """You are evaluating an AI agent trace for quality.

## Evaluation Criteria
{prompt_template}

## Trace to Evaluate

**Task**: {task}

**Trace Summary**:
{trace_summary}

**Key Events**:
{key_events}

**Agent Interactions**:
{agent_interactions}

## Instructions
Score this trace on a scale of 1-5. Respond with a JSON object:
{{
    "score": <1-5>,
    "confidence": <0-100>,
    "verdict": "<PASS|WARN|FAIL|UNCERTAIN>",
    "reasoning": "Brief explanation of your assessment",
    "evidence": ["specific evidence point 1", "evidence point 2"],
    "suggestions": ["improvement suggestion 1", "suggestion 2"]
}}"""


@dataclass
class ScorerGenerationResult:
    name: str
    prompt_template: str
    scoring_criteria: List[str]
    scoring_rubric: str
    model_used: str
    tokens_used: int
    cost_usd: float


@dataclass
class ScoringResult:
    score: int  # 1-5
    confidence: int  # 0-100
    verdict: str  # PASS, WARN, FAIL, UNCERTAIN
    reasoning: str
    evidence: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    model_used: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class AdHocScorerService:
    """Generates and runs custom quality scorers from natural language."""

    def __init__(self, model_key: str = "sonnet-4"):
        resolved = MODEL_ALIASES.get(model_key, model_key)
        if resolved not in MODEL_PRICING:
            resolved = "claude-sonnet-4-20250514"
        self._model_id = resolved
        pricing = MODEL_PRICING[resolved]
        self._input_price = pricing["input"]
        self._output_price = pricing["output"]
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def generate_scorer(self, description: str) -> ScorerGenerationResult:
        """Generate a scorer prompt from natural language description."""
        response = self.client.messages.create(
            model=self._model_id,
            max_tokens=4096,
            system=GENERATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Create an evaluation scorer for:\n\n{description}"}],
        )
        raw = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        cost = (response.usage.input_tokens * self._input_price + response.usage.output_tokens * self._output_price) / 1_000_000

        parsed = self._extract_json(raw)
        return ScorerGenerationResult(
            name=parsed.get("name", description[:50]),
            prompt_template=parsed.get("prompt_template", raw),
            scoring_criteria=parsed.get("scoring_criteria", []),
            scoring_rubric=parsed.get("scoring_rubric", ""),
            model_used=self._model_id,
            tokens_used=tokens,
            cost_usd=cost,
        )

    def score_trace(
        self,
        prompt_template: str,
        task: str,
        trace_summary: str,
        key_events: List[str],
        agent_interactions: Optional[List[str]] = None,
    ) -> ScoringResult:
        """Score a single trace using a generated prompt template."""
        start = time.time()
        full_prompt = EVALUATION_TEMPLATE.format(
            prompt_template=prompt_template,
            task=task,
            trace_summary=trace_summary,
            key_events="\n".join(f"- {e}" for e in key_events) if key_events else "N/A",
            agent_interactions="\n".join(f"- {i}" for i in (agent_interactions or [])) or "N/A",
        )

        response = self.client.messages.create(
            model=self._model_id,
            max_tokens=2048,
            messages=[{"role": "user", "content": full_prompt}],
        )
        latency_ms = int((time.time() - start) * 1000)
        raw = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        cost = (response.usage.input_tokens * self._input_price + response.usage.output_tokens * self._output_price) / 1_000_000

        parsed = self._extract_json(raw)
        score = max(1, min(5, parsed.get("score", 3)))
        confidence = max(0, min(100, parsed.get("confidence", 50)))
        verdict = parsed.get("verdict", "UNCERTAIN")
        if verdict not in ("PASS", "FAIL", "WARN", "UNCERTAIN"):
            verdict = "PASS" if score >= 4 else "FAIL" if score <= 2 else "WARN"

        return ScoringResult(
            score=score,
            confidence=confidence,
            verdict=verdict,
            reasoning=parsed.get("reasoning", raw[:500]),
            evidence=parsed.get("evidence", []),
            suggestions=parsed.get("suggestions", []),
            model_used=self._model_id,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling various formats."""
        # Try ```json ... ``` code blocks
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try raw JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try outermost braces
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            try:
                return json.loads(brace.group(0))
            except json.JSONDecodeError:
                pass
        return {}
