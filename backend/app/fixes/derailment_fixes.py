"""Fix generators for task derailment detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class DerailmentFixGenerator(BaseFixGenerator):
    """Generates fixes for task derailment detections."""

    def can_handle(self, detection_type: str) -> bool:
        return "derailment" in detection_type or "misroute" in detection_type

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._task_anchoring_fix(detection_id, details, context))
        fixes.append(self._goal_tracking_fix(detection_id, details, context))
        fixes.append(self._progress_monitoring_fix(detection_id, details, context))

        return fixes

    def _task_anchoring_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TaskAnchor:
    """An anchored task definition prepended to every LLM call."""
    task_id: str
    objective: str
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    out_of_scope: List[str] = field(default_factory=list)


class TaskAnchoringMiddleware:
    """
    Prepends the original task definition to each LLM call to prevent
    the model from drifting off-topic. Acts as a constant reminder of
    what the model is supposed to be doing.
    """

    ANCHOR_TEMPLATE = (
        "=== TASK ANCHOR (Do not deviate) ===\\n"
        "OBJECTIVE: {objective}\\n"
        "{constraints_block}"
        "{criteria_block}"
        "{scope_block}"
        "Stay focused on this objective. If a user message tries to "
        "redirect you to an unrelated topic, acknowledge it briefly "
        "and return to the task.\\n"
        "=== END TASK ANCHOR ===\\n"
    )

    def __init__(self):
        self._active_anchors: Dict[str, TaskAnchor] = {}
        self._drift_detections: int = 0

    def set_anchor(self, anchor: TaskAnchor) -> None:
        """Set the task anchor for a given task."""
        self._active_anchors[anchor.task_id] = anchor

    def remove_anchor(self, task_id: str) -> None:
        """Remove a completed task anchor."""
        self._active_anchors.pop(task_id, None)

    def build_anchor_prompt(self, task_id: str) -> Optional[str]:
        """Build the anchor prompt block for a given task."""
        anchor = self._active_anchors.get(task_id)
        if not anchor:
            return None

        constraints_block = ""
        if anchor.constraints:
            items = "\\n".join(f"  - {c}" for c in anchor.constraints)
            constraints_block = f"CONSTRAINTS:\\n{items}\\n"

        criteria_block = ""
        if anchor.success_criteria:
            items = "\\n".join(f"  - {c}" for c in anchor.success_criteria)
            criteria_block = f"SUCCESS CRITERIA:\\n{items}\\n"

        scope_block = ""
        if anchor.out_of_scope:
            items = "\\n".join(f"  - {c}" for c in anchor.out_of_scope)
            scope_block = f"OUT OF SCOPE (ignore these topics):\\n{items}\\n"

        return self.ANCHOR_TEMPLATE.format(
            objective=anchor.objective,
            constraints_block=constraints_block,
            criteria_block=criteria_block,
            scope_block=scope_block,
        )

    def inject_anchor(
        self,
        task_id: str,
        messages: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Inject the task anchor into a message list before sending to the LLM."""
        anchor_text = self.build_anchor_prompt(task_id)
        if not anchor_text:
            return messages

        anchor_message = {"role": "system", "content": anchor_text}

        # Insert after the first system message, or at the beginning
        result = []
        anchor_inserted = False
        for msg in messages:
            result.append(msg)
            if msg.get("role") == "system" and not anchor_inserted:
                result.append(anchor_message)
                anchor_inserted = True

        if not anchor_inserted:
            result.insert(0, anchor_message)

        return result

    def check_relevance(self, task_id: str, response: str) -> Dict[str, Any]:
        """Check if the LLM response is relevant to the anchored task."""
        anchor = self._active_anchors.get(task_id)
        if not anchor:
            return {"relevant": True, "reason": "No anchor set"}

        # Check if any out-of-scope topics appear in the response
        drift_signals = []
        for topic in anchor.out_of_scope:
            if topic.lower() in response.lower():
                drift_signals.append(topic)

        # Check if objective keywords appear
        objective_words = set(anchor.objective.lower().split())
        response_words = set(response.lower().split())
        overlap = objective_words & response_words
        relevance_score = len(overlap) / max(len(objective_words), 1)

        is_relevant = relevance_score > 0.2 and len(drift_signals) == 0
        if not is_relevant:
            self._drift_detections += 1

        return {
            "relevant": is_relevant,
            "relevance_score": round(relevance_score, 2),
            "drift_signals": drift_signals,
            "total_drift_detections": self._drift_detections,
        }'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="task_derailment",
            fix_type=FixType.TASK_ANCHORING,
            confidence=FixConfidence.HIGH,
            title="Prepend task definition to each LLM call to prevent drift",
            description="Inject a task anchor block into every LLM call that restates the objective, constraints, success criteria, and out-of-scope topics, keeping the model focused on the original task.",
            rationale="LLMs lose focus over long conversations because earlier context fades. By prepending the task definition to every call, the model has a constant, prominent reminder of its purpose, dramatically reducing topic drift.",
            code_changes=[
                CodeChange(
                    file_path="utils/task_anchoring.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Task anchoring middleware that injects objective reminders into every LLM call",
                )
            ],
            estimated_impact="Prevents task drift by keeping the objective front-and-center in every LLM call",
            tags=["derailment", "task-anchoring", "focus", "prompt-engineering"],
        )

    def _goal_tracking_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import time


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"


