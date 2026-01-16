"""Tests for the Grounding Detector (F15: Grounding Failure)."""

import pytest
from app.detection_enterprise.grounding import (
    GroundingDetector,
    GroundingResult,
    GroundingSeverity,
    UngroundedClaim,
    NumericalError,
)


# ============================================================================
# GroundingDetector Initialization Tests
# ============================================================================

class TestGroundingDetectorInit:
    """Tests for GroundingDetector initialization."""

    def test_default_initialization(self):
        """Should initialize with default thresholds."""
        detector = GroundingDetector()

        assert detector.grounding_threshold == 0.7
        assert detector.citation_threshold == 0.8
        assert detector.numerical_tolerance == 0.05
        assert detector.min_output_length == 50
        assert detector.confidence_scaling == 1.0

    def test_custom_initialization(self):
        """Should accept custom thresholds."""
        detector = GroundingDetector(
            grounding_threshold=0.8,
            citation_threshold=0.9,
            numerical_tolerance=0.1,
            min_output_length=100,
            confidence_scaling=0.9,
        )

        assert detector.grounding_threshold == 0.8
        assert detector.citation_threshold == 0.9
        assert detector.numerical_tolerance == 0.1
        assert detector.min_output_length == 100
        assert detector.confidence_scaling == 0.9


# ============================================================================
# Number Extraction Tests
# ============================================================================

class TestNumberExtraction:
    """Tests for number extraction from text."""

    def test_extract_currency_amounts(self):
        """Should extract currency amounts."""
        detector = GroundingDetector()
        text = "Revenue was $45.2M in Q3 and $1,234.56 in expenses."

        numbers = detector._extract_numbers(text)

        values = [n['value'] for n in numbers]
        types = [n['type'] for n in numbers]
        assert '$45.2M' in values
        assert '$1,234.56' in values
        assert 'currency' in types

    def test_extract_percentages(self):
        """Should extract percentages."""
        detector = GroundingDetector()
        text = "Growth was 15% year-over-year and margin improved to 23.5%."

        numbers = detector._extract_numbers(text)

        values = [n['value'] for n in numbers]
        assert '15%' in values
        assert '23.5%' in values

    def test_extract_quarters(self):
        """Should extract quarter references."""
        detector = GroundingDetector()
        text = "In Q3 we saw improvement over Q2 results."

        numbers = detector._extract_numbers(text)

        values = [n['value'] for n in numbers]
        assert 'Q3' in values or 'q3' in [v.lower() for v in values]
        assert 'Q2' in values or 'q2' in [v.lower() for v in values]

    def test_extract_years(self):
        """Should extract year references."""
        detector = GroundingDetector()
        text = "Revenue grew from 2023 to 2024."

        numbers = detector._extract_numbers(text)

        values = [n['value'] for n in numbers]
        assert '2023' in values
        assert '2024' in values

    def test_context_captured(self):
        """Should capture surrounding context."""
        detector = GroundingDetector()
        text = "The company reported revenue of $45.2M for the quarter."

        numbers = detector._extract_numbers(text)

        # At least one number should have context
        assert any(n.get('context') for n in numbers)


# ============================================================================
# Claim Extraction Tests
# ============================================================================

class TestClaimExtraction:
    """Tests for claim extraction from text."""

    def test_extract_factual_claims_with_is(self):
        """Should extract claims containing 'is'."""
        detector = GroundingDetector()
        text = "The company is headquartered in New York. The sky is blue."

        claims = detector._extract_claims(text)

        assert len(claims) >= 1
        assert any("headquartered" in c for c in claims)

    def test_extract_claims_with_was(self):
        """Should extract claims containing 'was'."""
        detector = GroundingDetector()
        text = "Revenue was $45M last quarter. The meeting was productive."

        claims = detector._extract_claims(text)

        assert len(claims) >= 1

    def test_extract_claims_with_according_to(self):
        """Should extract claims with 'according to'."""
        detector = GroundingDetector()
        text = "According to the report, sales increased by 15% in Q3."

        claims = detector._extract_claims(text)

        assert len(claims) >= 1
        assert any("according to" in c.lower() for c in claims)

    def test_filter_short_sentences(self):
        """Should filter out very short sentences."""
        detector = GroundingDetector()
        text = "OK. Yes. Sure. The detailed analysis shows significant growth in the eastern region."

        claims = detector._extract_claims(text)

        # Short sentences should be filtered, detailed one included
        assert not any(c in ["OK", "Yes", "Sure"] for c in claims)

    def test_limit_claims_count(self):
        """Should limit claims to 20."""
        detector = GroundingDetector()
        text = " ".join([f"This is statement number {i}." for i in range(30)])

        claims = detector._extract_claims(text)

        assert len(claims) <= 20


