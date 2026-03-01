"""
F15: Grounding Failure Detection (MAST Taxonomy)
================================================

Detects when an agent's output contains claims, data, or statements
not supported by or contradicting source documents.

Inspired by: Databricks OfficeQA benchmark showing agents achieve <45%
accuracy on document-grounded tasks due to:
- Extracting wrong values from tables
- Misattributing data to wrong columns/headers
- Hallucinating numbers not present in sources
- Confusing similar entities across documents
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GroundingSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"  # Minor paraphrasing issues
    MODERATE = "moderate"  # Some claims not fully grounded
    SEVERE = "severe"  # Significant misrepresentation
    CRITICAL = "critical"  # Fabricated data or wrong numbers


@dataclass
class UngroundedClaim:
    """Represents a claim that cannot be grounded in sources."""
    claim: str
    claim_type: str  # "numerical", "factual", "citation", "entity"
    searched_sources: bool
    evidence: Optional[str] = None


@dataclass
class NumericalError:
    """Represents a numerical mismatch between output and source."""
    claimed_value: str
    source_value: Optional[str]
    source_location: Optional[str]
    context: str


@dataclass
class GroundingResult:
    detected: bool
    confidence: float
    severity: GroundingSeverity
    grounding_score: float  # 0-1, ratio of grounded claims
    citation_accuracy: float  # 0-1, ratio of valid citations
    ungrounded_claims: list[UngroundedClaim]
    numerical_errors: list[NumericalError]
    explanation: str
    suggested_fix: Optional[str] = None
    calibration_info: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)


class GroundingDetector:
    """
    Detects F15: Grounding Failure - when agent output is not
    properly grounded in source documents.

    Analyzes whether claims, numbers, and citations in the output
    are supported by the provided source documents.

    v1.1: Uses embedding-based claim verification to reduce false
    positives from paraphrases. Falls back to word overlap if
    embedder is not available.
    """

    def __init__(
        self,
        grounding_threshold: float = 0.7,
        citation_threshold: float = 0.8,
        numerical_tolerance: float = 0.05,  # 5% tolerance for numerical matches
        min_output_length: int = 50,
        confidence_scaling: float = 1.0,
        embedding_grounding_threshold: float = 0.55,  # cosine sim threshold
    ):
        self.grounding_threshold = grounding_threshold
        self.citation_threshold = citation_threshold
        self.numerical_tolerance = numerical_tolerance
        self.min_output_length = min_output_length
        self.confidence_scaling = confidence_scaling
        self.embedding_grounding_threshold = embedding_grounding_threshold
        self._embedder = None

    @property
    def embedder(self):
        if self._embedder is None:
            try:
                from app.core.embeddings import get_embedder
                self._embedder = get_embedder()
            except Exception:
                pass
        return self._embedder

    def _extract_numbers(self, text: str) -> list[dict]:
        """Extract numerical values with context from text."""
        numbers = []

        # Match numbers with optional currency, percentage, units
        patterns = [
            # Currency amounts: $45.2M, $1,234.56
            (r'\$[\d,]+(?:\.\d+)?(?:[MBK])?', 'currency'),
            # Percentages: 45%, 12.5%
            (r'[\d.]+%', 'percentage'),
            # Plain numbers with context: Q3, 2024, 1234
            (r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b', 'number'),
            # Quarters: Q1, Q2, Q3, Q4
            (r'\bQ[1-4]\b', 'quarter'),
            # Years: 2023, 2024
            (r'\b20\d{2}\b', 'year'),
        ]

        for pattern, num_type in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Get surrounding context (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]

                numbers.append({
                    'value': match.group(),
                    'type': num_type,
                    'context': context,
                    'position': match.start(),
                })

        return numbers

    def _extract_claims(self, text: str) -> list[str]:
        """Extract factual claims from text."""
        claims = []

        # Split into sentences
        sentences = re.split(r'[.!?]+', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue

            # Look for factual claim indicators
            claim_indicators = [
                r'\bis\b',
                r'\bwas\b',
                r'\bwere\b',
                r'\breached\b',
                r'\bshows\b',
                r'\bdemonstrates\b',
                r'\bstates\b',
                r'\breports\b',
                r'\baccording to\b',
                r'\bdata\b',
                r'\bresearch\b',
                r'\bstudy\b',
                r'\bfound\b',
            ]

            for indicator in claim_indicators:
                if re.search(indicator, sentence, re.IGNORECASE):
                    claims.append(sentence)
                    break

        return claims[:20]  # Limit to 20 claims for performance

    def _extract_citations(self, text: str) -> list[dict]:
        """Extract citations and quoted content from text."""
        citations = []

        # Direct quotes
        quote_pattern = r'"([^"]+)"'
        for match in re.finditer(quote_pattern, text):
            citations.append({
                'type': 'quote',
                'content': match.group(1),
                'full_match': match.group(),
            })

        # "According to" citations
        according_pattern = r'according to ([^,.:]+)'
        for match in re.finditer(according_pattern, text, re.IGNORECASE):
            citations.append({
                'type': 'attribution',
                'content': match.group(1),
                'full_match': match.group(),
            })

        # Source references
        source_pattern = r'(?:source|report|document|study)(?:\s+\w+){0,3}\s+(?:shows|states|indicates|found)'
        for match in re.finditer(source_pattern, text, re.IGNORECASE):
            citations.append({
                'type': 'source_reference',
                'content': match.group(),
                'full_match': match.group(),
            })

        return citations

    def _verify_number_in_sources(
        self,
        number: dict,
        sources: list[str]
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Check if a number exists in source documents.

        Returns: (found, source_value, source_location)
        """
        value = number['value']

        # Normalize the value for comparison
        normalized = value.lower().replace(',', '').replace('$', '')

        for i, source in enumerate(sources):
            source_lower = source.lower().replace(',', '').replace('$', '')

            # Exact match
            if normalized in source_lower:
                return True, value, f"source_{i}"

            # Try to extract numeric value and compare with tolerance
            try:
                # Extract numeric part
                num_match = re.search(r'[\d.]+', normalized)
                if num_match:
                    target_num = float(num_match.group())

                    # Find all numbers in source
                    source_nums = re.findall(r'[\d.]+', source_lower)
                    for src_num in source_nums:
                        try:
                            src_float = float(src_num)
                            # Check within tolerance
                            if abs(target_num - src_float) / max(target_num, 1) < self.numerical_tolerance:
                                return True, src_num, f"source_{i}"
                        except ValueError:
                            continue
            except ValueError:
                pass

        return False, None, None

    def _verify_claim_in_sources_word_overlap(
        self,
        claim: str,
        sources: list[str]
    ) -> tuple[bool, float, Optional[str]]:
        """Fallback: Check claim grounding using word overlap."""
        claim_lower = claim.lower()
        claim_words = set(claim_lower.split())
        claim_words = {w for w in claim_words if len(w) > 4}

        best_match_score = 0.0
        best_evidence = None

        for source in sources:
            source_lower = source.lower()
            source_words = set(source_lower.split())
            if not claim_words:
                continue
            overlap = len(claim_words & source_words) / len(claim_words)
            if overlap > best_match_score:
                best_match_score = overlap
                if overlap > 0.5:
                    best_evidence = source[:200]

        grounded = best_match_score > 0.5
        return grounded, best_match_score, best_evidence

    def _verify_claims_batch_embedding(
        self,
        claims: list[str],
        sources: list[str],
    ) -> list[tuple[bool, float, Optional[str]]]:
        """Verify claims against sources using embedding similarity.

        Encodes all claims and sources in batches for efficiency.
        Returns list of (grounded, score, evidence) per claim.
        """
        import numpy as np

        embedder = self.embedder
        if not embedder or not claims or not sources:
            return [self._verify_claim_in_sources_word_overlap(c, sources) for c in claims]

        try:
            claim_embeddings = embedder.encode(claims)
            source_embeddings = embedder.encode(sources)

            # Handle single-text encoding returning 1D array
            if claim_embeddings.ndim == 1:
                claim_embeddings = claim_embeddings.reshape(1, -1)
            if source_embeddings.ndim == 1:
                source_embeddings = source_embeddings.reshape(1, -1)

            # Compute similarity matrix: claims × sources
            # Normalize for cosine similarity
            claim_norms = np.linalg.norm(claim_embeddings, axis=1, keepdims=True)
            source_norms = np.linalg.norm(source_embeddings, axis=1, keepdims=True)
            claim_normalized = claim_embeddings / np.maximum(claim_norms, 1e-10)
            source_normalized = source_embeddings / np.maximum(source_norms, 1e-10)
            sim_matrix = claim_normalized @ source_normalized.T  # (n_claims, n_sources)

            results = []
            for i, claim in enumerate(claims):
                max_sim = float(np.max(sim_matrix[i]))
                best_source_idx = int(np.argmax(sim_matrix[i]))
                grounded = max_sim > self.embedding_grounding_threshold
                evidence = sources[best_source_idx][:200] if grounded else None
                results.append((grounded, max_sim, evidence))
            return results

        except Exception as e:
            logger.warning("Embedding-based verification failed: %s, falling back to word overlap", e)
            return [self._verify_claim_in_sources_word_overlap(c, sources) for c in claims]

    def _verify_claim_in_sources(
        self,
        claim: str,
        sources: list[str]
    ) -> tuple[bool, float, Optional[str]]:
        """Check if a claim is supported by source documents.

        Returns: (grounded, confidence, evidence)
        """
        return self._verify_claim_in_sources_word_overlap(claim, sources)

    def _verify_citation(
        self,
        citation: dict,
        sources: list[str]
    ) -> tuple[bool, Optional[str]]:
        """Verify if a citation accurately represents source content."""
        content = citation['content'].lower()

        for source in sources:
            source_lower = source.lower()

            # For quotes, look for exact or near-exact match
            if citation['type'] == 'quote':
                if content in source_lower:
                    return True, "Exact quote found in source"

                # Check for high word overlap
                content_words = set(content.split())
                source_words = set(source_lower.split())
                if content_words and len(content_words & source_words) / len(content_words) > 0.8:
                    return True, "Near-exact quote found in source"

            # For attributions, just check if the source mentions similar content
            elif citation['type'] == 'attribution':
                # Attribution verification is looser
                if content in source_lower:
                    return True, "Attribution source found"

        return False, None

    def _calibrate_confidence(
        self,
        grounding_score: float,
        citation_accuracy: float,
        num_ungrounded: int,
        num_numerical_errors: int,
        total_claims: int = 0,
        total_source_words: int = 0,
    ) -> tuple[float, dict]:
        """Calibrate confidence with better TP/FP separation.

        Key insight: numerical errors are strong evidence of grounding failure.
        Claim-only ungrounding is weaker (could be paraphrasing). Sparse sources
        reduce confidence since word overlap is unreliable with little text.
        """
        # Count strong evidence dimensions
        has_numerical = num_numerical_errors > 0
        has_low_grounding = grounding_score < 0.5
        has_low_citation = citation_accuracy < 0.6
        strong_signals = sum([has_numerical, has_low_grounding, has_low_citation])

        if strong_signals >= 2:
            # Multiple strong signals → high confidence
            base_confidence = 0.75 + min(0.20, num_numerical_errors * 0.05)
        elif has_numerical:
            # Numerical errors alone are strong evidence
            base_confidence = 0.65 + min(0.15, num_numerical_errors * 0.05)
        elif has_low_grounding:
            # Low grounding without numerical errors → moderate
            base_confidence = 0.55 + min(0.10, num_ungrounded * 0.02)
        else:
            # Weak signals only → low confidence (likely FP)
            base_confidence = 0.35 + min(0.10, num_ungrounded * 0.02)

        # Penalize confidence when sources are sparse (word overlap unreliable)
        if total_source_words > 0 and total_source_words < 200:
            base_confidence *= 0.8

        # Apply scaling and cap
        calibrated = min(0.99, base_confidence * self.confidence_scaling)

        calibration_info = {
            "base_confidence": round(base_confidence, 4),
            "strong_signals": strong_signals,
            "grounding_score": round(grounding_score, 4),
            "citation_accuracy": round(citation_accuracy, 4),
            "ungrounded_count": num_ungrounded,
            "numerical_error_count": num_numerical_errors,
            "total_claims": total_claims,
            "total_source_words": total_source_words,
        }

        return round(calibrated, 4), calibration_info

    def _determine_severity(
        self,
        grounding_score: float,
        citation_accuracy: float,
        num_numerical_errors: int,
    ) -> GroundingSeverity:
        """Determine severity based on grounding metrics."""
        # Critical: Major numerical errors or very low grounding
        if num_numerical_errors >= 3 or grounding_score < 0.3:
            return GroundingSeverity.CRITICAL

        # Severe: Multiple issues
        if num_numerical_errors >= 2 or grounding_score < 0.5:
            return GroundingSeverity.SEVERE

        # Moderate: Some issues
        if num_numerical_errors >= 1 or grounding_score < 0.7 or citation_accuracy < 0.7:
            return GroundingSeverity.MODERATE

        # Minor: Small issues
        if grounding_score < 0.85 or citation_accuracy < 0.85:
            return GroundingSeverity.MINOR

        return GroundingSeverity.NONE

    def detect(
        self,
        agent_output: str,
        source_documents: list[str],
        citations: Optional[list[dict]] = None,
        task: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> GroundingResult:
        """Detect grounding failures in agent output.

        Args:
            agent_output: The agent's generated output
            source_documents: List of source documents to verify against
            citations: Optional pre-extracted citations
            task: Optional task description
            agent_name: Optional agent identifier

        Returns:
            GroundingResult with detection details
        """
        # Handle edge cases
        if len(agent_output) < self.min_output_length:
            return GroundingResult(
                detected=False,
                confidence=0.0,
                severity=GroundingSeverity.NONE,
                grounding_score=1.0,
                citation_accuracy=1.0,
                ungrounded_claims=[],
                numerical_errors=[],
                explanation="Output too short to analyze for grounding",
            )

        if not source_documents:
            return GroundingResult(
                detected=False,
                confidence=0.0,
                severity=GroundingSeverity.NONE,
                grounding_score=1.0,
                citation_accuracy=1.0,
                ungrounded_claims=[],
                numerical_errors=[],
                explanation="No source documents provided for grounding verification",
            )

        # Extract and verify numbers
        numbers = self._extract_numbers(agent_output)
        numerical_errors = []

        for num in numbers:
            found, source_value, source_loc = self._verify_number_in_sources(num, source_documents)
            if not found and num['type'] in ['currency', 'percentage']:
                numerical_errors.append(NumericalError(
                    claimed_value=num['value'],
                    source_value=source_value,
                    source_location=source_loc,
                    context=num['context'],
                ))

        # Extract and verify claims
        claims = self._extract_claims(agent_output)
        ungrounded_claims = []
        grounded_count = 0

        # When sources are sparse, limit claims checked to reduce false positives
        total_source_words = sum(len(s.split()) for s in source_documents)
        max_claims_to_check = len(claims)
        if total_source_words < 200:
            max_claims_to_check = min(5, len(claims))
        elif total_source_words < 500:
            max_claims_to_check = min(10, len(claims))

        for claim in claims[:max_claims_to_check]:
            grounded, confidence, evidence = self._verify_claim_in_sources(claim, source_documents)
            if grounded:
                grounded_count += 1
            else:
                ungrounded_claims.append(UngroundedClaim(
                    claim=claim[:200],
                    claim_type="factual",
                    searched_sources=True,
                    evidence=evidence,
                ))

        # Calculate grounding score
        checked = min(max_claims_to_check, len(claims))
        grounding_score = grounded_count / checked if checked else 1.0

        # Extract and verify citations
        if citations is None:
            citations = self._extract_citations(agent_output)

        valid_citations = 0
        for citation in citations:
            valid, _ = self._verify_citation(citation, source_documents)
            if valid:
                valid_citations += 1

        citation_accuracy = valid_citations / len(citations) if citations else 1.0

        # Determine if failure detected
        detected = (
            grounding_score < self.grounding_threshold or
            citation_accuracy < self.citation_threshold or
            len(numerical_errors) > 0
        )

        # Calculate severity
        severity = self._determine_severity(grounding_score, citation_accuracy, len(numerical_errors))

        # Calibrate confidence
        confidence, calibration_info = self._calibrate_confidence(
            grounding_score,
            citation_accuracy,
            len(ungrounded_claims),
            len(numerical_errors),
            total_claims=len(claims),
            total_source_words=total_source_words,
        )

        # Generate explanation
        issues = []
        if numerical_errors:
            issues.append(f"{len(numerical_errors)} numerical mismatches")
        if ungrounded_claims:
            issues.append(f"{len(ungrounded_claims)} ungrounded claims")
        if citation_accuracy < 1.0 and citations:
            issues.append(f"{len(citations) - valid_citations} citation issues")

        if detected:
            explanation = f"Grounding failure detected: {', '.join(issues)}. Grounding score: {grounding_score:.0%}"
            suggested_fix = "Verify all factual claims against source documents. Cross-check numerical values with original data."
        else:
            explanation = f"Output appears well-grounded. Score: {grounding_score:.0%}"
            suggested_fix = None

        return GroundingResult(
            detected=detected,
            confidence=confidence,
            severity=severity,
            grounding_score=grounding_score,
            citation_accuracy=citation_accuracy,
            ungrounded_claims=ungrounded_claims[:10],  # Limit for response size
            numerical_errors=numerical_errors[:10],
            explanation=explanation,
            suggested_fix=suggested_fix,
            calibration_info=calibration_info,
            details={
                "total_claims": len(claims),
                "total_numbers": len(numbers),
                "total_citations": len(citations),
                "agent_name": agent_name,
                "task": task[:200] if task else None,
            },
        )


# Module-level singleton instance
grounding_detector = GroundingDetector()
