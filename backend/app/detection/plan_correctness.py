"""Plan Correctness Detection (DAB FM2).

Detects when an agent's plan/strategy is logically incorrect — even if
executed perfectly, it would produce the wrong answer.

Inspired by DAB (Data Agent Benchmark, arXiv:2603.20576) which found
that 40% of data agent failures come from incorrect plans:
- Missing required operations (e.g., forgetting to GROUP BY)
- Wrong aggregation strategy (averaging averages vs. averaging all rows)
- Incorrect join logic (wrong key, missing conditions)
- Irrelevant operations that produce incorrect results

Unlike the specification detector (checks spec↔intent match), this checks
whether the computational strategy itself is sound.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanIssue:
    """A specific issue found in the agent's plan."""
    issue_type: str  # missing_step, wrong_aggregation, wrong_join, irrelevant_step, circular_logic
    severity: str  # low, medium, high, critical
    description: str
    evidence: str = ""


@dataclass
class PlanCorrectnessResult:
    """Result of plan correctness analysis."""
    detected: bool
    confidence: float
    issues: List[PlanIssue] = field(default_factory=list)
    plan_steps: List[str] = field(default_factory=list)
    missing_steps: List[str] = field(default_factory=list)
    raw_score: Optional[float] = None


class PlanCorrectnessDetector:
    """Detects logically incorrect agent plans.

    Analyzes the agent's stated plan or inferred strategy for:
    1. Missing required operations (GROUP BY, JOIN, FILTER)
    2. Wrong aggregation strategy (e.g., avg of avg vs global avg)
    3. Incorrect join logic
    4. Circular or contradictory steps
    5. Irrelevant operations that corrupt results
    """

    # Keywords indicating different plan components
    AGGREGATION_OPS = {"average", "avg", "sum", "count", "max", "min", "mean", "total", "group"}
    JOIN_OPS = {"join", "merge", "combine", "match", "link", "connect", "cross-reference"}
    FILTER_OPS = {"filter", "where", "select", "only", "exclude", "limit", "having"}
    TRANSFORM_OPS = {"extract", "parse", "convert", "transform", "format", "split", "regex"}

    def detect(
        self,
        plan: str,
        task: str,
        executed_steps: Optional[List[Dict[str, Any]]] = None,
        expected_operations: Optional[List[str]] = None,
    ) -> PlanCorrectnessResult:
        """Analyze an agent's plan for logical correctness.

        Args:
            plan: The agent's stated plan or reasoning
            task: The original task/query
            executed_steps: Optional list of actually executed steps
            expected_operations: Optional list of required operation types
        """
        issues = []
        plan_lower = plan.lower()
        task_lower = task.lower()

        # Extract plan steps
        plan_steps = self._extract_plan_steps(plan)

        # Check 1: Missing required operations
        missing = self._check_missing_operations(task_lower, plan_lower, expected_operations)
        for m in missing:
            issues.append(PlanIssue(
                issue_type="missing_step",
                severity="high",
                description=f"Plan missing required operation: {m}",
                evidence=f"Task requires '{m}' but plan doesn't include it",
            ))

        # Check 2: Wrong aggregation strategy
        agg_issues = self._check_aggregation_errors(task_lower, plan_lower)
        issues.extend(agg_issues)

        # Check 3: Incorrect join logic
        join_issues = self._check_join_logic(task_lower, plan_lower)
        issues.extend(join_issues)

        # Check 4: Circular/contradictory steps
        circular = self._check_circular_logic(plan_steps)
        issues.extend(circular)

        # Check 5: Irrelevant operations
        if executed_steps:
            irrelevant = self._check_irrelevant_steps(task_lower, executed_steps)
            issues.extend(irrelevant)

        # Score
        if not issues:
            return PlanCorrectnessResult(
                detected=False, confidence=0.0, plan_steps=plan_steps,
            )

        severity_weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2}
        max_severity = max(severity_weights.get(i.severity, 0.3) for i in issues)
        confidence = min(1.0, max_severity * (1 + 0.1 * (len(issues) - 1)))

        return PlanCorrectnessResult(
            detected=True,
            confidence=round(confidence, 4),
            issues=issues,
            plan_steps=plan_steps,
            missing_steps=[i.description for i in issues if i.issue_type == "missing_step"],
            raw_score=confidence,
        )

    def _extract_plan_steps(self, plan: str) -> List[str]:
        """Extract numbered or bulleted steps from plan text."""
        steps = []
        for line in plan.split("\n"):
            line = line.strip()
            if re.match(r"^\d+[\.\)]\s", line) or re.match(r"^[-•*]\s", line):
                steps.append(line)
            elif line.startswith("Step ") or line.startswith("First,") or line.startswith("Then,"):
                steps.append(line)
        return steps if steps else [plan[:200]]

    def _check_missing_operations(
        self, task: str, plan: str, expected: Optional[List[str]]
    ) -> List[str]:
        """Check if required operations are missing from the plan."""
        missing = []

        if expected:
            for op in expected:
                if op.lower() not in plan:
                    missing.append(op)
            return missing

        # Infer required operations from task
        if any(w in task for w in ("average", "avg", "mean")):
            if not any(w in plan for w in self.AGGREGATION_OPS):
                missing.append("aggregation (average/mean)")

        if any(w in task for w in ("across", "from both", "combine", "join", "multiple")):
            if not any(w in plan for w in self.JOIN_OPS):
                missing.append("join/merge across sources")

        if any(w in task for w in ("filter", "where", "only", "specific", "particular")):
            if not any(w in plan for w in self.FILTER_OPS):
                missing.append("filtering/selection")

        if any(w in task for w in ("extract", "parse", "from text", "from description")):
            if not any(w in plan for w in self.TRANSFORM_OPS):
                missing.append("text extraction/transformation")

        if any(w in task for w in ("group", "by category", "per", "each")):
            if "group" not in plan:
                missing.append("grouping operation")

        if any(w in task for w in ("sort", "rank", "top", "highest", "lowest", "best")):
            if not any(w in plan for w in ("sort", "order", "rank", "top")):
                missing.append("sorting/ranking")

        return missing

    def _check_aggregation_errors(self, task: str, plan: str) -> List[PlanIssue]:
        """Check for common aggregation mistakes."""
        issues = []

        # Average of averages (a common DAB FM2 error)
        if "average" in task:
            if "average" in plan and "per" in plan and "then average" in plan:
                issues.append(PlanIssue(
                    issue_type="wrong_aggregation",
                    severity="critical",
                    description="Possible average-of-averages error: computing per-group averages then averaging them produces wrong results",
                    evidence="Should compute global average directly, not average of group averages",
                ))

        # Count distinct vs count all
        if any(w in task for w in ("how many unique", "how many different", "distinct")):
            if "count" in plan and "distinct" not in plan and "unique" not in plan:
                issues.append(PlanIssue(
                    issue_type="wrong_aggregation",
                    severity="high",
                    description="Task asks for distinct/unique count but plan may count all (including duplicates)",
                ))

        return issues

    def _check_join_logic(self, task: str, plan: str) -> List[PlanIssue]:
        """Check for join logic errors."""
        issues = []

        # Task mentions multiple sources but plan doesn't join
        source_indicators = sum(1 for w in ("database", "table", "source", "system") if w in task)
        if source_indicators >= 2 and not any(w in plan for w in self.JOIN_OPS):
            issues.append(PlanIssue(
                issue_type="wrong_join",
                severity="high",
                description="Task references multiple data sources but plan doesn't include a join operation",
            ))

        return issues

    def _check_circular_logic(self, steps: List[str]) -> List[PlanIssue]:
        """Check for circular or contradictory plan steps."""
        issues = []

        # Check for steps that undo each other
        for i, step in enumerate(steps):
            for j, other in enumerate(steps[i+1:], i+1):
                step_lower = step.lower()
                other_lower = other.lower()
                # Filter then unfilter
                if "filter" in step_lower and "all" in other_lower and "remove filter" not in other_lower:
                    pass  # Not necessarily circular
                # Same operation repeated
                if step_lower == other_lower and len(step_lower) > 20:
                    issues.append(PlanIssue(
                        issue_type="circular_logic",
                        severity="medium",
                        description=f"Duplicate step: step {i+1} and step {j+1} are identical",
                    ))

        return issues

    def _check_irrelevant_steps(
        self, task: str, steps: List[Dict]
    ) -> List[PlanIssue]:
        """Check for steps that don't contribute to the task."""
        issues = []
        task_words = set(task.split())

        for i, step in enumerate(steps):
            step_desc = str(step.get("description", step.get("action", str(step))))[:200].lower()
            # If step has no overlap with task keywords, it might be irrelevant
            step_words = set(step_desc.split())
            overlap = len(task_words & step_words)
            if overlap == 0 and len(step_desc) > 20:
                issues.append(PlanIssue(
                    issue_type="irrelevant_step",
                    severity="low",
                    description=f"Step {i+1} may be irrelevant to the task",
                    evidence=f"No keyword overlap between task and step: '{step_desc[:60]}'",
                ))

        return issues


# Singleton
plan_correctness_detector = PlanCorrectnessDetector()
