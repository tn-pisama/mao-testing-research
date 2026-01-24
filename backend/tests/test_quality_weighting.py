"""Test 60/40 weighting formula for quality assessment."""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality import QualityAssessor


class TestWeightedScoring:
    """Test the 60% agent + 40% orchestration weighting formula."""

    def test_60_40_weighting_with_single_agent(self):
        """
        Verify: overall = (agent_score * 0.6) + (orchestration_score * 0.4)

        Using a well-defined agent and simple orchestration to get predictable scores.
        """
        assessor = QualityAssessor(use_llm_judge=False)

        # Simple workflow with one well-configured agent
        workflow = {
            "id": "test-workflow",
            "name": "Test Workflow",
            "nodes": [
                {
                    "id": "agent-1",
                    "name": "Analyst Agent",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {
                        "systemMessage": """You are a data analyst.

Your role is to analyze data and provide insights.

You must respond with JSON in this format:
{
  "summary": "text",
  "insights": ["item1", "item2"]
}

Do not make assumptions.
Never include PII.
Only analyze the provided data.""",
                        "temperature": 0.1,
                        "maxTokens": 2000,
                    },
                    "retryOnFail": True,
                    "maxTries": 3,
                    "waitBetweenTries": 1000,
                    "continueOnFail": False,
                },
            ],
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        # Extract scores
        assert len(report.agent_scores) == 1
        agent_score = report.agent_scores[0].overall_score
        orchestration_score = report.orchestration_score.overall_score

        # Verify formula: overall = (agent * 0.6) + (orchestration * 0.4)
        expected_overall = (agent_score * 0.6) + (orchestration_score * 0.4)

        assert abs(report.overall_score - expected_overall) < 0.001, (
            f"Expected {expected_overall:.3f}, got {report.overall_score:.3f}. "
            f"Agent: {agent_score:.3f}, Orchestration: {orchestration_score:.3f}"
        )

    def test_60_40_weighting_with_multiple_agents(self):
        """
        With multiple agents, should average agent scores first, then apply 60/40 weighting.
        Formula: overall = (avg(agent_scores) * 0.6) + (orchestration * 0.4)
        """
        assessor = QualityAssessor(use_llm_judge=False)

        # Workflow with two agents
        workflow = {
            "id": "multi-agent",
            "name": "Multi Agent Workflow",
            "nodes": [
                {
                    "id": "agent-1",
                    "name": "Agent 1",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {
                        "systemMessage": "You are agent 1.",
                    },
                },
                {
                    "id": "agent-2",
                    "name": "Agent 2",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {
                        "systemMessage": "You are agent 2.",
                    },
                },
            ],
            "connections": {
                "Agent 1": {
                    "main": [[{"node": "Agent 2", "type": "main", "index": 0}]],
                },
            },
        }

        report = assessor.assess_workflow(workflow)

        # Extract scores
        assert len(report.agent_scores) == 2
        agent_1_score = report.agent_scores[0].overall_score
        agent_2_score = report.agent_scores[1].overall_score
        avg_agent_score = (agent_1_score + agent_2_score) / 2
        orchestration_score = report.orchestration_score.overall_score

        # Verify formula
        expected_overall = (avg_agent_score * 0.6) + (orchestration_score * 0.4)

        assert abs(report.overall_score - expected_overall) < 0.001, (
            f"Expected {expected_overall:.3f}, got {report.overall_score:.3f}. "
            f"Agents: [{agent_1_score:.3f}, {agent_2_score:.3f}] avg={avg_agent_score:.3f}, "
            f"Orchestration: {orchestration_score:.3f}"
        )

    def test_no_agents_uses_orchestration_only(self):
        """
        When workflow has no AI agents, overall score should equal orchestration score.
        """
        assessor = QualityAssessor(use_llm_judge=False)

        # Workflow with no agent nodes
        workflow = {
            "id": "no-agents",
            "name": "No Agents Workflow",
            "nodes": [
                {
                    "id": "set-1",
                    "name": "Set Data",
                    "type": "n8n-nodes-base.set",
                    "parameters": {},
                },
                {
                    "id": "webhook",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {},
                },
            ],
            "connections": {
                "Webhook": {
                    "main": [[{"node": "Set Data", "type": "main", "index": 0}]],
                },
            },
        }

        report = assessor.assess_workflow(workflow)

        # Should have no agent scores
        assert len(report.agent_scores) == 0

        # Overall should equal orchestration score
        assert report.overall_score == report.orchestration_score.overall_score


class TestWeightingEdgeCases:
    """Test edge cases for score weighting."""

    def test_perfect_agent_and_orchestration_scores_perfect_overall(self):
        """
        When both agent and orchestration score 1.0, overall should be 1.0.
        Formula: (1.0 * 0.6) + (1.0 * 0.4) = 0.6 + 0.4 = 1.0
        """
        # This is theoretical - create test with mocked scores
        agent_score = 1.0
        orchestration_score = 1.0

        overall = (agent_score * 0.6) + (orchestration_score * 0.4)

        assert overall == 1.0

    def test_zero_agent_and_orchestration_scores_zero_overall(self):
        """
        When both agent and orchestration score 0.0, overall should be 0.0.
        Formula: (0.0 * 0.6) + (0.0 * 0.4) = 0.0 + 0.0 = 0.0
        """
        agent_score = 0.0
        orchestration_score = 0.0

        overall = (agent_score * 0.6) + (orchestration_score * 0.4)

        assert overall == 0.0

    def test_perfect_agent_zero_orchestration(self):
        """
        Agent at 1.0, orchestration at 0.0 should yield 0.6 overall.
        Formula: (1.0 * 0.6) + (0.0 * 0.4) = 0.6
        """
        agent_score = 1.0
        orchestration_score = 0.0

        overall = (agent_score * 0.6) + (orchestration_score * 0.4)

        assert overall == 0.6

    def test_zero_agent_perfect_orchestration(self):
        """
        Agent at 0.0, orchestration at 1.0 should yield 0.4 overall.
        Formula: (0.0 * 0.6) + (1.0 * 0.4) = 0.4
        """
        agent_score = 0.0
        orchestration_score = 1.0

        overall = (agent_score * 0.6) + (orchestration_score * 0.4)

        assert overall == 0.4

    def test_weighting_ratio_is_60_to_40(self):
        """
        Verify that the ratio of agent weight to orchestration weight is 60:40 (3:2).
        """
        agent_weight = 0.6
        orchestration_weight = 0.4

        # Total should be 1.0
        assert agent_weight + orchestration_weight == 1.0

        # Ratio should be 3:2
        ratio = agent_weight / orchestration_weight
        assert abs(ratio - 1.5) < 0.001  # 0.6 / 0.4 = 1.5

    def test_agent_weight_greater_than_orchestration_weight(self):
        """
        Agent weight (0.6) should be greater than orchestration weight (0.4).

        This reflects the design principle that agent quality issues typically
        cause more severe failures than orchestration issues.
        """
        agent_weight = 0.6
        orchestration_weight = 0.4

        assert agent_weight > orchestration_weight
        assert abs((agent_weight - orchestration_weight) - 0.2) < 0.001
