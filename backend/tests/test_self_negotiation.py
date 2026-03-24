"""Tests for self-eval weakness detection (self-negotiation + evaluator leniency)."""
import pytest
from app.detection.hallucination import HallucinationDetector
from app.detection.persona import PersonaConsistencyScorer, RoleType


class TestSelfNegotiation:
    """Tests for HallucinationDetector._detect_self_negotiation."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_no_self_negotiation_clean_output(self):
        """Clean output with no problems/dismissals should score 0."""
        output = "The code implementation looks correct and follows best practices."
        score, evidence = self.detector._detect_self_negotiation(output)
        assert score == 0.0
        assert len(evidence) == 0

    def test_self_negotiation_detected(self):
        """Output that identifies problems then dismisses them should score > 0."""
        output = (
            "The code has several issues: there's a bug in the error handling, "
            "and the input validation is missing. However this is acceptable for "
            "the current sprint, and these are edge cases that won't affect most users."
        )
        score, evidence = self.detector._detect_self_negotiation(output)
        assert score > 0.0
        assert len(evidence) > 0
        assert "Self-negotiation" in evidence[0]

    def test_high_rating_despite_issues(self):
        """High self-rating (8/10+) despite multiple problems should flag."""
        output = (
            "I found a bug in the parser and the error handling is incomplete. "
            "The test coverage is missing for edge cases. "
            "Overall score: 9/10"
        )
        score, evidence = self.detector._detect_self_negotiation(output)
        assert score >= 0.5
        assert any("self-rating" in e.lower() for e in evidence)

    def test_problems_only_no_dismissal(self):
        """Identifying problems without dismissing them should NOT flag."""
        output = (
            "Critical bugs found: the error handling fails on null input, "
            "the problem with authentication means it's broken for new users."
        )
        score, evidence = self.detector._detect_self_negotiation(output)
        # No dismissal → should not flag (or low score)
        assert score < 0.5

    def test_integration_with_hallucination_detection(self):
        """Self-negotiation should affect hallucination grounding score."""
        output = (
            "Question: Is the code quality acceptable?\n"
            "There are several issues and bugs. The implementation is incomplete "
            "and the error handling is wrong. But this is minor and good enough. "
            "Not a big deal. I'll approve. Score: 9/10"
        )
        result = self.detector.detect_hallucination(output, sources=None)
        # Self-negotiation should be tracked in details
        assert result.details.get("self_negotiation_score", 0) > 0


class TestEvaluatorLeniency:
    """Tests for PersonaConsistencyScorer evaluator leniency detection."""

    def setup_method(self):
        self.scorer = PersonaConsistencyScorer()

    def test_no_leniency_clean_output(self):
        """Clean approval without issues should not flag leniency."""
        output = "The code looks great and follows all requirements. Approved."
        score = self.scorer._detect_evaluator_leniency(output)
        assert score == 0.0

    def test_leniency_detected_approve_despite_bugs(self):
        """Approving work despite multiple identified bugs should flag."""
        output = (
            "Found 3 bugs: error handling is broken, validation is missing, "
            "there's a problem with the auth flow, and a defect in caching. "
            "Overall looks good. Approved. Ready to ship."
        )
        score = self.scorer._detect_evaluator_leniency(output)
        assert score > 0.0

    def test_evaluator_role_type_exists(self):
        """EVALUATOR role type should be defined."""
        assert hasattr(RoleType, 'EVALUATOR')
        assert RoleType.EVALUATOR.value == "evaluator"
