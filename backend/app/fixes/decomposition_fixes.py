"""Fix generators for poor decomposition detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class DecompositionFixGenerator(BaseFixGenerator):
    """Generates fixes for poor task decomposition detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type in ("poor_decomposition", "decomposition")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._task_decomposer_fix(detection_id, details, context))
        fixes.append(self._subtask_validator_fix(detection_id, details, context))
        fixes.append(self._progress_monitoring_fix(detection_id, details, context))

        return fixes

    def _task_decomposer_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class SubtaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Subtask:
    """A single subtask within a decomposed task."""
    subtask_id: str
    title: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    status: SubtaskStatus = SubtaskStatus.PENDING
    expected_output_keys: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None

    @property
    def is_ready(self) -> bool:
        """A subtask is ready when all dependencies are satisfied."""
        return self.status == SubtaskStatus.PENDING and not self.dependencies


@dataclass
class DecompositionPlan:
    """A structured decomposition plan for a complex task."""
    plan_id: str
    original_task: str
    subtasks: List[Subtask] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class StructuredTaskDecomposer:
    """
    Forces a structured decomposition step before task execution.
    Ensures complex tasks are broken down into well-defined subtasks
    with explicit dependencies and output expectations.
    """

    def __init__(self, min_subtasks: int = 2, max_subtasks: int = 10):
        self._min_subtasks = min_subtasks
        self._max_subtasks = max_subtasks

    def build_decomposition_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """Build a prompt that instructs the LLM to decompose a task."""
        context_str = ""
        if context:
            items = [f"- {k}: {str(v)[:150]}" for k, v in context.items()]
            context_str = "\\nRelevant context:\\n" + "\\n".join(items)

        return f"""Decompose the following task into {self._min_subtasks}-{self._max_subtasks} subtasks.

TASK: {task}
{context_str}

For each subtask provide:
1. title: Short descriptive name
2. description: What needs to be done
3. dependencies: List of subtask titles this depends on (empty if none)
4. expected_output_keys: What data keys this subtask produces
5. suggested_agent: Which type of agent should handle this

Output as JSON array of subtask objects.
Ensure subtasks are ordered so dependencies come before dependents.
Each subtask should be atomic and independently verifiable."""

    def parse_decomposition(self, llm_output: List[Dict[str, Any]]) -> DecompositionPlan:
        """Parse LLM decomposition output into a structured plan."""
        plan_id = str(uuid.uuid4())
        subtasks = []
        title_to_id: Dict[str, str] = {}

        # First pass: create subtasks and map titles to IDs
        for item in llm_output:
            subtask_id = str(uuid.uuid4())
            title = item.get("title", f"subtask_{len(subtasks) + 1}")
            title_to_id[title] = subtask_id

            subtasks.append(Subtask(
                subtask_id=subtask_id,
                title=title,
                description=item.get("description", ""),
                dependencies=[],  # resolved in second pass
                assigned_agent=item.get("suggested_agent"),
                expected_output_keys=item.get("expected_output_keys", []),
            ))

        # Second pass: resolve dependencies by title
        for i, item in enumerate(llm_output):
            dep_titles = item.get("dependencies", [])
            subtasks[i].dependencies = [
                title_to_id[t] for t in dep_titles if t in title_to_id
            ]

        # Validate no circular dependencies
        if self._has_circular_deps(subtasks):
            logger.warning("Circular dependencies detected in decomposition, removing cycles")
            self._break_cycles(subtasks)

        plan = DecompositionPlan(
            plan_id=plan_id,
            original_task="",
            subtasks=subtasks,
        )

        logger.info(f"Decomposed task into {len(subtasks)} subtasks (plan={plan_id[:8]})")
        return plan

    def get_ready_subtasks(self, plan: DecompositionPlan) -> List[Subtask]:
        """Get subtasks that are ready to execute (dependencies satisfied)."""
        completed_ids = {
            s.subtask_id for s in plan.subtasks
            if s.status == SubtaskStatus.COMPLETED
        }
        ready = []
        for subtask in plan.subtasks:
            if subtask.status != SubtaskStatus.PENDING:
                continue
            unmet = [d for d in subtask.dependencies if d not in completed_ids]
            if not unmet:
                ready.append(subtask)
        return ready

    def _has_circular_deps(self, subtasks: List[Subtask]) -> bool:
        """Check for circular dependencies using DFS."""
        id_to_deps = {s.subtask_id: set(s.dependencies) for s in subtasks}
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for dep in id_to_deps.get(node, set()):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        return any(dfs(s.subtask_id) for s in subtasks if s.subtask_id not in visited)

    def _break_cycles(self, subtasks: List[Subtask]):
        """Break circular dependencies by removing the last edge in each cycle."""
        for subtask in reversed(subtasks):
            if subtask.dependencies:
                subtask.dependencies = subtask.dependencies[:1]'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="poor_decomposition",
            fix_type=FixType.TASK_DECOMPOSER,
            confidence=FixConfidence.HIGH,
            title="Add structured task decomposition step before execution",
            description="Force a structured decomposition step that breaks complex tasks into well-defined subtasks with explicit dependencies and output expectations before any agent begins execution.",
            rationale="Poor decomposition occurs when tasks are handed to agents without proper breakdown. A mandatory decomposition step with dependency tracking ensures each subtask is atomic, ordered, and independently verifiable.",
            code_changes=[
                CodeChange(
                    file_path="utils/task_decomposer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Structured task decomposer with dependency graph and execution ordering",
                )
            ],
            estimated_impact="Ensures systematic task breakdown with explicit dependencies, preventing ad-hoc decomposition failures",
            tags=["decomposition", "task-planning", "dependency-graph", "structure"],
        )

    def _subtask_validator_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CompletenessLevel(Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    EMPTY = "empty"


@dataclass
class SubtaskValidationResult:
    """Result of validating a single subtask output."""
    subtask_id: str
    completeness: CompletenessLevel
    present_keys: List[str]
    missing_keys: List[str]
    quality_score: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)


