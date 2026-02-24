"""Fix verification orchestrator for proving fixes resolve detected failures."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

from .models import AppliedFix, FailureCategory, HealingConfig, ValidationResult
from .validator import FixValidator

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of fix verification."""

    passed: bool
    level: int  # 1 = config only, 2 = execution-based
    before_confidence: float  # Original detection confidence (0-1)
    after_confidence: float  # Post-fix detection confidence (0-1)
    config_checks: List[ValidationResult] = field(default_factory=list)
    execution_result: Optional[Dict[str, Any]] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    verified_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "level": self.level,
            "before_confidence": self.before_confidence,
            "after_confidence": self.after_confidence,
            "confidence_reduction": round(
                self.before_confidence - self.after_confidence, 4
            ),
            "config_checks": [
                {
                    "success": c.success,
                    "validation_type": c.validation_type,
                    "details": c.details,
                    "error_message": c.error_message,
                }
                for c in self.config_checks
            ],
            "execution_result": self.execution_result,
            "details": self.details,
            "error": self.error,
            "verified_at": self.verified_at,
        }


def _detection_type_to_category(detection_type: str) -> FailureCategory:
    """Map detection_type string to FailureCategory enum."""
    mapping = {
        "infinite_loop": FailureCategory.INFINITE_LOOP,
        "state_corruption": FailureCategory.STATE_CORRUPTION,
        "persona_drift": FailureCategory.PERSONA_DRIFT,
        "coordination_failure": FailureCategory.COORDINATION_DEADLOCK,
        "coordination_deadlock": FailureCategory.COORDINATION_DEADLOCK,
        "timeout": FailureCategory.TIMEOUT,
        "rate_limit": FailureCategory.RATE_LIMIT,
        "hallucination": FailureCategory.HALLUCINATION,
        "injection": FailureCategory.INJECTION,
        "overflow": FailureCategory.CONTEXT_OVERFLOW,
        "context_overflow": FailureCategory.CONTEXT_OVERFLOW,
        "task_derailment": FailureCategory.TASK_DERAILMENT,
        "derailment": FailureCategory.TASK_DERAILMENT,
        "context_neglect": FailureCategory.CONTEXT_NEGLECT,
        "communication_breakdown": FailureCategory.COMMUNICATION_BREAKDOWN,
        "communication": FailureCategory.COMMUNICATION_BREAKDOWN,
        "specification_mismatch": FailureCategory.SPECIFICATION_MISMATCH,
        "specification": FailureCategory.SPECIFICATION_MISMATCH,
        "poor_decomposition": FailureCategory.POOR_DECOMPOSITION,
        "decomposition": FailureCategory.POOR_DECOMPOSITION,
        "flawed_workflow": FailureCategory.FLAWED_WORKFLOW,
        "workflow": FailureCategory.FLAWED_WORKFLOW,
        "withholding": FailureCategory.INFORMATION_WITHHOLDING,
        "information_withholding": FailureCategory.INFORMATION_WITHHOLDING,
        "completion": FailureCategory.COMPLETION_MISJUDGMENT,
        "completion_misjudgment": FailureCategory.COMPLETION_MISJUDGMENT,
        "cost": FailureCategory.COST_OVERRUN,
        "cost_overrun": FailureCategory.COST_OVERRUN,
    }
    return mapping.get(detection_type, FailureCategory.API_FAILURE)


