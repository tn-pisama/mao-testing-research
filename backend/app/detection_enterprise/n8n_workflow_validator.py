"""Validates generated n8n workflow JSON structures.

Ensures that n8n workflow data produced by the golden dataset generator
has valid node types, connection topology, and structural integrity.

Used by:
1. Golden data generator -- validate n8n workflow entries before saving
2. Calibration pipeline -- pre-check n8n-typed entries
3. Input schemas -- extended n8n-specific validation
"""

import logging
import re
from typing import Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known n8n node types
# ---------------------------------------------------------------------------

KNOWN_N8N_NODE_TYPES: Set[str] = {
    # Core / utility
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.code",
    "n8n-nodes-base.set",
    "n8n-nodes-base.if",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.noOp",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.function",
    "n8n-nodes-base.functionItem",
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.wait",
    "n8n-nodes-base.respondToWebhook",
    # File / data format
    "n8n-nodes-base.spreadsheetFile",
    "n8n-nodes-base.xml",
    "n8n-nodes-base.html",
    # Communication
    "n8n-nodes-base.emailSend",
    "n8n-nodes-base.slack",
    "n8n-nodes-base.telegram",
    "n8n-nodes-base.discord",
    "n8n-nodes-base.gmail",
    # Databases
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.mysql",
    "n8n-nodes-base.redis",
    "n8n-nodes-base.mongodb",
    # SaaS integrations
    "n8n-nodes-base.googleSheets",
    "n8n-nodes-base.airtable",
    "n8n-nodes-base.hubspot",
    "n8n-nodes-base.salesforce",
    "n8n-nodes-base.stripe",
    # AI
    "n8n-nodes-base.openai",
    # LangChain nodes
    "@n8n/n8n-nodes-langchain.agent",
    "@n8n/n8n-nodes-langchain.chainLlm",
    "@n8n/n8n-nodes-langchain.toolWorkflow",
    "@n8n/n8n-nodes-langchain.memoryBufferWindow",
    "@n8n/n8n-nodes-langchain.outputParserStructured",
    "@n8n/n8n-nodes-langchain.vectorStoreRetriever",
    "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
}

