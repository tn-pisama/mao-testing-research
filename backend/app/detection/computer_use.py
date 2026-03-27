"""Computer Use Failure Detection — Screen Interaction Errors.

Detects failures when Claude controls a desktop via screenshots + clicking.
Thresholds calibrated against real benchmarks:
- OSWorld benchmark: 72.5% success rate (27.5% failure is NORMAL)
- Pace Insurance: 94% on structured workflows
- Known issues: hallucinated tool calls, multi-app failures, niche GUI misclicks

Error rate threshold at 40% (not 30%) because 28% failure is baseline.

EXPERIMENTAL: Based on benchmark data. Will improve with production traces.
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def detect(
    actions: List[Dict[str, Any]] = None,
    task: str = "",
    final_state: str = "",
) -> Tuple[bool, float]:
    """Detect screen interaction failures.

    Args:
        actions: List of {type, target, result, screenshot_description}
        task: Original task description
        final_state: Description of final screen state
    """
    action_list = actions or []
    if not action_list:
        return False, 0.0

    scores = []

    # 1. Error rate — OSWorld baseline is 27.5% failure. Flag at 40%+.
    errors = sum(1 for a in action_list if a.get("result") == "error")
    error_rate = errors / len(action_list)
    if error_rate > 0.4:
        scores.append(min(1.0, (error_rate - 0.4) * 3))  # 0.4→0, 0.7→0.9

    # 2. Repeated identical actions (loop/stuck) — flag at 3+ consecutive
    consecutive_repeats = 0
    max_repeats = 0
    for i in range(1, len(action_list)):
        prev = (action_list[i - 1].get("type"), action_list[i - 1].get("target"))
        curr = (action_list[i].get("type"), action_list[i].get("target"))
        if prev == curr:
            consecutive_repeats += 1
            max_repeats = max(max_repeats, consecutive_repeats)
        else:
            consecutive_repeats = 0
    if max_repeats >= 3:
        scores.append(min(1.0, max_repeats * 0.25))

    # 3. Consecutive failed interactions — flag at 5+ (retries are normal)
    consec_fails = 0
    max_consec_fails = 0
    for a in action_list:
        if a.get("result") == "error":
            consec_fails += 1
            max_consec_fails = max(max_consec_fails, consec_fails)
        else:
            consec_fails = 0
    if max_consec_fails >= 5:
        scores.append(min(1.0, (max_consec_fails - 4) * 0.2))

    # 4. Hallucinated actions: action type doesn't match any known type
    known_types = {"click", "type", "screenshot", "scroll", "key", "drag", "wait", "move"}
    hallucinated = [a for a in action_list if a.get("type", "").lower() not in known_types and a.get("type")]
    if hallucinated:
        scores.append(min(1.0, len(hallucinated) * 0.3))

    # 5. Task completion check — only if both task and final_state provided
    # Use lenient 10% overlap (outputs use different vocabulary than tasks)
    if task and final_state:
        stop = {"the", "a", "an", "to", "in", "on", "is", "and", "or", "of", "for", "it", "my", "me"}
        task_words = {w.lower() for w in task.split() if len(w) > 3 and w.lower() not in stop}
        state_words = {w.lower() for w in final_state.split() if len(w) > 3}
        if task_words:
            overlap = len(task_words & state_words) / len(task_words)
            if overlap < 0.1:
                scores.append(0.6)

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