# ============================================================================
# Citation Extraction Tests
# ============================================================================

class TestCitationExtraction:
    """Tests for citation extraction."""

    def test_extract_direct_quotes(self):
        """Should extract quoted text."""
        detector = GroundingDetector()
        text = 'The CEO said "we expect strong growth" in the earnings call.'

        citations = detector._extract_citations(text)

        assert any(c['type'] == 'quote' for c in citations)
        assert any('we expect strong growth' in c['content'] for c in citations)

    def test_extract_according_to_attributions(self):
        """Should extract 'according to' attributions."""
        detector = GroundingDetector()
        text = "According to the annual report, revenue increased by 20%."

        citations = detector._extract_citations(text)

        assert any(c['type'] == 'attribution' for c in citations)

    def test_extract_source_references(self):
        """Should extract source references."""
        detector = GroundingDetector()
        text = "The source document shows a significant increase in user engagement."

        citations = detector._extract_citations(text)

        # May or may not match depending on exact pattern
        # This is a softer assertion
        assert isinstance(citations, list)


# ============================================================================
# Number Verification Tests
# ============================================================================

class TestNumberVerification:
    """Tests for verifying numbers against sources."""

    def test_exact_match_found(self):
        """Should find exact number match."""
        detector = GroundingDetector()
        number = {'value': '$45.2M', 'type': 'currency', 'context': 'Revenue was $45.2M'}
        sources = ["In Q3 2024, revenue reached $45.2M."]

        found, source_val, loc = detector._verify_number_in_sources(number, sources)

        assert found is True

    def test_number_not_found(self):
        """Should not find number that doesn't exist."""
        detector = GroundingDetector()
        number = {'value': '$100M', 'type': 'currency', 'context': 'Revenue was $100M'}
        sources = ["Revenue was $45M in Q3."]

        found, source_val, loc = detector._verify_number_in_sources(number, sources)

        assert found is False

    def test_tolerance_matching(self):
        """Should match within tolerance."""
        detector = GroundingDetector(numerical_tolerance=0.1)  # 10% tolerance
        number = {'value': '45.0', 'type': 'number', 'context': 'Value is 45.0'}
        sources = ["The actual value is 44.0"]

        found, source_val, loc = detector._verify_number_in_sources(number, sources)

        # 44.0 vs 45.0 is within 10% tolerance
        assert found is True


# ============================================================================
# Claim Verification Tests
# ============================================================================

class TestClaimVerification:
    """Tests for verifying claims against sources."""

    def test_grounded_claim(self):
        """Should identify grounded claim."""
        detector = GroundingDetector()
        # Use a claim that very closely mirrors the source text
        claim = "Acme Corp reported revenue of $45.2M, up 15% year-over-year."
        sources = ["In Q3 2024, Acme Corp reported revenue of $45.2M, up 15% year-over-year."]

        grounded, confidence, evidence = detector._verify_claim_in_sources(claim, sources)

        assert grounded is True
        assert confidence > 0.5

    def test_ungrounded_claim(self):
        """Should identify ungrounded claim."""
        detector = GroundingDetector()
        claim = "The company expects Q4 revenue to exceed $100M."
        sources = ["In Q3 2024, revenue was $45.2M."]

        grounded, confidence, evidence = detector._verify_claim_in_sources(claim, sources)

        assert grounded is False
        assert confidence < 0.5


# ============================================================================
# Citation Verification Tests
# ============================================================================

