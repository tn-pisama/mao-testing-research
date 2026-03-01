"""
LangGraph State Corruption Detector
=====================================

Detects state corruption between consecutive state_snapshots:
- Type changes: a key's value type changes (str->int, list->dict)
- Null injections: a key becomes None when previously set
- Unexpected field deletions: key present in snapshot N, missing in N+1
- Value explosion: list/dict size grows >10x between snapshots
"""

import logging
from typing import Any, Dict, List, Optional

from app.detection.turn_aware._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)

logger = logging.getLogger(__name__)


def _value_size(value: Any) -> int:
    """Return the size of a container value, or 0 for scalars."""
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, str):
        return len(value)
    return 0


def _type_label(value: Any) -> str:
    """Return a readable type label for a value."""
    if value is None:
        return "null"
    return type(value).__name__


class LangGraphStateCorruptionDetector(TurnAwareDetector):
    """Detects state corruption across LangGraph state snapshots.

    Compares consecutive state_snapshots for:
    1. Type changes on the same key
    2. Null injections (non-None -> None)
    3. Unexpected field deletions
    4. Value explosion (container size grows >10x)
    """

    name = "LangGraphStateCorruptionDetector"
    version = "1.0"
    supported_failure_modes = ["F3"]

    def __init__(self, explosion_factor: float = 10.0):
        self.explosion_factor = explosion_factor

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Delegate to graph execution analysis."""
        graph_execution = (conversation_metadata or {}).get("graph_execution", {})
        if graph_execution:
            return self.detect_graph_execution(graph_execution)
        return TurnAwareDetectionResult(
            detected=False,
            severity=TurnAwareSeverity.NONE,
            confidence=0.0,
            failure_mode=None,
            explanation="No graph_execution data provided",
            detector_name=self.name,
        )

    def detect_graph_execution(
        self, graph_execution: Dict[str, Any]
    ) -> TurnAwareDetectionResult:
        """Analyze state_snapshots for corruption signals."""
        snapshots = graph_execution.get("state_snapshots", [])

        if len(snapshots) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 2 state snapshots to detect corruption",
                detector_name=self.name,
            )

        # Sort by superstep to ensure ordering
        snapshots = sorted(snapshots, key=lambda s: s.get("superstep", 0))

        corruption_signals: List[Dict[str, Any]] = []
        affected_supersteps: List[int] = []

        for i in range(len(snapshots) - 1):
            prev_state = snapshots[i].get("state", {}) or {}
            curr_state = snapshots[i + 1].get("state", {}) or {}
            prev_step = snapshots[i].get("superstep", i)
            curr_step = snapshots[i + 1].get("superstep", i + 1)

            # Check all keys in previous state
            for key in prev_state:
                prev_val = prev_state[key]
                if key not in curr_state:
                    # Field deletion
                    corruption_signals.append({
                        "type": "field_deletion",
                        "key": key,
                        "superstep_from": prev_step,
                        "superstep_to": curr_step,
                        "description": (
                            f"Key '{key}' present at superstep {prev_step} "
                            f"but missing at superstep {curr_step}"
                        ),
                    })
                    affected_supersteps.append(curr_step)
                    continue

                curr_val = curr_state[key]

                # Null injection
                if prev_val is not None and curr_val is None:
                    corruption_signals.append({
                        "type": "null_injection",
                        "key": key,
                        "previous_type": _type_label(prev_val),
                        "superstep_from": prev_step,
                        "superstep_to": curr_step,
                        "description": (
                            f"Key '{key}' changed from {_type_label(prev_val)} "
                            f"to null at superstep {curr_step}"
                        ),
                    })
                    affected_supersteps.append(curr_step)
                    continue

                # Type change (skip if either is None)
                if (
                    prev_val is not None
                    and curr_val is not None
                    and type(prev_val) != type(curr_val)
                ):
                    corruption_signals.append({
                        "type": "type_change",
                        "key": key,
                        "previous_type": _type_label(prev_val),
                        "current_type": _type_label(curr_val),
                        "superstep_from": prev_step,
                        "superstep_to": curr_step,
                        "description": (
                            f"Key '{key}' type changed from "
                            f"{_type_label(prev_val)} to {_type_label(curr_val)} "
                            f"at superstep {curr_step}"
                        ),
                    })
                    affected_supersteps.append(curr_step)
                    continue

                # Value explosion
                prev_size = _value_size(prev_val)
                curr_size = _value_size(curr_val)
                if (
                    prev_size > 0
                    and curr_size > prev_size * self.explosion_factor
                ):
                    corruption_signals.append({
                        "type": "value_explosion",
                        "key": key,
                        "previous_size": prev_size,
                        "current_size": curr_size,
                        "growth_factor": round(curr_size / prev_size, 1),
                        "superstep_from": prev_step,
                        "superstep_to": curr_step,
                        "description": (
                            f"Key '{key}' size grew from {prev_size} to "
                            f"{curr_size} ({curr_size / prev_size:.0f}x) "
                            f"at superstep {curr_step}"
                        ),
                    })
                    affected_supersteps.append(curr_step)

        if not corruption_signals:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No state corruption detected across snapshots",
                detector_name=self.name,
            )

        # Confidence: 0.6 base + 0.1 per signal, capped at 0.95
        confidence = min(0.95, 0.6 + len(corruption_signals) * 0.1)

        # Severity based on signal types
        signal_types = {s["type"] for s in corruption_signals}
        if "type_change" in signal_types or "field_deletion" in signal_types:
            severity = TurnAwareSeverity.SEVERE
        elif "null_injection" in signal_types:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        type_counts = {}
        for s in corruption_signals:
            type_counts[s["type"]] = type_counts.get(s["type"], 0) + 1
        summary_parts = [f"{count} {stype}" for stype, count in type_counts.items()]

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F3",
            explanation=(
                f"State corruption detected: {', '.join(summary_parts)} "
                f"across {len(snapshots)} snapshots"
            ),
            affected_turns=sorted(set(affected_supersteps)),
            evidence={
                "signals": corruption_signals,
                "total_snapshots": len(snapshots),
                "signal_count": len(corruption_signals),
            },
            suggested_fix=(
                "Validate state schema between supersteps. Use TypedDict or "
                "Pydantic models for state to enforce type safety. Add state "
                "reducers that handle None values gracefully."
            ),
            detector_name=self.name,
        )
