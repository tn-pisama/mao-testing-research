"""Fix validator for testing applied fixes."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
import asyncio
import time

from .models import ValidationResult, FailureCategory, AppliedFix


class FixValidator:
    """Validates that applied fixes work correctly."""
    
    def __init__(self):
        self._validators: List["ValidationStrategy"] = []
        self._register_default_validators()
    
    def _register_default_validators(self):
        self._validators.append(ConfigurationValidator())
        self._validators.append(LoopPreventionValidator())
        self._validators.append(StateIntegrityValidator())
        self._validators.append(PersonaConsistencyValidator())
        self._validators.append(CoordinationDeadlockValidator())
        self._validators.append(HallucinationPreventionValidator())
        self._validators.append(InjectionPreventionValidator())
        self._validators.append(ContextOverflowValidator())
        self._validators.append(DerailmentPreventionValidator())
        self._validators.append(ContextNeglectValidator())
        self._validators.append(CommunicationValidator())
        self._validators.append(SpecificationValidator())
        self._validators.append(DecompositionValidator())
        self._validators.append(WorkflowValidator())
        self._validators.append(WithholdingValidator())
        self._validators.append(CompletionValidator())
        self._validators.append(CostValidator())
        self._validators.append(RegressionValidator())
    
    async def validate(
        self,
        applied_fix: AppliedFix,
        failure_category: FailureCategory,
        workflow_runner: Optional[Callable] = None,
        test_input: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationResult]:
        """Run all applicable validations on an applied fix."""
        results = []
        
        for validator in self._validators:
            if validator.applies_to(failure_category, applied_fix):
                try:
                    result = await validator.validate(
                        applied_fix,
                        workflow_runner,
                        test_input,
                    )
                    results.append(result)
                except Exception as e:
                    results.append(ValidationResult(
                        success=False,
                        validation_type=validator.name,
                        details={"error": str(e)},
                        error_message=f"Validation failed: {e}",
                    ))
        
        return results
    
    async def validate_batch(
        self,
        applied_fixes: List[AppliedFix],
        failure_category: FailureCategory,
        workflow_runner: Optional[Callable] = None,
        test_inputs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, List[ValidationResult]]:
        """Validate multiple fixes."""
        results = {}
        test_inputs = test_inputs or [{}] * len(applied_fixes)
        
        for fix, test_input in zip(applied_fixes, test_inputs):
            results[fix.fix_id] = await self.validate(
                fix,
                failure_category,
                workflow_runner,
                test_input,
            )
        
        return results


class ValidationStrategy(ABC):
    """Base validation strategy."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        pass
    
    @abstractmethod
    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        pass


class ConfigurationValidator(ValidationStrategy):
    """Validates that configuration changes are valid."""
    
    @property
    def name(self) -> str:
        return "configuration_validation"
    
    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return True
    
    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        
        errors = []
        
        if "nodes" in modified:
            if not isinstance(modified["nodes"], list):
                errors.append("nodes must be a list")
            else:
                for i, node in enumerate(modified["nodes"]):
                    if not isinstance(node, dict):
                        errors.append(f"node {i} must be a dict")
                    elif "name" not in node and "id" not in node:
                        errors.append(f"node {i} missing name/id")
        
        if "settings" in modified:
            if not isinstance(modified["settings"], dict):
                errors.append("settings must be a dict")
        
        if "connections" in modified:
            if not isinstance(modified["connections"], dict):
                errors.append("connections must be a dict")
        
        return ValidationResult(
            success=len(errors) == 0,
            validation_type=self.name,
            details={
                "errors": errors,
                "settings_present": "settings" in modified,
                "nodes_count": len(modified.get("nodes", [])),
            },
            error_message="; ".join(errors) if errors else None,
        )


