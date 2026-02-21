"""Tests for QualityFixValidator — re-assessment after applying fixes."""

import pytest
import sys
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality.healing.validator import QualityFixValidator
from app.enterprise.quality.healing.models import (
    QualityAppliedFix,
    QualityValidationResult,
)
from app.enterprise.quality.models import (
    QualityReport,
    AgentQualityScore,
    OrchestrationQualityScore,
    DimensionScore,
    ComplexityMetrics,
)
from app.enterprise.quality import QualityAssessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_workflow(nodes=None, connections=None, settings=None):
    return {
        "id": "test-wf",
        "name": "Test Workflow",
        "nodes": nodes or [],
        "connections": connections or {},
        "settings": settings or {},
    }


def make_agent_node(node_id="agent-1", name="Test Agent", system_message="You are a helper."):
    return {
        "id": node_id,
        "name": name,
        "type": "@n8n/n8n-nodes-langchain.agent",
        "parameters": {"systemMessage": system_message},
        "position": [0, 0],
    }


def make_dimension_score(dimension, score, weight=1.0, issues=None):
    return DimensionScore(
        dimension=dimension,
        score=score,
        weight=weight,
        issues=issues or [],
    )


def make_agent_score(
    agent_id="agent-1",
    agent_name="Test Agent",
    overall_score=0.5,
    dimensions=None,
):
    if dimensions is None:
        dimensions = [
            make_dimension_score("role_clarity", overall_score),
            make_dimension_score("output_consistency", overall_score),
            make_dimension_score("error_handling", overall_score),
            make_dimension_score("tool_usage", overall_score),
            make_dimension_score("config_appropriateness", overall_score),
        ]
    return AgentQualityScore(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_type="@n8n/n8n-nodes-langchain.agent",
        overall_score=overall_score,
        dimensions=dimensions,
    )


def make_orchestration_score(
    workflow_id="test-wf",
    workflow_name="Test Workflow",
    overall_score=0.5,
    dimensions=None,
):
    if dimensions is None:
        dimensions = [
            make_dimension_score("data_flow_clarity", overall_score),
            make_dimension_score("complexity_management", overall_score),
            make_dimension_score("agent_coupling", overall_score),
            make_dimension_score("observability", overall_score),
            make_dimension_score("best_practices", overall_score),
            make_dimension_score("documentation_quality", overall_score),
            make_dimension_score("ai_architecture", overall_score),
            make_dimension_score("maintenance_quality", overall_score),
            make_dimension_score("test_coverage", overall_score),
            make_dimension_score("layout_quality", overall_score),
        ]
    return OrchestrationQualityScore(
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        overall_score=overall_score,
        dimensions=dimensions,
        complexity_metrics=ComplexityMetrics(),
    )


def make_report(
    overall_score=0.5,
    agent_dimensions=None,
    orch_dimensions=None,
    agent_score=None,
    orch_score=None,
):
    """Create a minimal QualityReport with given scores."""
    if agent_score is None:
        agent_score = make_agent_score(
            overall_score=overall_score,
            dimensions=agent_dimensions,
        )
    if orch_score is None:
        orch_score = make_orchestration_score(
            overall_score=overall_score,
            dimensions=orch_dimensions,
        )
    return QualityReport(
        workflow_id="test-wf",
        workflow_name="Test Workflow",
        overall_score=overall_score,
        agent_scores=[agent_score],
        orchestration_score=orch_score,
        improvements=[],
    )


def make_applied_fix(
    dimension="role_clarity",
    original_state=None,
    modified_state=None,
    fix_id="qfix_test123",
):
    """Create a QualityAppliedFix for testing."""
    return QualityAppliedFix(
        fix_id=fix_id,
        dimension=dimension,
        applied_at=datetime.now(UTC),
        target_component="agent-1",
        original_state=original_state or make_workflow(nodes=[make_agent_node()]),
        modified_state=modified_state or make_workflow(nodes=[make_agent_node()]),
        rollback_available=True,
    )


