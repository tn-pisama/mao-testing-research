"""Fix generators for convergence issue detections.

Generates fix suggestions for the 4 convergence failure types:
- Plateau: metric improvement stalls
- Regression: metric worsens past best
- Thrashing: metric oscillates without trend
- Divergence: metric consistently moves wrong direction
"""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class ConvergenceFixGenerator(BaseFixGenerator):
    """Generates fixes for convergence issue detections."""

    def can_handle(self, detection_type: str) -> bool:
        return "convergence" in detection_type

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})
        failure_type = details.get("failure_type", "plateau")

        if failure_type == "plateau":
            fixes.extend(self._plateau_fixes(detection_id, details, context))
        elif failure_type == "regression":
            fixes.extend(self._regression_fixes(detection_id, details, context))
        elif failure_type == "thrashing":
            fixes.extend(self._thrashing_fixes(detection_id, details, context))
        elif failure_type == "divergence":
            fixes.extend(self._divergence_fixes(detection_id, details, context))
        else:
            # Default: provide generic convergence fixes
            fixes.append(self._checkpoint_recovery_fix(detection_id, context))
            fixes.append(self._early_stopping_fix(detection_id, details, context))

        return fixes

    def _plateau_fixes(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        return [
            self._checkpoint_recovery_fix(detection_id, context),
            self._strategy_switch_fix(detection_id, details, context),
            self._early_stopping_fix(detection_id, details, context),
        ]

    def _regression_fixes(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        return [
            self._checkpoint_recovery_fix(detection_id, context),
            self._regression_guard_fix(detection_id, details, context),
        ]

    def _thrashing_fixes(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        return [
            self._direction_lock_fix(detection_id, details, context),
            self._exploration_temperature_fix(detection_id, details, context),
        ]

    def _divergence_fixes(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        return [
            self._emergency_stop_fix(detection_id, details, context),
            self._checkpoint_recovery_fix(detection_id, context),
        ]

    def _checkpoint_recovery_fix(
        self,
        detection_id: str,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''class CheckpointManager:
    """Track and restore best-known state in iterative experiments."""

    def __init__(self):
        self.best_value = None
        self.best_state = None
        self.best_step = -1

    def update(self, step: int, metric_value: float, state: dict,
               direction: str = "minimize") -> bool:
        """Record a new metric value. Returns True if it's a new best."""
        is_better = (
            self.best_value is None
            or (direction == "minimize" and metric_value < self.best_value)
            or (direction == "maximize" and metric_value > self.best_value)
        )
        if is_better:
            self.best_value = metric_value
            self.best_state = dict(state)  # snapshot
            self.best_step = step
            return True
        return False

    def restore_best(self) -> dict:
        """Restore the best-known state."""
        if self.best_state is None:
            raise RuntimeError("No checkpoint available")
        return dict(self.best_state)

# Usage in experiment loop
checkpoint = CheckpointManager()
for step in range(max_steps):
    result = run_experiment(current_state)
    is_new_best = checkpoint.update(step, result["metric"], current_state)
    if not is_new_best and step - checkpoint.best_step > patience:
        current_state = checkpoint.restore_best()
        logger.info(f"Reverted to best state from step {checkpoint.best_step}")'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="convergence_failure",
            fix_type=FixType.CHECKPOINT_RECOVERY,
            confidence=FixConfidence.HIGH,
            title="Add checkpoint manager to track and restore best state",
            description="Implement a checkpoint system that tracks the best metric value and can revert to it when the agent regresses or plateaus.",
            rationale="Without checkpoint tracking, the agent cannot recover from accidental regressions. A checkpoint manager ensures the best-known state is always recoverable.",
            code_changes=[
                CodeChange(
                    file_path="utils/checkpoint_manager.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Checkpoint manager for iterative experiment tracking",
                )
            ],
            estimated_impact="Prevents permanent loss of best results, enables automatic recovery",
            tags=["convergence", "checkpoint", "recovery"],
        )

    def _strategy_switch_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''class AdaptiveStrategy:
    """Switch between strategies when the current one plateaus."""

    def __init__(self, strategies: list, patience: int = 5):
        self.strategies = strategies
        self.patience = patience
        self.current_idx = 0
        self.steps_without_improvement = 0
        self.best_value = None

    @property
    def current_strategy(self) -> str:
        return self.strategies[self.current_idx]

    def step(self, metric_value: float, direction: str = "minimize") -> str:
        """Record a metric and switch strategy if plateaued.

        Returns the name of the strategy to use next.
        """
        is_better = (
            self.best_value is None
            or (direction == "minimize" and metric_value < self.best_value)
            or (direction == "maximize" and metric_value > self.best_value)
        )
        if is_better:
            self.best_value = metric_value
            self.steps_without_improvement = 0
        else:
            self.steps_without_improvement += 1

        if self.steps_without_improvement >= self.patience:
            self.current_idx = (self.current_idx + 1) % len(self.strategies)
            self.steps_without_improvement = 0
            logger.info(f"Switching to strategy: {self.current_strategy}")

        return self.current_strategy

# Usage
strategy = AdaptiveStrategy(
    strategies=["architecture_search", "hyperparameter_tune", "data_augmentation"],
    patience=5,
)
for step in range(max_steps):
    approach = strategy.step(current_metric)
    result = run_experiment(approach=approach)'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="convergence_failure",
            fix_type=FixType.STRATEGY_SWITCH,
            confidence=FixConfidence.MEDIUM,
            title="Add adaptive strategy switching on plateau",
            description="Automatically switch to a different approach when the current strategy stops making progress.",
            rationale="Plateau often indicates the current approach has been exhausted. Switching strategies can break through local optima.",
            code_changes=[
                CodeChange(
                    file_path="utils/adaptive_strategy.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Adaptive strategy manager with plateau-triggered switching",
                )
            ],
            estimated_impact="Breaks through plateaus by trying alternative approaches automatically",
            tags=["convergence", "plateau", "strategy"],
        )

    def _regression_guard_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        tolerance = details.get("regression_frac", 0.02)
        code = f'''class RegressionGuard:
    """Reject changes that worsen metrics beyond a tolerance."""

    def __init__(self, tolerance: float = {tolerance}, direction: str = "minimize"):
        self.tolerance = tolerance
        self.direction = direction
        self.best_value = None

    def should_keep(self, new_value: float) -> bool:
        """Return True if the new value should be kept (not a regression)."""
        if self.best_value is None:
            self.best_value = new_value
            return True

        if self.direction == "minimize":
            threshold = self.best_value * (1 + self.tolerance)
            if new_value > threshold:
                return False  # Regression beyond tolerance
            if new_value < self.best_value:
                self.best_value = new_value
        else:
            threshold = self.best_value * (1 - self.tolerance)
            if new_value < threshold:
                return False  # Regression beyond tolerance
            if new_value > self.best_value:
                self.best_value = new_value

        return True

# Usage in experiment loop
guard = RegressionGuard(tolerance={tolerance})
for step in range(max_steps):
    result = run_experiment(proposed_changes)
    if guard.should_keep(result["metric"]):
        apply_changes(proposed_changes)
    else:
        discard_changes(proposed_changes)
        logger.warning(f"Step {{step}}: rejected — regression beyond {{guard.tolerance:.1%}}")'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="convergence_failure",
            fix_type=FixType.REGRESSION_GUARD,
            confidence=FixConfidence.HIGH,
            title="Add regression guard to reject worsening changes",
            description=f"Block changes that worsen the metric by more than {tolerance:.1%} from the best known value.",
            rationale="Without a regression guard, the agent can accidentally undo good progress. This ensures monotonic improvement within a tolerance.",
            code_changes=[
                CodeChange(
                    file_path="utils/regression_guard.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Regression guard that rejects changes worsening metrics",
                )
            ],
            estimated_impact="Prevents accidental loss of progress, enforces near-monotonic improvement",
            tags=["convergence", "regression", "guard"],
        )

    def _direction_lock_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''class DirectionLock:
    """Commit to a direction once improvement is confirmed, preventing oscillation."""

    def __init__(self, confirmation_steps: int = 3):
        self.confirmation_steps = confirmation_steps
        self.locked_approach = None
        self.approach_history = []
        self.approach_scores = {}

    def select_approach(self, candidates: list) -> str:
        """Select which approach to try next, locking once one is confirmed."""
        if self.locked_approach:
            return self.locked_approach

        # Try approaches round-robin until one shows consistent improvement
        if not self.approach_history:
            return candidates[0]

        # Find the best-performing approach
        for approach, scores in self.approach_scores.items():
            if len(scores) >= self.confirmation_steps:
                # Check for consistent improvement
                improvements = sum(1 for i in range(1, len(scores)) if scores[i] < scores[i-1])
                if improvements >= self.confirmation_steps - 1:
                    self.locked_approach = approach
                    return approach

        # Round-robin through untried or undersampled approaches
        counts = {c: len(self.approach_scores.get(c, [])) for c in candidates}
        return min(candidates, key=lambda c: counts.get(c, 0))

    def record(self, approach: str, metric_value: float):
        self.approach_history.append(approach)
        self.approach_scores.setdefault(approach, []).append(metric_value)'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="convergence_failure",
            fix_type=FixType.DIRECTION_LOCK,
            confidence=FixConfidence.MEDIUM,
            title="Add direction lock to prevent oscillation between approaches",
            description="Once an approach shows confirmed improvement, lock onto it instead of alternating between approaches.",
            rationale="Thrashing occurs when the agent oscillates between approaches without committing. Direction locking ensures consistent progress once a promising direction is found.",
            code_changes=[
                CodeChange(
                    file_path="utils/direction_lock.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Direction lock that commits to an approach after confirmed improvement",
                )
            ],
            estimated_impact="Eliminates oscillation, ensures consistent exploration of promising directions",
            tags=["convergence", "thrashing", "direction-lock"],
        )

    def _exploration_temperature_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import random
import math

class ExplorationScheduler:
    """Adjust exploration randomness based on convergence health."""

    def __init__(self, initial_temp: float = 1.0, min_temp: float = 0.1,
                 decay_rate: float = 0.95):
        self.temperature = initial_temp
        self.min_temp = min_temp
        self.decay_rate = decay_rate
        self.recent_values = []

    def should_explore(self) -> bool:
        """Return True if the agent should try a random direction."""
        return random.random() < self.temperature

    def update(self, metric_value: float):
        """Adjust temperature based on recent convergence behavior."""
        self.recent_values.append(metric_value)
        if len(self.recent_values) < 3:
            return

        # Detect thrashing: many direction reversals
        reversals = sum(
            1 for i in range(2, len(self.recent_values[-5:]))
            if (self.recent_values[-5:][i] - self.recent_values[-5:][i-1]) *
               (self.recent_values[-5:][i-1] - self.recent_values[-5:][i-2]) < 0
        )

        if reversals >= 2:
            # Increase temperature to break out of oscillation
            self.temperature = min(1.0, self.temperature * 1.5)
        else:
            # Cool down normally
            self.temperature = max(self.min_temp, self.temperature * self.decay_rate)'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="convergence_failure",
            fix_type=FixType.EXPLORATION_TEMPERATURE,
            confidence=FixConfidence.MEDIUM,
            title="Add exploration temperature scheduling",
            description="Dynamically adjust exploration randomness — increase when thrashing is detected, decrease during steady improvement.",
            rationale="Thrashing often means the agent is stuck between two similar options. Increasing exploration temperature helps escape this by trying more diverse approaches.",
            code_changes=[
                CodeChange(
                    file_path="utils/exploration_scheduler.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Exploration temperature scheduler with thrashing detection",
                )
            ],
            estimated_impact="Breaks through oscillation patterns by diversifying exploration",
            tags=["convergence", "thrashing", "exploration"],
        )

    def _emergency_stop_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''class DivergenceMonitor:
    """Monitor metrics for divergence and trigger emergency stop."""

    def __init__(self, max_wrong_direction_ratio: float = 0.7,
                 window_size: int = 5):
        self.max_wrong_ratio = max_wrong_direction_ratio
        self.window_size = window_size
        self.values = []
        self.direction = "minimize"  # or "maximize"

    def record(self, value: float) -> bool:
        """Record a value. Returns False if emergency stop triggered."""
        self.values.append(value)
        if len(self.values) < self.window_size:
            return True  # Not enough data

        recent = self.values[-self.window_size:]
        wrong_steps = 0
        for i in range(1, len(recent)):
            if self.direction == "minimize" and recent[i] > recent[i-1]:
                wrong_steps += 1
            elif self.direction == "maximize" and recent[i] < recent[i-1]:
                wrong_steps += 1

        ratio = wrong_steps / (len(recent) - 1)
        if ratio >= self.max_wrong_ratio:
            logger.error(
                f"EMERGENCY STOP: {ratio:.0%} of last {self.window_size} steps "
                f"moving in wrong direction"
            )
            return False  # Trigger stop

        return True  # Continue

# Usage
monitor = DivergenceMonitor(direction="minimize")
for step in range(max_steps):
    result = run_experiment()
    if not monitor.record(result["metric"]):
        logger.error("Halting: metric is diverging")
        break'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="convergence_failure",
            fix_type=FixType.EMERGENCY_STOP,
            confidence=FixConfidence.HIGH,
            title="Add divergence monitor with emergency stop",
            description="Halt iterations immediately when the metric consistently moves in the wrong direction.",
            rationale="Divergence means the agent is actively making things worse. Continuing wastes compute and may cause irreversible damage. An emergency stop prevents further degradation.",
            code_changes=[
                CodeChange(
                    file_path="utils/divergence_monitor.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Divergence monitor with automatic emergency stop",
                )
            ],
            estimated_impact="Prevents wasted compute and further metric degradation",
            breaking_changes=False,
            tags=["convergence", "divergence", "emergency-stop"],
        )

    def _early_stopping_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        patience = details.get("stalled_steps", 5)
        code = f'''class EarlyStopping:
    """Stop iterating when no improvement is seen for `patience` steps."""

    def __init__(self, patience: int = {patience}, min_delta: float = 0.001,
                 direction: str = "minimize"):
        self.patience = patience
        self.min_delta = min_delta
        self.direction = direction
        self.best_value = None
        self.counter = 0

    def should_stop(self, metric_value: float) -> bool:
        if self.best_value is None:
            self.best_value = metric_value
            return False

        if self.direction == "minimize":
            improved = metric_value < self.best_value - self.min_delta
        else:
            improved = metric_value > self.best_value + self.min_delta

        if improved:
            self.best_value = metric_value
            self.counter = 0
        else:
            self.counter += 1

        return self.counter >= self.patience

# Usage
stopper = EarlyStopping(patience={patience})
for step in range(max_steps):
    result = run_experiment()
    if stopper.should_stop(result["metric"]):
        logger.info(f"Early stopping at step {{step}} (no improvement for {patience} steps)")
        break'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="convergence_failure",
            fix_type=FixType.PROGRESS_MONITORING,
            confidence=FixConfidence.HIGH,
            title=f"Add early stopping (patience={patience})",
            description=f"Stop iterating after {patience} consecutive steps without meaningful improvement.",
            rationale="Continuing to iterate without improvement wastes compute. Early stopping saves resources and lets the agent move on.",
            code_changes=[
                CodeChange(
                    file_path="utils/early_stopping.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Early stopping with configurable patience",
                )
            ],
            estimated_impact="Saves compute by terminating unproductive iteration loops",
            tags=["convergence", "plateau", "early-stopping"],
        )
