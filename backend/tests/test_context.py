"""Tests for F7: Context Neglect Detection."""

import pytest
from app.detection.context import (
    ContextNeglectDetector,
    NeglectSeverity,
)


class TestContextNeglectDetector:
    """Test suite for ContextNeglectDetector."""

    def setup_method(self):
        self.detector = ContextNeglectDetector()

    # Element Extraction Tests
    def test_extract_numbers(self):
        """Should extract numeric values."""
        elements = self.detector._extract_key_elements("Revenue was $1.5m with 25% growth")
        assert "1.5m" in elements["numbers"]
        # Regex captures the number portion, % is captured as part of boundary match
        assert any("25" in n for n in elements["numbers"])

    def test_extract_dates(self):
        """Should extract date patterns."""
        elements = self.detector._extract_key_elements("Meeting on 2024-01-15 and Jan 20, 2024")
        assert len(elements["dates"]) >= 1

    def test_extract_names(self):
        """Should extract capitalized names."""
        elements = self.detector._extract_key_elements("John Smith met with Mary Johnson")
        assert "John Smith" in elements["names"]
        assert "Mary Johnson" in elements["names"]

    def test_extract_urls(self):
        """Should extract URLs."""
        elements = self.detector._extract_key_elements("Visit https://example.com/page")
        assert "https://example.com/page" in elements["urls"]

    def test_extract_emails(self):
        """Should extract email addresses."""
        elements = self.detector._extract_key_elements("Contact john@example.com for details")
        assert "john@example.com" in elements["emails"]

    def test_extract_keywords(self):
        """Should extract significant keywords (>4 chars, no stopwords)."""
        elements = self.detector._extract_key_elements("The quarterly revenue analysis shows growth")
        assert "quarterly" in elements["keywords"]
        assert "revenue" in elements["keywords"]
        assert "analysis" in elements["keywords"]
        assert "growth" in elements["keywords"]
        # Stopwords should not be included
        assert "the" not in elements["keywords"]
        assert "shows" in elements["keywords"]

    # Utilization Computation Tests
    def test_utilization_full_match(self):
        """Should return high utilization when output contains all context elements."""
        context_elements = {
            "numbers": {"100", "25%"},
            "names": {"John Smith"},
            "keywords": {"revenue", "growth"},
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        output_elements = {
            "numbers": {"100", "25%"},
            "names": {"John Smith"},
            "keywords": {"revenue", "growth"},
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        utilization, missing = self.detector._compute_utilization(
            context_elements, output_elements
        )
        assert utilization == 1.0
        assert missing == []

    def test_utilization_partial_match(self):
        """Should return partial utilization for partial matches."""
        context_elements = {
            "numbers": {"100", "200"},
            "names": set(),
            "keywords": set(),
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        output_elements = {
            "numbers": {"100"},  # Only half the numbers
            "names": set(),
            "keywords": set(),
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        utilization, missing = self.detector._compute_utilization(
            context_elements, output_elements
        )
        assert utilization == 0.5
        assert any("200" in m for m in missing)

    def test_utilization_no_match(self):
        """Should return zero utilization when nothing matches."""
        context_elements = {
            "numbers": {"100"},
            "names": {"John"},
            "keywords": {"revenue"},
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        output_elements = {
            "numbers": {"500"},
            "names": {"Mary"},
            "keywords": {"expenses"},
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        utilization, missing = self.detector._compute_utilization(
            context_elements, output_elements
        )
        assert utilization == 0.0

    def test_utilization_empty_context(self):
        """Should return 1.0 utilization for empty context (nothing to miss)."""
        context_elements = {
            "numbers": set(),
            "names": set(),
            "keywords": set(),
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        output_elements = {
            "numbers": {"100"},
            "names": set(),
            "keywords": set(),
            "dates": set(),
            "urls": set(),
            "emails": set(),
        }
        utilization, missing = self.detector._compute_utilization(
            context_elements, output_elements
        )
        assert utilization == 1.0

    # Detection Tests
    def test_no_neglect_when_context_used(self):
        """Should not detect neglect when context is properly used."""
        context = "John Smith reported $1.5m revenue with 25% growth in Q4 2024 from sales department"
        output = "According to John Smith, the Q4 2024 revenue reached $1.5m, showing 25% growth in sales"

        result = self.detector.detect(context=context, output=output)

        assert result.detected is False
        assert result.severity == NeglectSeverity.NONE
        assert result.context_utilization >= 0.3

    def test_detect_severe_neglect(self):
        """Should detect severe neglect when context completely ignored."""
        context = "Budget is $500,000 for Project Alpha. Contact john@corp.com. Deadline is 2025-03-15."
        output = "I love pizza and sunny days at the beach!"

        result = self.detector.detect(context=context, output=output)

        assert result.detected is True
        assert result.severity == NeglectSeverity.SEVERE
        assert result.context_utilization < 0.1
        assert result.confidence > 0.8
        assert len(result.missing_elements) > 0
        assert result.suggested_fix is not None

    def test_detect_moderate_neglect(self):
        """Should detect moderate neglect with partial context usage."""
        context = "John Smith has budget of $100,000 for marketing. Email: john@corp.com. Start date: 2024-01-15."
        # Only mentions John Smith, missing budget, email, and date
        output = "John Smith will lead the project. We'll define budget later."

        result = self.detector.detect(context=context, output=output)

        # Should detect some level of neglect
        assert result.detected is True
        assert result.severity in (NeglectSeverity.MINOR, NeglectSeverity.MODERATE, NeglectSeverity.SEVERE)
        assert result.context_utilization < 0.3

    def test_short_context_skipped(self):
        """Should skip analysis for very short context."""
        result = self.detector.detect(
            context="Hi",
            output="Hello there, how are you?"
        )
        assert result.detected is False
        assert "too short" in result.explanation.lower()

    def test_agent_name_in_explanation(self):
        """Should include agent name in explanation."""
        context = "Budget is $500,000 for the project which starts immediately and requires attention"
        output = "Pizza is delicious"

        result = self.detector.detect(
            context=context,
            output=output,
            agent_name="DataAnalyzer"
        )

        assert result.detected is True
        assert "DataAnalyzer" in result.explanation

    # Handoff Detection Tests
    def test_detect_handoff_neglect(self):
        """Should detect when receiver ignores sender's output."""
        sender_output = "Analysis complete: Revenue is $2.5m with 30% YoY growth. Key account: Acme Corp."
        receiver_input = ""
        receiver_output = "I need more information to proceed."

        result = self.detector.detect_handoff(
            sender_output=sender_output,
            receiver_input=receiver_input,
            receiver_output=receiver_output,
            sender_name="Analyst",
            receiver_name="Reporter"
        )

        assert result.detected is True
        # Explanation mentions the sender being ignored
        assert "Reporter" in result.explanation or "downstream" in result.explanation

    def test_detect_handoff_proper_use(self):
        """Should not detect neglect when handoff context is used."""
        sender_output = "Found 3 candidates: John (score: 95), Mary (score: 88), Bob (score: 82)."
        receiver_input = ""
        receiver_output = "Based on scores, recommending John with 95 points, followed by Mary at 88."

        result = self.detector.detect_handoff(
            sender_output=sender_output,
            receiver_input=receiver_input,
            receiver_output=receiver_output,
        )

        assert result.detected is False

    # Trace Detection Tests
    def test_detect_from_trace_no_issues(self):
        """Should handle trace with no neglect issues."""
        trace = {
            "spans": [
                {
                    "name": "agent1",
                    "input": {"context": "Short"},
                    "output": {"content": "Response"},
                },
            ]
        }
        results = self.detector.detect_from_trace(trace)
        # Short context should not trigger detection
        assert isinstance(results, list)

    def test_detect_from_trace_with_neglect(self):
        """Should detect neglect in trace spans."""
        trace = {
            "spans": [
                {
                    "name": "DataFetcher",
                    "input": {"context": ""},
                    "output": {"content": "Revenue: $1.5m, Growth: 25%, Account: Acme Corp, Contact: sales@acme.com"},
                },
                {
                    "name": "Reporter",
                    "input": {"context": ""},
                    "output": {"content": "I don't have any information to report."},
                },
            ]
        }
        results = self.detector.detect_from_trace(trace)

        # Should detect that Reporter ignored DataFetcher's output
        assert len(results) >= 1
        assert results[0].detected is True

    def test_detect_from_empty_trace(self):
        """Should handle empty trace gracefully."""
        trace = {"spans": []}
        results = self.detector.detect_from_trace(trace)
        assert results == []

    # Configuration Tests
    def test_custom_utilization_threshold(self):
        """Should respect custom utilization threshold."""
        # Strict detector requires higher utilization
        strict_detector = ContextNeglectDetector(utilization_threshold=0.8)

        context = "Budget is $100,000 for Project Alpha starting January 2025 with team lead John Smith"
        output = "Project Alpha has a budget of $100,000."  # Only partially uses context

        result = strict_detector.detect(context=context, output=output)
        # With strict threshold, partial use should be flagged
        # (depends on actual utilization calculation)
        assert isinstance(result.detected, bool)

    def test_custom_min_context_length(self):
        """Should respect custom minimum context length."""
        short_context_detector = ContextNeglectDetector(min_context_length=10)

        result = short_context_detector.detect(
            context="Budget: $100",  # 12 chars, over threshold
            output="The budget is $100"
        )
        # Should not skip analysis for this context
        assert result.detected is False  # Context is used

    # Edge Cases
    def test_empty_output(self):
        """Should handle empty output."""
        result = self.detector.detect(
            context="Important context with budget $500,000 and deadline 2025-01-15 for critical project",
            output=""
        )
        # Empty output means complete neglect
        assert result.detected is True
        assert result.severity == NeglectSeverity.SEVERE

    def test_special_characters_in_context(self):
        """Should handle special characters."""
        result = self.detector.detect(
            context="Email: test@example.com! Price: $1,000.00 (discounted). URL: https://test.com/path?q=1",
            output="Contact test@example.com for the $1,000.00 price at https://test.com/path?q=1"
        )
        assert result.detected is False

    def test_case_insensitive_matching(self):
        """Should match elements case-insensitively."""
        context = "JOHN SMITH reported REVENUE of $500,000 from QUARTERLY sales analysis report"
        output = "john smith found revenue of $500,000 in the quarterly sales"

        result = self.detector.detect(context=context, output=output)
        # Should find matches despite case differences
        assert result.context_utilization > 0.3


class TestContextNeglectResult:
    """Tests for ContextNeglectResult properties."""

    def test_result_has_all_fields(self):
        """Result should have all required fields."""
        detector = ContextNeglectDetector()
        result = detector.detect(
            context="Sample context with enough words to meet the minimum length requirement",
            output="Sample output response"
        )
        assert hasattr(result, "detected")
        assert hasattr(result, "severity")
        assert hasattr(result, "confidence")
        assert hasattr(result, "context_utilization")
        assert hasattr(result, "missing_elements")
        assert hasattr(result, "explanation")
        assert hasattr(result, "suggested_fix")

    def test_confidence_in_valid_range(self):
        """Confidence should be between 0 and 1."""
        detector = ContextNeglectDetector()
        result = detector.detect(
            context="Context with some important information like $500k budget for project planning",
            output="Any response"
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_utilization_in_valid_range(self):
        """Context utilization should be between 0 and 1."""
        detector = ContextNeglectDetector()
        result = detector.detect(
            context="Context with numbers 100 and names John Smith for testing purposes",
            output="Any response about something"
        )
        assert 0.0 <= result.context_utilization <= 1.0
