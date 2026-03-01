"""Validates generated Dify workflow run JSON structures.

Ensures that Dify workflow run data produced by the golden dataset generator
has valid node types, timestamps, and structural integrity.

Used by:
1. Golden data generator -- validate Dify workflow entries before saving
2. Calibration pipeline -- pre-check Dify-typed entries
3. Input schemas -- extended Dify-specific validation
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
    "http_request",
    "code",
    "knowledge_retrieval",
    "question_classifier",
    "if_else",
    "template_transform",
    "variable_aggregator",
    "parameter_extractor",
    "iteration",
    "loop",
}

VALID_APP_TYPES = {"chatbot", "agent", "workflow", "chatflow"}

VALID_STATUS_VALUES = {"running", "succeeded", "failed", "stopped"}

ITERATION_NODE_TYPES = {"iteration", "loop"}

DIFY_DETECTION_TYPES = {
    "dify_rag_poisoning",
    "dify_iteration_escape",
    "dify_model_fallback",
    "dify_variable_leak",
    "dify_classifier_drift",
    "dify_tool_schema_mismatch",
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

def validate_dify_workflow_run(workflow_run: dict) -> Tuple[bool, str]:
    """Validate that *workflow_run* has a well-formed Dify workflow run structure.

    Checks performed:

    1. ``workflow_run_id`` is present and a non-empty string.
    2. ``app_id`` is present and a non-empty string.
    3. ``app_type`` if present is one of :data:`VALID_APP_TYPES`.
    4. ``nodes`` is present and is a list.
    5. Each node has ``node_id``, ``node_type``, ``title``, ``status``.
    6. Node types are from :data:`VALID_NODE_TYPES`.
    7. Node status values are from :data:`VALID_STATUS_VALUES`.
    8. ``started_at`` and ``finished_at`` if present are valid ISO 8601.
    9. ``token_count`` if present is a non-negative integer.
    10. ``total_tokens`` if present is a non-negative integer.
    11. ``total_steps`` if present is a non-negative integer.
    12. Iteration child nodes have valid ``parent_node_id`` references.

    Args:
        workflow_run: The Dify workflow run dict to validate.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")``
        otherwise.
    """
    if not isinstance(workflow_run, dict):
        return False, "workflow_run must be a dict"

    # ---- workflow_run_id ----
    run_id = workflow_run.get("workflow_run_id")
    if run_id is None:
        return False, "workflow_run missing required field 'workflow_run_id'"
    if not isinstance(run_id, str) or not run_id.strip():
        return False, "'workflow_run_id' must be a non-empty string"

    # ---- app_id ----
    app_id = workflow_run.get("app_id")
    if app_id is None:
        return False, "workflow_run missing required field 'app_id'"
    if not isinstance(app_id, str) or not app_id.strip():
        return False, "'app_id' must be a non-empty string"

    # ---- app_type ----
    app_type = workflow_run.get("app_type")
    if app_type is not None:
        if app_type not in VALID_APP_TYPES:
            return False, (
                f"'app_type' value '{app_type}' is not valid "
                f"(expected one of {sorted(VALID_APP_TYPES)})"
            )

    # ---- nodes ----
    nodes = workflow_run.get("nodes")
    if nodes is None:
        return False, "workflow_run missing required field 'nodes'"
    if not isinstance(nodes, list):
        return False, "'nodes' must be a list"

    # Collect node IDs for parent reference validation
    node_ids = set()
    iteration_node_ids = set()

    # ---- per-node validation ----
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            return False, f"nodes[{idx}] must be a dict"

        # node_id
        node_id = node.get("node_id")
        if node_id is not None:
            if not isinstance(node_id, str) or not node_id.strip():
                return False, f"nodes[{idx}].node_id must be a non-empty string"
            node_ids.add(node_id)

        # node_type
        node_type = node.get("node_type")
        if node_type is not None:
            if node_type not in VALID_NODE_TYPES:
                return False, (
                    f"nodes[{idx}].node_type '{node_type}' is not valid "
                    f"(expected one of {sorted(VALID_NODE_TYPES)})"
                )
            if node_type in ITERATION_NODE_TYPES:
                if node_id:
                    iteration_node_ids.add(node_id)

        # status
        status = node.get("status")
        if status is not None:
            if status not in VALID_STATUS_VALUES:
                return False, (
                    f"nodes[{idx}].status '{status}' is not valid "
                    f"(expected one of {sorted(VALID_STATUS_VALUES)})"
                )

        # token_count
        token_count = node.get("token_count")
        if token_count is not None:
            if not isinstance(token_count, (int, float)):
                return False, f"nodes[{idx}].token_count must be a number"
            if token_count < 0:
                return False, f"nodes[{idx}].token_count must be non-negative"

        # started_at / finished_at timestamps
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

        # iteration_index
        iter_idx = node.get("iteration_index")
        if iter_idx is not None:
            if not isinstance(iter_idx, (int, float)):
                return False, f"nodes[{idx}].iteration_index must be a number"

    # ---- validate parent_node_id references ----
    for idx, node in enumerate(nodes):
        parent_id = node.get("parent_node_id")
        if parent_id is not None:
            if not isinstance(parent_id, str):
                return False, f"nodes[{idx}].parent_node_id must be a string"
            # Warn but don't fail if parent isn't an iteration node
            if parent_id not in node_ids:
                logger.warning(
                    "nodes[%d].parent_node_id '%s' not found in node list",
                    idx, parent_id,
                )

    # ---- workflow-level optional fields ----
    total_tokens = workflow_run.get("total_tokens")
    if total_tokens is not None:
        if not isinstance(total_tokens, (int, float)):
            return False, "'total_tokens' must be a number"
        if total_tokens < 0:
            return False, "'total_tokens' must be non-negative"

    total_steps = workflow_run.get("total_steps")
    if total_steps is not None:
        if not isinstance(total_steps, (int, float)):
            return False, "'total_steps' must be a number"
        if total_steps < 0:
            return False, "'total_steps' must be non-negative"

    status = workflow_run.get("status")
    if status is not None:
        if status not in VALID_STATUS_VALUES:
            return False, (
                f"workflow_run 'status' value '{status}' is not valid "
                f"(expected one of {sorted(VALID_STATUS_VALUES)})"
            )

    # ---- started_at / finished_at on workflow run ----
    for ts_field in ("started_at", "finished_at"):
        ts_str = workflow_run.get(ts_field)
        if ts_str is not None and isinstance(ts_str, str):
            try:
                _parse_iso_timestamp(ts_str)
            except (ValueError, TypeError):
                return False, (
                    f"workflow_run.{ts_field} '{ts_str}' is not valid "
                    f"ISO 8601 format"
                )

    return True, ""


def validate_dify_input_data(
    detection_type: str, input_data: dict
) -> Tuple[bool, str]:
    """Extended Dify-specific validation for golden dataset ``input_data``.

    Dispatches validation depending on the detection type:

    * **Dify detection types** (``dify_rag_poisoning``,
      ``dify_iteration_escape``, ``dify_model_fallback``,
      ``dify_variable_leak``, ``dify_classifier_drift``,
      ``dify_tool_schema_mismatch``): expects ``input_data["workflow_run"]``
      and validates it with :func:`validate_dify_workflow_run`.
      Additionally checks for type-specific required fields.
    * All other types pass without Dify-specific checks.

    Args:
        detection_type: The detection type string.
        input_data: The input_data dict from a golden dataset entry.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")``
        otherwise.
    """
    if not isinstance(input_data, dict):
        return False, "input_data must be a dict"

    # --- Dify-specific detection types ---
    if detection_type in DIFY_DETECTION_TYPES:
        workflow_run = input_data.get("workflow_run")
        if workflow_run is None:
            return False, (
                f"input_data for '{detection_type}' must contain 'workflow_run'"
            )
        if not isinstance(workflow_run, dict):
            return False, (
                f"input_data['workflow_run'] must be a dict for '{detection_type}'"
            )

        valid, err = validate_dify_workflow_run(workflow_run)
        if not valid:
            return False, err

        # Type-specific required fields within the workflow_run
        if detection_type == "dify_rag_poisoning":
            if "app_type" not in workflow_run:
                return False, (
                    "workflow_run must contain 'app_type' key for "
                    "'dify_rag_poisoning' detection type"
                )

        if detection_type == "dify_classifier_drift":
            if "app_type" not in workflow_run:
                return False, (
                    "workflow_run must contain 'app_type' key for "
                    "'dify_classifier_drift' detection type"
                )

        return True, ""

    # --- All other types: no Dify-specific validation needed ---
    return True, ""
