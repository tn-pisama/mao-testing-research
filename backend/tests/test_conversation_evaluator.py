"""Tests for ConversationEvaluator.

Uses the real ConversationTrace and ConversationTurnData from
app.ingestion.conversation_trace to ensure realistic test coverage.
"""
import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterator

from app.enterprise.quality.conversation_evaluator import (
    ConversationEvaluator,
    EvalDimension,
    DimensionResult,
    TurnAnnotation,
    ConversationEvaluationResult,
    _score_to_grade,
    _tokenize,
    _jaccard,
    _extract_keywords,
    _count_signal_matches,
    _content_similarity,
    _COMPLETION_SIGNALS,
    _USER_POSITIVE_SIGNALS,
    _USER_NEGATIVE_SIGNALS,
    _ERROR_INDICATORS,
    _RETRY_PATTERNS,
    _CONTRADICTION_PATTERNS,
)
from app.ingestion.conversation_trace import ConversationTrace, ConversationTurnData


# ---------------------------------------------------------------------------
# Helpers for building test traces
# ---------------------------------------------------------------------------

def _make_turn(
    turn_number: int,
    role: str,
    content: str,
    participant_id: str = "",
) -> ConversationTurnData:
    """Create a ConversationTurnData with sensible defaults."""
    if not participant_id:
        participant_id = "user1" if role == "user" else "agent1"
    return ConversationTurnData(
        turn_id=f"turn-{turn_number}",
        turn_number=turn_number,
        role=role,
        participant_id=participant_id,
        content=content,
    )


def _make_trace(turns_data: List[tuple]) -> ConversationTrace:
    """Build a ConversationTrace from (role, content) tuples."""
    trace = ConversationTrace(
        trace_id="test-trace",
        conversation_id="test-conv",
        framework="test",
    )
    for idx, (role, content) in enumerate(turns_data, start=1):
        turn = _make_turn(idx, role, content)
        trace.add_turn(turn)
    return trace


# ===========================================================================
# Unit tests for helper functions
# ===========================================================================


class TestScoreToGrade:
    def test_grade_a(self):
        assert _score_to_grade(0.95) == "A"
        assert _score_to_grade(0.90) == "A"

    def test_grade_b(self):
        assert _score_to_grade(0.85) == "B"
        assert _score_to_grade(0.80) == "B"

    def test_grade_c(self):
        assert _score_to_grade(0.75) == "C"
        assert _score_to_grade(0.70) == "C"

    def test_grade_d(self):
        assert _score_to_grade(0.65) == "D"
        assert _score_to_grade(0.60) == "D"

    def test_grade_f(self):
        assert _score_to_grade(0.59) == "F"
        assert _score_to_grade(0.4) == "F"
        assert _score_to_grade(0.0) == "F"

    def test_grade_boundaries_exact(self):
        assert _score_to_grade(0.9) == "A"
        assert _score_to_grade(0.8) == "B"
        assert _score_to_grade(0.7) == "C"
        assert _score_to_grade(0.6) == "D"

    def test_perfect_score(self):
        assert _score_to_grade(1.0) == "A"


class TestTokenize:
    def test_basic(self):
        result = _tokenize("Hello World")
        assert "hello" in result
        assert "world" in result

    def test_strips_punctuation(self):
        result = _tokenize("foo! bar? baz.")
        assert result == {"foo", "bar", "baz"}

    def test_empty_string(self):
        assert _tokenize("") == set()


class TestJaccard:
    def test_identical_sets(self):
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        result = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(result - 0.5) < 0.001

    def test_both_empty(self):
        assert _jaccard(set(), set()) == 1.0


class TestExtractKeywords:
    def test_filters_stop_words(self):
        keywords = _extract_keywords("the quick brown fox jumps over the lazy dog")
        assert "the" not in keywords
        assert "over" not in keywords
        assert "quick" in keywords
        assert "brown" in keywords

    def test_filters_short_tokens(self):
        keywords = _extract_keywords("I a am ok")
        # single char tokens filtered
        assert "i" not in keywords
        assert "a" not in keywords

    def test_empty_input(self):
        assert _extract_keywords("") == set()


class TestCountSignalMatches:
    def test_counts_positive_signals(self):
        count = _count_signal_matches("Thanks, that's perfect!", _USER_POSITIVE_SIGNALS)
        assert count >= 2  # "thanks" and "perfect"

    def test_counts_negative_signals(self):
        count = _count_signal_matches("No, that's wrong, try again", _USER_NEGATIVE_SIGNALS)
        assert count >= 2  # "no" and "try again"

    def test_no_signals(self):
        count = _count_signal_matches("The fibonacci sequence is interesting", _USER_POSITIVE_SIGNALS)
        assert count == 0


