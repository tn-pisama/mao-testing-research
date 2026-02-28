"""Input data schemas for detection golden dataset entries.

Machine-readable validation schemas for each detector's expected
input_data format. Used by:
1. Golden data generator -- validate entries before saving
2. Calibration pipeline -- validate entries before running
3. API -- validate incoming traces

Schema definitions are based on the actual adapters in calibrate.py.
"""

from typing import Any, Dict, List, Tuple

# Schema for each detection type's input_data
# Keys:
#   required:  top-level required keys
#   optional:  top-level optional keys
#   nested:    validation for nested structures
#              {key: {is_list, min_items, item_keys, optional_item_keys}}
INPUT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "loop": {
        "required": ["states"],
        "nested": {
            "states": {
                "is_list": True,
                "min_items": 2,
                "item_keys": ["agent_id", "content"],
                "optional_item_keys": ["state_delta"],
            }
        },
    },
    "persona_drift": {
        "required": ["agent", "output"],
        "nested": {
            "agent": {
                "is_list": False,
                "item_keys": ["id", "persona_description"],
            }
        },
    },
    "hallucination": {
        "required": ["output", "sources"],
        "nested": {
            "sources": {
                "is_list": True,
                "min_items": 1,
                "item_keys": ["content"],
                "optional_item_keys": ["metadata"],
            }
        },
    },
    "injection": {
        "required": ["text"],
    },
    "overflow": {
        "required": ["current_tokens", "model"],
    },
    "corruption": {
        "required": ["prev_state", "current_state"],
    },
    "coordination": {
        "required": ["messages", "agent_ids"],
        "nested": {
            "messages": {
                "is_list": True,
                "min_items": 1,
                "item_keys": ["from_agent", "to_agent", "content", "timestamp"],
                "optional_item_keys": ["acknowledged"],
            }
        },
    },
    "communication": {
        "required": ["sender_message", "receiver_response"],
    },
    "context": {
        "required": ["context", "output"],
    },
    "grounding": {
        "required": ["agent_output", "source_documents"],
    },
    "retrieval_quality": {
        "required": ["query", "retrieved_documents", "agent_output"],
    },
    "completion": {
        "required": ["task", "agent_output"],
        "optional": ["subtasks", "success_criteria"],
    },
    "derailment": {
        "required": ["output", "task"],
    },
    "specification": {
        "required": ["user_intent", "task_specification"],
    },
    "decomposition": {
        "required": ["decomposition", "task_description"],
    },
    "withholding": {
        "required": ["agent_output", "internal_state"],
    },
    "workflow": {
        "required": ["workflow_definition"],
        "nested": {
            "workflow_definition": {
                "is_list": False,
                "item_keys": ["nodes", "connections"],
            }
        },
    },
    "n8n_schema": {
        "required": ["workflow_json"],
        "nested": {
            "workflow_json": {
                "is_list": False,
                "item_keys": ["nodes", "connections"],
            }
        },
    },
    "n8n_cycle": {
        "required": ["workflow_json"],
        "nested": {
            "workflow_json": {
                "is_list": False,
                "item_keys": ["nodes", "connections"],
            }
        },
    },
    "n8n_complexity": {
        "required": ["workflow_json"],
        "nested": {
            "workflow_json": {
                "is_list": False,
                "item_keys": ["nodes"],
            }
        },
    },
    "n8n_error": {
        "required": ["workflow_json"],
    },
    "n8n_resource": {
        "required": ["workflow_json"],
    },
    "n8n_timeout": {
        "required": ["workflow_json"],
    },
}


def validate_input(detection_type: str, input_data: dict) -> Tuple[bool, str]:
    """Validate input_data matches expected schema for a detection type.

    Args:
        detection_type: The detection type key (e.g., "loop", "hallucination").
        input_data: The input_data dict to validate.

    Returns:
        (valid, error_message) tuple. error_message is "" if valid.
    """
    schema = INPUT_SCHEMAS.get(detection_type)
    if schema is None:
        return True, ""  # Unknown types pass validation (extensibility)

    if not isinstance(input_data, dict):
        return False, f"input_data must be a dict, got {type(input_data).__name__}"

    # Check required keys
    for key in schema.get("required", []):
        if key not in input_data:
            return False, f"Missing required key '{key}' for {detection_type}"

    # Check nested structures
    for key, nested_schema in schema.get("nested", {}).items():
        if key not in input_data:
            continue  # Already caught by required-key check above

        value = input_data[key]

        if nested_schema.get("is_list"):
            if not isinstance(value, list):
                return False, f"'{key}' must be a list for {detection_type}"

            min_items = nested_schema.get("min_items", 0)
            if len(value) < min_items:
                return (
                    False,
                    f"'{key}' needs at least {min_items} items, got {len(value)}",
                )

            # Validate item keys
            required_item_keys = nested_schema.get("item_keys", [])
            for i, item in enumerate(value):
                if not isinstance(item, dict):
                    return False, f"'{key}[{i}]' must be a dict"
                for ik in required_item_keys:
                    if ik not in item:
                        return False, f"'{key}[{i}]' missing key '{ik}'"
        else:
            # Single dict
            if not isinstance(value, dict):
                return False, f"'{key}' must be a dict for {detection_type}"
            required_item_keys = nested_schema.get("item_keys", [])
            for ik in required_item_keys:
                if ik not in value:
                    return False, f"'{key}' missing key '{ik}'"

    return True, ""


def get_schema(detection_type: str) -> Dict[str, Any]:
    """Get the input schema for a detection type.

    Returns an empty dict for unknown detection types.
    """
    return INPUT_SCHEMAS.get(detection_type, {})


def get_required_keys(detection_type: str) -> List[str]:
    """Get the list of required top-level keys for a detection type.

    Returns an empty list for unknown detection types.
    """
    schema = INPUT_SCHEMAS.get(detection_type, {})
    return schema.get("required", [])
