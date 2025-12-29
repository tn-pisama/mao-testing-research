"""
F1: Specification Mismatch Detection (MAST Taxonomy)
====================================================

Detects when a task specification doesn't match the user's original intent.
This occurs at the system design level when:
- The task decomposition loses critical requirements
- The specification is ambiguous or incomplete
- The task scope drifts from original intent
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re

logger = logging.getLogger(__name__)


class MismatchSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class MismatchType(str, Enum):
    SCOPE_DRIFT = "scope_drift"
    MISSING_REQUIREMENT = "missing_requirement"
    AMBIGUOUS_SPEC = "ambiguous_spec"
    CONFLICTING_SPEC = "conflicting_spec"
    OVERSPECIFIED = "overspecified"


@dataclass
class SpecificationMismatchResult:
    detected: bool
    mismatch_type: Optional[MismatchType]
    severity: MismatchSeverity
    confidence: float
    requirement_coverage: float
    missing_requirements: list[str]
    ambiguous_elements: list[str]
    explanation: str
    suggested_fix: Optional[str] = None


class SpecificationMismatchDetector:
    """
    Detects F1: Specification Mismatch - task doesn't match user intent.
    
    Compares user intent with task specification to identify
    gaps, ambiguities, and scope drift.
    """
    
    def __init__(
        self,
        coverage_threshold: float = 0.7,
        ambiguity_threshold: int = 3,
    ):
        self.coverage_threshold = coverage_threshold
        self.ambiguity_threshold = ambiguity_threshold

    def _extract_requirements(self, text: str) -> list[str]:
        requirements = []
        
        must_patterns = [
            r'must\s+([^.!?]+)',
            r'should\s+([^.!?]+)',
            r'need(?:s)?\s+to\s+([^.!?]+)',
            r'require(?:s|d)?\s+([^.!?]+)',
            r'has\s+to\s+([^.!?]+)',
            r'ensure\s+(?:that\s+)?([^.!?]+)',
        ]
        
        for pattern in must_patterns:
            matches = re.findall(pattern, text.lower())
            requirements.extend(matches)
        
        action_patterns = [
            r'(?:create|build|make|generate)\s+(?:a\s+)?([^.!?,]+)',
            r'(?:find|search|get|fetch)\s+([^.!?,]+)',
            r'(?:analyze|evaluate|assess)\s+([^.!?,]+)',
            r'(?:send|deliver|transmit)\s+([^.!?,]+)',
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, text.lower())
            requirements.extend(matches)
        
        return [r.strip() for r in requirements if len(r.strip()) > 3]

    def _extract_constraints(self, text: str) -> list[str]:
        constraints = []
        
        constraint_patterns = [
            r'(?:no|not|never|without)\s+([^.!?,]+)',
            r'(?:only|exclusively)\s+([^.!?,]+)',
            r'(?:at\s+(?:most|least))\s+([^.!?,]+)',
            r'(?:within|under|below|above)\s+(\d+[^.!?,]*)',
            r'(?:before|after|by)\s+([^.!?,]+)',
            r'(?:limit(?:ed)?\s+to)\s+([^.!?,]+)',
        ]
        
        for pattern in constraint_patterns:
            matches = re.findall(pattern, text.lower())
            constraints.extend(matches)
        
        return [c.strip() for c in constraints if len(c.strip()) > 3]

    def _detect_ambiguities(self, text: str) -> list[str]:
        ambiguities = []
        
        vague_patterns = [
            (r'\b(some|several|many|few|various)\s+\w+', "vague quantity"),
            (r'\b(soon|later|eventually|sometime)\b', "vague timing"),
            (r'\b(good|better|best|nice|appropriate)\b', "subjective quality"),
            (r'\b(etc|and so on|and more|among others)\b', "incomplete list"),
            (r'\b(it|this|that)\b(?!\s+(?:is|are|was|will))', "ambiguous reference"),
            (r'\b(usually|typically|generally|normally)\b', "uncertain qualifier"),
            (r'\b(might|may|could|possibly|perhaps)\b', "uncertain action"),
            (r'\b(simple|easy|quick|basic)\b', "undefined complexity"),
        ]
        
        for pattern, issue_type in vague_patterns:
            if re.search(pattern, text.lower()):
                ambiguities.append(issue_type)
        
        return ambiguities

    def _compute_coverage(
        self,
        intent_requirements: list[str],
        spec_text: str,
    ) -> tuple[float, list[str]]:
        if not intent_requirements:
            return 1.0, []
        
        spec_lower = spec_text.lower()
        covered = 0
        missing = []
        
        for req in intent_requirements:
            req_words = set(req.lower().split())
            req_words = {w for w in req_words if len(w) > 3}
            
            if not req_words:
                covered += 1
                continue
            
            overlap = sum(1 for w in req_words if w in spec_lower)
            coverage_ratio = overlap / len(req_words)
            
            if coverage_ratio >= 0.5:
                covered += 1
            else:
                missing.append(req)
        
        return covered / len(intent_requirements), missing

    def detect(
        self,
        user_intent: str,
        task_specification: str,
        original_request: Optional[str] = None,
    ) -> SpecificationMismatchResult:
        intent_requirements = self._extract_requirements(user_intent)
        intent_constraints = self._extract_constraints(user_intent)
        all_requirements = intent_requirements + intent_constraints
        
        coverage, missing = self._compute_coverage(all_requirements, task_specification)
        
        ambiguities = self._detect_ambiguities(task_specification)
        
        mismatch_type = None
        detected = False
        
        if coverage < self.coverage_threshold:
            detected = True
            mismatch_type = MismatchType.MISSING_REQUIREMENT
        elif len(ambiguities) >= self.ambiguity_threshold:
            detected = True
            mismatch_type = MismatchType.AMBIGUOUS_SPEC
        
        if original_request and user_intent != original_request:
            orig_reqs = self._extract_requirements(original_request)
            orig_coverage, orig_missing = self._compute_coverage(orig_reqs, task_specification)
            if orig_coverage < coverage - 0.2:
                detected = True
                mismatch_type = MismatchType.SCOPE_DRIFT
                missing.extend(orig_missing)

        if not detected:
            return SpecificationMismatchResult(
                detected=False,
                mismatch_type=None,
                severity=MismatchSeverity.NONE,
                confidence=coverage,
                requirement_coverage=coverage,
                missing_requirements=[],
                ambiguous_elements=[],
                explanation="Specification matches user intent",
            )

        if coverage < 0.3:
            severity = MismatchSeverity.SEVERE
        elif coverage < 0.5:
            severity = MismatchSeverity.MODERATE
        else:
            severity = MismatchSeverity.MINOR

        confidence = 1 - coverage

        if mismatch_type == MismatchType.MISSING_REQUIREMENT:
            explanation = (
                f"Task specification missing {len(missing)} requirements from user intent. "
                f"Coverage: {coverage:.1%}"
            )
            fix = f"Add missing requirements to specification: {', '.join(missing[:3])}"
        elif mismatch_type == MismatchType.AMBIGUOUS_SPEC:
            explanation = (
                f"Task specification contains {len(ambiguities)} ambiguous elements: "
                f"{', '.join(ambiguities[:5])}"
            )
            fix = "Replace vague language with specific, measurable criteria"
        else:
            explanation = "Task specification has drifted from original user request"
            fix = "Re-align specification with original user intent"

        return SpecificationMismatchResult(
            detected=True,
            mismatch_type=mismatch_type,
            severity=severity,
            confidence=confidence,
            requirement_coverage=coverage,
            missing_requirements=missing[:10],
            ambiguous_elements=ambiguities,
            explanation=explanation,
            suggested_fix=fix,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> list[SpecificationMismatchResult]:
        results = []
        
        root_input = trace.get("input", {}).get("user_request", "")
        if not root_input:
            return results
        
        spans = trace.get("spans", [])
        for span in spans:
            task_spec = span.get("input", {}).get("task", "")
            if task_spec and len(task_spec) > 20:
                result = self.detect(
                    user_intent=root_input,
                    task_specification=task_spec,
                )
                if result.detected:
                    results.append(result)
        
        return results
