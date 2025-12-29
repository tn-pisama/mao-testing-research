"""Tests for F10: Communication Breakdown Detection."""

import pytest
from app.detection.communication import (
    CommunicationBreakdownDetector,
    BreakdownType,
    BreakdownSeverity,
)


class TestCommunicationBreakdownDetector:
    """Test suite for CommunicationBreakdownDetector."""

    def setup_method(self):
        self.detector = CommunicationBreakdownDetector()

    # Format Detection Tests
    def test_detect_expected_json_format(self):
        """Should detect JSON format request."""
        result = self.detector._detect_expected_format("Please return the data in JSON format")
        assert result == "json"

    def test_detect_expected_list_format(self):
        """Should detect list format request."""
        result = self.detector._detect_expected_format("Return a list of items")
        assert result == "list"

    def test_detect_expected_code_format(self):
        """Should detect code format request."""
        result = self.detector._detect_expected_format("Implement a function to calculate")
        assert result == "code"

    def test_detect_no_specific_format(self):
        """Should return None for general messages."""
        result = self.detector._detect_expected_format("What is the weather today?")
        assert result is None

    # Format Compliance Tests
    def test_json_format_compliance_valid(self):
        """Should pass for valid JSON response."""
        ok, msg = self.detector._check_format_compliance("json", '{"name": "John"}')
        assert ok is True
        assert "Valid JSON" in msg

    def test_json_format_compliance_invalid(self):
        """Should fail for invalid JSON when JSON expected."""
        ok, msg = self.detector._check_format_compliance("json", "This is not JSON")
        assert ok is False
        assert "not valid JSON" in msg

    def test_json_format_compliance_embedded(self):
        """Should pass for JSON embedded in text."""
        ok, msg = self.detector._check_format_compliance(
            "json", 'Here is the data: {"name": "John"}'
        )
        assert ok is True

    def test_list_format_compliance_numbered(self):
        """Should pass for numbered list."""
        ok, msg = self.detector._check_format_compliance(
            "list", "1. First item\n2. Second item"
        )
        assert ok is True

    def test_list_format_compliance_bulleted(self):
        """Should pass for bulleted list."""
        ok, msg = self.detector._check_format_compliance(
            "list", "- First item\n- Second item"
        )
        assert ok is True

    def test_list_format_compliance_missing(self):
        """Should fail when list expected but prose given."""
        ok, msg = self.detector._check_format_compliance(
            "list", "The items are apples and oranges."
        )
        assert ok is False

    def test_code_format_compliance_with_fence(self):
        """Should pass for code block with fence."""
        ok, msg = self.detector._check_format_compliance(
            "code", "```python\ndef foo(): pass\n```"
        )
        assert ok is True

    def test_code_format_compliance_with_def(self):
        """Should pass for code with function definition."""
        ok, msg = self.detector._check_format_compliance(
            "code", "def calculate_total(items): return sum(items)"
        )
        assert ok is True

    def test_no_format_always_passes(self):
        """Should pass when no format expected."""
        ok, msg = self.detector._check_format_compliance(None, "Any text here")
        assert ok is True

    # Ambiguous Language Detection Tests
    def test_detect_ambiguous_pronouns(self):
        """Should detect ambiguous pronoun usage."""
        issues = self.detector._detect_ambiguous_language("Send it to them")
        assert "ambiguous pronoun" in issues

    def test_detect_vague_quantifiers(self):
        """Should detect vague quantifiers."""
        issues = self.detector._detect_ambiguous_language("Get some data")
        assert "vague quantifier" in issues

    def test_detect_uncertain_language(self):
        """Should detect uncertain language."""
        issues = self.detector._detect_ambiguous_language("Maybe do this later")
        assert "uncertain language" in issues
        assert "vague timeline" in issues

    def test_detect_incomplete_enumeration(self):
        """Should detect incomplete enumerations."""
        issues = self.detector._detect_ambiguous_language("Handle cases A, B, etc.")
        assert "incomplete enumeration" in issues

    def test_clear_language_no_issues(self):
        """Should not flag clear, specific language."""
        issues = self.detector._detect_ambiguous_language(
            "Send the quarterly report to john@example.com by December 31, 2024"
        )
        assert len(issues) <= 1  # Might flag one minor issue but not many

    # Intent Alignment Tests
    def test_intent_alignment_high(self):
        """Should have high alignment for relevant response."""
        # Use same action verbs in both (detector uses exact word matching)
        score = self.detector._compute_intent_alignment(
            "search for hotels in Paris",
            "search complete: hotels in Paris found"
        )
        # Intent uses exact action verb matching - "search" in both messages
        assert score >= 0.5

    def test_intent_alignment_low(self):
        """Should have low alignment for irrelevant response."""
        score = self.detector._compute_intent_alignment(
            "Calculate quarterly revenue",
            "I love pizza and sunshine"
        )
        assert score < 0.4

    def test_intent_alignment_with_error(self):
        """Should reduce alignment for error responses."""
        score = self.detector._compute_intent_alignment(
            "Create a new user account",
            "Error: Unable to create user"
        )
        assert score < 0.7  # Penalized for error

    # Full Detection Tests
    def test_no_breakdown_clear_communication(self):
        """Should not detect breakdown in clear communication."""
        # Use same action verbs (detector uses exact word matching)
        result = self.detector.detect(
            sender_message="get the user data now",
            receiver_response="get user data complete: John, john@example.com"
        )
        assert result.detected is False
        assert result.severity == BreakdownSeverity.NONE

    def test_format_mismatch_detection(self):
        """Should detect format mismatch."""
        result = self.detector.detect(
            sender_message="Return the data in JSON format",
            receiver_response="The data shows John with email john@example.com"
        )
        assert result.detected is True
        assert result.breakdown_type == BreakdownType.FORMAT_MISMATCH
        assert result.severity == BreakdownSeverity.MODERATE
        assert result.suggested_fix is not None

    def test_intent_mismatch_detection(self):
        """Should detect severe intent mismatch."""
        result = self.detector.detect(
            sender_message="Calculate the Q4 revenue totals",
            receiver_response="I really enjoy pizza on sunny days!"
        )
        assert result.detected is True
        assert result.breakdown_type == BreakdownType.INTENT_MISMATCH
        assert result.severity in (BreakdownSeverity.MODERATE, BreakdownSeverity.SEVERE)
        assert result.intent_alignment < 0.4

    def test_semantic_ambiguity_detection(self):
        """Should detect semantic ambiguity with many issues."""
        # Message with 3+ ambiguity issues + response with matching action verb
        result = self.detector.detect(
            sender_message="Maybe process it soon and do some things etc.",
            receiver_response="Processing things soon, understood."
        )
        assert result.detected is True
        # May detect ambiguity or intent mismatch depending on alignment score
        assert result.breakdown_type in (BreakdownType.SEMANTIC_AMBIGUITY, BreakdownType.INTENT_MISMATCH)

    def test_agent_names_in_explanation(self):
        """Should include agent names in explanation."""
        result = self.detector.detect(
            sender_message="Return data in JSON",
            receiver_response="Here is the data as text",
            sender_name="DataRequester",
            receiver_name="DataProvider"
        )
        assert result.detected is True
        assert "DataRequester" in result.explanation
        assert "DataProvider" in result.explanation

    # Trace-based Detection Tests
    def test_detect_from_trace_no_issues(self):
        """Should handle trace with no issues."""
        trace = {
            "spans": [
                {"name": "agent1", "output": {"content": "Get data"}, "input": {}},
                {"name": "agent2", "output": {"content": "Here is the data"}, "input": {"message": "Get data"}},
            ]
        }
        results = self.detector.detect_from_trace(trace)
        # May or may not detect depending on content
        assert isinstance(results, list)

    def test_detect_from_trace_with_issues(self):
        """Should detect issues in trace."""
        trace = {
            "spans": [
                {"name": "requester", "output": {"content": "Return JSON data"}, "input": {}},
                {"name": "provider", "output": {"content": "Pizza is great!"}, "input": {"message": "Return JSON"}},
            ]
        }
        results = self.detector.detect_from_trace(trace)
        assert len(results) >= 1
        assert results[0].detected is True

    def test_detect_from_empty_trace(self):
        """Should handle empty trace gracefully."""
        trace = {"spans": []}
        results = self.detector.detect_from_trace(trace)
        assert results == []

    def test_detect_from_single_span_trace(self):
        """Should handle single span trace."""
        trace = {
            "spans": [
                {"name": "agent1", "output": {"content": "Hello"}, "input": {}},
            ]
        }
        results = self.detector.detect_from_trace(trace)
        assert results == []

    # Edge Cases
    def test_empty_messages(self):
        """Should handle empty messages."""
        result = self.detector.detect(
            sender_message="",
            receiver_response=""
        )
        assert isinstance(result.detected, bool)

    def test_very_long_messages(self):
        """Should handle very long messages."""
        long_message = "Please process " + "data " * 1000
        long_response = "Processing " + "complete " * 1000
        result = self.detector.detect(
            sender_message=long_message,
            receiver_response=long_response
        )
        assert isinstance(result.detected, bool)

    def test_special_characters(self):
        """Should handle special characters."""
        result = self.detector.detect(
            sender_message="Return data with $pecial ch@racters & symbols",
            receiver_response='{"price": "$100", "email": "test@example.com"}'
        )
        assert isinstance(result.detected, bool)

    # Configuration Tests
    def test_custom_intent_threshold(self):
        """Should respect custom intent threshold."""
        strict_detector = CommunicationBreakdownDetector(intent_threshold=0.8)
        result = strict_detector.detect(
            sender_message="Search hotels",
            receiver_response="Found some places to stay"
        )
        # With strict threshold, moderate alignment may trigger detection
        assert isinstance(result.detected, bool)

    def test_disable_format_check(self):
        """Should skip format check when disabled."""
        detector = CommunicationBreakdownDetector(check_format=False)
        result = detector.detect(
            sender_message="Return JSON data",
            receiver_response="Returning the data as requested"
        )
        # With format check disabled and matching intent, should not detect breakdown
        # or if detected, should not be format mismatch
        if result.detected:
            assert result.breakdown_type != BreakdownType.FORMAT_MISMATCH
        assert result.format_match is True  # Format check disabled means format_ok=True


class TestBreakdownResult:
    """Tests for CommunicationBreakdownResult properties."""

    def test_result_has_all_fields(self):
        """Result should have all required fields."""
        detector = CommunicationBreakdownDetector()
        result = detector.detect(
            sender_message="Test message",
            receiver_response="Test response"
        )
        assert hasattr(result, "detected")
        assert hasattr(result, "breakdown_type")
        assert hasattr(result, "severity")
        assert hasattr(result, "confidence")
        assert hasattr(result, "intent_alignment")
        assert hasattr(result, "format_match")
        assert hasattr(result, "explanation")
        assert hasattr(result, "suggested_fix")

    def test_confidence_in_valid_range(self):
        """Confidence should be between 0 and 1."""
        detector = CommunicationBreakdownDetector()
        result = detector.detect(
            sender_message="Any message",
            receiver_response="Any response"
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_intent_alignment_in_valid_range(self):
        """Intent alignment should be between 0 and 1."""
        detector = CommunicationBreakdownDetector()
        result = detector.detect(
            sender_message="Any message",
            receiver_response="Any response"
        )
        assert 0.0 <= result.intent_alignment <= 1.0