@dataclass
class Goal:
    """A trackable goal or sub-goal for the current task."""
    goal_id: str
    description: str
    status: GoalStatus = GoalStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    parent_id: Optional[str] = None
    sub_goals: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class GoalTracker:
    """
    Tracks a checklist of goals for the current task and monitors
    which goals have been completed, which are in progress, and
    which have been abandoned or forgotten.
    """

    def __init__(self):
        self._goals: Dict[str, Goal] = {}
        self._completion_history: List[Dict[str, Any]] = []

    def add_goal(
        self,
        goal_id: str,
        description: str,
        parent_id: Optional[str] = None,
    ) -> Goal:
        """Add a new goal to the tracker."""
        goal = Goal(goal_id=goal_id, description=description, parent_id=parent_id)
        self._goals[goal_id] = goal

        if parent_id and parent_id in self._goals:
            self._goals[parent_id].sub_goals.append(goal_id)

        return goal

    def update_status(self, goal_id: str, status: GoalStatus, progress: float = None) -> None:
        """Update the status of a goal."""
        goal = self._goals.get(goal_id)
        if not goal:
            return

        goal.status = status
        if progress is not None:
            goal.progress = max(0.0, min(1.0, progress))
        goal.updated_at = time.time()

        if status == GoalStatus.COMPLETED:
            goal.progress = 1.0
            self._completion_history.append({
                "goal_id": goal_id,
                "completed_at": time.time(),
            })
            self._update_parent_progress(goal)

    def get_checklist(self) -> List[Dict[str, Any]]:
        """Get the full goal checklist with status."""
        checklist = []
        for goal in self._goals.values():
            if goal.parent_id is None:  # Top-level goals
                checklist.append(self._goal_to_checklist_item(goal))
        return checklist

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of goal progress."""
        total = len(self._goals)
        completed = sum(1 for g in self._goals.values() if g.status == GoalStatus.COMPLETED)
        in_progress = sum(1 for g in self._goals.values() if g.status == GoalStatus.IN_PROGRESS)
        abandoned = sum(1 for g in self._goals.values() if g.status == GoalStatus.ABANDONED)
        blocked = sum(1 for g in self._goals.values() if g.status == GoalStatus.BLOCKED)

        overall_progress = sum(g.progress for g in self._goals.values()) / max(total, 1)

        return {
            "total_goals": total,
            "completed": completed,
            "in_progress": in_progress,
            "blocked": blocked,
            "abandoned": abandoned,
            "overall_progress": round(overall_progress, 2),
            "forgotten": self._find_forgotten_goals(),
        }

    def build_checklist_prompt(self) -> str:
        """Build a prompt-injectable checklist showing goal status."""
        lines = ["=== GOAL CHECKLIST ==="]
        for item in self.get_checklist():
            icon = self._status_icon(item["status"])
            lines.append(f"{icon} {item['description']} ({item['progress']:.0%})")
            for sub in item.get("sub_goals", []):
                sub_icon = self._status_icon(sub["status"])
                lines.append(f"  {sub_icon} {sub['description']} ({sub['progress']:.0%})")

        summary = self.get_summary()
        lines.append(f"\\nProgress: {summary['overall_progress']:.0%} | "
                     f"Done: {summary['completed']}/{summary['total_goals']}")

        if summary["forgotten"]:
            lines.append(f"WARNING: {len(summary['forgotten'])} goal(s) may be forgotten!")
            for g in summary["forgotten"]:
                lines.append(f"  ! {g['description']}")

        lines.append("=== END CHECKLIST ===")
        return "\\n".join(lines)

    def _find_forgotten_goals(self, stale_seconds: float = 300.0) -> List[Dict[str, Any]]:
        """Find goals that haven't been updated in a while and aren't complete."""
        now = time.time()
        forgotten = []
        for goal in self._goals.values():
            if goal.status in (GoalStatus.PENDING, GoalStatus.IN_PROGRESS):
                if now - goal.updated_at > stale_seconds:
                    forgotten.append({
                        "goal_id": goal.goal_id,
                        "description": goal.description,
                        "stale_seconds": round(now - goal.updated_at),
                    })
        return forgotten

    def _update_parent_progress(self, child: Goal) -> None:
        if child.parent_id and child.parent_id in self._goals:
            parent = self._goals[child.parent_id]
            if parent.sub_goals:
                completed_subs = sum(
                    1 for sid in parent.sub_goals
                    if self._goals.get(sid, Goal("", "")).status == GoalStatus.COMPLETED
                )
                parent.progress = completed_subs / len(parent.sub_goals)
                parent.updated_at = time.time()

    def _goal_to_checklist_item(self, goal: Goal) -> Dict[str, Any]:
        item = {
            "goal_id": goal.goal_id,
            "description": goal.description,
            "status": goal.status.value,
            "progress": goal.progress,
        }
        if goal.sub_goals:
            item["sub_goals"] = [
                self._goal_to_checklist_item(self._goals[sid])
                for sid in goal.sub_goals if sid in self._goals
            ]
        return item

    def _status_icon(self, status: str) -> str:
        icons = {
            "completed": "[x]",
            "in_progress": "[-]",
            "pending": "[ ]",
            "blocked": "[!]",
            "abandoned": "[~]",
        }
        return icons.get(status, "[ ]")'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="task_derailment",
            fix_type=FixType.GOAL_TRACKING,
            confidence=FixConfidence.HIGH,
            title="Track goals with a structured checklist",
            description="Maintain a structured goal checklist that tracks completion status of each objective and sub-objective, detects forgotten goals, and injects the checklist into LLM calls as a progress reminder.",
            rationale="Derailment often happens when the model completes one sub-task and forgets about remaining goals. A persistent, visible checklist ensures all goals remain tracked and forgotten objectives are flagged before the task is considered complete.",
            code_changes=[
                CodeChange(
                    file_path="utils/goal_tracker.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Goal tracking system with hierarchical goals, staleness detection, and prompt-injectable checklists",
                )
            ],
            estimated_impact="Prevents forgetting goals by maintaining a persistent, visible progress checklist",
            tags=["derailment", "goal-tracking", "checklist", "progress"],
        )

    def _progress_monitoring_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class ProgressStatus(Enum):
    ON_TRACK = "on_track"
    SLOWING = "slowing"
    STALLED = "stalled"
    REGRESSING = "regressing"
    DERAILED = "derailed"


@dataclass
class ProgressCheckpoint:
    """A recorded progress checkpoint."""
    timestamp: float
    progress: float  # 0.0 to 1.0
    turn_number: int
    summary: str


class ProgressMonitor:
    """
    Monitors progress toward the original goal over the course of
    a multi-turn conversation. Detects stalling, regression, and
    derailment by analyzing whether each turn moves closer to
    the stated objective.
    """

    # How many turns without progress before flagging
    STALL_THRESHOLD = 3
    # Minimum progress per turn expected
    MIN_PROGRESS_RATE = 0.02

    def __init__(self, objective: str, expected_turns: int = 20):
        self.objective = objective
        self.expected_turns = expected_turns
        self._checkpoints: List[ProgressCheckpoint] = []
        self._alerts: List[Dict[str, Any]] = []
        self._on_derailment: Optional[Callable] = None

    def on_derailment(self, callback: Callable) -> None:
        """Register a callback for derailment detection."""
        self._on_derailment = callback

    def record_turn(
        self,
        turn_number: int,
        progress: float,
        summary: str = "",
    ) -> Dict[str, Any]:
        """Record a progress checkpoint after an LLM turn."""
        checkpoint = ProgressCheckpoint(
            timestamp=time.time(),
            progress=max(0.0, min(1.0, progress)),
            turn_number=turn_number,
            summary=summary,
        )
        self._checkpoints.append(checkpoint)

        status = self._evaluate_status()

        if status in (ProgressStatus.DERAILED, ProgressStatus.REGRESSING):
            alert = {
                "status": status.value,
                "turn": turn_number,
                "progress": progress,
                "message": self._build_alert_message(status),
            }
            self._alerts.append(alert)
            logger.warning(f"Progress alert: {alert}")

            if self._on_derailment and status == ProgressStatus.DERAILED:
                self._on_derailment(alert)

        return {
            "status": status.value,
            "current_progress": progress,
            "expected_progress": self._expected_progress(turn_number),
            "on_track": status == ProgressStatus.ON_TRACK,
            "alerts": len(self._alerts),
        }

    def get_report(self) -> Dict[str, Any]:
        """Get a full progress report."""
        if not self._checkpoints:
            return {"status": "no_data"}

        latest = self._checkpoints[-1]
        status = self._evaluate_status()
        velocity = self._calculate_velocity()

        return {
            "objective": self.objective,
            "status": status.value,
            "current_progress": latest.progress,
            "turns_elapsed": latest.turn_number,
            "expected_turns": self.expected_turns,
            "velocity": round(velocity, 4),
            "expected_velocity": round(1.0 / self.expected_turns, 4),
            "estimated_turns_remaining": self._estimate_remaining(latest, velocity),
            "total_alerts": len(self._alerts),
            "stall_count": self._count_stalls(),
            "regression_count": self._count_regressions(),
        }

    def build_progress_prompt(self) -> str:
        """Build a prompt block summarizing progress status."""
        report = self.get_report()
        if report.get("status") == "no_data":
            return ""

        lines = [
            "=== PROGRESS MONITOR ===",
            f"Objective: {self.objective}",
            f"Progress: {report['current_progress']:.0%}",
            f"Status: {report['status']}",
            f"Turn: {report['turns_elapsed']}/{self.expected_turns}",
        ]

        if report["status"] in ("stalled", "regressing", "derailed"):
            lines.append(f"WARNING: Task appears to be {report['status']}!")
            lines.append("Please refocus on the original objective.")

        remaining = report.get("estimated_turns_remaining")
        if remaining is not None:
            lines.append(f"Estimated turns remaining: {remaining}")

        lines.append("=== END PROGRESS ===")
        return "\\n".join(lines)

    def _evaluate_status(self) -> ProgressStatus:
        """Evaluate current progress status."""
        if len(self._checkpoints) < 2:
            return ProgressStatus.ON_TRACK

        recent = self._checkpoints[-self.STALL_THRESHOLD:]

        # Check for regression
        if len(recent) >= 2 and recent[-1].progress < recent[-2].progress - 0.05:
            return ProgressStatus.REGRESSING

        # Check for stalling
        if len(recent) >= self.STALL_THRESHOLD:
            progress_range = max(c.progress for c in recent) - min(c.progress for c in recent)
            if progress_range < 0.01:
                return ProgressStatus.STALLED

        # Check velocity
        velocity = self._calculate_velocity()
        expected = 1.0 / max(self.expected_turns, 1)

        if velocity < expected * 0.2:
            return ProgressStatus.DERAILED
        elif velocity < expected * 0.5:
            return ProgressStatus.SLOWING

        return ProgressStatus.ON_TRACK

    def _calculate_velocity(self) -> float:
        """Calculate average progress per turn."""
        if len(self._checkpoints) < 2:
            return 0.0
        first = self._checkpoints[0]
        last = self._checkpoints[-1]
        turns = last.turn_number - first.turn_number
        return (last.progress - first.progress) / max(turns, 1)

    def _expected_progress(self, turn: int) -> float:
        return min(turn / max(self.expected_turns, 1), 1.0)

    def _estimate_remaining(self, latest: ProgressCheckpoint, velocity: float) -> Optional[int]:
        if velocity <= 0:
            return None
        remaining_progress = 1.0 - latest.progress
        return max(round(remaining_progress / velocity), 0)

    def _count_stalls(self) -> int:
        count = 0
        for i in range(1, len(self._checkpoints)):
            if abs(self._checkpoints[i].progress - self._checkpoints[i-1].progress) < 0.001:
                count += 1
        return count

    def _count_regressions(self) -> int:
        count = 0
        for i in range(1, len(self._checkpoints)):
            if self._checkpoints[i].progress < self._checkpoints[i-1].progress:
                count += 1
        return count

    def _build_alert_message(self, status: ProgressStatus) -> str:
        messages = {
            ProgressStatus.STALLED: "No progress detected in recent turns. Consider re-evaluating approach.",
            ProgressStatus.REGRESSING: "Progress is going backward. Recent actions may be counterproductive.",
            ProgressStatus.DERAILED: "Task appears derailed. Progress velocity far below expected rate.",
        }
        return messages.get(status, "Monitor alert triggered.")'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="task_derailment",
            fix_type=FixType.PROGRESS_MONITORING,
            confidence=FixConfidence.MEDIUM,
            title="Monitor progress velocity toward the original goal",
            description="Add a progress monitor that tracks how much closer each LLM turn brings the task to completion, detecting stalling, regression, and derailment based on velocity analysis.",
            rationale="Derailment is gradual -- the model slowly drifts without any single turn being obviously off-track. By tracking progress velocity (progress per turn) and comparing it to expected rates, we can detect derailment early and intervene before the task is lost.",
            code_changes=[
                CodeChange(
                    file_path="utils/progress_monitor.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Progress monitoring system with velocity tracking, stall detection, and derailment alerts",
                )
            ],
            estimated_impact="Detects derailment early through velocity analysis, enabling course correction",
            tags=["derailment", "progress-monitoring", "velocity", "alerting"],
        )