class LoopPreventionValidator(ValidationStrategy):
    """Validates loop prevention fixes work correctly."""
    
    @property
    def name(self) -> str:
        return "loop_prevention_validation"
    
    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.INFINITE_LOOP
    
    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})
        
        checks = {
            "has_max_iterations": False,
            "has_loop_prevention": False,
            "has_circuit_breaker": False,
            "has_backoff": False,
            "has_execution_timeout": False,
        }

        if "max_iterations" in settings:
            checks["has_max_iterations"] = True
        if "executionTimeout" in settings:
            checks["has_execution_timeout"] = True
        if settings.get("loop_prevention", {}).get("enabled"):
            checks["has_loop_prevention"] = True
        if settings.get("circuit_breaker", {}).get("enabled"):
            checks["has_circuit_breaker"] = True
        if settings.get("backoff", {}).get("enabled"):
            checks["has_backoff"] = True

        # Also check nodes for maxIterations parameter
        for node in modified.get("nodes", []):
            params = node.get("parameters", {})
            if "maxIterations" in params:
                checks["has_max_iterations"] = True
                break
        
        has_any_protection = any(checks.values())
        
        if workflow_runner and test_input:
            try:
                start = time.time()
                result = await asyncio.wait_for(
                    workflow_runner(modified, test_input),
                    timeout=30.0,
                )
                elapsed = time.time() - start
                
                iteration_count = result.get("_iteration_count", 0)
                terminated = result.get("_loop_terminated", False)
                
                return ValidationResult(
                    success=has_any_protection and (terminated or iteration_count < 100),
                    validation_type=self.name,
                    details={
                        **checks,
                        "execution_time_seconds": elapsed,
                        "iteration_count": iteration_count,
                        "terminated_gracefully": terminated,
                    },
                    metrics={
                        "execution_time": elapsed,
                        "iterations": float(iteration_count),
                    },
                )
            except asyncio.TimeoutError:
                return ValidationResult(
                    success=False,
                    validation_type=self.name,
                    details={**checks, "timeout": True},
                    error_message="Workflow timed out - loop prevention may not be working",
                )
        
        return ValidationResult(
            success=has_any_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_any_protection else "No loop prevention mechanism detected",
        )


class StateIntegrityValidator(ValidationStrategy):
    """Validates state integrity fixes."""
    
    @property
    def name(self) -> str:
        return "state_integrity_validation"
    
    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.STATE_CORRUPTION
    
    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})
        
        checks = {
            "has_state_validation": settings.get("state_validation", {}).get("enabled", False),
            "has_schema_enforcement": settings.get("schema_enforcement", {}).get("enabled", False),
            "has_checkpointing": settings.get("checkpointing", {}).get("enabled", False),
            "has_state_protection": settings.get("state_protection", {}).get("enabled", False),
        }
        
        has_protection = any(checks.values())
        
        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No state protection mechanism detected",
        )


class PersonaConsistencyValidator(ValidationStrategy):
    """Validates persona drift prevention fixes."""
    
    @property
    def name(self) -> str:
        return "persona_consistency_validation"
    
    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.PERSONA_DRIFT
    
    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})
        
        checks = {
            "has_persona_enforcement": settings.get("persona_enforcement", {}).get("enabled", False),
            "has_role_boundaries": settings.get("role_boundaries", {}).get("enabled", False),
            "has_periodic_reminder": settings.get("persona_enforcement", {}).get("periodic_reminder", False),
        }
        
        nodes_with_reinforcement = 0
        for node in modified.get("nodes", []):
            params = node.get("parameters", {})
            messages = params.get("messages", {}).get("values", [])
            for msg in messages:
                if "IMPORTANT:" in msg.get("content", "") or "maintain" in msg.get("content", "").lower():
                    nodes_with_reinforcement += 1
                    break
        
        checks["nodes_with_reinforcement"] = nodes_with_reinforcement
        
        has_protection = any([
            checks["has_persona_enforcement"],
            checks["has_role_boundaries"],
            nodes_with_reinforcement > 0,
        ])
        
        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No persona enforcement mechanism detected",
        )


