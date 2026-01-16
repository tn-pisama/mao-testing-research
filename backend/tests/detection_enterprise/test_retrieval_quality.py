"""Tests for the Retrieval Quality Detector (F16: Retrieval Quality Failure)."""

import pytest
from app.detection_enterprise.retrieval_quality import (
    RetrievalQualityDetector,
    RetrievalQualityResult,
    RetrievalSeverity,
    IrrelevantDocument,
    CoverageGap,
)


# ============================================================================
# RetrievalQualityDetector Initialization Tests
# ============================================================================

class TestRetrievalQualityDetectorInit:
    """Tests for RetrievalQualityDetector initialization."""

    def test_default_initialization(self):
        """Should initialize with default thresholds."""
        detector = RetrievalQualityDetector()

        assert detector.relevance_threshold == 0.6
        assert detector.coverage_threshold == 0.5
        assert detector.precision_threshold == 0.7
        assert detector.min_query_length == 10
        assert detector.confidence_scaling == 1.0

    def test_custom_initialization(self):
        """Should accept custom thresholds."""
        detector = RetrievalQualityDetector(
            relevance_threshold=0.8,
            coverage_threshold=0.7,
            precision_threshold=0.9,
            min_query_length=20,
            confidence_scaling=0.9,
        )

        assert detector.relevance_threshold == 0.8
        assert detector.coverage_threshold == 0.7
        assert detector.precision_threshold == 0.9
        assert detector.min_query_length == 20
        assert detector.confidence_scaling == 0.9


# ============================================================================
# Query Topic Extraction Tests
# ============================================================================

class TestQueryTopicExtraction:
    """Tests for extracting topics from queries."""

    def test_extract_years(self):
        """Should extract year references."""
        detector = RetrievalQualityDetector()
        query = "What was the revenue in 2023 and 2024?"

        topics = detector._extract_query_topics(query)

        assert "2023" in topics
        assert "2024" in topics

    def test_extract_quarters(self):
        """Should extract quarter references."""
        detector = RetrievalQualityDetector()
        query = "Show Q3 results compared to Q2"

        topics = detector._extract_query_topics(query)

        assert "Q3" in topics or "q3" in [t.lower() for t in topics]
        assert "Q2" in topics or "q2" in [t.lower() for t in topics]

    def test_extract_key_terms(self):
        """Should extract key terms, filtering stopwords."""
        detector = RetrievalQualityDetector()
        query = "What is the revenue for Acme Corporation?"

        topics = detector._extract_query_topics(query)

        # Should have relevant terms, but not stopwords
        assert "revenue" in topics or any("revenue" in t for t in topics)
        assert "the" not in topics
        assert "is" not in topics
        assert "for" not in topics


# ============================================================================
# Document Relevance Scoring Tests
# ============================================================================

class TestDocumentRelevanceScoring:
    """Tests for scoring document relevance."""

    def test_high_relevance_score(self):
        """Should give high score to relevant document."""
        detector = RetrievalQualityDetector()
        query = "What was Acme Corp revenue in Q3 2024?"
        document = "In Q3 2024, Acme Corp reported revenue of $45.2M."
        query_topics = detector._extract_query_topics(query)

        score, reason = detector._score_document_relevance(query, document, query_topics)

        assert score >= 0.5
        assert "relevant" in reason.lower() or score > 0.3

    def test_low_relevance_score(self):
        """Should give low score to irrelevant document."""
        detector = RetrievalQualityDetector()
        query = "What was Acme Corp revenue in Q3 2024?"
        document = "The weather forecast shows sunny skies for the weekend."
        query_topics = detector._extract_query_topics(query)

        score, reason = detector._score_document_relevance(query, document, query_topics)

        assert score < 0.5

    def test_temporal_mismatch_detection(self):
        """Should detect temporal mismatch."""
        detector = RetrievalQualityDetector()
        query = "What happened in 2024?"
        document = "In 2020, the company launched a new product."
        query_topics = detector._extract_query_topics(query)

        score, reason = detector._score_document_relevance(query, document, query_topics)

        # Should have lower score or mention temporal mismatch
        assert score < 0.7 or "2020" in reason or "temporal" in reason.lower()


