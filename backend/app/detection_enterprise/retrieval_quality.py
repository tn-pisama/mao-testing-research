"""
F16: Retrieval Quality Failure Detection (MAST Taxonomy)
========================================================

Detects when an agent retrieves wrong, irrelevant, or insufficient
documents for the task, leading to incomplete or incorrect reasoning.

Inspired by: Databricks OfficeQA benchmark showing humans need 50 min/question
to find data "buried across decades of publications" - retrieval is the bottleneck.

Detection approach:
1. Relevance scoring - are retrieved docs actually relevant to query?
2. Coverage analysis - did retrieval miss obviously relevant documents?
3. Precision measurement - ratio of useful vs total retrieved docs
4. Query-document alignment - semantic match between query intent and retrieved content
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RetrievalSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"  # Some irrelevant docs but core content present
    MODERATE = "moderate"  # Missing some relevant docs
    SEVERE = "severe"  # Most retrieved docs irrelevant
    CRITICAL = "critical"  # Complete retrieval failure


@dataclass
class IrrelevantDocument:
    """Represents a retrieved document that appears irrelevant."""
    doc_id: str
    reason: str
    relevance_score: float


@dataclass
class CoverageGap:
    """Represents a detected gap in document coverage."""
    topic: str
    signal: str  # What indicated this gap
    severity: str


@dataclass
class RetrievalQualityResult:
    detected: bool
    confidence: float
    severity: RetrievalSeverity
    relevance_score: float  # 0-1, avg relevance of retrieved docs
    coverage_score: float  # 0-1, estimated coverage of relevant docs
    precision: float  # relevant_retrieved / total_retrieved
    query_doc_alignment: float  # semantic similarity between query and docs
    irrelevant_docs: list[IrrelevantDocument]
    missing_signals: list[CoverageGap]
    explanation: str
    suggested_fix: Optional[str] = None
    calibration_info: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)


class RetrievalQualityDetector:
    """
    Detects F16: Retrieval Quality Failure - when agent retrieves
    wrong or insufficient documents for the task.

    Analyzes the quality, relevance, and coverage of retrieved documents
    relative to the query/task requirements.
    """

    def __init__(
        self,
        relevance_threshold: float = 0.6,
        coverage_threshold: float = 0.5,
        precision_threshold: float = 0.7,
        min_query_length: int = 10,
        confidence_scaling: float = 1.0,
    ):
        self.relevance_threshold = relevance_threshold
        self.coverage_threshold = coverage_threshold
        self.precision_threshold = precision_threshold
        self.min_query_length = min_query_length
        self.confidence_scaling = confidence_scaling
        self._embedder = None

    def _extract_query_topics(self, query: str) -> set[str]:
        """Extract key topics/entities from the query."""
        topics = set()

        # Extract years
        years = re.findall(r'\b20\d{2}\b', query)
        topics.update(years)

        # Extract quarters
        quarters = re.findall(r'\bQ[1-4]\b', query, re.IGNORECASE)
        topics.update(q.upper() for q in quarters)

        # Extract key terms (nouns, proper nouns)
        words = query.split()
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "what", "how",
            "when", "where", "why", "which", "who", "and", "or", "but",
            "for", "with", "about", "from", "to", "in", "on", "at",
        }

        for word in words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if len(clean_word) > 3 and clean_word not in stopwords:
                topics.add(clean_word)

        return topics

    def _score_document_relevance(
        self,
        query: str,
        document: str,
        query_topics: set[str],
    ) -> tuple[float, str]:
        """Score relevance of a document to the query.

        Returns: (relevance_score, reason)
        """
        doc_lower = document.lower()
        query_lower = query.lower()

        # Calculate topic overlap
        doc_words = set(doc_lower.split())
        topic_matches = sum(1 for topic in query_topics if topic.lower() in doc_lower)
        topic_score = topic_matches / len(query_topics) if query_topics else 0

        # Check for temporal alignment (year/quarter matching)
        query_years = set(re.findall(r'\b20\d{2}\b', query))
        doc_years = set(re.findall(r'\b20\d{2}\b', document))

        temporal_aligned = True
        temporal_reason = ""
        if query_years:
            year_overlap = query_years & doc_years
            if not year_overlap:
                temporal_aligned = False
                temporal_reason = f"Query asks for {query_years} but doc contains {doc_years or 'no years'}"

        # Check for entity alignment
        query_entities = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query))
        doc_entities = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', document))
        entity_overlap = len(query_entities & doc_entities) / len(query_entities) if query_entities else 1.0

        # Combined relevance score
        relevance = (topic_score * 0.5 + entity_overlap * 0.3 + (1.0 if temporal_aligned else 0.0) * 0.2)

        # Determine reason
        if relevance >= 0.7:
            reason = "Document appears highly relevant to query"
        elif relevance >= 0.4:
            reason = "Document has moderate relevance"
        elif temporal_reason:
            reason = temporal_reason
        elif entity_overlap < 0.3:
            reason = "Document lacks key entities from query"
        else:
            reason = f"Low topic overlap ({topic_score:.0%})"

        return relevance, reason

    def _detect_coverage_gaps(
        self,
        query: str,
        output: str,
        retrieved: list[str],
    ) -> list[CoverageGap]:
        """Detect signals that relevant documents may be missing."""
        gaps = []

        output_lower = output.lower()

        # Look for explicit mentions of missing information
        missing_patterns = [
            (r"(?:could not find|couldn't find|no (?:data|information|document))", "explicit_missing"),
            (r"(?:incomplete|partial|limited) (?:data|information|results)", "incomplete_data"),
            (r"(?:unable to|cannot) (?:locate|find|retrieve)", "retrieval_failure"),
            (r"(?:no results|nothing found|empty results)", "empty_results"),
            (r"(?:missing|lacking) (?:required|necessary|relevant)", "missing_required"),
        ]

        for pattern, gap_type in missing_patterns:
            if re.search(pattern, output_lower):
                gaps.append(CoverageGap(
                    topic="Explicit missing data",
                    signal=f"Output contains '{pattern}' indicator",
                    severity="high",
                ))

        # Check if output references data not in retrieved docs
        output_numbers = set(re.findall(r'\$[\d,]+(?:\.\d+)?[MBK]?', output))
        retrieved_text = " ".join(retrieved)
        retrieved_numbers = set(re.findall(r'\$[\d,]+(?:\.\d+)?[MBK]?', retrieved_text))

        unmatched_numbers = output_numbers - retrieved_numbers
        if unmatched_numbers:
            gaps.append(CoverageGap(
                topic="Ungrounded numbers",
                signal=f"Output contains {len(unmatched_numbers)} numbers not in retrieved docs",
                severity="medium",
            ))

        # Check temporal coverage
        query_years = set(re.findall(r'\b20\d{2}\b', query))
        retrieved_years = set(re.findall(r'\b20\d{2}\b', retrieved_text))

        if query_years and not (query_years & retrieved_years):
            gaps.append(CoverageGap(
                topic="Temporal mismatch",
                signal=f"Query asks for {query_years} but retrieved docs contain {retrieved_years or 'no years'}",
                severity="high",
            ))

        return gaps

    def _compute_precision(
        self,
        query: str,
        documents: list[str],
        relevance_scores: list[float],
    ) -> float:
        """Compute precision: ratio of relevant docs to total retrieved."""
        if not documents:
            return 1.0

        relevant_count = sum(1 for score in relevance_scores if score >= self.relevance_threshold)
        return relevant_count / len(documents)

    def _compute_query_alignment(
        self,
        query: str,
        documents: list[str],
    ) -> float:
        """Compute overall semantic alignment between query and document set."""
        if not documents:
            return 1.0

        query_words = set(query.lower().split())
        query_words = {w for w in query_words if len(w) > 3}

        if not query_words:
            return 1.0

        all_doc_words = set()
        for doc in documents:
            all_doc_words.update(doc.lower().split())

        overlap = len(query_words & all_doc_words)
        return overlap / len(query_words)

    def _calibrate_confidence(
        self,
        relevance_score: float,
        coverage_score: float,
        precision: float,
        num_irrelevant: int,
        num_gaps: int,
    ) -> tuple[float, dict]:
        """Calibrate confidence based on multiple factors.

        Uses wider spread to better separate true positives from negatives.
        """
        # Count how many quality dimensions are below threshold
        failing_dims = sum([
            relevance_score < self.relevance_threshold,
            precision < self.precision_threshold,
            coverage_score < self.coverage_threshold,
        ])

        if failing_dims >= 2:
            # Multiple quality dimensions failing → high confidence
            base_confidence = 0.70 + min(0.25, num_irrelevant * 0.03 + num_gaps * 0.03)
        elif failing_dims == 1:
            # Single dimension failing → moderate confidence
            base_confidence = 0.50 + min(0.15, (num_irrelevant + num_gaps) * 0.03)
        else:
            # No dimensions clearly failing → low confidence
            base_confidence = 0.25 + min(0.15, num_gaps * 0.03)

        # Apply scaling and cap
        calibrated = min(0.99, base_confidence * self.confidence_scaling)

        calibration_info = {
            "base_confidence": round(base_confidence, 4),
            "failing_dims": failing_dims,
            "relevance_score": round(relevance_score, 4),
            "coverage_score": round(coverage_score, 4),
            "precision": round(precision, 4),
            "irrelevant_count": num_irrelevant,
            "gap_count": num_gaps,
        }

        return round(calibrated, 4), calibration_info

    def _determine_severity(
        self,
        relevance_score: float,
        precision: float,
        coverage_score: float,
        num_gaps: int,
    ) -> RetrievalSeverity:
        """Determine severity based on retrieval metrics."""
        # Critical: Complete retrieval failure
        if relevance_score < 0.2 or precision < 0.2:
            return RetrievalSeverity.CRITICAL

        # Severe: Most docs irrelevant or major coverage gaps
        if relevance_score < 0.4 or precision < 0.4 or num_gaps >= 3:
            return RetrievalSeverity.SEVERE

        # Moderate: Some issues
        if relevance_score < 0.6 or precision < 0.6 or num_gaps >= 1:
            return RetrievalSeverity.MODERATE

        # Minor: Small issues
        if relevance_score < 0.8 or precision < 0.8:
            return RetrievalSeverity.MINOR

        return RetrievalSeverity.NONE

    def detect(
        self,
        query: str,
        retrieved_documents: list[str],
        agent_output: str,
        available_corpus_sample: Optional[list[str]] = None,
        task: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> RetrievalQualityResult:
        """Detect retrieval quality failures.

        Args:
            query: The original query/task
            retrieved_documents: Documents that were retrieved
            agent_output: The agent's output (to check for coverage gaps)
            available_corpus_sample: Optional sample of available docs (for coverage analysis)
            task: Optional task description
            agent_name: Optional agent identifier

        Returns:
            RetrievalQualityResult with detection details
        """
        # Handle edge cases
        if len(query) < self.min_query_length:
            return RetrievalQualityResult(
                detected=False,
                confidence=0.0,
                severity=RetrievalSeverity.NONE,
                relevance_score=1.0,
                coverage_score=1.0,
                precision=1.0,
                query_doc_alignment=1.0,
                irrelevant_docs=[],
                missing_signals=[],
                explanation="Query too short to analyze retrieval quality",
            )

        if not retrieved_documents:
            return RetrievalQualityResult(
                detected=True,
                confidence=0.9,
                severity=RetrievalSeverity.CRITICAL,
                relevance_score=0.0,
                coverage_score=0.0,
                precision=0.0,
                query_doc_alignment=0.0,
                irrelevant_docs=[],
                missing_signals=[CoverageGap(
                    topic="No documents",
                    signal="No documents were retrieved for the query",
                    severity="critical",
                )],
                explanation="No documents retrieved - complete retrieval failure",
                suggested_fix="Review retrieval system configuration and query processing",
            )

        # Extract query topics
        query_topics = self._extract_query_topics(query)

        # Score each document's relevance
        irrelevant_docs = []
        relevance_scores = []

        for i, doc in enumerate(retrieved_documents):
            score, reason = self._score_document_relevance(query, doc, query_topics)
            relevance_scores.append(score)

            if score < self.relevance_threshold:
                irrelevant_docs.append(IrrelevantDocument(
                    doc_id=f"doc_{i}",
                    reason=reason,
                    relevance_score=score,
                ))

        # Calculate average relevance
        relevance_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0

        # Calculate precision
        precision = self._compute_precision(query, retrieved_documents, relevance_scores)

        # Detect coverage gaps
        coverage_gaps = self._detect_coverage_gaps(query, agent_output, retrieved_documents)

        # Estimate coverage score (inverse of gap severity)
        gap_penalty = sum(0.2 if g.severity == "high" else 0.1 for g in coverage_gaps)
        coverage_score = max(0, 1 - gap_penalty)

        # Calculate query-document alignment
        query_doc_alignment = self._compute_query_alignment(query, retrieved_documents)

        # Determine if failure detected
        # v1.1: Require multiple gaps OR high-severity gap (not just any gap)
        high_severity_gaps = [g for g in coverage_gaps if g.severity == "high"]
        has_significant_gaps = len(coverage_gaps) >= 2 or len(high_severity_gaps) > 0
        detected = (
            relevance_score < self.relevance_threshold or
            precision < self.precision_threshold or
            coverage_score < self.coverage_threshold or
            has_significant_gaps
        )

        # Calculate severity
        severity = self._determine_severity(
            relevance_score, precision, coverage_score, len(coverage_gaps)
        )

        # Calibrate confidence
        confidence, calibration_info = self._calibrate_confidence(
            relevance_score,
            coverage_score,
            precision,
            len(irrelevant_docs),
            len(coverage_gaps),
        )

        # Generate explanation
        issues = []
        if irrelevant_docs:
            issues.append(f"{len(irrelevant_docs)}/{len(retrieved_documents)} irrelevant docs")
        if coverage_gaps:
            issues.append(f"{len(coverage_gaps)} coverage gaps")
        if precision < self.precision_threshold:
            issues.append(f"low precision ({precision:.0%})")

        if detected:
            explanation = f"Retrieval quality failure: {', '.join(issues)}. Relevance: {relevance_score:.0%}"
            suggested_fix = "Improve query processing, consider hybrid search, or expand retrieval scope"
        else:
            explanation = f"Retrieval appears adequate. Relevance: {relevance_score:.0%}, Precision: {precision:.0%}"
            suggested_fix = None

        return RetrievalQualityResult(
            detected=detected,
            confidence=confidence,
            severity=severity,
            relevance_score=relevance_score,
            coverage_score=coverage_score,
            precision=precision,
            query_doc_alignment=query_doc_alignment,
            irrelevant_docs=irrelevant_docs[:10],  # Limit for response size
            missing_signals=coverage_gaps[:10],
            explanation=explanation,
            suggested_fix=suggested_fix,
            calibration_info=calibration_info,
            details={
                "total_documents": len(retrieved_documents),
                "query_topics": list(query_topics)[:10],
                "relevance_scores": relevance_scores,
                "agent_name": agent_name,
                "task": task[:200] if task else None,
            },
        )


# Module-level singleton instance
retrieval_quality_detector = RetrievalQualityDetector()
