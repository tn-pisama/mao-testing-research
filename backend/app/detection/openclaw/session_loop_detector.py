"""
OpenClaw Session Loop Detector
==============================

Detects repetitive patterns in OpenClaw session event streams:
- Consecutive identical tool calls (same name + input hash)
- Ping-pong patterns between session.spawn/send and a fixed target

Mapped to failure mode F8 (Infinite Loop / Repetitive Behavior).
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from app.detection.turn_aware._base import (
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    TurnSnapshot,
)

logger = logging.getLogger(__name__)

MIN_CONSECUTIVE_REPEATS = 3


def _hash_input(tool_input: Any) -> str:
    """Produce a stable hash for a tool_input value."""
    raw = json.dumps(tool_input, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class OpenClawSessionLoopDetector(TurnAwareDetector):
    """Detects F8: Session-level loops in OpenClaw event streams.

    Looks for:
    1. Consecutive identical tool.call events (same tool_name + tool_input hash).
       3+ identical consecutive calls triggers detection.
    2. Ping-pong patterns where session.spawn or session.send alternates with
       the same target session/agent repeatedly.
    """

    name = "OpenClawSessionLoopDetector"
    version = "1.0"
    supported_failure_modes = ["F8"]

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Delegate to detect_session when called via the base interface."""
        session = (conversation_metadata or {}).get("session", {})
        return self.detect_session(session)

    def detect_session(self, session: dict) -> TurnAwareDetectionResult:
        events = session.get("events", [])
        if not events:
            return self._no_detection("No events in session")

        issues: List[Dict[str, Any]] = []
        affected_turns: List[int] = []

        # --- 1. Consecutive identical tool calls ---
        tool_loop = self._detect_tool_call_loop(events)
        if tool_loop["detected"]:
            issues.append(tool_loop)
            affected_turns.extend(tool_loop.get("turns", []))

        # --- 2. Spawn / send ping-pong ---
        ping_pong = self._detect_spawn_ping_pong(events)
        if ping_pong["detected"]:
            issues.append(ping_pong)
            affected_turns.extend(ping_pong.get("turns", []))

        if not issues:
            return self._no_detection("No loop patterns detected")

        max_repeats = max(i.get("repeat_count", 0) for i in issues)
        confidence = min(1.0, max_repeats / 5)

        if max_repeats >= 6:
            severity = TurnAwareSeverity.SEVERE
        elif max_repeats >= 4:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F8",
            explanation=f"Session loop detected: {len(issues)} pattern(s), max {max_repeats} repeats",
            affected_turns=sorted(set(affected_turns)),
            evidence={"issues": issues, "total_events": len(events)},
            suggested_fix=(
                "Add loop-breaking conditions or retry limits. "
                "Ensure tool calls advance state rather than repeating identically."
            ),
            detector_name=self.name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_tool_call_loop(self, events: List[dict]) -> Dict[str, Any]:
        """Find runs of consecutive tool.call events with identical name+input."""
        tool_calls = [
            (idx, evt)
            for idx, evt in enumerate(events)
            if evt.get("type") == "tool.call"
        ]

        if len(tool_calls) < MIN_CONSECUTIVE_REPEATS:
            return {"detected": False}

        best_run_start = 0
        best_run_len = 1
        run_start = 0
        run_len = 1

        for i in range(1, len(tool_calls)):
            prev_idx, prev = tool_calls[i - 1]
            cur_idx, cur = tool_calls[i]

            # Allow intermediate events (agent.turn, tool.result) between tool calls
            same_name = prev.get("tool_name") == cur.get("tool_name")
            same_input = _hash_input(prev.get("tool_input")) == _hash_input(cur.get("tool_input"))
            consecutive = cur_idx - prev_idx <= 4  # allow up to 3 events between tool calls

            if same_name and same_input and consecutive:
                run_len += 1
            else:
                if run_len > best_run_len:
                    best_run_len = run_len
                    best_run_start = run_start
                run_start = i
                run_len = 1

        if run_len > best_run_len:
            best_run_len = run_len
            best_run_start = run_start

        if best_run_len >= MIN_CONSECUTIVE_REPEATS:
            affected = [tool_calls[best_run_start + j][0] for j in range(best_run_len)]
            sample_evt = tool_calls[best_run_start][1]
            return {
                "detected": True,
                "type": "tool_call_loop",
                "repeat_count": best_run_len,
                "tool_name": sample_evt.get("tool_name"),
                "turns": affected,
                "description": (
                    f"Tool '{sample_evt.get('tool_name')}' called "
                    f"{best_run_len} times consecutively with identical input"
                ),
            }

        return {"detected": False}

    def _detect_spawn_ping_pong(self, events: List[dict]) -> Dict[str, Any]:
        """Detect alternating spawn/send events targeting the same session."""
        spawn_send = [
            (idx, evt)
            for idx, evt in enumerate(events)
            if evt.get("type") in ("session.spawn", "session.send")
        ]

        if len(spawn_send) < MIN_CONSECUTIVE_REPEATS:
            return {"detected": False}

        def _target(evt: dict) -> str:
            return evt.get("target_session", "") or evt.get("target_agent", "") or evt.get("spawned_session_id", "")

        best_count = 1
        best_target = ""
        best_indices: List[int] = []
        count = 1
        cur_target = _target(spawn_send[0][1])
        indices = [spawn_send[0][0]]

        for i in range(1, len(spawn_send)):
            t = _target(spawn_send[i][1])
            if t == cur_target and t:
                count += 1
                indices.append(spawn_send[i][0])
            else:
                if count > best_count:
                    best_count = count
                    best_target = cur_target
                    best_indices = list(indices)
                cur_target = t
                count = 1
                indices = [spawn_send[i][0]]

        if count > best_count:
            best_count = count
            best_target = cur_target
            best_indices = list(indices)

        if best_count >= MIN_CONSECUTIVE_REPEATS:
            return {
                "detected": True,
                "type": "spawn_ping_pong",
                "repeat_count": best_count,
                "target": best_target,
                "turns": best_indices,
                "description": (
                    f"Spawn/send ping-pong: {best_count} events "
                    f"targeting '{best_target}'"
                ),
            }

        return {"detected": False}

    def _no_detection(self, explanation: str) -> TurnAwareDetectionResult:
        return TurnAwareDetectionResult(
            detected=False,
            severity=TurnAwareSeverity.NONE,
            confidence=0.0,
            failure_mode=None,
            explanation=explanation,
            detector_name=self.name,
        )
