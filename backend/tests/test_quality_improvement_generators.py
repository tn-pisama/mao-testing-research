"""Tests for orchestration improvement generators.

Tests the 7 new orchestration improvement generators in
improvement_suggester.py:
- DataFlowClarityImprovementGenerator
- BestPracticesImprovementGenerator
- DocumentationQualityImprovementGenerator
- AIArchitectureImprovementGenerator
- MaintenanceQualityImprovementGenerator
- TestCoverageImprovementGenerator
- LayoutQualityImprovementGenerator
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality.improvement_suggester import (
    DataFlowClarityImprovementGenerator,
    BestPracticesImprovementGenerator,
    DocumentationQualityImprovementGenerator,
    AIArchitectureImprovementGenerator,
    MaintenanceQualityImprovementGenerator,
    TestCoverageImprovementGenerator,
    LayoutQualityImprovementGenerator,
)
from app.enterprise.quality.models import DimensionScore, OrchestrationDimension


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _orchestration_context(workflow_id="wf-test-001", workflow_name="Test Workflow"):
    """Return a minimal orchestration context dict."""
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
    }


# ---------------------------------------------------------------------------
# 1. DataFlowClarityImprovementGenerator
# ---------------------------------------------------------------------------

class TestDataFlowClarityImprovementGenerator:
    """Tests for DataFlowClarityImprovementGenerator."""

    def test_can_handle(self):
        """Returns True for data_flow_clarity, False for others."""
        gen = DataFlowClarityImprovementGenerator()
        assert gen.can_handle(OrchestrationDimension.DATA_FLOW_CLARITY.value) is True
        assert gen.can_handle(OrchestrationDimension.BEST_PRACTICES.value) is False
        assert gen.can_handle("role_clarity") is False

    def test_generates_improvements_low_score(self):
        """With low score and poor evidence, generates at least 1 improvement."""
        gen = DataFlowClarityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.DATA_FLOW_CLARITY.value,
            score=0.2,
            evidence={
                "connection_coverage": 0.4,
                "state_manipulation_ratio": 0.5,
                "generic_name_ratio": 0.7,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) >= 1
        for imp in improvements:
            assert imp.category == "data_flow_clarity"
            assert imp.title
            assert imp.description

    def test_no_improvements_high_score(self):
        """With high score and good evidence, generates 0 improvements."""
        gen = DataFlowClarityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.DATA_FLOW_CLARITY.value,
            score=0.95,
            evidence={
                "connection_coverage": 0.95,
                "state_manipulation_ratio": 0.1,
                "generic_name_ratio": 0.1,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) == 0


# ---------------------------------------------------------------------------
# 2. BestPracticesImprovementGenerator
# ---------------------------------------------------------------------------

class TestBestPracticesImprovementGenerator:
    """Tests for BestPracticesImprovementGenerator."""

    def test_can_handle(self):
        """Returns True for best_practices, False for others."""
        gen = BestPracticesImprovementGenerator()
        assert gen.can_handle(OrchestrationDimension.BEST_PRACTICES.value) is True
        assert gen.can_handle(OrchestrationDimension.DATA_FLOW_CLARITY.value) is False
        assert gen.can_handle("error_handling") is False

    def test_generates_improvements_low_score(self):
        """With low score and missing best practices, generates at least 1 improvement."""
        gen = BestPracticesImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.BEST_PRACTICES.value,
            score=0.2,
            evidence={
                "error_handler_present": False,
                "error_branch_coverage": 0.0,
                "execution_timeout": None,
                "config_uniformity": 0.3,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) >= 1
        for imp in improvements:
            assert imp.category == "best_practices"
            assert imp.title
            assert imp.description

    def test_no_improvements_high_score(self):
        """With high score and good evidence, generates 0 improvements."""
        gen = BestPracticesImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.BEST_PRACTICES.value,
            score=0.95,
            evidence={
                "error_handler_present": True,
                "error_branch_coverage": 0.9,
                "execution_timeout": 300,
                "config_uniformity": 0.9,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) == 0


# ---------------------------------------------------------------------------
# 3. DocumentationQualityImprovementGenerator
# ---------------------------------------------------------------------------

class TestDocumentationQualityImprovementGenerator:
    """Tests for DocumentationQualityImprovementGenerator."""

    def test_can_handle(self):
        """Returns True for documentation_quality, False for others."""
        gen = DocumentationQualityImprovementGenerator()
        assert gen.can_handle(OrchestrationDimension.DOCUMENTATION_QUALITY.value) is True
        assert gen.can_handle(OrchestrationDimension.OBSERVABILITY.value) is False
        assert gen.can_handle("tool_usage") is False

    def test_generates_improvements_low_score(self):
        """With low score and no documentation, generates at least 1 improvement."""
        gen = DocumentationQualityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.DOCUMENTATION_QUALITY.value,
            score=0.1,
            evidence={
                "sticky_note_count": 0,
                "workflow_description": "",
                "substantive_notes": 0,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) >= 1
        for imp in improvements:
            assert imp.category == "documentation_quality"
            assert imp.title
            assert imp.description

    def test_no_improvements_high_score(self):
        """With high score and good documentation, generates 0 improvements."""
        gen = DocumentationQualityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.DOCUMENTATION_QUALITY.value,
            score=0.95,
            evidence={
                "sticky_note_count": 5,
                "workflow_description": "A comprehensive workflow for processing customer feedback and routing to teams.",
                "substantive_notes": 4,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) == 0


# ---------------------------------------------------------------------------
# 4. AIArchitectureImprovementGenerator
# ---------------------------------------------------------------------------

class TestAIArchitectureImprovementGenerator:
    """Tests for AIArchitectureImprovementGenerator."""

    def test_can_handle(self):
        """Returns True for ai_architecture, False for others."""
        gen = AIArchitectureImprovementGenerator()
        assert gen.can_handle(OrchestrationDimension.AI_ARCHITECTURE.value) is True
        assert gen.can_handle(OrchestrationDimension.COMPLEXITY_MANAGEMENT.value) is False
        assert gen.can_handle("config_appropriateness") is False

    def test_generates_improvements_low_score(self):
        """With low score and architecture issues, generates at least 1 improvement."""
        gen = AIArchitectureImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.AI_ARCHITECTURE.value,
            score=0.25,
            evidence={
                "ai_connection_diversity": 0.2,
                "guardrails_present": False,
                "expensive_models_for_simple_tasks": True,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) >= 1
        for imp in improvements:
            assert imp.category == "ai_architecture"
            assert imp.title
            assert imp.description

    def test_no_improvements_high_score(self):
        """With high score and good architecture, generates 0 improvements."""
        gen = AIArchitectureImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.AI_ARCHITECTURE.value,
            score=0.95,
            evidence={
                "ai_connection_diversity": 0.9,
                "guardrails_present": True,
                "expensive_models_for_simple_tasks": False,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) == 0


# ---------------------------------------------------------------------------
# 5. MaintenanceQualityImprovementGenerator
# ---------------------------------------------------------------------------

class TestMaintenanceQualityImprovementGenerator:
    """Tests for MaintenanceQualityImprovementGenerator."""

    def test_can_handle(self):
        """Returns True for maintenance_quality, False for others."""
        gen = MaintenanceQualityImprovementGenerator()
        assert gen.can_handle(OrchestrationDimension.MAINTENANCE_QUALITY.value) is True
        assert gen.can_handle(OrchestrationDimension.AGENT_COUPLING.value) is False
        assert gen.can_handle("output_consistency") is False

    def test_generates_improvements_low_score(self):
        """With low score and maintenance issues, generates at least 1 improvement."""
        gen = MaintenanceQualityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.MAINTENANCE_QUALITY.value,
            score=0.2,
            evidence={
                "disabled_nodes": 3,
                "outdated_versions": 2,
                "workflow_description": "",
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) >= 1
        for imp in improvements:
            assert imp.category == "maintenance_quality"
            assert imp.title
            assert imp.description

    def test_no_improvements_high_score(self):
        """With high score and clean maintenance, generates 0 improvements."""
        gen = MaintenanceQualityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.MAINTENANCE_QUALITY.value,
            score=0.95,
            evidence={
                "disabled_nodes": 0,
                "outdated_versions": 0,
                "workflow_description": "Well-maintained workflow with up-to-date nodes.",
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) == 0


# ---------------------------------------------------------------------------
# 6. TestCoverageImprovementGenerator
# ---------------------------------------------------------------------------

class TestTestCoverageImprovementGenerator:
    """Tests for TestCoverageImprovementGenerator."""

    def test_can_handle(self):
        """Returns True for test_coverage, False for others."""
        gen = TestCoverageImprovementGenerator()
        assert gen.can_handle(OrchestrationDimension.TEST_COVERAGE.value) is True
        assert gen.can_handle(OrchestrationDimension.LAYOUT_QUALITY.value) is False
        assert gen.can_handle("role_clarity") is False

    def test_generates_improvements_low_score(self):
        """With low score and no test coverage, generates at least 1 improvement."""
        gen = TestCoverageImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.TEST_COVERAGE.value,
            score=0.1,
            evidence={
                "test_coverage_ratio": 0,
                "critical_nodes_unpinned": ["AI Agent", "HTTP Request"],
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) >= 1
        for imp in improvements:
            assert imp.category == "test_coverage"
            assert imp.title
            assert imp.description

    def test_no_improvements_high_score(self):
        """With high score and full test coverage, generates 0 improvements."""
        gen = TestCoverageImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.TEST_COVERAGE.value,
            score=0.95,
            evidence={
                "test_coverage_ratio": 1.0,
                "critical_nodes_unpinned": [],
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) == 0


# ---------------------------------------------------------------------------
# 7. LayoutQualityImprovementGenerator
# ---------------------------------------------------------------------------

class TestLayoutQualityImprovementGenerator:
    """Tests for LayoutQualityImprovementGenerator."""

    def test_can_handle(self):
        """Returns True for layout_quality, False for others."""
        gen = LayoutQualityImprovementGenerator()
        assert gen.can_handle(OrchestrationDimension.LAYOUT_QUALITY.value) is True
        assert gen.can_handle(OrchestrationDimension.TEST_COVERAGE.value) is False
        assert gen.can_handle("error_handling") is False

    def test_generates_improvements_low_score(self):
        """With low score and layout issues, generates at least 1 improvement."""
        gen = LayoutQualityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.LAYOUT_QUALITY.value,
            score=0.2,
            evidence={
                "overlapping_nodes": 4,
                "alignment_score": 0.2,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) >= 1
        for imp in improvements:
            assert imp.category == "layout_quality"
            assert imp.title
            assert imp.description

    def test_no_improvements_high_score(self):
        """With high score and good layout, generates 0 improvements."""
        gen = LayoutQualityImprovementGenerator()
        score = DimensionScore(
            dimension=OrchestrationDimension.LAYOUT_QUALITY.value,
            score=0.95,
            evidence={
                "overlapping_nodes": 0,
                "alignment_score": 0.95,
            },
        )
        improvements = gen.generate(score, _orchestration_context())
        assert len(improvements) == 0
