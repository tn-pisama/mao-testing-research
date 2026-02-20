"""Tests for fix verification orchestrator."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.healing.verification import VerificationOrchestrator, VerificationResult
from app.healing.models import FailureCategory, ValidationResult, AppliedFix


@pytest.fixture
def orchestrator():
    return VerificationOrchestrator()


def _make_original_state(nodes=None):
    return {
        "nodes": nodes or [{"name": "Planner", "parameters": {}}, {"name": "Worker", "parameters": {}}],
        "settings": {},
        "connections": {"Planner": {"main": [[{"node": "Worker"}]]}},
    }


def _make_applied_fixes(fix_type="circuit_breaker", workflow_id="wf-123"):
    return {
        "fix_applied": {"id": "fix-1", "fix_type": fix_type},
        "workflow_id": workflow_id,
    }


# --- Level 1 Tests ---


class TestVerifyLevel1:
    @pytest.mark.asyncio
    async def test_passes_with_loop_protection(self, orchestrator):
        """Level 1 passes when fix adds executionTimeout and maxIterations."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="infinite_loop",
            original_confidence=0.85,
            original_state=original,
            applied_fixes=_make_applied_fixes("circuit_breaker"),
        )
        assert result.passed is True
        assert result.level == 1
        assert result.before_confidence == 0.85
        assert result.after_confidence == 0.0
        assert len(result.config_checks) > 0

    @pytest.mark.asyncio
    async def test_fails_without_state_protection(self, orchestrator):
        """Level 1 fails when state_corruption fix adds no state protection."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="state_corruption",
            original_confidence=0.9,
            original_state=original,
            applied_fixes={
                "fix_applied": {"id": "fix-2", "fix_type": "noop"},
                "workflow_id": "wf-456",
            },
        )
        # StateIntegrityValidator should fail since no state protection mechanisms are present
        state_check = next(
            (c for c in result.config_checks if c.validation_type == "state_integrity_validation"),
            None,
        )
        assert state_check is not None
        assert state_check.success is False

    @pytest.mark.asyncio
    async def test_confidence_normalization_integer(self, orchestrator):
        """Confidence >1 is normalized to 0-1 range (e.g., 85 -> 0.85)."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="infinite_loop",
            original_confidence=85,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
        )
        assert result.before_confidence == 0.85

    @pytest.mark.asyncio
    async def test_confidence_normalization_float(self, orchestrator):
        """Confidence already in 0-1 range stays unchanged."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="infinite_loop",
            original_confidence=0.75,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
        )
        assert result.before_confidence == 0.75

    @pytest.mark.asyncio
    async def test_state_corruption_detection_type(self, orchestrator):
        """Level 1 runs StateIntegrityValidator for state_corruption type."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="state_corruption",
            original_confidence=0.8,
            original_state=original,
            applied_fixes=_make_applied_fixes("state_validation"),
        )
        assert result.level == 1
        check_types = [c.validation_type for c in result.config_checks]
        assert "state_integrity_validation" in check_types

    @pytest.mark.asyncio
    async def test_persona_drift_detection_type(self, orchestrator):
        """Level 1 runs PersonaConsistencyValidator for persona_drift type."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="persona_drift",
            original_confidence=0.7,
            original_state=original,
            applied_fixes=_make_applied_fixes("persona_reinforcement"),
        )
        assert result.level == 1
        check_types = [c.validation_type for c in result.config_checks]
        assert "persona_consistency_validation" in check_types

    @pytest.mark.asyncio
    async def test_has_verified_at_timestamp(self, orchestrator):
        """Result includes ISO timestamp."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="infinite_loop",
            original_confidence=0.85,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
        )
        assert result.verified_at is not None

    @pytest.mark.asyncio
    async def test_config_and_regression_always_run(self, orchestrator):
        """ConfigurationValidator and RegressionValidator run for all types."""
        original = _make_original_state()
        result = await orchestrator.verify_level1(
            detection_type="infinite_loop",
            original_confidence=0.85,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
        )
        check_types = [c.validation_type for c in result.config_checks]
        assert "configuration_validation" in check_types
        assert "regression_validation" in check_types


# --- Level 2 Tests ---


