"""Computer Use Failure Detection — Screen Interaction Errors.

Detects failures when Claude controls a desktop via screenshots + clicking:
- Screen misinterpretation (wrong click target)
- Action sequence loops (repeated identical actions)
- Task completion failure (final state doesn't match intent)
- Consecutive failed interactions

Based on Anthropic Computer Use (March 2026 research preview).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ComputerUseResult:
    detected: bool
    confidence: float
    issues: List[str] = field(default_factory=list)


def detect(
    actions: List[Dict[str, Any]],
    task: str = "",
    final_state: str = "",
) -> Tuple[bool, float]:
    """Detect screen interaction failures.

    Args:
        actions: List of {type, target, result, screenshot_description}
        task: Original task description
        final_state: Description of final screen state
    """
    if not actions:
        return False, 0.0

    issues = []
    scores = []

    # 1. Error rate
    errors = sum(1 for a in actions if a.get("result") == "error")
    error_rate = errors / len(actions)
    if error_rate > 0.3:
        issues.append(f"High error rate: {error_rate:.0%} of actions failed")
        scores.append(min(1.0, error_rate * 1.5))

    # 2. Repeated identical actions (loop)
    consecutive_repeats = 0
    max_repeats = 0
    for i in range(1, len(actions)):
        prev = (actions[i - 1].get("type"), actions[i - 1].get("target"))
        curr = (actions[i].get("type"), actions[i].get("target"))
        if prev == curr:
            consecutive_repeats += 1
            max_repeats = max(max_repeats, consecutive_repeats)
        else:
            consecutive_repeats = 0
    if max_repeats >= 2:
        issues.append(f"Action loop: {max_repeats + 1} identical consecutive actions")
        scores.append(min(1.0, max_repeats * 0.3))

    # 3. Consecutive failed clicks
    consec_fails = 0
    max_consec_fails = 0
    for a in actions:
        if a.get("result") == "error" and a.get("type") in ("click", "type"):
            consec_fails += 1
            max_consec_fails = max(max_consec_fails, consec_fails)
        else:
            consec_fails = 0
    if max_consec_fails > 3:
        issues.append(f"{max_consec_fails} consecutive failed interactions")
        scores.append(min(1.0, max_consec_fails * 0.2))

    # 4. Task completion check
    if task and final_state:
        stop = {"the", "a", "an", "to", "in", "on", "is", "and", "or", "of", "for", "it"}
        task_words = {w.lower() for w in task.split() if len(w) > 3 and w.lower() not in stop}
        state_words = {w.lower() for w in final_state.split() if len(w) > 3}
        if task_words:
            overlap = len(task_words & state_words) / len(task_words)
            if overlap < 0.2:
                issues.append(f"Final state doesn't match task intent (overlap: {overlap:.0%})")
                scores.append(0.7)

    if not scores:
        return False, 0.0

    confidence = max(scores)
    return True, round(confidence, 4)
