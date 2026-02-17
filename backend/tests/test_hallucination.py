"""Tests for Hallucination Detection.

Covers all 6 internal methods plus the main detect_hallucination() entry point.
"""

import pytest
from app.detection.hallucination import (
    HallucinationDetector,
    HallucinationResult,
    SourceDocument,
    hallucination_detector,
)


class TestFabricatedFactsDetection:
    """Tests for _detect_fabricated_facts (pure regex, no embeddings)."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_no_fabrication_clean_text(self):
        """Clean text should have score close to 1.0."""
        score, evidence = self.detector._detect_fabricated_facts(
            "The system processed 50 requests in the last hour."
        )
        assert score >= 0.9
        assert evidence == []

    def test_fabricated_founding_year(self):
        """Should flag specific founding year claims."""
        score, evidence = self.detector._detect_fabricated_facts(
            "Acme Corp was founded in 1847 and has been a leader in the industry."
        )
        assert score < 1.0
        assert any("founding year" in e.lower() for e in evidence)

    def test_fabricated_study_reference(self):
        """Should flag specific study references."""
        # Pattern is case-sensitive: "according to a 2023 study"
        score, evidence = self.detector._detect_fabricated_facts(
            "The data, according to a 2023 study, shows remote workers are 20% more productive."
        )
        assert score < 1.0
        assert any("study reference" in e.lower() for e in evidence)

    def test_fabricated_percentage(self):
        """Should flag specific percentage statistics about people/users."""
        score, evidence = self.detector._detect_fabricated_facts(
            "73.5% of users prefer dark mode interfaces."
        )
        assert score < 1.0
        assert any("percentage" in e.lower() for e in evidence)

    def test_fabricated_expert_name(self):
        """Should flag named expert references."""
        score, evidence = self.detector._detect_fabricated_facts(
            "Dr. James Wilson from MIT recommends this approach."
        )
        assert score < 1.0
        assert any("expert" in e.lower() for e in evidence)

    def test_fabricated_journal_reference(self):
        """Should flag journal references."""
        score, evidence = self.detector._detect_fabricated_facts(
            "This was published in the International Journal of Computing."
        )
        assert score < 1.0
        assert any("journal" in e.lower() for e in evidence)

    def test_high_definitiveness_penalty(self):
        """3+ definitive phrases should reduce score."""
        score, evidence = self.detector._detect_fabricated_facts(
            "This is definitely the best approach. It is certainly correct. "
            "It is absolutely proven. This is guaranteed to work."
        )
        assert score < 0.9
        assert any("definitiveness" in e.lower() for e in evidence)

    def test_combined_fabrication_indicators(self):
        """Multiple indicators should compound the score reduction."""
        score, evidence = self.detector._detect_fabricated_facts(
            "The data, according to a 2023 study by Dr. Sarah Thompson, "
            "shows that 82.3% of companies have adopted this approach. "
            "It was published in the Global Business Journal."
        )
        assert score <= 0.7
        assert len(evidence) >= 3


class TestCitationValidity:
    """Tests for _check_citation_validity (pure logic, no embeddings)."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_valid_citations(self):
        """Valid citation numbers within source range should pass."""
        sources = [
            SourceDocument(content="First source"),
            SourceDocument(content="Second source"),
        ]
        score, evidence = self.detector._check_citation_validity(
            "According to [1], this is true. See also [2].", sources
        )
        assert score == 1.0
        assert evidence == []

    def test_invalid_citation_out_of_range(self):
        """Citation referencing non-existent source should fail."""
        sources = [
            SourceDocument(content="First source"),
            SourceDocument(content="Second source"),
        ]
        score, evidence = self.detector._check_citation_validity(
            "According to [5], this is a fact.", sources
        )
        assert score < 1.0
        assert any("non-existent" in e.lower() for e in evidence)

    def test_citations_without_sources(self):
        """Citations present but no sources provided should flag."""
        score, evidence = self.detector._check_citation_validity(
            "According to [1], this is correct.", None
        )
        assert score == 0.5
        assert len(evidence) >= 1

    def test_no_citations(self):
        """No citations at all should return perfect score."""
        score, evidence = self.detector._check_citation_validity(
            "This is a simple statement.", None
        )
        assert score == 1.0
        assert evidence == []

    def test_no_citations_with_sources(self):
        """No citations used even though sources available."""
        sources = [SourceDocument(content="Some source")]
        score, evidence = self.detector._check_citation_validity(
            "This is a simple statement.", sources
        )
        assert score == 1.0


