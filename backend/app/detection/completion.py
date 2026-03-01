"""
F14: Completion Misjudgment Detection (MAST Taxonomy)
=====================================================

Detects when an agent incorrectly determines task completion.
This occurs in task verification when:
- Agent claims task is complete when it's not
- Agent delivers partial results as final
- Agent ignores incomplete subtasks
- Agent misses success criteria

Version History:
- v1.0: Initial implementation with explicit marker detection
- v1.1: Improved detection for adversarial cases:
  - Quantitative requirement detection ("all", "every", "complete")
  - Partial completeness hedges ("most", "core", "90%")
  - Qualifier detection ("appears", "seems", "on the surface")
  - Implicit completion claims (confident delivery)
- v1.2: Enhanced for Phase 2 adversarial accuracy:
  - More implicit completion patterns (comprehensive, fully covered)
  - Detection without explicit completion claim for quant requirements
  - "Planned" and "future" work detection as incomplete
  - Task-aware detection (MVP/prototype exemptions)
- v1.3: Phase 2 adversarial fixes:
  - Fixed percentage pattern regex (80% now matches)
  - JSON completion claim detection ("status": "complete")
  - JSON incomplete indicator detection ("documented": false)
  - Numeric ratio detection (8/10, documentedEndpoints: 8, total: 10)
  - Uncertainty language detection ("lingering", "might have missed")
- v1.5: Improved recall for quantitative-requirement tasks:
  - Structural incompleteness detection (list item count, missing sections)
  - Structural incompleteness registered as ensemble signal category
  - Quantitative-requirement exemption from 2-signal ensemble gate
"""

