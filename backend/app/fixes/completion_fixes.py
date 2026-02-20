"""Fix generators for completion misjudgment detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class CompletionFixGenerator(BaseFixGenerator):
    """Generates fixes for premature or delayed task completion detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type in ("completion", "completion_misjudgment")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._completion_gate_fix(detection_id, details, context))
        fixes.append(self._quality_checkpoint_fix(detection_id, details, context))
        fixes.append(self._progress_monitoring_fix(detection_id, details, context))

        return fixes

    def _completion_gate_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class GateVerdict(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


@dataclass
class AcceptanceCriterion:
    """A single criterion that must be met before task completion."""
    name: str
    description: str
    check: Callable[[Dict[str, Any]], bool]
    required: bool = True  # False = advisory only


@dataclass
class GateResult:
    verdict: GateVerdict
    criteria_met: List[str]
    criteria_failed: List[str]
    advisory_warnings: List[str]


class CompletionGate:
    """
    A review step that checks acceptance criteria before allowing
    a task to be marked as complete.
    """

    def __init__(self):
        self._criteria: Dict[str, List[AcceptanceCriterion]] = {}
        self._gate_history: List[Dict[str, Any]] = []

    def register_criteria(
        self, task_type: str, criteria: List[AcceptanceCriterion]
    ) -> None:
        self._criteria[task_type] = criteria

    def evaluate(
        self, task_type: str, output: Dict[str, Any]
    ) -> GateResult:
        """Evaluate output against registered acceptance criteria."""
        criteria = self._criteria.get(task_type, [])
        if not criteria:
            logger.info("No criteria registered for '%s', auto-approving", task_type)
            return GateResult(
                verdict=GateVerdict.APPROVED,
                criteria_met=[],
                criteria_failed=[],
                advisory_warnings=["No acceptance criteria defined"],
            )

        met: List[str] = []
        failed: List[str] = []
        warnings: List[str] = []

        for criterion in criteria:
            try:
                passed = criterion.check(output)
            except Exception as exc:
                logger.error("Criterion '%s' raised: %s", criterion.name, exc)
                passed = False

            if passed:
                met.append(criterion.name)
            elif criterion.required:
                failed.append(criterion.name)
            else:
                warnings.append(f"{criterion.name}: {criterion.description}")

        if failed:
            verdict = GateVerdict.REJECTED
        elif warnings:
            verdict = GateVerdict.NEEDS_REVISION
        else:
            verdict = GateVerdict.APPROVED

        result = GateResult(
            verdict=verdict,
            criteria_met=met,
            criteria_failed=failed,
            advisory_warnings=warnings,
        )
        self._gate_history.append({
            "task_type": task_type,
            "verdict": verdict.value,
            "met": met,
            "failed": failed,
        })

        if verdict != GateVerdict.APPROVED:
            logger.warning(
                "Completion gate %s for '%s': failed=[%s]",
                verdict.value,
                task_type,
                ", ".join(failed),
            )
        return result

    async def guard(
        self,
        task_type: str,
        task_fn: Callable,
        state: Dict[str, Any],
        max_revisions: int = 2,
    ) -> Dict[str, Any]:
        """Run task and re-attempt if gate rejects output."""
        for attempt in range(1, max_revisions + 2):
            output = await task_fn(state)
            result = self.evaluate(task_type, output)
            if result.verdict == GateVerdict.APPROVED:
                return output
            if attempt > max_revisions:
                logger.error(
                    "Task '%s' failed gate after %d attempts", task_type, attempt
                )
                raise CompletionGateError(
                    f"Output rejected after {attempt} attempts: {result.criteria_failed}"
                )
            state["_gate_feedback"] = {
                "failed_criteria": result.criteria_failed,
                "attempt": attempt,
            }
        return output


class CompletionGateError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="completion",
            fix_type=FixType.COMPLETION_GATE,
            confidence=FixConfidence.HIGH,
            title="Add a completion gate that checks acceptance criteria before finalizing",
            description=(
                "Insert a review step between task execution and completion that "
                "evaluates registered acceptance criteria. Tasks are only marked "
                "complete when all required criteria pass."
            ),
            rationale=(
                "Premature completion happens when an agent self-reports success "
                "without verifying the output meets requirements. An explicit gate "
                "with defined criteria removes the agent's ability to skip validation."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/completion_gate.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Acceptance-criteria gate with retry loop for task completion",
                )
            ],
            estimated_impact="Prevents premature task completion by enforcing acceptance criteria",
            tags=["completion", "gate", "acceptance-criteria", "quality"],
        )

    def _quality_checkpoint_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class QualityMetric:
    """A single quality dimension to score."""
    name: str
    scorer: Callable[[Dict[str, Any]], float]  # returns 0.0 - 1.0
    weight: float = 1.0
    min_threshold: float = 0.0  # per-metric floor


