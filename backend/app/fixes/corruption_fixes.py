"""Fix generators for state corruption detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class CorruptionFixGenerator(BaseFixGenerator):
    """Generates fixes for state corruption detections."""
    
    def can_handle(self, detection_type: str) -> bool:
        return "corruption" in detection_type or "state" in detection_type
    
    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})
        issue_type = details.get("issue_type", "")
        field = details.get("field", "")
        
        fixes.append(self._pydantic_validation_fix(detection_id, details, context))
        
        if issue_type == "hallucinated_key":
            fixes.append(self._strict_schema_fix(detection_id, details, context))
        
        if issue_type in ("type_mismatch", "domain_violation"):
            fixes.append(self._type_coercion_fix(detection_id, field, details, context))
        
        if issue_type == "cross_field_inconsistency":
            fixes.append(self._cross_field_validator_fix(detection_id, details, context))
        
        fixes.append(self._state_snapshot_fix(detection_id, context))
        
        return fixes
    
    def _pydantic_validation_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        fields = details.get("expected_fields", ["query", "context", "response"])
        
        field_defs = "\n    ".join([f'{f}: Optional[str] = None' for f in fields[:5]])
        
        code = f'''from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any

class AgentState(BaseModel):
    """Validated agent state with strict type checking."""
    {field_defs}
    
    model_config = {{"extra": "forbid"}}  # Reject unknown fields
    
    @field_validator("*", mode="before")
    @classmethod
    def validate_not_none_string(cls, v, info):
        if v is None:
            return v
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

def validate_state(state: dict) -> AgentState:
    """Validate and sanitize agent state."""
    try:
        return AgentState(**state)
    except Exception as e:
        logger.error(f"State validation failed: {{e}}")
        raise StateCorruptionError(f"Invalid state: {{e}}")

# Usage in agent node
def agent_node(state: dict) -> dict:
    validated = validate_state(state)
    result = process(validated)
    return validate_state(result).model_dump()'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="state_corruption",
            fix_type=FixType.STATE_VALIDATION,
            confidence=FixConfidence.HIGH,
            title="Add Pydantic state validation",
            description="Use Pydantic models to validate agent state at each step, catching corruption early.",
            rationale="State corruption was detected where field values didn't match expected types or contained unexpected keys. Pydantic validation catches these issues immediately.",
            code_changes=[
                CodeChange(
                    file_path="models/state.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Pydantic model for validated agent state",
                )
            ],
            estimated_impact="Catches state corruption at the source, prevents cascade effects",
            tags=["validation", "pydantic", "state-management"],
        )
    
    def _strict_schema_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        hallucinated_key = details.get("field", "unknown_field")
        
        code = f'''from typing import TypedDict, NotRequired

class StrictAgentState(TypedDict):
    """Strict state schema - only defined keys allowed."""
    query: str
    context: list[str]
    response: NotRequired[str]
    metadata: NotRequired[dict]

def sanitize_state(state: dict, schema: type = StrictAgentState) -> dict:
    """Remove keys not in schema, log warnings for hallucinated keys."""
    allowed_keys = set(schema.__annotations__.keys())
    sanitized = {{}}
    
    for key, value in state.items():
        if key in allowed_keys:
            sanitized[key] = value
        else:
            logger.warning(
                f"Removing hallucinated key '{{key}}' from state. "
                f"Value was: {{str(value)[:100]}}"
            )
    
    return sanitized

# Wrap your agent
def agent_with_schema_enforcement(func):
    def wrapper(state: dict) -> dict:
        clean_input = sanitize_state(state)
        result = func(clean_input)
        return sanitize_state(result)
    return wrapper'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="state_corruption",
            fix_type=FixType.SCHEMA_ENFORCEMENT,
            confidence=FixConfidence.HIGH,
            title=f"Enforce strict schema (remove hallucinated key: '{hallucinated_key}')",
            description="Add schema enforcement that rejects or removes keys not defined in the state schema.",
            rationale=f"The agent added an unexpected key '{hallucinated_key}' to the state. This can cause downstream errors or security issues. Strict schema enforcement prevents this.",
            code_changes=[
                CodeChange(
                    file_path="utils/schema.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Strict schema enforcement with hallucinated key removal",
                )
            ],
            estimated_impact="Prevents state pollution from LLM hallucinations",
            tags=["schema", "validation", "hallucination-prevention"],
        )
    
    def _type_coercion_fix(
        self,
        detection_id: str,
        field: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        expected_type = details.get("expected_type", "str")
        actual_type = details.get("actual_type", "unknown")
        
        code = f'''def coerce_field(value: Any, target_type: type, field_name: str) -> Any:
    """Safely coerce a value to target type with logging."""
    if value is None:
        return None
    
    if isinstance(value, target_type):
        return value
    
    try:
        if target_type == int:
            return int(float(str(value)))
        elif target_type == float:
            return float(str(value))
        elif target_type == str:
            return str(value)
        elif target_type == bool:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        elif target_type == list:
            if isinstance(value, str):
                return [value]
            return list(value)
        else:
            return target_type(value)
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Could not coerce {{field_name}} from {{type(value).__name__}} "
            f"to {{target_type.__name__}}: {{e}}"
        )
        return None

# Field-specific coercion
FIELD_TYPES = {{
    "{field}": {expected_type},
    "count": int,
    "score": float,
    "enabled": bool,
}}

def coerce_state(state: dict) -> dict:
    """Coerce all fields to expected types."""
    result = {{}}
    for key, value in state.items():
        if key in FIELD_TYPES:
            result[key] = coerce_field(value, FIELD_TYPES[key], key)
        else:
            result[key] = value
    return result'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="state_corruption",
            fix_type=FixType.INPUT_SANITIZATION,
            confidence=FixConfidence.MEDIUM,
            title=f"Add type coercion for '{field}' field",
            description=f"Automatically coerce '{field}' from {actual_type} to {expected_type} with logging.",
            rationale=f"Field '{field}' had type {actual_type} but expected {expected_type}. Type coercion provides graceful handling while logging the discrepancy.",
            code_changes=[
                CodeChange(
                    file_path="utils/coercion.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Type coercion utilities with logging",
                )
            ],
            estimated_impact="Prevents type errors while preserving data where possible",
            tags=["type-safety", "coercion", "validation"],
        )
    
    def _cross_field_validator_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from pydantic import BaseModel, model_validator
from datetime import datetime

class ValidatedState(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    @model_validator(mode="after")
    def validate_date_order(self):
        if self.start_date and self.end_date:
            start = datetime.fromisoformat(self.start_date)
            end = datetime.fromisoformat(self.end_date)
            if start > end:
                raise ValueError(f"start_date ({self.start_date}) must be before end_date ({self.end_date})")
        return self
    
    @model_validator(mode="after")
    def validate_value_range(self):
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise ValueError(f"min_value ({self.min_value}) cannot exceed max_value ({self.max_value})")
        return self

# Generic cross-field validation
FIELD_CONSTRAINTS = [
    ("start_date", "end_date", lambda a, b: a <= b, "start must be before end"),
    ("min_value", "max_value", lambda a, b: a <= b, "min must not exceed max"),
    ("requested", "available", lambda a, b: a <= b, "cannot request more than available"),
]

def validate_cross_fields(state: dict) -> list[str]:
    """Validate cross-field constraints, return list of violations."""
    violations = []
    for field_a, field_b, check, message in FIELD_CONSTRAINTS:
        val_a = state.get(field_a)
        val_b = state.get(field_b)
        if val_a is not None and val_b is not None:
            try:
                if not check(val_a, val_b):
                    violations.append(f"{field_a}/{field_b}: {message}")
            except Exception:
                pass
    return violations'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="state_corruption",
            fix_type=FixType.STATE_VALIDATION,
            confidence=FixConfidence.HIGH,
            title="Add cross-field validation rules",
            description="Validate relationships between fields (e.g., start_date < end_date, min < max).",
            rationale="Inconsistent field values were detected where one field contradicts another. Cross-field validators catch these logical errors.",
            code_changes=[
                CodeChange(
                    file_path="validators/cross_field.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Cross-field validation using Pydantic model validators",
                )
            ],
            estimated_impact="Catches logical inconsistencies before they cause runtime errors",
            tags=["validation", "cross-field", "logic-check"],
        )
    
    def _state_snapshot_fix(
        self,
        detection_id: str,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import copy
import hashlib
import json
from typing import Optional

class StateCheckpointer:
    """Checkpoint and recover state to handle corruption."""
    
    def __init__(self, max_checkpoints=10):
        self.checkpoints = []
        self.max_checkpoints = max_checkpoints
    
    def checkpoint(self, state: dict, label: str = "") -> str:
        """Save a checkpoint of current state."""
        snapshot = {
            "state": copy.deepcopy(state),
            "hash": self._hash_state(state),
            "label": label,
        }
        self.checkpoints.append(snapshot)
        
        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints.pop(0)
        
        return snapshot["hash"]
    
    def recover(self, target_hash: Optional[str] = None) -> dict:
        """Recover state from checkpoint."""
        if not self.checkpoints:
            raise ValueError("No checkpoints available")
        
        if target_hash:
            for cp in reversed(self.checkpoints):
                if cp["hash"] == target_hash:
                    return copy.deepcopy(cp["state"])
            raise ValueError(f"Checkpoint {target_hash} not found")
        
        return copy.deepcopy(self.checkpoints[-1]["state"])
    
    def _hash_state(self, state: dict) -> str:
        return hashlib.sha256(
            json.dumps(state, sort_keys=True).encode()
        ).hexdigest()[:16]

# Usage with agent
checkpointer = StateCheckpointer()

def agent_with_recovery(state: dict) -> dict:
    # Checkpoint before risky operations
    checkpoint_hash = checkpointer.checkpoint(state, "pre_processing")
    
    try:
        result = process_state(state)
        validate_state(result)  # Raises on corruption
        return result
    except StateCorruptionError:
        logger.warning("State corruption detected, recovering from checkpoint")
        return checkpointer.recover(checkpoint_hash)'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="state_corruption",
            fix_type=FixType.CHECKPOINT_RECOVERY,
            confidence=FixConfidence.MEDIUM,
            title="Add state checkpointing for corruption recovery",
            description="Checkpoint state before operations to enable recovery when corruption is detected.",
            rationale="When state corruption occurs, having a recent valid checkpoint allows automatic recovery instead of failing completely.",
            code_changes=[
                CodeChange(
                    file_path="utils/checkpointer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="State checkpointing and recovery system",
                )
            ],
            estimated_impact="Enables automatic recovery from state corruption",
            tags=["recovery", "checkpoint", "resilience"],
        )
