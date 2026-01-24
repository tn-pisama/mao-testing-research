"""Tests for n8n quality enhancements (Phase 4)."""

import pytest
from app.enterprise.quality.n8n_categorizer import (
    N8nWorkflowCategory,
    categorize_workflow,
    get_category_stats,
)
from app.enterprise.quality.orchestration_scorer import OrchestrationQualityScorer


class TestN8nCategorization:
    """Test workflow categorization by node composition."""

    def test_ai_multi_agent_categorization(self):
        """Workflow with 2+ LangChain nodes = AI_MULTI_AGENT."""
        workflow = {
            "nodes": [
                {"type": "@n8n/n8n-nodes-langchain.agent", "name": "Agent 1"},
                {"type": "@n8n/n8n-nodes-langchain.agent", "name": "Agent 2"},
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ]
        }
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.AI_MULTI_AGENT

    def test_ai_single_agent_categorization(self):
        """Workflow with 1 LangChain node = AI_SINGLE_AGENT."""
        workflow = {
            "nodes": [
                {"type": "@n8n/n8n-nodes-langchain.agent", "name": "Agent"},
                {"type": "n8n-nodes-base.set", "name": "Set"},
                {"type": "n8n-nodes-base.code", "name": "Code"},
            ]
        }
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.AI_SINGLE_AGENT

    def test_integration_categorization(self):
        """Workflow with Slack + Google = INTEGRATION."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.slack", "name": "Slack"},
                {"type": "n8n-nodes-base.googleSheets", "name": "Google Sheets"},
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ]
        }
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.INTEGRATION

    def test_scheduled_automation_categorization(self):
        """Workflow with scheduleTrigger = AUTOMATION_SCHEDULED."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.scheduleTrigger", "name": "Schedule"},
                {"type": "n8n-nodes-base.httpRequest", "name": "HTTP"},
            ]
        }
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.AUTOMATION_SCHEDULED

    def test_event_automation_categorization(self):
        """Workflow with webhook = AUTOMATION_EVENT."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.webhook", "name": "Webhook"},
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ]
        }
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.AUTOMATION_EVENT

    def test_data_processing_categorization(self):
        """Workflow with 40%+ Code/Set nodes = DATA_PROCESSING."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.code", "name": "Code 1"},
                {"type": "n8n-nodes-base.code", "name": "Code 2"},
                {"type": "n8n-nodes-base.set", "name": "Set 1"},
                {"type": "n8n-nodes-base.set", "name": "Set 2"},
                {"type": "n8n-nodes-base.httpRequest", "name": "HTTP"},
            ]
        }
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.DATA_PROCESSING

    def test_utility_categorization(self):
        """Simple workflow without specialized patterns = UTILITY."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.httpRequest", "name": "HTTP"},
                {"type": "n8n-nodes-base.noOp", "name": "NoOp"},
                {"type": "n8n-nodes-base.merge", "name": "Merge"},
            ]
        }
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.UTILITY

    def test_empty_workflow_categorization(self):
        """Empty workflow = UTILITY."""
        workflow = {"nodes": []}
        category = categorize_workflow(workflow)
        assert category == N8nWorkflowCategory.UTILITY

    def test_get_category_stats(self):
        """Test category statistics aggregation."""
        workflows = [
            {"nodes": [{"type": "@n8n/n8n-nodes-langchain.agent"}, {"type": "@n8n/n8n-nodes-langchain.agent"}]},
            {"nodes": [{"type": "@n8n/n8n-nodes-langchain.agent"}]},
            {"nodes": [{"type": "n8n-nodes-base.slack"}, {"type": "n8n-nodes-base.googleSheets"}]},
            {"nodes": [{"type": "n8n-nodes-base.scheduleTrigger"}]},
        ]
        stats = get_category_stats(workflows)

        assert stats[N8nWorkflowCategory.AI_MULTI_AGENT.value] == 1
        assert stats[N8nWorkflowCategory.AI_SINGLE_AGENT.value] == 1
        assert stats[N8nWorkflowCategory.INTEGRATION.value] == 1
        assert stats[N8nWorkflowCategory.AUTOMATION_SCHEDULED.value] == 1


class TestDocumentationQualityDimension:
    """Test documentation quality dimension scoring."""

    def test_no_sticky_notes_scores_low(self):
        """Workflow without sticky notes scores lower."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.set", "name": "Set"},
                {"type": "n8n-nodes-base.code", "name": "Code"},
            ]
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_documentation_quality(workflow)

        assert score is not None
        assert score.score < 0.5
        assert "No documentation" in score.issues[0]
        assert len(score.suggestions) > 0

    def test_single_sticky_note_scores_medium(self):
        """Workflow with 1 sticky note scores medium."""
        workflow = {
            "nodes": [
                {
                    "type": "n8n-nodes-base.stickyNote",
                    "name": "Note",
                    "parameters": {"content": "This is a workflow description"},
                },
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ]
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_documentation_quality(workflow)

        assert score is not None
        assert 0.5 <= score.score < 0.8
        assert score.evidence["sticky_note_count"] == 1

    def test_multiple_sticky_notes_scores_high(self):
        """Workflow with 3+ sticky notes and good content scores high."""
        workflow = {
            "nodes": [
                {
                    "type": "n8n-nodes-base.stickyNote",
                    "name": "Note 1",
                    "parameters": {"content": "Section 1: This workflow handles customer onboarding automation with detailed step-by-step processing"},
                },
                {
                    "type": "n8n-nodes-base.stickyNote",
                    "name": "Note 2",
                    "parameters": {"content": "Section 2: Data validation and transformation logic including schema checks and error handling"},
                },
                {
                    "type": "n8n-nodes-base.stickyNote",
                    "name": "Note 3",
                    "parameters": {"content": "Section 3: Error handling and notifications with retry mechanisms and alerting"},
                },
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ]
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_documentation_quality(workflow)

        assert score is not None
        assert score.score >= 0.9
        assert score.evidence["sticky_note_count"] == 3
        assert score.evidence["total_documentation_chars"] > 200

    def test_empty_workflow_returns_none(self):
        """Empty workflow returns None."""
        workflow = {"nodes": []}
        scorer = OrchestrationQualityScorer()
        score = scorer._score_documentation_quality(workflow)

        assert score is None


class TestAIArchitectureDimension:
    """Test AI architecture dimension scoring."""

    def test_non_ai_workflow_returns_none(self):
        """Non-AI workflow returns None for AI architecture."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.set", "name": "Set"},
                {"type": "n8n-nodes-base.code", "name": "Code"},
            ],
            "connections": {},
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_ai_architecture(workflow)

        assert score is None

    def test_ai_nodes_without_connections_scores_low(self):
        """AI nodes without specialized connections score low."""
        workflow = {
            "nodes": [
                {"type": "@n8n/n8n-nodes-langchain.agent", "name": "Agent"},
            ],
            "connections": {},
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_ai_architecture(workflow)

        assert score is not None
        assert score.score < 0.5
        assert "no specialized AI connections" in score.issues[0]

    def test_ai_connections_scored(self):
        """AI-specific connections (ai_tool, ai_memory) boost score."""
        workflow = {
            "nodes": [
                {"type": "@n8n/n8n-nodes-langchain.agent", "name": "Agent"},
            ],
            "connections": {
                "Agent": {
                    "ai_languageModel": [[{"node": "OpenAI", "type": "ai_languageModel"}]],
                    "ai_tool": [
                        [{"node": "Calculator", "type": "ai_tool"}],
                        [{"node": "WebSearch", "type": "ai_tool"}],
                    ],
                    "ai_memory": [[{"node": "BufferMemory", "type": "ai_memory"}]],
                }
            },
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_ai_architecture(workflow)

        assert score is not None
        assert score.score > 0.7
        assert score.evidence["ai_connections"] == 4
        assert score.evidence["unique_ai_connection_types"] == 3
        assert "ai_tool" in score.evidence["ai_connection_types_used"]
        assert "ai_memory" in score.evidence["ai_connection_types_used"]

    def test_multiple_ai_connection_types_score_higher(self):
        """Diverse AI connection types score higher."""
        workflow = {
            "nodes": [
                {"type": "@n8n/n8n-nodes-langchain.agent", "name": "Agent"},
            ],
            "connections": {
                "Agent": {
                    "ai_languageModel": [[{"node": "OpenAI"}]],
                    "ai_tool": [[{"node": "Tool"}]],
                    "ai_memory": [[{"node": "Memory"}]],
                    "ai_retriever": [[{"node": "Retriever"}]],
                }
            },
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_ai_architecture(workflow)

        assert score is not None
        assert score.score >= 0.8
        assert score.evidence["unique_ai_connection_types"] == 4


class TestMaintenanceQualityDimension:
    """Test maintenance quality dimension scoring."""

    def test_disabled_nodes_flagged(self):
        """Disabled nodes reduce maintenance score."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.set", "name": "Set 1", "disabled": False},
                {"type": "n8n-nodes-base.set", "name": "Set 2", "disabled": True},
                {"type": "n8n-nodes-base.code", "name": "Code", "disabled": True},
            ]
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_maintenance_quality(workflow)

        assert score is not None
        assert score.score < 1.0
        assert "2 disabled node(s)" in score.issues[0]
        assert score.evidence["disabled_nodes"] == 2

    def test_unconfigured_credentials_flagged(self):
        """Empty credential IDs reduce score."""
        workflow = {
            "nodes": [
                {
                    "type": "n8n-nodes-base.slack",
                    "name": "Slack",
                    "credentials": {
                        "slackApi": {"id": ""},  # Unconfigured
                    },
                },
                {
                    "type": "n8n-nodes-base.googleSheets",
                    "name": "Google",
                    "credentials": {
                        "googleSheetsOAuth2Api": {"id": "abc123"},  # Configured
                    },
                },
            ]
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_maintenance_quality(workflow)

        assert score is not None
        assert score.score < 1.0
        assert "1 unconfigured credential" in score.issues[0]
        assert score.evidence["unconfigured_credentials"] == 1

    def test_outdated_type_versions_flagged(self):
        """Old typeVersions reduce score."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.set", "name": "Set 1", "typeVersion": 2},
                {"type": "n8n-nodes-base.set", "name": "Set 2", "typeVersion": 0},
            ]
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_maintenance_quality(workflow)

        assert score is not None
        assert score.score < 1.0
        assert "deprecated versions" in score.issues[0]
        assert score.evidence["outdated_nodes"] == 1

    def test_missing_workflow_description_suggestion(self):
        """Missing workflow description adds suggestion."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ],
            "meta": {},
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_maintenance_quality(workflow)

        assert score is not None
        assert "workflow description" in " ".join(score.suggestions).lower()
        assert score.evidence["has_workflow_description"] is False

    def test_clean_workflow_scores_perfect(self):
        """Clean workflow with no issues scores 1.0."""
        workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.set", "name": "Set", "typeVersion": 2},
            ],
            "meta": {"description": "A well-maintained workflow"},
        }
        scorer = OrchestrationQualityScorer()
        score = scorer._score_maintenance_quality(workflow)

        assert score is not None
        assert score.score == 1.0
        assert len(score.issues) == 0

    def test_empty_workflow_returns_none(self):
        """Empty workflow returns None."""
        workflow = {"nodes": []}
        scorer = OrchestrationQualityScorer()
        score = scorer._score_maintenance_quality(workflow)

        assert score is None


