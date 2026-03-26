"""
F18: Delegation Quality Detection (MAST Taxonomy)
==================================================

Detects low-quality task delegations between humans and agents, or between
agents, where critical context, success criteria, or bounds are missing.

Inspired by Anthropic's AI Fluency Index finding that only 30% of humans
set explicit collaboration terms when working with AI. In multi-agent systems,
this under-specification at handoff points causes specification drift,
context loss, and unverifiable outcomes.

Version History:
- v1.0: Initial implementation — heuristic Tier 1 detector
  - Instruction specificity scoring (vague term detection)
  - Success criteria presence checking
  - Context completeness estimation
  - Bounds detection (time, cost, scope, authority)
"""

DETECTOR_VERSION = "1.0"
DETECTOR_NAME = "DelegationQualityDetector"

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DelegationSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class DelegationIssueType(str, Enum):
    MISSING_SUCCESS_CRITERIA = "missing_success_criteria"
    VAGUE_INSTRUCTION = "vague_instruction"
    INCOMPLETE_CONTEXT = "incomplete_context"
    MISSING_BOUNDS = "missing_bounds"
    CAPABILITY_MISMATCH = "capability_mismatch"


@dataclass
class DelegationIssue:
    issue_type: DelegationIssueType
    description: str
    severity: DelegationSeverity


@dataclass
class DelegationResult:
    detected: bool
    primary_issue: Optional[DelegationIssueType]
    severity: DelegationSeverity
    confidence: float
    specificity_score: float
    criteria_score: float
    context_score: float
    bounds_score: float
    issues: list[DelegationIssue] = field(default_factory=list)
    explanation: str = ""
    suggested_fix: Optional[str] = None


