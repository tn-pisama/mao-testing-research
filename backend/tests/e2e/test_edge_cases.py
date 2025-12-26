"""E2E tests for edge cases and error handling."""

import pytest
from app.healing import SelfHealingEngine, HealingStatus
from app.healing.models import FailureCategory
from .utils import E2EAssertions


class TestEdgeCaseDetections:
    """Tests for edge case detection scenarios."""
    
    @pytest.mark.asyncio
    async def test_empty_detection(self, healing_engine, langgraph_workflow):
        """Test handling of empty detection."""
        result = await healing_engine.heal({}, langgraph_workflow)
        
        assert result.failure_signature is not None
        assert result.failure_signature.category == FailureCategory.API_FAILURE
    
    @pytest.mark.asyncio
    async def test_unknown_detection_type(self, healing_engine, langgraph_workflow):
        """Test handling of unknown detection type."""
        detection = {
            "id": "unknown_det",
            "detection_type": "quantum_entanglement_failure",
            "details": {"message": "Unknown failure"}
        }
        
        result = await healing_engine.heal(detection, langgraph_workflow)
        
        assert result.failure_signature is not None
    
    @pytest.mark.asyncio
    async def test_high_confidence_detection(
        self,
        healing_engine,
        langgraph_workflow,
        detection_factory,
    ):
        """Test handling of high confidence detection."""
        detection = detection_factory.infinite_loop(confidence=0.99, loop_length=15)
        
        result = await healing_engine.heal(detection, langgraph_workflow)
        
        E2EAssertions.assert_healing_successful(result)
        assert result.failure_signature.confidence == 0.99
    
    @pytest.mark.asyncio
    async def test_low_confidence_detection(
        self,
        healing_engine,
        langgraph_workflow,
        detection_factory,
    ):
        """Test handling of low confidence detection."""
        detection = detection_factory.infinite_loop(confidence=0.3, loop_length=2)
        
        result = await healing_engine.heal(detection, langgraph_workflow)
        
        assert result.failure_signature is not None
        assert result.failure_signature.confidence == 0.3


class TestEdgeCaseWorkflows:
    """Tests for edge case workflow scenarios."""
    
    @pytest.mark.asyncio
    async def test_empty_workflow(self, healing_engine, loop_detection):
        """Test handling of empty workflow configuration."""
        result = await healing_engine.heal(loop_detection, {})
        
        assert result.status in (HealingStatus.SUCCESS, HealingStatus.PARTIAL_SUCCESS, HealingStatus.FAILED)
    
    @pytest.mark.asyncio
    async def test_minimal_workflow(self, healing_engine, loop_detection):
        """Test handling of minimal workflow."""
        minimal_workflow = {
            "name": "minimal",
            "nodes": [{"id": "single", "name": "Single Node"}],
            "connections": {},
            "settings": {}
        }
        
        result = await healing_engine.heal(loop_detection, minimal_workflow)
        
        E2EAssertions.assert_healing_successful(result)
    
    @pytest.mark.asyncio
    async def test_complex_workflow(
        self,
        healing_engine,
        workflow_factory,
        loop_detection,
    ):
        """Test handling of complex multi-agent workflow."""
        complex_workflow = workflow_factory.langgraph.create_complex_workflow(num_agents=10)
        
        result = await healing_engine.heal(loop_detection, complex_workflow)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_workflow_structure_preserved(result)
    
    @pytest.mark.asyncio
    async def test_workflow_with_existing_settings(
        self,
        healing_engine,
        detection_factory,
    ):
        """Test workflow that already has some protective settings."""
        workflow = {
            "name": "protected_workflow",
            "nodes": [{"id": "agent", "name": "Agent"}],
            "connections": {},
            "settings": {
                "max_iterations": 5,
                "timeout_ms": 30000,
            }
        }
        
        detection = detection_factory.infinite_loop()
        result = await healing_engine.heal(detection, workflow)
        
        modified = result.applied_fixes[-1].modified_state if result.applied_fixes else workflow
        assert modified["settings"].get("max_iterations") is not None


class TestMultipleDetections:
    """Tests for handling multiple detections."""
    
    @pytest.mark.asyncio
    async def test_batch_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
    ):
        """Test batch healing of multiple detections."""
        detections = [
            detection_factory.infinite_loop(),
            detection_factory.state_corruption(),
            detection_factory.persona_drift(),
        ]
        
        workflows = {
            det["id"]: workflow_factory.create_workflow("langgraph", "normal")
            for det in detections
        }
        
        results = await healing_engine.heal_batch(detections, workflows)
        
        assert len(results) == 3
        successful = sum(1 for r in results if r.is_successful)
        assert successful >= 2, f"Only {successful}/3 healed successfully"
    
    @pytest.mark.asyncio
    async def test_sequential_healing_same_workflow(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
    ):
        """Test sequential healing of different failures on same workflow."""
        workflow = workflow_factory.create_workflow("langgraph", "normal")
        
        loop_result = await healing_engine.heal(
            detection_factory.infinite_loop(),
            workflow
        )
        E2EAssertions.assert_healing_successful(loop_result)
        
        healed_workflow = loop_result.applied_fixes[-1].modified_state
        
        corruption_result = await healing_engine.heal(
            detection_factory.state_corruption(),
            healed_workflow
        )
        E2EAssertions.assert_healing_successful(corruption_result)
        
        final_workflow = corruption_result.applied_fixes[-1].modified_state
        assert "loop_prevention" in final_workflow["settings"]
        assert "state_validation" in final_workflow["settings"]


class TestErrorRecovery:
    """Tests for error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_invalid_rollback_id(self, healing_engine):
        """Test handling of invalid rollback ID."""
        with pytest.raises(ValueError, match="not found"):
            healing_engine.rollback("nonexistent_id")
    
    @pytest.mark.asyncio
    async def test_approve_non_pending(
        self,
        healing_engine,
        langgraph_workflow,
        loop_detection,
    ):
        """Test approving non-pending healing result."""
        result = await healing_engine.heal(loop_detection, langgraph_workflow)
        
        with pytest.raises(ValueError, match="not pending"):
            healing_engine.approve_and_apply(result.id, ["fix_1"])
    
    @pytest.mark.asyncio
    async def test_healing_preserves_on_error(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
    ):
        """Test workflow is not corrupted if healing fails."""
        original = workflow_factory.create_workflow("langgraph", "normal")
        original_copy = original.copy()
        
        await healing_engine.heal(detection_factory.infinite_loop(), original)
        
        assert original["nodes"] == original_copy["nodes"]
        assert original["connections"] == original_copy["connections"]
