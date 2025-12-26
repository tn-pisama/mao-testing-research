"""E2E assertion helpers."""

from typing import Dict, Any, List, Optional
from app.healing.models import HealingStatus, HealingResult, FailureCategory


class E2EAssertions:
    """Assertion helpers for E2E tests."""
    
    @staticmethod
    def assert_healing_successful(result: HealingResult, min_validations: int = 1):
        """Assert healing completed successfully."""
        assert result.status in (HealingStatus.SUCCESS, HealingStatus.PARTIAL_SUCCESS), \
            f"Healing failed with status: {result.status.value}, error: {result.error}"
        assert result.is_successful, "Healing result is_successful is False"
        assert len(result.applied_fixes) > 0, "No fixes were applied"
        assert len(result.validation_results) >= min_validations, \
            f"Expected at least {min_validations} validations, got {len(result.validation_results)}"
    
    @staticmethod
    def assert_all_validations_passed(result: HealingResult):
        """Assert all validations passed."""
        failed = [v for v in result.validation_results if not v.success]
        assert len(failed) == 0, \
            f"Validations failed: {[v.validation_type for v in failed]}"
    
    @staticmethod
    def assert_failure_category(result: HealingResult, expected: FailureCategory):
        """Assert correct failure category was identified."""
        assert result.failure_signature is not None, "No failure signature"
        assert result.failure_signature.category == expected, \
            f"Expected {expected.value}, got {result.failure_signature.category.value}"
    
    @staticmethod
    def assert_fix_applied(result: HealingResult, fix_type: str):
        """Assert a specific fix type was applied."""
        fix_types = [f.fix_type for f in result.applied_fixes]
        assert fix_type in fix_types, \
            f"Fix type {fix_type} not in applied fixes: {fix_types}"
    
    @staticmethod
    def assert_config_modified(result: HealingResult, setting_path: str):
        """Assert configuration was modified with expected setting."""
        if not result.applied_fixes:
            raise AssertionError("No fixes applied")
        
        modified = result.applied_fixes[-1].modified_state
        settings = modified.get("settings", {})
        
        parts = setting_path.split(".")
        current = settings
        for part in parts:
            assert part in current, f"Setting {setting_path} not found in {list(current.keys())}"
            current = current[part]
    
    @staticmethod
    def assert_rollback_available(result: HealingResult):
        """Assert rollback is available for all applied fixes."""
        for fix in result.applied_fixes:
            assert fix.rollback_available, f"Rollback not available for {fix.fix_id}"
    
    @staticmethod
    def assert_healing_timing(result: HealingResult, max_seconds: float = 60.0):
        """Assert healing completed within time limit."""
        if result.completed_at and result.started_at:
            duration = (result.completed_at - result.started_at).total_seconds()
            assert duration <= max_seconds, \
                f"Healing took {duration:.2f}s, max allowed: {max_seconds}s"
    
    @staticmethod
    def assert_workflow_structure_preserved(result: HealingResult):
        """Assert original workflow structure was preserved."""
        if not result.applied_fixes:
            return
        
        original = result.applied_fixes[0].original_state
        modified = result.applied_fixes[-1].modified_state
        
        original_nodes = {n.get("name") or n.get("id") for n in original.get("nodes", [])}
        modified_nodes = {n.get("name") or n.get("id") for n in modified.get("nodes", [])}
        
        removed = original_nodes - modified_nodes
        assert len(removed) == 0, f"Nodes were removed: {removed}"
    
    @staticmethod
    def assert_no_regression(result: HealingResult):
        """Assert no regression was introduced."""
        regression_result = next(
            (v for v in result.validation_results if v.validation_type == "regression_validation"),
            None
        )
        if regression_result:
            assert regression_result.success, \
                f"Regression detected: {regression_result.error_message}"