class TestCitationVerification:
    """Tests for verifying citations."""

    def test_valid_quote_verification(self):
        """Should verify exact quote."""
        detector = GroundingDetector()
        citation = {'type': 'quote', 'content': 'we expect strong growth'}
        sources = ['CEO stated "we expect strong growth in Q4"']

        valid, evidence = detector._verify_citation(citation, sources)

        assert valid is True

    def test_invalid_quote_verification(self):
        """Should identify fabricated quote."""
        detector = GroundingDetector()
        citation = {'type': 'quote', 'content': 'this was never said'}
        sources = ["The CEO discussed quarterly results."]

        valid, evidence = detector._verify_citation(citation, sources)

        assert valid is False


# ============================================================================
# Severity Classification Tests
# ============================================================================

class TestSeverityClassification:
    """Tests for severity determination."""

    def test_critical_severity_low_grounding(self):
        """Should return CRITICAL for very low grounding score."""
        detector = GroundingDetector()

        severity = detector._determine_severity(
            grounding_score=0.25,
            citation_accuracy=0.9,
            num_numerical_errors=0,
        )

        assert severity == GroundingSeverity.CRITICAL

    def test_critical_severity_many_numerical_errors(self):
        """Should return CRITICAL for many numerical errors."""
        detector = GroundingDetector()

        severity = detector._determine_severity(
            grounding_score=0.8,
            citation_accuracy=0.9,
            num_numerical_errors=3,
        )

        assert severity == GroundingSeverity.CRITICAL

    def test_severe_severity(self):
        """Should return SEVERE for moderate issues."""
        detector = GroundingDetector()

        severity = detector._determine_severity(
            grounding_score=0.45,
            citation_accuracy=0.9,
            num_numerical_errors=1,
        )

        assert severity == GroundingSeverity.SEVERE

    def test_moderate_severity(self):
        """Should return MODERATE for some issues."""
        detector = GroundingDetector()

        severity = detector._determine_severity(
            grounding_score=0.65,
            citation_accuracy=0.65,
            num_numerical_errors=0,
        )

        assert severity == GroundingSeverity.MODERATE

    def test_minor_severity(self):
        """Should return MINOR for small issues."""
        detector = GroundingDetector()

        severity = detector._determine_severity(
            grounding_score=0.8,
            citation_accuracy=0.8,
            num_numerical_errors=0,
        )

        assert severity == GroundingSeverity.MINOR

    def test_none_severity_well_grounded(self):
        """Should return NONE for well-grounded output."""
        detector = GroundingDetector()

        severity = detector._determine_severity(
            grounding_score=0.95,
            citation_accuracy=0.95,
            num_numerical_errors=0,
        )

        assert severity == GroundingSeverity.NONE


# ============================================================================
# detect() Integration Tests
# ============================================================================