# ============================================================================
# Coverage Gap Detection Tests
# ============================================================================

class TestCoverageGapDetection:
    """Tests for detecting coverage gaps."""

    def test_detect_explicit_missing_data(self):
        """Should detect explicit mentions of missing data."""
        detector = RetrievalQualityDetector()
        query = "Find all Q3 2024 data"
        output = "I could not find any relevant data for Q3 2024."
        retrieved = ["Some unrelated document."]

        gaps = detector._detect_coverage_gaps(query, output, retrieved)

        assert len(gaps) >= 1
        assert any("missing" in g.topic.lower() or "explicit" in g.topic.lower() for g in gaps)

    def test_detect_incomplete_data(self):
        """Should detect mentions of incomplete data."""
        detector = RetrievalQualityDetector()
        query = "Get complete financial data"
        output = "The results are incomplete data and may not reflect the full picture."
        retrieved = ["Partial financial report."]

        gaps = detector._detect_coverage_gaps(query, output, retrieved)

        assert len(gaps) >= 1

    def test_detect_temporal_mismatch_gap(self):
        """Should detect temporal coverage gaps."""
        detector = RetrievalQualityDetector()
        query = "What was revenue in 2024?"
        output = "Based on the documents, the revenue in 2024 was..."
        retrieved = ["In 2020, revenue was $10M."]

        gaps = detector._detect_coverage_gaps(query, output, retrieved)

        temporal_gaps = [g for g in gaps if "temporal" in g.topic.lower()]
        assert len(temporal_gaps) >= 1

    def test_no_gaps_for_complete_data(self):
        """Should not detect gaps when data is complete."""
        detector = RetrievalQualityDetector()
        query = "What was revenue in Q3 2024?"
        output = "Revenue in Q3 2024 was $45.2M."
        retrieved = ["In Q3 2024, Acme Corp reported revenue of $45.2M."]

        gaps = detector._detect_coverage_gaps(query, output, retrieved)

        # Should have no or few gaps
        assert len(gaps) <= 1


# ============================================================================
# Precision Computation Tests
# ============================================================================

class TestPrecisionComputation:
    """Tests for precision calculation."""

    def test_full_precision(self):
        """Should return 1.0 when all docs are relevant."""
        detector = RetrievalQualityDetector(relevance_threshold=0.5)
        query = "Test query"
        documents = ["Doc 1", "Doc 2", "Doc 3"]
        relevance_scores = [0.8, 0.7, 0.9]  # All above threshold

        precision = detector._compute_precision(query, documents, relevance_scores)

        assert precision == 1.0

    def test_zero_precision(self):
        """Should return 0.0 when no docs are relevant."""
        detector = RetrievalQualityDetector(relevance_threshold=0.5)
        query = "Test query"
        documents = ["Doc 1", "Doc 2", "Doc 3"]
        relevance_scores = [0.2, 0.3, 0.1]  # All below threshold

        precision = detector._compute_precision(query, documents, relevance_scores)

        assert precision == 0.0

    def test_partial_precision(self):
        """Should return correct precision for mixed relevance."""
        detector = RetrievalQualityDetector(relevance_threshold=0.5)
        query = "Test query"
        documents = ["Doc 1", "Doc 2", "Doc 3", "Doc 4"]
        relevance_scores = [0.8, 0.3, 0.7, 0.2]  # 2 above threshold

        precision = detector._compute_precision(query, documents, relevance_scores)

        assert precision == 0.5

    def test_empty_documents(self):
        """Should return 1.0 for empty document list."""
        detector = RetrievalQualityDetector()
        precision = detector._compute_precision("query", [], [])

        assert precision == 1.0


# ============================================================================
# Query Alignment Tests
# ============================================================================