class VerificationOrchestrator:
    """Orchestrates fix verification at two levels.

    Level 1 (Config): Re-runs validators against the fixed workflow config.
    Level 2 (Execution): Triggers a real n8n execution, ingests the trace,
                          and re-runs detection to compare confidence.
    """

    def __init__(
        self,
        verification_timeout: float = 60.0,
        config: Optional[HealingConfig] = None,
    ):
        self._validator = FixValidator()
        self._config = config or HealingConfig()
        self._verification_timeout = verification_timeout or self._config.verification_timeout

    async def verify_level1(
        self,
        detection_type: str,
        original_confidence: float,
        original_state: Dict[str, Any],
        applied_fixes: Dict[str, Any],
    ) -> VerificationResult:
        """Level 1: Config-based verification.

        Checks that the fix introduces protective mechanisms
        (e.g., max_iterations, circuit_breaker) and doesn't remove
        existing nodes/connections.

        Args:
            detection_type: The type of detection (e.g., "infinite_loop")
            original_confidence: Original detection confidence (0-100 int or 0-1 float)
            original_state: Workflow state before fix
            applied_fixes: Dict with fix details including diff
        """
        # Normalize confidence to 0-1 range (handle None from nullable DB column)
        if original_confidence is None:
            original_confidence = 0.0
        before = original_confidence / 100.0 if original_confidence > 1 else original_confidence

        category = _detection_type_to_category(detection_type)

        # Build AppliedFix from the healing record data
        fix_data = applied_fixes.get("fix_applied", {})
        applied_fix = AppliedFix(
            fix_id=fix_data.get("id", "unknown"),
            fix_type=fix_data.get("fix_type", detection_type),
            applied_at=datetime.utcnow(),
            target_component=applied_fixes.get("workflow_id", "unknown"),
            original_state=original_state,
            modified_state=_reconstruct_modified_state(original_state, applied_fixes),
        )

        # Run existing validators
        config_checks = await self._validator.validate(
            applied_fix, category
        )

        all_passed = all(c.success for c in config_checks)

        # Estimate post-fix confidence based on config checks
        # If protection mechanisms are present, confidence should drop significantly
        after = 0.0 if all_passed else before * self._config.confidence_fail_factor

        return VerificationResult(
            passed=all_passed,
            level=1,
            before_confidence=before,
            after_confidence=after,
            config_checks=config_checks,
            details={
                "detection_type": detection_type,
                "checks_run": len(config_checks),
                "checks_passed": sum(1 for c in config_checks if c.success),
            },
            verified_at=datetime.utcnow().isoformat(),
        )

    async def verify_level2(
        self,
        detection_type: str,
        original_confidence: float,
        original_state: Dict[str, Any],
        applied_fixes: Dict[str, Any],
        n8n_client,
        workflow_id: str,
        loop_detector=None,
    ) -> VerificationResult:
        """Level 2: Execution-based verification.

        Temporarily activates the staged workflow, runs it, captures the
        execution trace, and re-runs detection to compare.

        Args:
            detection_type: The type of detection
            original_confidence: Original detection confidence
            original_state: Workflow state before fix
            applied_fixes: Dict with fix details
            n8n_client: Active N8nApiClient instance
            workflow_id: n8n workflow ID
            loop_detector: Optional detector instance for re-detection
        """
        # First run Level 1
        level1 = await self.verify_level1(
            detection_type, original_confidence, original_state, applied_fixes
        )

        before = level1.before_confidence
        execution_result = None
        after = before  # Default: no improvement

        try:
            # Temporarily activate for test execution
            await n8n_client.activate_workflow(workflow_id)

            try:
                # Trigger test execution
                run_result = await n8n_client.run_workflow(workflow_id)
                execution_id = run_result.get("executionId") or run_result.get("id")

                if execution_id:
                    # Wait for completion
                    execution = await n8n_client.wait_for_execution(
                        str(execution_id), timeout=self._verification_timeout
                    )

                    execution_status = execution.get("status", "unknown")
                    finished = execution.get("finished", False)

                    execution_result = {
                        "execution_id": str(execution_id),
                        "status": execution_status,
                        "finished": finished,
                    }

                    # If the workflow completed without error, the fix is working
                    if execution_status == "success" or finished:
                        # Re-run detection on the execution data
                        redetect = self._get_redetector(detection_type, loop_detector)
                        if redetect:
                            after = await redetect(execution)
                        else:
                            # Workflow completed successfully = fix likely working
                            after = 0.0
                    elif execution_status == "error":
                        # Workflow errored - check if it's a controlled termination
                        error_msg = execution.get("data", {}).get(
                            "resultData", {}
                        ).get("error", {}).get("message", "")
                        if "max iterations" in error_msg.lower() or "circuit breaker" in error_msg.lower():
                            # Fix correctly terminated the loop
                            after = 0.0
                            execution_result["controlled_termination"] = True
                        else:
                            after = before * self._config.partial_improvement_factor
                else:
                    execution_result = {"error": "No execution ID returned"}

            finally:
                # Always deactivate (restore staged state)
                await n8n_client.deactivate_workflow(workflow_id)

        except Exception as e:
            logger.error(f"Level 2 verification failed: {e}")
            return VerificationResult(
                passed=level1.passed,  # Fall back to Level 1 result
                level=2,
                before_confidence=before,
                after_confidence=level1.after_confidence,
                config_checks=level1.config_checks,
                execution_result={"error": str(e)},
                details={
                    **level1.details,
                    "level2_error": str(e),
                    "fell_back_to_level1": True,
                },
                error=f"Execution verification failed: {e}",
                verified_at=datetime.utcnow().isoformat(),
            )

        passed = level1.passed and after < before * self._config.improvement_threshold
        return VerificationResult(
            passed=passed,
            level=2,
            before_confidence=before,
            after_confidence=after,
            config_checks=level1.config_checks,
            execution_result=execution_result,
            details={
                **level1.details,
                "execution_completed": execution_result is not None,
            },
            verified_at=datetime.utcnow().isoformat(),
        )

    def _get_redetector(self, detection_type: str, loop_detector=None):
        """Return the appropriate re-detection coroutine for a detection type.

        Returns a callable(execution) -> float, or None for unsupported types.
        """
        if detection_type == "infinite_loop" and loop_detector:
            return lambda execution: self._redetect_loop(execution, loop_detector)
        redetectors = {
            "context_overflow": self._redetect_overflow,
            "overflow": self._redetect_overflow,
            "hallucination": self._redetect_hallucination,
            "injection": self._redetect_injection,
            "state_corruption": self._redetect_corruption,
            "coordination_deadlock": self._redetect_coordination,
            "coordination_failure": self._redetect_coordination,
        }
        return redetectors.get(detection_type)

    async def _redetect_loop(self, execution: Dict[str, Any], loop_detector) -> float:
        """Re-run loop detection on execution data and return new confidence."""
        from app.detection.loop import StateSnapshot

        # Extract node execution data from the n8n execution result
        result_data = execution.get("data", {}).get("resultData", {})
        run_data = result_data.get("runData", {})

        states = []
        seq = 0
        for node_name, node_runs in run_data.items():
            for run in node_runs:
                output_data = run.get("data", {}).get("main", [[]])
                state_content = str(output_data)
                states.append(StateSnapshot(
                    agent_id=node_name,
                    state_delta={"output": output_data},
                    content=state_content,
                    sequence_num=seq,
                ))
                seq += 1

        if not states or len(states) < 3:
            return 0.0  # Not enough data to detect a loop

        result = loop_detector.detect_loop(states)
        return result.confidence if result.detected else 0.0


    async def _redetect_overflow(self, execution: Dict[str, Any]) -> float:
        """Re-run context overflow detection on execution data."""
        from app.detection.overflow import ContextOverflowDetector

        result_data = execution.get("data", {}).get("resultData", {})
        run_data = result_data.get("runData", {})

        total_tokens = 0
        for _node_name, node_runs in run_data.items():
            for run in node_runs:
                data = run.get("data", {}).get("main", [[]])
                for items in data:
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                json_data = item.get("json", {})
                                total_tokens += json_data.get("tokens_input", 0)
                                total_tokens += json_data.get("tokens_output", 0)
                                total_tokens += json_data.get("usage", {}).get("total_tokens", 0)

        if total_tokens == 0:
            return 0.0

        detector = ContextOverflowDetector()
        result = detector.detect(total_tokens=total_tokens)
        return result.confidence if result.detected else 0.0

    async def _redetect_hallucination(self, execution: Dict[str, Any]) -> float:
        """Re-run hallucination detection on execution output."""
        from app.detection.hallucination import HallucinationDetector

        result_data = execution.get("data", {}).get("resultData", {})
        run_data = result_data.get("runData", {})

        outputs = []
        for _node_name, node_runs in run_data.items():
            for run in node_runs:
                data = run.get("data", {}).get("main", [[]])
                for items in data:
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                json_data = item.get("json", {})
                                output = json_data.get("output", json_data.get("text", ""))
                                if output:
                                    outputs.append(str(output))

        if not outputs:
            return 0.0

        detector = HallucinationDetector()
        combined = "\n".join(outputs)
        result = detector.detect(agent_output=combined)
        return result.confidence if result.detected else 0.0

    async def _redetect_injection(self, execution: Dict[str, Any]) -> float:
        """Re-run injection detection on execution prompts."""
        from app.detection.injection import InjectionDetector

        result_data = execution.get("data", {}).get("resultData", {})
        run_data = result_data.get("runData", {})

        prompts = []
        for _node_name, node_runs in run_data.items():
            for run in node_runs:
                data = run.get("data", {}).get("main", [[]])
                for items in data:
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                json_data = item.get("json", {})
                                prompt = json_data.get("prompt", json_data.get("input", ""))
                                if prompt:
                                    prompts.append(str(prompt))

        if not prompts:
            return 0.0

        detector = InjectionDetector()
        combined = "\n".join(prompts)
        result = detector.detect(text=combined)
        return result.confidence if result.detected else 0.0

    async def _redetect_corruption(self, execution: Dict[str, Any]) -> float:
        """Re-run state corruption detection on execution data."""
        from app.detection.corruption import SemanticCorruptionDetector

        result_data = execution.get("data", {}).get("resultData", {})
        run_data = result_data.get("runData", {})

        states = []
        for node_name, node_runs in run_data.items():
            for run in node_runs:
                data = run.get("data", {}).get("main", [[]])
                states.append({
                    "agent_id": node_name,
                    "state": data,
                })

        if len(states) < 2:
            return 0.0

        detector = SemanticCorruptionDetector()
        result = detector.detect(states=states)
        return result.confidence if result.detected else 0.0

    async def _redetect_coordination(self, execution: Dict[str, Any]) -> float:
        """Re-run coordination/deadlock detection on execution data."""
        from app.detection.coordination import CoordinationAnalyzer

        result_data = execution.get("data", {}).get("resultData", {})
        run_data = result_data.get("runData", {})

        messages = []
        seq = 0
        for node_name, node_runs in run_data.items():
            for run in node_runs:
                data = run.get("data", {}).get("main", [[]])
                messages.append({
                    "agent_id": node_name,
                    "content": str(data),
                    "sequence": seq,
                })
                seq += 1

        if len(messages) < 2:
            return 0.0

        analyzer = CoordinationAnalyzer()
        result = analyzer.detect(messages=messages)
        return result.confidence if result.detected else 0.0


