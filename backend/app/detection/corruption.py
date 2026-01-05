"""
F7: Memory/State Corruption Detection (MAST Taxonomy)
======================================================

Detects when agent memory or state becomes corrupted, including:
- Structured state corruption (type drift, schema violations)
- Text-based context corruption (ignoring related context)
- Cross-field inconsistencies
- Hallucinated references

Version History:
- v1.0: Initial implementation (structured state only)
- v1.1: Improved for adversarial accuracy:
  - Text-based context analysis for ignored context
  - Related topic extraction and verification
  - Narrow focus detection patterns
  - Task dependency awareness
"""

# Detector version for tracking
DETECTOR_VERSION = "1.1"
DETECTOR_NAME = "SemanticCorruptionDetector"

from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import re


@dataclass
class CorruptionIssue:
    issue_type: str
    field: Optional[str]
    message: str
    severity: str


@dataclass
class CorruptionResult:
    detected: bool
    confidence: float
    issues: List[CorruptionIssue]
    issue_count: int
    max_severity: str
    raw_score: Optional[float] = None
    calibration_info: Optional[Dict[str, Any]] = None


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
    """
    Detects F7: Memory/State Corruption in agent systems.

    Handles both structured state corruption and text-based context corruption.
    """

    # v1.1: Related topic mappings for context verification
    # When a task mentions key topic, related topics should typically be addressed
    RELATED_TOPICS = {
        'authentication': ['session', 'token', 'login', 'logout', 'credential', 'password', 'security'],
        'auth': ['session', 'token', 'login', 'logout', 'credential', 'password', 'security'],
        'login': ['session', 'authentication', 'token', 'logout', 'security'],
        'database': ['transaction', 'connection', 'query', 'migration', 'schema', 'index'],
        'api': ['endpoint', 'request', 'response', 'error handling', 'validation', 'rate limit'],
        'payment': ['refund', 'transaction', 'billing', 'subscription', 'invoice'],
        'user': ['profile', 'permission', 'role', 'account', 'preference'],
        'cache': ['invalidation', 'expiration', 'refresh', 'consistency'],
        'file': ['permission', 'path', 'encoding', 'backup', 'cleanup'],
        'error': ['logging', 'handling', 'recovery', 'notification', 'retry'],
        'test': ['coverage', 'assertion', 'mock', 'fixture', 'edge case'],
    }

    # v1.1: Patterns indicating narrow focus (potential context ignorance)
    NARROW_FOCUS_PATTERNS = [
        (r'\bonly\s+(?:addressed|fixed|updated|changed|modified)\b', 'explicit_narrow_focus'),
        (r'\bjust\s+(?:the|this|that)\s+\w+\b', 'narrow_scope'),
        (r'\bfocused\s+(?:specifically|only|solely)\s+on\b', 'explicit_narrow_focus'),
        (r'\bwithout\s+(?:touching|changing|modifying|affecting)\b', 'explicit_exclusion'),
        (r'\bdidn\'t\s+(?:touch|change|modify|address)\b', 'explicit_exclusion'),
        (r'\bignored?\s+(?:the|any)\b', 'explicit_ignorance'),
        (r'\bspecific\s+(?:fix|change|update)\b', 'narrow_scope'),
    ]

    # v1.1: Patterns indicating comprehensive handling (reduces false positives)
    COMPREHENSIVE_PATTERNS = [
        r'\balso\s+(?:updated|checked|verified|ensured)\b',
        r'\badditionally\b',
        r'\brelated\s+(?:to|changes|updates)\b',
        r'\bensured?\s+(?:that|consistency)\b',
        r'\bconsidered?\s+(?:the|all|related)\b',
        r'\bacross\s+(?:the|all|related)\b',
    ]

    def __init__(
        self,
        velocity_config: Optional[VelocityConfig] = None,
        confidence_scaling: float = 1.0,
    ):
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        url_pattern = re.compile(r'^https?://[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+(/.*)?$')
        
        self.domain_validators: Dict[str, Callable] = {
            "age": lambda v: isinstance(v, (int, float)) and 0 <= v <= 150,
            "price": lambda v: isinstance(v, (int, float)) and v >= 0,
            "percentage": lambda v: isinstance(v, (int, float)) and 0 <= v <= 100,
            "email": lambda v: isinstance(v, str) and bool(email_pattern.match(v)),
            "url": lambda v: isinstance(v, str) and bool(url_pattern.match(v)),
            "phone": lambda v: isinstance(v, str) and len(re.sub(r'\D', '', v)) >= 10,
            "uuid": lambda v: isinstance(v, str) and len(v) == 36 and v.count('-') == 4,
        }
        self.known_ids: set = set()
        self.velocity_config = velocity_config or VelocityConfig()
        self._change_history: Dict[str, deque] = {}
        self._field_velocities: Dict[str, float] = {}
        self.confidence_scaling = confidence_scaling
    
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
    
    def detect_corruption_with_confidence(
        self,
        prev_state: StateSnapshot,
        current_state: StateSnapshot,
        schema: Optional[Schema] = None,
    ) -> CorruptionResult:
        issues = self.detect_corruption(prev_state, current_state, schema)
        
        max_severity = "low"
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        
        for issue in issues:
            sev = issue.severity
            if sev in severity_counts:
                severity_counts[sev] += 1
            if self._severity_rank(sev) > self._severity_rank(max_severity):
                max_severity = sev
        
        raw_score = self._calculate_raw_score(issues, severity_counts)
        confidence, calibration_info = self._calibrate_confidence(
            issues=issues,
            severity_counts=severity_counts,
            max_severity=max_severity,
            raw_score=raw_score,
        )
        
        return CorruptionResult(
            detected=len(issues) > 0,
            confidence=confidence,
            issues=issues,
            issue_count=len(issues),
            max_severity=max_severity if issues else "none",
            raw_score=raw_score,
            calibration_info=calibration_info,
        )
    
    def _severity_rank(self, severity: str) -> int:
        ranks = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return ranks.get(severity, 0)
    
    def _calculate_raw_score(
        self,
        issues: List[CorruptionIssue],
        severity_counts: Dict[str, int],
    ) -> float:
        if not issues:
            return 0.0
        
        score = (
            severity_counts.get("low", 0) * 0.1 +
            severity_counts.get("medium", 0) * 0.25 +
            severity_counts.get("high", 0) * 0.4 +
            severity_counts.get("critical", 0) * 0.6
        )
        
        return min(1.0, score)
    
    def _calibrate_confidence(
        self,
        issues: List[CorruptionIssue],
        severity_counts: Dict[str, int],
        max_severity: str,
        raw_score: float,
    ) -> Tuple[float, Dict[str, Any]]:
        if not issues:
            return 0.0, {
                "issue_count": 0,
                "severity_counts": severity_counts,
                "max_severity": "none",
                "raw_score": 0.0,
                "confidence_scaling": self.confidence_scaling,
            }
        
        severity_weight = {
            "low": 0.4,
            "medium": 0.6,
            "high": 0.8,
            "critical": 0.95,
        }.get(max_severity, 0.5)
        
        issue_types = set(i.issue_type for i in issues)
        diversity_factor = min(1.0, len(issue_types) / 4)
        
        issue_factor = min(0.3, len(issues) * 0.05)
        
        base_confidence = (
            severity_weight * 0.40 +
            raw_score * 0.30 +
            diversity_factor * 0.15 +
            issue_factor
        )
        
        calibrated = min(0.99, base_confidence * self.confidence_scaling)
        
        calibration_info = {
            "issue_count": len(issues),
            "severity_counts": severity_counts,
            "max_severity": max_severity,
            "severity_weight": severity_weight,
            "diversity_factor": round(diversity_factor, 4),
            "issue_types": list(issue_types),
            "raw_score": round(raw_score, 4),
            "confidence_scaling": self.confidence_scaling,
        }
        
        return round(calibrated, 4), calibration_info
    
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

    # =========================================================================
    # v1.1: Text-based context corruption detection
    # =========================================================================

    def _extract_task_topics(self, task: str) -> List[str]:
        """v1.1: Extract key topics from task description."""
        task_lower = task.lower()
        found_topics = []

        for topic in self.RELATED_TOPICS.keys():
            if topic in task_lower:
                found_topics.append(topic)

        return found_topics

    def _get_expected_related_topics(self, task_topics: List[str]) -> List[str]:
        """v1.1: Get related topics that should be addressed given task topics."""
        related = set()
        for topic in task_topics:
            if topic in self.RELATED_TOPICS:
                related.update(self.RELATED_TOPICS[topic])
        return list(related)

    def _check_narrow_focus_patterns(self, output: str) -> List[tuple]:
        """v1.1: Check for patterns indicating narrow/incomplete focus."""
        found_patterns = []
        output_lower = output.lower()

        for pattern, pattern_type in self.NARROW_FOCUS_PATTERNS:
            if re.search(pattern, output_lower):
                found_patterns.append((pattern_type, pattern))

        return found_patterns

    def _check_comprehensive_patterns(self, output: str) -> bool:
        """v1.1: Check if output shows signs of comprehensive handling."""
        output_lower = output.lower()

        for pattern in self.COMPREHENSIVE_PATTERNS:
            if re.search(pattern, output_lower):
                return True

        return False

    def _check_related_topics_addressed(
        self,
        output: str,
        expected_related: List[str],
    ) -> tuple[List[str], List[str]]:
        """v1.1: Check which related topics are addressed vs missing."""
        output_lower = output.lower()
        addressed = []
        missing = []

        for topic in expected_related:
            # Check if topic or its variants are mentioned
            if topic in output_lower:
                addressed.append(topic)
            else:
                missing.append(topic)

        return addressed, missing

    def detect_from_text(
        self,
        task: str,
        output: str,
        context: Optional[str] = None,
    ) -> CorruptionResult:
        """
        v1.1: Detect context/memory corruption in text-based outputs.

        Checks if the output ignores related context that should be addressed
        given the task description.

        Args:
            task: The task description/instruction
            output: The agent's output text
            context: Optional additional context that was provided

        Returns:
            CorruptionResult with detection status and issues
        """
        issues = []

        # Extract topics from task
        task_topics = self._extract_task_topics(task)

        if not task_topics:
            # No recognized topics, can't verify context handling
            return CorruptionResult(
                detected=False,
                confidence=0.0,
                issues=[],
                issue_count=0,
                max_severity="none",
            )

        # Get expected related topics
        expected_related = self._get_expected_related_topics(task_topics)

        # Check for narrow focus patterns
        narrow_patterns = self._check_narrow_focus_patterns(output)

        # Check for comprehensive handling
        is_comprehensive = self._check_comprehensive_patterns(output)

        # Check which related topics are addressed
        addressed, missing = self._check_related_topics_addressed(output, expected_related)

        # Determine if there's a context corruption issue
        # Issue detected if: narrow focus patterns found + missing related topics + not comprehensive
        if narrow_patterns and missing and not is_comprehensive:
            issues.append(CorruptionIssue(
                issue_type="context_ignored",
                field=",".join(task_topics),
                message=f"Task mentions {task_topics} but output shows narrow focus, missing: {missing[:3]}",
                severity="medium",
            ))

        # Also flag if significant related topics missing without explicit narrow focus
        # (but only if many related topics are expected and most are missing)
        if len(missing) >= 3 and len(missing) > len(addressed) and not is_comprehensive:
            issues.append(CorruptionIssue(
                issue_type="incomplete_context",
                field=",".join(missing[:3]),
                message=f"Related topics not addressed: {missing[:3]}",
                severity="low",
            ))

        # Check context parameter if provided
        if context:
            context_keywords = self._extract_context_keywords(context)
            missing_context = [kw for kw in context_keywords if kw.lower() not in output.lower()]
            if len(missing_context) > len(context_keywords) * 0.7:  # More than 70% missing
                issues.append(CorruptionIssue(
                    issue_type="context_not_used",
                    field="context",
                    message=f"Provided context largely ignored: {missing_context[:3]}",
                    severity="high",
                ))

        # Calculate result
        if not issues:
            return CorruptionResult(
                detected=False,
                confidence=0.0,
                issues=[],
                issue_count=0,
                max_severity="none",
            )

        max_severity = max((self._severity_rank(i.severity) for i in issues), default=0)
        severity_map = {0: "low", 1: "medium", 2: "high", 3: "critical"}

        # Confidence based on number of indicators
        confidence = min(0.9, 0.3 + len(issues) * 0.2 + len(narrow_patterns) * 0.1)

        return CorruptionResult(
            detected=True,
            confidence=round(confidence, 2),
            issues=issues,
            issue_count=len(issues),
            max_severity=severity_map.get(max_severity, "low"),
        )

    def _extract_context_keywords(self, context: str) -> List[str]:
        """v1.1: Extract key terms from context string."""
        # Extract significant words (nouns, technical terms)
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b', context)
        # Filter common words
        stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'will', 'would', 'should', 'could', 'when', 'where', 'what', 'which', 'there', 'their', 'them', 'then', 'than', 'also', 'just', 'only', 'some', 'more', 'other', 'into', 'your', 'about'}
        return [w for w in words if w.lower() not in stopwords][:10]

    def detect(
        self,
        task: str,
        output: str,
        context: Optional[str] = None,
    ) -> CorruptionResult:
        """
        v1.1: Main detection entry point for text-based detection.

        Convenience method that wraps detect_from_text.
        """
        return self.detect_from_text(task, output, context)


corruption_detector = SemanticCorruptionDetector()