class CoordinationDeadlockValidator(ValidationStrategy):
    """Validates coordination/deadlock prevention fixes."""

    @property
    def name(self) -> str:
        return "coordination_deadlock_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.COORDINATION_DEADLOCK

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_error_workflow": bool(settings.get("errorWorkflow")),
            "has_timeout": "executionTimeout" in settings,
            "has_retry_config": bool(settings.get("retry", {}).get("enabled")),
            "has_deadlock_prevention": settings.get("deadlock_prevention", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No deadlock prevention mechanism detected",
        )


class HallucinationPreventionValidator(ValidationStrategy):
    """Validates hallucination prevention fixes."""

    @property
    def name(self) -> str:
        return "hallucination_prevention_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.HALLUCINATION

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_fact_checking": settings.get("fact_checking", {}).get("enabled", False),
            "has_source_grounding": settings.get("source_grounding", {}).get("enabled", False),
            "has_confidence_calibration": settings.get("confidence_calibration", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No hallucination prevention mechanism detected",
        )


class InjectionPreventionValidator(ValidationStrategy):
    """Validates injection prevention fixes."""

    @property
    def name(self) -> str:
        return "injection_prevention_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.INJECTION

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_input_filtering": settings.get("input_filtering", {}).get("enabled", False),
            "has_safety_boundary": settings.get("safety_boundary", {}).get("enabled", False),
            "has_permission_gate": settings.get("permission_gate", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No injection prevention mechanism detected",
        )


class ContextOverflowValidator(ValidationStrategy):
    """Validates context overflow prevention fixes."""

    @property
    def name(self) -> str:
        return "context_overflow_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.CONTEXT_OVERFLOW

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_context_pruning": settings.get("context_pruning", {}).get("enabled", False),
            "has_summarization": settings.get("summarization", {}).get("enabled", False),
            "has_window_management": settings.get("window_management", {}).get("enabled", False),
            "has_execution_timeout": "executionTimeout" in settings,
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No context overflow prevention mechanism detected",
        )


class DerailmentPreventionValidator(ValidationStrategy):
    """Validates task derailment prevention fixes."""

    @property
    def name(self) -> str:
        return "derailment_prevention_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.TASK_DERAILMENT

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_task_anchoring": settings.get("task_anchoring", {}).get("enabled", False),
            "has_goal_tracking": settings.get("goal_tracking", {}).get("enabled", False),
            "has_progress_monitoring": settings.get("progress_monitoring", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No derailment prevention mechanism detected",
        )


class ContextNeglectValidator(ValidationStrategy):
    """Validates context neglect prevention fixes."""

    @property
    def name(self) -> str:
        return "context_neglect_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.CONTEXT_NEGLECT

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_context_injection": settings.get("context_injection", {}).get("enabled", False),
            "has_retrieval_verification": settings.get("retrieval_verification", {}).get("enabled", False),
            "has_checkpointing": settings.get("checkpointing", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No context neglect prevention mechanism detected",
        )


class CommunicationValidator(ValidationStrategy):
    """Validates communication breakdown prevention fixes."""

    @property
    def name(self) -> str:
        return "communication_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.COMMUNICATION_BREAKDOWN

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_message_schema": settings.get("message_schema", {}).get("enabled", False),
            "has_handoff_protocol": settings.get("handoff_protocol", {}).get("enabled", False),
            "has_retry": bool(settings.get("retry", {}).get("enabled")),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No communication fix mechanism detected",
        )


class SpecificationValidator(ValidationStrategy):
    """Validates specification mismatch prevention fixes."""

    @property
    def name(self) -> str:
        return "specification_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.SPECIFICATION_MISMATCH

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_spec_validation": settings.get("spec_validation", {}).get("enabled", False),
            "has_output_constraints": settings.get("output_constraints", {}).get("enabled", False),
            "has_schema_enforcement": settings.get("schema_enforcement", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No specification validation mechanism detected",
        )


class DecompositionValidator(ValidationStrategy):
    """Validates poor decomposition prevention fixes."""

    @property
    def name(self) -> str:
        return "decomposition_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.POOR_DECOMPOSITION

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_task_decomposition": settings.get("task_decomposition", {}).get("enabled", False),
            "has_subtask_validation": settings.get("subtask_validation", {}).get("enabled", False),
            "has_progress_monitoring": settings.get("progress_monitoring", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No decomposition fix mechanism detected",
        )