class TestContentSimilarity:
    def test_identical_text(self):
        sim = _content_similarity("hello world", "hello world")
        assert sim == 1.0

    def test_completely_different(self):
        sim = _content_similarity("alpha beta gamma", "delta epsilon zeta")
        assert sim == 0.0

    def test_partial_overlap(self):
        sim = _content_similarity("the cat sat on the mat", "the dog sat on the rug")
        assert 0.0 < sim < 1.0


# ===========================================================================
# Tests for ConversationEvaluator
# ===========================================================================


class TestGoalAchievement:
    def test_high_score_when_task_completed(self):
        trace = _make_trace([
            ("user", "Write a factorial function in Python"),
            ("agent", "Here is the factorial function: def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"),
            ("user", "Thanks, that looks correct!"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        goal_dim = result.dimensions[EvalDimension.GOAL_ACHIEVEMENT]
        assert goal_dim.score >= 0.5  # keyword coverage + completion + user ack

    def test_low_score_when_task_unanswered(self):
        trace = _make_trace([
            ("user", "Implement a binary search tree with insert delete and search operations"),
            ("agent", "I think the weather today is quite nice."),
            ("user", "That's not what I asked for"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        goal_dim = result.dimensions[EvalDimension.GOAL_ACHIEVEMENT]
        # Agent completely ignored the task, negative user feedback
        assert goal_dim.score < 0.6


class TestCoherence:
    def test_coherent_conversation(self):
        trace = _make_trace([
            ("user", "What is the capital of France?"),
            ("agent", "The capital of France is Paris. It is the largest city in France."),
            ("user", "What is the population of Paris?"),
            ("agent", "The population of Paris is approximately 2.1 million in the city proper."),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        coherence_dim = result.dimensions[EvalDimension.COHERENCE]
        assert coherence_dim.score >= 0.3  # Related topic, shared vocabulary

    def test_contradiction_lowers_score(self):
        trace = _make_trace([
            ("user", "What is 2+2?"),
            ("agent", "2+2 is 5."),
            ("user", "Are you sure?"),
            ("agent", "Actually, I was wrong. Correction: 2+2 is 4."),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        coherence_dim = result.dimensions[EvalDimension.COHERENCE]
        # Contradiction patterns detected should lower score
        assert coherence_dim.details.get("contradiction_count", 0) >= 1


class TestEfficiency:
    def test_short_conversation_scores_high(self):
        trace = _make_trace([
            ("user", "What is 2+2?"),
            ("agent", "2+2 equals 4."),
            ("user", "Thanks!"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        eff_dim = result.dimensions[EvalDimension.EFFICIENCY]
        assert eff_dim.score >= 0.8

    def test_long_conversation_scores_lower(self):
        turns = []
        for i in range(12):
            turns.append(("user", f"Question {i}: What about topic {i}?"))
            turns.append(("agent", f"Answer {i}: Here is information about topic {i}."))
        trace = _make_trace(turns)

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        eff_dim = result.dimensions[EvalDimension.EFFICIENCY]
        assert eff_dim.score < 0.9  # Long conversation penalized

    def test_redundant_content_penalized(self):
        trace = _make_trace([
            ("user", "Tell me about Python"),
            ("agent", "Python is a programming language used for web development and data science"),
            ("user", "Tell me more"),
            ("agent", "Python is a programming language used for web development and data science"),
            ("user", "Anything else?"),
            ("agent", "Python is a programming language used for web development and data science"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        eff_dim = result.dimensions[EvalDimension.EFFICIENCY]
        assert eff_dim.details.get("redundant_turn_pairs", 0) >= 1


class TestErrorRecovery:
    def test_no_errors_scores_high(self):
        trace = _make_trace([
            ("user", "Hello"),
            ("agent", "Hi, how can I help?"),
            ("user", "Write a poem"),
            ("agent", "Here is a short poem about spring..."),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        recovery_dim = result.dimensions[EvalDimension.ERROR_RECOVERY]
        assert recovery_dim.score >= 0.8

    def test_error_with_recovery_scores_moderate(self):
        trace = _make_trace([
            ("user", "Write code for a REST API"),
            ("agent", "Sorry, I made a mistake in my initial attempt. Let me correct that and provide a proper implementation with Flask:"),
            ("user", "Ok, continue"),
            ("agent", "Here is the complete REST API: from flask import Flask, jsonify\napp = Flask(__name__)\n..."),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        recovery_dim = result.dimensions[EvalDimension.ERROR_RECOVERY]
        # Errors detected but recovery happened
        assert recovery_dim.details.get("error_turn_count", 0) >= 1


class TestUserSatisfaction:
    def test_positive_signals_score_high(self):
        trace = _make_trace([
            ("user", "Help me write a function"),
            ("agent", "Here is the function you requested"),
            ("user", "Perfect, exactly what I needed! Great job, thanks!"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        sat_dim = result.dimensions[EvalDimension.USER_SATISFACTION]
        assert sat_dim.score >= 0.5

    def test_negative_signals_score_low(self):
        trace = _make_trace([
            ("user", "Write a sorting algorithm"),
            ("agent", "The weather today is sunny."),
            ("user", "No, wrong, that's not what I asked. Not helpful at all."),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        sat_dim = result.dimensions[EvalDimension.USER_SATISFACTION]
        assert sat_dim.details.get("total_negative_signals", 0) >= 1


class TestOverallEvaluation:
    def test_produces_valid_result(self):
        trace = _make_trace([
            ("user", "Hello there"),
            ("agent", "Hi! How can I help you today?"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        assert 0 <= result.overall_score <= 1
        assert result.overall_grade in ("A", "B", "C", "D", "F")
        assert len(result.dimensions) == 5
        assert result.scoring_method == "heuristic"
        assert result.cost_usd == 0.0
        assert result.tokens_used == 0

    def test_all_dimensions_present(self):
        trace = _make_trace([
            ("user", "Help me"),
            ("agent", "Sure, what do you need?"),
            ("user", "Write a function"),
            ("agent", "Here is a function: def foo(): pass"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        for dim in EvalDimension:
            assert dim in result.dimensions, f"Missing dimension: {dim}"
            dr = result.dimensions[dim]
            assert 0.0 <= dr.score <= 1.0
            assert 0.0 <= dr.confidence <= 1.0
            assert dr.method in ("heuristic", "llm", "blended")

    def test_to_dict_serializable(self):
        trace = _make_trace([
            ("user", "Hello"),
            ("agent", "Hi"),
            ("user", "Thanks"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        d = result.to_dict()
        assert "overall_score" in d
        assert "overall_grade" in d
        assert "dimensions" in d
        assert "summary" in d
        assert len(d["dimensions"]) == 5


class TestEdgeCases:
    def test_empty_conversation(self):
        trace = ConversationTrace(
            trace_id="empty",
            conversation_id="empty-conv",
            framework="test",
        )
        e = ConversationEvaluator()
        result = e.evaluate(trace)
        # Trivial result for < 2 turns
        assert result.overall_grade == "F"
        assert result.overall_score == 0.5

    def test_single_turn(self):
        trace = _make_trace([
            ("user", "Hello"),
        ])
        e = ConversationEvaluator()
        result = e.evaluate(trace)
        # < 2 turns => trivial result
        assert result.overall_score >= 0

    def test_very_long_conversation(self):
        turns = []
        for i in range(30):
            turns.append(("user", f"Question about topic {i}: explain the concept"))
            turns.append(("agent", f"Topic {i} involves multiple complex ideas related to algorithms and data structures"))
        trace = _make_trace(turns)

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        assert 0 <= result.overall_score <= 1

    def test_agent_only_turns(self):
        """Conversation with no user turns after initial."""
        trace = _make_trace([
            ("user", "Start the task"),
            ("agent", "Step 1 complete"),
            ("agent", "Step 2 complete"),
            ("agent", "All done!"),
        ])

        e = ConversationEvaluator()
        result = e.evaluate(trace)
        assert 0 <= result.overall_score <= 1


class TestCustomWeights:
    def test_custom_dimension_weights(self):
        trace = _make_trace([
            ("user", "Write code"),
            ("agent", "Here is the code"),
            ("user", "Perfect, thanks!"),
        ])

        # Weight goal achievement heavily
        weights = {
            "goal_achievement": 0.90,
            "coherence": 0.025,
            "efficiency": 0.025,
            "error_recovery": 0.025,
            "user_satisfaction": 0.025,
        }
        e = ConversationEvaluator(dimension_weights=weights)
        result = e.evaluate(trace)
        assert 0 <= result.overall_score <= 1


class TestDimensionResult:
    def test_to_dict(self):
        dr = DimensionResult(
            dimension=EvalDimension.GOAL_ACHIEVEMENT,
            score=0.85,
            confidence=0.9,
            method="heuristic",
            details={"key": "value"},
            evidence=["evidence1"],
        )
        d = dr.to_dict()
        assert d["dimension"] == "goal_achievement"
        assert d["score"] == 0.85
        assert d["confidence"] == 0.9
        assert d["method"] == "heuristic"


class TestTurnAnnotation:
    def test_to_dict(self):
        ann = TurnAnnotation(
            turn_number=3,
            annotation="Good recovery",
            score_impact=0.1,
            dimension=EvalDimension.ERROR_RECOVERY,
        )
        d = ann.to_dict()
        assert d["turn_number"] == 3
        assert d["annotation"] == "Good recovery"
        assert d["dimension"] == "error_recovery"