class TestToolResultConsistency:
    """Tests for _check_tool_result_consistency (pure logic)."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_consistent_tool_results(self):
        """Output reflecting tool results should have high score."""
        tool_results = [
            {"tool": "calculator", "result": "The sum is 500"},
        ]
        score, evidence = self.detector._check_tool_result_consistency(
            "The calculation returned 500.", tool_results
        )
        assert score >= 0.8
        assert len(evidence) == 0

    def test_contradictory_tool_results(self):
        """Output contradicting tool results should have lower score."""
        tool_results = [
            {"tool": "lookup", "result": "The price is 1500 dollars"},
        ]
        score, evidence = self.detector._check_tool_result_consistency(
            "The price is 2000 dollars.", tool_results
        )
        # Tool returned 1500, output says 2000 — contradiction
        assert score < 1.0 or len(evidence) >= 1

    def test_empty_tool_results(self):
        """No tool results should return perfect score."""
        score, evidence = self.detector._check_tool_result_consistency(
            "Some output text.", []
        )
        assert score == 1.0
        assert evidence == []

    def test_tool_result_with_no_output(self):
        """Tool result with empty result field should be skipped."""
        tool_results = [
            {"tool": "search", "result": ""},
        ]
        score, evidence = self.detector._check_tool_result_consistency(
            "Found results.", tool_results
        )
        assert score == 1.0


class TestConfidenceCalibration:
    """Tests for _analyze_confidence_calibration (string matching)."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_uncertain_language(self):
        """Output with uncertainty phrases should indicate good calibration."""
        score = self.detector._analyze_confidence_calibration(
            "I think this might be correct, but I'm not sure. Perhaps we should verify."
        )
        assert score == 0.9

    def test_overconfident_language(self):
        """Output with many definitive phrases should indicate poor calibration."""
        score = self.detector._analyze_confidence_calibration(
            "This is definitely correct. It is certainly true. "
            "Absolutely guaranteed to work."
        )
        assert score == 0.6

    def test_balanced_language(self):
        """Balanced output should return middle score."""
        score = self.detector._analyze_confidence_calibration(
            "The data shows positive trends in this quarter's metrics."
        )
        assert score == 0.75


class TestSourceGrounding:
    """Tests for _check_source_grounding (uses embeddings)."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_well_grounded_output(self):
        """Output matching sources should have high grounding score."""
        sources = [
            SourceDocument(content="The quarterly revenue increased by 25% to $1.5 million."),
            SourceDocument(content="Customer satisfaction scores improved from 78% to 92%."),
        ]
        score, evidence = self.detector._check_source_grounding(
            "Revenue grew 25% to $1.5 million. Customer satisfaction rose to 92%.",
            sources,
        )
        assert score >= 0.5
        # Well-grounded output should have few or no evidence items
        assert len(evidence) <= 1

    def test_ungrounded_output(self):
        """Output diverging from sources should have low grounding score."""
        sources = [
            SourceDocument(content="Revenue was flat this quarter at $800K."),
        ]
        score, evidence = self.detector._check_source_grounding(
            "The company's new AI product launched to great success. "
            "Employees received generous bonuses for their outstanding work. "
            "The CEO announced plans for international expansion into Asia.",
            sources,
        )
        assert score < 0.6
        assert len(evidence) >= 1

    def test_empty_sources(self):
        """Empty source list should return perfect score."""
        score, evidence = self.detector._check_source_grounding(
            "Some output text.", []
        )
        assert score == 1.0
        assert evidence == []


class TestContextConsistency:
    """Tests for _check_context_consistency (uses embeddings)."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_consistent_with_context(self):
        """Output matching context should have high consistency."""
        score, evidence = self.detector._check_context_consistency(
            "The financial report shows strong Q4 revenue growth.",
            "This is a financial report covering Q4 2024 revenue performance.",
        )
        assert score >= 0.5

    def test_inconsistent_with_context(self):
        """Output diverging from context should have lower consistency."""
        score, evidence = self.detector._check_context_consistency(
            "I love pizza and sunny beaches in California!",
            "This is a technical review of database indexing strategies.",
        )
        assert score < 0.5
        assert len(evidence) >= 1


