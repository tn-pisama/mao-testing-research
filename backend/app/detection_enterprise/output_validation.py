"""
F12: Output Validation Failure Detection (MAST Taxonomy)
=========================================================

Detects when validation steps are skipped or bypassed:
- Validation steps that are bypassed
- Approval given despite failed/skipped checks
- Missing validation in workflow
- Validation results ignored

Version History:
- v1.0: Initial implementation
- v1.1: FPR reduction:
  - False positive context filter (hypothetical, negation, alternatives)
  - Validation performed patterns (detect when validation actually ran)
  - Multi-issue requirement (single minor issue = not detected)
"""

# Detector version for tracking
DETECTOR_VERSION = "1.1"
DETECTOR_NAME = "OutputValidationDetector"

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Set

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class ValidationIssueType(str, Enum):
    VALIDATION_BYPASSED = "validation_bypassed"
    VALIDATION_SKIPPED = "validation_skipped"
    APPROVAL_DESPITE_FAILURE = "approval_despite_failure"
    MISSING_VALIDATION = "missing_validation"
    VALIDATION_IGNORED = "validation_ignored"
    INCOMPLETE_VALIDATION = "incomplete_validation"


@dataclass
class ValidationStep:
    """Represents a validation step in a workflow."""
    step_id: str
    validation_type: str  # "schema", "content", "quality", "security", etc.
    passed: bool
    bypassed: bool = False
    skipped: bool = False
    result_message: str = ""
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationIssue:
    issue_type: ValidationIssueType
    step_id: str
    validation_type: str
    description: str
    severity: ValidationSeverity


@dataclass
class OutputValidationResult:
    detected: bool
    severity: ValidationSeverity
    confidence: float
    issues: List[ValidationIssue] = field(default_factory=list)
    bypassed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    total_validations: int = 0
    explanation: str = ""
    suggested_fix: Optional[str] = None


