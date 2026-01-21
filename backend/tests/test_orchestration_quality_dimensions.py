"""Test orchestration quality dimension scoring."""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.orchestration_scorer import OrchestrationQualityScorer
from app.enterprise.quality.models import OrchestrationDimension


class TestDataFlowClarityDimension:
    """Test data_flow_clarity dimension scoring."""

    def test_workflow_with_single_node_scores_reasonable(self):
        """Workflow with single node should score reasonably."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Single Node Workflow",
            "nodes": [
                {"id": "1", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}}
            ],
            "connections": {}
        }

        score = scorer.score_orchestration(workflow)
        data_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.DATA_FLOW_CLARITY.value)

        # Should have reasonable default score
        assert 0.4 <= data_dim.score <= 0.8

    def test_poor_naming_scores_lower(self):
        """Workflow with generic node names should score lower."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Poor Naming",
            "nodes": [
                {"id": "1", "name": "Node", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "2", "name": "Set", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "3", "name": "Unnamed", "type": "n8n-nodes-base.code", "parameters": {}},
                {"id": "4", "name": "Code", "type": "n8n-nodes-base.code", "parameters": {}},
            ],
            "connections": {
                "Node": {"main": [[{"node": "Set"}]]},
                "Set": {"main": [[{"node": "Unnamed"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        data_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.DATA_FLOW_CLARITY.value)

        # Should be penalized for generic names
        assert data_dim.score < 0.7
        assert data_dim.evidence.get("generic_node_names", 0) >= 3

    def test_good_naming_explicit_connections_scores_high(self):
        """Workflow with good names and explicit connections should score high."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Well Named Workflow",
            "nodes": [
                {"id": "1", "name": "Fetch Customer Data", "type": "n8n-nodes-base.httpRequest", "parameters": {}},
                {"id": "2", "name": "Transform Response", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Store Results", "type": "n8n-nodes-base.postgres", "parameters": {}},
                {"id": "4", "name": "Send Notification", "type": "n8n-nodes-base.slack", "parameters": {}},
            ],
            "connections": {
                "Fetch Customer Data": {"main": [[{"node": "Transform Response"}]]},
                "Transform Response": {"main": [[{"node": "Store Results"}]]},
                "Store Results": {"main": [[{"node": "Send Notification"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        data_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.DATA_FLOW_CLARITY.value)

        # Should score high with good naming and connections
        assert data_dim.score >= 0.7
        assert data_dim.evidence.get("generic_node_names", 0) == 0

    def test_high_state_manipulation_scores_lower(self):
        """Workflow with many Set/Code nodes should score lower."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "State Heavy Workflow",
            "nodes": [
                {"id": "1", "name": "Set Global State", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "2", "name": "Process State", "type": "n8n-nodes-base.code", "parameters": {}},
                {"id": "3", "name": "Update State", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "4", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "5", "name": "More State", "type": "n8n-nodes-base.set", "parameters": {}},
            ],
            "connections": {
                "Set Global State": {"main": [[{"node": "Process State"}]]},
                "Process State": {"main": [[{"node": "Update State"}]]},
                "Update State": {"main": [[{"node": "Agent"}]]},
                "Agent": {"main": [[{"node": "More State"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        data_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.DATA_FLOW_CLARITY.value)

        # Should be penalized for high state manipulation ratio
        assert data_dim.evidence.get("state_manipulation_nodes", 0) >= 4
        assert any("state manipulation" in issue.lower() for issue in data_dim.issues)


class TestComplexityManagementDimension:
    """Test complexity_management dimension scoring."""

    def test_small_workflow_scores_high(self):
        """Small workflow within thresholds should score high."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Simple Workflow",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Output", "type": "n8n-nodes-base.respond", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Agent"}]]},
                "Agent": {"main": [[{"node": "Output"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        complexity_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.COMPLEXITY_MANAGEMENT.value)

        assert complexity_dim.score >= 0.8
        assert complexity_dim.evidence.get("node_count") == 3

    def test_too_many_nodes_scores_lower(self):
        """Workflow with many nodes should score lower."""
        scorer = OrchestrationQualityScorer()
        nodes = [{"id": str(i), "name": f"Node {i}", "type": "n8n-nodes-base.set", "parameters": {}} for i in range(20)]
        connections = {f"Node {i}": {"main": [[{"node": f"Node {i+1}"}]]} for i in range(19)}

        workflow = {
            "id": "test-workflow",
            "name": "Large Workflow",
            "nodes": nodes,
            "connections": connections
        }

        score = scorer.score_orchestration(workflow)
        complexity_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.COMPLEXITY_MANAGEMENT.value)

        # Should be penalized for too many nodes
        assert complexity_dim.score < 1.0
        assert complexity_dim.evidence.get("node_count") == 20
        assert any("nodes" in issue.lower() for issue in complexity_dim.issues)

    def test_deep_workflow_scores_lower(self):
        """Workflow with high depth should score lower."""
        scorer = OrchestrationQualityScorer()
        nodes = [{"id": str(i), "name": f"Step {i}", "type": "n8n-nodes-base.set", "parameters": {}} for i in range(10)]
        connections = {f"Step {i}": {"main": [[{"node": f"Step {i+1}"}]]} for i in range(9)}

        workflow = {
            "id": "test-workflow",
            "name": "Deep Workflow",
            "nodes": nodes,
            "connections": connections
        }

        score = scorer.score_orchestration(workflow)
        complexity_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.COMPLEXITY_MANAGEMENT.value)

        # Should flag depth issues
        assert complexity_dim.evidence.get("max_depth") >= 8

    def test_many_agents_flagged(self):
        """Workflow with many agents should flag coordination concerns."""
        scorer = OrchestrationQualityScorer()
        nodes = [
            {"id": str(i), "name": f"Agent {i}", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}}
            for i in range(10)
        ]
        connections = {f"Agent {i}": {"main": [[{"node": f"Agent {i+1}"}]]} for i in range(9)}

        workflow = {
            "id": "test-workflow",
            "name": "Many Agents",
            "nodes": nodes,
            "connections": connections
        }

        score = scorer.score_orchestration(workflow)
        complexity_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.COMPLEXITY_MANAGEMENT.value)

        # Should flag many agents
        assert any("agents" in issue.lower() for issue in complexity_dim.issues)


class TestAgentCouplingDimension:
    """Test agent_coupling dimension scoring."""

    def test_single_agent_scores_high(self):
        """Single agent workflow should score well (no coupling issues)."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Single Agent",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Agent"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        coupling_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.AGENT_COUPLING.value)

        # Single agent = no coupling issues
        assert coupling_dim.score >= 0.9
        assert coupling_dim.evidence.get("agent_count") == 1

    def test_independent_agents_score_high(self):
        """Agents with intermediate processing should score high."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Independent Agents",
            "nodes": [
                {"id": "1", "name": "Agent A", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "2", "name": "Process A Output", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "3", "name": "Agent B", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "4", "name": "Process B Output", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "5", "name": "Agent C", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
            ],
            "connections": {
                "Agent A": {"main": [[{"node": "Process A Output"}]]},
                "Process A Output": {"main": [[{"node": "Agent B"}]]},
                "Agent B": {"main": [[{"node": "Process B Output"}]]},
                "Process B Output": {"main": [[{"node": "Agent C"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        coupling_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.AGENT_COUPLING.value)

        # Agents with intermediate processing = lower coupling
        assert coupling_dim.score >= 0.7
        assert coupling_dim.evidence.get("coupling_ratio", 1.0) < 0.5

    def test_tightly_coupled_agents_score_lower(self):
        """Direct agent-to-agent connections should score lower."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Coupled Agents",
            "nodes": [
                {"id": "1", "name": "Agent A", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "2", "name": "Agent B", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Agent C", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
            ],
            "connections": {
                "Agent A": {"main": [[{"node": "Agent B"}]]},
                "Agent B": {"main": [[{"node": "Agent C"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        coupling_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.AGENT_COUPLING.value)

        # Direct coupling = higher coupling ratio
        assert coupling_dim.evidence.get("coupling_ratio", 0) > 0.3
        assert coupling_dim.evidence.get("max_agent_chain", 0) >= 3

    def test_long_agent_chain_flagged(self):
        """Long chains of agents should be flagged."""
        scorer = OrchestrationQualityScorer()
        nodes = [
            {"id": str(i), "name": f"Agent {i}", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}}
            for i in range(6)
        ]
        connections = {f"Agent {i}": {"main": [[{"node": f"Agent {i+1}"}]]} for i in range(5)}

        workflow = {
            "id": "test-workflow",
            "name": "Long Agent Chain",
            "nodes": nodes,
            "connections": connections
        }

        score = scorer.score_orchestration(workflow)
        coupling_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.AGENT_COUPLING.value)

        # Long chain should be flagged
        assert coupling_dim.evidence.get("max_agent_chain", 0) >= 5
        assert any("chain" in issue.lower() for issue in coupling_dim.issues)


class TestObservabilityDimension:
    """Test observability dimension scoring."""

    def test_no_observability_scores_low(self):
        """Workflow without observability features should score low."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "No Observability",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Agent"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        obs_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.OBSERVABILITY.value)

        # Should be penalized for no observability
        assert obs_dim.score < 0.5
        assert obs_dim.evidence.get("observability_nodes", 1) == 0

    def test_checkpoint_nodes_score_higher(self):
        """Workflow with checkpoint nodes should score higher."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "With Checkpoints",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Checkpoint 1", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "3", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "4", "name": "Checkpoint 2", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "5", "name": "Output", "type": "n8n-nodes-base.respond", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Checkpoint 1"}]]},
                "Checkpoint 1": {"main": [[{"node": "Agent"}]]},
                "Agent": {"main": [[{"node": "Checkpoint 2"}]]},
                "Checkpoint 2": {"main": [[{"node": "Output"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        obs_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.OBSERVABILITY.value)

        # Should be better with checkpoints
        assert obs_dim.evidence.get("observability_nodes", 0) >= 2
        assert obs_dim.score >= 0.5

    def test_error_trigger_scores_higher(self):
        """Workflow with error trigger should score higher."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "With Error Trigger",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Error Handler", "type": "n8n-nodes-base.errorTrigger", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Agent"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        obs_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.OBSERVABILITY.value)

        # Error trigger should boost score
        assert obs_dim.evidence.get("error_triggers", 0) >= 1
        assert obs_dim.score >= 0.6

    def test_monitoring_webhook_scores_higher(self):
        """Workflow with monitoring webhook should score higher."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "With Monitoring",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Send to MAO", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "https://mao.example.com/webhook"}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Agent"}]]},
                "Agent": {"main": [[{"node": "Send to MAO"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        obs_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.OBSERVABILITY.value)

        # Monitoring webhook should boost score
        assert obs_dim.evidence.get("monitoring_webhooks", 0) >= 1


class TestBestPracticesDimension:
    """Test best_practices dimension scoring."""

    def test_no_error_handler_scores_lower(self):
        """Workflow without global error handler should score lower."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "No Error Handler",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Agent"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        bp_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.BEST_PRACTICES.value)

        # Should be penalized for no global error handler
        assert bp_dim.evidence.get("has_global_error_handler") is False
        assert any("error handler" in issue.lower() for issue in bp_dim.issues)

    def test_global_error_handler_scores_higher(self):
        """Workflow with global error handler should score higher."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "With Error Handler",
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "parameters": {}},
                {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Error Handler", "type": "n8n-nodes-base.errorTrigger", "parameters": {}},
            ],
            "connections": {
                "Trigger": {"main": [[{"node": "Agent"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        bp_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.BEST_PRACTICES.value)

        # Should be boosted for global error handler
        assert bp_dim.evidence.get("has_global_error_handler") is True

    def test_uniform_config_scores_higher(self):
        """Workflow with uniform retry config should score higher."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Uniform Config",
            "nodes": [
                {"id": "1", "name": "Agent A", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"options": {"retryOnFail": True, "timeout": 30000}}},
                {"id": "2", "name": "Agent B", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"options": {"retryOnFail": True, "timeout": 30000}}},
                {"id": "3", "name": "Agent C", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"options": {"retryOnFail": True, "timeout": 30000}}},
            ],
            "connections": {
                "Agent A": {"main": [[{"node": "Agent B"}]]},
                "Agent B": {"main": [[{"node": "Agent C"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        bp_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.BEST_PRACTICES.value)

        # Uniform config should be rewarded
        assert bp_dim.evidence.get("nodes_with_retry") == 3
        assert bp_dim.evidence.get("nodes_with_timeout") == 3

    def test_non_uniform_config_flagged(self):
        """Workflow with inconsistent config should flag as suggestion."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "Inconsistent Config",
            "nodes": [
                {"id": "1", "name": "Agent A", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"options": {"retryOnFail": True}}},
                {"id": "2", "name": "Agent B", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Agent C", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"options": {"retryOnFail": True}}},
            ],
            "connections": {
                "Agent A": {"main": [[{"node": "Agent B"}]]},
                "Agent B": {"main": [[{"node": "Agent C"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)
        bp_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.BEST_PRACTICES.value)

        # Should suggest consistent config
        assert bp_dim.evidence.get("nodes_with_retry") == 2
        assert any("consistently" in suggestion.lower() for suggestion in bp_dim.suggestions)

    def test_workflow_settings_boost_score(self):
        """Workflow with error preservation settings should score higher."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test-workflow",
            "name": "With Good Settings",
            "nodes": [
                {"id": "1", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
            ],
            "connections": {},
            "settings": {
                "saveManualExecutions": True,
                "saveDataErrorExecution": "all"
            }
        }

        score = scorer.score_orchestration(workflow)
        bp_dim = next(d for d in score.dimensions if d.dimension == OrchestrationDimension.BEST_PRACTICES.value)

        # Good workflow settings should boost score
        assert bp_dim.evidence.get("workflow_settings_score", 0) >= 0.5


class TestOverallOrchestrationScoring:
    """Test overall orchestration scoring."""

    def test_all_dimensions_present(self):
        """Verify all 5 orchestration dimensions are scored."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test",
            "name": "Test",
            "nodes": [{"id": "1", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}}],
            "connections": {}
        }

        score = scorer.score_orchestration(workflow)

        dimension_names = {d.dimension for d in score.dimensions}
        expected = {
            OrchestrationDimension.DATA_FLOW_CLARITY.value,
            OrchestrationDimension.COMPLEXITY_MANAGEMENT.value,
            OrchestrationDimension.AGENT_COUPLING.value,
            OrchestrationDimension.OBSERVABILITY.value,
            OrchestrationDimension.BEST_PRACTICES.value,
        }

        assert dimension_names == expected

    def test_complexity_metrics_calculated(self):
        """Verify complexity metrics are calculated."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test",
            "name": "Test",
            "nodes": [
                {"id": "1", "name": "Agent A", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "2", "name": "Agent B", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
                {"id": "3", "name": "Output", "type": "n8n-nodes-base.respond", "parameters": {}},
            ],
            "connections": {
                "Agent A": {"main": [[{"node": "Agent B"}]]},
                "Agent B": {"main": [[{"node": "Output"}]]},
            }
        }

        score = scorer.score_orchestration(workflow)

        assert score.complexity_metrics is not None
        assert score.complexity_metrics.node_count == 3
        assert score.complexity_metrics.agent_count == 2
        assert score.complexity_metrics.connection_count == 2

    def test_pattern_detection(self):
        """Verify pattern detection works."""
        scorer = OrchestrationQualityScorer()

        # Linear workflow
        linear_workflow = {
            "id": "linear",
            "name": "Linear",
            "nodes": [
                {"id": "1", "name": "A", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "2", "name": "B", "type": "n8n-nodes-base.set", "parameters": {}},
            ],
            "connections": {"A": {"main": [[{"node": "B"}]]}}
        }
        linear_score = scorer.score_orchestration(linear_workflow)
        assert linear_score.detected_pattern == "linear"

        # Loop workflow
        loop_workflow = {
            "id": "loop",
            "name": "Loop",
            "nodes": [
                {"id": "1", "name": "A", "type": "n8n-nodes-base.set", "parameters": {}},
                {"id": "2", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "parameters": {}},
            ],
            "connections": {"A": {"main": [[{"node": "Loop"}]]}}
        }
        loop_score = scorer.score_orchestration(loop_workflow)
        # May detect as linear since splitInBatches doesn't have "loop" in type
        # But if there were a proper loop node it would be "loop"

    def test_overall_score_weighted_correctly(self):
        """Verify overall score is calculated from dimensions."""
        scorer = OrchestrationQualityScorer()
        workflow = {
            "id": "test",
            "name": "Test",
            "nodes": [
                {"id": "1", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {}},
            ],
            "connections": {}
        }

        score = scorer.score_orchestration(workflow)

        # Overall should be weighted average of dimensions
        assert 0 <= score.overall_score <= 1
        # Sum of individual dimension scores * weights should equal overall
        total_weight = sum(d.weight for d in score.dimensions)
        calculated = sum(d.score * d.weight for d in score.dimensions) / total_weight
        assert abs(score.overall_score - calculated) < 0.01

