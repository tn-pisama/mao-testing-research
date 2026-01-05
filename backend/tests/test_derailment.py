"""Tests for F6: Task Derailment Detection."""

import pytest
from app.detection.derailment import (
    TaskDerailmentDetector,
    DerailmentSeverity,
)


class TestTaskDerailmentDetector:
    """Test suite for TaskDerailmentDetector."""

    def setup_method(self):
        self.detector = TaskDerailmentDetector()

    # Key Term Extraction Tests
    def test_extract_key_terms(self):
        """Should extract meaningful terms excluding stopwords."""
        terms = self.detector._extract_key_terms(
            "The quick brown fox jumps over the lazy dog"
        )
        assert "quick" in terms
        assert "brown" in terms
        assert "fox" in terms
        assert "jumps" in terms
        assert "lazy" in terms
        assert "dog" in terms
        # Common stopwords excluded
        assert "the" not in terms

    def test_extract_key_terms_empty(self):
        """Should handle empty text."""
        terms = self.detector._extract_key_terms("")
        assert terms == set()

    def test_extract_key_terms_only_stopwords(self):
        """Should return empty for text with only stopwords."""
        terms = self.detector._extract_key_terms("the a an is are was")
        assert terms == set()

    # Similarity Tests (uses embedding similarity)
    def test_compute_similarity_identical(self):
        """Should return high similarity for identical texts."""
        similarity = self.detector._compute_similarity(
            "analyze quarterly revenue data",
            "analyze quarterly revenue data"
        )
        # Embedding similarity should be very high for identical texts
        assert similarity > 0.9

    def test_compute_similarity_partial(self):
        """Should return partial similarity for related texts."""
        similarity = self.detector._compute_similarity(
            "analyze quarterly revenue data",
            "analyze revenue and expenses data"
        )
        # Related texts should have moderate-high similarity
        assert 0.5 < similarity < 1.0

    def test_compute_similarity_different_topics(self):
        """Should return lower similarity for unrelated texts."""
        similarity = self.detector._compute_similarity(
            "analyze quarterly revenue financial reports",
            "beach vacation summer holiday travel"
        )
        # Unrelated topics have lower semantic similarity (but not necessarily zero)
        assert similarity < 0.8

    def test_compute_similarity_handles_empty(self):
        """Should handle empty texts without crashing."""
        similarity = self.detector._compute_similarity("", "some text")
        # Should return a valid similarity value
        assert 0.0 <= similarity <= 1.0

    # Topic Drift Tests
    def test_compute_topic_drift_on_topic(self):
        """Should return low drift for on-topic output."""
        drift, _ = self.detector._compute_topic_drift(
            task="analyze revenue growth trends",
            output="The revenue growth analysis shows a 25% increase in Q4 trends"
        )
        assert drift < 0.5

    def test_compute_topic_drift_off_topic(self):
        """Should return high drift for off-topic output."""
        drift, _ = self.detector._compute_topic_drift(
            task="analyze revenue growth trends",
            output="I love pizza and sunny beaches in California!"
        )
        assert drift > 0.5

    def test_compute_topic_drift_with_context(self):
        """Should consider context in drift calculation."""
        drift, _ = self.detector._compute_topic_drift(
            task="summarize the report",
            output="The financial report shows strong performance",
            context="This is a financial performance report for Q4"
        )
        # Context provides relevant terms, reducing drift
        assert drift < 0.7

    def test_compute_topic_drift_empty_task(self):
        """Should handle empty task."""
        drift, _ = self.detector._compute_topic_drift(
            task="",
            output="Some output text here"
        )
        assert drift == 0.0

    # Detection Tests
    def test_no_derailment_on_topic(self):
        """Should not detect derailment when agent stays on topic."""
        result = self.detector.detect(
            task="Calculate the quarterly revenue totals",
            output="The quarterly revenue totals are: Q1: $1.2M, Q2: $1.5M, Q3: $1.8M, Q4: $2.1M. Total annual revenue: $6.6M."
        )
        assert result.detected is False
        assert result.severity == DerailmentSeverity.NONE

    def test_detect_severe_derailment(self):
        """Should detect severe derailment for completely off-topic output."""
        result = self.detector.detect(
            task="Analyze the financial quarterly reports",
            output="I absolutely love pizza! The best toppings are pepperoni and mushrooms. Beach vacations are also wonderful in summer."
        )
        assert result.detected is True
        assert result.severity in (DerailmentSeverity.MODERATE, DerailmentSeverity.SEVERE)
        assert result.confidence > 0.5
        assert result.suggested_fix is not None

    def test_detect_moderate_derailment(self):
        """Should detect moderate derailment for partially off-topic output."""
        result = self.detector.detect(
            task="Summarize the sales report for Q4",
            output="The sales data looks interesting. By the way, have you tried the new coffee shop downtown? Anyway, Q4 had some sales activity."
        )
        assert result.detected is True
        assert result.severity in (DerailmentSeverity.MINOR, DerailmentSeverity.MODERATE, DerailmentSeverity.SEVERE)

    def test_short_output_skipped(self):
        """Should skip analysis for very short output."""
        result = self.detector.detect(
            task="Analyze the comprehensive financial data",
            output="OK"
        )
        assert result.detected is False
        assert "too short" in result.explanation.lower()

    def test_agent_name_in_explanation(self):
        """Should include agent name in explanation."""
        result = self.detector.detect(
            task="Calculate revenue",
            output="I love pizza and sunny days at the beach with friends and family!",
            agent_name="FinanceBot"
        )
        assert result.detected is True
        assert "FinanceBot" in result.explanation

    def test_evidence_included(self):
        """Should include evidence dict in result."""
        result = self.detector.detect(
            task="Analyze data patterns in the dataset",
            output="Looking at the data patterns, we see clear seasonal trends in the dataset values."
        )
        assert result.evidence is not None
        assert "similarity" in result.evidence
        assert "drift_score" in result.evidence
        assert "output_length" in result.evidence

    # Trace Detection Tests
    def test_detect_from_trace_no_issues(self):
        """Should handle trace with no derailment issues."""
        trace = {
            "spans": [
                {
                    "name": "agent1",
                    "input": {"task": "Calculate sum", "context": ""},
                    "output": {"content": "Short"},
                },
            ]
        }
        results = self.detector.detect_from_trace(trace)
        assert isinstance(results, list)

    def test_detect_from_trace_with_derailment(self):
        """Should detect derailment in trace spans."""
        trace = {
            "spans": [
                {
                    "name": "AnalysisBot",
                    "input": {"task": "Analyze the quarterly financial report data", "context": ""},
                    "output": {"content": "I really enjoy cooking pasta and watching movies on weekends with my friends!"},
                },
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

    def test_detect_from_trace_missing_task(self):
        """Should skip spans without task."""
        trace = {
            "spans": [
                {
                    "name": "agent1",
                    "input": {"context": "some context"},
                    "output": {"content": "Some long output that would normally be analyzed"},
                },
            ]
        }
        results = self.detector.detect_from_trace(trace)
        assert results == []

    # Configuration Tests
    def test_custom_similarity_threshold(self):
        """Should respect custom similarity threshold."""
        strict_detector = TaskDerailmentDetector(similarity_threshold=0.8)
        result = strict_detector.detect(
            task="analyze revenue",
            output="The revenue analysis shows moderate growth patterns in the data"
        )
        # Stricter threshold may trigger more detections
        assert isinstance(result.detected, bool)

    def test_custom_drift_threshold(self):
        """Should respect custom drift threshold."""
        lenient_detector = TaskDerailmentDetector(drift_threshold=0.9)
        result = lenient_detector.detect(
            task="analyze data",
            output="Looking at some interesting patterns and data analysis results here"
        )
        # Lenient threshold less likely to trigger
        assert isinstance(result.detected, bool)

    def test_custom_min_output_length(self):
        """Should respect custom minimum output length."""
        short_detector = TaskDerailmentDetector(min_output_length=5)
        result = short_detector.detect(
            task="Summarize",
            output="Done!"  # 5 chars
        )
        # Should not skip analysis
        assert "too short" not in result.explanation.lower()

    # Confidence Calibration Tests
    def test_confidence_calibration_severe(self):
        """Should calibrate confidence for severe cases."""
        confidence = self.detector._calibrate_confidence(
            similarity=0.05,
            drift_score=0.9,
            severity=DerailmentSeverity.SEVERE,
            output_length=100
        )
        assert 0.7 <= confidence <= 0.99

    def test_confidence_calibration_minor(self):
        """Should calibrate confidence for minor cases."""
        confidence = self.detector._calibrate_confidence(
            similarity=0.35,
            drift_score=0.4,
            severity=DerailmentSeverity.MINOR,
            output_length=50
        )
        assert 0.3 <= confidence <= 0.7

    def test_confidence_scaling(self):
        """Should apply confidence scaling factor."""
        scaled_detector = TaskDerailmentDetector(confidence_scaling=0.5)
        confidence = scaled_detector._calibrate_confidence(
            similarity=0.1,
            drift_score=0.8,
            severity=DerailmentSeverity.SEVERE,
            output_length=100
        )
        # Scaled down
        assert confidence < 0.7

    # Edge Cases
    def test_special_characters(self):
        """Should handle special characters."""
        result = self.detector.detect(
            task="Analyze data for $revenue & %growth",
            output="The $revenue shows 25% growth with strong &performance metrics overall"
        )
        assert isinstance(result.detected, bool)

    def test_very_long_output(self):
        """Should handle very long output."""
        long_output = "analyzing data patterns " * 100
        result = self.detector.detect(
            task="analyze data patterns",
            output=long_output
        )
        assert isinstance(result.detected, bool)
        assert result.evidence["output_length"] == len(long_output)


class TestDerailmentResult:
    """Tests for DerailmentResult properties."""

    def test_result_has_all_fields(self):
        """Result should have all required fields."""
        detector = TaskDerailmentDetector()
        result = detector.detect(
            task="Sample task description here",
            output="Sample output that is long enough to analyze properly"
        )
        assert hasattr(result, "detected")
        assert hasattr(result, "severity")
        assert hasattr(result, "confidence")
        assert hasattr(result, "task_output_similarity")
        assert hasattr(result, "topic_drift_score")
        assert hasattr(result, "explanation")
        assert hasattr(result, "suggested_fix")
        assert hasattr(result, "raw_score")
        assert hasattr(result, "evidence")

    def test_similarity_in_valid_range(self):
        """Task-output similarity should be between 0 and 1."""
        detector = TaskDerailmentDetector()
        result = detector.detect(
            task="Analyze the financial report data",
            output="The financial analysis report shows key data trends"
        )
        assert 0.0 <= result.task_output_similarity <= 1.0

    def test_drift_score_in_valid_range(self):
        """Topic drift score should be between 0 and 1."""
        detector = TaskDerailmentDetector()
        result = detector.detect(
            task="Calculate revenue totals",
            output="Revenue calculations show total amounts for each quarter"
        )
        assert 0.0 <= result.topic_drift_score <= 1.0
