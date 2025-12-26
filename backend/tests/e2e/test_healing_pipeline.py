"""E2E tests for complete healing pipeline flows."""

import pytest
from app.healing import SelfHealingEngine, HealingStatus
from app.healing.models import FailureCategory
from .utils import E2EAssertions, WorkflowRunner


class TestHealingPipelineFlow:
    """Tests for the complete healing pipeline."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_detection_to_validation(
        self,
        healing_engine,
        langgraph_workflow,
        loop_detection,
    ):
        """Test complete pipeline: detection → analysis → fix → validate."""
        result = await healing_engine.heal(loop_detection, langgraph_workflow)
        
        assert result.failure_signature is not None, "Analysis failed - no signature"
        assert result.failure_signature.category == FailureCategory.INFINITE_LOOP
        assert result.failure_signature.root_cause is not None
        assert len(result.failure_signature.indicators) > 0
        
        assert "fix_suggestions" in result.metadata
        assert result.metadata["fix_suggestions_count"] > 0
        
        assert len(result.applied_fixes) > 0
        first_fix = result.applied_fixes[0]
        assert first_fix.fix_type in ["retry_limit", "circuit_breaker", "exponential_backoff"]
        assert first_fix.rollback_available
        
        assert len(result.validation_results) >= 3
        validation_types = [v.validation_type for v in result.validation_results]
        assert "configuration_validation" in validation_types
        assert "loop_prevention_validation" in validation_types
        assert "regression_validation" in validation_types
        
        assert result.status == HealingStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_pipeline_with_workflow_runner(
        self,
        workflow_runner,
        langgraph_workflow,
        corruption_detection,
    ):
        """Test pipeline using workflow runner helper."""
        result = await workflow_runner.run_healing_cycle(
            detection=corruption_detection,
            workflow=langgraph_workflow,
            failure_mode="corruption"
        )
        
        assert result["success"]
        assert result["healing_result"].is_successful
        assert result["validation_execution"] is not None
    
    @pytest.mark.asyncio
    async def test_pipeline_timing_constraints(
        self,
        healing_engine,
        langgraph_workflow,
        drift_detection,
    ):
        """Test pipeline completes within time constraints."""
        result = await healing_engine.heal(drift_detection, langgraph_workflow)
        
        E2EAssertions.assert_healing_timing(result, max_seconds=30.0)
        
        assert result.completed_at is not None
        assert result.started_at is not None
        duration = (result.completed_at - result.started_at).total_seconds()
        assert duration < 30.0, f"Pipeline took {duration}s"


class TestHealingRollback:
    """Tests for rollback functionality."""
    
    @pytest.mark.asyncio
    async def test_rollback_after_healing(
        self,
        healing_engine,
        langgraph_workflow,
        loop_detection,
    ):
        """Test rollback restores original configuration."""
        result = await healing_engine.heal(loop_detection, langgraph_workflow)
        
        assert result.is_successful
        assert len(result.applied_fixes) > 0
        
        rolled_back = healing_engine.rollback(result.id)
        
        assert rolled_back == langgraph_workflow
        assert "loop_prevention" not in rolled_back.get("settings", {})
    
    @pytest.mark.asyncio
    async def test_rollback_preserves_original_state(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
    ):
        """Test rollback preserves exact original workflow state."""
        original = workflow_factory.create_workflow("langgraph", "normal")
        original["settings"]["custom_setting"] = {"value": 123}
        
        detection = detection_factory.infinite_loop()
        result = await healing_engine.heal(detection, original)
        
        rolled_back = healing_engine.rollback(result.id)
        
        assert rolled_back["settings"]["custom_setting"]["value"] == 123


class TestHealingHistory:
    """Tests for healing history and statistics."""
    
    @pytest.mark.asyncio
    async def test_history_tracking(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
    ):
        """Test healing operations are tracked in history."""
        detections = [
            detection_factory.infinite_loop(),
            detection_factory.state_corruption(),
            detection_factory.persona_drift(),
        ]
        
        for det in detections:
            workflow = workflow_factory.create_workflow("langgraph", "normal")
            await healing_engine.heal(det, workflow)
        
        history = healing_engine.get_healing_history()
        assert len(history) >= 3
    
    @pytest.mark.asyncio
    async def test_statistics_accuracy(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
    ):
        """Test healing statistics are accurate."""
        for _ in range(5):
            det = detection_factory.infinite_loop()
            workflow = workflow_factory.create_workflow("langgraph", "normal")
            await healing_engine.heal(det, workflow)
        
        stats = healing_engine.get_healing_stats()
        
        assert stats["total"] >= 5
        assert "success_rate" in stats
        assert "by_status" in stats
        assert "by_failure_category" in stats


class TestManualApprovalFlow:
    """Tests for manual approval healing flow."""
    
    @pytest.mark.asyncio
    async def test_manual_approval_pending_status(
        self,
        healing_engine_manual,
        langgraph_workflow,
        loop_detection,
    ):
        """Test manual mode returns pending status."""
        result = await healing_engine_manual.heal(loop_detection, langgraph_workflow)
        
        assert result.status == HealingStatus.PENDING
        assert result.metadata.get("requires_approval")
        assert len(result.applied_fixes) == 0
        assert "fix_suggestions" in result.metadata
    
    @pytest.mark.asyncio
    async def test_approve_and_apply(
        self,
        healing_engine_manual,
        langgraph_workflow,
        loop_detection,
    ):
        """Test approving and applying fixes."""
        result = await healing_engine_manual.heal(loop_detection, langgraph_workflow)
        
        assert result.status == HealingStatus.PENDING
        
        fix_ids = [f["id"] for f in result.metadata.get("fix_suggestions", [])]
        
        if fix_ids:
            approved = healing_engine_manual.approve_and_apply(result.id, fix_ids[:1])
            assert approved.status == HealingStatus.SUCCESS