class WorkflowValidator(ValidationStrategy):
    """Validates flawed workflow prevention fixes."""

    @property
    def name(self) -> str:
        return "workflow_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.FLAWED_WORKFLOW

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_workflow_guards": settings.get("workflow_guards", {}).get("enabled", False),
            "has_step_validation": settings.get("step_validation", {}).get("enabled", False),
            "has_error_workflow": bool(settings.get("errorWorkflow")),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No workflow fix mechanism detected",
        )


class WithholdingValidator(ValidationStrategy):
    """Validates information withholding prevention fixes."""

    @property
    def name(self) -> str:
        return "withholding_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.INFORMATION_WITHHOLDING

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_transparency": settings.get("transparency", {}).get("enabled", False),
            "has_completeness_check": settings.get("completeness_check", {}).get("enabled", False),
            "has_source_grounding": settings.get("source_grounding", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No withholding prevention mechanism detected",
        )


class CompletionValidator(ValidationStrategy):
    """Validates completion misjudgment prevention fixes."""

    @property
    def name(self) -> str:
        return "completion_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.COMPLETION_MISJUDGMENT

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_completion_gate": settings.get("completion_gate", {}).get("enabled", False),
            "has_quality_checkpoint": settings.get("quality_checkpoint", {}).get("enabled", False),
            "has_progress_monitoring": settings.get("progress_monitoring", {}).get("enabled", False),
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No completion validation mechanism detected",
        )


class CostValidator(ValidationStrategy):
    """Validates cost overrun prevention fixes."""

    @property
    def name(self) -> str:
        return "cost_validation"

    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return category == FailureCategory.COST_OVERRUN

    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        modified = applied_fix.modified_state
        settings = modified.get("settings", {})

        checks = {
            "has_budget_limit": settings.get("budget_limit", {}).get("enabled", False),
            "has_cost_monitoring": settings.get("cost_monitoring", {}).get("enabled", False),
            "has_token_optimizer": settings.get("token_optimizer", {}).get("enabled", False),
            "has_execution_timeout": "executionTimeout" in settings,
        }

        has_protection = any(checks.values())

        return ValidationResult(
            success=has_protection,
            validation_type=self.name,
            details=checks,
            error_message=None if has_protection else "No cost control mechanism detected",
        )


class RegressionValidator(ValidationStrategy):
    """Validates that fixes don't break existing functionality."""
    
    @property
    def name(self) -> str:
        return "regression_validation"
    
    def applies_to(self, category: FailureCategory, fix: AppliedFix) -> bool:
        return True
    
    async def validate(
        self,
        applied_fix: AppliedFix,
        workflow_runner: Optional[Callable],
        test_input: Optional[Dict[str, Any]],
    ) -> ValidationResult:
        original = applied_fix.original_state
        modified = applied_fix.modified_state
        
        preserved = {
            "nodes_preserved": True,
            "connections_preserved": True,
            "core_settings_preserved": True,
        }
        
        original_nodes = {n.get("name") or n.get("id") for n in original.get("nodes", [])}
        modified_nodes = {n.get("name") or n.get("id") for n in modified.get("nodes", [])}
        
        if original_nodes - modified_nodes:
            preserved["nodes_preserved"] = False
            preserved["removed_nodes"] = list(original_nodes - modified_nodes)
        
        original_connections = set(original.get("connections", {}).keys())
        modified_connections = set(modified.get("connections", {}).keys())
        
        if original_connections - modified_connections:
            preserved["connections_preserved"] = False
            preserved["removed_connections"] = list(original_connections - modified_connections)
        
        all_preserved = all([
            preserved["nodes_preserved"],
            preserved["connections_preserved"],
            preserved["core_settings_preserved"],
        ])
        
        return ValidationResult(
            success=all_preserved,
            validation_type=self.name,
            details=preserved,
            error_message=None if all_preserved else "Fix modified existing workflow structure",
        )
