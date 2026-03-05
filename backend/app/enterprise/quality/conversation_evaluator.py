"""Conversation-level quality evaluator for multi-turn agent interactions.

Scores conversations across five dimensions:
  1. Goal Achievement  - Did the agent accomplish what the user asked?
  2. Coherence         - Are responses logically connected and consistent?
  3. Efficiency        - Was the conversation concise without redundancy?
  4. Error Recovery    - Did the agent recover gracefully from mistakes?
  5. User Satisfaction - Does the user appear satisfied with the outcome?

Each dimension produces a 0.0-1.0 score with confidence, evidence, and
optional turn-level annotations.  An optional LLM blend (Anthropic Claude
only) refines borderline heuristic scores.

Usage:
    from app.enterprise.quality.conversation_evaluator import ConversationEvaluator
    from app.ingestion.conversation_trace import ConversationTrace

    evaluator = ConversationEvaluator()
    result = evaluator.evaluate(trace)
    print(result.overall_grade, result.overall_score)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ingestion.conversation_trace import ConversationTrace, ConversationTurnData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop-words excluded from keyword extraction (common English function words)
# ---------------------------------------------------------------------------
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "i", "you", "he",
    "she", "it", "we", "they", "me", "him", "her", "us", "them", "my",
    "your", "his", "its", "our", "their", "this", "that", "these", "those",
    "what", "which", "who", "whom", "how", "where", "when", "why",
    "and", "or", "but", "if", "then", "else", "so", "because", "as",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further",
    "not", "no", "nor", "just", "also", "very", "too", "here", "there",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "than", "up", "down", "any", "same", "own", "please",
    "need", "want", "like", "get", "make", "go", "know", "think", "see",
    "come", "take", "use", "find", "give", "tell", "help",
})

# ---------------------------------------------------------------------------
# Signal word lists
# ---------------------------------------------------------------------------
_COMPLETION_SIGNALS: list[str] = [
    "done", "complete", "completed", "here is", "here are", "here's",
    "finished", "i've completed", "i have completed", "all set",
    "ready for review", "as requested", "below is", "attached",
    "i've prepared", "i've generated", "task complete",
]

_USER_POSITIVE_SIGNALS: list[str] = [
    "thanks", "thank you", "great", "perfect", "exactly", "awesome",
    "helpful", "excellent", "wonderful", "nice", "good job", "well done",
    "looks good", "that's right", "correct", "yes", "appreciated",
    "amazing", "brilliant", "fantastic", "love it", "spot on",
]

_USER_NEGATIVE_SIGNALS: list[str] = [
    "no", "wrong", "not what i asked", "try again", "incorrect",
    "that's not right", "you misunderstood", "not helpful", "bad",
    "doesn't work", "doesn't make sense", "i said", "not what i meant",
    "redo", "start over", "you forgot", "missing", "error", "fail",
]

_ERROR_INDICATORS: list[str] = [
    "sorry", "mistake", "i apologize", "apologies", "error", "incorrect",
    "i was wrong", "my mistake", "let me correct", "correction",
    "i made an error", "that was wrong", "i misspoke",
]

_RETRY_PATTERNS: list[str] = [
    "let me try again", "sorry, let me", "let me redo", "i'll redo",
    "let me start over", "here is a corrected", "here's the corrected",
    "updated version", "revised version", "let me rephrase",
]

_CONTRADICTION_PATTERNS: list[str] = [
    "but actually", "i was wrong", "correction:", "no, ", "actually,",
    "on second thought", "i need to correct", "disregard",
    "that's not accurate", "i made a mistake",
]

# ---------------------------------------------------------------------------
# Dimension weights for overall score
# ---------------------------------------------------------------------------
_DIMENSION_WEIGHTS: Dict[str, float] = {
    "goal_achievement": 0.30,
    "coherence": 0.20,
    "efficiency": 0.20,
    "error_recovery": 0.15,
    "user_satisfaction": 0.15,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class EvalDimension(str, Enum):
    """Evaluation dimensions for conversation quality."""
    GOAL_ACHIEVEMENT = "goal_achievement"
    COHERENCE = "coherence"
    EFFICIENCY = "efficiency"
    ERROR_RECOVERY = "error_recovery"
    USER_SATISFACTION = "user_satisfaction"


@dataclass
class DimensionResult:
    """Result for a single evaluation dimension."""
    dimension: EvalDimension
    score: float               # 0.0 - 1.0
    confidence: float          # 0.0 - 1.0
    method: str                # "heuristic", "llm", "blended"
    details: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 2),
            "method": self.method,
            "details": self.details,
            "evidence": self.evidence,
        }


@dataclass
class TurnAnnotation:
    """Annotation for a notable moment in the conversation."""
    turn_number: int
    annotation: str
    score_impact: float        # positive = helps, negative = hurts
    dimension: EvalDimension

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_number": self.turn_number,
            "annotation": self.annotation,
            "score_impact": round(self.score_impact, 3),
            "dimension": self.dimension.value,
        }


@dataclass
class ConversationEvaluationResult:
    """Complete evaluation result for a conversation."""
    overall_score: float                          # 0.0 - 1.0
    overall_grade: str                            # A, B, C, D, F
    dimensions: Dict[EvalDimension, DimensionResult] = field(default_factory=dict)
    summary: str = ""
    turn_annotations: List[TurnAnnotation] = field(default_factory=list)
    scoring_method: str = "heuristic"             # "heuristic", "blended"
    cost_usd: float = 0.0
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 3),
            "overall_grade": self.overall_grade,
            "dimensions": {
                dim.value: dr.to_dict() for dim, dr in self.dimensions.items()
            },
            "summary": self.summary,
            "turn_annotations": [a.to_dict() for a in self.turn_annotations],
            "scoring_method": self.scoring_method,
            "cost_usd": round(self.cost_usd, 6),
            "tokens_used": self.tokens_used,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_to_grade(score: float) -> str:
    """Map a 0.0-1.0 score to a letter grade."""
    if score >= 0.9:
        return "A"
    if score >= 0.8:
        return "B"
    if score >= 0.7:
        return "C"
    if score >= 0.6:
        return "D"
    return "F"


def _tokenize(text: str) -> set[str]:
    """Lowercase word-tokenize, stripping punctuation."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _extract_keywords(text: str, max_keywords: int = 30) -> set[str]:
    """Extract meaningful keywords from text, filtering stop-words."""
    words = _tokenize(text)
    keywords = words - _STOP_WORDS
    # Also filter very short tokens (single char) and very long (likely hashes)
    keywords = {w for w in keywords if 2 <= len(w) <= 40}
    # If we have too many, keep the longest (more likely to be meaningful)
    if len(keywords) > max_keywords:
        keywords = set(sorted(keywords, key=len, reverse=True)[:max_keywords])
    return keywords