@dataclass
class DecompositionValidationReport:
    """Full validation report for a decomposition plan."""
    plan_id: str
    total_subtasks: int
    validated_subtasks: int
    complete_subtasks: int
    coverage_score: float  # fraction of expected outputs covered
    subtask_results: List[SubtaskValidationResult] = field(default_factory=list)
    missing_coverage: List[str] = field(default_factory=list)
    is_sufficient: bool = True


class SubtaskCompletenessValidator:
    """
    Validates that subtask outputs are complete and that the overall
    decomposition covers all aspects of the original task.
    """

    def __init__(
        self,
        min_quality_score: float = 0.6,
        min_coverage_score: float = 0.8,
    ):
        self._min_quality = min_quality_score
        self._min_coverage = min_coverage_score

    def validate_subtask_output(
        self,
        subtask_id: str,
        output: Dict[str, Any],
        expected_keys: List[str],
        required_keys: Optional[Set[str]] = None,
    ) -> SubtaskValidationResult:
        """Validate a single subtask's output for completeness."""
        present = [k for k in expected_keys if k in output]
        missing = [k for k in expected_keys if k not in output]
        issues = []

        # Check for empty or trivial values
        for key in present:
            value = output[key]
            if value is None:
                issues.append(f"Key '{key}' is present but None")
                missing.append(key)
                present.remove(key)
            elif isinstance(value, str) and len(value.strip()) == 0:
                issues.append(f"Key '{key}' is an empty string")
                missing.append(key)
                present.remove(key)
            elif isinstance(value, (list, dict)) and len(value) == 0:
                issues.append(f"Key '{key}' is an empty collection")

        # Check required keys strictly
        if required_keys:
            for req in required_keys:
                if req not in output or output[req] is None:
                    issues.append(f"Required key '{req}' is missing or null")

        # Calculate quality score
        total = len(expected_keys)
        if total == 0:
            quality = 1.0
        else:
            quality = len(present) / total

        # Determine completeness level
        if quality >= 0.95:
            completeness = CompletenessLevel.COMPLETE
        elif quality >= 0.6:
            completeness = CompletenessLevel.PARTIAL
        elif quality > 0:
            completeness = CompletenessLevel.INSUFFICIENT
        else:
            completeness = CompletenessLevel.EMPTY

        if completeness in (CompletenessLevel.INSUFFICIENT, CompletenessLevel.EMPTY):
            logger.warning(
                f"Subtask {subtask_id[:8]} output is {completeness.value}: "
                f"missing {missing}"
            )

        return SubtaskValidationResult(
            subtask_id=subtask_id,
            completeness=completeness,
            present_keys=present,
            missing_keys=missing,
            quality_score=quality,
            issues=issues,
        )

    def validate_plan_coverage(
        self,
        plan_id: str,
        subtask_results: List[SubtaskValidationResult],
        overall_expected_outputs: List[str],
        all_subtask_outputs: Dict[str, Dict[str, Any]],
    ) -> DecompositionValidationReport:
        """Validate that the complete decomposition covers the original task."""
        # Collect all output keys produced across subtasks
        all_produced_keys: Set[str] = set()
        for output in all_subtask_outputs.values():
            all_produced_keys.update(output.keys())

        # Check coverage of expected overall outputs
        covered = [k for k in overall_expected_outputs if k in all_produced_keys]
        missing = [k for k in overall_expected_outputs if k not in all_produced_keys]

        coverage = len(covered) / len(overall_expected_outputs) if overall_expected_outputs else 1.0
        complete = sum(
            1 for r in subtask_results
            if r.completeness == CompletenessLevel.COMPLETE
        )

        is_sufficient = (
            coverage >= self._min_coverage
            and all(r.quality_score >= self._min_quality for r in subtask_results)
        )

        if not is_sufficient:
            logger.warning(
                f"Decomposition plan {plan_id[:8]} insufficient: "
                f"coverage={coverage:.2%}, missing={missing}"
            )

        return DecompositionValidationReport(
            plan_id=plan_id,
            total_subtasks=len(subtask_results),
            validated_subtasks=len(subtask_results),
            complete_subtasks=complete,
            coverage_score=coverage,
            subtask_results=subtask_results,
            missing_coverage=missing,
            is_sufficient=is_sufficient,
        )'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="poor_decomposition",
            fix_type=FixType.SUBTASK_VALIDATOR,
            confidence=FixConfidence.MEDIUM,
            title="Validate subtask completeness and overall coverage",
            description="After each subtask completes, validate that its output contains all expected keys. After all subtasks complete, verify that the overall decomposition covers all aspects of the original task.",
            rationale="Poor decomposition manifests as subtasks that produce incomplete outputs or collectively fail to cover the original task requirements. Validation at both the subtask and plan level catches these gaps early.",
            code_changes=[
                CodeChange(
                    file_path="utils/subtask_validator.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Subtask completeness validator with per-subtask and plan-level coverage checking",
                )
            ],
            estimated_impact="Catches incomplete subtask outputs and coverage gaps before final assembly",
            tags=["decomposition", "validation", "completeness", "coverage"],
        )

    def _progress_monitoring_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ProgressState(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    STALLED = "stalled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubtaskProgress:
    """Tracks progress of a single subtask."""
    subtask_id: str
    title: str
    state: ProgressState = ProgressState.NOT_STARTED
    progress_pct: float = 0.0
    started_at: Optional[datetime] = None
    last_update: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    checkpoints_hit: List[str] = field(default_factory=list)


@dataclass
class PlanProgress:
    """Overall progress of a decomposition plan."""
    plan_id: str
    total_subtasks: int
    completed: int
    in_progress: int
    stalled: int
    failed: int
    overall_pct: float
    estimated_completion: Optional[datetime] = None
    stalled_subtasks: List[str] = field(default_factory=list)


class SubtaskProgressMonitor:
    """
    Monitors progress of subtasks in a decomposition plan.
    Detects stalled subtasks and provides real-time progress visibility.
    """

    def __init__(
        self,
        stall_threshold_seconds: float = 120.0,
        on_stall: Optional[Callable[[str, SubtaskProgress], None]] = None,
        on_complete: Optional[Callable[[str, SubtaskProgress], None]] = None,
    ):
        self._stall_threshold = stall_threshold_seconds
        self._on_stall = on_stall
        self._on_complete = on_complete
        self._subtasks: Dict[str, SubtaskProgress] = {}
        self._plan_id: Optional[str] = None

    def register_plan(self, plan_id: str, subtask_titles: Dict[str, str]):
        """Register a decomposition plan for monitoring."""
        self._plan_id = plan_id
        for subtask_id, title in subtask_titles.items():
            self._subtasks[subtask_id] = SubtaskProgress(
                subtask_id=subtask_id,
                title=title,
            )
        logger.info(f"Monitoring plan {plan_id[:8]} with {len(subtask_titles)} subtasks")

    def start_subtask(self, subtask_id: str):
        """Mark a subtask as started."""
        if subtask_id in self._subtasks:
            prog = self._subtasks[subtask_id]
            prog.state = ProgressState.IN_PROGRESS
            prog.started_at = datetime.utcnow()
            prog.last_update = datetime.utcnow()
            logger.info(f"Subtask started: {prog.title} ({subtask_id[:8]})")

    def update_progress(
        self, subtask_id: str, progress_pct: float, checkpoint: Optional[str] = None
    ):
        """Update progress for a subtask."""
        if subtask_id not in self._subtasks:
            return
        prog = self._subtasks[subtask_id]
        prog.progress_pct = min(progress_pct, 100.0)
        prog.last_update = datetime.utcnow()
        if prog.state == ProgressState.STALLED:
            prog.state = ProgressState.IN_PROGRESS
            logger.info(f"Subtask {prog.title} resumed from stall")
        if checkpoint:
            prog.checkpoints_hit.append(checkpoint)

    def complete_subtask(self, subtask_id: str):
        """Mark a subtask as completed."""
        if subtask_id in self._subtasks:
            prog = self._subtasks[subtask_id]
            prog.state = ProgressState.COMPLETED
            prog.progress_pct = 100.0
            prog.last_update = datetime.utcnow()
            logger.info(f"Subtask completed: {prog.title} ({subtask_id[:8]})")
            if self._on_complete:
                self._on_complete(subtask_id, prog)

    def fail_subtask(self, subtask_id: str, reason: str = ""):
        """Mark a subtask as failed."""
        if subtask_id in self._subtasks:
            prog = self._subtasks[subtask_id]
            prog.state = ProgressState.FAILED
            logger.error(f"Subtask failed: {prog.title} - {reason}")

    def check_for_stalls(self) -> List[SubtaskProgress]:
        """Check for stalled subtasks that haven't updated recently."""
        stalled = []
        now = datetime.utcnow()
        threshold = timedelta(seconds=self._stall_threshold)

        for prog in self._subtasks.values():
            if prog.state != ProgressState.IN_PROGRESS:
                continue
            if prog.last_update and (now - prog.last_update) > threshold:
                prog.state = ProgressState.STALLED
                stalled.append(prog)
                logger.warning(
                    f"Subtask stalled: {prog.title} ({prog.subtask_id[:8]}) "
                    f"- no update for {self._stall_threshold}s"
                )
                if self._on_stall:
                    self._on_stall(prog.subtask_id, prog)

        return stalled

    def get_plan_progress(self) -> PlanProgress:
        """Get overall plan progress summary."""
        total = len(self._subtasks)
        states = [p.state for p in self._subtasks.values()]
        completed = states.count(ProgressState.COMPLETED)
        in_progress = states.count(ProgressState.IN_PROGRESS)
        stalled = states.count(ProgressState.STALLED)
        failed = states.count(ProgressState.FAILED)

        overall_pct = (completed / total * 100) if total > 0 else 0.0
        stalled_ids = [
            p.title for p in self._subtasks.values()
            if p.state == ProgressState.STALLED
        ]

        return PlanProgress(
            plan_id=self._plan_id or "",
            total_subtasks=total,
            completed=completed,
            in_progress=in_progress,
            stalled=stalled,
            failed=failed,
            overall_pct=overall_pct,
            stalled_subtasks=stalled_ids,
        )'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="poor_decomposition",
            fix_type=FixType.PROGRESS_MONITORING,
            confidence=FixConfidence.MEDIUM,
            title="Track subtask progress with stall detection",
            description="Monitor progress of each subtask in the decomposition plan with real-time tracking, stall detection, and progress callbacks for visibility into execution state.",
            rationale="Poor decomposition often goes undetected until the final output is assembled. Real-time progress monitoring with stall detection provides early warning when subtasks are stuck or failing, enabling intervention before the entire plan fails.",
            code_changes=[
                CodeChange(
                    file_path="utils/progress_monitor.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Subtask progress monitor with stall detection and plan-level tracking",
                )
            ],
            estimated_impact="Provides early detection of stuck or failing subtasks, enabling timely intervention",
            tags=["decomposition", "progress", "monitoring", "stall-detection"],
        )
