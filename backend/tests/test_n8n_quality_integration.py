"""Quality assessment integration tests.

Tests quality assessment logic for n8n workflows.
Full HTTP webhook integration tests require asyncpg and database connectivity
and are in a separate integration test suite.
"""

import pytest
import sys
from pathlib import Path
from uuid import uuid4

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Sample workflow JSON for quality assessment tests
SAMPLE_WORKFLOW = {
    "id": "wf-quality-test",
    "name": "Quality Test Workflow",
    "nodes": [
        {
            "id": "1",
            "name": "Trigger",
            "type": "n8n-nodes-base.webhook",
            "parameters": {}
        },
        {
            "id": "2",
            "name": "Analyst Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "continueOnFail": True,
            "parameters": {
                "systemMessage": "You are a data analyst. Analyze the input and return JSON.",
                "options": {
                    "temperature": 0.3,
                    "timeout": 30000,
                    "retryOnFail": True
                }
            }
        },
        {
            "id": "3",
            "name": "Output",
            "type": "n8n-nodes-base.respond",
            "parameters": {}
        },
        {
            "id": "4",
            "name": "Error Handler",
            "type": "n8n-nodes-base.errorTrigger",
            "parameters": {}
        }
    ],
    "connections": {
        "Trigger": {"main": [[{"node": "Analyst Agent"}]]},
        "Analyst Agent": {"main": [[{"node": "Output"}]]}
    }
}


# NOTE: Full HTTP webhook integration tests require asyncpg and database connectivity.
# These tests have been moved to a separate integration test suite.
# See tests/integration/test_n8n_quality_webhook.py for full HTTP tests.
#
# The tests below verify quality assessment logic without requiring full app setup.


class TestQualityAssessmentBackgroundTask:
    """Test the background task for quality assessment."""

    def test_quality_assessor_creates_valid_report(self):
        """Test that QualityAssessor creates valid assessment reports."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        # Verify report structure is valid for database storage
        assert report.workflow_id == "wf-quality-test"
        assert 0 <= report.overall_score <= 1
        assert report.overall_grade in ["Healthy", "Good", "Needs Attention", "Needs Data", "At Risk", "Critical"]

        # Verify serialization works (used in background task)
        for agent in report.agent_scores:
            agent_dict = agent.to_dict()
            assert isinstance(agent_dict, dict)
            assert "agent_id" in agent_dict

        orch_dict = report.orchestration_score.to_dict()
        assert isinstance(orch_dict, dict)
        assert "dimensions" in orch_dict

    def test_quality_report_serialization(self):
        """Test that quality report can be serialized for database storage."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        # Simulate what background task does
        score_as_int = int(report.overall_score * 100)
        assert 0 <= score_as_int <= 100

        # Verify complexity metrics serialization
        if report.orchestration_score.complexity_metrics:
            metrics_dict = report.orchestration_score.complexity_metrics.to_dict()
            assert isinstance(metrics_dict, dict)
            assert "node_count" in metrics_dict


