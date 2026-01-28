"""
F14: Error Handling Detection for n8n
=====================================

Detects hidden errors in n8n workflows where nodes fail but workflow continues:
- Node has error but continueOnFail=true hides it
- Downstream nodes receive null/invalid data from failed nodes
- Workflow marked "success" but contains node failures
- Error rate exceeds acceptable threshold

This is n8n-specific because it analyzes workflow error propagation patterns
unique to the n8n node execution model.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from app.detection.turn_aware._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)

logger = logging.getLogger(__name__)

# Indicators of null/invalid data
NULL_DATA_INDICATORS: Set[str] = {
    "null",
    "undefined",
    "none",
    "error:",
    "failed:",
    "invalid",
    "missing",
    "not found",
    "cannot read property",
    "typeerror",
}

# Maximum acceptable error rate (% of nodes that can fail)
DEFAULT_MAX_ERROR_RATE = 0.10  # 10% of nodes


class N8NErrorDetector(TurnAwareDetector):
    """Detects F14: Error Handling failures in n8n workflows.

    Analyzes workflow execution for:
    1. Nodes with errors that continued execution (continueOnFail=true)
    2. Data flow issues from failed nodes to downstream nodes
    3. Workflow success despite node failures
    4. High error rates indicating systemic issues

    n8n-specific manifestation of F14 (Error Handling):
    In conversational agents, this is about graceful error handling.
    In n8n workflows, this is about hidden failures and data propagation.
    """

    name = "N8NErrorDetector"
    version = "1.0"
    supported_failure_modes = ["F14"]

    def __init__(
        self,
        max_error_rate: float = DEFAULT_MAX_ERROR_RATE,
        check_downstream_data: bool = True,
    ):
        """Initialize error detector.

        Args:
            max_error_rate: Maximum acceptable error rate (0.0-1.0)
            check_downstream_data: Whether to check downstream nodes for invalid data
        """
        self.max_error_rate = max_error_rate
        self.check_downstream_data = check_downstream_data

    def _has_error(self, turn: TurnSnapshot) -> bool:
        """Check if a turn represents a node with an error."""
        # Check turn metadata for error flag
        if turn.turn_metadata.get("has_error"):
            return True

        # Check if error mentioned in content
        content_lower = turn.content.lower()
        return any(
            indicator in content_lower
            for indicator in ["error:", "failed:", "exception:"]
        )

    def _is_workflow_successful(
        self, metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if workflow was marked as successful."""
        if not metadata:
            return True  # Assume success if no metadata

        status = metadata.get("workflow_status", "success").lower()
        return status in ["success", "completed", "finished"]

    def _continued_on_fail(self, turn: TurnSnapshot) -> bool:
        """Check if node had continueOnFail enabled."""
        return turn.turn_metadata.get("continue_on_fail", False)

    def _has_invalid_data(self, turn: TurnSnapshot) -> bool:
        """Check if turn contains indicators of null/invalid data."""
        content_lower = turn.content.lower()
        return any(indicator in content_lower for indicator in NULL_DATA_INDICATORS)

    def _detect_hidden_failures(
        self, turns: List[TurnSnapshot], metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect nodes with errors that continued execution."""
        hidden_failures = []

        for turn in turns:
            if self._has_error(turn) and self._continued_on_fail(turn):
                hidden_failures.append(
                    {
                        "turn": turn.turn_number,
                        "node": turn.participant_id,
                        "node_type": turn.turn_metadata.get("node_type", "unknown"),
                    }
                )

        if hidden_failures:
            # Check if workflow was still marked successful
            workflow_successful = self._is_workflow_successful(metadata)

            return {
                "detected": True,
                "type": "hidden_failure",
                "failures": hidden_failures,
                "workflow_status": (
                    "success" if workflow_successful else "failed"
                ),
                "explanation": f"{len(hidden_failures)} node(s) failed but continued execution (continueOnFail=true)",
                "turns": [f["turn"] for f in hidden_failures],
            }

        return None

    def _detect_invalid_data_propagation(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect downstream nodes receiving invalid data from failed nodes."""
        if not self.check_downstream_data:
            return None

        invalid_data_issues = []

        # Build a map of node execution order
        for i, turn in enumerate(turns):
            if self._has_error(turn):
                # Check subsequent turns for invalid data
                for j in range(i + 1, min(i + 5, len(turns))):  # Check next 4 nodes
                    downstream_turn = turns[j]
                    if self._has_invalid_data(downstream_turn):
                        invalid_data_issues.append(
                            {
                                "failed_node_turn": i,
                                "failed_node": turn.participant_id,
                                "affected_node_turn": j,
                                "affected_node": downstream_turn.participant_id,
                            }
                        )

        if invalid_data_issues:
            return {
                "detected": True,
                "type": "invalid_data_propagation",
                "issues": invalid_data_issues,
                "explanation": f"{len(invalid_data_issues)} downstream node(s) received invalid data from failed nodes",
                "turns": [
                    issue["affected_node_turn"] for issue in invalid_data_issues
                ],
            }

        return None

    def _detect_high_error_rate(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect if error rate exceeds acceptable threshold."""
        if not turns:
            return None

        error_count = sum(1 for turn in turns if self._has_error(turn))
        error_rate = error_count / len(turns)

        if error_rate > self.max_error_rate:
            return {
                "detected": True,
                "type": "high_error_rate",
                "error_count": error_count,
                "total_nodes": len(turns),
                "error_rate": error_rate,
                "threshold": self.max_error_rate,
                "explanation": f"Error rate {error_rate:.1%} exceeds threshold {self.max_error_rate:.1%} ({error_count}/{len(turns)} nodes failed)",
                "turns": [
                    i for i, turn in enumerate(turns) if self._has_error(turn)
                ],
            }

        return None

    def _detect_success_despite_failures(
        self, turns: List[TurnSnapshot], metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect workflow marked successful despite node failures."""
        if not self._is_workflow_successful(metadata):
            return None  # Workflow already marked as failed

        failed_nodes = [
            (i, turn) for i, turn in enumerate(turns) if self._has_error(turn)
        ]

        if failed_nodes:
            return {
                "detected": True,
                "type": "success_despite_failures",
                "failed_nodes": [
                    {
                        "turn": i,
                        "node": turn.participant_id,
                        "node_type": turn.turn_metadata.get("node_type", "unknown"),
                    }
                    for i, turn in failed_nodes
                ],
                "explanation": f"Workflow marked as successful but {len(failed_nodes)} node(s) failed",
                "turns": [i for i, _ in failed_nodes],
            }

        return None

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect error handling failures in n8n workflow."""
        if len(turns) < 1:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 1 node to detect error handling issues",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Detect hidden failures (continueOnFail=true)
        hidden = self._detect_hidden_failures(turns, conversation_metadata)
        if hidden:
            issues.append(hidden)
            affected_turns.extend(hidden.get("turns", []))

        # 2. Detect invalid data propagation
        invalid_data = self._detect_invalid_data_propagation(turns)
        if invalid_data:
            issues.append(invalid_data)
            affected_turns.extend(invalid_data.get("turns", []))

        # 3. Detect high error rate
        high_error_rate = self._detect_high_error_rate(turns)
        if high_error_rate:
            issues.append(high_error_rate)
            affected_turns.extend(high_error_rate.get("turns", []))

        # 4. Detect success despite failures
        success_despite_failures = self._detect_success_despite_failures(
            turns, conversation_metadata
        )
        if success_despite_failures:
            issues.append(success_despite_failures)
            affected_turns.extend(success_despite_failures.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No error handling issues detected",
                detector_name=self.name,
            )

        # Determine severity
        severity = TurnAwareSeverity.MODERATE
        if hidden or success_despite_failures:
            severity = TurnAwareSeverity.SEVERE
        elif high_error_rate:
            severity = TurnAwareSeverity.MODERATE

        # Calculate confidence
        confidence = 0.90 if hidden or success_despite_failures else 0.80

        # Build explanation
        explanations = [issue["explanation"] for issue in issues]
        full_explanation = "; ".join(explanations)

        # Suggest fixes
        fixes = []
        if hidden:
            fixes.append("Set continueOnFail=false to stop workflow on errors")
        if invalid_data:
            fixes.append(
                "Add data validation nodes after potentially failing operations"
            )
        if high_error_rate:
            fixes.append(
                "Review workflow logic - high error rate indicates systemic issues"
            )
        if success_despite_failures:
            fixes.append("Add error handler nodes to properly handle failures")

        suggested_fix = "; ".join(fixes) if fixes else None

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F14",
            explanation=full_explanation,
            affected_turns=sorted(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=suggested_fix,
            detector_name=self.name,
            detector_version=self.version,
        )
