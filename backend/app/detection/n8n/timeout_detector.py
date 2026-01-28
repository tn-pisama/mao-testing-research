"""
F13: Workflow Timeout Detection for n8n
=======================================

Detects workflows that exceed expected duration thresholds:
- Workflow duration > configurable threshold (default: 5 min)
- Webhook execution > 30s (caller likely timed out)
- Node execution > expected duration for node type
- Stalled workflows (no progress for 60s+)

This is n8n-specific because it analyzes workflow execution timing patterns
rather than conversational turn-taking dynamics.
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

# Default timeouts in milliseconds
DEFAULT_MAX_WORKFLOW_DURATION_MS = 300_000  # 5 minutes
DEFAULT_MAX_WEBHOOK_WAIT_MS = 30_000  # 30 seconds
DEFAULT_STALL_THRESHOLD_MS = 60_000  # 60 seconds no progress

# Node type timeout thresholds (ms)
NODE_TIMEOUT_THRESHOLDS = {
    "n8n-nodes-base.httpRequest": 30_000,
    "n8n-nodes-base.openAi": 120_000,  # AI calls can be slow
    "n8n-nodes-base.anthropicChat": 120_000,
    "n8n-nodes-base.function": 10_000,
    "n8n-nodes-base.set": 1_000,
    "n8n-nodes-base.merge": 5_000,
    "n8n-nodes-base.if": 1_000,
    "default": 60_000,  # 1 minute default
}


class N8NTimeoutDetector(TurnAwareDetector):
    """Detects F13: Workflow Timeout failures in n8n workflows.

    Analyzes workflow execution for:
    1. Workflow duration exceeding thresholds
    2. Webhook response timeouts (>30s)
    3. Individual node timeouts
    4. Stalled execution (no progress)

    n8n-specific manifestation of F13 (Completion Failure):
    In conversational agents, this is about tasks not completing.
    In n8n workflows, this is about execution timeouts and stalls.
    """

    name = "N8NTimeoutDetector"
    version = "1.0"
    supported_failure_modes = ["F13"]

    def __init__(
        self,
        max_workflow_duration_ms: int = DEFAULT_MAX_WORKFLOW_DURATION_MS,
        max_webhook_wait_ms: int = DEFAULT_MAX_WEBHOOK_WAIT_MS,
        stall_threshold_ms: int = DEFAULT_STALL_THRESHOLD_MS,
        node_timeout_thresholds: Optional[Dict[str, int]] = None,
    ):
        """Initialize timeout detector.

        Args:
            max_workflow_duration_ms: Maximum workflow duration before flagging
            max_webhook_wait_ms: Maximum webhook wait time before caller timeout
            stall_threshold_ms: Time without progress indicating stall
            node_timeout_thresholds: Custom timeouts per node type
        """
        self.max_workflow_duration_ms = max_workflow_duration_ms
        self.max_webhook_wait_ms = max_webhook_wait_ms
        self.stall_threshold_ms = stall_threshold_ms
        self.node_timeout_thresholds = (
            node_timeout_thresholds or NODE_TIMEOUT_THRESHOLDS
        )

    def _get_workflow_duration(
        self, turns: List[TurnSnapshot], metadata: Optional[Dict[str, Any]]
    ) -> Optional[int]:
        """Calculate total workflow duration in milliseconds."""
        if not turns:
            return None

        # Try to get from metadata first
        if metadata and "workflow_duration_ms" in metadata:
            return metadata["workflow_duration_ms"]

        # Calculate from turn timestamps if available
        if turns[0].turn_metadata.get("timestamp") and turns[-1].turn_metadata.get(
            "timestamp"
        ):
            start = turns[0].turn_metadata["timestamp"]
            end = turns[-1].turn_metadata["timestamp"]
            # Assuming timestamps are datetime objects or ISO strings
            try:
                from datetime import datetime

                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if isinstance(end, str):
                    end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                duration = (end - start).total_seconds() * 1000
                return int(duration)
            except Exception as e:
                logger.warning(f"Failed to calculate duration from timestamps: {e}")
                return None

        return None

    def _detect_workflow_timeout(
        self, turns: List[TurnSnapshot], metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect if overall workflow exceeded duration threshold."""
        duration_ms = self._get_workflow_duration(turns, metadata)
        if duration_ms is None:
            return None

        if duration_ms > self.max_workflow_duration_ms:
            return {
                "detected": True,
                "type": "workflow_timeout",
                "duration_ms": duration_ms,
                "threshold_ms": self.max_workflow_duration_ms,
                "explanation": f"Workflow took {duration_ms / 1000:.1f}s (threshold: {self.max_workflow_duration_ms / 1000:.1f}s)",
                "turns": list(range(len(turns))),
            }

        return None

    def _detect_webhook_timeout(
        self, turns: List[TurnSnapshot], metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect if workflow execution would cause webhook caller timeout."""
        duration_ms = self._get_workflow_duration(turns, metadata)
        if duration_ms is None:
            return None

        # Check if workflow was triggered via webhook
        is_webhook = metadata and metadata.get("workflow_mode") == "webhook"
        if not is_webhook:
            return None

        if duration_ms > self.max_webhook_wait_ms:
            return {
                "detected": True,
                "type": "webhook_timeout",
                "duration_ms": duration_ms,
                "threshold_ms": self.max_webhook_wait_ms,
                "explanation": f"Webhook call took {duration_ms / 1000:.1f}s - caller likely timed out (threshold: {self.max_webhook_wait_ms / 1000:.1f}s)",
                "turns": list(range(len(turns))),
            }

        return None

    def _detect_node_timeout(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect individual nodes that exceeded their expected duration."""
        timeout_nodes = []

        for turn in turns:
            node_type = turn.turn_metadata.get("node_type", "default")
            execution_time_ms = turn.turn_metadata.get("execution_time_ms")

            if execution_time_ms is None:
                continue

            # Get threshold for this node type
            threshold = self.node_timeout_thresholds.get(
                node_type, self.node_timeout_thresholds["default"]
            )

            if execution_time_ms > threshold:
                timeout_nodes.append(
                    {
                        "turn": turn.turn_number,
                        "node": turn.participant_id,
                        "node_type": node_type,
                        "duration_ms": execution_time_ms,
                        "threshold_ms": threshold,
                    }
                )

        if timeout_nodes:
            return {
                "detected": True,
                "type": "node_timeout",
                "nodes": timeout_nodes,
                "explanation": f"{len(timeout_nodes)} node(s) exceeded execution time threshold",
                "turns": [n["turn"] for n in timeout_nodes],
            }

        return None

    def _detect_stalled_execution(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect if workflow stalled (no progress for extended period)."""
        if len(turns) < 2:
            return None

        # Look for large gaps between consecutive turns
        stalled_gaps = []

        for i in range(1, len(turns)):
            prev_turn = turns[i - 1]
            curr_turn = turns[i]

            prev_time = prev_turn.turn_metadata.get("timestamp")
            curr_time = curr_turn.turn_metadata.get("timestamp")

            if not prev_time or not curr_time:
                continue

            try:
                from datetime import datetime

                if isinstance(prev_time, str):
                    prev_time = datetime.fromisoformat(prev_time.replace("Z", "+00:00"))
                if isinstance(curr_time, str):
                    curr_time = datetime.fromisoformat(curr_time.replace("Z", "+00:00"))

                gap_ms = (curr_time - prev_time).total_seconds() * 1000

                if gap_ms > self.stall_threshold_ms:
                    stalled_gaps.append(
                        {
                            "after_turn": i - 1,
                            "before_turn": i,
                            "gap_ms": gap_ms,
                            "prev_node": prev_turn.participant_id,
                            "next_node": curr_turn.participant_id,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to calculate gap between turns: {e}")
                continue

        if stalled_gaps:
            return {
                "detected": True,
                "type": "stalled_execution",
                "gaps": stalled_gaps,
                "explanation": f"Found {len(stalled_gaps)} stall(s) with >60s no progress",
                "turns": [g["after_turn"] for g in stalled_gaps],
            }

        return None

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect timeout failures in n8n workflow."""
        if len(turns) < 1:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 1 node to detect timeouts",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Detect overall workflow timeout
        workflow_timeout = self._detect_workflow_timeout(turns, conversation_metadata)
        if workflow_timeout:
            issues.append(workflow_timeout)
            affected_turns.extend(workflow_timeout.get("turns", []))

        # 2. Detect webhook timeout
        webhook_timeout = self._detect_webhook_timeout(turns, conversation_metadata)
        if webhook_timeout:
            issues.append(webhook_timeout)
            affected_turns.extend(webhook_timeout.get("turns", []))

        # 3. Detect individual node timeouts
        node_timeout = self._detect_node_timeout(turns)
        if node_timeout:
            issues.append(node_timeout)
            affected_turns.extend(node_timeout.get("turns", []))

        # 4. Detect stalled execution
        stalled = self._detect_stalled_execution(turns)
        if stalled:
            issues.append(stalled)
            affected_turns.extend(stalled.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No timeout issues detected",
                detector_name=self.name,
            )

        # Determine severity based on issue types
        severity = TurnAwareSeverity.MINOR
        if workflow_timeout or webhook_timeout:
            severity = TurnAwareSeverity.SEVERE
        elif node_timeout:
            severity = TurnAwareSeverity.MODERATE

        # Calculate confidence
        confidence = 0.95 if workflow_timeout or webhook_timeout else 0.85

        # Build explanation
        explanations = [issue["explanation"] for issue in issues]
        full_explanation = "; ".join(explanations)

        # Suggest fixes
        fixes = []
        if workflow_timeout:
            fixes.append("Split workflow into smaller sub-workflows")
        if webhook_timeout:
            fixes.append(
                "Use async pattern: respond immediately, send callback when done"
            )
        if node_timeout:
            fixes.append("Optimize slow nodes or increase timeout thresholds")
        if stalled:
            fixes.append("Add timeout settings to merge/wait nodes")

        suggested_fix = "; ".join(fixes) if fixes else None

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F13",
            explanation=full_explanation,
            affected_turns=sorted(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=suggested_fix,
            detector_name=self.name,
            detector_version=self.version,
        )
