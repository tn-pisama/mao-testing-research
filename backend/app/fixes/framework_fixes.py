"""Fix generators for framework-specific detection types (OpenClaw, Dify, LangGraph)."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class OpenClawFixGenerator(BaseFixGenerator):
    """Generates fixes for OpenClaw framework-specific detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type.startswith("openclaw_")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        det_type = detection.get("detection_type", "")
        det_id = detection.get("id", "")

        if "session_loop" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.CIRCUIT_BREAKER,
                confidence=FixConfidence.HIGH,
                title="Add loop breaker to session",
                description="Add max iteration guard and duplicate tool call detection to the agent session.",
                rationale="Session is repeating identical tool calls without progress.",
            ))
        elif "tool_abuse" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.RETRY_LIMIT,
                confidence=FixConfidence.MEDIUM,
                title="Add tool rate limiting",
                description="Configure per-session tool call limits and restrict sensitive tool access.",
                rationale="Agent is making excessive or dangerous tool calls.",
            ))
        elif "elevated_risk" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.PERMISSION_GATE,
                confidence=FixConfidence.HIGH,
                title="Restrict elevated mode operations",
                description="Add operation whitelist for elevated mode and require explicit approval for risky actions.",
                rationale="Elevated mode operations include potentially dangerous actions.",
            ))
        elif "spawn_chain" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.CIRCUIT_BREAKER,
                confidence=FixConfidence.MEDIUM,
                title="Limit spawn chain depth",
                description="Set maximum spawn depth to 3 and prevent circular session references.",
                rationale="Session spawning has exceeded safe depth or contains circular references.",
            ))
        elif "channel_mismatch" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.OUTPUT_CONSTRAINT,
                confidence=FixConfidence.HIGH,
                title="Add channel-aware formatting",
                description="Configure agent to adapt message format based on channel constraints.",
                rationale="Response format is inappropriate for the communication channel.",
            ))
        elif "sandbox_escape" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.SAFETY_BOUNDARY,
                confidence=FixConfidence.HIGH,
                title="Enforce sandbox boundaries",
                description="Block restricted tool calls when sandbox is enabled and add violation logging.",
                rationale="Agent performed operations that violate sandbox restrictions.",
            ))

        return fixes


class DifyFixGenerator(BaseFixGenerator):
    """Generates fixes for Dify framework-specific detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type.startswith("dify_")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        det_type = detection.get("detection_type", "")
        det_id = detection.get("id", "")

        if "rag_poisoning" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.INPUT_FILTERING,
                confidence=FixConfidence.HIGH,
                title="Add RAG input sanitization",
                description="Scan retrieved documents for prompt injection patterns before passing to LLM.",
                rationale="Knowledge base documents contain embedded prompt injection attempts.",
            ))
        elif "iteration_escape" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.CIRCUIT_BREAKER,
                confidence=FixConfidence.HIGH,
                title="Set iteration bounds",
                description="Configure max iteration count and add explicit break conditions.",
                rationale="Iteration/loop node exceeding expected bounds without termination.",
            ))
        elif "model_fallback" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.PROGRESS_MONITORING,
                confidence=FixConfidence.MEDIUM,
                title="Add explicit fallback logging",
                description="Configure model fallback to log when a different model is used and alert on capability degradation.",
                rationale="LLM node silently using a different model than configured.",
            ))
        elif "variable_leak" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.INPUT_SANITIZATION,
                confidence=FixConfidence.HIGH,
                title="Add output sanitization",
                description="Scan node outputs for sensitive data patterns and redact before passing downstream.",
                rationale="Sensitive data (API keys, credentials) detected in node outputs.",
            ))
        elif "classifier_drift" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.CONFIDENCE_CALIBRATION,
                confidence=FixConfidence.MEDIUM,
                title="Recalibrate classifier",
                description="Update question classifier categories and confidence thresholds.",
                rationale="Classifier producing low-confidence or incorrect categorizations.",
            ))
        elif "tool_schema_mismatch" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.SCHEMA_ENFORCEMENT,
                confidence=FixConfidence.HIGH,
                title="Fix tool schema alignment",
                description="Update tool node configuration to match declared input/output schema.",
                rationale="Tool inputs/outputs violating declared schema.",
            ))

        return fixes


class LangGraphFixGenerator(BaseFixGenerator):
    """Generates fixes for LangGraph framework-specific detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type.startswith("langgraph_")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        det_type = detection.get("detection_type", "")
        det_id = detection.get("id", "")

        if "recursion" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.CIRCUIT_BREAKER,
                confidence=FixConfidence.HIGH,
                title="Add recursion guard",
                description="Set explicit recursion_limit and add node-level cycle detection.",
                rationale="Graph execution hitting or approaching GRAPH_RECURSION_LIMIT.",
            ))
        elif "state_corruption" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.STATE_VALIDATION,
                confidence=FixConfidence.HIGH,
                title="Add state validation",
                description="Add state channel type validators and immutability checks between supersteps.",
                rationale="State mutations violating type annotations or invariants.",
            ))
        elif "edge_misroute" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.STEP_VALIDATOR,
                confidence=FixConfidence.MEDIUM,
                title="Fix conditional edge routing",
                description="Review and correct conditional edge conditions to ensure proper routing.",
                rationale="Conditional edges routing to wrong nodes or creating dead-end paths.",
            ))
        elif "tool_failure" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.CIRCUIT_BREAKER,
                confidence=FixConfidence.HIGH,
                title="Add tool error handling",
                description="Wrap tool nodes with try/except and add retry/fallback patterns.",
                rationale="Tool node failures propagating without proper error handling.",
            ))
        elif "parallel_sync" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.ASYNC_HANDOFF,
                confidence=FixConfidence.MEDIUM,
                title="Add synchronization barriers",
                description="Add state aggregation node after parallel branches and resolve write conflicts.",
                rationale="Parallel supersteps causing state write conflicts or missing synchronization.",
            ))
        elif "checkpoint_corruption" in det_type:
            fixes.append(self._create_suggestion(
                detection_id=det_id,
                detection_type=det_type,
                fix_type=FixType.CHECKPOINT_RECOVERY,
                confidence=FixConfidence.HIGH,
                title="Add checkpoint validation",
                description="Validate checkpoint integrity on creation and add recovery for corrupted checkpoints.",
                rationale="Checkpoint data inconsistent or corrupted.",
            ))

        return fixes
