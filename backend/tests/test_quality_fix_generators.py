"""Tests for per-dimension quality fix generators.

Tests the 15 fix generators across agent and orchestration dimensions:

Agent fixes (agent_fixes.py):
- RoleClarityFixGenerator
- OutputConsistencyFixGenerator
- ErrorHandlingFixGenerator
- ToolUsageFixGenerator
- ConfigAppropriatenessFixGenerator

Orchestration fixes (orchestration_fixes.py):
- DataFlowClarityFixGenerator
- ComplexityManagementFixGenerator
- AgentCouplingFixGenerator
- ObservabilityFixGenerator
- BestPracticesFixGenerator
- DocumentationQualityFixGenerator
- AIArchitectureFixGenerator
- MaintenanceQualityFixGenerator
- TestCoverageFixGenerator
- LayoutQualityFixGenerator
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality.healing.agent_fixes import (
    RoleClarityFixGenerator,
    OutputConsistencyFixGenerator,
    ErrorHandlingFixGenerator,
    ToolUsageFixGenerator,
    ConfigAppropriatenessFixGenerator,
)
from app.enterprise.quality.healing.orchestration_fixes import (
    DataFlowClarityFixGenerator,
    ComplexityManagementFixGenerator,
    AgentCouplingFixGenerator,
    ObservabilityFixGenerator,
    BestPracticesFixGenerator,
    DocumentationQualityFixGenerator,
    AIArchitectureFixGenerator,
    MaintenanceQualityFixGenerator,
    TestCoverageFixGenerator,
    LayoutQualityFixGenerator,
)
from app.enterprise.quality.models import DimensionScore
from app.enterprise.quality.healing.models import QualityFixSuggestion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_context(
    agent_id="agent-001",
    agent_name="Test Agent",
    agent_type="agent",
    workflow_id="wf-test-001",
):
    """Return a minimal agent context dict."""
    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "agent_type": agent_type,
        "workflow_id": workflow_id,
    }


def _orchestration_context(
    workflow_id="wf-test-001",
    workflow_name="Test Workflow",
):
    """Return a minimal orchestration context dict."""
    return {
        "target_type": "orchestration",
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
    }


def _assert_fix_structure(fix: QualityFixSuggestion):
    """Verify a fix has all required structural fields."""
    assert fix.id, "Fix must have a non-empty id"
    assert fix.dimension, "Fix must have a dimension"
    assert fix.category is not None, "Fix must have a category"
    assert isinstance(fix.changes, dict), "Fix changes must be a dict"
    assert len(fix.changes) > 0, "Fix changes must be non-empty"
    assert fix.title, "Fix must have a title"
    assert fix.description, "Fix must have a description"
    assert fix.confidence > 0, "Fix confidence must be > 0"
    assert fix.expected_improvement > 0, "Fix expected_improvement must be > 0"


# ===========================================================================
# Agent Fix Generators
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. RoleClarityFixGenerator
# ---------------------------------------------------------------------------

class TestRoleClarityFixGenerator:
    """Tests for RoleClarityFixGenerator."""

    def test_can_handle(self):
        """Returns True for role_clarity, False for others."""
        gen = RoleClarityFixGenerator()
        assert gen.can_handle("role_clarity") is True
        assert gen.can_handle("error_handling") is False
        assert gen.can_handle("data_flow_clarity") is False

    def test_generates_fixes(self):
        """With low score, generates fixes with changes dict, title, description."""
        gen = RoleClarityFixGenerator()
        score = DimensionScore(
            dimension="role_clarity",
            score=0.3,
            evidence={
                "has_role_definition": False,
                "has_output_format": False,
                "has_boundaries": False,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = RoleClarityFixGenerator()
        score = DimensionScore(
            dimension="role_clarity",
            score=0.3,
            evidence={
                "has_role_definition": False,
                "has_output_format": False,
                "has_boundaries": False,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "role_clarity"


# ---------------------------------------------------------------------------
# 2. OutputConsistencyFixGenerator
# ---------------------------------------------------------------------------

class TestOutputConsistencyFixGenerator:
    """Tests for OutputConsistencyFixGenerator."""

    def test_can_handle(self):
        """Returns True for output_consistency, False for others."""
        gen = OutputConsistencyFixGenerator()
        assert gen.can_handle("output_consistency") is True
        assert gen.can_handle("role_clarity") is False
        assert gen.can_handle("best_practices") is False

    def test_generates_fixes(self):
        """With low score, generates fixes with changes dict, title, description."""
        gen = OutputConsistencyFixGenerator()
        score = DimensionScore(
            dimension="output_consistency",
            score=0.3,
            evidence={
                "has_output_schema": False,
                "format_variance": 0.5,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = OutputConsistencyFixGenerator()
        score = DimensionScore(
            dimension="output_consistency",
            score=0.3,
            evidence={
                "has_output_schema": False,
                "format_variance": 0.5,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "output_consistency"


# ---------------------------------------------------------------------------
# 3. ErrorHandlingFixGenerator
# ---------------------------------------------------------------------------

class TestErrorHandlingFixGenerator:
    """Tests for ErrorHandlingFixGenerator."""

    def test_can_handle(self):
        """Returns True for error_handling, False for others."""
        gen = ErrorHandlingFixGenerator()
        assert gen.can_handle("error_handling") is True
        assert gen.can_handle("tool_usage") is False
        assert gen.can_handle("observability") is False

    def test_generates_fixes(self):
        """With low score, generates fixes with changes dict, title, description."""
        gen = ErrorHandlingFixGenerator()
        score = DimensionScore(
            dimension="error_handling",
            score=0.3,
            evidence={
                "has_continue_on_fail": False,
                "has_retry": False,
                "has_timeout": False,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = ErrorHandlingFixGenerator()
        score = DimensionScore(
            dimension="error_handling",
            score=0.3,
            evidence={
                "has_continue_on_fail": False,
                "has_retry": False,
                "has_timeout": False,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "error_handling"


# ---------------------------------------------------------------------------
# 4. ToolUsageFixGenerator
# ---------------------------------------------------------------------------

class TestToolUsageFixGenerator:
    """Tests for ToolUsageFixGenerator."""

    def test_can_handle(self):
        """Returns True for tool_usage, False for others."""
        gen = ToolUsageFixGenerator()
        assert gen.can_handle("tool_usage") is True
        assert gen.can_handle("config_appropriateness") is False
        assert gen.can_handle("layout_quality") is False

    def test_generates_fixes(self):
        """With low score, generates fixes with changes dict, title, description."""
        gen = ToolUsageFixGenerator()
        score = DimensionScore(
            dimension="tool_usage",
            score=0.3,
            evidence={
                "tools_missing_descriptions": 3,
                "has_tool_descriptions": False,
                "tools_missing_schemas": 2,
                "has_parameter_schemas": False,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = ToolUsageFixGenerator()
        score = DimensionScore(
            dimension="tool_usage",
            score=0.3,
            evidence={
                "tools_missing_descriptions": 3,
                "has_tool_descriptions": False,
                "tools_missing_schemas": 2,
                "has_parameter_schemas": False,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "tool_usage"


# ---------------------------------------------------------------------------
# 5. ConfigAppropriatenessFixGenerator
# ---------------------------------------------------------------------------

class TestConfigAppropriatenessFixGenerator:
    """Tests for ConfigAppropriatenessFixGenerator."""

    def test_can_handle(self):
        """Returns True for config_appropriateness, False for others."""
        gen = ConfigAppropriatenessFixGenerator()
        assert gen.can_handle("config_appropriateness") is True
        assert gen.can_handle("role_clarity") is False
        assert gen.can_handle("ai_architecture") is False

    def test_generates_fixes(self):
        """With low score, generates fixes with changes dict, title, description."""
        gen = ConfigAppropriatenessFixGenerator()
        score = DimensionScore(
            dimension="config_appropriateness",
            score=0.3,
            evidence={
                "temperature_issue": True,
                "temperature": None,
                "max_tokens_issue": True,
                "max_tokens": None,
                "model_issue": True,
                "model": None,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = ConfigAppropriatenessFixGenerator()
        score = DimensionScore(
            dimension="config_appropriateness",
            score=0.3,
            evidence={
                "temperature_issue": True,
                "temperature": None,
                "max_tokens_issue": True,
                "max_tokens": None,
                "model_issue": True,
                "model": None,
            },
        )
        fixes = gen.generate_fixes(score, _agent_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "config_appropriateness"


# ===========================================================================
# Orchestration Fix Generators
# ===========================================================================


# ---------------------------------------------------------------------------
# 6. DataFlowClarityFixGenerator
# ---------------------------------------------------------------------------

class TestDataFlowClarityFixGenerator:
    """Tests for DataFlowClarityFixGenerator."""

    def test_can_handle(self):
        """Returns True for data_flow_clarity, False for others."""
        gen = DataFlowClarityFixGenerator()
        assert gen.can_handle("data_flow_clarity") is True
        assert gen.can_handle("complexity_management") is False
        assert gen.can_handle("role_clarity") is False

    def test_generates_fixes(self):
        """With low score, generates fixes with changes dict, title, description."""
        gen = DataFlowClarityFixGenerator()
        score = DimensionScore(
            dimension="data_flow_clarity",
            score=0.3,
            evidence={
                "generic_name_ratio": 0.6,
                "connection_coverage": 0.4,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = DataFlowClarityFixGenerator()
        score = DimensionScore(
            dimension="data_flow_clarity",
            score=0.3,
            evidence={
                "generic_name_ratio": 0.6,
                "connection_coverage": 0.4,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "data_flow_clarity"


# ---------------------------------------------------------------------------
# 7. ComplexityManagementFixGenerator
# ---------------------------------------------------------------------------

class TestComplexityManagementFixGenerator:
    """Tests for ComplexityManagementFixGenerator."""

    def test_can_handle(self):
        """Returns True for complexity_management, False for others."""
        gen = ComplexityManagementFixGenerator()
        assert gen.can_handle("complexity_management") is True
        assert gen.can_handle("agent_coupling") is False
        assert gen.can_handle("error_handling") is False

    def test_generates_fixes(self):
        """With low score and high complexity, generates fixes with changes dict."""
        gen = ComplexityManagementFixGenerator()
        score = DimensionScore(
            dimension="complexity_management",
            score=0.3,
            evidence={
                "node_count": 25,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = ComplexityManagementFixGenerator()
        score = DimensionScore(
            dimension="complexity_management",
            score=0.3,
            evidence={
                "node_count": 25,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "complexity_management"


# ---------------------------------------------------------------------------
# 8. AgentCouplingFixGenerator
# ---------------------------------------------------------------------------

class TestAgentCouplingFixGenerator:
    """Tests for AgentCouplingFixGenerator."""

    def test_can_handle(self):
        """Returns True for agent_coupling, False for others."""
        gen = AgentCouplingFixGenerator()
        assert gen.can_handle("agent_coupling") is True
        assert gen.can_handle("observability") is False
        assert gen.can_handle("tool_usage") is False

    def test_generates_fixes(self):
        """With low score and high coupling, generates fixes with changes dict."""
        gen = AgentCouplingFixGenerator()
        score = DimensionScore(
            dimension="agent_coupling",
            score=0.3,
            evidence={
                "coupling_ratio": 0.8,
                "max_agent_chain": 6,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = AgentCouplingFixGenerator()
        score = DimensionScore(
            dimension="agent_coupling",
            score=0.3,
            evidence={
                "coupling_ratio": 0.8,
                "max_agent_chain": 6,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "agent_coupling"


# ---------------------------------------------------------------------------
# 9. ObservabilityFixGenerator
# ---------------------------------------------------------------------------

class TestObservabilityFixGenerator:
    """Tests for ObservabilityFixGenerator."""

    def test_can_handle(self):
        """Returns True for observability, False for others."""
        gen = ObservabilityFixGenerator()
        assert gen.can_handle("observability") is True
        assert gen.can_handle("best_practices") is False
        assert gen.can_handle("output_consistency") is False

    def test_generates_fixes(self):
        """With low score and no observability, generates fixes with changes dict."""
        gen = ObservabilityFixGenerator()
        score = DimensionScore(
            dimension="observability",
            score=0.3,
            evidence={
                "observability_nodes": 0,
                "error_triggers": 0,
                "monitoring_webhooks": 0,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = ObservabilityFixGenerator()
        score = DimensionScore(
            dimension="observability",
            score=0.3,
            evidence={
                "observability_nodes": 0,
                "error_triggers": 0,
                "monitoring_webhooks": 0,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "observability"


# ---------------------------------------------------------------------------
# 10. BestPracticesFixGenerator
# ---------------------------------------------------------------------------

class TestBestPracticesFixGenerator:
    """Tests for BestPracticesFixGenerator."""

    def test_can_handle(self):
        """Returns True for best_practices, False for others."""
        gen = BestPracticesFixGenerator()
        assert gen.can_handle("best_practices") is True
        assert gen.can_handle("documentation_quality") is False
        assert gen.can_handle("role_clarity") is False

    def test_generates_fixes(self):
        """With low score and missing practices, generates fixes with changes dict."""
        gen = BestPracticesFixGenerator()
        score = DimensionScore(
            dimension="best_practices",
            score=0.3,
            evidence={
                "error_handler_present": False,
                "execution_timeout": None,
                "config_uniformity": 0.3,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = BestPracticesFixGenerator()
        score = DimensionScore(
            dimension="best_practices",
            score=0.3,
            evidence={
                "error_handler_present": False,
                "execution_timeout": None,
                "config_uniformity": 0.3,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "best_practices"


# ---------------------------------------------------------------------------
# 11. DocumentationQualityFixGenerator
# ---------------------------------------------------------------------------

class TestDocumentationQualityFixGenerator:
    """Tests for DocumentationQualityFixGenerator."""

    def test_can_handle(self):
        """Returns True for documentation_quality, False for others."""
        gen = DocumentationQualityFixGenerator()
        assert gen.can_handle("documentation_quality") is True
        assert gen.can_handle("ai_architecture") is False
        assert gen.can_handle("error_handling") is False

    def test_generates_fixes(self):
        """With low score and missing docs, generates fixes with changes dict."""
        gen = DocumentationQualityFixGenerator()
        score = DimensionScore(
            dimension="documentation_quality",
            score=0.3,
            evidence={
                "has_description": False,
                "sticky_note_count": 0,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = DocumentationQualityFixGenerator()
        score = DimensionScore(
            dimension="documentation_quality",
            score=0.3,
            evidence={
                "has_description": False,
                "sticky_note_count": 0,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "documentation_quality"


# ---------------------------------------------------------------------------
# 12. AIArchitectureFixGenerator
# ---------------------------------------------------------------------------

class TestAIArchitectureFixGenerator:
    """Tests for AIArchitectureFixGenerator."""

    def test_can_handle(self):
        """Returns True for ai_architecture, False for others."""
        gen = AIArchitectureFixGenerator()
        assert gen.can_handle("ai_architecture") is True
        assert gen.can_handle("maintenance_quality") is False
        assert gen.can_handle("config_appropriateness") is False

    def test_generates_fixes(self):
        """With low score and architecture issues, generates fixes with changes dict."""
        gen = AIArchitectureFixGenerator()
        score = DimensionScore(
            dimension="ai_architecture",
            score=0.3,
            evidence={
                "ai_agent_count": 3,
                "has_output_validation": False,
                "ai_connection_diversity": 0.2,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = AIArchitectureFixGenerator()
        score = DimensionScore(
            dimension="ai_architecture",
            score=0.3,
            evidence={
                "ai_agent_count": 3,
                "has_output_validation": False,
                "ai_connection_diversity": 0.2,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "ai_architecture"


# ---------------------------------------------------------------------------
# 13. MaintenanceQualityFixGenerator
# ---------------------------------------------------------------------------

class TestMaintenanceQualityFixGenerator:
    """Tests for MaintenanceQualityFixGenerator."""

    def test_can_handle(self):
        """Returns True for maintenance_quality, False for others."""
        gen = MaintenanceQualityFixGenerator()
        assert gen.can_handle("maintenance_quality") is True
        assert gen.can_handle("test_coverage") is False
        assert gen.can_handle("output_consistency") is False

    def test_generates_fixes(self):
        """With low score and maintenance issues, generates fixes with changes dict."""
        gen = MaintenanceQualityFixGenerator()
        score = DimensionScore(
            dimension="maintenance_quality",
            score=0.3,
            evidence={
                "disabled_nodes": 3,
                "outdated_versions": 2,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = MaintenanceQualityFixGenerator()
        score = DimensionScore(
            dimension="maintenance_quality",
            score=0.3,
            evidence={
                "disabled_nodes": 3,
                "outdated_versions": 2,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "maintenance_quality"


# ---------------------------------------------------------------------------
# 14. TestCoverageFixGenerator
# ---------------------------------------------------------------------------

class TestTestCoverageFixGenerator:
    """Tests for TestCoverageFixGenerator."""

    def test_can_handle(self):
        """Returns True for test_coverage, False for others."""
        gen = TestCoverageFixGenerator()
        assert gen.can_handle("test_coverage") is True
        assert gen.can_handle("layout_quality") is False
        assert gen.can_handle("role_clarity") is False

    def test_generates_fixes(self):
        """With low score and zero coverage, generates fixes with changes dict."""
        gen = TestCoverageFixGenerator()
        score = DimensionScore(
            dimension="test_coverage",
            score=0.3,
            evidence={
                "test_coverage_ratio": 0,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = TestCoverageFixGenerator()
        score = DimensionScore(
            dimension="test_coverage",
            score=0.3,
            evidence={
                "test_coverage_ratio": 0,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "test_coverage"


# ---------------------------------------------------------------------------
# 15. LayoutQualityFixGenerator
# ---------------------------------------------------------------------------

class TestLayoutQualityFixGenerator:
    """Tests for LayoutQualityFixGenerator."""

    def test_can_handle(self):
        """Returns True for layout_quality, False for others."""
        gen = LayoutQualityFixGenerator()
        assert gen.can_handle("layout_quality") is True
        assert gen.can_handle("data_flow_clarity") is False
        assert gen.can_handle("error_handling") is False

    def test_generates_fixes(self):
        """With low score and layout issues, generates fixes with changes dict."""
        gen = LayoutQualityFixGenerator()
        score = DimensionScore(
            dimension="layout_quality",
            score=0.3,
            evidence={
                "overlapping_nodes": 4,
                "alignment_score": 0.2,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            assert isinstance(fix.changes, dict)
            assert len(fix.changes) > 0
            assert fix.title
            assert fix.description

    def test_fix_structure(self):
        """Each fix has id, dimension, category, changes, confidence, expected_improvement."""
        gen = LayoutQualityFixGenerator()
        score = DimensionScore(
            dimension="layout_quality",
            score=0.3,
            evidence={
                "overlapping_nodes": 4,
                "alignment_score": 0.2,
            },
        )
        fixes = gen.generate_fixes(score, _orchestration_context())
        assert len(fixes) >= 1
        for fix in fixes:
            _assert_fix_structure(fix)
            assert fix.dimension == "layout_quality"
