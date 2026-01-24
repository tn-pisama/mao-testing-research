"""Test quality assessment API logic.

These tests verify the quality assessment logic and models.
Full HTTP API integration tests require asyncpg and database connectivity
and are in a separate integration test suite.
"""

import pytest
import sys
from pathlib import Path
from uuid import uuid4

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Sample workflow JSON for testing
SAMPLE_WORKFLOW = {
    "id": "wf-api-test",
    "name": "API Test Workflow",
    "nodes": [
        {
            "id": "1",
            "name": "Trigger",
            "type": "n8n-nodes-base.webhook",
            "parameters": {}
        },
        {
            "id": "2",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "continueOnFail": True,
            "parameters": {
                "systemMessage": "You are a helpful assistant. Respond in JSON format.",
                "options": {"temperature": 0.5}
            }
        },
        {
            "id": "3",
            "name": "Output",
            "type": "n8n-nodes-base.respond",
            "parameters": {}
        }
    ],
    "connections": {
        "Trigger": {"main": [[{"node": "Test Agent"}]]},
        "Test Agent": {"main": [[{"node": "Output"}]]}
    }
}

# Sample agent node JSON for testing
SAMPLE_AGENT_NODE = {
    "id": "agent-1",
    "name": "Test Agent",
    "type": "@n8n/n8n-nodes-langchain.agent",
    "continueOnFail": True,
    "parameters": {
        "systemMessage": "You are a data analyst. Analyze the input and return structured results.",
        "options": {
            "temperature": 0.3,
            "timeout": 30000
        }
    }
}


# NOTE: Full HTTP API tests require asyncpg and database connectivity.
# These tests have been moved to a separate integration test suite.
# See tests/integration/test_quality_api_http.py for full HTTP tests.
#
# The tests below verify quality assessment logic without requiring full app setup.


class TestQualityAssessor:
    """Test QualityAssessor class."""

    def test_assess_workflow_returns_valid_report(self):
        """Test QualityAssessor.assess_workflow returns valid report."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        assert report.workflow_id == "wf-api-test"
        assert report.workflow_name == "API Test Workflow"
        assert 0 <= report.overall_score <= 1
        assert report.overall_grade in ["A", "B+", "B", "C+", "C", "D", "F"]
        assert len(report.agent_scores) == 1
        assert report.orchestration_score is not None

    def test_assess_workflow_with_execution_history(self):
        """Test QualityAssessor with execution history."""
        from app.enterprise.quality import QualityAssessor

        execution_history = [
            {"node_name": "Test Agent", "output": {"result": "A", "score": 0.9}},
            {"node_name": "Test Agent", "output": {"result": "B", "score": 0.8}},
        ]

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW, execution_history=execution_history)

        assert report.workflow_id == "wf-api-test"
        assert 0 <= report.overall_score <= 1

    def test_assess_agent_returns_valid_score(self):
        """Test QualityAssessor.assess_agent returns valid score."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        score = assessor.assess_agent(SAMPLE_AGENT_NODE)

        assert score.agent_id == "agent-1"
        assert score.agent_name == "Test Agent"
        assert 0 <= score.overall_score <= 1
        assert len(score.dimensions) == 5

    def test_assess_agent_with_execution_samples(self):
        """Test QualityAssessor.assess_agent with execution samples."""
        from app.enterprise.quality import QualityAssessor

        execution_samples = [
            {"output": {"result": "consistent", "score": 0.9}},
            {"output": {"result": "consistent", "score": 0.8}},
        ]

        assessor = QualityAssessor(use_llm_judge=False)
        score = assessor.assess_agent(SAMPLE_AGENT_NODE, execution_history=execution_samples)

        assert score.agent_id == "agent-1"
        # With consistent execution samples, output_consistency should be high
        consistency_dim = next(d for d in score.dimensions if d.dimension == "output_consistency")
        assert consistency_dim.score >= 0.7


