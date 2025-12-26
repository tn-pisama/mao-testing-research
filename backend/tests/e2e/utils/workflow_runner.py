"""Workflow runner utilities for E2E testing."""

from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timezone

from app.healing import SelfHealingEngine, HealingResult
from ..fixtures.mock_responses import MockLLMResponses


class WorkflowRunner:
    """Helper for running workflows in E2E tests."""
    
    def __init__(self, healing_engine: SelfHealingEngine):
        self.healing_engine = healing_engine
        self.mock_responses = MockLLMResponses()
        self.execution_history: List[Dict[str, Any]] = []
    
    async def run_healing_cycle(
        self,
        detection: Dict[str, Any],
        workflow: Dict[str, Any],
        test_input: Optional[Dict[str, Any]] = None,
        failure_mode: str = "normal"
    ) -> Dict[str, Any]:
        """Run complete detection -> healing -> validation cycle."""
        
        async def mock_workflow_runner(config: Dict, input_data: Dict) -> Dict:
            return self.mock_responses.create_workflow_execution_result(
                config, 
                failure_mode="normal",
                iteration_count=3
            )
        
        healing_result = await self.healing_engine.heal(
            detection=detection,
            workflow_config=workflow,
            workflow_runner=mock_workflow_runner,
            test_input=test_input or {"query": "test query"}
        )
        
        execution_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detection_id": detection.get("id"),
            "detection_type": detection.get("detection_type"),
            "healing_status": healing_result.status.value,
            "fixes_applied": len(healing_result.applied_fixes),
            "validations_passed": sum(1 for v in healing_result.validation_results if v.success),
            "validations_total": len(healing_result.validation_results),
        }
        self.execution_history.append(execution_record)
        
        if healing_result.applied_fixes:
            healed_workflow = healing_result.applied_fixes[-1].modified_state
            validation_execution = self.mock_responses.create_workflow_execution_result(
                healed_workflow,
                failure_mode="normal",
                iteration_count=2
            )
        else:
            validation_execution = None
        
        return {
            "healing_result": healing_result,
            "validation_execution": validation_execution,
            "success": healing_result.is_successful,
        }
    
    async def run_batch_healing(
        self,
        detections: List[Dict[str, Any]],
        workflows: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Run healing for multiple detections."""
        results = []
        for detection in detections:
            det_id = detection.get("id", "")
            workflow = workflows.get(det_id, list(workflows.values())[0] if workflows else {})
            result = await self.run_healing_cycle(detection, workflow)
            results.append(result)
        return results
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all executions."""
        if not self.execution_history:
            return {"total": 0}
        
        total = len(self.execution_history)
        successful = sum(1 for e in self.execution_history if e["healing_status"] == "success")
        
        by_type = {}
        for e in self.execution_history:
            det_type = e["detection_type"]
            if det_type not in by_type:
                by_type[det_type] = {"total": 0, "successful": 0}
            by_type[det_type]["total"] += 1
            if e["healing_status"] == "success":
                by_type[det_type]["successful"] += 1
        
        return {
            "total": total,
            "successful": successful,
            "success_rate": successful / total if total > 0 else 0,
            "by_detection_type": by_type,
        }