class TestVerifyLevel2:
    @pytest.mark.asyncio
    async def test_successful_execution(self, orchestrator):
        """Level 2 passes when workflow executes successfully."""
        mock_client = AsyncMock()
        mock_client.activate_workflow = AsyncMock()
        mock_client.deactivate_workflow = AsyncMock()
        mock_client.run_workflow = AsyncMock(return_value={"executionId": "exec-1"})
        mock_client.wait_for_execution = AsyncMock(return_value={
            "status": "success",
            "finished": True,
        })

        original = _make_original_state()
        result = await orchestrator.verify_level2(
            detection_type="infinite_loop",
            original_confidence=0.9,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
            n8n_client=mock_client,
            workflow_id="wf-123",
        )
        assert result.level == 2
        assert result.execution_result is not None
        assert result.execution_result["status"] == "success"
        mock_client.activate_workflow.assert_called_once_with("wf-123")
        mock_client.deactivate_workflow.assert_called_once_with("wf-123")

    @pytest.mark.asyncio
    async def test_deactivates_on_failure(self, orchestrator):
        """Level 2 always deactivates workflow even if execution fails."""
        mock_client = AsyncMock()
        mock_client.activate_workflow = AsyncMock()
        mock_client.deactivate_workflow = AsyncMock()
        mock_client.run_workflow = AsyncMock(side_effect=Exception("n8n API error"))

        original = _make_original_state()
        result = await orchestrator.verify_level2(
            detection_type="infinite_loop",
            original_confidence=0.9,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
            n8n_client=mock_client,
            workflow_id="wf-456",
        )
        assert result.error is not None
        assert "fell_back_to_level1" in result.details

    @pytest.mark.asyncio
    async def test_controlled_termination(self, orchestrator):
        """Level 2 passes when workflow terminates with max iterations message."""
        mock_client = AsyncMock()
        mock_client.activate_workflow = AsyncMock()
        mock_client.deactivate_workflow = AsyncMock()
        mock_client.run_workflow = AsyncMock(return_value={"executionId": "exec-2"})
        mock_client.wait_for_execution = AsyncMock(return_value={
            "status": "error",
            "finished": False,
            "data": {"resultData": {"error": {"message": "Max iterations reached"}}},
        })

        original = _make_original_state()
        result = await orchestrator.verify_level2(
            detection_type="infinite_loop",
            original_confidence=0.9,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
            n8n_client=mock_client,
            workflow_id="wf-789",
        )
        assert result.execution_result.get("controlled_termination") is True
        assert result.after_confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_execution_id_returned(self, orchestrator):
        """Level 2 handles missing execution ID gracefully."""
        mock_client = AsyncMock()
        mock_client.activate_workflow = AsyncMock()
        mock_client.deactivate_workflow = AsyncMock()
        mock_client.run_workflow = AsyncMock(return_value={})

        original = _make_original_state()
        result = await orchestrator.verify_level2(
            detection_type="infinite_loop",
            original_confidence=0.9,
            original_state=original,
            applied_fixes=_make_applied_fixes(),
            n8n_client=mock_client,
            workflow_id="wf-abc",
        )
        assert result.level == 2
        assert result.execution_result is not None
        assert "error" in result.execution_result


# --- VerificationResult Tests ---


class TestVerificationResult:
    def test_to_dict_structure(self):
        result = VerificationResult(
            passed=True,
            level=1,
            before_confidence=0.9,
            after_confidence=0.0,
            config_checks=[
                ValidationResult(
                    success=True,
                    validation_type="loop_prevention_validation",
                    details={"has_max_iterations": True},
                ),
            ],
            verified_at="2025-01-01T00:00:00",
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["level"] == 1
        assert d["before_confidence"] == 0.9
        assert d["after_confidence"] == 0.0
        assert d["confidence_reduction"] == 0.9
        assert len(d["config_checks"]) == 1
        assert d["config_checks"][0]["success"] is True
        assert d["verified_at"] == "2025-01-01T00:00:00"

    def test_to_dict_with_error(self):
        result = VerificationResult(
            passed=False,
            level=2,
            before_confidence=0.85,
            after_confidence=0.85,
            error="Execution verification failed",
        )
        d = result.to_dict()
        assert d["passed"] is False
        assert d["confidence_reduction"] == 0.0
        assert d["error"] == "Execution verification failed"