class DelegationQualityDetector:
    """
    Detects F18: Delegation Quality — low-quality task handoffs where
    critical information is missing or underspecified.

    Evaluates four dimensions:
    1. Instruction specificity — are instructions concrete enough to act on?
    2. Success criteria — is there a measurable definition of done?
    3. Context completeness — was relevant context transferred?
    4. Bounds — are there constraints on time, cost, scope, or authority?
    """

    # Vague delegation phrases that signal underspecification
    VAGUE_PATTERNS = [
        r"\bhandle\s+(?:this|that|it)\b",
        r"\btake\s+(?:care\s+of|over)\b",
        r"\bdeal\s+with\b",
        r"\bfigure\s+(?:it\s+)?out\b",
        r"\bjust\s+(?:do|fix|make)\b",
        r"\bdo\s+(?:something|whatever)\b",
        r"\bwork\s+on\s+(?:this|that|it)\b",
        r"\bsort\s+(?:this|that|it)\s+out\b",
        r"\blook\s+into\b",
        r"\bget\s+(?:this|that|it)\s+done\b",
        r"\bmake\s+(?:this|that|it)\s+work\b",
        r"\bclean\s+(?:this|that|it)\s+up\b",
    ]

    # Patterns that indicate success criteria are present
    CRITERIA_PATTERNS = [
        r"\bsuccess(?:ful(?:ly)?)?\s+(?:when|if|means)\b",
        r"\bdone\s+when\b",
        r"\bcomplete(?:d)?\s+(?:when|if|once)\b",
        r"\bacceptance\s+criteria\b",
        r"\bexpect(?:ed)?\s+(?:output|result|outcome)\b",
        r"\bshould\s+(?:return|produce|output|generate|result)\b",
        r"\bmust\s+(?:return|produce|output|generate|result|include|contain)\b",
        r"\bverif(?:y|ied)\s+(?:by|that|when)\b",
        r"\btest(?:ed)?\s+(?:by|that|when)\b",
        r"\bmetric[s]?\b",
        r"\bkpi[s]?\b",
        r"\btarget\s+(?:is|of|:)\b",
        r"\bgoal\s+(?:is|:)\b",
        r"\bdefin(?:e|ition)\s+of\s+done\b",
        r"\b(?:at\s+least|minimum|no\s+more\s+than|maximum|exactly)\s+\d+\b",
    ]

    # Patterns that indicate bounds/constraints are present
    BOUNDS_PATTERNS = [
        # Time bounds
        r"\bby\s+(?:end\s+of\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|eod|eow)\b",
        r"\bdeadline\b",
        r"\bdue\s+(?:by|date|on)\b",
        r"\bwithin\s+\d+\s+(?:minute|hour|day|week)\b",
        r"\bbefore\s+\d{4}[-/]\d{2}[-/]\d{2}\b",
        r"\btimeout\b",
        r"\btime\s*(?:limit|box|bound)\b",
        # Cost bounds
        r"\bbudget\b",
        r"\bcost\s+(?:limit|cap|ceiling|maximum)\b",
        r"\bmax(?:imum)?\s+(?:cost|spend|budget|tokens?)\b",
        r"\b(?:no|don'?t)\s+(?:exceed|spend\s+more\s+than)\b",
        r"\b\$\d+\b",
        # Scope bounds
        r"\bscope(?:d)?\s+to\b",
        r"\blimit(?:ed)?\s+to\b",
        r"\bonly\s+(?:touch|modify|change|update|affect)\b",
        r"\bdon'?t\s+(?:touch|modify|change|update|affect)\b",
        r"\bout\s+of\s+scope\b",
        r"\bdo\s+not\s+(?:include|add|change)\b",
        # Authority bounds
        r"\bapproval\s+(?:required|needed|from)\b",
        r"\bescalate\s+(?:if|when|to)\b",
        r"\bask\s+(?:me|before|first)\b",
        r"\bdon'?t\s+(?:deploy|push|merge|delete|publish)\s+without\b",
        r"\bpermission\b",
    ]

    # Concrete specificity markers (nouns, verbs, quantifiers)
    SPECIFICITY_PATTERNS = [
        r"\b\d+\b",  # numbers
        r"\b(?:function|class|method|endpoint|table|file|module|service|api)\s+\w+",  # named code entities
        r"\b(?:create|build|implement|write|add|remove|update|delete|migrate|refactor|deploy)\s+\w+",  # action verbs
        r"\b(?:using|with|via|through)\s+\w+",  # tool/method specification
        r"\b(?:because|since|given\s+that|due\s+to)\b",  # reasoning context
        r"```",  # code blocks
        r"\b(?:input|output|request|response|payload|schema|format)\b",  # I/O specification
    ]

    def __init__(
        self,
        specificity_threshold: float = 0.40,
        criteria_threshold: float = 0.30,
        context_threshold: float = 0.35,
        bounds_threshold: float = 0.25,
        overall_threshold: float = 0.45,
    ):
        self.specificity_threshold = specificity_threshold
        self.criteria_threshold = criteria_threshold
        self.context_threshold = context_threshold
        self.bounds_threshold = bounds_threshold
        self.overall_threshold = overall_threshold

        self._vague_compiled = [re.compile(p, re.IGNORECASE) for p in self.VAGUE_PATTERNS]
        self._criteria_compiled = [re.compile(p, re.IGNORECASE) for p in self.CRITERIA_PATTERNS]
        self._bounds_compiled = [re.compile(p, re.IGNORECASE) for p in self.BOUNDS_PATTERNS]
        self._specificity_compiled = [re.compile(p, re.IGNORECASE) for p in self.SPECIFICITY_PATTERNS]

    def detect(
        self,
        delegator_instruction: str,
        task_context: str = "",
        success_criteria: str = "",
        delegatee_capabilities: str = "",
    ) -> DelegationResult:
        """
        Detect delegation quality issues.

        Args:
            delegator_instruction: The instruction given by the delegator.
            task_context: Background context provided with the delegation.
            success_criteria: Explicit success criteria, if any.
            delegatee_capabilities: Description of what the delegatee can do.

        Returns:
            DelegationResult with scores and detected issues.
        """
        if not delegator_instruction or not delegator_instruction.strip():
            return DelegationResult(
                detected=True,
                primary_issue=DelegationIssueType.VAGUE_INSTRUCTION,
                severity=DelegationSeverity.SEVERE,
                confidence=0.95,
                specificity_score=0.0,
                criteria_score=0.0,
                context_score=0.0,
                bounds_score=0.0,
                issues=[DelegationIssue(
                    issue_type=DelegationIssueType.VAGUE_INSTRUCTION,
                    description="Empty or missing delegation instruction.",
                    severity=DelegationSeverity.SEVERE,
                )],
                explanation="No delegation instruction provided.",
                suggested_fix="Provide a clear instruction describing the task, expected outcome, and any constraints.",
            )

        # Combine instruction + criteria + context for full-text analysis
        full_text = f"{delegator_instruction} {success_criteria} {task_context}".strip()

        # 1. Instruction specificity
        specificity_score = self._score_specificity(delegator_instruction)

        # 2. Success criteria
        criteria_score = self._score_criteria(delegator_instruction, success_criteria)

        # 3. Context completeness
        context_score = self._score_context(delegator_instruction, task_context)

        # 4. Bounds
        bounds_score = self._score_bounds(full_text)

        # Collect issues
        issues = []

        if specificity_score < self.specificity_threshold:
            issues.append(DelegationIssue(
                issue_type=DelegationIssueType.VAGUE_INSTRUCTION,
                description=f"Instruction lacks specificity (score: {specificity_score:.2f}).",
                severity=DelegationSeverity.MODERATE if specificity_score > 0.20 else DelegationSeverity.SEVERE,
            ))

        if criteria_score < self.criteria_threshold:
            issues.append(DelegationIssue(
                issue_type=DelegationIssueType.MISSING_SUCCESS_CRITERIA,
                description=f"No measurable success criteria provided (score: {criteria_score:.2f}).",
                severity=DelegationSeverity.MODERATE if criteria_score > 0.10 else DelegationSeverity.SEVERE,
            ))

        if context_score < self.context_threshold:
            issues.append(DelegationIssue(
                issue_type=DelegationIssueType.INCOMPLETE_CONTEXT,
                description=f"Relevant context may be missing (score: {context_score:.2f}).",
                severity=DelegationSeverity.MINOR if context_score > 0.20 else DelegationSeverity.MODERATE,
            ))

        if bounds_score < self.bounds_threshold:
            issues.append(DelegationIssue(
                issue_type=DelegationIssueType.MISSING_BOUNDS,
                description=f"No constraints on time, cost, scope, or authority (score: {bounds_score:.2f}).",
                severity=DelegationSeverity.MINOR,
            ))

        # Capability mismatch (if delegatee_capabilities provided)
        if delegatee_capabilities:
            cap_issue = self._check_capability_mismatch(delegator_instruction, delegatee_capabilities)
            if cap_issue:
                issues.append(cap_issue)

        # Overall quality score (weighted average)
        overall_score = (
            specificity_score * 0.35
            + criteria_score * 0.30
            + context_score * 0.20
            + bounds_score * 0.15
        )

        detected = overall_score < self.overall_threshold and len(issues) > 0

        # Determine severity from worst issue
        if issues:
            severity_order = {
                DelegationSeverity.SEVERE: 3,
                DelegationSeverity.MODERATE: 2,
                DelegationSeverity.MINOR: 1,
                DelegationSeverity.NONE: 0,
            }
            worst = max(issues, key=lambda i: severity_order[i.severity])
            severity = worst.severity
            primary_issue = worst.issue_type
        else:
            severity = DelegationSeverity.NONE
            primary_issue = None

        # Confidence: higher when score is clearly below threshold
        if detected:
            distance = self.overall_threshold - overall_score
            confidence = min(0.95, 0.50 + distance * 2.0)
        else:
            confidence = min(0.95, 0.50 + (overall_score - self.overall_threshold) * 2.0)

        explanation = self._build_explanation(
            specificity_score, criteria_score, context_score, bounds_score, issues
        )
        suggested_fix = self._build_fix(issues) if detected else None

        return DelegationResult(
            detected=detected,
            primary_issue=primary_issue,
            severity=severity,
            confidence=round(confidence, 3),
            specificity_score=round(specificity_score, 3),
            criteria_score=round(criteria_score, 3),
            context_score=round(context_score, 3),
            bounds_score=round(bounds_score, 3),
            issues=issues,
            explanation=explanation,
            suggested_fix=suggested_fix,
        )

    def _score_specificity(self, instruction: str) -> float:
        """Score how specific and actionable the instruction is (0-1)."""
        words = instruction.split()
        word_count = len(words)

        if word_count == 0:
            return 0.0

        # Vague phrase penalty
        vague_matches = sum(1 for p in self._vague_compiled if p.search(instruction))
        vague_ratio = vague_matches / max(1, word_count / 10)
        vague_penalty = min(0.5, vague_ratio * 0.25)

        # Specificity signal count
        specificity_matches = sum(1 for p in self._specificity_compiled if p.search(instruction))

        # Length contributes (longer instructions tend to be more specific, with diminishing returns)
        length_score = min(1.0, word_count / 30.0)

        # Specificity signal density
        signal_score = min(1.0, specificity_matches / 4.0)

        score = (length_score * 0.4 + signal_score * 0.6) - vague_penalty
        return max(0.0, min(1.0, score))

    def _score_criteria(self, instruction: str, success_criteria: str) -> float:
        """Score whether success criteria are defined (0-1)."""
        # Check explicit success_criteria field first
        if success_criteria and success_criteria.strip():
            criteria_text = success_criteria.strip()
            # Explicit criteria provided — score based on quality
            criteria_matches = sum(1 for p in self._criteria_compiled if p.search(criteria_text))
            has_numbers = bool(re.search(r"\b\d+\b", criteria_text))
            word_count = len(criteria_text.split())

            quality = min(1.0, (criteria_matches * 0.25 + (0.2 if has_numbers else 0) + min(0.3, word_count / 20)))
            return max(0.3, quality)  # Floor of 0.3 for having any explicit criteria

        # Fall back to checking instruction text for embedded criteria
        criteria_matches = sum(1 for p in self._criteria_compiled if p.search(instruction))
        has_numbers = bool(re.search(r"\b\d+\b", instruction))

        if criteria_matches >= 2 and has_numbers:
            return 0.7
        elif criteria_matches >= 1:
            return 0.4
        elif has_numbers:
            return 0.3
        return 0.0

    def _score_context(self, instruction: str, task_context: str) -> float:
        """Score context completeness (0-1)."""
        if not task_context or not task_context.strip():
            # No context provided — check if instruction is self-contained
            word_count = len(instruction.split())
            has_reasoning = bool(re.search(r"\b(?:because|since|given|due\s+to|context|background)\b", instruction, re.IGNORECASE))

            if word_count > 50 and has_reasoning:
                return 0.5  # Long self-contained instruction
            elif word_count > 30:
                return 0.3
            return 0.1

        context_words = len(task_context.split())
        instruction_words = len(instruction.split())

        # Check for entity references in instruction that appear in context
        # Extract potential entity references (capitalized words, quoted strings)
        instruction_entities = set(re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b", instruction))
        instruction_entities.update(re.findall(r'"([^"]+)"', instruction))
        instruction_entities.update(re.findall(r"'([^']+)'", instruction))

        if instruction_entities:
            entities_in_context = sum(
                1 for e in instruction_entities
                if e.lower() in task_context.lower()
            )
            entity_coverage = entities_in_context / len(instruction_entities) if instruction_entities else 0
        else:
            entity_coverage = 0.5  # No entities to check

        # Context length relative to instruction complexity
        ratio = min(1.0, context_words / max(1, instruction_words * 2))

        score = ratio * 0.4 + entity_coverage * 0.4 + (0.2 if context_words > 20 else context_words / 100)
        return max(0.0, min(1.0, score))

    def _score_bounds(self, full_text: str) -> float:
        """Score whether bounds/constraints are specified (0-1)."""
        bounds_matches = sum(1 for p in self._bounds_compiled if p.search(full_text))

        if bounds_matches >= 3:
            return 1.0
        elif bounds_matches == 2:
            return 0.7
        elif bounds_matches == 1:
            return 0.4
        return 0.0

    def _check_capability_mismatch(
        self, instruction: str, capabilities: str
    ) -> Optional[DelegationIssue]:
        """Check if the instruction requires capabilities the delegatee doesn't have."""
        # Extract action verbs from instruction
        action_pattern = re.compile(
            r"\b(deploy|delete|merge|publish|approve|access|modify|create|write|read|execute)\b",
            re.IGNORECASE,
        )
        required_actions = set(m.lower() for m in action_pattern.findall(instruction))
        available_actions = set(m.lower() for m in action_pattern.findall(capabilities))

        if not required_actions:
            return None

        missing = required_actions - available_actions
        # Only flag if capabilities are specific enough to compare
        if missing and len(available_actions) >= 2:
            return DelegationIssue(
                issue_type=DelegationIssueType.CAPABILITY_MISMATCH,
                description=f"Instruction requires actions not in delegatee capabilities: {', '.join(sorted(missing))}.",
                severity=DelegationSeverity.MODERATE,
            )
        return None

    def _build_explanation(
        self,
        specificity: float,
        criteria: float,
        context: float,
        bounds: float,
        issues: list[DelegationIssue],
    ) -> str:
        parts = []
        if not issues:
            parts.append("Delegation appears well-specified.")
        else:
            parts.append(f"Found {len(issues)} delegation quality issue(s).")

        scores = []
        if specificity < self.specificity_threshold:
            scores.append(f"specificity={specificity:.2f}")
        if criteria < self.criteria_threshold:
            scores.append(f"criteria={criteria:.2f}")
        if context < self.context_threshold:
            scores.append(f"context={context:.2f}")
        if bounds < self.bounds_threshold:
            scores.append(f"bounds={bounds:.2f}")

        if scores:
            parts.append(f"Low scores: {', '.join(scores)}.")

        return " ".join(parts)

    def _build_fix(self, issues: list[DelegationIssue]) -> str:
        suggestions = []
        issue_types = {i.issue_type for i in issues}

        if DelegationIssueType.VAGUE_INSTRUCTION in issue_types:
            suggestions.append("Replace vague phrases with specific actions and named entities.")
        if DelegationIssueType.MISSING_SUCCESS_CRITERIA in issue_types:
            suggestions.append("Add measurable success criteria (e.g., 'done when all tests pass and coverage > 80%').")
        if DelegationIssueType.INCOMPLETE_CONTEXT in issue_types:
            suggestions.append("Include relevant background context, current state, and any prior decisions.")
        if DelegationIssueType.MISSING_BOUNDS in issue_types:
            suggestions.append("Specify constraints: deadline, budget, scope limits, or escalation rules.")
        if DelegationIssueType.CAPABILITY_MISMATCH in issue_types:
            suggestions.append("Verify the delegatee has the required capabilities or permissions.")

        return " ".join(suggestions)


# Singleton instance
delegation_detector = DelegationQualityDetector()
