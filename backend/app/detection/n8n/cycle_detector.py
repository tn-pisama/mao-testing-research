"""
F11: Graph Cycle Detection for n8n Workflows
=============================================

Detects circular execution patterns in n8n workflows:
- Same node executing multiple times in sequence
- Circular delegation patterns (A->B->C->A)
- Retry storms that indicate stuck workflows
- Ping-pong patterns between nodes

This is n8n-specific because workflow execution order is deterministic
based on the graph structure, unlike conversational agent turn-taking.
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.detection.turn_aware._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)

logger = logging.getLogger(__name__)


class N8NCycleDetector(TurnAwareDetector):
    """Detects F11: Coordination Failure / Workflow Cycles in n8n workflows.

    Analyzes workflow execution for:
    1. Repeated node sequences indicating loops
    2. Circular delegation patterns
    3. Retry/error cycles
    4. Parallel branch conflicts

    n8n-specific manifestation of F11 (Coordination Failure):
    In conversational agents, this is about delegation loops between agents.
    In n8n workflows, this is about graph cycles and execution loops.
    """

    name = "N8NCycleDetector"
    version = "1.0"
    supported_failure_modes = ["F11"]

    def __init__(
        self,
        min_cycle_repetitions: int = 2,
        max_healthy_retries: int = 3,
    ):
        """Initialize cycle detector.

        Args:
            min_cycle_repetitions: Minimum times a pattern must repeat to be a cycle
            max_healthy_retries: Maximum retries before flagging as problematic
        """
        self.min_cycle_repetitions = min_cycle_repetitions
        self.max_healthy_retries = max_healthy_retries

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect graph cycles and coordination failures in n8n workflow."""
        if len(turns) < 4:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 4 nodes to detect cycles",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Detect exact node sequence repetition
        sequence_cycle = self._detect_sequence_cycle(turns)
        if sequence_cycle["detected"]:
            issues.append(sequence_cycle)
            affected_turns.extend(sequence_cycle.get("turns", []))

        # 2. Detect circular delegation (A->B->C->A)
        circular = self._detect_circular_delegation(turns)
        if circular["detected"]:
            issues.append(circular)
            affected_turns.extend(circular.get("turns", []))

        # 3. Detect ping-pong pattern (A->B->A->B)
        pingpong = self._detect_pingpong(turns)
        if pingpong["detected"]:
            issues.append(pingpong)
            affected_turns.extend(pingpong.get("turns", []))

        # 4. Detect retry storms
        retry = self._detect_retry_storm(turns)
        if retry["detected"]:
            issues.append(retry)
            affected_turns.extend(retry.get("turns", []))

        # 5. Detect node over-execution
        over_exec = self._detect_node_overexecution(turns)
        if over_exec["detected"]:
            issues.append(over_exec)
            affected_turns.extend(over_exec.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No cycle patterns detected in workflow execution",
                detector_name=self.name,
            )

        # Determine severity based on cycle characteristics
        has_infinite = any(i.get("potentially_infinite", False) for i in issues)
        cycle_lengths = [i.get("cycle_length", 0) for i in issues]
        max_repetitions = max((i.get("repetitions", 0) for i in issues), default=0)

        if has_infinite or max_repetitions >= 5:
            severity = TurnAwareSeverity.SEVERE
        elif max_repetitions >= 3 or any(l >= 4 for l in cycle_lengths):
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.95, 0.6 + len(issues) * 0.15)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F11",
            explanation=f"Workflow cycle detected: {len(issues)} patterns found",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "total_nodes": len(turns),
                "unique_nodes": len(set(t.participant_id for t in turns)),
            },
            suggested_fix=(
                "Add cycle-breaking conditions to prevent infinite loops. "
                "Use n8n's IF node to check exit conditions. "
                "Add maximum iteration limits or use the Loop Over Items node with bounds."
            ),
            detector_name=self.name,
        )

    def _detect_sequence_cycle(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect exact sequence repetition in node execution.

        Example: [A, B, C, A, B, C, A, B, C] -> cycle of [A, B, C]
        """
        node_sequence = [t.participant_id for t in turns]
        n = len(node_sequence)

        # Check for cycle lengths from 2 to n/2
        for cycle_len in range(2, n // 2 + 1):
            # Count how many times this potential cycle repeats
            repetitions = 0
            start_pattern = node_sequence[:cycle_len]

            for i in range(0, n - cycle_len + 1, cycle_len):
                if node_sequence[i:i + cycle_len] == start_pattern:
                    repetitions += 1
                else:
                    break

            if repetitions >= self.min_cycle_repetitions:
                # Found a repeating pattern
                return {
                    "detected": True,
                    "type": "sequence_cycle",
                    "cycle_length": cycle_len,
                    "repetitions": repetitions,
                    "pattern": start_pattern,
                    "turns": [turns[i].turn_number for i in range(repetitions * cycle_len)],
                    "potentially_infinite": repetitions >= 4,
                    "description": f"Sequence cycle: {start_pattern} repeated {repetitions} times",
                }

        return {"detected": False}

    def _detect_circular_delegation(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect circular delegation patterns (A->B->C->A).

        This is different from sequence cycles - it looks for the same
        node appearing at regular intervals, suggesting circular handoff.
        """
        node_sequence = [t.participant_id for t in turns]

        # Find nodes that appear multiple times
        node_positions: Dict[str, List[int]] = {}
        for i, node in enumerate(node_sequence):
            if node not in node_positions:
                node_positions[node] = []
            node_positions[node].append(i)

        # Check if any node appears in a regular pattern
        for node, positions in node_positions.items():
            if len(positions) >= 3:
                # Check for regular interval
                intervals = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]

                # If intervals are consistent, this suggests a cycle
                if len(set(intervals)) == 1 and intervals[0] >= 2:
                    cycle_length = intervals[0]
                    # Verify the full pattern
                    pattern_nodes = node_sequence[positions[0]:positions[0] + cycle_length]

                    return {
                        "detected": True,
                        "type": "circular_delegation",
                        "cycle_length": cycle_length,
                        "repetitions": len(positions),
                        "anchor_node": node,
                        "pattern": pattern_nodes,
                        "turns": [turns[p].turn_number for p in positions],
                        "potentially_infinite": len(positions) >= 4,
                        "description": f"Circular delegation: {node} appears every {cycle_length} nodes",
                    }

        return {"detected": False}

    def _detect_pingpong(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect ping-pong pattern between two nodes (A->B->A->B).

        This is a special case of coordination failure where two nodes
        keep passing control back and forth without progress.
        """
        if len(turns) < 4:
            return {"detected": False}

        node_sequence = [t.participant_id for t in turns]

        # Look for A->B->A->B pattern
        for i in range(len(node_sequence) - 3):
            a, b = node_sequence[i], node_sequence[i + 1]
            if a != b:  # Must be different nodes
                # Count consecutive ping-pong
                count = 1
                j = i + 2
                while j + 1 < len(node_sequence):
                    if node_sequence[j] == a and node_sequence[j + 1] == b:
                        count += 1
                        j += 2
                    else:
                        break

                if count >= self.min_cycle_repetitions:
                    affected = [turns[k].turn_number for k in range(i, min(i + count * 2, len(turns)))]
                    return {
                        "detected": True,
                        "type": "pingpong",
                        "cycle_length": 2,
                        "repetitions": count,
                        "nodes": [a, b],
                        "turns": affected,
                        "potentially_infinite": count >= 4,
                        "description": f"Ping-pong pattern: {a} <-> {b} repeated {count} times",
                    }

        return {"detected": False}

    def _detect_retry_storm(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect retry storms where a node executes repeatedly on failure.

        Look for patterns like:
        - Same node executing multiple times in a row
        - Error indicators in content followed by retry
        """
        consecutive_counts: List[Tuple[str, int, int]] = []  # (node, count, start_idx)
        current_node = None
        current_count = 0
        current_start = 0

        for i, turn in enumerate(turns):
            if turn.participant_id == current_node:
                current_count += 1
            else:
                if current_count > 1:
                    consecutive_counts.append((current_node, current_count, current_start))
                current_node = turn.participant_id
                current_count = 1
                current_start = i

        # Don't forget the last sequence
        if current_count > 1:
            consecutive_counts.append((current_node, current_count, current_start))

        # Find problematic retries
        for node, count, start in consecutive_counts:
            if count > self.max_healthy_retries:
                # Check for error indicators
                has_errors = any(
                    any(err in turns[j].content.lower() for err in ['error', 'fail', 'retry', 'exception'])
                    for j in range(start, min(start + count, len(turns)))
                )

                affected = [turns[j].turn_number for j in range(start, min(start + count, len(turns)))]
                return {
                    "detected": True,
                    "type": "retry_storm",
                    "node": node,
                    "repetitions": count,
                    "has_error_indicators": has_errors,
                    "turns": affected,
                    "potentially_infinite": count >= 6,
                    "description": f"Retry storm: {node} executed {count} consecutive times",
                }

        return {"detected": False}

    def _detect_node_overexecution(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect nodes that execute far more times than expected.

        In a healthy workflow, most nodes execute once or a small number of times.
        Excessive execution suggests a loop or retry issue.
        """
        node_counts = Counter(t.participant_id for t in turns)
        total_nodes = len(turns)

        # Calculate threshold: if a node executes more than 40% of total executions
        # or more than 5 times when total is small
        threshold = max(5, int(total_nodes * 0.4))

        overexecuted = [(node, count) for node, count in node_counts.items() if count > threshold]

        if overexecuted:
            worst_node, worst_count = max(overexecuted, key=lambda x: x[1])
            node_turns = [t.turn_number for t in turns if t.participant_id == worst_node]

            return {
                "detected": True,
                "type": "node_overexecution",
                "node": worst_node,
                "repetitions": worst_count,
                "total_executions": total_nodes,
                "percentage": worst_count / total_nodes * 100,
                "turns": node_turns,
                "all_overexecuted": overexecuted,
                "potentially_infinite": worst_count >= total_nodes * 0.5,
                "description": f"Node overexecution: {worst_node} ran {worst_count}/{total_nodes} times ({worst_count/total_nodes*100:.0f}%)",
            }

        return {"detected": False}
