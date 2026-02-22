"""n8n node schema validation for quality healing fixes.

Validates that fix changes target valid n8n node parameters,
preventing fixes from introducing unknown or invalid parameter keys.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Set


# Known n8n node type schemas mapping node type to valid parameter keys.
N8N_NODE_SCHEMAS: Dict[str, Set[str]] = {
    # Agent nodes
    "@n8n/n8n-nodes-langchain.agent": {
        "systemMessage", "text", "options", "hasOutputParser",
        "options.systemMessage", "options.maxIterations", "options.returnIntermediateSteps",
    },
    # OpenAI Chat Model
    "@n8n/n8n-nodes-langchain.lmChatOpenAi": {
        "model", "options", "options.temperature", "options.maxTokens",
        "options.topP", "options.frequencyPenalty", "options.presencePenalty",
    },
    # Anthropic Chat Model
    "@n8n/n8n-nodes-langchain.lmChatAnthropic": {
        "model", "options", "options.temperature", "options.maxTokensToSample",
    },
    # Tool nodes
    "n8n-nodes-base.httpRequest": {
        "url", "method", "authentication", "options", "headerParameters",
        "queryParameters", "body", "sendBody", "bodyContentType",
    },
    # Code node
    "n8n-nodes-base.code": {
        "jsCode", "pythonCode", "mode", "language",
    },
    # Set node
    "n8n-nodes-base.set": {
        "assignments", "options", "mode",
    },
    # IF node
    "n8n-nodes-base.if": {
        "conditions", "combineConditions",
    },
    # Switch node
    "n8n-nodes-base.switch": {
        "rules", "fallbackOutput",
    },
    # Common settings (apply to all nodes via n8n framework)
    "_common": {
        "continueOnFail", "alwaysOutputData", "retryOnFail", "maxTries",
        "waitBetweenTries", "timeout", "executeOnce", "notes",
    },
}

# Internal applicator keys that should be skipped during validation
_SKIP_KEYS = {"mode", "value"}


@dataclass
class SchemaValidationResult:
    """Result of validating fix changes against an n8n node schema."""
    valid: bool
    invalid_keys: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_fix_against_n8n_schema(
    fix_changes: Dict[str, Any],
    node_type: str,
) -> SchemaValidationResult:
    """Validate that fix changes only reference valid parameters for a given n8n node type.

    Args:
        fix_changes: Dictionary of changes the fix wants to apply (may contain
            nested "parameters.xxx" paths or flat parameter keys).
        node_type: The n8n node type string (e.g. "@n8n/n8n-nodes-langchain.agent").

    Returns:
        SchemaValidationResult indicating whether all keys are valid.
    """
    if node_type not in N8N_NODE_SCHEMAS:
        return SchemaValidationResult(
            valid=True,
            warnings=[f"Unknown node type: {node_type}"],
        )

    # Build the combined set of valid keys for this node type
    valid_keys = N8N_NODE_SCHEMAS[node_type] | N8N_NODE_SCHEMAS["_common"]

    # Extract parameter keys from fix_changes
    param_keys = _extract_parameter_keys(fix_changes)

    invalid_keys: List[str] = []
    for key in param_keys:
        # Skip internal applicator format keys
        if key in _SKIP_KEYS:
            continue
        if key not in valid_keys:
            invalid_keys.append(key)

    warnings: List[str] = []
    if invalid_keys:
        warnings.append(
            f"Fix references unknown parameters for {node_type}: {', '.join(invalid_keys)}"
        )

    return SchemaValidationResult(
        valid=len(invalid_keys) == 0,
        invalid_keys=invalid_keys,
        warnings=warnings,
    )


def _extract_parameter_keys(changes: Dict[str, Any]) -> List[str]:
    """Extract parameter keys from a fix changes dict.

    Handles both flat keys and nested "parameters.xxx" paths by stripping
    the "parameters." prefix when present.
    """
    keys: List[str] = []
    for key in changes:
        # Strip "parameters." prefix if present
        if key.startswith("parameters."):
            param_key = key[len("parameters."):]
            keys.append(param_key)
        else:
            keys.append(key)

    # Also recurse into a top-level "parameters" dict if present
    if "parameters" in changes and isinstance(changes["parameters"], dict):
        for key in changes["parameters"]:
            keys.append(key)

    return keys
