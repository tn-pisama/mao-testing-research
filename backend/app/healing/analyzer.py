"""Failure analyzer for diagnosing root causes."""

from typing import Dict, Any, List, Optional
import re
from .models import FailureSignature, FailureCategory


class FailureAnalyzer:
    """Analyzes detections to diagnose root causes and determine fix strategies."""
    
    LOOP_PATTERNS = {
        "state_repetition": r"state_hash.*repeated (\d+) times",
        "node_cycle": r"node sequence.*\[(.*?)\].*cycles",
        "iteration_exceeded": r"iteration[_\s]*(count|limit).*exceeded",
        "recursion_limit": r"recursion.*limit.*hit",
    }
    
    CORRUPTION_PATTERNS = {
        "null_injection": r"(null|None|undefined).*injected",
        "type_mismatch": r"expected.*type.*got",
        "hash_mismatch": r"hash.*mismatch|checksum.*failed",
        "data_loss": r"data.*lost|original.*destroyed",
    }
    
    DRIFT_PATTERNS = {
        "tone_mismatch": r"tone.*mismatch|style.*inconsistent",
        "persona_violation": r"persona.*violated|character.*break",
        "output_format": r"output.*format.*unexpected",
        "slang_detected": r"slang.*detected|informal.*language",
    }
    
    def analyze(self, detection: Dict[str, Any], trace: Optional[Dict[str, Any]] = None) -> FailureSignature:
        """Analyze a detection to produce a failure signature."""
        detection_type = detection.get("detection_type", "").lower()
        details = detection.get("details", {})
        
        if "loop" in detection_type or "infinite" in detection_type:
            return self._analyze_loop(detection, details, trace)
        elif "corruption" in detection_type or "state" in detection_type:
            return self._analyze_corruption(detection, details, trace)
        elif "drift" in detection_type or "persona" in detection_type:
            return self._analyze_drift(detection, details, trace)
        elif "timeout" in detection_type:
            return self._analyze_timeout(detection, details, trace)
        elif "deadlock" in detection_type:
            return self._analyze_deadlock(detection, details, trace)
        else:
            return self._analyze_generic(detection, details, trace)
    
    def _analyze_loop(
        self,
        detection: Dict[str, Any],
        details: Dict[str, Any],
        trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        """Analyze infinite loop detection."""
        indicators = []
        pattern = "unknown"
        root_cause = None
        affected = details.get("affected_agents", [])
        
        loop_length = details.get("loop_length", 0)
        if loop_length > 0:
            indicators.append(f"Loop length: {loop_length} iterations")
        
        method = detection.get("method", "")
        if method == "structural":
            pattern = "structural_cycle"
            indicators.append("Detected via graph structure analysis")
            root_cause = "Agent routing always returns to same node without exit condition"
        elif method == "state_hash":
            pattern = "state_repetition"
            indicators.append("Detected via repeated state hashes")
            root_cause = "Agent produces identical state repeatedly without progress"
        elif method == "iteration_count":
            pattern = "iteration_exceeded"
            indicators.append(f"Iteration count exceeded threshold")
            root_cause = "No termination condition or condition never met"
        
        if len(affected) >= 2:
            pattern = "multi_agent_ping_pong"
            indicators.append(f"Multiple agents involved: {', '.join(affected[:3])}")
            root_cause = "Agents delegating to each other in a cycle"
        
        message = details.get("message", "")
        for name, regex in self.LOOP_PATTERNS.items():
            if re.search(regex, message, re.IGNORECASE):
                indicators.append(f"Pattern match: {name}")
        
        return FailureSignature(
            category=FailureCategory.INFINITE_LOOP,
            pattern=pattern,
            confidence=detection.get("confidence", 0.8),
            indicators=indicators,
            root_cause=root_cause,
            affected_components=affected,
        )
    
    def _analyze_corruption(
        self,
        detection: Dict[str, Any],
        details: Dict[str, Any],
        trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        """Analyze state corruption detection."""
        indicators = []
        pattern = "unknown"
        root_cause = None
        affected = []
        
        corrupted_fields = details.get("corrupted_fields", [])
        if corrupted_fields:
            indicators.append(f"Corrupted fields: {', '.join(corrupted_fields[:5])}")
            affected = corrupted_fields
        
        if details.get("null_injection"):
            pattern = "null_injection"
            indicators.append("Null values injected into state")
            root_cause = "Node returning null/None where object expected"
        elif details.get("type_error"):
            pattern = "type_mismatch"
            indicators.append("Type mismatch in state")
            root_cause = "Node returning wrong data type"
        elif details.get("data_loss"):
            pattern = "data_loss"
            indicators.append("Original data was destroyed")
            root_cause = "Node overwrites state instead of merging"
        else:
            pattern = "generic_corruption"
            root_cause = "State modified unexpectedly between nodes"
        
        message = details.get("message", "")
        for name, regex in self.CORRUPTION_PATTERNS.items():
            if re.search(regex, message, re.IGNORECASE):
                indicators.append(f"Pattern match: {name}")
        
        return FailureSignature(
            category=FailureCategory.STATE_CORRUPTION,
            pattern=pattern,
            confidence=detection.get("confidence", 0.75),
            indicators=indicators,
            root_cause=root_cause,
            affected_components=affected,
        )
    
    def _analyze_drift(
        self,
        detection: Dict[str, Any],
        details: Dict[str, Any],
        trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        """Analyze persona drift detection."""
        indicators = []
        pattern = "unknown"
        root_cause = None
        affected = []
        
        drift_score = details.get("drift_score", 0)
        if drift_score > 0:
            indicators.append(f"Drift score: {drift_score:.2f}")
        
        expected_tone = details.get("expected_tone", "professional")
        actual_tone = details.get("actual_tone", "unknown")
        if expected_tone != actual_tone:
            pattern = "tone_mismatch"
            indicators.append(f"Expected: {expected_tone}, Actual: {actual_tone}")
            root_cause = f"Agent output style changed from {expected_tone} to {actual_tone}"
        
        if details.get("emojis_detected"):
            indicators.append("Emojis detected in professional context")
        if details.get("slang_detected"):
            indicators.append("Informal slang detected")
            pattern = "informal_language"
        
        affected_agent = details.get("agent_name") or details.get("node_name")
        if affected_agent:
            affected = [affected_agent]
        
        message = details.get("message", "")
        for name, regex in self.DRIFT_PATTERNS.items():
            if re.search(regex, message, re.IGNORECASE):
                indicators.append(f"Pattern match: {name}")
        
        return FailureSignature(
            category=FailureCategory.PERSONA_DRIFT,
            pattern=pattern,
            confidence=detection.get("confidence", 0.7),
            indicators=indicators,
            root_cause=root_cause or "Agent deviated from assigned persona/style",
            affected_components=affected,
        )
    
    def _analyze_timeout(
        self,
        detection: Dict[str, Any],
        details: Dict[str, Any],
        trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        """Analyze timeout detection."""
        return FailureSignature(
            category=FailureCategory.TIMEOUT,
            pattern="execution_timeout",
            confidence=detection.get("confidence", 0.9),
            indicators=[
                f"Timeout after {details.get('timeout_ms', 0)}ms",
                f"Node: {details.get('node_name', 'unknown')}",
            ],
            root_cause="Agent execution exceeded time limit",
            affected_components=[details.get("node_name", "unknown")],
        )
    
    def _analyze_deadlock(
        self,
        detection: Dict[str, Any],
        details: Dict[str, Any],
        trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        """Analyze coordination deadlock detection."""
        return FailureSignature(
            category=FailureCategory.COORDINATION_DEADLOCK,
            pattern="resource_deadlock",
            confidence=detection.get("confidence", 0.85),
            indicators=[
                f"Agents waiting: {details.get('waiting_agents', [])}",
                f"Resources held: {details.get('held_resources', [])}",
            ],
            root_cause="Agents waiting on each other for resources",
            affected_components=details.get("waiting_agents", []),
        )
    
    def _analyze_generic(
        self,
        detection: Dict[str, Any],
        details: Dict[str, Any],
        trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        """Analyze generic/unknown detection type."""
        return FailureSignature(
            category=FailureCategory.API_FAILURE,
            pattern="generic_failure",
            confidence=detection.get("confidence", 0.5),
            indicators=[f"Detection type: {detection.get('detection_type')}"],
            root_cause=details.get("message", "Unknown failure"),
            affected_components=[],
        )
