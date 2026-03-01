"""
OpenClaw Spawn Chain Detector
==============================

Detects suspicious session.spawn chains in OpenClaw:
- Spawn depth exceeding threshold (>3 spawns in a session)
- Circular references (spawned session ID equals current or prior IDs)
- Privilege escalation patterns across spawns

Mapped to failure mode F11 (Coordination Failure / Delegation Storm).
"""

import logging
from typing import Any, Dict, List, Optional, Set

from app.detection.turn_aware._base import (
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    TurnSnapshot,
)

logger = logging.getLogger(__name__)

MAX_SAFE_SPAWN_DEPTH = 3

# Keywords suggesting higher-privilege agents
PRIVILEGE_KEYWORDS = {
    "admin", "root", "supervisor", "manager", "elevated", "privileged",
    "system", "internal", "master", "controller",
}


class OpenClawSpawnChainDetector(TurnAwareDetector):
    """Detects F11: Spawn chain issues in OpenClaw sessions.

    Checks:
    1. Spawn depth: >3 session.spawn events signals excessive delegation.
    2. Circular references: a spawned_session_id matching the current session
       or any previously spawned session.
    3. Privilege escalation: each successive spawn targets a higher-privilege
       agent (based on keyword heuristics).
    """

    name = "OpenClawSpawnChainDetector"
    version = "1.0"
    supported_failure_modes = ["F11"]

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        session = (conversation_metadata or {}).get("session", {})
        return self.detect_session(session)

    def detect_session(self, session: dict) -> TurnAwareDetectionResult:
        events = session.get("events", [])
        session_id = session.get("session_id", "")

        if not events:
            return self._no_detection("No events in session")

        spawn_events = [
            (i, evt)
            for i, evt in enumerate(events)
            if evt.get("type") == "session.spawn"
        ]

        if not spawn_events:
            return self._no_detection("No spawn events in session")

        issues: List[Dict[str, Any]] = []
        affected_turns: List[int] = []
        spawn_count = len(spawn_events)

        # --- 1. Excessive spawn depth ---
        if spawn_count > MAX_SAFE_SPAWN_DEPTH:
            indices = [idx for idx, _ in spawn_events]
            issues.append({
                "type": "excessive_depth",
                "spawn_count": spawn_count,
                "threshold": MAX_SAFE_SPAWN_DEPTH,
                "description": f"{spawn_count} spawns exceed safe depth of {MAX_SAFE_SPAWN_DEPTH}",
            })
            affected_turns.extend(indices)

        # --- 2. Circular references ---
        seen_ids: Set[str] = {session_id} if session_id else set()
        for idx, evt in spawn_events:
            spawned_id = evt.get("spawned_session_id", "")
            if spawned_id and spawned_id in seen_ids:
                issues.append({
                    "type": "circular_reference",
                    "spawned_session_id": spawned_id,
                    "event_index": idx,
                    "description": f"Circular spawn: '{spawned_id}' already seen",
                })
                affected_turns.append(idx)
            if spawned_id:
                seen_ids.add(spawned_id)

        # --- 3. Privilege escalation pattern ---
        targets = [
            (idx, (evt.get("target_agent") or "").lower())
            for idx, evt in spawn_events
        ]
        escalation_chain: List[str] = []
        escalation_indices: List[int] = []
        for idx, agent in targets:
            if any(kw in agent for kw in PRIVILEGE_KEYWORDS):
                escalation_chain.append(agent)
                escalation_indices.append(idx)

        if len(escalation_chain) >= 2:
            issues.append({
                "type": "privilege_escalation",
                "chain": escalation_chain,
                "description": (
                    f"Privilege escalation pattern: spawning {len(escalation_chain)} "
                    f"privileged agents ({', '.join(escalation_chain)})"
                ),
            })
            affected_turns.extend(escalation_indices)

        if not issues:
            return self._no_detection("Spawn chain within safe limits")

        confidence = min(1.0, spawn_count / 4)

        has_circular = any(i["type"] == "circular_reference" for i in issues)
        has_escalation = any(i["type"] == "privilege_escalation" for i in issues)

        if has_circular:
            severity = TurnAwareSeverity.SEVERE
        elif has_escalation or spawn_count > MAX_SAFE_SPAWN_DEPTH * 2:
            severity = TurnAwareSeverity.SEVERE
        elif spawn_count > MAX_SAFE_SPAWN_DEPTH:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F11",
            explanation=f"Spawn chain issue: {len(issues)} problem(s) across {spawn_count} spawns",
            affected_turns=sorted(set(affected_turns)),
            evidence={
                "issues": issues,
                "spawn_count": spawn_count,
                "session_id": session_id,
                "spawned_ids": list(seen_ids - {session_id}),
            },
            suggested_fix=(
                "Limit spawn chain depth with a max_depth parameter. "
                "Track visited session IDs to prevent circular spawning. "
                "Require explicit authorization for privileged agent spawns."
            ),
            detector_name=self.name,
        )

    def _no_detection(self, explanation: str) -> TurnAwareDetectionResult:
        return TurnAwareDetectionResult(
            detected=False,
            severity=TurnAwareSeverity.NONE,
            confidence=0.0,
            failure_mode=None,
            explanation=explanation,
            detector_name=self.name,
        )