# ---------------------------------------------------------------------------
# TestQualityFixValidator
# ---------------------------------------------------------------------------

class TestQualityFixValidator:
    """Tests for the QualityFixValidator class."""

    def test_validate_improved_dimension(self):
        """A fix that adds a systemMessage to a bare agent should improve role_clarity."""
        validator = QualityFixValidator()

        # Original: agent with no system message (low role_clarity)
        original_config = make_workflow(nodes=[
            make_agent_node(system_message=""),
        ])
        # Modified: agent with a good system message (higher role_clarity)
        modified_config = make_workflow(nodes=[
            make_agent_node(
                system_message="You are a senior data analyst. Respond with structured JSON."
            ),
        ])

        # Create a report reflecting the poor original state
        original_report = make_report(
            overall_score=0.3,
            agent_dimensions=[
                make_dimension_score("role_clarity", 0.2),
                make_dimension_score("output_consistency", 0.5),
                make_dimension_score("error_handling", 0.3),
                make_dimension_score("tool_usage", 0.3),
                make_dimension_score("config_appropriateness", 0.3),
            ],
        )

        applied_fix = make_applied_fix(
            dimension="role_clarity",
            original_state=original_config,
            modified_state=modified_config,
        )

        result = validator.validate(applied_fix, original_report)

        assert isinstance(result, QualityValidationResult)
        assert result.dimension == "role_clarity"
        # The modified state has a system prompt, so the re-assessed score should be higher
        assert result.after_score > result.before_score
        assert result.improvement > 0
        assert result.success is True

    def test_validate_no_improvement(self):
        """A fix that does not change anything meaningful should return success=False."""
        validator = QualityFixValidator()

        # Both states are identical (no actual change)
        config = make_workflow(nodes=[make_agent_node(system_message="You are a helper.")])

        original_report = make_report(
            overall_score=0.5,
            agent_dimensions=[
                make_dimension_score("role_clarity", 0.5),
                make_dimension_score("output_consistency", 0.5),
                make_dimension_score("error_handling", 0.5),
                make_dimension_score("tool_usage", 0.5),
                make_dimension_score("config_appropriateness", 0.5),
            ],
        )

        applied_fix = make_applied_fix(
            dimension="role_clarity",
            original_state=config,
            modified_state=config,  # same config
        )

        result = validator.validate(applied_fix, original_report)

        assert isinstance(result, QualityValidationResult)
        assert result.dimension == "role_clarity"
        # No improvement since config did not change
        assert result.improvement <= 0
        assert result.success is False

    def test_find_dimension_score_agent(self):
        """_find_dimension_score should find agent-level dimension scores."""
        report = make_report(
            agent_dimensions=[
                make_dimension_score("role_clarity", 0.75),
                make_dimension_score("output_consistency", 0.60),
                make_dimension_score("error_handling", 0.50),
                make_dimension_score("tool_usage", 0.40),
                make_dimension_score("config_appropriateness", 0.80),
            ],
        )

        score = QualityFixValidator._find_dimension_score(report, "role_clarity")
        assert score == 0.75

        score = QualityFixValidator._find_dimension_score(report, "config_appropriateness")
        assert score == 0.80

    def test_find_dimension_score_orchestration(self):
        """_find_dimension_score should find orchestration-level dimension scores."""
        report = make_report(
            orch_dimensions=[
                make_dimension_score("data_flow_clarity", 0.65),
                make_dimension_score("complexity_management", 0.70),
                make_dimension_score("agent_coupling", 0.55),
                make_dimension_score("observability", 0.40),
                make_dimension_score("best_practices", 0.80),
                make_dimension_score("documentation_quality", 0.30),
                make_dimension_score("ai_architecture", 0.50),
                make_dimension_score("maintenance_quality", 0.60),
                make_dimension_score("test_coverage", 0.45),
                make_dimension_score("layout_quality", 0.70),
            ],
        )

        score = QualityFixValidator._find_dimension_score(report, "best_practices")
        assert score == 0.80

        score = QualityFixValidator._find_dimension_score(report, "observability")
        assert score == 0.40

    def test_find_dimension_score_missing(self):
        """_find_dimension_score should return 0.0 for a dimension not in the report."""
        report = make_report()

        score = QualityFixValidator._find_dimension_score(report, "nonexistent_dimension")
        assert score == 0.0

    def test_validate_all(self):
        """validate_all should return a list of QualityValidationResults."""
        validator = QualityFixValidator()

        # Original: bare agent
        original_config = make_workflow(nodes=[
            make_agent_node(system_message=""),
        ])
        # Modified: improved agent
        modified_config = make_workflow(nodes=[
            make_agent_node(
                system_message="You are a senior data analyst. Always respond in JSON."
            ),
        ])

        original_report = make_report(
            overall_score=0.3,
            agent_dimensions=[
                make_dimension_score("role_clarity", 0.2),
                make_dimension_score("output_consistency", 0.3),
                make_dimension_score("error_handling", 0.3),
                make_dimension_score("tool_usage", 0.3),
                make_dimension_score("config_appropriateness", 0.3),
            ],
        )

        fix1 = make_applied_fix(
            dimension="role_clarity",
            original_state=original_config,
            modified_state=modified_config,
            fix_id="qfix_1",
        )
        fix2 = make_applied_fix(
            dimension="output_consistency",
            original_state=original_config,
            modified_state=modified_config,
            fix_id="qfix_2",
        )

        results = validator.validate_all(
            applied_fixes=[fix1, fix2],
            original_report=original_report,
            final_config=modified_config,
        )

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, QualityValidationResult) for r in results)
        assert results[0].dimension == "role_clarity"
        assert results[1].dimension == "output_consistency"

    def test_validator_uses_assessor(self):
        """validate() should internally call QualityAssessor.assess_workflow."""
        validator = QualityFixValidator()

        # We verify the assessor is called by checking that the validator
        # produces a QualityValidationResult with real score data
        config = make_workflow(nodes=[
            make_agent_node(
                system_message="You are a detailed financial analyst. Always provide sources."
            ),
        ])

        original_report = make_report(
            overall_score=0.3,
            agent_dimensions=[
                make_dimension_score("role_clarity", 0.2),
                make_dimension_score("output_consistency", 0.3),
                make_dimension_score("error_handling", 0.3),
                make_dimension_score("tool_usage", 0.3),
                make_dimension_score("config_appropriateness", 0.3),
            ],
        )

        applied_fix = make_applied_fix(
            dimension="role_clarity",
            modified_state=config,
        )

        result = validator.validate(applied_fix, original_report)

        # The result must contain real assessment data from the assessor
        assert isinstance(result, QualityValidationResult)
        assert result.before_score == 0.2  # from original_report
        assert isinstance(result.after_score, float)
        assert 0.0 <= result.after_score <= 1.0
        assert "overall_before" in result.details
        assert "overall_after" in result.details

    def test_validate_returns_correct_detail_keys(self):
        """validate() result details should include overall_before, overall_after, and overall_improvement."""
        validator = QualityFixValidator()

        config = make_workflow(nodes=[make_agent_node()])

        original_report = make_report(overall_score=0.5)
        applied_fix = make_applied_fix(
            dimension="role_clarity",
            modified_state=config,
        )

        result = validator.validate(applied_fix, original_report)

        assert "overall_before" in result.details
        assert "overall_after" in result.details
        assert "overall_improvement" in result.details
        assert result.details["overall_before"] == 0.5

    def test_validate_all_uses_single_assessment(self):
        """validate_all should re-assess the final config only once, not per fix."""
        validator = QualityFixValidator()

        config = make_workflow(nodes=[make_agent_node()])
        original_report = make_report(overall_score=0.4)

        fixes = [
            make_applied_fix(dimension="role_clarity", modified_state=config, fix_id="f1"),
            make_applied_fix(dimension="error_handling", modified_state=config, fix_id="f2"),
            make_applied_fix(dimension="tool_usage", modified_state=config, fix_id="f3"),
        ]

        # Spy on the assessor
        original_assess = validator._assessor.assess_workflow
        call_count = 0

        def counting_assess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_assess(*args, **kwargs)

        validator._assessor.assess_workflow = counting_assess

        results = validator.validate_all(fixes, original_report, config)

        assert len(results) == 3
        # validate_all should call assess_workflow exactly once
        assert call_count == 1

    def test_validate_result_to_dict(self):
        """QualityValidationResult.to_dict() should produce a serializable dict."""
        result = QualityValidationResult(
            success=True,
            dimension="role_clarity",
            before_score=0.3,
            after_score=0.75,
            improvement=0.45,
            details={"overall_before": 0.4, "overall_after": 0.7},
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["dimension"] == "role_clarity"
        assert d["before_score"] == 0.3
        assert d["after_score"] == 0.75
        assert d["improvement"] == 0.45
        assert d["details"]["overall_before"] == 0.4

    def test_validate_multiple_agents_finds_correct_dimension(self):
        """When multiple agents exist, _find_dimension_score returns first match."""
        agent1_dims = [
            make_dimension_score("role_clarity", 0.3),
            make_dimension_score("output_consistency", 0.4),
            make_dimension_score("error_handling", 0.5),
            make_dimension_score("tool_usage", 0.6),
            make_dimension_score("config_appropriateness", 0.7),
        ]
        agent2_dims = [
            make_dimension_score("role_clarity", 0.9),
            make_dimension_score("output_consistency", 0.8),
            make_dimension_score("error_handling", 0.7),
            make_dimension_score("tool_usage", 0.6),
            make_dimension_score("config_appropriateness", 0.5),
        ]
        agent1 = make_agent_score(
            agent_id="a1", agent_name="Agent 1",
            overall_score=0.5, dimensions=agent1_dims,
        )
        agent2 = make_agent_score(
            agent_id="a2", agent_name="Agent 2",
            overall_score=0.7, dimensions=agent2_dims,
        )

        report = QualityReport(
            workflow_id="test-wf",
            workflow_name="Test Workflow",
            overall_score=0.6,
            agent_scores=[agent1, agent2],
            orchestration_score=make_orchestration_score(),
            improvements=[],
        )

        # Should return the first agent's role_clarity score (0.3)
        score = QualityFixValidator._find_dimension_score(report, "role_clarity")
        assert score == 0.3

    def test_validate_orchestration_dimension_fix(self):
        """validate() should work correctly for orchestration-level dimension fixes."""
        validator = QualityFixValidator()

        # Original: workflow with no settings
        original_config = make_workflow(nodes=[make_agent_node()])
        # Modified: workflow with settings added
        modified_config = make_workflow(
            nodes=[make_agent_node()],
            settings={"executionTimeout": 300},
        )

        original_report = make_report(
            overall_score=0.4,
            orch_dimensions=[
                make_dimension_score("data_flow_clarity", 0.5),
                make_dimension_score("complexity_management", 0.5),
                make_dimension_score("agent_coupling", 0.5),
                make_dimension_score("observability", 0.3),
                make_dimension_score("best_practices", 0.3),
                make_dimension_score("documentation_quality", 0.4),
                make_dimension_score("ai_architecture", 0.5),
                make_dimension_score("maintenance_quality", 0.4),
                make_dimension_score("test_coverage", 0.3),
                make_dimension_score("layout_quality", 0.5),
            ],
        )

        applied_fix = make_applied_fix(
            dimension="best_practices",
            original_state=original_config,
            modified_state=modified_config,
        )

        result = validator.validate(applied_fix, original_report)

        assert isinstance(result, QualityValidationResult)
        assert result.dimension == "best_practices"
        assert result.before_score == 0.3
        assert isinstance(result.after_score, float)
