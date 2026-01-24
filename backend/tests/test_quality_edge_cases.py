"""Test edge cases for quality assessment."""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.agent_scorer import is_agent_node


class TestEmptyWorkflow:
    """Test quality assessment of empty workflows."""

    def test_empty_workflow_handles_gracefully(self):
        """Empty workflow with no nodes should not crash."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "empty-workflow",
            "name": "Empty Workflow",
            "nodes": [],
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        assert report.workflow_id == "empty-workflow"
        assert len(report.agent_scores) == 0
        assert report.orchestration_score is not None

    def test_empty_workflow_returns_valid_report_structure(self):
        """Empty workflow should return a complete QualityReport."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "empty",
            "name": "Empty",
            "nodes": [],
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        # Should have all required fields
        assert hasattr(report, "workflow_id")
        assert hasattr(report, "workflow_name")
        assert hasattr(report, "overall_score")
        assert hasattr(report, "overall_grade")
        assert hasattr(report, "agent_scores")
        assert hasattr(report, "orchestration_score")
        assert hasattr(report, "improvements")

    def test_workflow_missing_nodes_key(self):
        """Workflow without 'nodes' key should handle gracefully."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "no-nodes-key",
            "name": "No Nodes Key",
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        # Should default to empty nodes
        assert len(report.agent_scores) == 0

    def test_workflow_missing_connections_key(self):
        """Workflow without 'connections' key should handle gracefully."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "no-connections",
            "name": "No Connections",
            "nodes": [
                {
                    "id": "node-1",
                    "name": "Node 1",
                    "type": "n8n-nodes-base.set",
                    "parameters": {},
                }
            ],
        }

        report = assessor.assess_workflow(workflow)

        # Should still produce valid report
        assert report.orchestration_score is not None


class TestSingleNodeWorkflow:
    """Test workflows with a single node."""

    def test_single_non_agent_node(self):
        """Single non-agent node should produce orchestration-only score."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "single-node",
            "name": "Single Node",
            "nodes": [
                {
                    "id": "webhook",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {},
                }
            ],
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        # No agent nodes
        assert len(report.agent_scores) == 0
        # Overall equals orchestration
        assert report.overall_score == report.orchestration_score.overall_score

    def test_single_agent_node_uses_60_40_weight(self):
        """Single agent node should use 60/40 weighting."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "single-agent",
            "name": "Single Agent",
            "nodes": [
                {
                    "id": "agent",
                    "name": "Agent",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {
                        "systemMessage": "You are an assistant.",
                    },
                }
            ],
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        # Should have one agent
        assert len(report.agent_scores) == 1

        # Verify 60/40 formula
        agent_score = report.agent_scores[0].overall_score
        orchestration_score = report.orchestration_score.overall_score
        expected = (agent_score * 0.6) + (orchestration_score * 0.4)

        assert abs(report.overall_score - expected) < 0.001


class TestVeryLargeWorkflow:
    """Test workflows with many nodes."""

    def test_workflow_with_many_nodes(self):
        """Workflow with 50 nodes should not crash and should flag complexity."""
        assessor = QualityAssessor(use_llm_judge=False)

        # Create 50 nodes
        nodes = []
        connections = {}

        for i in range(50):
            node = {
                "id": f"node-{i}",
                "name": f"Node {i}",
                "type": "n8n-nodes-base.set",
                "parameters": {},
            }
            nodes.append(node)

            # Connect to next node
            if i < 49:
                connections[f"Node {i}"] = {
                    "main": [[{"node": f"Node {i+1}", "type": "main", "index": 0}]]
                }

        workflow = {
            "id": "large-workflow",
            "name": "Large Workflow",
            "nodes": nodes,
            "connections": connections,
        }

        report = assessor.assess_workflow(workflow)

        # Should produce valid report
        assert report.orchestration_score is not None

        # Complexity metrics should reflect large size
        complexity = report.orchestration_score.complexity_metrics
        assert complexity.node_count == 50

    def test_workflow_with_many_agents(self):
        """Workflow with 20 agents should handle gracefully."""
        assessor = QualityAssessor(use_llm_judge=False)

        # Create 20 agent nodes
        nodes = []
        for i in range(20):
            node = {
                "id": f"agent-{i}",
                "name": f"Agent {i}",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": f"You are agent {i}.",
                },
            }
            nodes.append(node)

        workflow = {
            "id": "many-agents",
            "name": "Many Agents",
            "nodes": nodes,
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        # Should score all agents
        assert len(report.agent_scores) == 20

        # Should produce valid overall score
        assert 0.0 <= report.overall_score <= 1.0


class TestDisconnectedNodes:
    """Test workflows with disconnected or orphan nodes."""

    def test_workflow_with_orphan_nodes(self):
        """Workflow with unconnected nodes should handle gracefully."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "orphans",
            "name": "Orphan Nodes",
            "nodes": [
                {
                    "id": "node-1",
                    "name": "Connected Node",
                    "type": "n8n-nodes-base.set",
                    "parameters": {},
                },
                {
                    "id": "node-2",
                    "name": "Orphan Node",
                    "type": "n8n-nodes-base.set",
                    "parameters": {},
                },
            ],
            "connections": {},  # No connections - all orphaned
        }

        report = assessor.assess_workflow(workflow)

        # Should still produce valid report
        assert report.orchestration_score is not None

    def test_workflow_with_multiple_start_nodes(self):
        """Workflow with multiple entry points should handle gracefully."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "multi-start",
            "name": "Multiple Starts",
            "nodes": [
                {
                    "id": "webhook-1",
                    "name": "Webhook 1",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {},
                },
                {
                    "id": "webhook-2",
                    "name": "Webhook 2",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {},
                },
                {
                    "id": "merge",
                    "name": "Merge",
                    "type": "n8n-nodes-base.merge",
                    "parameters": {},
                },
            ],
            "connections": {
                "Webhook 1": {
                    "main": [[{"node": "Merge", "type": "main", "index": 0}]]
                },
                "Webhook 2": {
                    "main": [[{"node": "Merge", "type": "main", "index": 0}]]
                },
            },
        }

        report = assessor.assess_workflow(workflow)

        # Should handle multiple entry points
        assert report.orchestration_score is not None


