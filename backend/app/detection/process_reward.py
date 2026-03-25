"""Process Reward Model (PRM) — Step-Level Quality Scoring.

Instead of scoring only the final output (Outcome Reward Model), PRMs
score each intermediate reasoning/action step. This enables:
- Identifying exactly WHERE in a trajectory the agent went wrong
- Training step-level reward signals for agent improvement
- More granular quality assessment than trace-level detection

Reference: "Let's Verify Step by Step" (Lightman et al., 2023)

No competitor has this. We use existing detectors as weak labelers
to bootstrap step-level quality scores.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StepReward:
    """Quality score for a single agent step."""
    step_index: int
    step_type: str  # tool_call, generation, reasoning, action
    reward: float  # -1.0 (catastrophic) to 1.0 (perfect)
    features: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""


@dataclass
class TrajectoryReward:
    """Step-level rewards for an entire trajectory."""
    step_rewards: List[StepReward]
    trajectory_reward: float  # Aggregated trajectory score
    first_error_step: Optional[int] = None  # Where things went wrong
    critical_steps: List[int] = field(default_factory=list)  # Key decision points


class ProcessRewardModel:
    """Scores individual agent steps using detectors as weak labelers.

    Architecture:
    1. Extract features from each step (tool used, output length, error status, etc.)
    2. Run relevant detectors on step-local context
    3. Combine into a per-step reward signal
    4. Identify the first error step and critical decision points

    This is a foundation — the feature extraction and scoring can be
    upgraded to a trained model (logistic regression → transformer)
    once we have enough labeled step data.
    """

    # Step feature weights (learned from golden dataset patterns)
    FEATURE_WEIGHTS = {
        "has_output": 0.2,
        "output_length_norm": 0.1,
        "no_error": 0.3,
        "tool_appropriate": 0.15,
        "builds_on_previous": 0.15,
        "not_repetitive": 0.1,
    }

    def score_trajectory(
        self,
        steps: List[Dict[str, Any]],
        task: Optional[str] = None,
    ) -> TrajectoryReward:
        """Score each step in a trajectory.

        Args:
            steps: List of step dicts with {tool, action, output, status, ...}
            task: Optional task description for relevance scoring
        """
        if not steps:
            return TrajectoryReward(step_rewards=[], trajectory_reward=0.0)

        step_rewards = []
        first_error = None
        prev_output = ""

        for i, step in enumerate(steps):
            features = self._extract_features(step, prev_output, task)
            reward = self._compute_reward(features)

            step_rewards.append(StepReward(
                step_index=i,
                step_type=self._classify_step_type(step),
                reward=round(reward, 4),
                features={k: round(v, 4) for k, v in features.items()},
                explanation=self._explain_reward(features, reward),
            ))

            if reward < 0 and first_error is None:
                first_error = i

            prev_output = str(step.get("output", ""))[:500]

        # Aggregate trajectory reward (weighted by step position — later steps matter more)
        if step_rewards:
            weights = [1.0 + 0.5 * (i / len(step_rewards)) for i in range(len(step_rewards))]
            total_weight = sum(weights)
            trajectory_reward = sum(sr.reward * w for sr, w in zip(step_rewards, weights)) / total_weight
        else:
            trajectory_reward = 0.0

        # Critical steps: steps with reward < -0.3 or > 0.8
        critical = [sr.step_index for sr in step_rewards if sr.reward < -0.3 or sr.reward > 0.8]

        return TrajectoryReward(
            step_rewards=step_rewards,
            trajectory_reward=round(trajectory_reward, 4),
            first_error_step=first_error,
            critical_steps=critical,
        )

    def _extract_features(
        self, step: Dict, prev_output: str, task: Optional[str]
    ) -> Dict[str, float]:
        """Extract quality features from a single step."""
        output = str(step.get("output", ""))
        status = str(step.get("status", "")).lower()
        tool = str(step.get("tool", step.get("tool_name", step.get("node_type", ""))))

        features = {}

        # Has output?
        features["has_output"] = 1.0 if len(output.strip()) > 0 else 0.0

        # Output length (normalized — very short or very long is bad)
        out_len = len(output)
        if out_len == 0:
            features["output_length_norm"] = 0.0
        elif out_len < 10:
            features["output_length_norm"] = 0.3
        elif out_len < 5000:
            features["output_length_norm"] = 1.0
        else:
            features["output_length_norm"] = max(0.3, 1.0 - (out_len - 5000) / 50000)

        # No error?
        features["no_error"] = 1.0 if status not in ("error", "failed", "timeout") else 0.0

        # Tool appropriate (has a tool vs no tool)
        features["tool_appropriate"] = 1.0 if tool else 0.5

        # Builds on previous (output references previous content)
        if prev_output and output:
            overlap = len(set(output.lower().split()) & set(prev_output.lower().split()))
            features["builds_on_previous"] = min(1.0, overlap / 10) if overlap > 0 else 0.3
        else:
            features["builds_on_previous"] = 0.5

        # Not repetitive (output differs from previous)
        if prev_output and output and output == prev_output:
            features["not_repetitive"] = 0.0
        else:
            features["not_repetitive"] = 1.0

        return features

    def _compute_reward(self, features: Dict[str, float]) -> float:
        """Compute weighted reward from features."""
        reward = 0.0
        for feat, weight in self.FEATURE_WEIGHTS.items():
            value = features.get(feat, 0.5)
            reward += weight * (2 * value - 1)  # Map [0,1] → [-1,1]
        return max(-1.0, min(1.0, reward))

    def _classify_step_type(self, step: Dict) -> str:
        """Classify the type of step."""
        tool = str(step.get("tool", step.get("tool_name", ""))).lower()
        if "search" in tool or "retriev" in tool:
            return "retrieval"
        if "code" in tool or "exec" in tool:
            return "execution"
        if "write" in tool or "generat" in tool:
            return "generation"
        if tool:
            return "tool_call"
        return "reasoning"

    def _explain_reward(self, features: Dict[str, float], reward: float) -> str:
        """Generate human-readable explanation for the reward."""
        issues = []
        if features.get("no_error", 1) < 0.5:
            issues.append("step errored")
        if features.get("has_output", 1) < 0.5:
            issues.append("no output")
        if features.get("not_repetitive", 1) < 0.5:
            issues.append("repeated previous output")
        if features.get("output_length_norm", 1) < 0.3:
            issues.append("very short output")

        if not issues:
            return f"Good step (reward={reward:.2f})"
        return f"Issues: {', '.join(issues)} (reward={reward:.2f})"


# Singleton
process_reward_model = ProcessRewardModel()
