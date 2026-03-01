"""Fix generators for hallucination detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class HallucinationFixGenerator(BaseFixGenerator):
    """Generates fixes for hallucination detections."""

    def can_handle(self, detection_type: str) -> bool:
        return "hallucination" in detection_type

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._fact_checking_fix(detection_id, details, context))
        fixes.append(self._source_grounding_fix(detection_id, details, context))
        fixes.append(self._confidence_calibration_fix(detection_id, details, context))

        return fixes

    def _fact_checking_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Claim:
    """A factual claim extracted from LLM output."""
    text: str
    category: str  # "numeric", "entity", "temporal", "causal"
    confidence: float = 0.0
    verified: bool = False
    source: Optional[str] = None


@dataclass
class FactCheckResult:
    """Result of fact-checking a single claim."""
    claim: Claim
    is_valid: bool
    evidence: str = ""
    correction: Optional[str] = None


class PostOutputFactValidator:
    """
    Validates factual claims in LLM output before returning to the user.
    Extracts claims, checks them against known sources, and flags
    or corrects hallucinated content.
    """

    def __init__(self, knowledge_base: Optional[Dict[str, Any]] = None):
        self.knowledge_base = knowledge_base or {}
        self._claim_patterns = {
            "numeric": re.compile(r"\\b\\d+[\\.,]?\\d*\\s*(?:%|percent|million|billion|thousand)\\b", re.IGNORECASE),
            "temporal": re.compile(r"\\b(?:in|since|from|during)\\s+\\d{4}\\b", re.IGNORECASE),
            "entity": re.compile(r"(?:according to|as stated by|reported by)\\s+([A-Z][\\w\\s]+)", re.IGNORECASE),
        }
        self._hallucination_count = 0
        self._total_claims_checked = 0

    def extract_claims(self, text: str) -> List[Claim]:
        """Extract verifiable claims from LLM output text."""
        claims = []
        sentences = re.split(r"[.!?]+", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            for category, pattern in self._claim_patterns.items():
                matches = pattern.findall(sentence)
                if matches:
                    claims.append(Claim(
                        text=sentence,
                        category=category,
                    ))
                    break

        return claims

    def verify_claim(self, claim: Claim) -> FactCheckResult:
        """Verify a single claim against the knowledge base."""
        self._total_claims_checked += 1

        # Check against knowledge base entries
        for key, facts in self.knowledge_base.items():
            if key.lower() in claim.text.lower():
                for fact in facts if isinstance(facts, list) else [facts]:
                    if self._contradicts(claim.text, str(fact)):
                        self._hallucination_count += 1
                        return FactCheckResult(
                            claim=claim,
                            is_valid=False,
                            evidence=f"Knowledge base entry '{key}' contradicts claim",
                            correction=str(fact),
                        )
                claim.verified = True
                return FactCheckResult(claim=claim, is_valid=True, evidence=f"Matches '{key}'")

        # No evidence found -- flag as unverified
        return FactCheckResult(
            claim=claim,
            is_valid=True,
            evidence="No contradicting evidence found (unverified)",
        )

    def validate_output(self, llm_output: str) -> Dict[str, Any]:
        """Full validation pipeline for an LLM output string."""
        claims = self.extract_claims(llm_output)
        results = [self.verify_claim(c) for c in claims]

        invalid = [r for r in results if not r.is_valid]
        corrected_output = llm_output
        for r in invalid:
            if r.correction:
                corrected_output = corrected_output.replace(
                    r.claim.text, f"[CORRECTED] {r.correction}"
                )

        return {
            "original": llm_output,
            "corrected": corrected_output,
            "total_claims": len(claims),
            "invalid_claims": len(invalid),
            "hallucination_rate": len(invalid) / max(len(claims), 1),
            "details": [
                {"claim": r.claim.text, "valid": r.is_valid, "evidence": r.evidence}
                for r in results
            ],
        }

    def _contradicts(self, claim_text: str, fact: str) -> bool:
        """Check if a claim contradicts a known fact."""
        claim_numbers = re.findall(r"\\d+\\.?\\d*", claim_text)
        fact_numbers = re.findall(r"\\d+\\.?\\d*", fact)
        if claim_numbers and fact_numbers:
            return claim_numbers[0] != fact_numbers[0]
        return False

    @property
    def hallucination_rate(self) -> float:
        if self._total_claims_checked == 0:
            return 0.0
        return self._hallucination_count / self._total_claims_checked'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="hallucination",
            fix_type=FixType.FACT_CHECKING,
            confidence=FixConfidence.HIGH,
            title="Add post-output fact validator to catch hallucinations",
            description="Insert a fact-checking layer after LLM output that extracts verifiable claims and validates them against a knowledge base before returning results.",
            rationale="Hallucinations often contain plausible-sounding but incorrect factual claims. A post-output validator catches these by cross-referencing extracted claims against known facts, reducing the risk of propagating false information.",
            code_changes=[
                CodeChange(
                    file_path="utils/fact_validator.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Post-output fact validation pipeline with claim extraction and verification",
                )
            ],
            estimated_impact="Catches factual hallucinations before they reach downstream agents or users",
            tags=["hallucination", "fact-checking", "validation"],
        )

    def _source_grounding_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import re


@dataclass
class SourceReference:
    """A reference to a grounding source."""
    source_id: str
    title: str
    content: str
    relevance_score: float = 0.0


@dataclass
class GroundedResponse:
    """An LLM response with source citations attached."""
    text: str
    citations: List[Dict[str, str]] = field(default_factory=list)
    grounding_score: float = 0.0
    ungrounded_segments: List[str] = field(default_factory=list)


class SourceGroundingEnforcer:
    """
    Enforces that LLM outputs are grounded in provided source documents.
    Requires the model to cite sources for factual claims and flags
    unsupported statements.
    """

    GROUNDING_SYSTEM_PROMPT = (
        "You MUST cite sources for every factual claim you make. "
        "Use the format [Source: <id>] after each claim. "
        "If you cannot find a source for a claim, prefix it with [UNSOURCED]. "
        "Do NOT generate facts that are not supported by the provided documents."
    )

    def __init__(self, sources: Optional[List[SourceReference]] = None):
        self.sources = sources or []
        self._source_index: Dict[str, SourceReference] = {
            s.source_id: s for s in self.sources
        }

    def add_source(self, source: SourceReference) -> None:
        """Register a source document for grounding."""
        self.sources.append(source)
        self._source_index[source.source_id] = source

    def build_grounded_prompt(self, user_query: str) -> str:
        """Build a prompt that includes source context and grounding instructions."""
        source_block = "\\n\\n".join(
            f"[Source {s.source_id}]: {s.title}\\n{s.content}"
            for s in self.sources
        )

        return (
            f"{self.GROUNDING_SYSTEM_PROMPT}\\n\\n"
            f"--- Available Sources ---\\n{source_block}\\n\\n"
            f"--- User Query ---\\n{user_query}"
        )

    def validate_grounding(self, response_text: str) -> GroundedResponse:
        """Validate that the response properly cites sources."""
        citation_pattern = re.compile(r"\\[Source:\\s*(\\w+)\\]")
        unsourced_pattern = re.compile(r"\\[UNSOURCED\\]")

        citations = []
        found_ids = citation_pattern.findall(response_text)
        for src_id in found_ids:
            source = self._source_index.get(src_id)
            if source:
                citations.append({
                    "source_id": src_id,
                    "title": source.title,
                })

        # Find unsourced segments
        sentences = re.split(r"(?<=[.!?])\\s+", response_text)
        ungrounded = []
        for sentence in sentences:
            has_citation = citation_pattern.search(sentence)
            is_marked_unsourced = unsourced_pattern.search(sentence)
            is_factual = self._looks_factual(sentence)

            if is_factual and not has_citation and not is_marked_unsourced:
                ungrounded.append(sentence)

        total_factual = sum(1 for s in sentences if self._looks_factual(s))
        grounded_count = total_factual - len(ungrounded)
        grounding_score = grounded_count / max(total_factual, 1)

        return GroundedResponse(
            text=response_text,
            citations=citations,
            grounding_score=grounding_score,
            ungrounded_segments=ungrounded,
        )

    def enforce(self, response_text: str, min_grounding: float = 0.8) -> Dict[str, Any]:
        """Enforce minimum grounding score, rejecting poorly grounded responses."""
        result = self.validate_grounding(response_text)

        return {
            "accepted": result.grounding_score >= min_grounding,
            "grounding_score": result.grounding_score,
            "citations": result.citations,
            "ungrounded_segments": result.ungrounded_segments,
            "response": result.text,
        }

    def _looks_factual(self, sentence: str) -> bool:
        """Heuristic: does this sentence contain a factual claim?"""
        factual_indicators = [
            r"\\b\\d+",                    # numbers
            r"\\b(?:is|are|was|were)\\b",  # assertions
            r"\\baccording to\\b",         # attributions
            r"\\b(?:always|never)\\b",     # absolutes
        ]
        return any(re.search(p, sentence, re.IGNORECASE) for p in factual_indicators)'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="hallucination",
            fix_type=FixType.SOURCE_GROUNDING,
            confidence=FixConfidence.HIGH,
            title="Require source citations in LLM responses",
            description="Force the LLM to ground every factual claim in a provided source document, and flag or reject responses that contain unsupported statements.",
            rationale="Hallucinations arise when the model generates facts from its parametric memory rather than from provided context. Requiring explicit citations forces grounded generation and makes unsupported claims visible.",
            code_changes=[
                CodeChange(
                    file_path="utils/source_grounding.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Source grounding enforcer with citation validation and minimum grounding thresholds",
                )
            ],
            estimated_impact="Reduces hallucination by anchoring responses to verified source documents",
            tags=["hallucination", "grounding", "citations", "rag"],
        )

    def _confidence_calibration_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import math


@dataclass
class CalibratedClaim:
    """A claim with a calibrated confidence score."""
    text: str
    raw_confidence: float
    calibrated_confidence: float
    bucket: str  # "high", "medium", "low", "uncertain"


class ConfidenceCalibrator:
    """
    Calibrates confidence scores on LLM-generated claims.
    Uses historical accuracy data to map raw model confidence
    to calibrated probabilities, preventing overconfident hallucinations.
    """

    CONFIDENCE_PROMPT = (
        "For each factual claim in your response, rate your confidence "
        "on a scale of 0.0 to 1.0. Format: [confidence: X.X] after each claim. "
        "Be honest -- say [confidence: 0.3] if you are unsure."
    )

    # Bucket thresholds
    BUCKETS = {
        "high": (0.8, 1.0),
        "medium": (0.5, 0.8),
        "low": (0.2, 0.5),
        "uncertain": (0.0, 0.2),
    }

    def __init__(self):
        # Historical calibration data: raw_confidence -> actual_accuracy
        self._calibration_history: List[Tuple[float, bool]] = []
        self._calibration_curve: Dict[str, float] = {
            "high": 0.75,     # Models claiming 0.9 are right ~75% of the time
            "medium": 0.55,
            "low": 0.30,
            "uncertain": 0.15,
        }

    def record_outcome(self, raw_confidence: float, was_correct: bool) -> None:
        """Record a prediction outcome for calibration curve updates."""
        self._calibration_history.append((raw_confidence, was_correct))
        if len(self._calibration_history) % 50 == 0:
            self._update_calibration_curve()

    def calibrate(self, raw_confidence: float) -> float:
        """Map raw model confidence to calibrated confidence."""
        bucket = self._get_bucket(raw_confidence)
        calibrated = self._calibration_curve.get(bucket, raw_confidence)

        # Apply Platt scaling within bucket
        midpoint = sum(self.BUCKETS[bucket]) / 2
        deviation = raw_confidence - midpoint
        adjusted = calibrated + (deviation * 0.1)

        return max(0.0, min(1.0, adjusted))

    def evaluate_response(self, claims_with_confidence: List[Tuple[str, float]]) -> List[CalibratedClaim]:
        """Evaluate a list of (claim_text, raw_confidence) pairs."""
        results = []
        for text, raw_conf in claims_with_confidence:
            calibrated = self.calibrate(raw_conf)
            bucket = self._get_bucket(calibrated)
            results.append(CalibratedClaim(
                text=text,
                raw_confidence=raw_conf,
                calibrated_confidence=calibrated,
                bucket=bucket,
            ))
        return results

    def flag_overconfident(
        self,
        claims: List[CalibratedClaim],
        threshold: float = 0.3,
    ) -> List[CalibratedClaim]:
        """Flag claims where raw confidence greatly exceeds calibrated confidence."""
        return [
            c for c in claims
            if (c.raw_confidence - c.calibrated_confidence) > threshold
        ]

    def apply_to_output(self, claims: List[CalibratedClaim]) -> Dict[str, Any]:
        """Generate a summary report for calibrated claims."""
        overconfident = self.flag_overconfident(claims)
        avg_calibrated = sum(c.calibrated_confidence for c in claims) / max(len(claims), 1)

        return {
            "total_claims": len(claims),
            "average_calibrated_confidence": round(avg_calibrated, 3),
            "overconfident_claims": [
                {"text": c.text, "raw": c.raw_confidence, "calibrated": c.calibrated_confidence}
                for c in overconfident
            ],
            "bucket_distribution": self._bucket_distribution(claims),
            "recommendation": "review" if len(overconfident) > 0 else "accept",
        }

    def _get_bucket(self, confidence: float) -> str:
        for name, (low, high) in self.BUCKETS.items():
            if low <= confidence <= high:
                return name
        return "uncertain"

    def _bucket_distribution(self, claims: List[CalibratedClaim]) -> Dict[str, int]:
        dist = {b: 0 for b in self.BUCKETS}
        for c in claims:
            dist[c.bucket] = dist.get(c.bucket, 0) + 1
        return dist

    def _update_calibration_curve(self) -> None:
        """Recompute calibration curve from historical outcomes."""
        bucket_outcomes: Dict[str, List[bool]] = {b: [] for b in self.BUCKETS}
        for raw_conf, correct in self._calibration_history:
            bucket = self._get_bucket(raw_conf)
            bucket_outcomes[bucket].append(correct)

        for bucket, outcomes in bucket_outcomes.items():
            if outcomes:
                self._calibration_curve[bucket] = sum(outcomes) / len(outcomes)'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="hallucination",
            fix_type=FixType.CONFIDENCE_CALIBRATION,
            confidence=FixConfidence.MEDIUM,
            title="Calibrate confidence scores on LLM claims",
            description="Add a confidence calibration layer that maps raw model confidence to empirically calibrated probabilities, flagging overconfident claims that are likely hallucinations.",
            rationale="LLMs are notoriously overconfident in their outputs. By tracking historical accuracy per confidence bucket and applying calibration, we can identify claims where the model is unjustifiably certain -- a strong hallucination signal.",
            code_changes=[
                CodeChange(
                    file_path="utils/confidence_calibrator.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Confidence calibration system with Platt scaling and historical accuracy tracking",
                )
            ],
            estimated_impact="Surfaces overconfident hallucinations by revealing calibration gaps",
            tags=["hallucination", "confidence", "calibration", "reliability"],
        )