class OutputValidationDetector:
    """
    Detects F12: Output Validation Failure - skipped or bypassed validation.

    Analyzes validation workflow to identify when validation steps
    are bypassed, skipped, or their results ignored.
    """

    # Patterns indicating validation bypass
    BYPASS_PATTERNS = [
        (r"BYPASS(?:ED|ING)?:?\s*", "explicit_bypass"),
        (r"(?:skip|skipp)(?:ed|ing)?\s+(?:the\s+)?validation", "skipped_validation"),
        (r"(?:assum|pressum)(?:ed?|ing)\s+(?:it's\s+)?(?:correct|valid)", "assumed_valid"),
        (r"due to (?:time|deadline|pressure)", "time_pressure_bypass"),
        (r"(?:no\s+time|rush|urgent)", "urgent_bypass"),
        (r"(?:will|can)\s+validate\s+later", "deferred_validation"),
        (r"proceed(?:ing)?\s+without\s+(?:the\s+)?(?:validation|check)", "proceed_without_check"),
    ]

    # Patterns indicating approval despite issues
    APPROVAL_DESPITE_FAILURE_PATTERNS = [
        (r"approv(?:ed|ing)\s+(?:anyway|despite|regardless)", "approved_despite"),
        (r"(?:override|overrid)(?:den|ing)?\s+(?:the\s+)?(?:check|validation)", "override"),
        (r"approv(?:ed|al)\s+.*\s+(?:fail|error|issue)", "approved_with_failure"),
        (r"(?:ignor|dismiss)(?:ed|ing)?\s+(?:the\s+)?(?:warning|error|failure)", "ignored_failure"),
    ]

    # v1.1: Context patterns that indicate discussion vs actual bypass (false positives)
    FALSE_POSITIVE_CONTEXTS = [
        r"(?:if\s+(?:we|I)\s+)?(?:were\s+to|could|might)\s+(?:skip|bypass)",  # Hypothetical
        r"(?:should\s+not|shouldn't|don't|won't|never)\s+(?:skip|bypass)",     # Negation
        r"(?:instead\s+of|rather\s+than)\s+(?:skipping|bypassing)",            # Alternatives
        r"(?:important\s+(?:to|not\s+to))\s+(?:skip|bypass)",                  # Advice
        r"(?:risk|danger|problem)\s+(?:of|with)\s+(?:skipping|bypassing)",     # Warning about
        r"(?:avoid|prevent)\s+(?:skipping|bypassing)",                         # Prevention
        r"(?:why|when)\s+(?:to|not\s+to)\s+(?:skip|bypass)",                   # Educational
    ]

    # v1.1: Patterns indicating validation WAS actually performed
    VALIDATION_PERFORMED_PATTERNS = [
        r"(?:running|ran|executed?)\s+(?:the\s+)?(?:test|validation|check)",
        r"(?:test|validation|check)\s+(?:pass|fail|complet|success|result)",
        r"(?:verified|validated|confirmed|checked)\s+(?:that|the)",
        r"(?:all\s+)?(?:tests?|checks?)\s+(?:pass|green|successful)",
        r"(?:validation|verification)\s+(?:complete|done|finished)",
        r"(?:no\s+)?(?:issues?|errors?|problems?)\s+(?:found|detected)",
    ]

    # Required validation types for different content
    REQUIRED_VALIDATIONS = {
        "financial": ["schema", "calculation", "compliance"],
        "code": ["syntax", "security", "quality"],
        "data": ["schema", "integrity", "completeness"],
        "document": ["format", "content", "approval"],
        "api": ["schema", "authentication", "rate_limit"],
    }

    def __init__(
        self,
        required_validations: Optional[Dict[str, List[str]]] = None,
        strict_mode: bool = False,
        min_issues_for_detection: int = 2,  # v1.1: Require multiple issues
    ):
        self.required_validations = required_validations or self.REQUIRED_VALIDATIONS
        self.strict_mode = strict_mode
        self.min_issues_for_detection = min_issues_for_detection

    def _is_false_positive_context(self, text: str, match_pos: int) -> bool:
        """
        v1.1: Check if bypass pattern is in a false positive context.

        Returns True if the bypass mention is hypothetical, negated,
        or part of a discussion rather than actual bypass.
        """
        # Get 150 chars before and after the match for context
        start = max(0, match_pos - 150)
        end = min(len(text), match_pos + 150)
        context = text[start:end]

        for pattern in self.FALSE_POSITIVE_CONTEXTS:
            if re.search(pattern, context, re.IGNORECASE):
                return True

        return False

    def _was_validation_performed(self, text: str) -> bool:
        """
        v1.1: Check if text indicates validation was actually performed.

        Returns True if there's evidence of validation being run successfully.
        """
        for pattern in self.VALIDATION_PERFORMED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_bypass_patterns(self, text: str) -> List[tuple]:
        """Detect bypass patterns in text with v1.1 context verification."""
        bypasses = []
        for pattern, bypass_type in self.BYPASS_PATTERNS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                # v1.1: Check context for false positives
                if not self._is_false_positive_context(text, match.start()):
                    bypasses.append((pattern, bypass_type))
                    break  # Only count each pattern once
        return bypasses

    def _detect_approval_despite_failure(self, text: str) -> List[tuple]:
        """Detect patterns indicating approval despite failures."""
        approvals = []
        for pattern, approval_type in self.APPROVAL_DESPITE_FAILURE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                approvals.append((pattern, approval_type))
        return approvals

    def _check_validation_step(
        self,
        step: ValidationStep,
    ) -> List[ValidationIssue]:
        """Check a single validation step for issues."""
        issues = []

        # Check for explicit bypass
        if step.bypassed:
            severity = ValidationSeverity.SEVERE
            if step.validation_type in ["security", "compliance", "authentication"]:
                severity = ValidationSeverity.CRITICAL

            issues.append(ValidationIssue(
                issue_type=ValidationIssueType.VALIDATION_BYPASSED,
                step_id=step.step_id,
                validation_type=step.validation_type,
                description=f"Validation '{step.validation_type}' was explicitly bypassed",
                severity=severity,
            ))

        # Check for skipped validation
        if step.skipped:
            issues.append(ValidationIssue(
                issue_type=ValidationIssueType.VALIDATION_SKIPPED,
                step_id=step.step_id,
                validation_type=step.validation_type,
                description=f"Validation '{step.validation_type}' was skipped",
                severity=ValidationSeverity.MODERATE,
            ))

        # Check result message for bypass patterns
        if step.result_message:
            bypasses = self._detect_bypass_patterns(step.result_message)
            for pattern, bypass_type in bypasses:
                issues.append(ValidationIssue(
                    issue_type=ValidationIssueType.VALIDATION_BYPASSED,
                    step_id=step.step_id,
                    validation_type=step.validation_type,
                    description=f"Validation bypass detected: {bypass_type}",
                    severity=ValidationSeverity.MODERATE,
                ))

        return issues

    def _check_approval_chain(
        self,
        validation_steps: List[ValidationStep],
        final_approved: bool,
    ) -> List[ValidationIssue]:
        """Check if approval was given despite validation failures."""
        issues = []

        if not final_approved:
            return issues

        # Count failed, bypassed, or skipped validations
        failed = [s for s in validation_steps if not s.passed and not s.bypassed and not s.skipped]
        bypassed = [s for s in validation_steps if s.bypassed]
        skipped = [s for s in validation_steps if s.skipped]

        problematic = failed + bypassed + skipped

        if problematic:
            types = [s.validation_type for s in problematic]
            issues.append(ValidationIssue(
                issue_type=ValidationIssueType.APPROVAL_DESPITE_FAILURE,
                step_id="final_approval",
                validation_type="approval",
                description=f"Output approved despite {len(problematic)} validation issue(s): {', '.join(types)}",
                severity=ValidationSeverity.SEVERE,
            ))

        return issues

    def _check_missing_validations(
        self,
        validation_steps: List[ValidationStep],
        content_type: Optional[str] = None,
    ) -> List[ValidationIssue]:
        """Check for missing required validations."""
        issues = []

        if not content_type or content_type not in self.required_validations:
            return issues

        required = set(self.required_validations[content_type])
        performed = set(s.validation_type for s in validation_steps)
        missing = required - performed

        for validation_type in missing:
            issues.append(ValidationIssue(
                issue_type=ValidationIssueType.MISSING_VALIDATION,
                step_id="workflow",
                validation_type=validation_type,
                description=f"Required validation '{validation_type}' was not performed for {content_type} content",
                severity=ValidationSeverity.MODERATE,
            ))

        return issues

    def detect(
        self,
        validation_steps: List[ValidationStep],
        final_approved: bool = False,
        content_type: Optional[str] = None,
    ) -> OutputValidationResult:
        """
        Detect output validation failures.

        Args:
            validation_steps: List of validation steps performed
            final_approved: Whether the output was ultimately approved
            content_type: Type of content for checking required validations

        Returns:
            OutputValidationResult with detection outcome
        """
        if not validation_steps:
            if final_approved and content_type:
                # Approved without any validation
                return OutputValidationResult(
                    detected=True,
                    severity=ValidationSeverity.SEVERE,
                    confidence=0.9,
                    issues=[ValidationIssue(
                        issue_type=ValidationIssueType.MISSING_VALIDATION,
                        step_id="workflow",
                        validation_type="all",
                        description=f"Output approved without any validation for {content_type} content",
                        severity=ValidationSeverity.SEVERE,
                    )],
                    explanation="No validations performed before approval",
                    suggested_fix="Add required validation steps before approval",
                )

            return OutputValidationResult(
                detected=False,
                severity=ValidationSeverity.NONE,
                confidence=0.0,
                explanation="No validation steps to analyze",
            )

        all_issues = []

        # Check each validation step
        for step in validation_steps:
            issues = self._check_validation_step(step)
            all_issues.extend(issues)

        # Check approval chain
        approval_issues = self._check_approval_chain(validation_steps, final_approved)
        all_issues.extend(approval_issues)

        # Check for missing validations
        missing_issues = self._check_missing_validations(validation_steps, content_type)
        all_issues.extend(missing_issues)

        if not all_issues:
            return OutputValidationResult(
                detected=False,
                severity=ValidationSeverity.NONE,
                confidence=0.9,
                total_validations=len(validation_steps),
                explanation="All validations passed without issues",
            )

        # v1.1: Multi-issue requirement - single minor issue likely false positive
        max_severity = max((i.severity for i in all_issues), default=ValidationSeverity.NONE)
        if len(all_issues) < self.min_issues_for_detection:
            # Single issue with non-critical severity = likely false positive
            if max_severity not in [ValidationSeverity.CRITICAL, ValidationSeverity.SEVERE]:
                return OutputValidationResult(
                    detected=False,
                    severity=ValidationSeverity.NONE,
                    confidence=0.4,
                    total_validations=len(validation_steps),
                    explanation=f"Single minor issue detected, below threshold (need {self.min_issues_for_detection})",
                )

        # v1.2: Ensemble voting — require 2+ distinct issue types for non-critical.
        # Multiple issues of the same type (e.g., 3 "missing_validation") are
        # often from the same pattern-matching pass and don't increase confidence.
        distinct_issue_types = set(i.issue_type for i in all_issues)
        if len(distinct_issue_types) < 2 and max_severity not in [
            ValidationSeverity.CRITICAL, ValidationSeverity.SEVERE
        ]:
            return OutputValidationResult(
                detected=False,
                severity=ValidationSeverity.NONE,
                confidence=0.4,
                total_validations=len(validation_steps),
                explanation=(
                    f"Only one signal type ({next(iter(distinct_issue_types)).value}) "
                    "detected. Require 2+ distinct signal types to confirm detection."
                ),
            )

        # Calculate metrics
        bypassed_count = len([s for s in validation_steps if s.bypassed])
        skipped_count = len([s for s in validation_steps if s.skipped])
        failed_count = len([s for s in validation_steps if not s.passed and not s.bypassed and not s.skipped])

        # Determine overall severity
        if any(i.severity == ValidationSeverity.CRITICAL for i in all_issues):
            severity = ValidationSeverity.CRITICAL
        elif any(i.severity == ValidationSeverity.SEVERE for i in all_issues):
            severity = ValidationSeverity.SEVERE
        elif any(i.severity == ValidationSeverity.MODERATE for i in all_issues):
            severity = ValidationSeverity.MODERATE
        else:
            severity = ValidationSeverity.MINOR

        # Calculate confidence
        confidence = min(0.95, 0.5 + (len(all_issues) * 0.1))

        # Build explanation
        issue_types = set(i.issue_type.value for i in all_issues)
        explanation = f"Detected {len(all_issues)} validation issue(s): {', '.join(issue_types)}"

        # Suggest fix
        fixes = []
        if bypassed_count > 0:
            fixes.append(f"remove bypass for {bypassed_count} validation(s)")
        if skipped_count > 0:
            fixes.append(f"enable {skipped_count} skipped validation(s)")
        if any(i.issue_type == ValidationIssueType.APPROVAL_DESPITE_FAILURE for i in all_issues):
            fixes.append("do not approve outputs with failed validations")
        if any(i.issue_type == ValidationIssueType.MISSING_VALIDATION for i in all_issues):
            fixes.append("add missing required validations to workflow")

        return OutputValidationResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            issues=all_issues,
            bypassed_count=bypassed_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            total_validations=len(validation_steps),
            explanation=explanation,
            suggested_fix="; ".join(fixes) if fixes else None,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> OutputValidationResult:
        """
        Detect output validation failures from trace data.
        """
        spans = trace.get("spans", [])
        if not spans:
            return OutputValidationResult(
                detected=False,
                severity=ValidationSeverity.NONE,
                confidence=0.0,
                explanation="No spans in trace",
            )

        validation_steps = []
        final_approved = False
        content_type = None

        for span in spans:
            metadata = span.get("metadata", {})
            name = span.get("name", "").lower()
            role = metadata.get("role", "").lower()

            # Check if this is a validation span
            is_validation = (
                "valid" in name or
                "check" in name or
                role == "validation" or
                metadata.get("validation_type")
            )

            if is_validation:
                validation_type = metadata.get("validation_type", name.replace("_validator", "").replace("_", " "))
                passed = metadata.get("validation_passed", True)
                bypassed = metadata.get("validation_bypassed", False)
                skipped = metadata.get("validation_skipped", False)

                # Check output for bypass indicators
                output = span.get("output_data", {}).get("result", "")
                if isinstance(output, str):
                    if "BYPASS" in output.upper() or "skipping" in output.lower():
                        bypassed = True
                    result_message = output
                else:
                    result_message = ""

                validation_steps.append(ValidationStep(
                    step_id=span.get("span_id", name),
                    validation_type=validation_type,
                    passed=passed and not bypassed and not skipped,
                    bypassed=bypassed,
                    skipped=skipped,
                    result_message=result_message,
                    timestamp=span.get("start_time", 0),
                    metadata=metadata,
                ))

            # Check for approval span
            if "approv" in name or role == "approval":
                output = span.get("output_data", {}).get("result", "")
                if isinstance(output, str) and ("approved" in output.lower() or "approval" in output.lower()):
                    final_approved = True

                # Check for approval despite bypassed validations
                if metadata.get("approved_with_bypassed_validations"):
                    final_approved = True

        # Infer content type from trace metadata
        trace_metadata = trace.get("metadata", {})
        if "financial" in str(trace_metadata).lower():
            content_type = "financial"
        elif "code" in str(trace_metadata).lower():
            content_type = "code"
        elif "data" in str(trace_metadata).lower():
            content_type = "data"

        return self.detect(validation_steps, final_approved, content_type)


# Singleton instance
output_validation_detector = OutputValidationDetector()