@dataclass
class QualityScore:
    metric_name: str
    score: float
    weight: float
    passed: bool


@dataclass
class CheckpointResult:
    overall_score: float
    threshold: float
    passed: bool
    scores: List[QualityScore]
    elapsed_ms: float


class QualityCheckpoint:
    """
    Evaluate output quality against a weighted score threshold
    before allowing finalization.
    """

    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold
        self._metrics: List[QualityMetric] = []
        self._results: List[CheckpointResult] = []

    def add_metric(self, metric: QualityMetric) -> None:
        self._metrics.append(metric)

    def evaluate(self, output: Dict[str, Any]) -> CheckpointResult:
        start = time.time()
        scores: List[QualityScore] = []
        total_weight = 0.0
        weighted_sum = 0.0

        for metric in self._metrics:
            try:
                raw_score = metric.scorer(output)
                score = max(0.0, min(1.0, raw_score))
            except Exception as exc:
                logger.error("Metric '%s' failed: %s", metric.name, exc)
                score = 0.0

            passed = score >= metric.min_threshold
            scores.append(
                QualityScore(
                    metric_name=metric.name,
                    score=score,
                    weight=metric.weight,
                    passed=passed,
                )
            )
            weighted_sum += score * metric.weight
            total_weight += metric.weight

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        elapsed_ms = (time.time() - start) * 1000

        result = CheckpointResult(
            overall_score=overall,
            threshold=self._threshold,
            passed=overall >= self._threshold,
            scores=scores,
            elapsed_ms=elapsed_ms,
        )
        self._results.append(result)

        if not result.passed:
            logger.warning(
                "Quality checkpoint failed: %.2f < %.2f (metrics: %s)",
                overall,
                self._threshold,
                {s.metric_name: f"{s.score:.2f}" for s in scores},
            )
        return result

    @property
    def average_score(self) -> float:
        if not self._results:
            return 0.0
        return sum(r.overall_score for r in self._results) / len(self._results)


# Common quality scorers
def length_scorer(min_words: int = 50) -> Callable:
    def scorer(output: Dict[str, Any]) -> float:
        text = output.get("text", output.get("content", ""))
        word_count = len(text.split())
        return min(1.0, word_count / min_words)
    return scorer


def completeness_scorer(required_fields: List[str]) -> Callable:
    def scorer(output: Dict[str, Any]) -> float:
        present = sum(1 for f in required_fields if output.get(f))
        return present / len(required_fields) if required_fields else 1.0
    return scorer


def error_free_scorer() -> Callable:
    def scorer(output: Dict[str, Any]) -> float:
        errors = output.get("errors", [])
        return 1.0 if not errors else 0.0
    return scorer'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="completion",
            fix_type=FixType.QUALITY_CHECKPOINT,
            confidence=FixConfidence.MEDIUM,
            title="Require quality threshold before task finalization",
            description=(
                "Score task output on multiple weighted quality metrics and "
                "block finalization if the overall score falls below the "
                "configured threshold."
            ),
            rationale=(
                "Completion misjudgment often means the agent stops too early "
                "with low-quality output. A numeric quality checkpoint gives an "
                "objective, tunable bar that must be cleared before the task is "
                "considered done."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/quality_checkpoint.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Weighted quality scoring with configurable threshold",
                )
            ],
            estimated_impact="Blocks low-quality outputs from being accepted as complete",
            tags=["completion", "quality", "scoring", "threshold"],
        )

    def _progress_monitoring_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class Subtask:
    id: str
    name: str
    weight: float = 1.0
    completed: bool = False
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class ProgressSnapshot:
    timestamp: float
    completion_pct: float
    subtasks_done: int
    subtasks_total: int
    elapsed_seconds: float


