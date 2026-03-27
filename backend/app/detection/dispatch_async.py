"""Dispatch Async Failure Detection — Phone→Desktop Background Tasks.

Detects failures in Anthropic Dispatch (March 2026): async task execution
where instructions come from phone and execute on desktop.

Failure modes: context loss, timeout, no recovery, staleness.
"""

from typing import Any, Dict, List, Tuple

def detect(
    instruction: str = "",
    execution_steps: List[Dict[str, Any]] = None,
    result: str = "",
    instruction_timestamp: str = "",
    result_timestamp: str = "",
) -> Tuple[bool, float]:
    steps = execution_steps or []
    if not instruction and not steps:
        return False, 0.0

    scores = []

    # 1. Context loss: result doesn't reference instruction
    if instruction and result:
        stop = {"the", "a", "to", "in", "and", "or", "of", "for", "is", "it", "my", "me"}
        instr_words = {w.lower() for w in instruction.split() if len(w) > 3 and w.lower() not in stop}
        result_words = set(result.lower().split())
        if instr_words:
            overlap = len(instr_words & result_words) / len(instr_words)
            if overlap < 0.15:
                scores.append(0.8)

    # 2. Timeout: total latency > 300s with no progress
    if steps:
        total_latency = sum(s.get("latency_ms", 0) for s in steps)
        if total_latency > 300000:
            scores.append(min(1.0, total_latency / 600000))

    # 3. Error without recovery
    errors = [s for s in steps if s.get("status") == "error"]
    if errors:
        has_retry = any(
            steps[i + 1].get("action") == steps[i].get("action")
            for i in range(len(steps) - 1)
            if steps[i].get("status") == "error"
        )
        if not has_retry:
            scores.append(0.7)

    # 4. Staleness: long gap between instruction and result
    if instruction_timestamp and result_timestamp:
        try:
            from datetime import datetime
            t1 = datetime.fromisoformat(instruction_timestamp.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(result_timestamp.replace("Z", "+00:00"))
            gap_s = (t2 - t1).total_seconds()
            if gap_s > 600:
                scores.append(min(1.0, gap_s / 1200))
        except (ValueError, TypeError):
            pass

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
