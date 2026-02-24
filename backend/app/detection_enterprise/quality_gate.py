"""
F13: Quality Gate Bypass Detection (MAST Taxonomy)
===================================================

Detects when an agent skips or bypasses quality checks/validation.
This occurs in task verification when:
- Agent skips required validation steps
- Agent ignores quality thresholds
- Agent proceeds despite failing checks
- Agent omits mandatory review processes
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Set

logger = logging.getLogger(__name__)


class QualityGateSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class QualityGateIssueType(str, Enum):
    SKIPPED_VALIDATION = "skipped_validation"
    IGNORED_THRESHOLD = "ignored_threshold"
    BYPASSED_REVIEW = "bypassed_review"
    MISSING_CHECKS = "missing_checks"
    FORCED_COMPLETION = "forced_completion"


@dataclass
class QualityGateIssue:
    issue_type: QualityGateIssueType
    gate_name: str
    description: str
    severity: QualityGateSeverity
    expected_check: Optional[str] = None
    actual_behavior: Optional[str] = None


@dataclass
class QualityGateResult:
    detected: bool
    severity: QualityGateSeverity
    confidence: float
    issues: List[QualityGateIssue] = field(default_factory=list)
    gates_expected: int = 0
    gates_passed: int = 0
    gates_skipped: int = 0
    gates_failed: int = 0
    explanation: str = ""
    suggested_fix: Optional[str] = None


class QualityGateDetector:
    """
    Detects F13: Quality Gate Bypass - agent skips quality checks.

    Analyzes agent execution to identify when validation steps,
    quality thresholds, or review processes are bypassed.
    """

    # Common quality gate patterns that should be present
    VALIDATION_PATTERNS = [
        (r'\b(?:validate|validation|validating)\b', "validation"),
        (r'\b(?:verify|verification|verifying)\b', "verification"),
        (r'\b(?:check|checking|checked)\b', "check"),
        (r'\b(?:test|testing|tested)\b', "testing"),
        (r'\b(?:review|reviewing|reviewed)\b', "review"),
        (r'\b(?:approve|approval|approved)\b', "approval"),
        (r'\b(?:confirm|confirmation|confirmed)\b', "confirmation"),
        (r'\b(?:lint|linting|linted)\b', "linting"),
        (r'\b(?:format|formatting|formatted)\b', "formatting"),
        (r'\b(?:scan|scanning|scanned)\b', "scanning"),
    ]

    # Patterns indicating bypass or skip
    BYPASS_PATTERNS = [
        (r'\b(?:skip|skipping|skipped)\s+(?:validation|verification|check|test|review)', "explicit_skip"),
        (r'\b(?:bypass|bypassing|bypassed)\s+\w+', "explicit_bypass"),
        (r'\b(?:ignore|ignoring|ignored)\s+(?:error|warning|check|validation)', "ignored_check"),
        (r'\b(?:proceed|proceeding)\s+(?:anyway|regardless|despite)', "forced_proceed"),
        (r'\bforce\s+(?:complete|finish|push|commit)', "forced_completion"),
        (r'\b(?:disable|disabled|disabling)\s+(?:check|validation|test|lint)', "disabled_check"),
        (r'--no-verify\b', "git_no_verify"),
        (r'--skip-\w+', "skip_flag"),
        (r'-f\s|--force\b', "force_flag"),
        (r'\bTODO:?\s*(?:add|fix|implement)\s+(?:validation|test|check)', "missing_todo"),
        # v1.1: Implicit bypass patterns (improve recall)
        (r'\bmoving forward without\s+(?:\w+\s+)?(?:validation|test|review)', "implicit_bypass"),
        (r'\baccept(?:ing)?\s+(?:the\s+)?(?:risk|technical debt)', "risk_acceptance"),
        (r'\bdefer(?:ring|red)?\s+(?:validation|testing|review)', "deferred_gate"),
        (r'\btemporarily\s+(?:skip|disable|bypass)', "temporary_bypass"),
        (r'\bwill\s+(?:add|fix|implement)\s+(?:tests?|validation|checks?)\s+later', "deferred_gate"),
        (r'\b(?:manual|manually)\s+(?:verified|checked|tested)', "manual_override"),
    ]

    # Patterns indicating quality gate execution
    GATE_EXECUTION_PATTERNS = [
        (r'(?:running|executing|performing)\s+(?:validation|tests?|checks?)', "gate_running"),
        (r'(?:all|tests?|checks?|validation)\s+(?:passed|succeeded|successful)', "gate_passed"),
        (r'(?:tests?|checks?|validation)\s+(?:failed|unsuccessful|error)', "gate_failed"),
        (r'(?:coverage|quality)\s*(?:score|ratio|percentage)?\s*[:=]?\s*\d+', "quality_metric"),
    ]

    # Required gates by task type
    TASK_REQUIRED_GATES = {
        "code_change": ["lint", "test", "format"],
        "deployment": ["test", "review", "approval"],
        "data_processing": ["validation", "verification"],
        "api_integration": ["test", "validation"],
        "security_change": ["security_scan", "review", "approval"],
        # v1.1: Expanded task types (improve recall)
        "database_change": ["backup", "test", "validation"],
        "config_change": ["test", "validation"],
        "ml_model": ["evaluation", "validation", "test"],
        "documentation": ["review"],
        "infrastructure": ["test", "review", "approval"],
    }

    def __init__(
        self,
        strict_mode: bool = False,
        required_gates: Optional[List[str]] = None,
    ):
        self.strict_mode = strict_mode
        self.required_gates = set(required_gates or [])

    def _extract_gates_mentioned(self, text: str) -> Set[str]:
        """Extract quality gates mentioned in text."""
        gates = set()

        for pattern, gate_type in self.VALIDATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                gates.add(gate_type)

        return gates

    def _detect_bypass_patterns(self, text: str) -> List[tuple]:
        """Detect patterns indicating bypass or skip."""
        bypasses = []

        for pattern, bypass_type in self.BYPASS_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Get context
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                bypasses.append((match.group(), bypass_type, context))

        return bypasses

    def _detect_gate_execution(self, text: str) -> Dict[str, str]:
        """Detect gate execution patterns and their outcomes."""
        executions = {}

        for pattern, exec_type in self.GATE_EXECUTION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                executions[exec_type] = matches[0] if isinstance(matches[0], str) else matches[0][0]

        return executions

    def _infer_task_type(self, task: str, context: str = "") -> Optional[str]:
        """Infer task type to determine required gates."""
        combined = f"{task} {context}".lower()

        if any(w in combined for w in ["deploy", "release", "production", "publish"]):
            return "deployment"
        if any(w in combined for w in ["security", "auth", "password", "token", "key"]):
            return "security_change"
        if any(w in combined for w in ["api", "endpoint", "integration", "webhook"]):
            return "api_integration"
        if any(w in combined for w in ["data", "database", "migration", "import", "export"]):
            return "data_processing"
        if any(w in combined for w in ["code", "function", "class", "refactor", "fix", "feature"]):
            return "code_change"

        return None

    def _analyze_workflow_steps(
        self,
        workflow_steps: List[Dict[str, Any]],
    ) -> tuple[int, int, int, List[str]]:
        """Analyze workflow steps for gate compliance."""
        expected = 0
        passed = 0
        skipped = 0
        issues = []

        for step in workflow_steps:
            step_type = step.get("type", "")
            status = step.get("status", "")
            is_gate = step.get("is_quality_gate", False)

            if is_gate or any(g in step_type.lower() for g in ["test", "lint", "validate", "review"]):
                expected += 1

                if status == "passed" or status == "success":
                    passed += 1
                elif status == "skipped" or status == "bypassed":
                    skipped += 1
                    issues.append(f"Gate '{step_type}' was skipped")
                elif status == "failed":
                    # Check if workflow continued despite failure
                    step_index = workflow_steps.index(step)
                    if step_index < len(workflow_steps) - 1:
                        issues.append(f"Gate '{step_type}' failed but workflow continued")
                        skipped += 1

        return expected, passed, skipped, issues

    def detect(
        self,
        task: str,
        agent_output: str,
        workflow_steps: Optional[List[Dict[str, Any]]] = None,
        required_gates: Optional[List[str]] = None,
        context: Optional[str] = None,
    ) -> QualityGateResult:
        """
        Detect quality gate bypass.

        Args:
            task: The task the agent was asked to perform
            agent_output: The agent's response/output
            workflow_steps: List of workflow steps with status
            required_gates: List of gates required for this task
            context: Additional context

        Returns:
            QualityGateResult with detection outcome
        """
        issues = []

        # Combine required gates
        all_required = self.required_gates.copy()
        if required_gates:
            all_required.update(required_gates)

        # Infer required gates from task type
        task_type = self._infer_task_type(task, context or "")
        if task_type and task_type in self.TASK_REQUIRED_GATES:
            all_required.update(self.TASK_REQUIRED_GATES[task_type])

        # Detect bypass patterns in output
        bypasses = self._detect_bypass_patterns(agent_output)
        for bypass_match, bypass_type, bypass_context in bypasses:
            severity = QualityGateSeverity.SEVERE if bypass_type in ["explicit_bypass", "disabled_check", "git_no_verify"] else QualityGateSeverity.MODERATE

            issues.append(QualityGateIssue(
                issue_type=QualityGateIssueType.BYPASSED_REVIEW if "bypass" in bypass_type else QualityGateIssueType.SKIPPED_VALIDATION,
                gate_name=bypass_type,
                description=f"Detected bypass pattern: {bypass_match}",
                severity=severity,
                actual_behavior=bypass_context,
            ))

        # Analyze workflow steps if provided
        gates_expected = 0
        gates_passed = 0
        gates_skipped = 0
        gates_failed = 0

        if workflow_steps:
            expected, passed, skipped, step_issues = self._analyze_workflow_steps(workflow_steps)
            gates_expected = expected
            gates_passed = passed
            gates_skipped = skipped
            gates_failed = expected - passed - skipped

            for issue_desc in step_issues:
                issues.append(QualityGateIssue(
                    issue_type=QualityGateIssueType.SKIPPED_VALIDATION,
                    gate_name="workflow_gate",
                    description=issue_desc,
                    severity=QualityGateSeverity.SEVERE,
                ))

        # Check for gates mentioned in output
        gates_mentioned = self._extract_gates_mentioned(agent_output)
        gate_executions = self._detect_gate_execution(agent_output)

        # Check if required gates are missing
        if all_required:
            missing_gates = all_required - gates_mentioned

            for missing in missing_gates:
                # Check if it might be implicitly covered
                if not any(missing in exec_type for exec_type in gate_executions.keys()):
                    issues.append(QualityGateIssue(
                        issue_type=QualityGateIssueType.MISSING_CHECKS,
                        gate_name=missing,
                        description=f"Required gate '{missing}' not mentioned or executed",
                        severity=QualityGateSeverity.MODERATE if not self.strict_mode else QualityGateSeverity.SEVERE,
                        expected_check=missing,
                    ))

        # Check for forced completion patterns
        force_patterns = [b for b in bypasses if b[1] in ["forced_completion", "force_flag", "forced_proceed"]]
        if force_patterns:
            issues.append(QualityGateIssue(
                issue_type=QualityGateIssueType.FORCED_COMPLETION,
                gate_name="completion",
                description="Task was force-completed, potentially bypassing checks",
                severity=QualityGateSeverity.SEVERE,
            ))

        # Check for ignored thresholds
        threshold_patterns = re.findall(
            r'(?:coverage|quality|score)\s*[:=]?\s*(\d+)%?\s*(?:below|under|less than|<)\s*(?:threshold|required|minimum)',
            agent_output,
            re.IGNORECASE
        )
        if threshold_patterns:
            issues.append(QualityGateIssue(
                issue_type=QualityGateIssueType.IGNORED_THRESHOLD,
                gate_name="quality_threshold",
                description=f"Quality threshold not met but task proceeded",
                severity=QualityGateSeverity.MODERATE,
            ))

        # Determine result
        detected = len(issues) > 0

        if not detected:
            return QualityGateResult(
                detected=False,
                severity=QualityGateSeverity.NONE,
                confidence=0.8,
                gates_expected=gates_expected or len(all_required),
                gates_passed=gates_passed or len(gates_mentioned),
                gates_skipped=0,
                gates_failed=0,
                explanation="No quality gate bypass detected",
            )

        # Calculate severity
        if any(i.severity == QualityGateSeverity.CRITICAL for i in issues):
            severity = QualityGateSeverity.CRITICAL
        elif any(i.severity == QualityGateSeverity.SEVERE for i in issues):
            severity = QualityGateSeverity.SEVERE
        elif any(i.severity == QualityGateSeverity.MODERATE for i in issues):
            severity = QualityGateSeverity.MODERATE
        else:
            severity = QualityGateSeverity.MINOR

        # Calculate confidence
        confidence = min(0.95, 0.5 + (len(issues) * 0.1) + (len(bypasses) * 0.15))

        # Build explanation
        issue_types = set(i.issue_type.value for i in issues)
        explanation = f"Detected {len(issues)} quality gate issue(s): {', '.join(issue_types)}"

        # Suggest fix
        if any(i.issue_type == QualityGateIssueType.FORCED_COMPLETION for i in issues):
            suggested_fix = "Configure agent to require all quality gates to pass before completion"
        elif any(i.issue_type == QualityGateIssueType.MISSING_CHECKS for i in issues):
            suggested_fix = "Add required quality gates to agent workflow"
        elif any(i.issue_type == QualityGateIssueType.BYPASSED_REVIEW for i in issues):
            suggested_fix = "Remove bypass flags and ensure proper review process"
        else:
            suggested_fix = "Review agent quality gate configuration"

        return QualityGateResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            issues=issues,
            gates_expected=gates_expected or len(all_required),
            gates_passed=gates_passed,
            gates_skipped=gates_skipped,
            gates_failed=gates_failed,
            explanation=explanation,
            suggested_fix=suggested_fix,
        )


# Singleton instance
quality_gate_detector = QualityGateDetector()