class TestQueryAlignment:
    """Tests for query-document alignment computation."""

    def test_high_alignment(self):
        """Should compute high alignment for matching content."""
        detector = RetrievalQualityDetector()
        query = "Acme Corporation quarterly revenue report"
        documents = ["Acme Corporation Q3 revenue report shows growth."]

        alignment = detector._compute_query_alignment(query, documents)

        assert alignment >= 0.5

    def test_low_alignment(self):
        """Should compute low alignment for unrelated content."""
        detector = RetrievalQualityDetector()
        query = "Acme Corporation quarterly revenue report"
        documents = ["The weather forecast predicts sunny skies."]

        alignment = detector._compute_query_alignment(query, documents)

        assert alignment < 0.5

    def test_empty_documents(self):
        """Should return 1.0 for empty documents."""
        detector = RetrievalQualityDetector()
        alignment = detector._compute_query_alignment("query", [])

        assert alignment == 1.0


# ============================================================================
# Severity Classification Tests
# ============================================================================

class TestSeverityClassification:
    """Tests for severity determination."""

    def test_critical_severity_low_relevance(self):
        """Should return CRITICAL for very low relevance."""
        detector = RetrievalQualityDetector()

        severity = detector._determine_severity(
            relevance_score=0.15,
            precision=0.8,
            coverage_score=0.8,
            num_gaps=0,
        )

        assert severity == RetrievalSeverity.CRITICAL

    def test_critical_severity_low_precision(self):
        """Should return CRITICAL for very low precision."""
        detector = RetrievalQualityDetector()

        severity = detector._determine_severity(
            relevance_score=0.8,
            precision=0.15,
            coverage_score=0.8,
            num_gaps=0,
        )

        assert severity == RetrievalSeverity.CRITICAL

    def test_severe_severity(self):
        """Should return SEVERE for multiple issues."""
        detector = RetrievalQualityDetector()

        severity = detector._determine_severity(
            relevance_score=0.35,
            precision=0.5,
            coverage_score=0.5,
            num_gaps=2,
        )

        assert severity == RetrievalSeverity.SEVERE

    def test_moderate_severity(self):
        """Should return MODERATE for some issues."""
        detector = RetrievalQualityDetector()

        severity = detector._determine_severity(
            relevance_score=0.55,
            precision=0.7,
            coverage_score=0.8,
            num_gaps=1,
        )

        assert severity == RetrievalSeverity.MODERATE

    def test_minor_severity(self):
        """Should return MINOR for small issues."""
        detector = RetrievalQualityDetector()

        severity = detector._determine_severity(
            relevance_score=0.75,
            precision=0.75,
            coverage_score=0.9,
            num_gaps=0,
        )

        assert severity == RetrievalSeverity.MINOR

    def test_none_severity(self):
        """Should return NONE for good retrieval."""
        detector = RetrievalQualityDetector()

        severity = detector._determine_severity(
            relevance_score=0.9,
            precision=0.9,
            coverage_score=0.9,
            num_gaps=0,
        )

        assert severity == RetrievalSeverity.NONE


# ============================================================================
# detect() Integration Tests
# ============================================================================