# Detector version for tracking
DETECTOR_VERSION = "1.5"
DETECTOR_NAME = "CompletionMisjudgmentDetector"

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
        # v1.7: Tightened subject patterns — only match task/work nouns, not any word
        r'\b(?:migration|implementation|setup|integration|feature|system|module|service|component|api|app|application|build|deployment|test|testing|code|refactor|fix|update|upgrade)\s+(?:is\s+)?(?:complete|completed|done|ready|finished|implemented|working|set up|configured|live)\b',
        r'\b(?:done|complete|completed|ready|finished|implemented)\s*[!.]',
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

    # v1.1: Words in task that require 100% completion
    QUANTITATIVE_REQUIREMENTS = [
        "all", "every", "each", "complete", "full", "entire",
        "comprehensive", "thorough", "exhaustive", "total",
    ]

    # v1.1: Patterns indicating partial/incomplete work (hedges)
    PARTIAL_COMPLETION_PATTERNS = [
        (r'\b(?:most|majority|mainly|primarily|largely)\b', "partial_scope"),
        (r'\b(?:core|main|primary|key|essential)\s+(?:functionality|features?|parts?)\b', "core_only"),
        (r'\b(?:basic|minimal|initial|preliminary)\b', "minimal_scope"),
        (r'\b\d{1,2}%', "percentage_incomplete"),  # v1.3: Fixed - removed trailing \b (% is not word char)
        (r'\b(?:some|several|few|certain)\s+(?:of|aspects?|parts?|areas?)\b', "partial_coverage"),
        (r'\b(?:focus(?:ed|ing)?|priorit(?:ized?|izing))\s+on\b', "selective_focus"),
        (r'\b(?:for now|at this point|currently|at the moment)\b', "temporal_limitation"),
        (r'\b(?:happy path|common case|typical scenario)\b', "limited_coverage"),
        # v1.3: Uncertainty language indicating incomplete
        (r'\b(?:lingering|might have missed|could still|probably missed)\b', "uncertainty_incomplete"),
        (r'\b(?:couple of|few more|some more)\s+(?:edge cases?|cases?|tests?|items?)\b', "acknowledged_gaps"),
    ]

    # v1.1: Qualifier patterns that suggest uncertainty about completion
    QUALIFIER_PATTERNS = [
        (r'\b(?:appears?|seems?|looks?)\s+(?:to be\s+)?(?:complete|done|finished|solid|good)\b', "appearance_qualifier"),
        (r'\bon the surface\b', "surface_qualifier"),
        (r'\b(?:should|might|could)\s+(?:be\s+)?(?:complete|working|functional)\b', "uncertainty_qualifier"),
        (r'\b(?:believe|think|assume)\s+(?:it\'?s?|we\'?re?|this is)\b', "belief_qualifier"),
        (r'\b(?:as far as|to the best of)\b', "limited_knowledge"),
    ]

    # v1.1: Implicit completion indicators (confident delivery without caveats)
    CONFIDENT_DELIVERY_PATTERNS = [
        r'\b(?:i\'ve|we\'ve|i have|we have)\s+(?:completed|finished|done|implemented)\b',
        r'\b(?:successfully|thoroughly|fully)\s+(?:completed|implemented|deployed)\b',
        r'\b(?:the|this)\s+(?:implementation|feature|system)\s+is\s+(?:ready|complete|done)\b',
        r'\bjust wrapped up\b',
        # v1.2: Additional implicit completion patterns
        r'\bfully\s+covered\b',
        r'\b(?:all|every)\s+(?:main|major|key|critical)\s+(?:modules?|components?|features?|endpoints?)\b',
        r'\b(?:operational|ready)\s+(?:and\s+ready\s+)?for\s+(?:review|deployment|production)\b',
        r'\b(?:we\'ve|i\'ve)\s+(?:pushed|deployed|shipped|released)\b',
        r'\bin\s+place\b',  # "monitoring in place"
    ]

    # v1.2: Progress language that implies work is ongoing (NOT complete)
    # These are NOT completion claims - they indicate partial progress
    PROGRESS_NOT_COMPLETE_PATTERNS = [
        r'\bgreat progress\b',
        r'\bgood progress\b',
        r'\bmaking progress\b',
        r'\bprogressing\s+(?:well|nicely)\b',
        r'\bcoming\s+along\b',
        r'\bcomprehensive\s+(?:overview|coverage)\b',  # overview != complete
    ]

    # v1.2: Patterns indicating planned/future work (not actually complete)
    PLANNED_WORK_PATTERNS = [
        (r'\b(?:coverage|tests?|testing)\s+planned\b', "planned_tests"),
        (r'\bwill\s+(?:be\s+)?(?:added|implemented|included|covered)\b', "future_work"),
        (r'\b(?:next|later|future)\s+(?:phase|step|iteration)\b', "deferred_work"),
        (r'\b(?:to\s+be|tbd|coming\s+soon)\b', "pending_work"),
        (r'\b(?:placeholder|stub|mock)\s+(?:test|coverage|implementation)?\b', "stub_work"),
    ]

    # v1.2: Task types that are intentionally scoped (avoid false positives)
    SCOPED_TASK_PATTERNS = [
        r'\b(?:prototype|mvp|poc|proof\s+of\s+concept)\b',
        r'\b(?:quick|initial|rough|first)\s+(?:draft|version|pass|attempt)\b',
        r'\b(?:minimal|basic)\s+(?:version|implementation)\b',
        r'\bv0(?:\.\d+)?\b',  # v0.1, v0.2, etc.
    ]

    # v1.3: JSON-specific completion claim patterns
    JSON_COMPLETION_PATTERNS = [
        r'"status"\s*:\s*"[^"]*(?:complete|done|finished)[^"]*"',
        r'"(?:is_complete|completed|finished|done)"\s*:\s*true',
        r'"state"\s*:\s*"[^"]*(?:complete|success)[^"]*"',
    ]

    # v1.3: JSON-specific incomplete indicator patterns
    JSON_INCOMPLETE_PATTERNS = [
        (r'"(?:documented|hasExamples?|completed|done|tested|covered|implemented)"\s*:\s*false', "json_false_flag"),
        (r'"(?:missing|pending|todo|incomplete)"\s*:\s*\[', "json_missing_list"),
        (r'"(?:coverage|completion)"\s*:\s*"?\d{1,2}%"?', "json_partial_coverage"),
    ]

    # v1.3: Numeric ratio patterns (e.g., "8/10", "documented: 8, total: 10")
    NUMERIC_RATIO_PATTERNS = [
        (r'(\d+)\s*/\s*(\d+)', "explicit_ratio"),  # 8/10
        (r'(\d+)\s+(?:of|out of)\s+(\d+)', "explicit_count"),  # 8 of 10
        (r'"(?:documented|completed|done|tested)(?:Endpoints?|Items?|Tasks?)?"\s*:\s*(\d+).*?"(?:total)(?:Endpoints?|Items?|Tasks?)?"\s*:\s*(\d+)', "json_ratio"),
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

    def _has_quantitative_requirement(self, task: str) -> bool:
        """v1.1: Check if task requires 100% completion."""
        task_lower = task.lower()
        return any(req in task_lower for req in self.QUANTITATIVE_REQUIREMENTS)

    def _detect_partial_completion(self, text: str) -> List[tuple]:
        """v1.1: Detect hedges indicating partial completion."""
        indicators = []
        for pattern, indicator_type in self.PARTIAL_COMPLETION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                indicators.append((match.group(), indicator_type, context))
        return indicators

    def _detect_qualifiers(self, text: str) -> List[tuple]:
        """v1.1: Detect uncertainty qualifiers."""
        qualifiers = []
        for pattern, qualifier_type in self.QUALIFIER_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                qualifiers.append((match.group(), qualifier_type, context))
        return qualifiers

    def _detect_confident_delivery(self, text: str) -> bool:
        """v1.1: Detect implicit completion via confident delivery."""
        for pattern in self.CONFIDENT_DELIVERY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_planned_work(self, text: str) -> List[tuple]:
        """v1.2: Detect indicators of planned/future work (not actually complete)."""
        indicators = []
        for pattern, indicator_type in self.PLANNED_WORK_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                indicators.append((match.group(), indicator_type, context))
        return indicators

    def _is_intentionally_scoped_task(self, task: str) -> bool:
        """v1.2: Check if task is intentionally scoped (MVP, prototype, etc.)."""
        task_lower = task.lower()
        for pattern in self.SCOPED_TASK_PATTERNS:
            if re.search(pattern, task_lower):
                return True
        return False

    def _detect_progress_language(self, text: str) -> bool:
        """v1.2: Detect progress language that implies work is ongoing (not complete)."""
        for pattern in self.PROGRESS_NOT_COMPLETE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_json_completion_claim(self, text: str) -> bool:
        """v1.3: Detect completion claims in JSON/structured output."""
        for pattern in self.JSON_COMPLETION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_json_incomplete(self, text: str) -> List[tuple]:
        """v1.3: Detect incomplete indicators in JSON/structured output."""
        indicators = []
        for pattern, indicator_type in self.JSON_INCOMPLETE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                indicators.append((match.group(), indicator_type, context))
        return indicators

    def _detect_numeric_ratio(self, text: str) -> Optional[tuple]:
        """v1.3: Detect numeric ratios indicating partial completion (e.g., 8/10).

        Returns:
            tuple: (completed, total, ratio) if found, None otherwise
        """
        for pattern, ratio_type in self.NUMERIC_RATIO_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                try:
                    if ratio_type == "json_ratio":
                        completed = int(match.group(1))
                        total = int(match.group(2))
                    else:
                        completed = int(match.group(1))
                        total = int(match.group(2))

                    # Only flag if ratio is less than 100%
                    if total > 0 and completed < total:
                        ratio = completed / total
                        return (completed, total, ratio)
                except (ValueError, IndexError):
                    continue
        return None

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

    def _detect_structural_incompleteness(self, task: str, output: str) -> list:
        """Detect structural incompleteness in the output.

        Checks whether the output satisfies explicit numeric or sectional
        requirements mentioned in the task description.
        """
        issues: list = []

        # Check for requested list item count
        count_patterns = [
            r'(?:list|provide|give|name|identify|enumerate)\s+(\d+)',
            r'(\d+)\s+(?:items|examples|points|reasons|steps|features|recommendations)',
            r'top\s+(\d+)',
        ]

        requested_count = None
        for pattern in count_patterns:
            match = re.search(pattern, task.lower())
            if match:
                requested_count = int(match.group(1))
                break

        if requested_count and requested_count > 1:
            # Count actual list items in output
            bullet_pattern = r'(?:^|\n)\s*(?:\d+[\.\/\)]\s|[-*\u2022]\s)'
            actual_items = len(re.findall(bullet_pattern, output))

            if actual_items > 0 and actual_items < requested_count:
                ratio = actual_items / requested_count
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                    description=f"Task requests {requested_count} items but output contains only {actual_items}",
                    severity=CompletionSeverity.MODERATE if ratio >= 0.5 else CompletionSeverity.SEVERE,
                    evidence=f"requested={requested_count}, actual={actual_items}, ratio={ratio:.2f}",
                ))

        # v1.5: Check for missing sections mentioned in the task
        # Look for explicit section names the task requires (e.g., "include
        # introduction, methodology, results, and conclusion")
        section_patterns = [
            # "include X, Y, and Z sections"
            r'(?:include|cover|write|add|provide|create)\s+(?:a\s+)?(?:sections?\s+(?:on|for|about)\s+)?(.+?)(?:\s+section[s]?)?(?:\.|$)',
            # "sections: X, Y, Z"
            r'sections?\s*:\s*(.+?)(?:\.|$)',
        ]

        task_lower = task.lower()
        output_lower = output.lower()

        for pattern in section_patterns:
            match = re.search(pattern, task_lower)
            if match:
                # Extract potential section names from comma/and-separated list
                section_text = match.group(1)
                # Split on commas and "and"
                parts = re.split(r',\s*|\s+and\s+', section_text)
                # Filter to reasonable section names (2-40 chars, no full sentences)
                section_names = [
                    p.strip().strip('"\'')
                    for p in parts
                    if 2 <= len(p.strip()) <= 40 and ' is ' not in p and ' are ' not in p
                ]
                if len(section_names) >= 2:
                    missing = [
                        s for s in section_names
                        if s not in output_lower
                    ]
                    if missing and len(missing) < len(section_names):
                        # Some sections present, some missing — partial delivery
                        issues.append(CompletionIssue(
                            issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                            description=f"Task mentions sections but {len(missing)} missing from output: {', '.join(missing[:3])}",
                            severity=CompletionSeverity.MODERATE,
                            evidence=f"required={len(section_names)}, missing={len(missing)}",
                        ))
                    break  # Only use the first matching pattern

        return issues

    def _detect_enumerated_coverage(self, task: str, output: str) -> list:
        """Detect when task enumerates specific items (A, B, and C) but output
        only covers a subset."""
        issues: list = []

        # Extract enumerated items from task:
        #   "with Google, GitHub, and Microsoft"
        #   "including login, logout, and token refresh"
        #   "for CSV, JSON, and PDF formats"
        enum_patterns = [
            r'(?:with|including|for|supporting|using|like)\s+(.+?)(?:\.|$)',
            r'(?:implement|build|create|add|set up)\s+(.+?)(?:\.|$)',
        ]

        task_lower = task.lower()
        output_lower = output.lower()

        for pattern in enum_patterns:
            match = re.search(pattern, task_lower)
            if not match:
                continue
            fragment = match.group(1)
            # Split on commas and "and"
            parts = re.split(r',\s*|\s+and\s+', fragment)
            # Filter to meaningful items (2+ chars, not common filler words)
            items = [
                p.strip() for p in parts
                if len(p.strip()) >= 2 and p.strip() not in (
                    'the', 'a', 'an', 'all', 'each', 'every', 'other',
                )
            ]
            if len(items) >= 3:
                found = sum(1 for item in items if item in output_lower)
                if found < len(items):
                    missing = [i for i in items if i not in output_lower]
                    severity = (
                        CompletionSeverity.SEVERE if found == 0
                        else CompletionSeverity.MODERATE
                    )
                    issues.append(CompletionIssue(
                        issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                        description=(
                            f"Task enumerates {len(items)} items but output "
                            f"only covers {found}: missing {', '.join(missing[:3])}"
                        ),
                        severity=severity,
                        evidence=f"items={items}, found={found}",
                    ))
                    break  # One match is enough

        return issues

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

        # Check if agent claims completion (explicit or implicit)
        completion_claimed = self._detect_completion_claim(agent_output)

        # v1.1: Check for implicit completion via confident delivery
        confident_delivery = self._detect_confident_delivery(agent_output)
        if confident_delivery and not completion_claimed:
            completion_claimed = True  # Treat confident delivery as implicit claim

        # v1.3: Check for JSON-specific completion claims
        json_completion = self._detect_json_completion_claim(agent_output)
        if json_completion and not completion_claimed:
            completion_claimed = True  # Treat JSON completion status as claim

        # Detect incomplete markers
        incomplete_markers = self._detect_incomplete_markers(agent_output)

        # v1.3: Detect JSON-specific incomplete indicators
        json_incomplete = self._detect_json_incomplete(agent_output)

        # v1.3: Detect numeric ratios (e.g., 8/10)
        numeric_ratio = self._detect_numeric_ratio(agent_output)

        # Detect errors
        errors = self._detect_errors(agent_output)

        # v1.1: Detect partial completion hedges and qualifiers
        has_quant_req = self._has_quantitative_requirement(task)
        partial_indicators = self._detect_partial_completion(agent_output)
        qualifiers = self._detect_qualifiers(agent_output)

        # v1.2: Detect planned/future work indicators and check for scoped tasks
        planned_work = self._detect_planned_work(agent_output)
        is_scoped_task = self._is_intentionally_scoped_task(task)
        has_progress_language = self._detect_progress_language(agent_output)

        # Calculate completion ratio
        completion_ratio = self._calculate_completion_ratio(agent_output, task)

        # v1.1: Penalize completion ratio if partial indicators found with quantitative requirement
        if has_quant_req and partial_indicators:
            penalty = min(0.3, len(partial_indicators) * 0.1)
            completion_ratio = max(0.0, completion_ratio - penalty)

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

        # v1.1: Check for partial completion with quantitative requirement
        if has_quant_req and partial_indicators and completion_claimed:
            for indicator, indicator_type, context in partial_indicators[:2]:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                    description=f"Task requires 100% but output indicates partial: '{indicator}'",
                    severity=CompletionSeverity.MODERATE,
                    evidence=context,
                ))

        # v1.1: Check for uncertainty qualifiers with completion claim
        if qualifiers and completion_claimed:
            for qualifier, qualifier_type, context in qualifiers[:2]:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.INCOMPLETE_VERIFICATION,
                    description=f"Uncertainty qualifier suggests incomplete: '{qualifier}'",
                    severity=CompletionSeverity.MINOR,
                    evidence=context,
                ))

        # v1.2: Check for planned/future work (indicates incomplete even with completion claim)
        if planned_work and completion_claimed:
            for indicator, indicator_type, context in planned_work[:2]:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.PREMATURE_COMPLETION,
                    description=f"Work marked as planned/future but completion claimed: '{indicator}'",
                    severity=CompletionSeverity.MODERATE,
                    evidence=context,
                ))

        # v1.2: For quantitative requirements, detect failure even without explicit claim
        # If task requires "all" and output shows partial work, that's a failure
        if has_quant_req and not is_scoped_task and not completion_claimed:
            # Check if there are partial indicators or qualifiers
            if partial_indicators:
                for indicator, indicator_type, context in partial_indicators[:2]:
                    issues.append(CompletionIssue(
                        issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                        description=f"Task requires 100% completion but partial work indicated: '{indicator}'",
                        severity=CompletionSeverity.MODERATE,
                        evidence=context,
                    ))
            if qualifiers:
                for qualifier, qualifier_type, context in qualifiers[:2]:
                    issues.append(CompletionIssue(
                        issue_type=CompletionIssueType.INCOMPLETE_VERIFICATION,
                        description=f"Task requires certainty but uncertainty expressed: '{qualifier}'",
                        severity=CompletionSeverity.MODERATE,
                        evidence=context,
                    ))
            # v1.2: Progress language without completion = not done
            if has_progress_language:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.PREMATURE_COMPLETION,
                    description="Task requires 100% but uses progress language (implies ongoing work)",
                    severity=CompletionSeverity.MODERATE,
                    evidence="Progress language detected without explicit completion claim",
                ))

        # v1.3: Check for JSON incomplete indicators with completion claim
        if completion_claimed and json_incomplete:
            for indicator, indicator_type, context in json_incomplete[:2]:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                    description=f"JSON output shows incomplete items: '{indicator}'",
                    severity=CompletionSeverity.MODERATE,
                    evidence=context,
                ))

        # v1.3: Check for numeric ratios showing incomplete (with or without completion claim)
        if numeric_ratio and has_quant_req and not is_scoped_task:
            completed, total, ratio = numeric_ratio
            if ratio < 1.0:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                    description=f"Task requires 100% but output shows {completed}/{total} ({ratio*100:.0f}%)",
                    severity=CompletionSeverity.MODERATE,
                    evidence=f"Numeric ratio detected: {completed}/{total}",
                ))

        # v1.3: JSON incomplete without explicit claim but with quantitative requirement
        if json_incomplete and has_quant_req and not is_scoped_task and not completion_claimed:
            for indicator, indicator_type, context in json_incomplete[:2]:
                issues.append(CompletionIssue(
                    issue_type=CompletionIssueType.PARTIAL_DELIVERY,
                    description=f"Task requires 100% but JSON shows incomplete: '{indicator}'",
                    severity=CompletionSeverity.MODERATE,
                    evidence=context,
                ))

        # v1.5: Detect structural incompleteness (e.g., fewer list items than requested)
        structural_issues = self._detect_structural_incompleteness(task, agent_output)
        if structural_issues:
            issues.extend(structural_issues)

        # v1.5: Detect enumerated items coverage gap
        enum_issues = self._detect_enumerated_coverage(task, agent_output)
        if enum_issues:
            issues.extend(enum_issues)

        # v1.6: Completion by absence — if task has explicit criteria
        # and output addresses fewer than half, flag even without claim
        if criteria_total > 0 and criteria_met < criteria_total * 0.5 and not is_scoped_task:
            issues.append(CompletionIssue(
                issue_type=CompletionIssueType.MISSED_CRITERIA,
                description=f"Output addresses only {criteria_met}/{criteria_total} success criteria",
                severity=CompletionSeverity.MODERATE,
                evidence=f"Unmet: {', '.join(unmet_criteria[:3])}",
            ))

        # v1.2: Reduce false positives for scoped tasks
        if is_scoped_task and issues:
            # Filter out minor issues for intentionally scoped tasks
            issues = [i for i in issues if i.severity in [
                CompletionSeverity.SEVERE, CompletionSeverity.CRITICAL
            ]]

        # v1.4: Ensemble voting — require 2+ distinct signal categories
        # to trigger detection for non-critical issues.  A single signal
        # category (e.g., only "partial_indicators" without a completion
        # claim) produces too many false positives.
        distinct_issue_types = set(i.issue_type for i in issues)
        max_issue_severity = max(
            (i.severity for i in issues), default=CompletionSeverity.NONE
        )
        if issues and max_issue_severity not in [
            CompletionSeverity.SEVERE, CompletionSeverity.CRITICAL
        ]:
            # Count distinct signal categories (not just issue types)
            signal_categories = set()
            if completion_claimed:
                signal_categories.add("completion_claim")
            if incomplete_markers:
                signal_categories.add("incomplete_markers")
            if partial_indicators:
                signal_categories.add("partial_indicators")
            if qualifiers:
                signal_categories.add("qualifiers")
            if numeric_ratio and numeric_ratio[2] < 1.0:
                signal_categories.add("numeric_ratio")
            if json_incomplete:
                signal_categories.add("json_incomplete")
            if planned_work:
                signal_categories.add("planned_work")
            if errors:
                signal_categories.add("errors")
            if incomplete_subtasks:
                signal_categories.add("incomplete_subtasks")
            if structural_issues:
                signal_categories.add("structural_incompleteness")
            if enum_issues:
                signal_categories.add("enumerated_coverage")

            # v1.5: Exempt quantitative-requirement cases: a single strong signal
            # (partial_indicators, numeric_ratio, or structural_incompleteness)
            # is sufficient when the task has explicit numeric requirements.
            has_quant_exemption = has_quant_req and (
                "partial_indicators" in signal_categories
                or "numeric_ratio" in signal_categories
                or "incomplete_subtasks" in signal_categories
                or "structural_incompleteness" in signal_categories
                or "enumerated_coverage" in signal_categories
            )
            # Enumerated coverage + completion claim is always strong enough
            if "enumerated_coverage" in signal_categories and "completion_claim" in signal_categories:
                has_quant_exemption = True
            # v1.6: Completion claim + any incompleteness signal is strong
            if "completion_claim" in signal_categories and (
                "incomplete_markers" in signal_categories
                or "planned_work" in signal_categories
                or "errors" in signal_categories
                or "json_incomplete" in signal_categories
            ):
                has_quant_exemption = True
            # v1.6: Structural or enumerated coverage alone is strong evidence
            if "structural_incompleteness" in signal_categories or "enumerated_coverage" in signal_categories:
                has_quant_exemption = True

            if len(signal_categories) < 2 and not has_quant_exemption:
                issues = []  # Suppress detection — single signal insufficient

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

        # Calculate confidence based on evidence strength and signal diversity
        signal_count = sum([
            bool(completion_claimed),
            bool(incomplete_markers),
            bool(errors),
            bool(incomplete_subtasks),
            bool(partial_indicators),
            bool(planned_work),
            bool(structural_issues),
            bool(enum_issues),
            bool(numeric_ratio and numeric_ratio[2] < 1.0),
            bool(json_incomplete),
        ])
        if signal_count >= 4:
            base_confidence = 0.85
        elif signal_count >= 3:
            base_confidence = 0.75
        elif signal_count >= 2:
            base_confidence = 0.65
        else:
            base_confidence = 0.55
        # Boost for severe issues
        if any(i.severity in (CompletionSeverity.SEVERE, CompletionSeverity.CRITICAL) for i in issues):
            base_confidence = max(base_confidence, 0.75)
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