class ProgressMonitor:
    """
    Track subtask completion percentage to detect premature
    completion claims and stalled progress.
    """

    def __init__(
        self,
        min_completion_pct: float = 0.9,
        stall_timeout_seconds: float = 120.0,
    ):
        self._min_completion = min_completion_pct
        self._stall_timeout = stall_timeout_seconds
        self._subtasks: Dict[str, Subtask] = {}
        self._snapshots: List[ProgressSnapshot] = []
        self._start_time: Optional[float] = None

    def register_subtasks(self, subtasks: List[Subtask]) -> None:
        self._start_time = time.time()
        for st in subtasks:
            self._subtasks[st.id] = st

    def mark_started(self, subtask_id: str) -> None:
        if subtask_id in self._subtasks:
            self._subtasks[subtask_id].started_at = time.time()

    def mark_completed(self, subtask_id: str) -> None:
        if subtask_id in self._subtasks:
            st = self._subtasks[subtask_id]
            st.completed = True
            st.completed_at = time.time()
            self._take_snapshot()

    @property
    def completion_percentage(self) -> float:
        if not self._subtasks:
            return 0.0
        total_weight = sum(st.weight for st in self._subtasks.values())
        done_weight = sum(
            st.weight for st in self._subtasks.values() if st.completed
        )
        return done_weight / total_weight if total_weight > 0 else 0.0

    def can_finalize(self) -> bool:
        """Check whether enough subtasks are done to allow finalization."""
        pct = self.completion_percentage
        if pct < self._min_completion:
            logger.warning(
                "Finalization blocked: %.1f%% complete (need %.1f%%)",
                pct * 100,
                self._min_completion * 100,
            )
            return False
        return True

    def detect_stall(self) -> bool:
        """Detect if progress has stalled (no completions for too long)."""
        if not self._snapshots:
            return False
        last = self._snapshots[-1]
        if last.completion_pct >= self._min_completion:
            return False
        elapsed_since_last = time.time() - last.timestamp
        return elapsed_since_last > self._stall_timeout

    def get_missing_subtasks(self) -> List[str]:
        return [
            st.name for st in self._subtasks.values() if not st.completed
        ]

    def summary(self) -> Dict[str, Any]:
        elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            "completion_pct": round(self.completion_percentage * 100, 1),
            "subtasks_done": sum(1 for s in self._subtasks.values() if s.completed),
            "subtasks_total": len(self._subtasks),
            "missing": self.get_missing_subtasks(),
            "elapsed_seconds": round(elapsed, 1),
            "stalled": self.detect_stall(),
        }

    def _take_snapshot(self) -> None:
        elapsed = time.time() - self._start_time if self._start_time else 0
        self._snapshots.append(
            ProgressSnapshot(
                timestamp=time.time(),
                completion_pct=self.completion_percentage,
                subtasks_done=sum(
                    1 for s in self._subtasks.values() if s.completed
                ),
                subtasks_total=len(self._subtasks),
                elapsed_seconds=elapsed,
            )
        )'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="completion",
            fix_type=FixType.PROGRESS_MONITORING,
            confidence=FixConfidence.MEDIUM,
            title="Track subtask completion percentage to prevent premature finalization",
            description=(
                "Register the expected subtasks for a workflow and track their "
                "individual completion. Block finalization until a minimum "
                "percentage threshold is reached and detect stalled progress."
            ),
            rationale=(
                "Agents can claim a task is complete when only a fraction of the "
                "work is done. Explicit subtask tracking provides an objective "
                "progress metric that the agent cannot bypass."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/progress_monitor.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Subtask-level progress tracking with stall detection",
                )
            ],
            estimated_impact="Prevents premature completion claims and detects stalled workflows",
            tags=["completion", "progress", "monitoring", "subtask-tracking"],
        )
