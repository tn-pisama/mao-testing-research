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
        }
        
        if "max_iterations" in settings:
            checks["has_max_iterations"] = True
        if settings.get("loop_prevention", {}).get("enabled"):
            checks["has_loop_prevention"] = True
        if settings.get("circuit_breaker", {}).get("enabled"):
            checks["has_circuit_breaker"] = True
        if settings.get("backoff", {}).get("enabled"):
            checks["has_backoff"] = True
        
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
