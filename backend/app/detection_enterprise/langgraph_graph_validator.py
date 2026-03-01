"""Validates generated LangGraph graph execution JSON structures.

Ensures that LangGraph graph execution data produced by the golden dataset
generator has valid node types, edge types, timestamps, and structural
integrity.

Used by:
1. Golden data generator -- validate LangGraph graph entries before saving
2. Calibration pipeline -- pre-check LangGraph-typed entries
3. Input schemas -- extended LangGraph-specific validation
"""

import logging
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_NODE_TYPES = {
    "llm",
    "tool",
    "router",
    "human",
    "subgraph",
    "passthrough",
    "map_reduce",
}

VALID_GRAPH_TYPES = {"StateGraph", "MessageGraph", "CompiledGraph"}

VALID_STATUS_VALUES = {"completed", "failed", "interrupted", "timeout", "recursion_limit"}

VALID_NODE_STATUS_VALUES = {"succeeded", "failed", "interrupted", "skipped"}

VALID_EDGE_TYPES = {"fixed", "conditional", "send"}

LANGGRAPH_DETECTION_TYPES = {
    "langgraph_recursion",
    "langgraph_state_corruption",
    "langgraph_edge_misroute",
    "langgraph_tool_failure",
    "langgraph_parallel_sync",
    "langgraph_checkpoint_corruption",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_iso_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string, raising ValueError on failure."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_langgraph_graph_execution(graph_execution: dict) -> Tuple[bool, str]:
    """Validate that *graph_execution* has a well-formed LangGraph structure.

    Checks performed:

    1. ``graph_id`` is present and a non-empty string.
    2. ``thread_id`` is present and a non-empty string.
    3. ``graph_type`` if present is one of :data:`VALID_GRAPH_TYPES`.
    4. ``status`` if present is one of :data:`VALID_STATUS_VALUES`.
    5. ``nodes`` is present and is a list.
    6. Each node has ``node_id``, ``node_type``, ``superstep``, ``status``.
    7. Node types are from :data:`VALID_NODE_TYPES`.
    8. Node status values are from :data:`VALID_NODE_STATUS_VALUES`.
    9. ``superstep`` is a non-negative integer.
    10. ``edges`` if present is a list of dicts with ``source``, ``target``,
        ``edge_type``.
    11. Edge types are from :data:`VALID_EDGE_TYPES`.
    12. ``checkpoints`` if present have ``checkpoint_id`` and ``superstep``.
    13. ``state_snapshots`` if present have ``superstep`` and ``state``.
    14. Timestamps are valid ISO 8601.
    15. ``token_count`` / ``total_tokens`` are non-negative.
    16. ``recursion_limit`` if present is a positive integer.

    Args:
        graph_execution: The LangGraph graph execution dict to validate.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")``
        otherwise.
    """
    if not isinstance(graph_execution, dict):
        return False, "graph_execution must be a dict"

    # ---- graph_id ----
    graph_id = graph_execution.get("graph_id")
    if graph_id is None:
        return False, "graph_execution missing required field 'graph_id'"
    if not isinstance(graph_id, str) or not graph_id.strip():
        return False, "'graph_id' must be a non-empty string"

    # ---- thread_id ----
    thread_id = graph_execution.get("thread_id")
    if thread_id is None:
        return False, "graph_execution missing required field 'thread_id'"
    if not isinstance(thread_id, str) or not thread_id.strip():
        return False, "'thread_id' must be a non-empty string"

    # ---- graph_type ----
    graph_type = graph_execution.get("graph_type")
    if graph_type is not None:
        if graph_type not in VALID_GRAPH_TYPES:
            return False, (
                f"'graph_type' value '{graph_type}' is not valid "
                f"(expected one of {sorted(VALID_GRAPH_TYPES)})"
            )

    # ---- status ----
    status = graph_execution.get("status")
    if status is not None:
        if status not in VALID_STATUS_VALUES:
            return False, (
                f"graph_execution 'status' value '{status}' is not valid "
                f"(expected one of {sorted(VALID_STATUS_VALUES)})"
            )

    # ---- nodes ----
    nodes = graph_execution.get("nodes")
    if nodes is None:
        return False, "graph_execution missing required field 'nodes'"
    if not isinstance(nodes, list):
        return False, "'nodes' must be a list"

    # ---- per-node validation ----
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            return False, f"nodes[{idx}] must be a dict"

        # node_id
        node_id = node.get("node_id")
        if node_id is None:
            return False, f"nodes[{idx}] missing required field 'node_id'"
        if not isinstance(node_id, str) or not node_id.strip():
            return False, f"nodes[{idx}].node_id must be a non-empty string"

        # node_type
        node_type = node.get("node_type")
        if node_type is None:
            return False, f"nodes[{idx}] missing required field 'node_type'"
        if node_type not in VALID_NODE_TYPES:
            return False, (
                f"nodes[{idx}].node_type '{node_type}' is not valid "
                f"(expected one of {sorted(VALID_NODE_TYPES)})"
            )

        # superstep
        superstep = node.get("superstep")
        if superstep is None:
            return False, f"nodes[{idx}] missing required field 'superstep'"
        if not isinstance(superstep, int) or isinstance(superstep, bool):
            return False, f"nodes[{idx}].superstep must be an integer"
        if superstep < 0:
            return False, f"nodes[{idx}].superstep must be non-negative"

        # status
        node_status = node.get("status")
        if node_status is None:
            return False, f"nodes[{idx}] missing required field 'status'"
        if node_status not in VALID_NODE_STATUS_VALUES:
            return False, (
                f"nodes[{idx}].status '{node_status}' is not valid "
                f"(expected one of {sorted(VALID_NODE_STATUS_VALUES)})"
            )

        # token_count (optional)
        token_count = node.get("token_count")
        if token_count is not None:
            if not isinstance(token_count, (int, float)):
                return False, f"nodes[{idx}].token_count must be a number"
            if token_count < 0:
                return False, f"nodes[{idx}].token_count must be non-negative"

        # started_at / finished_at timestamps (optional)
        for ts_field in ("started_at", "finished_at"):
            ts_str = node.get(ts_field)
            if ts_str is not None and isinstance(ts_str, str):
                try:
                    _parse_iso_timestamp(ts_str)
                except (ValueError, TypeError):
                    return False, (
                        f"nodes[{idx}].{ts_field} '{ts_str}' is not valid "
                        f"ISO 8601 format"
                    )

    # ---- edges (optional) ----
    edges = graph_execution.get("edges")
    if edges is not None:
        if not isinstance(edges, list):
            return False, "'edges' must be a list"

        for idx, edge in enumerate(edges):
            if not isinstance(edge, dict):
                return False, f"edges[{idx}] must be a dict"

            # source
            source = edge.get("source")
            if source is None:
                return False, f"edges[{idx}] missing required field 'source'"
            if not isinstance(source, str) or not source.strip():
                return False, f"edges[{idx}].source must be a non-empty string"

            # target
            target = edge.get("target")
            if target is None:
                return False, f"edges[{idx}] missing required field 'target'"
            if not isinstance(target, str) or not target.strip():
                return False, f"edges[{idx}].target must be a non-empty string"

            # edge_type
            edge_type = edge.get("edge_type")
            if edge_type is None:
                return False, f"edges[{idx}] missing required field 'edge_type'"
            if edge_type not in VALID_EDGE_TYPES:
                return False, (
                    f"edges[{idx}].edge_type '{edge_type}' is not valid "
                    f"(expected one of {sorted(VALID_EDGE_TYPES)})"
                )

    # ---- checkpoints (optional) ----
    checkpoints = graph_execution.get("checkpoints")
    if checkpoints is not None:
        if not isinstance(checkpoints, list):
            return False, "'checkpoints' must be a list"

        for idx, cp in enumerate(checkpoints):
            if not isinstance(cp, dict):
                return False, f"checkpoints[{idx}] must be a dict"

            # checkpoint_id
            cp_id = cp.get("checkpoint_id")
            if cp_id is None:
                return False, f"checkpoints[{idx}] missing required field 'checkpoint_id'"
            if not isinstance(cp_id, str) or not cp_id.strip():
                return False, f"checkpoints[{idx}].checkpoint_id must be a non-empty string"

            # superstep
            cp_superstep = cp.get("superstep")
            if cp_superstep is None:
                return False, f"checkpoints[{idx}] missing required field 'superstep'"
            if not isinstance(cp_superstep, int) or isinstance(cp_superstep, bool):
                return False, f"checkpoints[{idx}].superstep must be an integer"
            if cp_superstep < 0:
                return False, f"checkpoints[{idx}].superstep must be non-negative"

            # timestamp (optional)
            ts_str = cp.get("timestamp")
            if ts_str is not None and isinstance(ts_str, str):
                try:
                    _parse_iso_timestamp(ts_str)
                except (ValueError, TypeError):
                    return False, (
                        f"checkpoints[{idx}].timestamp '{ts_str}' is not valid "
                        f"ISO 8601 format"
                    )

    # ---- state_snapshots (optional) ----
    state_snapshots = graph_execution.get("state_snapshots")
    if state_snapshots is not None:
        if not isinstance(state_snapshots, list):
            return False, "'state_snapshots' must be a list"

        for idx, snap in enumerate(state_snapshots):
            if not isinstance(snap, dict):
                return False, f"state_snapshots[{idx}] must be a dict"

            # superstep
            snap_superstep = snap.get("superstep")
            if snap_superstep is None:
                return False, f"state_snapshots[{idx}] missing required field 'superstep'"
            if not isinstance(snap_superstep, int) or isinstance(snap_superstep, bool):
                return False, f"state_snapshots[{idx}].superstep must be an integer"
            if snap_superstep < 0:
                return False, f"state_snapshots[{idx}].superstep must be non-negative"

            # state
            state = snap.get("state")
            if state is None:
                return False, f"state_snapshots[{idx}] missing required field 'state'"

    # ---- graph-level optional fields ----
    total_tokens = graph_execution.get("total_tokens")
    if total_tokens is not None:
        if not isinstance(total_tokens, (int, float)):
            return False, "'total_tokens' must be a number"
        if total_tokens < 0:
            return False, "'total_tokens' must be non-negative"

    token_count = graph_execution.get("token_count")
    if token_count is not None:
        if not isinstance(token_count, (int, float)):
            return False, "'token_count' must be a number"
        if token_count < 0:
            return False, "'token_count' must be non-negative"

    recursion_limit = graph_execution.get("recursion_limit")
    if recursion_limit is not None:
        if not isinstance(recursion_limit, int) or isinstance(recursion_limit, bool):
            return False, "'recursion_limit' must be an integer"
        if recursion_limit <= 0:
            return False, "'recursion_limit' must be a positive integer"

    # ---- started_at / finished_at on graph execution ----
    for ts_field in ("started_at", "finished_at"):
        ts_str = graph_execution.get(ts_field)
        if ts_str is not None and isinstance(ts_str, str):
            try:
                _parse_iso_timestamp(ts_str)
            except (ValueError, TypeError):
                return False, (
                    f"graph_execution.{ts_field} '{ts_str}' is not valid "
                    f"ISO 8601 format"
                )

    return True, ""


def validate_langgraph_input_data(
    detection_type: str, input_data: dict
) -> Tuple[bool, str]:
    """Extended LangGraph-specific validation for golden dataset ``input_data``.

    Dispatches validation depending on the detection type:

    * **LangGraph detection types** (``langgraph_recursion``,
      ``langgraph_state_corruption``, ``langgraph_edge_misroute``,
      ``langgraph_tool_failure``, ``langgraph_parallel_sync``,
      ``langgraph_checkpoint_corruption``): expects
      ``input_data["graph_execution"]`` and validates it with
      :func:`validate_langgraph_graph_execution`.
      Additionally checks for type-specific required fields.
    * All other types pass without LangGraph-specific checks.

    Args:
        detection_type: The detection type string.
        input_data: The input_data dict from a golden dataset entry.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")``
        otherwise.
    """
    if not isinstance(input_data, dict):
        return False, "input_data must be a dict"

    # --- LangGraph-specific detection types ---
    if detection_type in LANGGRAPH_DETECTION_TYPES:
        graph_execution = input_data.get("graph_execution")
        if graph_execution is None:
            return False, (
                f"input_data for '{detection_type}' must contain 'graph_execution'"
            )
        if not isinstance(graph_execution, dict):
            return False, (
                f"input_data['graph_execution'] must be a dict for '{detection_type}'"
            )

        valid, err = validate_langgraph_graph_execution(graph_execution)
        if not valid:
            return False, err

        # Type-specific required fields within the graph_execution
        if detection_type == "langgraph_edge_misroute":
            if "edges" not in graph_execution:
                return False, (
                    "graph_execution must contain 'edges' key for "
                    "'langgraph_edge_misroute' detection type"
                )

        if detection_type == "langgraph_checkpoint_corruption":
            if "checkpoints" not in graph_execution:
                return False, (
                    "graph_execution must contain 'checkpoints' key for "
                    "'langgraph_checkpoint_corruption' detection type"
                )

        return True, ""

    # --- All other types: no LangGraph-specific validation needed ---
    return True, ""