class TestQualityAssessmentDirectScoring:
    """Test quality assessment scoring directly (without HTTP layer)."""

    def test_sample_workflow_scores_reasonably(self):
        """Test that the sample workflow gets a reasonable quality score."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW, max_suggestions=5)

        # Sample workflow has some good practices
        assert 0.4 <= report.overall_score <= 0.9
        assert report.overall_grade in ["Healthy", "Good", "Needs Attention", "Needs Data", "At Risk"]

        # Should have 1 agent
        assert len(report.agent_scores) == 1

        # Agent should have reasonable score (has prompt, config, error handling)
        assert report.agent_scores[0].overall_score >= 0.5

        # Orchestration should have reasonable score
        assert report.orchestration_score.overall_score >= 0.4

    def test_minimal_workflow_scores_lower(self):
        """Test that a minimal workflow scores lower."""
        from app.enterprise.quality import QualityAssessor

        minimal_workflow = {
            "id": "wf-minimal",
            "name": "Minimal",
            "nodes": [
                {
                    "id": "1",
                    "name": "Agent",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {}
                }
            ],
            "connections": {}
        }

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(minimal_workflow)

        # Minimal workflow should score lower
        assert report.overall_score < 0.7
        assert report.agent_scores[0].overall_score < 0.5

        # Should have issues flagged
        assert report.total_issues > 0

    def test_well_configured_workflow_scores_high(self):
        """Test that a well-configured workflow scores high."""
        from app.enterprise.quality import QualityAssessor

        well_configured = {
            "id": "wf-excellent",
            "name": "Excellent Workflow",
            "nodes": [
                {
                    "id": "1",
                    "name": "Webhook Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {}
                },
                {
                    "id": "2",
                    "name": "Data Analyst",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "continueOnFail": True,
                    "alwaysOutputData": True,
                    "parameters": {
                        "systemMessage": """You are a senior data analyst specializing in business intelligence.
Your role is to analyze data and provide actionable insights.
Your task is to examine the provided dataset and identify trends.

You must respond with a JSON object in this format:
{
  "summary": "Brief analysis summary",
  "insights": ["insight 1", "insight 2"],
  "confidence": 0.0-1.0
}

Do not make assumptions about missing data.
Only respond to data analysis requests.""",
                        "options": {
                            "temperature": 0.2,
                            "timeout": 60000,
                            "retryOnFail": True,
                            "maxRetries": 3
                        },
                        "tools": [
                            {
                                "name": "search_data",
                                "description": "Search the data warehouse for relevant datasets",
                                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
                            }
                        ]
                    }
                },
                {
                    "id": "3",
                    "name": "Checkpoint",
                    "type": "n8n-nodes-base.set",
                    "parameters": {}
                },
                {
                    "id": "4",
                    "name": "Send Response",
                    "type": "n8n-nodes-base.respond",
                    "parameters": {}
                },
                {
                    "id": "5",
                    "name": "Error Handler",
                    "type": "n8n-nodes-base.errorTrigger",
                    "parameters": {}
                }
            ],
            "connections": {
                "Webhook Trigger": {"main": [[{"node": "Data Analyst"}]]},
                "Data Analyst": {"main": [[{"node": "Checkpoint"}]]},
                "Checkpoint": {"main": [[{"node": "Send Response"}]]}
            },
            "settings": {
                "saveManualExecutions": True,
                "saveDataErrorExecution": "all"
            }
        }

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(well_configured)

        # Well-configured workflow should score well
        assert report.overall_score >= 0.6
        assert report.agent_scores[0].overall_score >= 0.7

    def test_quality_report_structure(self):
        """Test that quality report has correct structure."""
        from app.enterprise.quality import QualityAssessor

        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(SAMPLE_WORKFLOW)

        # Check report fields
        assert report.workflow_id == "wf-quality-test"
        assert report.workflow_name == "Quality Test Workflow"
        assert 0 <= report.overall_score <= 1
        assert report.overall_grade in ["Healthy", "Good", "Needs Attention", "Needs Data", "At Risk", "Critical"]
        assert isinstance(report.agent_scores, list)
        assert report.orchestration_score is not None
        assert isinstance(report.improvements, list)
        assert isinstance(report.summary, str)
        assert report.generated_at is not None

        # Check agent score structure
        if report.agent_scores:
            agent = report.agent_scores[0]
            assert agent.agent_id is not None
            assert agent.agent_name is not None
            assert 0 <= agent.overall_score <= 1
            assert len(agent.dimensions) == 5

        # Check orchestration score structure
        orch = report.orchestration_score
        assert orch.workflow_id is not None
        assert 0 <= orch.overall_score <= 1
        # Should have core 5 dimensions plus optional n8n-specific dimensions
        assert len(orch.dimensions) >= 5
        assert orch.complexity_metrics is not None

