"""Subagent Permission Boundary Violation Detection.

Detects when YAML-defined subagents violate their permission boundaries:
- Using tools not in allowed_tools list
- Attempting to spawn child agents (not allowed for subagents)
- Output drifting from parent instruction scope

Based on Claude Code Subagents (early 2026).
"""

from typing import Any, Dict, List, Tuple

def detect(
    allowed_tools: List[str] = None,
    actual_tool_calls: List[str] = None,
    parent_instruction: str = "",
    subagent_output: str = "",
    spawn_attempts: int = 0,
) -> Tuple[bool, float]:
    allowed = set(allowed_tools or [])
    actual = actual_tool_calls or []
    if not allowed and not actual and not spawn_attempts:
        return False, 0.0

    scores = []

    # 1. Tool boundary violation
    if allowed and actual:
        violations = [t for t in actual if t not in allowed]
        if violations:
            violation_rate = len(violations) / len(actual)
            scores.append(min(1.0, violation_rate + 0.3))

    # 2. Spawn attempt (subagents cannot spawn children)
    if spawn_attempts > 0:
        scores.append(min(1.0, 0.5 + spawn_attempts * 0.2))

    # 3. Scope drift: output doesn't relate to parent instruction
    if parent_instruction and subagent_output:
        stop = {"the", "a", "an", "to", "in", "on", "is", "and", "or", "of", "for", "it", "that", "this"}
        instr_words = {w.lower() for w in parent_instruction.split() if len(w) > 3 and w.lower() not in stop}
        out_words = set(subagent_output.lower().split())
        if instr_words:
            overlap = len(instr_words & out_words) / len(instr_words)
            if overlap < 0.15:
                scores.append(0.6)

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