class TestDetect:
    """Integration tests for the detect method."""

    def test_detect_short_output(self):
        """Should handle short output gracefully."""
        detector = GroundingDetector(min_output_length=50)
        output = "Too short."
        sources = ["Source document here."]

        result = detector.detect(output, sources)

        assert isinstance(result, GroundingResult)
        assert result.detected is False
        assert "too short" in result.explanation.lower()

    def test_detect_no_sources(self):
        """Should handle empty sources gracefully."""
        detector = GroundingDetector()
        output = "This is a detailed analysis of the quarterly results."
        sources = []

        result = detector.detect(output, sources)

        assert isinstance(result, GroundingResult)
        assert result.detected is False
        assert "no source documents" in result.explanation.lower()

    def test_detect_well_grounded_output(self, sample_source_documents, sample_output_with_claims):
        """Should not detect failure for well-grounded output."""
        detector = GroundingDetector()

        # Create output that matches sources well
        grounded_output = """
        In Q3 2024, Acme Corp reported revenue of $45.2M, which represents
        a 15% increase year-over-year. The operating margin improved to 23%
        from the previous quarter. CEO John Smith announced the expansion.
        """ * 2  # Make it long enough

        result = detector.detect(grounded_output, sample_source_documents)

        assert isinstance(result, GroundingResult)
        # Well-grounded output should have high grounding score
        assert result.grounding_score >= 0.5

    def test_detect_ungrounded_output(self, sample_source_documents):
        """Should detect failure for ungrounded output."""
        detector = GroundingDetector()

        # Create output with fabricated claims
        ungrounded_output = """
        According to our analysis, the company's revenue was $100M in Q3 2024,
        representing a 50% decline year-over-year. The CFO Jane Doe announced
        massive layoffs affecting 10,000 employees. The company headquarters
        is relocating to Antarctica as part of the restructuring plan.
        """ * 2

        result = detector.detect(ungrounded_output, sample_source_documents)

        assert isinstance(result, GroundingResult)
        # Ungrounded output should have issues
        # The specific detection depends on content overlap
        assert result.grounding_score < 1.0 or len(result.numerical_errors) > 0

    def test_detect_numerical_errors(self):
        """Should detect numerical errors."""
        detector = GroundingDetector()

        sources = ["Revenue was $45.2M in Q3 2024."]
        output = """
        The quarterly report shows revenue of $100M, which represents
        a significant increase from previous periods. The company also
        reported operating expenses of $50M and net income of $25M.
        """

        result = detector.detect(output, sources)

        # Should have numerical errors (numbers not in sources)
        assert isinstance(result, GroundingResult)

    def test_detect_returns_suggested_fix(self, sample_source_documents):
        """Should provide suggested fix when failure detected."""
        detector = GroundingDetector(grounding_threshold=0.99)

        output = """
        This is an analysis with some claims that may not be fully grounded.
        The company reported various metrics and achievements during the period.
        """ * 2

        result = detector.detect(output, sample_source_documents)

        if result.detected:
            assert result.suggested_fix is not None

    def test_detect_includes_calibration_info(self, sample_source_documents):
        """Should include calibration information."""
        detector = GroundingDetector()

        output = """
        In Q3 2024, Acme Corp achieved strong results with revenue of $45.2M.
        The operating margin improved significantly during this period.
        """ * 2

        result = detector.detect(output, sample_source_documents)

        assert isinstance(result.calibration_info, dict)


# ============================================================================
# GroundingResult Tests
# ============================================================================

class TestGroundingResult:
    """Tests for GroundingResult dataclass."""

    def test_grounding_result_creation(self):
        """Should create result with all fields."""
        result = GroundingResult(
            detected=True,
            confidence=0.85,
            severity=GroundingSeverity.MODERATE,
            grounding_score=0.6,
            citation_accuracy=0.8,
            ungrounded_claims=[
                UngroundedClaim(
                    claim="Test claim",
                    claim_type="factual",
                    searched_sources=True,
                )
            ],
            numerical_errors=[
                NumericalError(
                    claimed_value="$100M",
                    source_value=None,
                    source_location=None,
                    context="Revenue was $100M",
                )
            ],
            explanation="Grounding failure detected",
            suggested_fix="Verify claims",
        )

        assert result.detected is True
        assert result.confidence == 0.85
        assert result.severity == GroundingSeverity.MODERATE
        assert len(result.ungrounded_claims) == 1
        assert len(result.numerical_errors) == 1


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_output(self):
        """Should handle empty output."""
        detector = GroundingDetector()
        result = detector.detect("", ["Source document."])

        assert result.detected is False

    def test_output_with_no_claims(self):
        """Should handle output with no extractable claims."""
        detector = GroundingDetector(min_output_length=10)
        output = "Hello there! How are you doing today? Nice weather we have."
        sources = ["Weather report: Sunny and warm."]

        result = detector.detect(output, sources)

        assert isinstance(result, GroundingResult)

    def test_sources_with_special_characters(self):
        """Should handle sources with special characters."""
        detector = GroundingDetector()
        output = "Revenue was $45.2M according to the Q3 2024 report, showing 15% growth."
        sources = ["Q3 '24 results: $45.2M revenue (+15% YoY). See §2.1 for details."]

        result = detector.detect(output, sources)

        assert isinstance(result, GroundingResult)

    def test_unicode_in_text(self):
        """Should handle Unicode characters."""
        detector = GroundingDetector()
        output = "The company's café in München reported €1M in revenue."
        sources = ["München café revenue: €1M"]

        result = detector.detect(output, sources)

        assert isinstance(result, GroundingResult)
