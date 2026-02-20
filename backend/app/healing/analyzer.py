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
        elif "deadlock" in detection_type or "coordination" in detection_type:
            return self._analyze_deadlock(detection, details, trace)
        elif "hallucination" in detection_type:
            return self._analyze_hallucination(detection, details, trace)
        elif "injection" in detection_type:
            return self._analyze_injection(detection, details, trace)
        elif "overflow" in detection_type:
            return self._analyze_overflow(detection, details, trace)
        elif "derailment" in detection_type:
            return self._analyze_derailment(detection, details, trace)
        elif "context" in detection_type and "neglect" in detection_type:
            return self._analyze_context_neglect(detection, details, trace)
        elif "communication" in detection_type:
            return self._analyze_communication(detection, details, trace)
        elif "specification" in detection_type or "spec" in detection_type:
            return self._analyze_specification(detection, details, trace)
        elif "decomposition" in detection_type:
            return self._analyze_decomposition(detection, details, trace)
        elif "workflow" in detection_type:
            return self._analyze_workflow(detection, details, trace)
        elif "withholding" in detection_type:
            return self._analyze_withholding(detection, details, trace)
        elif "completion" in detection_type:
            return self._analyze_completion(detection, details, trace)
        elif "cost" in detection_type or "budget" in detection_type:
            return self._analyze_cost(detection, details, trace)
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
    
    def _analyze_hallucination(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("hallucinated_fields"):
            indicators.append(f"Hallucinated fields: {', '.join(details['hallucinated_fields'][:5])}")
        if details.get("grounding_score") is not None:
            indicators.append(f"Grounding score: {details['grounding_score']:.2f}")
        if details.get("fabricated_facts"):
            indicators.append(f"Fabricated facts: {len(details['fabricated_facts'])}")
        return FailureSignature(
            category=FailureCategory.HALLUCINATION,
            pattern=details.get("hallucination_type", "ungrounded_claim"),
            confidence=detection.get("confidence", 0.7),
            indicators=indicators or ["Hallucinated content detected"],
            root_cause=details.get("message", "Agent generated ungrounded or fabricated content"),
            affected_components=details.get("affected_nodes", []),
        )

    def _analyze_injection(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        attack_type = details.get("attack_type", "unknown")
        indicators.append(f"Attack type: {attack_type}")
        if details.get("matched_patterns"):
            indicators.append(f"Matched patterns: {len(details['matched_patterns'])}")
        severity = details.get("severity", "medium")
        indicators.append(f"Severity: {severity}")
        return FailureSignature(
            category=FailureCategory.INJECTION,
            pattern=attack_type,
            confidence=detection.get("confidence", 0.8),
            indicators=indicators,
            root_cause=details.get("message", "Prompt injection attempt detected in agent input"),
            affected_components=details.get("affected_nodes", []),
        )

    def _analyze_overflow(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("current_tokens"):
            indicators.append(f"Current tokens: {details['current_tokens']}")
        if details.get("context_window"):
            indicators.append(f"Context window: {details['context_window']}")
        if details.get("usage_percent"):
            indicators.append(f"Usage: {details['usage_percent']:.0f}%")
        return FailureSignature(
            category=FailureCategory.CONTEXT_OVERFLOW,
            pattern=details.get("severity", "overflow").lower(),
            confidence=detection.get("confidence", 0.85),
            indicators=indicators or ["Context window approaching limit"],
            root_cause=details.get("message", "Context window exhausted or approaching limit"),
            affected_components=[details.get("node_name", "unknown")],
        )

    def _analyze_derailment(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("deviation_score"):
            indicators.append(f"Deviation score: {details['deviation_score']:.2f}")
        if details.get("original_task"):
            indicators.append(f"Original task: {details['original_task'][:80]}")
        if details.get("current_focus"):
            indicators.append(f"Current focus: {details['current_focus'][:80]}")
        return FailureSignature(
            category=FailureCategory.TASK_DERAILMENT,
            pattern=details.get("derailment_type", "topic_drift"),
            confidence=detection.get("confidence", 0.7),
            indicators=indicators or ["Agent deviated from assigned task"],
            root_cause=details.get("message", "Agent lost focus on the original task"),
            affected_components=details.get("affected_agents", []),
        )

    def _analyze_context_neglect(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("neglected_items"):
            indicators.append(f"Neglected items: {len(details['neglected_items'])}")
        if details.get("context_utilization") is not None:
            indicators.append(f"Context utilization: {details['context_utilization']:.0%}")
        return FailureSignature(
            category=FailureCategory.CONTEXT_NEGLECT,
            pattern=details.get("neglect_type", "context_ignored"),
            confidence=detection.get("confidence", 0.7),
            indicators=indicators or ["Agent ignored provided context"],
            root_cause=details.get("message", "Agent failed to use available context in its response"),
            affected_components=details.get("affected_agents", []),
        )

    def _analyze_communication(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("failed_handoffs"):
            indicators.append(f"Failed handoffs: {len(details['failed_handoffs'])}")
        if details.get("misunderstood_messages"):
            indicators.append(f"Misunderstood messages: {details['misunderstood_messages']}")
        affected = details.get("affected_agents", [])
        if affected:
            indicators.append(f"Agents involved: {', '.join(affected[:3])}")
        return FailureSignature(
            category=FailureCategory.COMMUNICATION_BREAKDOWN,
            pattern=details.get("breakdown_type", "intent_mismatch"),
            confidence=detection.get("confidence", 0.75),
            indicators=indicators or ["Inter-agent communication failed"],
            root_cause=details.get("message", "Agents failed to communicate effectively"),
            affected_components=affected,
        )

    def _analyze_specification(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("missing_fields"):
            indicators.append(f"Missing fields: {', '.join(details['missing_fields'][:5])}")
        if details.get("requirement_coverage") is not None:
            indicators.append(f"Coverage: {details['requirement_coverage']:.0%}")
        return FailureSignature(
            category=FailureCategory.SPECIFICATION_MISMATCH,
            pattern=details.get("mismatch_type", "scope_drift"),
            confidence=detection.get("confidence", 0.75),
            indicators=indicators or ["Output doesn't match specification"],
            root_cause=details.get("message", "Agent output deviated from specification"),
            affected_components=details.get("affected_nodes", []),
        )

    def _analyze_decomposition(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("subtask_count"):
            indicators.append(f"Subtask count: {details['subtask_count']}")
        if details.get("coverage_score") is not None:
            indicators.append(f"Coverage: {details['coverage_score']:.0%}")
        if details.get("problematic_subtasks"):
            indicators.append(f"Problematic: {', '.join(details['problematic_subtasks'][:3])}")
        return FailureSignature(
            category=FailureCategory.POOR_DECOMPOSITION,
            pattern=details.get("decomposition_type", "imbalanced"),
            confidence=detection.get("confidence", 0.7),
            indicators=indicators or ["Task was poorly decomposed"],
            root_cause=details.get("message", "Task breakdown was incomplete or imbalanced"),
            affected_components=details.get("affected_agents", []),
        )

    def _analyze_workflow(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("failed_steps"):
            indicators.append(f"Failed steps: {len(details['failed_steps'])}")
        if details.get("missing_error_handlers"):
            indicators.append(f"Missing error handlers: {details['missing_error_handlers']}")
        if details.get("problematic_nodes"):
            indicators.append(f"Problem nodes: {', '.join(details['problematic_nodes'][:3])}")
        return FailureSignature(
            category=FailureCategory.FLAWED_WORKFLOW,
            pattern=details.get("workflow_issue_type", "execution_error"),
            confidence=detection.get("confidence", 0.75),
            indicators=indicators or ["Workflow execution issues detected"],
            root_cause=details.get("message", "Workflow has structural or execution flaws"),
            affected_components=details.get("problematic_nodes", []),
        )

    def _analyze_withholding(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("withheld_items"):
            indicators.append(f"Withheld items: {len(details['withheld_items'])}")
        if details.get("completeness_score") is not None:
            indicators.append(f"Completeness: {details['completeness_score']:.0%}")
        return FailureSignature(
            category=FailureCategory.INFORMATION_WITHHOLDING,
            pattern=details.get("withholding_type", "selective_reporting"),
            confidence=detection.get("confidence", 0.7),
            indicators=indicators or ["Agent withheld information"],
            root_cause=details.get("message", "Agent omitted important information from its response"),
            affected_components=details.get("affected_agents", []),
        )

    def _analyze_completion(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        completion_type = details.get("completion_type", "premature")
        indicators.append(f"Type: {completion_type}")
        if details.get("quality_score") is not None:
            indicators.append(f"Quality score: {details['quality_score']:.2f}")
        if details.get("criteria_met") is not None and details.get("criteria_total") is not None:
            indicators.append(f"Criteria: {details['criteria_met']}/{details['criteria_total']}")
        return FailureSignature(
            category=FailureCategory.COMPLETION_MISJUDGMENT,
            pattern=completion_type,
            confidence=detection.get("confidence", 0.7),
            indicators=indicators,
            root_cause=details.get("message", "Agent declared task complete prematurely"),
            affected_components=details.get("affected_agents", []),
        )

    def _analyze_cost(
        self, detection: Dict[str, Any], details: Dict[str, Any], trace: Optional[Dict[str, Any]],
    ) -> FailureSignature:
        indicators = []
        if details.get("total_cost"):
            indicators.append(f"Total cost: ${details['total_cost']:.4f}")
        if details.get("budget_limit"):
            indicators.append(f"Budget: ${details['budget_limit']:.4f}")
        if details.get("token_count"):
            indicators.append(f"Tokens: {details['token_count']}")
        return FailureSignature(
            category=FailureCategory.COST_OVERRUN,
            pattern=details.get("cost_type", "budget_exceeded"),
            confidence=detection.get("confidence", 0.9),
            indicators=indicators or ["Cost budget exceeded"],
            root_cause=details.get("message", "Workflow execution exceeded cost budget"),
            affected_components=[],
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