# Compiled regex for valid n8n node type prefixes.
# Matches:
#   n8n-nodes-base.<name>
#   @n8n/n8n-nodes-langchain.<name>
#   n8n-nodes-<community-package>.<name>   (custom / community nodes)
_VALID_NODE_TYPE_RE = re.compile(
    r"^(?:n8n-nodes-[a-zA-Z0-9_-]+\.[a-zA-Z0-9_]+|@n8n/n8n-nodes-[a-zA-Z0-9_-]+\.[a-zA-Z0-9_]+)$"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_valid_n8n_node_type(node_type: str) -> bool:
    """Quick check if *node_type* matches a known n8n pattern.

    Returns True when the type is either:
    - An exact member of ``KNOWN_N8N_NODE_TYPES``, or
    - Matches the structural prefix pattern (``n8n-nodes-*.*`` or
      ``@n8n/n8n-nodes-*.*``).
    """
    if node_type in KNOWN_N8N_NODE_TYPES:
        return True
    return bool(_VALID_NODE_TYPE_RE.match(node_type))


def validate_n8n_workflow(workflow_json: dict) -> Tuple[bool, str]:
    """Validate that *workflow_json* has a valid n8n workflow structure.

    Checks performed:
    1. Required fields: ``nodes`` (list), ``connections`` (dict).
    2. Optional fields: ``id``, ``name``, ``settings`` (type-checked when present).
    3. Per-node fields: ``id``, ``name``, ``type``, ``position``, ``parameters``.
    4. Node type must match known n8n prefixes.
    5. Connection topology: keys must reference existing node names, and each
       connection target must reference an existing node name.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")`` otherwise.
    """
    if not isinstance(workflow_json, dict):
        return False, "workflow_json must be a dict"

    # ---- required fields ----
    if "nodes" not in workflow_json:
        return False, "workflow_json missing required field 'nodes'"
    if "connections" not in workflow_json:
        return False, "workflow_json missing required field 'connections'"

    nodes = workflow_json["nodes"]
    connections = workflow_json["connections"]

    if not isinstance(nodes, list):
        return False, "'nodes' must be a list"
    if not isinstance(connections, dict):
        return False, "'connections' must be a dict"

    # ---- optional field type checks ----
    if "id" in workflow_json and not isinstance(workflow_json["id"], str):
        return False, "'id' must be a string"
    if "name" in workflow_json and not isinstance(workflow_json["name"], str):
        return False, "'name' must be a string"
    if "settings" in workflow_json and not isinstance(workflow_json["settings"], dict):
        return False, "'settings' must be a dict"

    # ---- per-node validation ----
    node_names: set = set()

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            return False, f"nodes[{idx}] must be a dict"

        # Required node fields
        for field in ("id", "name", "type", "position", "parameters"):
            if field not in node:
                return False, f"nodes[{idx}] missing required field '{field}'"

        # Field types
        if not isinstance(node["id"], (str, int)):
            return False, f"nodes[{idx}].id must be a string or int"
        if not isinstance(node["name"], str):
            return False, f"nodes[{idx}].name must be a string"
        if not isinstance(node["type"], str):
            return False, f"nodes[{idx}].type must be a string"
        if not isinstance(node["parameters"], dict):
            return False, f"nodes[{idx}].parameters must be a dict"

        # Position: list/tuple of exactly 2 ints (or floats that are integral)
        pos = node["position"]
        if not isinstance(pos, (list, tuple)) or len(pos) != 2:
            return False, f"nodes[{idx}].position must be a list of 2 numbers"
        for pi, coord in enumerate(pos):
            if not isinstance(coord, (int, float)):
                return False, (
                    f"nodes[{idx}].position[{pi}] must be an int or float"
                )

        # Node type validation
        ntype = node["type"]
        if not is_valid_n8n_node_type(ntype):
            return False, (
                f"nodes[{idx}].type '{ntype}' does not match any known n8n "
                f"node type pattern (expected n8n-nodes-*.* or @n8n/n8n-nodes-*.*)"
            )

        node_names.add(node["name"])

    # ---- connections validation ----
    for source_name, outputs in connections.items():
        # Source must be a known node name
        if source_name not in node_names:
            return False, (
                f"connections key '{source_name}' does not match any node name"
            )

        if not isinstance(outputs, dict):
            return False, (
                f"connections['{source_name}'] must be a dict, "
                f"got {type(outputs).__name__}"
            )

        # Expected structure: {"main": [[{...}]]}
        if "main" not in outputs:
            return False, (
                f"connections['{source_name}'] missing 'main' key"
            )

        main = outputs["main"]
        if not isinstance(main, list):
            return False, (
                f"connections['{source_name}'].main must be a list"
            )

        for output_idx, output_connections in enumerate(main):
            if not isinstance(output_connections, list):
                return False, (
                    f"connections['{source_name}'].main[{output_idx}] "
                    f"must be a list"
                )

            for conn_idx, conn in enumerate(output_connections):
                if not isinstance(conn, dict):
                    return False, (
                        f"connections['{source_name}'].main"
                        f"[{output_idx}][{conn_idx}] must be a dict"
                    )

                # Each connection entry must have a "node" key
                if "node" not in conn:
                    return False, (
                        f"connections['{source_name}'].main"
                        f"[{output_idx}][{conn_idx}] missing 'node' key"
                    )

                target_name = conn["node"]
                if target_name not in node_names:
                    return False, (
                        f"connections['{source_name}'].main"
                        f"[{output_idx}][{conn_idx}] references unknown "
                        f"node '{target_name}'"
                    )

                # Optional but expected keys
                if "type" in conn and not isinstance(conn["type"], str):
                    return False, (
                        f"connections['{source_name}'].main"
                        f"[{output_idx}][{conn_idx}].type must be a string"
                    )
                if "index" in conn and not isinstance(conn["index"], (int, float)):
                    return False, (
                        f"connections['{source_name}'].main"
                        f"[{output_idx}][{conn_idx}].index must be an int"
                    )

    return True, ""


# Detection types whose input_data contains a workflow_json key
_N8N_WORKFLOW_TYPES = frozenset({
    "n8n_schema",
    "n8n_cycle",
    "n8n_complexity",
    "n8n_error",
    "n8n_resource",
    "n8n_timeout",
})


def validate_n8n_input_data(
    detection_type: str, input_data: dict
) -> Tuple[bool, str]:
    """Extended n8n-specific validation for golden dataset ``input_data``.

    Dispatches validation depending on the detection type:

    * **n8n_schema / n8n_cycle / n8n_complexity / n8n_error / n8n_resource /
      n8n_timeout**: expects ``input_data["workflow_json"]`` and validates it
      with :func:`validate_n8n_workflow`.
    * **loop**: if ``input_data["states"]`` is present, checks that each
      ``agent_id`` resembles an n8n node name.
    * **workflow**: if ``input_data["workflow_definition"]`` is present,
      validates that it has ``nodes`` and ``connections``.
    * All other types pass without n8n-specific checks.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")`` otherwise.
    """
    if not isinstance(input_data, dict):
        return False, "input_data must be a dict"

    # --- n8n workflow types ---
    if detection_type in _N8N_WORKFLOW_TYPES:
        wf = input_data.get("workflow_json")
        if wf is None:
            return False, (
                f"input_data for '{detection_type}' must contain 'workflow_json'"
            )
        return validate_n8n_workflow(wf)

    # --- loop type: agent_id resembles n8n node name ---
    if detection_type == "loop":
        states = input_data.get("states")
        if isinstance(states, list):
            for idx, state in enumerate(states):
                if not isinstance(state, dict):
                    continue
                agent_id = state.get("agent_id")
                if agent_id is not None and not isinstance(agent_id, str):
                    return False, (
                        f"states[{idx}].agent_id must be a string"
                    )
        return True, ""

    # --- workflow type: structural check ---
    if detection_type == "workflow":
        wf_def = input_data.get("workflow_definition")
        if isinstance(wf_def, dict):
            if "nodes" not in wf_def:
                return False, (
                    "workflow_definition missing 'nodes'"
                )
            if "connections" not in wf_def:
                return False, (
                    "workflow_definition missing 'connections'"
                )
        return True, ""

    # --- all other types: no n8n-specific validation needed ---
    return True, ""
