from dataclasses import dataclass
from typing import List, Dict, Any, Callable, Optional


@dataclass
class CorruptionIssue:
    issue_type: str
    field: Optional[str]
    message: str
    severity: str


@dataclass
class StateSnapshot:
    state_delta: dict
    agent_id: str


@dataclass
class Schema:
    fields: Dict[str, type]
    required_fields: List[str]


class SemanticCorruptionDetector:
    def __init__(self):
        self.domain_validators: Dict[str, Callable] = {
            "age": lambda v: isinstance(v, (int, float)) and 0 <= v <= 150,
            "price": lambda v: isinstance(v, (int, float)) and v >= 0,
            "percentage": lambda v: isinstance(v, (int, float)) and 0 <= v <= 100,
            "email": lambda v: isinstance(v, str) and "@" in v and "." in v,
            "url": lambda v: isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")),
        }
        self.known_ids: set = set()
    
    def detect_corruption(
        self,
        prev_state: StateSnapshot,
        current_state: StateSnapshot,
        schema: Optional[Schema] = None,
    ) -> List[CorruptionIssue]:
        issues = []
        
        if schema:
            issues.extend(self._validate_schema(current_state, schema))
        
        issues.extend(self._validate_cross_field_consistency(current_state))
        issues.extend(self._validate_domain_constraints(current_state))
        issues.extend(self._detect_hallucinated_references(prev_state, current_state))
        issues.extend(self._detect_value_copying(current_state))
        
        return issues
    
    def _validate_schema(self, state: StateSnapshot, schema: Schema) -> List[CorruptionIssue]:
        issues = []
        data = state.state_delta
        
        for key, value in data.items():
            if key not in schema.fields:
                issues.append(CorruptionIssue(
                    issue_type="hallucinated_key",
                    field=key,
                    message=f"Key '{key}' not in schema",
                    severity="medium",
                ))
            elif not isinstance(value, schema.fields[key]):
                issues.append(CorruptionIssue(
                    issue_type="type_drift",
                    field=key,
                    message=f"Expected {schema.fields[key].__name__}, got {type(value).__name__}",
                    severity="high",
                ))
        
        for required in schema.required_fields:
            if required not in data:
                issues.append(CorruptionIssue(
                    issue_type="missing_field",
                    field=required,
                    message=f"Required field '{required}' missing",
                    severity="high",
                ))
        
        return issues
    
    def _validate_cross_field_consistency(self, state: StateSnapshot) -> List[CorruptionIssue]:
        issues = []
        data = state.state_delta
        
        if "start_date" in data and "end_date" in data:
            try:
                if data["start_date"] > data["end_date"]:
                    issues.append(CorruptionIssue(
                        issue_type="cross_field_inconsistency",
                        field="start_date,end_date",
                        message="Start date after end date",
                        severity="high",
                    ))
            except (TypeError, ValueError):
                pass
        
        if "min_value" in data and "max_value" in data:
            try:
                if data["min_value"] > data["max_value"]:
                    issues.append(CorruptionIssue(
                        issue_type="cross_field_inconsistency",
                        field="min_value,max_value",
                        message="Min value greater than max value",
                        severity="high",
                    ))
            except (TypeError, ValueError):
                pass
        
        return issues
    
    def _validate_domain_constraints(self, state: StateSnapshot) -> List[CorruptionIssue]:
        issues = []
        data = state.state_delta
        
        for key, validator in self.domain_validators.items():
            if key in data:
                try:
                    if not validator(data[key]):
                        issues.append(CorruptionIssue(
                            issue_type="domain_violation",
                            field=key,
                            message=f"Value {data[key]} violates domain constraint for {key}",
                            severity="medium",
                        ))
                except Exception:
                    issues.append(CorruptionIssue(
                        issue_type="domain_violation",
                        field=key,
                        message=f"Could not validate {key}",
                        severity="low",
                    ))
        
        return issues
    
    def _detect_hallucinated_references(
        self,
        prev: StateSnapshot,
        current: StateSnapshot,
    ) -> List[CorruptionIssue]:
        issues = []
        data = current.state_delta
        
        id_fields = [k for k in data if k.endswith("_id")]
        for field in id_fields:
            ref_id = data[field]
            if isinstance(ref_id, str) and ref_id not in self.known_ids:
                if prev.state_delta.get(field) != ref_id:
                    issues.append(CorruptionIssue(
                        issue_type="hallucinated_reference",
                        field=field,
                        message=f"Reference '{ref_id}' may not exist",
                        severity="high",
                    ))
        
        return issues
    
    def _detect_value_copying(self, state: StateSnapshot) -> List[CorruptionIssue]:
        issues = []
        data = state.state_delta
        values = list(data.values())
        keys = list(data.keys())
        
        for i, v1 in enumerate(values):
            if not isinstance(v1, str) or len(v1) <= 10:
                continue
            for j, v2 in enumerate(values[i + 1:], i + 1):
                if v1 == v2:
                    issues.append(CorruptionIssue(
                        issue_type="suspicious_value_copy",
                        field=f"{keys[i]},{keys[j]}",
                        message=f"Identical values in different fields",
                        severity="low",
                    ))
        
        return issues
    
    def register_known_id(self, id_value: str):
        self.known_ids.add(id_value)


corruption_detector = SemanticCorruptionDetector()
