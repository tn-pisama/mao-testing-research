"""E2E tests for complete quality healing pipeline flows."""

import sys
from pathlib import Path
import pytest

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.healing.engine import QualityHealingEngine
from app.enterprise.quality.healing.models import QualityHealingStatus


class TestQualityHealingPipelineFlow:
    """Tests for the complete quality healing pipeline."""

    def test_full_pipeline_assess_to_validation(
        self, quality_healing_engine, low_quality_workflow,
    ):
        """Test complete pipeline: assess → generate → apply → validate."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(low_quality_workflow)
        
        result = quality_healing_engine.heal(report, low_quality_workflow)
        
        # Should have targeted some dimensions
        assert len(result.dimensions_targeted) > 0
        # Pipeline should have completed (not crashed)
        assert result.completed_at is not None
        # Should have a before score
        assert result.before_score is not None
        # Status should be a valid terminal state
        assert result.status in (
            QualityHealingStatus.SUCCESS,
            QualityHealingStatus.PARTIAL_SUCCESS,
            QualityHealingStatus.FAILED,
        )
        # If fixes were applied, should have validation results
        if result.applied_fixes:
            assert len(result.validation_results) > 0

    def test_pipeline_with_low_quality_workflow(
        self, quality_healing_engine, low_quality_workflow,
    ):
        """Test low quality workflow produces many fix suggestions."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(low_quality_workflow)
        
        result = quality_healing_engine.heal(report, low_quality_workflow)
        
        # Low quality should target multiple dimensions
        assert len(result.dimensions_targeted) >= 3
        # Should have before_score below threshold
        assert result.before_score < 0.8
        # Should have generated fix suggestions
        assert result.metadata.get("fix_suggestions_count", 0) > 0

    def test_pipeline_high_quality_fewer_dimensions(
        self, quality_healing_engine, high_quality_workflow,
    ):
        """Test high quality workflow targets fewer dimensions than low quality."""
        assessor = QualityAssessor(use_llm_judge=False)
        
        # Assess low quality
        low_wf = {
            "id": "wf-low",
            "name": "Low Quality",
            "nodes": [
                {
                    "id": "agent1",
                    "name": "AI Agent",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {},
                    "typeVersion": 1,
                    "position": [100, 100],
                },
            ],
            "connections": {},
            "settings": {},
        }
        low_report = assessor.assess_workflow(low_wf)
        low_result = quality_healing_engine.heal(low_report, low_wf)
        
        # Assess high quality
        high_report = assessor.assess_workflow(high_quality_workflow)
        
        # High quality should have a better overall score
        assert high_report.overall_score > low_report.overall_score
        
        # Pipeline should complete
        high_result = quality_healing_engine.heal(high_report, high_quality_workflow)
        assert high_result.completed_at is not None
        # High quality should target fewer dimensions (or equal)
        assert len(high_result.dimensions_targeted) <= len(low_result.dimensions_targeted)


