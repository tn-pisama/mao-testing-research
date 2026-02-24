"""Shared scoring utilities for agent and orchestration quality scorers."""

from typing import Dict, Any, Optional


class LLMScorerMixin:
    """Mixin providing LLM score blending and escalation logic.

    Requires the consuming class to set:
        self._judge: Optional LLM judge instance
        self.use_llm_judge: bool
        self.escalation_range: Tuple[float, float]
    """

    def _should_use_llm(self, heuristic_score: float) -> bool:
        """Determine if LLM evaluation should be used for this score."""
        if not self._judge:
            return False
        if self.use_llm_judge:
            return True
        # Escalate ambiguous scores
        return self.escalation_range[0] < heuristic_score < self.escalation_range[1]

    def _blend_scores(
        self,
        heuristic_score: float,
        llm_result: Optional[Dict[str, Any]],
        dim_score: Any,
    ) -> float:
        """Blend heuristic and LLM scores, annotating the dimension with reasoning."""
        if llm_result is None:
            return heuristic_score
        llm_score = llm_result["score"]
        tokens = llm_result.get("tokens", 0)
        reasoning = llm_result.get("reasoning", "")
        # If LLM call failed (0 tokens or API error), fall back to heuristic only
        if tokens == 0 or "API error" in reasoning or "Error" in reasoning[:20]:
            dim_score.evidence["llm_fallback"] = True
            dim_score.evidence["llm_error"] = reasoning
            return heuristic_score
        blended = 0.3 * heuristic_score + 0.7 * llm_score
        dim_score.evidence["llm_score"] = round(llm_score, 3)
        dim_score.evidence["heuristic_score"] = round(heuristic_score, 3)
        dim_score.evidence["llm_reasoning"] = reasoning
        dim_score.evidence["scoring_tier"] = "llm"
        dim_score.evidence["llm_tokens"] = tokens
        return blended
