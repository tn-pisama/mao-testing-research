"""
LangGraph Parallel Sync Detector
==================================

Detects synchronization issues in parallel node execution:
- State write conflicts: multiple nodes in the same superstep writing
  to the same state key
- Missing join/aggregation: no single node in the next superstep to
  merge parallel results
- Race conditions: parallel nodes reading and writing the same key
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


class LangGraphParallelSyncDetector(TurnAwareDetector):
    """Detects parallel execution synchronization issues in LangGraph.

    Analyzes nodes executing in the same superstep for:
    1. Write conflicts (multiple nodes writing to the same state key)
    2. Missing join node after parallel branches
    3. Race conditions (parallel read-then-write on same key)
    """

    name = "LangGraphParallelSyncDetector"
    version = "1.0"
    supported_failure_modes = ["F11"]

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
        """Analyze parallel node execution for sync issues."""
        nodes = graph_execution.get("nodes", [])

        if not nodes:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No nodes in graph execution",
                detector_name=self.name,
            )

        # Group nodes by superstep
        superstep_nodes: Dict[int, List[Dict[str, Any]]] = {}
        for node in nodes:
            step = node.get("superstep", -1)
            if step not in superstep_nodes:
                superstep_nodes[step] = []
            superstep_nodes[step].append(node)

        # Find supersteps with parallel execution (>1 node)
        parallel_steps = {
            step: step_nodes
            for step, step_nodes in superstep_nodes.items()
            if len(step_nodes) > 1
        }

        if not parallel_steps:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No parallel execution detected (all supersteps have single nodes)",
                detector_name=self.name,
            )

        issues: List[Dict[str, Any]] = []
        affected_supersteps: List[int] = []

        for step, step_nodes in sorted(parallel_steps.items()):
            # 1. Check for write conflicts
            write_conflicts = self._detect_write_conflicts(step, step_nodes)
            if write_conflicts:
                issues.append(write_conflicts)
                affected_supersteps.append(step)

            # 2. Check for race conditions
            race_conditions = self._detect_race_conditions(step, step_nodes)
            if race_conditions:
                issues.append(race_conditions)
                affected_supersteps.append(step)

            # 3. Check for missing join node
            missing_join = self._detect_missing_join(
                step, step_nodes, superstep_nodes
            )
            if missing_join:
                issues.append(missing_join)
                affected_supersteps.append(step)

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation=(
                    f"Parallel execution in {len(parallel_steps)} supersteps, "
                    f"no sync issues detected"
                ),
                detector_name=self.name,
            )

        # Determine confidence and severity
        issue_types = {i["type"] for i in issues}
        if "write_conflict" in issue_types:
            confidence = 0.7
            severity = TurnAwareSeverity.SEVERE
        elif "race_condition" in issue_types:
            confidence = 0.65
            severity = TurnAwareSeverity.MODERATE
        else:
            confidence = 0.6
            severity = TurnAwareSeverity.MINOR

        type_counts = {}
        for i in issues:
            type_counts[i["type"]] = type_counts.get(i["type"], 0) + 1
        summary = [f"{c} {t}" for t, c in type_counts.items()]

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F11",
            explanation=(
                f"Parallel sync issues: {', '.join(summary)} "
                f"across {len(parallel_steps)} parallel supersteps"
            ),
            affected_turns=sorted(set(affected_supersteps)),
            evidence={
                "issues": issues,
                "parallel_supersteps": len(parallel_steps),
                "total_supersteps": len(superstep_nodes),
            },
            suggested_fix=(
                "Use state reducers (e.g., operator.add for lists) to handle "
                "concurrent writes. Add an explicit join/aggregation node after "
                "parallel branches. Avoid having parallel nodes write to the "
                "same state key without a reducer."
            ),
            detector_name=self.name,
        )

    def _get_output_keys(self, node: Dict[str, Any]) -> Set[str]:
        """Extract state keys written by a node from its outputs."""
        outputs = node.get("outputs", {})
        if isinstance(outputs, dict):
            return set(outputs.keys())
        return set()

    def _get_input_keys(self, node: Dict[str, Any]) -> Set[str]:
        """Extract state keys read by a node from its inputs."""
        inputs = node.get("inputs", {})
        if isinstance(inputs, dict):
            return set(inputs.keys())
        return set()

    def _detect_write_conflicts(
        self, superstep: int, step_nodes: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect multiple parallel nodes writing to the same state key."""
        key_writers: Dict[str, List[str]] = {}

        for node in step_nodes:
            node_id = node.get("node_id", "")
            for key in self._get_output_keys(node):
                if key not in key_writers:
                    key_writers[key] = []
                key_writers[key].append(node_id)

        # Find keys with multiple writers
        conflicts = {
            key: writers
            for key, writers in key_writers.items()
            if len(writers) > 1
        }

        if not conflicts:
            return None

        return {
            "type": "write_conflict",
            "superstep": superstep,
            "conflicts": {k: v for k, v in conflicts.items()},
            "description": (
                f"Superstep {superstep}: {len(conflicts)} state key(s) written by "
                f"multiple parallel nodes: "
                + ", ".join(
                    f"'{k}' by [{', '.join(w)}]" for k, w in conflicts.items()
                )
            ),
        }

    def _detect_race_conditions(
        self, superstep: int, step_nodes: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect parallel nodes that read and write the same key."""
        races: List[Dict[str, Any]] = []

        for i, node_a in enumerate(step_nodes):
            a_id = node_a.get("node_id", "")
            a_reads = self._get_input_keys(node_a)
            a_writes = self._get_output_keys(node_a)

            for node_b in step_nodes[i + 1:]:
                b_id = node_b.get("node_id", "")
                b_reads = self._get_input_keys(node_b)
                b_writes = self._get_output_keys(node_b)

                # Race: A reads key that B writes, or B reads key that A writes
                a_read_b_write = a_reads & b_writes
                b_read_a_write = b_reads & a_writes

                conflicting_keys = a_read_b_write | b_read_a_write
                if conflicting_keys:
                    races.append({
                        "nodes": [a_id, b_id],
                        "keys": list(conflicting_keys),
                    })

        if not races:
            return None

        return {
            "type": "race_condition",
            "superstep": superstep,
            "races": races,
            "description": (
                f"Superstep {superstep}: {len(races)} potential race condition(s) "
                f"between parallel nodes reading/writing same keys"
            ),
        }

    def _detect_missing_join(
        self,
        superstep: int,
        step_nodes: List[Dict[str, Any]],
        all_superstep_nodes: Dict[int, List[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        """Detect missing join/aggregation node after parallel branches."""
        next_step_nodes = all_superstep_nodes.get(superstep + 1, [])

        # If there are no nodes in the next superstep, that is suspicious
        # (parallel branches with no merge)
        if not next_step_nodes:
            return {
                "type": "missing_join",
                "superstep": superstep,
                "parallel_count": len(step_nodes),
                "description": (
                    f"Superstep {superstep} has {len(step_nodes)} parallel nodes "
                    f"but no nodes in superstep {superstep + 1} to join results"
                ),
            }

        # If the next superstep also has multiple nodes (not a single join),
        # that might indicate missing aggregation
        if len(next_step_nodes) > 1 and len(next_step_nodes) >= len(step_nodes):
            return {
                "type": "missing_join",
                "superstep": superstep,
                "parallel_count": len(step_nodes),
                "next_count": len(next_step_nodes),
                "description": (
                    f"Superstep {superstep} has {len(step_nodes)} parallel nodes "
                    f"followed by {len(next_step_nodes)} nodes in superstep "
                    f"{superstep + 1} (expected a single join node)"
                ),
            }

        return None