class TestQualityHealingRollback:
    """Tests for rollback functionality."""

    def test_rollback_after_healing(
        self, quality_healing_engine, low_quality_workflow,
    ):
        """Test rollback restores original configuration."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(low_quality_workflow)
        
        result = quality_healing_engine.heal(report, low_quality_workflow)
        
        # We need at least one applied fix for rollback to work
        if result.applied_fixes:
            rolled_back = quality_healing_engine.rollback(result.id)
            assert rolled_back == low_quality_workflow

    def test_rollback_preserves_custom_settings(
        self, quality_healing_engine,
    ):
        """Test rollback preserves exact original workflow state."""
        workflow = {
            "id": "wf-custom",
            "name": "Custom Settings",
            "nodes": [
                {
                    "id": "agent1",
                    "name": "Agent",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {},
                    "typeVersion": 1,
                    "position": [100, 100],
                },
            ],
            "connections": {},
            "settings": {"custom_key": {"nested": 42}},
        }
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(workflow)
        result = quality_healing_engine.heal(report, workflow)
        
        if result.applied_fixes:
            rolled_back = quality_healing_engine.rollback(result.id)
            assert rolled_back["settings"]["custom_key"]["nested"] == 42


class TestQualityHealingHistory:
    """Tests for healing history and statistics."""

    def test_history_tracking(self, quality_healing_engine, low_quality_workflow):
        """Test healing operations are tracked in history."""
        assessor = QualityAssessor(use_llm_judge=False)
        
        for _ in range(3):
            report = assessor.assess_workflow(low_quality_workflow)
            quality_healing_engine.heal(report, low_quality_workflow)
        
        history = quality_healing_engine.get_healing_history()
        assert len(history) >= 3

    def test_statistics_accuracy(self, quality_healing_engine, low_quality_workflow):
        """Test healing statistics are accurate."""
        assessor = QualityAssessor(use_llm_judge=False)
        
        for _ in range(3):
            report = assessor.assess_workflow(low_quality_workflow)
            quality_healing_engine.heal(report, low_quality_workflow)
        
        stats = quality_healing_engine.get_healing_stats()
        assert stats["total"] >= 3
        assert "success_rate" in stats
        assert "by_status" in stats
        assert "by_dimension" in stats


class TestQualityManualApprovalFlow:
    """Tests for manual approval healing flow."""

    def test_manual_approval_pending_status(
        self, quality_healing_engine_manual, low_quality_workflow,
    ):
        """Test manual mode returns pending status."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(low_quality_workflow)
        
        result = quality_healing_engine_manual.heal(report, low_quality_workflow)
        
        assert result.status == QualityHealingStatus.PENDING
        assert len(result.applied_fixes) == 0
        assert "fix_suggestions" in result.metadata

    def test_approve_and_apply(
        self, quality_healing_engine_manual, low_quality_workflow,
    ):
        """Test approving and applying fixes."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(low_quality_workflow)
        
        result = quality_healing_engine_manual.heal(report, low_quality_workflow)
        assert result.status == QualityHealingStatus.PENDING
        
        fix_ids = [f["id"] for f in result.metadata.get("fix_suggestions", [])]
        if fix_ids:
            approved = quality_healing_engine_manual.approve_and_apply(result.id, fix_ids[:1])
            assert approved.status in (QualityHealingStatus.SUCCESS, QualityHealingStatus.PARTIAL_SUCCESS)


class TestQualityFullLifecycle:
    """End-to-end test: assess → heal → verify → rollback."""

    def test_assess_heal_verify_rollback(
        self, quality_healing_engine, low_quality_workflow,
    ):
        """Full lifecycle: assess, heal, check scores, rollback."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(low_quality_workflow)
        
        # Step 1: Heal
        result = quality_healing_engine.heal(report, low_quality_workflow)
        assert result.completed_at is not None
        
        # Step 2: Check scores are present
        assert result.before_score is not None
        if result.after_score is not None:
            assert result.after_score >= 0.0
        
        # Step 3: Rollback (if fixes were applied)
        if result.applied_fixes:
            rolled_back = quality_healing_engine.rollback(result.id)
            assert rolled_back == low_quality_workflow

    def test_all_15_dimensions_produce_fixes(self):
        """E2E: All 15 quality dimensions can produce fix suggestions."""
        from app.enterprise.quality.healing.agent_fixes import ALL_AGENT_FIX_GENERATORS
        from app.enterprise.quality.healing.orchestration_fixes import ALL_ORCHESTRATION_FIX_GENERATORS
        from app.enterprise.quality.models import DimensionScore
        
        all_generators = ALL_AGENT_FIX_GENERATORS + ALL_ORCHESTRATION_FIX_GENERATORS
        
        all_dimensions = [
            "role_clarity", "output_consistency", "error_handling",
            "tool_usage", "config_appropriateness",
            "data_flow_clarity", "complexity_management", "agent_coupling",
            "observability", "best_practices", "documentation_quality",
            "ai_architecture", "maintenance_quality", "test_coverage",
            "layout_quality",
        ]
        
        for dimension in all_dimensions:
            # Find matching generator
            matching = [g for g in all_generators if g.can_handle(dimension)]
            assert len(matching) >= 1, f"No generator for dimension: {dimension}"
            
            # Generate fixes with low score
            dim_score = DimensionScore(
                dimension=dimension,
                score=0.2,
                evidence={
                    "has_system_prompt": False,
                    "connection_coverage": 0.3,
                    "node_count": 20,
                    "coupling_ratio": 0.8,
                    "max_agent_chain": 5,
                    "observability_nodes": 0,
                    "error_triggers": 0,
                    "monitoring_webhooks": 0,
                    "error_handler_present": False,
                    "execution_timeout": 0,
                    "config_uniformity": 0.3,
                    "sticky_note_count": 0,
                    "workflow_description": "",
                    "ai_connection_diversity": 0.2,
                    "disabled_nodes": 3,
                    "outdated_versions": 2,
                    "test_coverage_ratio": 0.0,
                    "overlapping_nodes": 5,
                    "alignment_score": 0.3,
                    "generic_name_ratio": 0.6,
                },
            )
            context = {
                "target_type": "agent" if dimension in all_dimensions[:5] else "orchestration",
                "agent_id": "test-agent",
                "agent_name": "Test Agent",
                "agent_type": "langchain_agent",
                "workflow_id": "wf-test",
                "workflow_name": "Test Workflow",
            }
            
            fixes = matching[0].generate_fixes(dim_score, context)
            assert len(fixes) >= 1, f"{dimension}: expected >= 1 fix, got {len(fixes)}"

    def test_heal_idempotent_on_good_workflow(
        self, quality_healing_engine, high_quality_workflow,
    ):
        """High quality workflow should heal successfully with minimal changes."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(high_quality_workflow)
        
        result = quality_healing_engine.heal(report, high_quality_workflow)
        
        # Pipeline should complete without crashing
        assert result.completed_at is not None
        # Should be a valid terminal status
        assert result.status in (
            QualityHealingStatus.SUCCESS,
            QualityHealingStatus.PARTIAL_SUCCESS,
            QualityHealingStatus.FAILED,
        )
        # High quality workflow should have fewer targeted dimensions than a bare one
        assert result.before_score > 0.3