class TestDetect:
    """Integration tests for the detect method."""

    def test_detect_short_query(self):
        """Should handle short query gracefully."""
        detector = RetrievalQualityDetector(min_query_length=10)
        query = "Hi"
        retrieved = ["Some document."]
        output = "Some output."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)
        assert result.detected is False
        assert "too short" in result.explanation.lower()

    def test_detect_no_documents(self):
        """Should detect failure when no documents retrieved."""
        detector = RetrievalQualityDetector()
        query = "What was the revenue in Q3 2024?"
        retrieved = []
        output = "I couldn't find any relevant information."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)
        assert result.detected is True
        assert result.severity == RetrievalSeverity.CRITICAL
        assert result.relevance_score == 0.0

    def test_detect_good_retrieval(self):
        """Should not detect failure for good retrieval."""
        detector = RetrievalQualityDetector()
        query = "What was Acme Corp revenue in Q3 2024?"
        retrieved = [
            "In Q3 2024, Acme Corp reported revenue of $45.2M, up 15% year-over-year.",
            "Acme Corp Q3 2024 earnings exceeded analyst expectations.",
        ]
        output = "Based on the documents, Acme Corp revenue in Q3 2024 was $45.2M."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)
        assert result.relevance_score >= 0.5

    def test_detect_poor_retrieval(self):
        """Should detect failure for poor retrieval."""
        detector = RetrievalQualityDetector()
        query = "What was Acme Corp revenue in Q3 2024?"
        retrieved = [
            "The weather forecast shows sunny skies.",
            "A recipe for chocolate cake requires flour.",
            "The history of ancient Rome spans centuries.",
        ]
        output = "I could not find relevant information about Acme Corp revenue."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)
        assert result.detected is True
        assert len(result.irrelevant_docs) >= 1

    def test_detect_returns_suggested_fix(self):
        """Should provide suggested fix when failure detected."""
        detector = RetrievalQualityDetector()
        query = "Find Q3 2024 financial data"
        retrieved = []
        output = "No data found."

        result = detector.detect(query, retrieved, output)

        assert result.detected is True
        assert result.suggested_fix is not None

    def test_detect_includes_calibration_info(self):
        """Should include calibration information."""
        detector = RetrievalQualityDetector()
        query = "What was revenue in Q3 2024?"
        retrieved = ["Q3 2024 revenue report."]
        output = "Revenue was reported."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result.calibration_info, dict)


# ============================================================================
# RetrievalQualityResult Tests
# ============================================================================

class TestRetrievalQualityResult:
    """Tests for RetrievalQualityResult dataclass."""

    def test_result_creation(self):
        """Should create result with all fields."""
        result = RetrievalQualityResult(
            detected=True,
            confidence=0.8,
            severity=RetrievalSeverity.MODERATE,
            relevance_score=0.5,
            coverage_score=0.6,
            precision=0.7,
            query_doc_alignment=0.65,
            irrelevant_docs=[
                IrrelevantDocument(
                    doc_id="doc_1",
                    reason="Low topic overlap",
                    relevance_score=0.2,
                )
            ],
            missing_signals=[
                CoverageGap(
                    topic="Missing Q3 data",
                    signal="Query asks for Q3 but docs lack it",
                    severity="medium",
                )
            ],
            explanation="Retrieval quality issues detected",
            suggested_fix="Improve query or expand document corpus",
        )

        assert result.detected is True
        assert result.confidence == 0.8
        assert result.severity == RetrievalSeverity.MODERATE
        assert len(result.irrelevant_docs) == 1
        assert len(result.missing_signals) == 1


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_single_document(self):
        """Should handle single document."""
        detector = RetrievalQualityDetector()
        query = "What was revenue in Q3 2024?"
        retrieved = ["Q3 2024 revenue was $45M."]
        output = "Revenue was $45M."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)

    def test_many_documents(self):
        """Should handle many documents."""
        detector = RetrievalQualityDetector()
        query = "Find all financial data"
        retrieved = [f"Financial document {i}" for i in range(20)]
        output = "Found 20 financial documents."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)

    def test_unicode_in_query(self):
        """Should handle Unicode characters in query."""
        detector = RetrievalQualityDetector()
        query = "Quelle était la situation financière de société française?"
        retrieved = ["La société française a déclaré des revenus de €10M."]
        output = "Les revenus étaient de €10M."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)

    def test_empty_output(self):
        """Should handle empty output."""
        detector = RetrievalQualityDetector()
        query = "What was revenue in 2024?"
        retrieved = ["Revenue report for 2024."]
        output = ""

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)

    def test_numeric_query(self):
        """Should handle queries with many numbers."""
        detector = RetrievalQualityDetector()
        query = "Compare Q1 2023 vs Q2 2023 vs Q3 2023 vs Q4 2023"
        retrieved = ["Q1 2023: $10M, Q2 2023: $12M, Q3 2023: $15M, Q4 2023: $18M"]
        output = "Quarterly comparison shows growth throughout 2023."

        result = detector.detect(query, retrieved, output)

        assert isinstance(result, RetrievalQualityResult)
