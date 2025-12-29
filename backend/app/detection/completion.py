"""
F14: Completion Misjudgment Detection (MAST Taxonomy)
=====================================================

Detects when an agent incorrectly determines task completion.
This occurs in task verification when:
- Agent claims task is complete when it's not
- Agent delivers partial results as final
- Agent ignores incomplete subtasks
- Agent misses success criteria
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Set

logger = logging.getLogger(__name__)


class CompletionSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class CompletionIssueType(str, Enum):
    PREMATURE_COMPLETION = "premature_completion"
    PARTIAL_DELIVERY = "partial_delivery"
    IGNORED_SUBTASKS = "ignored_subtasks"
    MISSED_CRITERIA = "missed_criteria"
    FALSE_SUCCESS_CLAIM = "false_success_claim"
    INCOMPLETE_VERIFICATION = "incomplete_verification"


@dataclass
class CompletionIssue:
    issue_type: CompletionIssueType
    description: str
    severity: CompletionSeverity
    missing_element: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class CompletionResult:
    detected: bool
    severity: CompletionSeverity
    confidence: float
    issues: List[CompletionIssue] = field(default_factory=list)
    completion_claimed: bool = False
    actual_completion_ratio: float = 1.0
    subtasks_total: int = 0
    subtasks_completed: int = 0
    success_criteria_met: int = 0
    success_criteria_total: int = 0
    explanation: str = ""
    suggested_fix: Optional[str] = None


class CompletionMisjudgmentDetector:
    """
    Detects F14: Completion Misjudgment - agent wrongly claims completion.

    Analyzes agent output against task requirements to identify
    premature or false completion claims.
    """

    # Patterns indicating completion claims
    COMPLETION_CLAIM_PATTERNS = [
        r'\b(?:task|work|job)\s+(?:is\s+)?(?:complete|completed|done|finished)\b',
        r'\b(?:i have|i\'ve)\s+(?:completed|finished|done)\b',
        r'\b(?:successfully|successfully)\s+(?:completed|finished|done)\b',
        r'\b(?:all\s+)?(?:tasks?|steps?|items?)\s+(?:are\s+)?(?:complete|done)\b',
        r'\b(?:mission\s+accomplished|job\s+done)\b',
        r'\bhere(?:\'s| is)\s+the\s+(?:final|completed|finished)\b',
        r'\b(?:that\'s|this\s+is)\s+everything\b',
        r'\bnothing\s+(?:else|more)\s+(?:to\s+do|needed|required)\b',
    ]

    # Patterns indicating incomplete work
    INCOMPLETE_PATTERNS = [
        (r'\bTODO\b', "todo_marker"),
        (r'\bFIXME\b', "fixme_marker"),
        (r'\bHACK\b', "hack_marker"),
        (r'\bXXX\b', "xxx_marker"),
        (r'\b(?:not\s+yet|still\s+need|remaining|pending)\b', "pending_marker"),
        (r'\b(?:placeholder|stub|dummy|mock)\b', "placeholder"),
        (r'\b(?:will\s+be|to\s+be)\s+(?:implemented|added|done)\b', "future_work"),
        (r'\.{3,}|etc\.', "ellipsis"),
        (r'\b(?:part\s+\d|step\s+\d)\s+(?:of|/)\s+\d+', "partial_progress"),
        (r'\b(?:partial|incomplete|unfinished)\b', "explicit_incomplete"),
    ]

    # Patterns indicating errors or failures
    ERROR_PATTERNS = [
        r'\b(?:error|exception|failure|failed)\b',
        r'\b(?:could not|couldn\'t|unable to|cannot)\b',
        r'\b(?:crash|crashed|crashing)\b',
        r'\b(?:bug|broken|breaking)\b',
    ]

    # Success criteria extraction patterns
    CRITERIA_PATTERNS = [
        r'(?:should|must|need to|required to)\s+(.+?)(?:\.|$)',
        r'(?:criteria|requirement|goal):\s*(.+?)(?:\.|$)',
        r'(?:success|completion)\s+(?:means?|requires?):\s*(.+?)(?:\.|$)',
        r'\d+\.\s+(.+?)(?:\n|$)',  # Numbered list items
    ]

    def __init__(
        self,
        strict_mode: bool = False,
        completion_threshold: float = 0.9,
    ):
        self.strict_mode = strict_mode
        self.completion_threshold = completion_threshold

    def _detect_completion_claim(self, text: str) -> bool:
        """Detect if agent claims task completion."""
        for pattern in self.COMPLETION_CLAIM_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_incomplete_markers(self, text: str) -> List[tuple]:
        """Detect markers indicating incomplete work."""
        markers = []

        for pattern, marker_type in self.INCOMPLETE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                markers.append((match.group(), marker_type, context))

        return markers

    def _detect_errors(self, text: str) -> List[str]:
        """Detect error/failure mentions in output."""
        errors = []

        for pattern in self.ERROR_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                context = text[start:end].strip()
                errors.append(context)

        return errors

    def _extract_success_criteria(self, task: str) -> List[str]:
        """Extract success criteria from task description."""
        criteria = []

        for pattern in self.CRITERIA_PATTERNS:
            matches = re.findall(pattern, task, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if len(match.strip()) > 5:  # Filter very short matches
                    criteria.append(match.strip())

        return criteria

    def _check_criteria_met(
        self,
        criteria: List[str],
        output: str,
    ) -> tuple[int, int, List[str]]:
        """Check how many success criteria appear to be met."""
        met = 0
        unmet = []

        output_lower = output.lower()

        for criterion in criteria:
            # Extract key terms from criterion
            words = re.findall(r'\b\w{4,}\b', criterion.lower())
            key_words = [w for w in words if w not in {
                'should', 'must', 'need', 'required', 'that', 'this',
                'will', 'have', 'been', 'with', 'from', 'into'
            }]

            if not key_words:
                continue

            # Check if key words appear in output
            matches = sum(1 for w in key_words if w in output_lower)
            if matches >= len(key_words) * 0.5:  # At least 50% of key words
                met += 1
            else:
                unmet.append(criterion)

        return met, len(criteria), unmet

    def _analyze_subtasks(
        self,
        subtasks: List[Dict[str, Any]],
    ) -> tuple[int, int, List[str]]:
        """Analyze subtask completion status."""
        total = len(subtasks)
        completed = 0
        incomplete = []

        for subtask in subtasks:
            status = subtask.get("status", "").lower()
            name = subtask.get("name", subtask.get("description", "Unknown"))

            if status in ["complete", "completed", "done", "success", "passed"]:
                completed += 1
            else:
                incomplete.append(name)

        return completed, total, incomplete

    def _calculate_completion_ratio(
        self,
        output: str,
        task: str,
    ) -> float:
        """Estimate completion ratio based on output analysis."""
        # Count incomplete markers
        incomplete_markers = len(self._detect_incomplete_markers(output))

        # Count errors
        errors = len(self._detect_errors(output))

        # Base ratio
        if incomplete_markers + errors == 0:
            return 1.0

        # Penalize for incomplete markers and errors
        penalty = min(0.5, incomplete_markers * 0.1 + errors * 0.15)
        return max(0.0, 1.0 - penalty)

    def detect(
        self,
        task: str,
        agent_output: str,
        subtasks: Optional[List[Dict[str, Any]]] = None,
        success_criteria: Optional[List[str]] = None,
        expected_outputs: Optional[List[str]] = None,
        context: Optional[str] = None,
    ) -> CompletionResult:
        """
        Detect completion misjudgment.

        Args:
            task: The task the agent was asked to perform
            agent_output: The agent's response/output
            subtasks: List of subtasks with completion status
            success_criteria: List of success criteria to check
            expected_outputs: List of expected output elements
            context: Additional context

        Returns:
            CompletionResult with detection outcome
        """
        issues = []

        # Check if agent claims completion
        completion_claimed = self._detect_completion_claim(agent_output)

        # Detect incomplete markers
        incomplete_markers = self._detect_incomplete_markers(agent_output)

        # Detect errors
        errors = self._detect_errors(agent_output)

        # Calculate completion ratio
        completion_ratio = self._calculate_completion_ratio(agent_output, task)

        # Analyze subtasks if provided
        subtasks_completed = 0
        subtasks_total = 0
        incomplete_subtasks = []

        if subtasks:
            subtasks_completed, subtasks_total, incomplete_subtasks = self._analyze_subtasks(subtasks)
            if subtasks_total > 0:
                completion_ratio = min(completion_ratio, subtasks_completed / subtasks_total)

        # Check success criteria
        criteria = success_criteria or self._extract_success_criteria(task)
        criteria_met = 0
        criteria_total = 0
        unmet_criteria = []

        if criteria:
            criteria_met, criteria_total, unmet_criteria = self._check_criteria_met(criteria, agent_output)
            if criteria_total > 0:
                criteria_ratio = criteria_met / criteria_total
                completion_ratio = min(completion_ratio, criteria_ratio)

        # Check expected outputs
        if expected_outputs:
            output_lower = agent_output.lower()
            found_outputs = sum(1 for exp in expected_outputs if exp.lower() in output_lower)
            if len(expected_outputs) > 0:
                output_ratio = found_outputs / len(expected_outputs)
                completion_ratio = min(completion_ratio, output_ratio)
                if found_outputs < len(expected_outputs):
                    missing = [e for e in expected_outputs if e.lower() not in output_lower]
                    for m in missing[:3]:  # Top 3 missing
                        issues.append(CompletionIssue(
                            issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                            description=f"Expected output missing: {m}",
                            severity=CompletionSeverity.MODERATE,
                            missing_element=m,
                        ))

        # Detect misjudgment
        if completion_claimed and completion_ratio < self.completion_threshold:
            issues.append(CompletionIssue(
                issue_type=CompletionIssueType.PREMATURE_COMPLETION,
                description=f"Agent claimed completion at {completion_ratio:.0%} actual progress",
                severity=CompletionSeverity.SEVERE,
                evidence=f"Completion ratio: {completion_ratio:.2f}",
            ))

        # Check for incomplete markers with completion claim
        if completion_claimed and incomplete_markers:
            for marker, marker_type, context in incomplete_markers[:3]:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.INCOMPLETE_VERIFICATION,
                    description=f"Incomplete marker found despite completion claim: {marker}",
                    severity=CompletionSeverity.MODERATE,
                    evidence=context,
                ))

        # Check for errors with completion claim
        if completion_claimed and errors:
            issues.append(CompletionIssue(
                issue_type=CompletionIssueType.FALSE_SUCCESS_CLAIM,
                description=f"Errors detected despite completion claim ({len(errors)} error mentions)",
                severity=CompletionSeverity.SEVERE,
                evidence=errors[0] if errors else None,
            ))

        # Check for incomplete subtasks with completion claim
        if completion_claimed and incomplete_subtasks:
            issues.append(CompletionIssue(
                issue_type=CompletionIssueType.IGNORED_SUBTASKS,
                description=f"{len(incomplete_subtasks)} subtasks incomplete despite completion claim",
                severity=CompletionSeverity.SEVERE,
                missing_element=", ".join(incomplete_subtasks[:3]),
            ))

        # Check for unmet criteria with completion claim
        if completion_claimed and unmet_criteria:
            issues.append(CompletionIssue(
                issue_type=CompletionIssueType.MISSED_CRITERIA,
                description=f"{len(unmet_criteria)} success criteria not met",
                severity=CompletionSeverity.MODERATE,
                missing_element=unmet_criteria[0] if unmet_criteria else None,
            ))

        # Determine result
        detected = len(issues) > 0

        if not detected:
            return CompletionResult(
                detected=False,
                severity=CompletionSeverity.NONE,
                confidence=0.8,
                completion_claimed=completion_claimed,
                actual_completion_ratio=completion_ratio,
                subtasks_total=subtasks_total,
                subtasks_completed=subtasks_completed,
                success_criteria_met=criteria_met,
                success_criteria_total=criteria_total,
                explanation="No completion misjudgment detected",
            )

        # Calculate severity
        if any(i.severity == CompletionSeverity.CRITICAL for i in issues):
            severity = CompletionSeverity.CRITICAL
        elif any(i.severity == CompletionSeverity.SEVERE for i in issues):
            severity = CompletionSeverity.SEVERE
        elif any(i.severity == CompletionSeverity.MODERATE for i in issues):
            severity = CompletionSeverity.MODERATE
        else:
            severity = CompletionSeverity.MINOR

        # Calculate confidence based on evidence strength
        base_confidence = 0.5
        if completion_claimed:
            base_confidence += 0.2
        if incomplete_markers:
            base_confidence += 0.1
        if errors:
            base_confidence += 0.1
        if incomplete_subtasks:
            base_confidence += 0.15
        confidence = min(0.95, base_confidence)

        # Build explanation
        issue_types = set(i.issue_type.value for i in issues)
        explanation = (
            f"Detected completion misjudgment: {', '.join(issue_types)}. "
            f"Actual completion: {completion_ratio:.0%}"
        )

        # Suggest fix
        if any(i.issue_type == CompletionIssueType.IGNORED_SUBTASKS for i in issues):
            suggested_fix = "Ensure agent tracks and completes all subtasks before claiming completion"
        elif any(i.issue_type == CompletionIssueType.MISSED_CRITERIA for i in issues):
            suggested_fix = "Implement success criteria verification before completion"
        elif any(i.issue_type == CompletionIssueType.FALSE_SUCCESS_CLAIM for i in issues):
            suggested_fix = "Add error detection to prevent false success claims"
        else:
            suggested_fix = "Add comprehensive completion verification to agent workflow"

        return CompletionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            issues=issues,
            completion_claimed=completion_claimed,
            actual_completion_ratio=completion_ratio,
            subtasks_total=subtasks_total,
            subtasks_completed=subtasks_completed,
            success_criteria_met=criteria_met,
            success_criteria_total=criteria_total,
            explanation=explanation,
            suggested_fix=suggested_fix,
        )


# Singleton instance
completion_detector = CompletionMisjudgmentDetector()
