"""
LangGraph Edge Misroute Detector
==================================

Detects routing issues in LangGraph conditional edges:
- Target node referenced by edge does not exist in nodes list
- Dead-end routes: non-terminal nodes with no outgoing edges
- Unreachable nodes: nodes not targeted by any edge and not the entry point
- Condition name mismatches: condition text suggesting wrong routing
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

# Node types that are expected to be terminal (no outgoing edges needed)
TERMINAL_NODE_TYPES = {"human", "end", "__end__"}

# Condition name patterns that suggest routing to an end/terminal
END_CONDITION_PATTERNS = {"end", "finish", "stop", "terminate", "complete", "done"}

# Condition name patterns that suggest routing to processing/continuation
PROCESS_CONDITION_PATTERNS = {"process", "continue", "next", "run", "execute", "start"}


class LangGraphEdgeMisrouteDetector(TurnAwareDetector):
    """Detects edge misrouting in LangGraph graph executions.

    Analyzes edges and nodes for:
    1. Missing target nodes (edge points to non-existent node)
    2. Dead-end routes (non-terminal nodes without outgoing edges)
    3. Unreachable nodes (no incoming edges, not the first node)
    4. Condition name mismatches (condition text contradicts target)
    """

    name = "LangGraphEdgeMisrouteDetector"
    version = "1.0"
    supported_failure_modes = ["F12"]

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
        """Analyze edges and nodes for routing issues."""
        nodes = graph_execution.get("nodes", [])
        edges = graph_execution.get("edges", [])

        if not nodes:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No nodes in graph execution",
                detector_name=self.name,
            )

        # Build lookup structures
        node_ids: Set[str] = {n.get("node_id", "") for n in nodes}
        node_types: Dict[str, str] = {
            n.get("node_id", ""): n.get("node_type", "") for n in nodes
        }
        node_titles: Dict[str, str] = {
            n.get("node_id", ""): n.get("title", "") for n in nodes
        }

        # Track which nodes have outgoing/incoming edges
        nodes_with_outgoing: Set[str] = set()
        nodes_with_incoming: Set[str] = set()

        issues: List[Dict[str, Any]] = []

        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            edge_type = edge.get("edge_type", "")
            condition = edge.get("condition", "")

            nodes_with_outgoing.add(source)
            nodes_with_incoming.add(target)

            # 1. Missing target node
            if target and target not in node_ids:
                issues.append({
                    "type": "missing_target",
                    "source": source,
                    "target": target,
                    "edge_type": edge_type,
                    "description": (
                        f"Edge from '{source}' targets non-existent node '{target}'"
                    ),
                })

            # 4. Condition name mismatch (only for conditional edges)
            if edge_type == "conditional" and condition and target in node_ids:
                mismatch = self._check_condition_mismatch(
                    condition, target, node_types.get(target, ""),
                    node_titles.get(target, ""),
                )
                if mismatch:
                    issues.append(mismatch)

        # 2. Dead-end routes: non-terminal nodes without outgoing edges
        for node in nodes:
            nid = node.get("node_id", "")
            ntype = node.get("node_type", "")
            title = node.get("title", "").lower()

            is_terminal = (
                ntype in TERMINAL_NODE_TYPES
                or title in TERMINAL_NODE_TYPES
                or nid in TERMINAL_NODE_TYPES
            )

            if nid not in nodes_with_outgoing and not is_terminal:
                # Check if this is the last node by superstep (might be expected)
                status = graph_execution.get("status", "")
                if status == "completed":
                    # In a completed graph, the last executing node might
                    # legitimately have no outgoing edge if it is the final step.
                    # Only flag if there are other nodes after it.
                    node_superstep = node.get("superstep", -1)
                    max_superstep = max(
                        (n.get("superstep", 0) for n in nodes), default=0
                    )
                    if node_superstep >= max_superstep:
                        continue

                issues.append({
                    "type": "dead_end",
                    "node_id": nid,
                    "node_type": ntype,
                    "title": node.get("title", ""),
                    "description": (
                        f"Node '{nid}' ({ntype}) has no outgoing edges "
                        f"but is not a terminal node"
                    ),
                })

        # 3. Unreachable nodes: no incoming edges and not the entry point
        if nodes:
            # The first node (lowest superstep) is the entry point
            entry_node = min(nodes, key=lambda n: n.get("superstep", 0))
            entry_id = entry_node.get("node_id", "")

            for node in nodes:
                nid = node.get("node_id", "")
                if nid != entry_id and nid not in nodes_with_incoming:
                    issues.append({
                        "type": "unreachable",
                        "node_id": nid,
                        "node_type": node.get("node_type", ""),
                        "title": node.get("title", ""),
                        "description": (
                            f"Node '{nid}' has no incoming edges and "
                            f"is not the entry point"
                        ),
                    })

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No edge routing issues detected",
                detector_name=self.name,
            )

        # Confidence based on issue count and severity
        issue_types = {i["type"] for i in issues}
        if "missing_target" in issue_types:
            confidence = min(0.95, 0.8 + len(issues) * 0.05)
        else:
            confidence = min(0.90, 0.6 + len(issues) * 0.1)

        # Severity
        if "missing_target" in issue_types:
            severity = TurnAwareSeverity.SEVERE
        elif "dead_end" in issue_types:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        type_counts = {}
        for i in issues:
            type_counts[i["type"]] = type_counts.get(i["type"], 0) + 1
        summary_parts = [f"{count} {itype}" for itype, count in type_counts.items()]

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F12",
            explanation=f"Edge routing issues: {', '.join(summary_parts)}",
            affected_turns=[],
            evidence={
                "issues": issues,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
            suggested_fix=(
                "Verify all conditional edge targets exist in the graph. "
                "Ensure non-terminal nodes have outgoing edges. "
                "Check that condition functions route to the intended nodes."
            ),
            detector_name=self.name,
        )

    def _check_condition_mismatch(
        self,
        condition: str,
        target_id: str,
        target_type: str,
        target_title: str,
    ) -> Optional[Dict[str, Any]]:
        """Check if a condition name contradicts the target node.

        For example, a condition named "route_to_end" routing to a processing
        node suggests a misroute.
        """
        condition_lower = condition.lower().replace("_", " ")
        target_lower = (target_title or target_id).lower()

        # Check if condition suggests end but target is a processing node
        condition_suggests_end = any(
            p in condition_lower for p in END_CONDITION_PATTERNS
        )
        target_is_processing = target_type in ("llm", "tool", "subgraph", "map_reduce")

        if condition_suggests_end and target_is_processing:
            return {
                "type": "condition_mismatch",
                "condition": condition,
                "target_id": target_id,
                "target_type": target_type,
                "description": (
                    f"Condition '{condition}' suggests termination but "
                    f"routes to processing node '{target_id}' ({target_type})"
                ),
            }

        # Check if condition suggests processing but target is terminal
        condition_suggests_process = any(
            p in condition_lower for p in PROCESS_CONDITION_PATTERNS
        )
        target_is_terminal = (
            target_type in TERMINAL_NODE_TYPES
            or any(p in target_lower for p in END_CONDITION_PATTERNS)
        )

        if condition_suggests_process and target_is_terminal:
            return {
                "type": "condition_mismatch",
                "condition": condition,
                "target_id": target_id,
                "target_type": target_type,
                "description": (
                    f"Condition '{condition}' suggests continuation but "
                    f"routes to terminal node '{target_id}'"
                ),
            }

        return None
