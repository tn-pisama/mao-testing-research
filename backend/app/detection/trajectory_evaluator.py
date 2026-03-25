"""Trajectory-Level Evaluation for Agent Systems.

Evaluates the ENTIRE agent trajectory — not just individual steps.
Implements 5 metrics matching Google Vertex AI's trajectory evaluation:

1. tool_selection_quality: Did the agent pick the right tools?
2. path_efficiency: Was this the shortest path to the goal?
3. trajectory_completeness: Were all required steps taken?
4. step_ordering: Were steps in a logical order?
5. recovery_quality: How well did the agent recover from errors?

Reference: Google Vertex AI Agent Evaluation (2025/2026)
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryScore:
    """Multi-dimensional trajectory quality score."""
    overall: float  # 0.0-1.0, weighted combination
    tool_selection: float = 0.0  # Did agent pick right tools?
    path_efficiency: float = 0.0  # Shortest path vs actual
    completeness: float = 0.0  # All required steps taken?
    step_ordering: float = 0.0  # Logical step order?
    recovery_quality: float = 0.0  # Error recovery effectiveness?
    dimensions: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    step_scores: List[Dict[str, Any]] = field(default_factory=list)


class TrajectoryEvaluator:
    """Evaluates full agent trajectories against reference paths.

    Unlike step-level detection which asks "is this step a failure?",
    trajectory evaluation asks "was this the right sequence of steps?"
    """

    def __init__(
        self,
        tool_weight: float = 0.25,
        efficiency_weight: float = 0.20,
        completeness_weight: float = 0.25,
        ordering_weight: float = 0.15,
        recovery_weight: float = 0.15,
    ):
        self.weights = {
            "tool_selection": tool_weight,
            "path_efficiency": efficiency_weight,
            "completeness": completeness_weight,
            "step_ordering": ordering_weight,
            "recovery_quality": recovery_weight,
        }

    def evaluate(
        self,
        trajectory: List[Dict[str, Any]],
        reference_trajectory: Optional[List[Dict[str, Any]]] = None,
        required_tools: Optional[Set[str]] = None,
        required_steps: Optional[List[str]] = None,
        max_steps: Optional[int] = None,
    ) -> TrajectoryScore:
        """Evaluate a full agent trajectory.

        Args:
            trajectory: List of steps, each with {tool, action, input, output, status}
            reference_trajectory: Optional ideal trajectory for comparison
            required_tools: Set of tools that MUST be used
            required_steps: List of required step descriptions
            max_steps: Maximum expected steps (for efficiency scoring)
        """
        if not trajectory:
            return TrajectoryScore(overall=0.0, issues=["Empty trajectory"])

        issues = []

        # 1. Tool Selection Quality
        tool_score = self._score_tool_selection(
            trajectory, required_tools, reference_trajectory
        )

        # 2. Path Efficiency
        efficiency_score = self._score_path_efficiency(
            trajectory, reference_trajectory, max_steps
        )

        # 3. Completeness
        completeness_score = self._score_completeness(
            trajectory, required_steps, reference_trajectory
        )

        # 4. Step Ordering
        ordering_score = self._score_step_ordering(
            trajectory, reference_trajectory
        )

        # 5. Recovery Quality
        recovery_score = self._score_recovery_quality(trajectory)

        # Per-step scores
        step_scores = self._compute_step_scores(trajectory, reference_trajectory)

        # Weighted overall
        overall = (
            tool_score * self.weights["tool_selection"]
            + efficiency_score * self.weights["path_efficiency"]
            + completeness_score * self.weights["completeness"]
            + ordering_score * self.weights["step_ordering"]
            + recovery_score * self.weights["recovery_quality"]
        )

        return TrajectoryScore(
            overall=round(overall, 4),
            tool_selection=round(tool_score, 4),
            path_efficiency=round(efficiency_score, 4),
            completeness=round(completeness_score, 4),
            step_ordering=round(ordering_score, 4),
            recovery_quality=round(recovery_score, 4),
            dimensions={
                "tool_selection": round(tool_score, 4),
                "path_efficiency": round(efficiency_score, 4),
                "completeness": round(completeness_score, 4),
                "step_ordering": round(ordering_score, 4),
                "recovery_quality": round(recovery_score, 4),
            },
            issues=issues,
            step_scores=step_scores,
        )

    def _score_tool_selection(
        self,
        trajectory: List[Dict],
        required_tools: Optional[Set[str]],
        reference: Optional[List[Dict]],
    ) -> float:
        """Score: did the agent use the right tools?"""
        actual_tools = {
            s.get("tool", s.get("tool_name", s.get("node_type", "")))
            for s in trajectory if s.get("tool") or s.get("tool_name") or s.get("node_type")
        }

        if required_tools:
            if not required_tools:
                return 1.0
            used_required = actual_tools & required_tools
            precision = len(used_required) / max(len(actual_tools), 1)
            recall = len(used_required) / len(required_tools)
            if precision + recall == 0:
                return 0.0
            return 2 * precision * recall / (precision + recall)

        if reference:
            ref_tools = {
                s.get("tool", s.get("tool_name", s.get("node_type", "")))
                for s in reference if s.get("tool") or s.get("tool_name") or s.get("node_type")
            }
            if not ref_tools:
                return 1.0
            overlap = len(actual_tools & ref_tools)
            precision = overlap / max(len(actual_tools), 1)
            recall = overlap / max(len(ref_tools), 1)
            if precision + recall == 0:
                return 0.0
            return 2 * precision * recall / (precision + recall)

        # No reference — score based on tool diversity and no-op rate
        if not actual_tools:
            return 0.5  # Can't evaluate without reference
        no_ops = sum(1 for s in trajectory if not s.get("tool") and not s.get("tool_name"))
        return max(0.0, 1.0 - no_ops / len(trajectory))

    def _score_path_efficiency(
        self,
        trajectory: List[Dict],
        reference: Optional[List[Dict]],
        max_steps: Optional[int],
    ) -> float:
        """Score: was the path efficient (no unnecessary steps)?"""
        actual_len = len(trajectory)

        if reference:
            ref_len = len(reference)
            if ref_len == 0:
                return 1.0
            # Efficiency = reference_length / actual_length (capped at 1.0)
            return min(1.0, ref_len / max(actual_len, 1))

        if max_steps:
            return min(1.0, max_steps / max(actual_len, 1))

        # Without reference, check for repeated steps (inefficiency signal)
        seen_actions = set()
        repeated = 0
        for step in trajectory:
            action_key = f"{step.get('tool', '')}-{step.get('action', '')}"
            if action_key in seen_actions and action_key != "-":
                repeated += 1
            seen_actions.add(action_key)

        return max(0.0, 1.0 - repeated / max(actual_len, 1))

    def _score_completeness(
        self,
        trajectory: List[Dict],
        required_steps: Optional[List[str]],
        reference: Optional[List[Dict]],
    ) -> float:
        """Score: were all required steps taken?"""
        if required_steps:
            traj_text = " ".join(
                f"{s.get('tool', '')} {s.get('action', '')} {s.get('description', '')}"
                for s in trajectory
            ).lower()
            found = sum(1 for req in required_steps if req.lower() in traj_text)
            return found / max(len(required_steps), 1)

        if reference:
            # Check how many reference step types were covered
            ref_types = [s.get("tool", s.get("node_type", "")) for s in reference]
            actual_types = [s.get("tool", s.get("node_type", "")) for s in trajectory]
            if not ref_types:
                return 1.0
            covered = sum(1 for rt in ref_types if rt in actual_types)
            return covered / len(ref_types)

        # Without reference, check for terminal step (did it complete?)
        if trajectory:
            last = trajectory[-1]
            status = last.get("status", "").lower()
            if status in ("success", "completed", "done"):
                return 1.0
            elif status in ("failed", "error"):
                return 0.3
        return 0.5

    def _score_step_ordering(
        self,
        trajectory: List[Dict],
        reference: Optional[List[Dict]],
    ) -> float:
        """Score: were steps in a logical order?"""
        if not reference or len(reference) < 2:
            # Check for obvious ordering issues: error before any action
            for i, step in enumerate(trajectory):
                if step.get("status") == "error" and i == 0:
                    return 0.3
            return 0.8  # Assume reasonable ordering without reference

        # Compute longest common subsequence ratio
        ref_types = [s.get("tool", s.get("node_type", "")) for s in reference]
        actual_types = [s.get("tool", s.get("node_type", "")) for s in trajectory]
        lcs_len = self._lcs_length(ref_types, actual_types)
        return lcs_len / max(len(ref_types), 1)

    def _score_recovery_quality(self, trajectory: List[Dict]) -> float:
        """Score: how well did the agent recover from errors?"""
        errors = []
        for i, step in enumerate(trajectory):
            status = step.get("status", "").lower()
            if status in ("failed", "error"):
                errors.append(i)

        if not errors:
            return 1.0  # No errors to recover from

        # Check if steps after errors show recovery
        recoveries = 0
        for err_idx in errors:
            # Look for successful step after error
            for j in range(err_idx + 1, min(err_idx + 3, len(trajectory))):
                if trajectory[j].get("status", "").lower() in ("success", "completed"):
                    recoveries += 1
                    break

        return recoveries / max(len(errors), 1)

    def _compute_step_scores(
        self,
        trajectory: List[Dict],
        reference: Optional[List[Dict]],
    ) -> List[Dict[str, Any]]:
        """Compute per-step quality scores."""
        scores = []
        for i, step in enumerate(trajectory):
            status = step.get("status", "unknown").lower()
            score = {
                "step": i,
                "tool": step.get("tool", step.get("tool_name", step.get("node_type", "unknown"))),
                "status": status,
                "quality": 1.0 if status in ("success", "completed") else 0.3 if status == "error" else 0.5,
            }
            scores.append(score)
        return scores

    @staticmethod
    def _lcs_length(a: List[str], b: List[str]) -> int:
        """Longest common subsequence length."""
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        return dp[m][n]


# Singleton
trajectory_evaluator = TrajectoryEvaluator()
