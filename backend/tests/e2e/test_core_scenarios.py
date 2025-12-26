"""Core E2E test scenarios: 9 primary (3 frameworks × 3 failure modes)."""

import pytest
from app.healing.models import HealingStatus, FailureCategory
from .utils import E2EAssertions


class TestLangGraphE2E:
    """E2E tests for LangGraph workflows."""
    
    @pytest.mark.asyncio
    async def test_langgraph_infinite_loop_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-LG-001: LangGraph infinite loop → retry limit fix → success."""
        workflow = workflow_factory.create_workflow("langgraph", "loop")
        detection = detection_factory.infinite_loop(
            loop_length=7,
            agents=["researcher", "analyst"]
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("langgraph_loop", "langgraph", "infinite_loop", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.INFINITE_LOOP)
        E2EAssertions.assert_config_modified(result, "loop_prevention.enabled")
        E2EAssertions.assert_rollback_available(result)
        E2EAssertions.assert_no_regression(result)
    
    @pytest.mark.asyncio
    async def test_langgraph_state_corruption_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-LG-002: LangGraph state corruption → state validation fix → success."""
        workflow = workflow_factory.create_workflow("langgraph", "normal")
        detection = detection_factory.state_corruption(
            corrupted_fields=["research_notes", "analysis"],
            null_injection=True
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("langgraph_corruption", "langgraph", "state_corruption", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.STATE_CORRUPTION)
        E2EAssertions.assert_config_modified(result, "state_validation.enabled")
        E2EAssertions.assert_workflow_structure_preserved(result)
    
    @pytest.mark.asyncio
    async def test_langgraph_persona_drift_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-LG-003: LangGraph persona drift → prompt reinforcement → success."""
        workflow = workflow_factory.create_workflow("langgraph", "normal")
        detection = detection_factory.persona_drift(
            agent_name="writer",
            drift_score=0.85
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("langgraph_drift", "langgraph", "persona_drift", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.PERSONA_DRIFT)
        E2EAssertions.assert_config_modified(result, "persona_enforcement.enabled")


class TestCrewAIE2E:
    """E2E tests for CrewAI workflows."""
    
    @pytest.mark.asyncio
    async def test_crewai_infinite_loop_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-CR-001: CrewAI infinite loop → circuit breaker fix → success."""
        workflow = workflow_factory.create_workflow("crewai", "loop")
        detection = detection_factory.infinite_loop(
            loop_length=5,
            agents=["researcher", "analyst"],
            method="structural"
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("crewai_loop", "crewai", "infinite_loop", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.INFINITE_LOOP)
        E2EAssertions.assert_rollback_available(result)
    
    @pytest.mark.asyncio
    async def test_crewai_state_corruption_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-CR-002: CrewAI state corruption → validation fix → success."""
        workflow = workflow_factory.create_workflow("crewai", "normal")
        detection = detection_factory.state_corruption(
            corrupted_fields=["task_output", "context"],
            data_loss=True
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("crewai_corruption", "crewai", "state_corruption", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.STATE_CORRUPTION)
    
    @pytest.mark.asyncio
    async def test_crewai_persona_drift_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-CR-003: CrewAI persona drift → role boundary fix → success."""
        workflow = workflow_factory.create_workflow("crewai", "normal")
        detection = detection_factory.persona_drift(
            agent_name="Technical Writer",
            expected_tone="professional",
            actual_tone="casual"
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("crewai_drift", "crewai", "persona_drift", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.PERSONA_DRIFT)


class TestN8nE2E:
    """E2E tests for n8n workflows."""
    
    @pytest.mark.asyncio
    async def test_n8n_infinite_loop_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-N8-001: n8n infinite loop → timeout/limit fix → success."""
        workflow = workflow_factory.create_workflow("n8n", "loop")
        detection = detection_factory.infinite_loop(
            loop_length=10,
            agents=["openai", "check"],
            method="iteration_count"
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("n8n_loop", "n8n", "infinite_loop", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.INFINITE_LOOP)
    
    @pytest.mark.asyncio
    async def test_n8n_state_corruption_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-N8-002: n8n state corruption → data sanitization → success."""
        workflow = workflow_factory.create_workflow("n8n", "normal")
        detection = detection_factory.state_corruption(
            corrupted_fields=["response", "data"],
            null_injection=True
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("n8n_corruption", "n8n", "state_corruption", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.STATE_CORRUPTION)
    
    @pytest.mark.asyncio
    async def test_n8n_persona_drift_healing(
        self,
        healing_engine,
        workflow_factory,
        detection_factory,
        metrics_collector,
    ):
        """E2E-N8-003: n8n persona drift → output format fix → success."""
        workflow = workflow_factory.create_workflow("n8n", "normal")
        detection = detection_factory.persona_drift(
            agent_name="OpenAI Research",
            expected_tone="professional",
            actual_tone="casual_unprofessional"
        )
        
        result = await healing_engine.heal(detection, workflow)
        
        metrics_collector.record("n8n_drift", "n8n", "persona_drift", result)
        
        E2EAssertions.assert_healing_successful(result)
        E2EAssertions.assert_failure_category(result, FailureCategory.PERSONA_DRIFT)


class TestParametrizedE2E:
    """Parametrized E2E tests for comprehensive coverage."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework", ["langgraph", "crewai", "n8n"])
    @pytest.mark.parametrize("failure_mode", ["infinite_loop", "state_corruption", "persona_drift"])
    async def test_all_framework_failure_combinations(
        self,
        framework: str,
        failure_mode: str,
        healing_engine,
        workflow_factory,
        detection_factory,
    ):
        """Test all 9 framework × failure mode combinations."""
        workflow = workflow_factory.create_workflow(framework, "normal")
        detection = detection_factory.create_detection(failure_mode)
        
        result = await healing_engine.heal(detection, workflow)
        
        assert result.status in (HealingStatus.SUCCESS, HealingStatus.PARTIAL_SUCCESS), \
            f"Failed for {framework}/{failure_mode}: {result.error}"
        assert result.failure_signature is not None
        assert len(result.applied_fixes) > 0