class TestIntegrationWithOrchestrationScorer:
    """Test that new dimensions integrate properly into overall scoring."""

    def test_new_dimensions_included_in_score(self):
        """New dimensions are included in orchestration score."""
        workflow = {
            "nodes": [
                {
                    "type": "n8n-nodes-base.stickyNote",
                    "name": "Note",
                    "parameters": {"content": "This is documentation"},
                },
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ],
            "connections": {},
        }
        scorer = OrchestrationQualityScorer()
        result = scorer.score_orchestration(workflow)

        # Check that documentation_quality dimension is present
        dimension_names = [d.dimension for d in result.dimensions]
        assert "documentation_quality" in dimension_names
        assert "maintenance_quality" in dimension_names

    def test_ai_dimension_only_for_ai_workflows(self):
        """AI architecture dimension only appears for AI workflows."""
        non_ai_workflow = {
            "nodes": [
                {"type": "n8n-nodes-base.set", "name": "Set"},
            ],
            "connections": {},
        }
        scorer = OrchestrationQualityScorer()
        result = scorer.score_orchestration(non_ai_workflow)

        dimension_names = [d.dimension for d in result.dimensions]
        assert "ai_architecture" not in dimension_names

        # Now test with AI workflow
        ai_workflow = {
            "nodes": [
                {"type": "@n8n/n8n-nodes-langchain.agent", "name": "Agent"},
            ],
            "connections": {
                "Agent": {
                    "ai_languageModel": [[{"node": "OpenAI"}]],
                }
            },
        }
        result = scorer.score_orchestration(ai_workflow)

        dimension_names = [d.dimension for d in result.dimensions]
        assert "ai_architecture" in dimension_names

    def test_overall_score_calculation_with_new_dimensions(self):
        """Overall score correctly weights new dimensions."""
        workflow = {
            "nodes": [
                {
                    "type": "n8n-nodes-base.stickyNote",
                    "name": "Note",
                    "parameters": {"content": "Great documentation for this workflow"},
                },
                {"type": "n8n-nodes-base.set", "name": "Set", "typeVersion": 2},
            ],
            "connections": {},
            "meta": {"description": "Well-documented workflow"},
        }
        scorer = OrchestrationQualityScorer()
        result = scorer.score_orchestration(workflow)

        # Should have base 5 dimensions + documentation + maintenance
        assert len(result.dimensions) >= 5
        assert result.overall_score > 0
        assert result.overall_score <= 1.0