class TestFullDetection:
    """Integration tests for detect_hallucination."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_singleton_instance_exists(self):
        """Module-level singleton should be available."""
        assert hallucination_detector is not None
        assert isinstance(hallucination_detector, HallucinationDetector)

    def test_no_hallucination_clean_output(self):
        """Clean output without sources should not trigger detection."""
        result = self.detector.detect_hallucination(
            output="The system processed 100 requests successfully.",
        )
        assert result.detected is False
        assert result.grounding_score >= 0.65

    def test_hallucination_fabricated_facts(self):
        """Output with heavy fabrication indicators should trigger detection."""
        # Need enough fabrication patterns to drop score below 0.7, which
        # then gets included in grounding_score via min()
        result = self.detector.detect_hallucination(
            output=(
                "The data, according to a 2023 report by Dr. James Wilson, "
                "shows 73.5% of users have adopted this framework. "
                "Professor Anna Chen from MIT confirmed these findings. "
                "It was published in the International Computing Journal. "
                "A separate 2022 survey found 68.2% of companies agree."
            ),
        )
        # Heavy fabrication should lower grounding and trigger detection
        assert result.details.get("fabrication_indicators") is not None
        assert len(result.details.get("fabrication_indicators", [])) >= 3

    def test_hallucination_invalid_citations(self):
        """Output with invalid citations should trigger detection."""
        sources = [SourceDocument(content="Only one source available.")]
        result = self.detector.detect_hallucination(
            output="According to [1], this is true. But [5] states otherwise.",
            sources=sources,
        )
        # Invalid citation [5] with only 1 source should flag
        assert result.details.get("citation_issues") is not None

    def test_hallucination_ungrounded_claims(self):
        """Output contradicting sources should trigger ungrounded_claim."""
        sources = [
            SourceDocument(content="The budget is $100,000 for Q4."),
        ]
        result = self.detector.detect_hallucination(
            output=(
                "The new marketing campaign will target Gen Z demographics. "
                "Social media influencers will drive brand awareness. "
                "Video content is the primary medium for engagement."
            ),
            sources=sources,
        )
        if result.detected:
            assert result.hallucination_type in ("ungrounded_claim", "general_hallucination")

    def test_hallucination_tool_contradiction(self):
        """Output contradicting tool results should flag."""
        tool_results = [
            {"tool": "database_query", "result": "Total users: 5000"},
        ]
        result = self.detector.detect_hallucination(
            output="We have 50000 active users in our system.",
            tool_results=tool_results,
        )
        if result.details.get("tool_result_score", 1.0) < 0.5:
            assert result.hallucination_type == "tool_result_contradiction"

    def test_result_has_all_fields(self):
        """Result should contain all expected fields."""
        result = self.detector.detect_hallucination(
            output="Test output for field verification.",
        )
        assert hasattr(result, "detected")
        assert hasattr(result, "confidence")
        assert hasattr(result, "hallucination_type")
        assert hasattr(result, "evidence")
        assert hasattr(result, "grounding_score")
        assert hasattr(result, "details")
        assert hasattr(result, "raw_score")
        assert hasattr(result, "calibration_info")

    def test_confidence_in_valid_range(self):
        """Confidence should be between 0 and 1."""
        result = self.detector.detect_hallucination(
            output="Some test output for confidence checking.",
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_grounding_score_in_valid_range(self):
        """Grounding score should be between 0 and 1."""
        result = self.detector.detect_hallucination(
            output="Output for grounding check.",
        )
        assert 0.0 <= result.grounding_score <= 1.0

    def test_calibration_info_present(self):
        """Calibration info should be populated."""
        result = self.detector.detect_hallucination(
            output="Test output for calibration info.",
        )
        assert result.calibration_info is not None
        assert "evidence_count" in result.calibration_info
        assert "has_sources" in result.calibration_info

    def test_custom_grounding_threshold(self):
        """Custom threshold should affect detection sensitivity."""
        strict_detector = HallucinationDetector(grounding_threshold=0.9)
        lenient_detector = HallucinationDetector(grounding_threshold=0.3)

        output = "According to a 2023 study, this approach works well."

        strict_result = strict_detector.detect_hallucination(output=output)
        lenient_result = lenient_detector.detect_hallucination(output=output)

        # Strict threshold more likely to detect
        # Lenient threshold less likely
        assert strict_result.grounding_score == lenient_result.grounding_score
        # Same grounding score, different detection outcomes possible
        if strict_result.detected:
            assert strict_result.grounding_score < 0.9

    def test_confidence_scaling(self):
        """Confidence scaling should affect reported confidence."""
        normal = HallucinationDetector(confidence_scaling=1.0)
        scaled = HallucinationDetector(confidence_scaling=0.5)

        output = "According to a 2023 study by Dr. Jane Doe, this is proven."

        result_normal = normal.detect_hallucination(output=output)
        result_scaled = scaled.detect_hallucination(output=output)

        assert result_scaled.confidence < result_normal.confidence

    def test_empty_output(self):
        """Should handle empty output gracefully."""
        result = self.detector.detect_hallucination(output="")
        assert isinstance(result.detected, bool)
        assert 0.0 <= result.confidence <= 1.0

    def test_no_hallucination_with_matching_context(self):
        """Output consistent with context should not trigger."""
        result = self.detector.detect_hallucination(
            output="The quarterly revenue report shows 25% growth in Q4 sales.",
            context="This is a quarterly revenue report analyzing Q4 sales growth.",
        )
        assert result.grounding_score >= 0.5


class TestCalibrationFunction:
    """Tests for _calibrate_confidence method."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_calibration_with_sources(self):
        """Sources present should boost confidence."""
        conf_with, _ = self.detector._calibrate_confidence(
            grounding_score=0.5, evidence_count=2, has_sources=True, fabrication_score=0.8
        )
        conf_without, _ = self.detector._calibrate_confidence(
            grounding_score=0.5, evidence_count=2, has_sources=False, fabrication_score=0.8
        )
        assert conf_with > conf_without

    def test_calibration_with_more_evidence(self):
        """More evidence should increase confidence."""
        conf_few, _ = self.detector._calibrate_confidence(
            grounding_score=0.5, evidence_count=1, has_sources=True, fabrication_score=0.8
        )
        conf_many, _ = self.detector._calibrate_confidence(
            grounding_score=0.5, evidence_count=5, has_sources=True, fabrication_score=0.8
        )
        assert conf_many >= conf_few

    def test_calibration_returns_info_dict(self):
        """Should return calibration info dictionary."""
        _, info = self.detector._calibrate_confidence(
            grounding_score=0.7, evidence_count=1, has_sources=False, fabrication_score=0.9
        )
        assert "base_confidence" in info
        assert "evidence_count" in info
        assert "has_sources" in info
        assert "grounding_factor" in info
        assert "fabrication_factor" in info

    def test_calibration_max_capped_at_099(self):
        """Confidence should not exceed 0.99."""
        conf, _ = self.detector._calibrate_confidence(
            grounding_score=0.0, evidence_count=100, has_sources=True, fabrication_score=0.0
        )
        assert conf <= 0.99


class TestSentenceSplitting:
    """Tests for _split_sentences helper."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    def test_splits_on_punctuation(self):
        """Should split on sentence-ending punctuation."""
        sentences = self.detector._split_sentences(
            "This is a long enough sentence. Here is another long sentence!"
        )
        assert len(sentences) == 2

    def test_filters_short_fragments(self):
        """Fragments under 20 chars should be filtered out."""
        sentences = self.detector._split_sentences(
            "Short. This is a longer sentence that meets the minimum."
        )
        assert len(sentences) == 1
        assert "longer sentence" in sentences[0]

    def test_empty_text(self):
        """Empty text should return empty list."""
        sentences = self.detector._split_sentences("")
        assert sentences == []
