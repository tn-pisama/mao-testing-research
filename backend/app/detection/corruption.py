from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime, timedelta
from collections import deque


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
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VelocityConfig:
    """Configuration for state change velocity thresholds."""
    window_seconds: float = 5.0
    max_changes_per_window: int = 10
    high_velocity_fields: List[str] = field(default_factory=lambda: [
        "counter", "count", "iteration", "step", "progress",
        "timestamp", "updated_at", "last_seen", "version",
    ])
    ignore_velocity_for_types: List[type] = field(default_factory=lambda: [bool])


@dataclass
class Schema:
    fields: Dict[str, type]
    required_fields: List[str]


class SemanticCorruptionDetector:
    def __init__(self, velocity_config: Optional[VelocityConfig] = None):
        self.domain_validators: Dict[str, Callable] = {
            "age": lambda v: isinstance(v, (int, float)) and 0 <= v <= 150,
            "price": lambda v: isinstance(v, (int, float)) and v >= 0,
            "percentage": lambda v: isinstance(v, (int, float)) and 0 <= v <= 100,
            "email": lambda v: isinstance(v, str) and "@" in v and "." in v,
            "url": lambda v: isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")),
        }
        self.known_ids: set = set()
        self.velocity_config = velocity_config or VelocityConfig()
        self._change_history: Dict[str, deque] = {}
        self._field_velocities: Dict[str, float] = {}
    
    def _is_high_velocity_field(self, field_name: str) -> bool:
        """Check if a field is expected to change rapidly."""
        field_lower = field_name.lower()
        return any(
            kw in field_lower 
            for kw in self.velocity_config.high_velocity_fields
        )
    
    def _update_velocity_tracking(self, field: str, timestamp: datetime) -> float:
        """Update velocity tracking for a field and return current velocity."""
        if field not in self._change_history:
            self._change_history[field] = deque(maxlen=100)
        
        self._change_history[field].append(timestamp)
        
        window_start = timestamp - timedelta(seconds=self.velocity_config.window_seconds)
        recent_changes = [
            t for t in self._change_history[field]
            if t >= window_start
        ]
        
        velocity = len(recent_changes) / self.velocity_config.window_seconds
        self._field_velocities[field] = velocity
        return velocity
    
    def _should_suppress_for_velocity(
        self,
        field: str,
        value: Any,
        timestamp: datetime,
    ) -> bool:
        """Check if a change should be suppressed due to expected high velocity."""
        if self._is_high_velocity_field(field):
            return True
        
        if type(value) in self.velocity_config.ignore_velocity_for_types:
            return False
        
        velocity = self._update_velocity_tracking(field, timestamp)
        
        if velocity > self.velocity_config.max_changes_per_window / self.velocity_config.window_seconds:
            return True
        
        return False
    
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
        issues.extend(self._detect_suspicious_rapid_changes(prev_state, current_state))
        
        filtered_issues = self._apply_velocity_filtering(issues, current_state)
        
        return filtered_issues
    
    def _apply_velocity_filtering(
        self,
        issues: List[CorruptionIssue],
        state: StateSnapshot,
    ) -> List[CorruptionIssue]:
        """Filter out issues for fields with expected high velocity."""
        filtered = []
        
        for issue in issues:
            if issue.field is None:
                filtered.append(issue)
                continue
            
            fields = issue.field.split(",")
            should_suppress = False
            
            for field in fields:
                field = field.strip()
                value = state.state_delta.get(field)
                
                if self._should_suppress_for_velocity(field, value, state.timestamp):
                    should_suppress = True
                    break
            
            if not should_suppress:
                filtered.append(issue)
        
        return filtered
    
    def _detect_suspicious_rapid_changes(
        self,
        prev: StateSnapshot,
        current: StateSnapshot,
    ) -> List[CorruptionIssue]:
        """Detect suspiciously rapid changes that don't fit expected patterns."""
        issues = []
        
        time_delta = (current.timestamp - prev.timestamp).total_seconds()
        if time_delta <= 0:
            time_delta = 0.001
        
        changed_fields = []
        for key in set(prev.state_delta.keys()) | set(current.state_delta.keys()):
            prev_val = prev.state_delta.get(key)
            curr_val = current.state_delta.get(key)
            
            if prev_val != curr_val and not self._is_high_velocity_field(key):
                changed_fields.append(key)
        
        change_rate = len(changed_fields) / time_delta
        
        if change_rate > 20 and len(changed_fields) > 5:
            issues.append(CorruptionIssue(
                issue_type="suspicious_rapid_changes",
                field=",".join(changed_fields[:5]) + ("..." if len(changed_fields) > 5 else ""),
                message=f"Unusually high change rate: {len(changed_fields)} fields in {time_delta:.2f}s",
                severity="medium",
            ))
        
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
