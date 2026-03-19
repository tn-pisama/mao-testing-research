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
        "convergence": FailureCategory.CONVERGENCE_FAILURE,
        "convergence_failure": FailureCategory.CONVERGENCE_FAILURE,
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

    async def verify_level2_generic(
        self,
        detection_type: str,
        original_confidence: float,
        original_state: Dict[str, Any],
        applied_fixes: Dict[str, Any],
        framework: str,
        client: Any,
        entity_id: str,
    ) -> VerificationResult:
        """Level 2: Execution-based verification for any framework.

        Creates a test execution using the framework client, waits for
        completion, and checks whether the execution succeeds without
        triggering the same failure.

        Args:
            detection_type: The type of detection
            original_confidence: Original detection confidence
            original_state: Config state before fix
            applied_fixes: Dict with fix details
            framework: Framework name (langgraph, dify, openclaw)
            client: Framework API client
            entity_id: Entity ID (assistant_id, app_id, agent_id)
        """
        # First run Level 1
        level1 = await self.verify_level1(
            detection_type, original_confidence, original_state, applied_fixes
        )

        before = level1.before_confidence
        execution_result = None
        after = before  # Default: no improvement

        try:
            if framework == "langgraph":
                execution_result, after = await self._verify_langgraph(
                    client, entity_id, before
                )
            elif framework == "dify":
                execution_result, after = await self._verify_dify(
                    client, entity_id, before
                )
            elif framework == "openclaw":
                execution_result, after = await self._verify_openclaw(
                    client, entity_id, before
                )
            else:
                return VerificationResult(
                    passed=level1.passed,
                    level=1,
                    before_confidence=before,
                    after_confidence=level1.after_confidence,
                    config_checks=level1.config_checks,
                    details={**level1.details, "unsupported_framework": framework},
                    verified_at=datetime.utcnow().isoformat(),
                )

        except Exception as e:
            logger.error(f"Level 2 verification failed for {framework}/{entity_id}: {e}")
            return VerificationResult(
                passed=level1.passed,
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
                "framework": framework,
                "execution_completed": execution_result is not None,
            },
            verified_at=datetime.utcnow().isoformat(),
        )

    async def _verify_langgraph(
        self, client: Any, assistant_id: str, before: float,
    ) -> tuple:
        """Run a LangGraph test execution and check results."""
        result = await client.run_graph(
            assistant_id=assistant_id,
            input_data={"messages": [{"role": "user", "content": "test"}]},
            config={"configurable": {"recursion_limit": 25}},
            timeout=self._verification_timeout,
        )

        status = result.get("status", "")
        execution_result = {
            "run_id": result.get("run_id", result.get("id", "")),
            "thread_id": result.get("thread_id", ""),
            "status": status,
        }

        if status == "success":
            after = 0.0
        elif status == "error":
            error_msg = result.get("error", "")
            if "recursion" in str(error_msg).lower() or "circuit" in str(error_msg).lower():
                after = 0.0
                execution_result["controlled_termination"] = True
            else:
                after = before * self._config.partial_improvement_factor
        else:
            after = before * self._config.partial_improvement_factor

        return execution_result, after

    async def _verify_dify(
        self, client: Any, app_id: str, before: float,
    ) -> tuple:
        """Run a Dify test workflow and check results."""
        result = await client.run_and_wait(
            inputs={"query": "test verification"},
            timeout=self._verification_timeout,
        )

        workflow_run = result.get("workflow_run", result)
        status = workflow_run.get("status", "")
        execution_result = {
            "workflow_run_id": workflow_run.get("id", ""),
            "status": status,
        }

        if status == "succeeded":
            after = 0.0
        elif status == "failed":
            error = workflow_run.get("error", "")
            if "iteration" in str(error).lower() or "limit" in str(error).lower():
                after = 0.0
                execution_result["controlled_termination"] = True
            else:
                after = before * self._config.partial_improvement_factor
        else:
            after = before * self._config.partial_improvement_factor

        return execution_result, after

    async def _verify_openclaw(
        self, client: Any, agent_id: str, before: float,
    ) -> tuple:
        """Run an OpenClaw test session and check results."""
        result = await client.run_session(
            agent_id=agent_id,
            message="test verification",
            timeout=self._verification_timeout,
        )

        status = result.get("status", "")
        execution_result = {
            "session_id": result.get("session_id", result.get("id", "")),
            "status": status,
        }

        if status == "completed":
            after = 0.0
        elif status in ("failed", "error"):
            error = result.get("error", "")
            if "loop" in str(error).lower() or "limit" in str(error).lower():
                after = 0.0
                execution_result["controlled_termination"] = True
            else:
                after = before * self._config.partial_improvement_factor
        else:
            after = before * self._config.partial_improvement_factor

        return execution_result, after

    async def verify_level2_langgraph(
        self,
        detection_type: str,
        original_confidence: float,
        original_state: Dict[str, Any],
        applied_fixes: Dict[str, Any],
        langgraph_client: Any,
        assistant_id: str,
    ) -> VerificationResult:
        """Level 2: Execution-based verification for LangGraph with re-detection.

        Runs a test graph execution, then re-runs the appropriate detector
        on the execution result to measure actual confidence reduction.
        """
        level1 = await self.verify_level1(
            detection_type, original_confidence, original_state, applied_fixes
        )

        before = level1.before_confidence
        execution_result = None
        after = before

        try:
            execution_result, after = await self._verify_langgraph(
                langgraph_client, assistant_id, before
            )

            # Re-detect on the execution result if basic verification succeeded
            if after == 0.0 and execution_result:
                redetector = self._get_redetector_for_framework(detection_type, "langgraph")
                if redetector:
                    after = await redetector(execution_result)

        except Exception as e:
            logger.error(f"Level 2 verification failed for langgraph/{assistant_id}: {e}")
            return VerificationResult(
                passed=level1.passed,
                level=2,
                before_confidence=before,
                after_confidence=level1.after_confidence,
                config_checks=level1.config_checks,
                execution_result={"error": str(e)},
                details={**level1.details, "level2_error": str(e), "fell_back_to_level1": True},
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
                "framework": "langgraph",
                "execution_completed": execution_result is not None,
                "redetection_applied": after != before,
            },
            verified_at=datetime.utcnow().isoformat(),
        )

    async def verify_level2_dify(
        self,
        detection_type: str,
        original_confidence: float,
        original_state: Dict[str, Any],
        applied_fixes: Dict[str, Any],
        dify_client: Any,
        app_id: str,
    ) -> VerificationResult:
        """Level 2: Execution-based verification for Dify with re-detection."""
        level1 = await self.verify_level1(
            detection_type, original_confidence, original_state, applied_fixes
        )

        before = level1.before_confidence
        execution_result = None
        after = before

        try:
            execution_result, after = await self._verify_dify(
                dify_client, app_id, before
            )

            if after == 0.0 and execution_result:
                redetector = self._get_redetector_for_framework(detection_type, "dify")
                if redetector:
                    after = await redetector(execution_result)

        except Exception as e:
            logger.error(f"Level 2 verification failed for dify/{app_id}: {e}")
            return VerificationResult(
                passed=level1.passed,
                level=2,
                before_confidence=before,
                after_confidence=level1.after_confidence,
                config_checks=level1.config_checks,
                execution_result={"error": str(e)},
                details={**level1.details, "level2_error": str(e), "fell_back_to_level1": True},
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
                "framework": "dify",
                "execution_completed": execution_result is not None,
                "redetection_applied": after != before,
            },
            verified_at=datetime.utcnow().isoformat(),
        )

    async def verify_level2_openclaw(
        self,
        detection_type: str,
        original_confidence: float,
        original_state: Dict[str, Any],
        applied_fixes: Dict[str, Any],
        openclaw_client: Any,
        agent_id: str,
    ) -> VerificationResult:
        """Level 2: Execution-based verification for OpenClaw with re-detection."""
        level1 = await self.verify_level1(
            detection_type, original_confidence, original_state, applied_fixes
        )

        before = level1.before_confidence
        execution_result = None
        after = before

        try:
            execution_result, after = await self._verify_openclaw(
                openclaw_client, agent_id, before
            )

            if after == 0.0 and execution_result:
                redetector = self._get_redetector_for_framework(detection_type, "openclaw")
                if redetector:
                    after = await redetector(execution_result)

        except Exception as e:
            logger.error(f"Level 2 verification failed for openclaw/{agent_id}: {e}")
            return VerificationResult(
                passed=level1.passed,
                level=2,
                before_confidence=before,
                after_confidence=level1.after_confidence,
                config_checks=level1.config_checks,
                execution_result={"error": str(e)},
                details={**level1.details, "level2_error": str(e), "fell_back_to_level1": True},
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
                "framework": "openclaw",
                "execution_completed": execution_result is not None,
                "redetection_applied": after != before,
            },
            verified_at=datetime.utcnow().isoformat(),
        )

    async def _redetect_convergence_generic(self, execution_result: Dict[str, Any]) -> float:
        """Re-run convergence detection on execution metric data."""
        metrics = []
        for key in ("steps", "nodes", "events"):
            for item in execution_result.get(key, []):
                if isinstance(item, dict):
                    for metric_key in ("metric_value", "score", "val_bpb", "loss", "accuracy"):
                        if metric_key in item:
                            try:
                                metrics.append({"value": float(item[metric_key])})
                            except (ValueError, TypeError):
                                continue
                            break
        if len(metrics) < 3:
            return 0.0
        from app.detection.convergence import ConvergenceDetector
        result = ConvergenceDetector().detect_convergence_issues(metrics)
        return result.confidence if result.detected else 0.0

    def _get_redetector_for_framework(self, detection_type: str, framework: str):
        """Return the appropriate re-detection coroutine for a framework detection type.

        Universal redetectors (overflow, hallucination, injection, corruption,
        coordination, convergence) work for all frameworks. Framework-specific
        redetectors handle recursion/loop/iteration types.

        Returns a callable(execution_result) -> float, or None.
        """
        # Universal redetectors work across all frameworks
        universal = {
            "context_overflow": self._redetect_overflow_generic,
            "overflow": self._redetect_overflow_generic,
            "hallucination": self._redetect_hallucination_generic,
            "injection": self._redetect_injection_generic,
            "state_corruption": self._redetect_corruption_generic,
            "corruption": self._redetect_corruption_generic,
            "coordination_deadlock": self._redetect_coordination_generic,
            "coordination_failure": self._redetect_coordination_generic,
            "convergence": self._redetect_convergence_generic,
            "convergence_failure": self._redetect_convergence_generic,
        }
        if detection_type in universal:
            return universal[detection_type]

        # Framework-specific redetectors
        framework_specific = {
            "langgraph": {
                "langgraph_recursion": self._redetect_langgraph_recursion,
                "langgraph_checkpoint_corruption": self._redetect_langgraph_recursion,
                "infinite_loop": self._redetect_langgraph_recursion,
            },
            "dify": {
                "dify_iteration_escape": self._redetect_dify_iteration,
                "dify_node_failure_cascade": self._redetect_dify_iteration,
                "infinite_loop": self._redetect_dify_iteration,
            },
            "openclaw": {
                "openclaw_session_loop": self._redetect_openclaw_loop,
                "openclaw_spawn_bomb": self._redetect_openclaw_loop,
                "infinite_loop": self._redetect_openclaw_loop,
            },
        }
        fw_map = framework_specific.get(framework, {})
        return fw_map.get(detection_type)

    async def _redetect_langgraph_recursion(self, execution_result: Dict[str, Any]) -> float:
        """Re-detect recursion/loop in LangGraph execution result."""
        steps = execution_result.get("steps", [])
        if not steps:
            return 0.0

        # Check for repeated node patterns indicating recursion
        node_sequence = [s.get("node", "") for s in steps if isinstance(s, dict)]
        if len(node_sequence) < 3:
            return 0.0

        # Count consecutive repeated subsequences
        max_repeat = 1
        for window_size in range(1, len(node_sequence) // 2 + 1):
            repeats = 0
            for i in range(window_size, len(node_sequence)):
                if node_sequence[i] == node_sequence[i - window_size]:
                    repeats += 1
                else:
                    break
            if repeats >= window_size:
                max_repeat = max(max_repeat, repeats // window_size + 1)

        if max_repeat >= 3:
            return min(0.9, max_repeat * 0.15)
        return 0.0

    async def _redetect_dify_iteration(self, execution_result: Dict[str, Any]) -> float:
        """Re-detect iteration escape in Dify execution result."""
        nodes = execution_result.get("nodes", [])
        if not nodes:
            return 0.0

        iteration_count = 0
        for node in nodes:
            if isinstance(node, dict):
                node_type = node.get("node_type", node.get("type", ""))
                if node_type in ("iteration", "loop"):
                    iteration_count += 1

        if iteration_count > 10:
            return min(0.9, iteration_count * 0.05)
        return 0.0

    async def _redetect_openclaw_loop(self, execution_result: Dict[str, Any]) -> float:
        """Re-detect session loop in OpenClaw execution result."""
        events = execution_result.get("events", [])
        if not events:
            return 0.0

        # Check for repeated event patterns
        event_types = [e.get("type", "") for e in events if isinstance(e, dict)]
        if len(event_types) < 4:
            return 0.0

        # Simple loop detection: count consecutive same-type events
        max_run = 1
        current_run = 1
        for i in range(1, len(event_types)):
            if event_types[i] == event_types[i - 1]:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1

        if max_run >= 5:
            return min(0.9, max_run * 0.1)
        return 0.0

    async def _redetect_overflow_generic(self, execution_result: Dict[str, Any]) -> float:
        """Re-run context overflow detection on generic execution data."""
        total_tokens = execution_result.get("total_tokens", 0)
        if not total_tokens:
            # Try to sum from steps/nodes/events
            for key in ("steps", "nodes", "events"):
                for item in execution_result.get(key, []):
                    if isinstance(item, dict):
                        total_tokens += item.get("token_count", 0)
                        total_tokens += item.get("tokens", 0)

        if total_tokens == 0:
            return 0.0

        from app.detection.overflow import ContextOverflowDetector
        detector = ContextOverflowDetector()
        result = detector.detect(total_tokens=total_tokens)
        return result.confidence if result.detected else 0.0

    async def _redetect_hallucination_generic(self, execution_result: Dict[str, Any]) -> float:
        """Re-run hallucination detection on generic execution output."""
        outputs = []
        for key in ("steps", "nodes", "events"):
            for item in execution_result.get(key, []):
                if isinstance(item, dict):
                    output = item.get("output", item.get("outputs", {}).get("text", ""))
                    if output and isinstance(output, str):
                        outputs.append(output)

        if not outputs:
            return 0.0

        from app.detection.hallucination import HallucinationDetector
        detector = HallucinationDetector()
        combined = "\n".join(outputs)
        result = detector.detect(agent_output=combined)
        return result.confidence if result.detected else 0.0

    async def _redetect_injection_generic(self, execution_result: Dict[str, Any]) -> float:
        """Re-run injection detection on generic execution prompts."""
        prompts = []
        for key in ("steps", "nodes", "events"):
            for item in execution_result.get(key, []):
                if isinstance(item, dict):
                    prompt = item.get("input", item.get("inputs", {}).get("query", ""))
                    if prompt and isinstance(prompt, str):
                        prompts.append(prompt)

        if not prompts:
            return 0.0

        from app.detection.injection import InjectionDetector
        detector = InjectionDetector()
        combined = "\n".join(prompts)
        result = detector.detect(text=combined)
        return result.confidence if result.detected else 0.0

    async def _redetect_corruption_generic(self, execution_result: Dict[str, Any]) -> float:
        """Re-run state corruption detection on generic execution data."""
        states = []
        for key in ("steps", "nodes", "events"):
            for item in execution_result.get(key, []):
                if isinstance(item, dict):
                    states.append({
                        "agent_id": item.get("node", item.get("agent_name", "unknown")),
                        "state": item.get("outputs", item.get("data", {})),
                    })

        if len(states) < 2:
            return 0.0

        from app.detection.corruption import SemanticCorruptionDetector
        detector = SemanticCorruptionDetector()
        result = detector.detect(states=states)
        return result.confidence if result.detected else 0.0

    async def _redetect_coordination_generic(self, execution_result: Dict[str, Any]) -> float:
        """Re-run coordination detection on generic execution data."""
        messages = []
        seq = 0
        for key in ("steps", "nodes", "events"):
            for item in execution_result.get(key, []):
                if isinstance(item, dict):
                    messages.append({
                        "agent_id": item.get("node", item.get("agent_name", "unknown")),
                        "content": str(item.get("outputs", item.get("data", ""))),
                        "sequence": seq,
                    })
                    seq += 1

        if len(messages) < 2:
            return 0.0

        from app.detection.coordination import CoordinationAnalyzer
        analyzer = CoordinationAnalyzer()
        result = analyzer.detect(messages=messages)
        return result.confidence if result.detected else 0.0

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
            "convergence": self._redetect_convergence_generic,
            "convergence_failure": self._redetect_convergence_generic,
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