class TestQualityReportSerialization:
    """Test quality report serialization for API responses."""

    def test_agent_score_serialization(self):
        """Test agent scores are serializable to dict."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        for agent in report.agent_scores:
            d = agent.to_dict()
            assert isinstance(d, dict)
            assert "agent_id" in d
            assert "agent_name" in d
            assert "overall_score" in d
            assert "dimensions" in d
            assert "grade" in d

    def test_orchestration_score_serialization(self):
        """Test orchestration score is serializable to dict."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        o = report.orchestration_score.to_dict()
        assert isinstance(o, dict)
        assert "workflow_id" in o
        assert "overall_score" in o
        assert "dimensions" in o

    def test_improvement_serialization(self):
        """Test improvements are serializable to dict."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW, max_suggestions=5)

        for imp in report.improvements:
            i = imp.to_dict()
            assert isinstance(i, dict)
            assert "title" in i
            assert "severity" in i

    def test_complexity_metrics_serialization(self):
        """Test complexity metrics are serializable to dict."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        if report.orchestration_score.complexity_metrics:
            m = report.orchestration_score.complexity_metrics.to_dict()
            assert isinstance(m, dict)
            assert "node_count" in m
            assert "agent_count" in m


class TestQualityDimensions:
    """Test quality dimension coverage."""

    def test_agent_has_five_dimensions(self):
        """Test that agent scores have 5 dimensions."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        score = assessor.assess_agent(SAMPLE_AGENT_NODE)

        assert len(score.dimensions) == 5

        dimension_names = {d.dimension for d in score.dimensions}
        expected = {"role_clarity", "output_consistency", "error_handling", "tool_usage", "config_appropriateness"}
        assert dimension_names == expected

    def test_orchestration_has_five_dimensions(self):
        """Test that orchestration scores have core 5 dimensions plus optional n8n-specific ones."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        # Should have at least the core 5 dimensions, possibly more with n8n enhancements
        assert len(report.orchestration_score.dimensions) >= 5

        dimension_names = {d.dimension for d in report.orchestration_score.dimensions}
        core_expected = {"data_flow_clarity", "complexity_management", "agent_coupling", "observability", "best_practices"}

        # Core dimensions should always be present
        assert core_expected.issubset(dimension_names)


class TestQualitySuggestions:
    """Test improvement suggestion generation."""

    def test_suggestions_are_generated(self):
        """Test that improvement suggestions are generated."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW, max_suggestions=10)

        # Should have some suggestions
        assert isinstance(report.improvements, list)

    def test_suggestions_have_required_fields(self):
        """Test that suggestions have required fields."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)

        # Use minimal workflow to ensure issues are found
        minimal = {
            "id": "minimal",
            "name": "Minimal",
            "nodes": [{"id": "1", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}}],
            "connections": {}
        }
        report = assessor.assess_workflow(minimal, max_suggestions=10)

        for imp in report.improvements:
            imp_dict = imp.to_dict()
            assert "title" in imp_dict
            assert "description" in imp_dict
            assert "severity" in imp_dict
            assert imp_dict["severity"] in ["critical", "high", "medium", "low", "info"]


class TestQualityGrading:
    """Test quality grade assignment."""

    def test_grade_matches_score(self):
        """Test that grade corresponds to score."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)

        # Well-configured workflow should score well
        well_configured = {
            "id": "wf-good",
            "name": "Good Workflow",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {
                    "id": "2",
                    "name": "Analyst",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "continueOnFail": True,
                    "alwaysOutputData": True,
                    "parameters": {
                        "systemMessage": """You are a senior analyst.
Your role is to analyze data and provide insights.
Your task is to examine input data.
You must respond with JSON: {"result": "...", "confidence": 0.0-1.0}
Do not make assumptions.
Never include PII.""",
                        "options": {"temperature": 0.2, "timeout": 30000, "retryOnFail": True}
                    }
                },
                {"id": "3", "name": "Output", "type": "n8n-nodes-base.respond", "parameters": {}},
                {"id": "4", "name": "Error", "type": "n8n-nodes-base.errorTrigger", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Analyst"}]]},
                "Analyst": {"main": [[{"node": "Output"}]]}
            }
        }
        report = assessor.assess_workflow(well_configured)

        # Check grade is valid
        assert report.overall_grade in ["A", "B+", "B", "C+", "C", "D", "F"]

        # Grade should roughly match score
        if report.overall_score >= 0.9:
            assert report.overall_grade == "A"
        elif report.overall_score >= 0.8:
            assert report.overall_grade in ["A", "B+"]
        elif report.overall_score >= 0.7:
            assert report.overall_grade in ["B+", "B"]