def _reconstruct_modified_state(
    original_state: Dict[str, Any],
    applied_fixes: Dict[str, Any],
) -> Dict[str, Any]:
    """Reconstruct modified workflow state from original + diff.

    Re-applies the same fix transformation that was used when staging,
    using the _apply_fix_to_workflow function from the healing API.
    """
    import copy
    modified = copy.deepcopy(original_state)

    fix_applied = applied_fixes.get("fix_applied", {})
    detection_type = fix_applied.get("fix_type", "")

    # Map fix_type back to detection_type for _apply_fix_to_workflow
    fix_to_detection = {
        "retry_limit": "infinite_loop",
        "circuit_breaker": "infinite_loop",
        "exponential_backoff": "infinite_loop",
        "conversation_terminator": "infinite_loop",
        "state_validation": "state_corruption",
        "persona_reinforcement": "persona_drift",
        "deadlock_prevention": "coordination_failure",
    }
    detection_type = fix_to_detection.get(detection_type, detection_type)

    try:
        from app.api.v1.healing import _apply_fix_to_workflow
        modified = _apply_fix_to_workflow(modified, fix_applied, detection_type)
    except ImportError:
        # Fallback: apply basic fix settings manually
        settings = modified.get("settings", {})
        settings.setdefault("executionTimeout", 300)
        settings.setdefault("max_iterations", 100)
        modified["settings"] = settings

    return modified