def _count_signal_matches(text: str, signals: list[str]) -> int:
    """Count how many signal phrases appear in text (case-insensitive)."""
    text_lower = text.lower()
    return sum(1 for s in signals if s in text_lower)


def _content_similarity(a: str, b: str) -> float:
    """Compute word-level Jaccard similarity between two texts."""
    return _jaccard(_tokenize(a), _tokenize(b))


# ---------------------------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------------------------

class ConversationEvaluator:
    """Evaluate multi-turn conversation quality across five dimensions.

    Parameters
    ----------
    use_llm_judge : bool, optional
        When True, borderline heuristic scores (0.35-0.65) are refined
        via Anthropic Claude.  Defaults to False.
    judge_model : str
        Anthropic model identifier for the LLM judge.
    escalation_range : tuple[float, float]
        Heuristic score range that triggers LLM escalation.
    dimension_weights : dict, optional
        Override default dimension weights for overall score computation.
    """

    def __init__(
        self,
        use_llm_judge: bool = False,
        judge_model: str = "claude-3-5-haiku-20241022",
        escalation_range: tuple[float, float] = (0.35, 0.65),
        dimension_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.use_llm_judge = use_llm_judge
        self.judge_model = judge_model
        self.escalation_range = escalation_range
        self.dimension_weights = dimension_weights or dict(_DIMENSION_WEIGHTS)

        self._llm_client = None
        self._total_cost: float = 0.0
        self._total_tokens: int = 0

        if use_llm_judge:
            self._init_llm_client()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, trace: ConversationTrace) -> ConversationEvaluationResult:
        """Evaluate a complete conversation trace.

        Parameters
        ----------
        trace : ConversationTrace
            The conversation to evaluate.

        Returns
        -------
        ConversationEvaluationResult
            Scores, grade, annotations, and evidence.
        """
        self._total_cost = 0.0
        self._total_tokens = 0
        annotations: List[TurnAnnotation] = []

        user_turns = trace.get_user_turns()
        agent_turns = trace.get_agent_turns()

        # Edge case: empty or trivial conversation
        if len(trace.turns) < 2:
            return self._trivial_result(trace, annotations)

        # Score each dimension
        goal_result = self._score_goal_achievement(trace, user_turns, agent_turns, annotations)
        coherence_result = self._score_coherence(trace, annotations)
        efficiency_result = self._score_efficiency(trace, agent_turns, annotations)
        recovery_result = self._score_error_recovery(trace, agent_turns, annotations)
        satisfaction_result = self._score_user_satisfaction(trace, user_turns, annotations)

        dimensions = {
            EvalDimension.GOAL_ACHIEVEMENT: goal_result,
            EvalDimension.COHERENCE: coherence_result,
            EvalDimension.EFFICIENCY: efficiency_result,
            EvalDimension.ERROR_RECOVERY: recovery_result,
            EvalDimension.USER_SATISFACTION: satisfaction_result,
        }

        # Optional LLM refinement for borderline scores
        scoring_method = "heuristic"
        if self.use_llm_judge and self._llm_client:
            any_blended = False
            for dim_enum, dim_result in dimensions.items():
                lo, hi = self.escalation_range
                if lo <= dim_result.score <= hi:
                    refined = self._llm_refine(trace, dim_enum, dim_result)
                    if refined is not None:
                        dim_result.score = refined
                        dim_result.method = "blended"
                        any_blended = True
            if any_blended:
                scoring_method = "blended"

        # Weighted overall score
        overall = 0.0
        weight_total = 0.0
        for dim_enum, dim_result in dimensions.items():
            w = self.dimension_weights.get(dim_enum.value, 0.2)
            overall += dim_result.score * w
            weight_total += w
        if weight_total > 0:
            overall /= weight_total

        overall = max(0.0, min(1.0, overall))
        grade = _score_to_grade(overall)

        # Summary
        summary = self._generate_summary(trace, dimensions, overall, grade)

        # Sort annotations by turn number
        annotations.sort(key=lambda a: a.turn_number)

        return ConversationEvaluationResult(
            overall_score=overall,
            overall_grade=grade,
            dimensions=dimensions,
            summary=summary,
            turn_annotations=annotations,
            scoring_method=scoring_method,
            cost_usd=self._total_cost,
            tokens_used=self._total_tokens,
        )

    # ------------------------------------------------------------------
    # Dimension 1: Goal Achievement
    # ------------------------------------------------------------------

    def _score_goal_achievement(
        self,
        trace: ConversationTrace,
        user_turns: List[ConversationTurnData],
        agent_turns: List[ConversationTurnData],
        annotations: List[TurnAnnotation],
    ) -> DimensionResult:
        """Score whether the agent accomplished the user's stated goal.

        Sub-signals (weights):
          - Keyword coverage in agent responses      (0.40)
          - Completion signals in agent turns         (0.30)
          - User acknowledgement of completion        (0.30)
        """
        details: Dict[str, Any] = {}
        evidence: List[str] = []

        # --- Extract task keywords from initial user turn ---
        initial_task = trace.get_initial_task()
        if not initial_task:
            # Fall back to first user turn content
            initial_task = user_turns[0].content if user_turns else ""

        task_keywords = _extract_keywords(initial_task)
        details["task_keywords_count"] = len(task_keywords)

        if not task_keywords:
            # Cannot evaluate goal achievement without a clear task
            evidence.append("No clear task keywords found in initial message")
            return DimensionResult(
                dimension=EvalDimension.GOAL_ACHIEVEMENT,
                score=0.5,
                confidence=0.3,
                method="heuristic",
                details=details,
                evidence=evidence,
            )

        # --- Keyword coverage in agent responses ---
        # Weight later agent turns more heavily (they likely contain the answer)
        covered_keywords: set[str] = set()
        for turn in agent_turns:
            turn_words = _tokenize(turn.content)
            covered_keywords |= (task_keywords & turn_words)

        coverage_ratio = len(covered_keywords) / len(task_keywords) if task_keywords else 0.0
        # Apply a gentle curve: partial coverage is ok, we don't need 100%
        # Many task keywords are contextual, not required in output
        keyword_score = min(1.0, coverage_ratio * 1.5)
        details["keyword_coverage"] = round(coverage_ratio, 3)
        details["covered_keywords"] = len(covered_keywords)
        details["total_task_keywords"] = len(task_keywords)

        if coverage_ratio < 0.2:
            evidence.append(f"Low keyword coverage ({coverage_ratio:.0%}) — agent may not have addressed the task")

        # --- Completion signals in agent turns ---
        completion_count = 0
        for turn in agent_turns:
            matches = _count_signal_matches(turn.content, _COMPLETION_SIGNALS)
            if matches > 0:
                completion_count += matches
                if turn.turn_number == trace.turns[-1].turn_number or \
                   turn.turn_number >= len(trace.turns) - 2:
                    annotations.append(TurnAnnotation(
                        turn_number=turn.turn_number,
                        annotation="Agent signals task completion",
                        score_impact=0.1,
                        dimension=EvalDimension.GOAL_ACHIEVEMENT,
                    ))

        completion_score = min(1.0, completion_count / 2.0)  # 2+ signals = full
        details["completion_signals"] = completion_count

        if completion_count == 0:
            evidence.append("No completion signals detected in agent responses")

        # --- User acknowledgement ---
        ack_score = 0.0
        if user_turns:
            # Check last 2 user turns for positive acknowledgement
            check_turns = user_turns[-2:] if len(user_turns) >= 2 else user_turns
            positive_ack = 0
            for turn in check_turns:
                positive_ack += _count_signal_matches(turn.content, _USER_POSITIVE_SIGNALS)
            ack_score = min(1.0, positive_ack / 2.0)
            details["user_acknowledgement_signals"] = positive_ack

            if positive_ack > 0:
                evidence.append(f"User acknowledged completion ({positive_ack} positive signals)")
            else:
                # Check if last user turn is a follow-up question (indicates incomplete)
                last_user = user_turns[-1].content.strip()
                if last_user.endswith("?"):
                    ack_score = 0.2
                    evidence.append("Conversation ends with user question — goal may be incomplete")
                    annotations.append(TurnAnnotation(
                        turn_number=user_turns[-1].turn_number,
                        annotation="Conversation ends with user question",
                        score_impact=-0.1,
                        dimension=EvalDimension.GOAL_ACHIEVEMENT,
                    ))

        # --- Combine sub-scores ---
        score = (keyword_score * 0.40) + (completion_score * 0.30) + (ack_score * 0.30)
        score = max(0.0, min(1.0, score))

        # Confidence is higher when we have clear signals
        signal_strength = (
            (1.0 if len(task_keywords) >= 5 else 0.5) +
            (1.0 if completion_count > 0 else 0.3) +
            (1.0 if ack_score > 0.5 else 0.3)
        ) / 3.0
        confidence = min(0.9, 0.4 + signal_strength * 0.5)

        return DimensionResult(
            dimension=EvalDimension.GOAL_ACHIEVEMENT,
            score=score,
            confidence=round(confidence, 2),
            method="heuristic",
            details=details,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Dimension 2: Coherence
    # ------------------------------------------------------------------

    def _score_coherence(
        self,
        trace: ConversationTrace,
        annotations: List[TurnAnnotation],
    ) -> DimensionResult:
        """Score logical coherence across consecutive turns.

        Sub-signals:
          - Average word overlap (Jaccard) between consecutive turns  (0.40)
          - Absence of contradiction patterns                         (0.30)
          - Vocabulary consistency across the conversation            (0.30)
        """
        details: Dict[str, Any] = {}
        evidence: List[str] = []

        if len(trace.turns) < 2:
            return DimensionResult(
                dimension=EvalDimension.COHERENCE,
                score=0.8,
                confidence=0.3,
                method="heuristic",
                details={"reason": "Too few turns to evaluate coherence"},
                evidence=["Single-turn conversation; coherence is trivially high"],
            )

        # --- Consecutive-turn word overlap ---
        overlaps: List[float] = []
        for prev_turn, curr_turn in trace.iter_turn_pairs():
            prev_words = _tokenize(prev_turn.content)
            curr_words = _tokenize(curr_turn.content)
            overlap = _jaccard(prev_words, curr_words)
            overlaps.append(overlap)

        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0
        # Jaccard on real conversations is typically 0.05-0.30
        # Normalize: 0.05 -> 0.5, 0.20 -> 1.0
        overlap_score = min(1.0, max(0.0, (avg_overlap - 0.02) / 0.18))
        details["avg_turn_overlap"] = round(avg_overlap, 4)
        details["turn_pair_count"] = len(overlaps)

        # --- Contradiction detection ---
        contradiction_count = 0
        for turn in trace.turns:
            if turn.role == "agent":
                matches = _count_signal_matches(turn.content, _CONTRADICTION_PATTERNS)
                if matches > 0:
                    contradiction_count += matches
                    annotations.append(TurnAnnotation(
                        turn_number=turn.turn_number,
                        annotation=f"Potential contradiction or self-correction detected",
                        score_impact=-0.05 * matches,
                        dimension=EvalDimension.COHERENCE,
                    ))

        # 0 contradictions = 1.0, 1 = 0.7, 2 = 0.4, 3+ = 0.1
        contradiction_penalty = max(0.1, 1.0 - contradiction_count * 0.3)
        details["contradiction_count"] = contradiction_count

        if contradiction_count > 0:
            evidence.append(f"{contradiction_count} contradiction/self-correction pattern(s) detected")

        # --- Vocabulary consistency ---
        # Compare vocabulary of first half vs second half of agent turns
        agent_turns = trace.get_agent_turns()
        if len(agent_turns) >= 2:
            mid = len(agent_turns) // 2
            first_half_vocab: set[str] = set()
            second_half_vocab: set[str] = set()
            for t in agent_turns[:mid]:
                first_half_vocab |= _tokenize(t.content)
            for t in agent_turns[mid:]:
                second_half_vocab |= _tokenize(t.content)

            vocab_consistency = _jaccard(first_half_vocab, second_half_vocab)
            # Normalize: real conversations have ~0.15-0.40 Jaccard on vocab halves
            vocab_score = min(1.0, max(0.0, (vocab_consistency - 0.05) / 0.35))
            details["vocab_consistency"] = round(vocab_consistency, 4)
        else:
            vocab_score = 0.8  # Single agent turn — assume consistent
            details["vocab_consistency"] = None

        # --- Combine ---
        score = (overlap_score * 0.40) + (contradiction_penalty * 0.30) + (vocab_score * 0.30)
        score = max(0.0, min(1.0, score))

        confidence = 0.6 if len(trace.turns) >= 4 else 0.4

        return DimensionResult(
            dimension=EvalDimension.COHERENCE,
            score=score,
            confidence=confidence,
            method="heuristic",
            details=details,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Dimension 3: Efficiency
    # ------------------------------------------------------------------

    def _score_efficiency(
        self,
        trace: ConversationTrace,
        agent_turns: List[ConversationTurnData],
        annotations: List[TurnAnnotation],
    ) -> DimensionResult:
        """Score conversation efficiency.

        Sub-signals:
          - Turn count appropriateness      (0.35)
          - Redundancy / repeated content    (0.35)
          - Retry pattern detection          (0.30)
        """
        details: Dict[str, Any] = {}
        evidence: List[str] = []

        total_turns = trace.total_turns

        # --- Turn count appropriateness ---
        # Simple tasks: <=5 turns is efficient
        # Medium tasks: 5-10 is normal
        # Long: 10-15 is getting verbose
        # Excessive: >15 is likely inefficient
        if total_turns <= 4:
            turn_score = 1.0
        elif total_turns <= 8:
            turn_score = 0.9
        elif total_turns <= 12:
            turn_score = 0.7
        elif total_turns <= 15:
            turn_score = 0.5
        elif total_turns <= 20:
            turn_score = 0.3
        else:
            turn_score = max(0.1, 0.3 - (total_turns - 20) * 0.02)

        details["total_turns"] = total_turns
        details["turn_score"] = round(turn_score, 3)

        if total_turns > 15:
            evidence.append(f"Conversation has {total_turns} turns — may be excessively long")
            annotations.append(TurnAnnotation(
                turn_number=total_turns,
                annotation=f"Conversation length ({total_turns} turns) exceeds expected range",
                score_impact=-0.1,
                dimension=EvalDimension.EFFICIENCY,
            ))

        # --- Redundancy detection ---
        # Compare each agent turn to all subsequent agent turns
        redundant_pairs = 0
        total_pairs = 0
        for i in range(len(agent_turns)):
            for j in range(i + 1, len(agent_turns)):
                total_pairs += 1
                sim = _content_similarity(agent_turns[i].content, agent_turns[j].content)
                if sim > 0.6:  # High similarity = redundant
                    redundant_pairs += 1
                    if sim > 0.8:
                        annotations.append(TurnAnnotation(
                            turn_number=agent_turns[j].turn_number,
                            annotation=f"Near-duplicate content with turn {agent_turns[i].turn_number} (similarity={sim:.2f})",
                            score_impact=-0.1,
                            dimension=EvalDimension.EFFICIENCY,
                        ))

        redundancy_ratio = redundant_pairs / total_pairs if total_pairs > 0 else 0.0
        redundancy_score = max(0.0, 1.0 - redundancy_ratio * 2.0)
        details["redundant_turn_pairs"] = redundant_pairs
        details["total_agent_turn_pairs"] = total_pairs
        details["redundancy_ratio"] = round(redundancy_ratio, 3)

        if redundant_pairs > 0:
            evidence.append(f"{redundant_pairs} redundant agent turn pair(s) detected")

        # --- Retry pattern detection ---
        retry_count = 0
        for turn in agent_turns:
            matches = _count_signal_matches(turn.content, _RETRY_PATTERNS)
            if matches > 0:
                retry_count += matches
                annotations.append(TurnAnnotation(
                    turn_number=turn.turn_number,
                    annotation="Retry/redo pattern detected",
                    score_impact=-0.05,
                    dimension=EvalDimension.EFFICIENCY,
                ))

        # 0 retries = 1.0, 1 = 0.7, 2 = 0.4, 3+ = 0.2
        retry_score = max(0.2, 1.0 - retry_count * 0.3)
        details["retry_count"] = retry_count

        if retry_count > 0:
            evidence.append(f"{retry_count} retry/redo pattern(s) detected")

        # --- Combine ---
        score = (turn_score * 0.35) + (redundancy_score * 0.35) + (retry_score * 0.30)
        score = max(0.0, min(1.0, score))

        confidence = 0.7 if total_turns >= 4 else 0.5

        return DimensionResult(
            dimension=EvalDimension.EFFICIENCY,
            score=score,
            confidence=confidence,
            method="heuristic",
            details=details,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Dimension 4: Error Recovery
    # ------------------------------------------------------------------

    def _score_error_recovery(
        self,
        trace: ConversationTrace,
        agent_turns: List[ConversationTurnData],
        annotations: List[TurnAnnotation],
    ) -> DimensionResult:
        """Score how well the agent recovers from errors.

        Logic:
          - If no errors detected -> score 0.9 (good baseline, not perfect
            since we may have missed subtle errors)
          - If errors detected -> evaluate whether subsequent turns show
            improvement (different content, progression, resolution)
        """
        details: Dict[str, Any] = {}
        evidence: List[str] = []

        # --- Detect errors in agent turns ---
        error_turns: List[int] = []  # indices into agent_turns
        for idx, turn in enumerate(agent_turns):
            matches = _count_signal_matches(turn.content, _ERROR_INDICATORS)
            if matches > 0:
                error_turns.append(idx)
                annotations.append(TurnAnnotation(
                    turn_number=turn.turn_number,
                    annotation=f"Error/apology detected ({matches} indicator(s))",
                    score_impact=-0.05,
                    dimension=EvalDimension.ERROR_RECOVERY,
                ))

        details["error_turn_count"] = len(error_turns)
        details["total_agent_turns"] = len(agent_turns)

        if not error_turns:
            # No errors: assume smooth conversation
            evidence.append("No error indicators found in agent responses")
            return DimensionResult(
                dimension=EvalDimension.ERROR_RECOVERY,
                score=0.9,
                confidence=0.6,
                method="heuristic",
                details=details,
                evidence=evidence,
            )

        evidence.append(f"{len(error_turns)} agent turn(s) contain error indicators")

        # --- Evaluate recovery quality for each error ---
        recovery_scores: List[float] = []
        for err_idx in error_turns:
            if err_idx + 1 < len(agent_turns):
                error_turn = agent_turns[err_idx]
                next_turn = agent_turns[err_idx + 1]

                # Check if next turn is substantially different (progression)
                sim = _content_similarity(error_turn.content, next_turn.content)
                content_diverged = sim < 0.5

                # Check if next turn is longer (more effort to fix)
                length_ratio = len(next_turn.content) / max(len(error_turn.content), 1)
                more_effort = length_ratio > 0.8

                # Check if next turn has completion signals (resolved)
                has_completion = _count_signal_matches(next_turn.content, _COMPLETION_SIGNALS) > 0

                # Score this recovery
                recovery = 0.0
                if content_diverged:
                    recovery += 0.4
                if more_effort:
                    recovery += 0.3
                if has_completion:
                    recovery += 0.3

                recovery_scores.append(recovery)

                details[f"recovery_turn_{error_turn.turn_number}"] = {
                    "content_diverged": content_diverged,
                    "similarity_to_next": round(sim, 3),
                    "more_effort": more_effort,
                    "resolved": has_completion,
                    "recovery_score": round(recovery, 3),
                }

                if recovery >= 0.7:
                    annotations.append(TurnAnnotation(
                        turn_number=next_turn.turn_number,
                        annotation="Good recovery from previous error",
                        score_impact=0.1,
                        dimension=EvalDimension.ERROR_RECOVERY,
                    ))
                    evidence.append(f"Turn {next_turn.turn_number}: strong recovery after error")
            else:
                # Error in last agent turn with no follow-up — poor recovery
                recovery_scores.append(0.2)
                evidence.append(f"Error in last agent turn ({agent_turns[err_idx].turn_number}) with no recovery")

        # --- Combine: base penalty for errors + recovery quality ---
        avg_recovery = sum(recovery_scores) / len(recovery_scores) if recovery_scores else 0.0
        # Base: 0.4 for having errors at all, up to 0.6 bonus for good recovery
        score = 0.4 + avg_recovery * 0.5
        # Additional penalty if many errors relative to total turns
        error_ratio = len(error_turns) / max(len(agent_turns), 1)
        if error_ratio > 0.3:
            penalty = (error_ratio - 0.3) * 0.5
            score = max(0.1, score - penalty)
            evidence.append(f"High error rate ({error_ratio:.0%} of agent turns)")

        score = max(0.0, min(1.0, score))
        details["avg_recovery_quality"] = round(avg_recovery, 3)
        details["error_ratio"] = round(error_ratio, 3)

        confidence = 0.7 if len(error_turns) >= 2 else 0.5

        return DimensionResult(
            dimension=EvalDimension.ERROR_RECOVERY,
            score=score,
            confidence=confidence,
            method="heuristic",
            details=details,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Dimension 5: User Satisfaction
    # ------------------------------------------------------------------

    def _score_user_satisfaction(
        self,
        trace: ConversationTrace,
        user_turns: List[ConversationTurnData],
        annotations: List[TurnAnnotation],
    ) -> DimensionResult:
        """Score inferred user satisfaction from conversation signals.

        Sub-signals:
          - Positive/negative signal balance
          - Response length trend (shorter user turns = satisfied)
          - Final turn sentiment (2x weight)
        """
        details: Dict[str, Any] = {}
        evidence: List[str] = []

        if not user_turns:
            return DimensionResult(
                dimension=EvalDimension.USER_SATISFACTION,
                score=0.5,
                confidence=0.2,
                method="heuristic",
                details={"reason": "No user turns found"},
                evidence=["Cannot evaluate satisfaction without user messages"],
            )

        # --- Positive / negative signal counting ---
        total_positive = 0
        total_negative = 0
        per_turn_sentiment: List[Dict[str, Any]] = []

        for turn in user_turns:
            pos = _count_signal_matches(turn.content, _USER_POSITIVE_SIGNALS)
            neg = _count_signal_matches(turn.content, _USER_NEGATIVE_SIGNALS)
            total_positive += pos
            total_negative += neg
            per_turn_sentiment.append({
                "turn": turn.turn_number,
                "positive": pos,
                "negative": neg,
            })

        details["total_positive_signals"] = total_positive
        details["total_negative_signals"] = total_negative

        # --- Final turn sentiment (2x weight) ---
        final_turn = user_turns[-1]
        final_pos = _count_signal_matches(final_turn.content, _USER_POSITIVE_SIGNALS)
        final_neg = _count_signal_matches(final_turn.content, _USER_NEGATIVE_SIGNALS)
        # Double the final turn signals
        total_positive += final_pos  # already counted once, this adds 1x more
        total_negative += final_neg
        details["final_turn_positive"] = final_pos
        details["final_turn_negative"] = final_neg

        if final_pos > 0:
            annotations.append(TurnAnnotation(
                turn_number=final_turn.turn_number,
                annotation="Positive sentiment in final user turn",
                score_impact=0.1,
                dimension=EvalDimension.USER_SATISFACTION,
            ))
            evidence.append("User expresses positive sentiment at end of conversation")

        if final_neg > 0:
            annotations.append(TurnAnnotation(
                turn_number=final_turn.turn_number,
                annotation="Negative sentiment in final user turn",
                score_impact=-0.15,
                dimension=EvalDimension.USER_SATISFACTION,
            ))
            evidence.append("User expresses dissatisfaction at end of conversation")

        # --- Response length trend ---
        # If user messages get shorter over time, it can indicate either:
        #   - satisfaction (short acknowledgements) or
        #   - frustration (giving up)
        # We disambiguate using sentiment signals
        length_trend_score = 0.5  # neutral default
        if len(user_turns) >= 3:
            lengths = [len(t.content) for t in user_turns]
            first_half_avg = sum(lengths[:len(lengths) // 2]) / max(len(lengths) // 2, 1)
            second_half_avg = sum(lengths[len(lengths) // 2:]) / max(len(lengths) - len(lengths) // 2, 1)

            if second_half_avg < first_half_avg * 0.5:
                # Messages getting much shorter
                if total_positive > total_negative:
                    length_trend_score = 0.8  # short + positive = satisfied
                    evidence.append("User messages getting shorter with positive signals — indicates satisfaction")
                else:
                    length_trend_score = 0.3  # short + negative = frustrated
                    evidence.append("User messages getting shorter with negative signals — possible frustration")
            elif second_half_avg > first_half_avg * 1.5:
                # Messages getting longer — may indicate repeated explanations
                length_trend_score = 0.4
                evidence.append("User messages getting longer — may indicate need for repeated clarification")
            else:
                length_trend_score = 0.6  # stable length

            details["first_half_avg_length"] = round(first_half_avg, 1)
            details["second_half_avg_length"] = round(second_half_avg, 1)

        details["length_trend_score"] = round(length_trend_score, 3)

        # --- Compute sentiment score ---
        # Formula: (positive - negative + baseline) / normalizer, clamped 0-1
        baseline = 2.0  # gentle positive bias (assume neutral if no signals)
        normalizer = max(total_positive + total_negative + baseline, 4.0)
        sentiment_score = (total_positive - total_negative + baseline) / normalizer
        sentiment_score = max(0.0, min(1.0, sentiment_score))
        details["raw_sentiment_score"] = round(sentiment_score, 3)

        # --- Combine: 60% sentiment, 40% length trend ---
        score = sentiment_score * 0.60 + length_trend_score * 0.40
        score = max(0.0, min(1.0, score))

        # Confidence depends on signal volume
        signal_volume = total_positive + total_negative
        if signal_volume >= 4:
            confidence = 0.8
        elif signal_volume >= 2:
            confidence = 0.6
        else:
            confidence = 0.4

        return DimensionResult(
            dimension=EvalDimension.USER_SATISFACTION,
            score=score,
            confidence=confidence,
            method="heuristic",
            details=details,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # LLM refinement (Anthropic Claude only)
    # ------------------------------------------------------------------

    def _init_llm_client(self) -> None:
        """Lazily initialize the Anthropic client if a key is available."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "ConversationEvaluator: use_llm_judge=True but ANTHROPIC_API_KEY not set. "
                "Falling back to heuristic-only scoring."
            )
            self.use_llm_judge = False
            return
        try:
            import anthropic
            self._llm_client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            logger.warning(
                "ConversationEvaluator: anthropic package not installed. "
                "Falling back to heuristic-only scoring."
            )
            self.use_llm_judge = False

    def _llm_refine(
        self,
        trace: ConversationTrace,
        dimension: EvalDimension,
        current_result: DimensionResult,
    ) -> Optional[float]:
        """Call Anthropic Claude to refine a borderline heuristic score.

        Returns the blended score (0.3 * heuristic + 0.7 * LLM) or None on failure.
        """
        if self._llm_client is None:
            return None

        # Build conversation excerpt (truncate long conversations)
        excerpt_lines: List[str] = []
        for turn in trace.turns[:20]:  # Max 20 turns
            role_label = turn.role.upper()
            content_preview = turn.content[:500]
            excerpt_lines.append(f"[{role_label} - Turn {turn.turn_number}]: {content_preview}")
        excerpt = "\n".join(excerpt_lines)

        prompt = (
            f"You are evaluating the '{dimension.value}' quality of a multi-turn conversation.\n\n"
            f"## Conversation Excerpt\n{excerpt}\n\n"
            f"## Heuristic Analysis\n"
            f"Current heuristic score: {current_result.score:.3f}\n"
            f"Evidence: {'; '.join(current_result.evidence) if current_result.evidence else 'None'}\n\n"
            f"## Task\n"
            f"Score this conversation's {dimension.value.replace('_', ' ')} from 0.0 to 1.0.\n"
            f"Respond with ONLY a JSON object: {{\"score\": <float>, \"reasoning\": \"<brief explanation>\"}}"
        )

        try:
            import anthropic
            response = self._llm_client.messages.create(
                model=self.judge_model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )

            # Track cost and tokens
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            self._total_tokens += total_tokens

            # Approximate cost for Haiku
            cost = (input_tokens * 0.25 + output_tokens * 1.25) / 1_000_000
            self._total_cost += cost

            # Parse response
            response_text = response.content[0].text.strip()
            import json
            parsed = json.loads(response_text)
            llm_score = float(parsed["score"])
            llm_score = max(0.0, min(1.0, llm_score))

            # Blend: 30% heuristic + 70% LLM
            blended = 0.3 * current_result.score + 0.7 * llm_score

            # Record evidence
            current_result.details["llm_score"] = round(llm_score, 3)
            current_result.details["heuristic_score"] = round(current_result.score, 3)
            current_result.details["llm_reasoning"] = parsed.get("reasoning", "")
            current_result.details["llm_tokens"] = total_tokens
            current_result.confidence = min(0.9, current_result.confidence + 0.2)

            return max(0.0, min(1.0, blended))

        except Exception as e:
            logger.debug("LLM refinement failed for %s: %s", dimension.value, e)
            current_result.details["llm_error"] = str(e)
            return None

    # ------------------------------------------------------------------
    # Summary and helpers
    # ------------------------------------------------------------------

    def _generate_summary(
        self,
        trace: ConversationTrace,
        dimensions: Dict[EvalDimension, DimensionResult],
        overall: float,
        grade: str,
    ) -> str:
        """Generate a human-readable evaluation summary."""
        parts: List[str] = []

        parts.append(
            f"Conversation ({trace.total_turns} turns, "
            f"{len(trace.participants)} participants): "
            f"{grade} ({overall:.0%})"
        )

        # Report each dimension
        for dim_enum in EvalDimension:
            dr = dimensions.get(dim_enum)
            if dr:
                dim_label = dim_enum.value.replace("_", " ").title()
                parts.append(f"{dim_label}: {dr.score:.0%}")

        # Highlight strengths and weaknesses
        sorted_dims = sorted(dimensions.items(), key=lambda x: x[1].score)
        if sorted_dims:
            weakest = sorted_dims[0]
            strongest = sorted_dims[-1]
            if weakest[1].score < 0.6:
                parts.append(
                    f"Needs improvement: {weakest[0].value.replace('_', ' ')}"
                )
            if strongest[1].score >= 0.8:
                parts.append(
                    f"Strength: {strongest[0].value.replace('_', ' ')}"
                )

        return ". ".join(parts) + "."

    def _trivial_result(
        self,
        trace: ConversationTrace,
        annotations: List[TurnAnnotation],
    ) -> ConversationEvaluationResult:
        """Return a minimal result for very short conversations."""
        dims = {}
        for dim_enum in EvalDimension:
            dims[dim_enum] = DimensionResult(
                dimension=dim_enum,
                score=0.5,
                confidence=0.2,
                method="heuristic",
                details={"reason": "Conversation too short for meaningful evaluation"},
                evidence=["Fewer than 2 turns — cannot evaluate"],
            )

        return ConversationEvaluationResult(
            overall_score=0.5,
            overall_grade="F",
            dimensions=dims,
            summary=f"Conversation has only {trace.total_turns} turn(s) — insufficient for evaluation.",
            turn_annotations=annotations,
            scoring_method="heuristic",
            cost_usd=0.0,
            tokens_used=0,
        )