class TestNodeTypeFiltering:
    """Test correct identification of agent vs non-agent nodes."""

    def test_langchain_agent_is_agent_node(self):
        """LangChain agent node should be identified as agent."""
        node = {
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {},
        }
        assert is_agent_node(node) is True

    def test_langchain_chain_llm_is_agent_node(self):
        """LangChain chain LLM node should be identified as agent."""
        node = {
            "type": "@n8n/n8n-nodes-langchain.chainLlm",
            "parameters": {},
        }
        assert is_agent_node(node) is True

    def test_openai_node_is_agent_node(self):
        """OpenAI node should be identified as agent."""
        node = {
            "type": "n8n-nodes-base.openAi",
            "parameters": {},
        }
        assert is_agent_node(node) is True

    def test_anthropic_node_is_agent_node(self):
        """Anthropic node should be identified as agent."""
        node = {
            "type": "n8n-nodes-base.anthropic",
            "parameters": {},
        }
        assert is_agent_node(node) is True

    def test_lm_chat_openai_is_not_agent_node(self):
        """LM chat model config nodes should NOT be identified as agents."""
        node = {
            "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
            "parameters": {},
        }
        assert is_agent_node(node) is False

    def test_lm_chat_anthropic_is_not_agent_node(self):
        """LM chat Anthropic config should NOT be identified as agent."""
        node = {
            "type": "@n8n/n8n-nodes-langchain.lmChatAnthropic",
            "parameters": {},
        }
        assert is_agent_node(node) is False

    def test_set_node_is_not_agent_node(self):
        """Regular data processing nodes should NOT be identified as agents."""
        node = {
            "type": "n8n-nodes-base.set",
            "parameters": {},
        }
        assert is_agent_node(node) is False

    def test_webhook_node_is_not_agent_node(self):
        """Webhook nodes should NOT be identified as agents."""
        node = {
            "type": "n8n-nodes-base.webhook",
            "parameters": {},
        }
        assert is_agent_node(node) is False

    def test_workflow_with_mixed_node_types(self):
        """Workflow with agents and non-agents should count agents correctly."""
        assessor = QualityAssessor(use_llm_judge=False)

        workflow = {
            "id": "mixed",
            "name": "Mixed Nodes",
            "nodes": [
                {
                    "id": "agent",
                    "name": "Agent",
                    "type": "@n8n/n8n-nodes-langchain.agent",
                    "parameters": {},
                },
                {
                    "id": "model-config",
                    "name": "Model Config",
                    "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                    "parameters": {},
                },
                {
                    "id": "set",
                    "name": "Set",
                    "type": "n8n-nodes-base.set",
                    "parameters": {},
                },
            ],
            "connections": {},
        }

        report = assessor.assess_workflow(workflow)

        # Should only count the agent, not the model config or set node
        assert len(report.agent_scores) == 1
        assert report.agent_scores[0].agent_id == "agent"
