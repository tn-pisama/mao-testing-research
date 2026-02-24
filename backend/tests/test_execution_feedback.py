"""Tests for Sprint 3 execution feedback and detection correlation features."""

import pytest
from unittest.mock import patch, MagicMock
from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.orchestration_scorer import OrchestrationQualityScorer
from app.enterprise.quality.models import ComplexityMetrics


# Minimal workflow with one agent node for testing
_MINIMAL_WORKFLOW = {
    "id": "test-wf",
    "name": "Test Workflow",
    "nodes": [
        {
            "id": "agent_1",
            "name": "AI Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": "You are a helpful assistant.",
                "maxIterations": 5,
            },
        },
        {
            "id": "trigger_1",
            "name": "Manual Trigger",
            "type": "n8n-nodes-base.manualTrigger",
            "parameters": {},
        },
    ],
    "connections": {
        "Manual Trigger": {
            "main": [[{"node": "AI Agent"}]],
        },
    },
}


class TestAutoActivation:
    """Test that execution_weight auto-activates when execution_history is provided."""

    def test_default_weight_is_zero(self):
        assessor = QualityAssessor(use_llm_judge=False)
        assert assessor.execution_weight == 0.0

    def test_auto_activation_with_execution_history(self):
        """When execution_history is provided and execution_weight==0.0,
        auto-activate to 0.2."""
        assessor = QualityAssessor(use_llm_judge=False)
        assert assessor.execution_weight == 0.0

        execution_history = [
            {
                "node_id": "agent_1",
                "status": "success",
                "node_results": {"AI Agent": {"status": "success"}},
            },
        ]

        report = assessor.assess_workflow(_MINIMAL_WORKFLOW, execution_history=execution_history)
        # The report should exist (execution scorer ran without crashing)
        assert report is not None
        assert report.overall_score > 0

    def test_no_activation_without_history(self):
        """Without execution_history, execution_weight stays 0.0 and scoring
        uses the standard 60/40 blend."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(_MINIMAL_WORKFLOW)
        assert report is not None
        assert report.overall_score > 0

    def test_explicit_weight_respected(self):
        """If user sets execution_weight explicitly, it's used."""
        assessor = QualityAssessor(use_llm_judge=False, execution_weight=0.3)
        assert assessor.execution_weight == 0.3

    def test_weight_clamped_to_max(self):
        assessor = QualityAssessor(use_llm_judge=False, execution_weight=0.9)
        assert assessor.execution_weight == 0.4


class TestDetectionCorrelation:
    """Test _compute_detection_correlation method."""

    def setup_method(self):
        self.assessor = QualityAssessor(use_llm_judge=False)

    def test_empty_findings_returns_empty(self):
        result = self.assessor._compute_detection_correlation([], [])
        assert result == {}

    def test_empty_history_returns_empty(self):
        findings = [{"failure_mode": "cycle", "confidence": 0.8}]
        result = self.assessor._compute_detection_correlation(findings, [])
        assert result == {}

    def test_empty_findings_with_history_returns_empty(self):
        history = [{"status": "error", "node_results": {}}]
        result = self.assessor._compute_detection_correlation([], history)
        assert result == {}

    def test_correlation_with_matching_errors(self):
        findings = [{"failure_mode": "cycle", "confidence": 0.85}]
        execution_history = [
            {"status": "error", "node_results": {
                "Agent1": {"status": "error", "error": "Timeout: infinite loop detected"},
            }},
            {"status": "success", "node_results": {}},
        ]

        result = self.assessor._compute_detection_correlation(findings, execution_history)
        assert "cycle" in result
        assert result["cycle"]["execution_confirmed"] is True
        assert result["cycle"]["matching_execution_errors"] > 0
        assert result["cycle"]["count"] == 1
        assert result["cycle"]["avg_confidence"] == 0.85
        # Quality delta should be negative (quality loss)
        assert result["cycle"]["quality_delta"] < 0

    def test_correlation_no_matching_errors(self):
        findings = [{"failure_mode": "schema", "confidence": 0.7}]
        execution_history = [
            {"status": "error", "node_results": {
                "Agent1": {"status": "error", "error": "Connection refused"},
            }},
        ]

        result = self.assessor._compute_detection_correlation(findings, execution_history)
        assert "schema" in result
        assert result["schema"]["execution_confirmed"] is False
        assert result["schema"]["matching_execution_errors"] == 0
        assert result["schema"]["quality_delta"] == 0.0

    def test_correlation_multiple_findings_same_category(self):
        findings = [
            {"failure_mode": "timeout", "confidence": 0.9},
            {"failure_mode": "timeout", "confidence": 0.7},
        ]
        execution_history = [
            {"status": "error", "node_results": {
                "Slow Node": {"status": "error", "error": "Request timed out"},
            }},
        ]

        result = self.assessor._compute_detection_correlation(findings, execution_history)
        assert "timeout" in result
        assert result["timeout"]["count"] == 2
        assert result["timeout"]["avg_confidence"] == 0.8  # (0.9 + 0.7) / 2

    def test_correlation_unknown_category(self):
        """Unknown failure modes get no pattern matching but still appear."""
        findings = [{"failure_mode": "unknown_type", "confidence": 0.5}]
        execution_history = [
            {"status": "error", "node_results": {
                "Node": {"status": "error", "error": "Something broke"},
            }},
        ]

        result = self.assessor._compute_detection_correlation(findings, execution_history)
        assert "unknown_type" in result
        assert result["unknown_type"]["execution_confirmed"] is False


class TestCircularDependencyPenalty:
    """Test that circular dependencies are detected and penalize coupling score."""

    def _make_metrics(self, coupling_ratio: float = 0.5) -> ComplexityMetrics:
        return ComplexityMetrics(
            node_count=3,
            agent_count=2,
            connection_count=2,
            coupling_ratio=coupling_ratio,
        )

    def test_no_cycles_no_penalty(self):
        """Linear workflow A→B has no circular dependencies."""
        workflow = {
            "nodes": [
                {"name": "Agent A", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"systemMessage": "A"}},
                {"name": "Agent B", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"systemMessage": "B"}},
            ],
            "connections": {
                "Agent A": {"main": [[{"node": "Agent B"}]]},
            },
        }
        scorer = OrchestrationQualityScorer(use_llm_judge=False)
        result = scorer._score_agent_coupling(workflow, self._make_metrics())
        assert result.evidence.get("has_circular_dependencies") is False

    def test_cycle_detected_and_penalized(self):
        """A→B→A creates a circular dependency, which should be detected."""
        workflow = {
            "nodes": [
                {"name": "Agent A", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"systemMessage": "A"}},
                {"name": "Agent B", "type": "@n8n/n8n-nodes-langchain.agent", "parameters": {"systemMessage": "B"}},
            ],
            "connections": {
                "Agent A": {"main": [[{"node": "Agent B"}]]},
                "Agent B": {"main": [[{"node": "Agent A"}]]},
            },
        }
        scorer = OrchestrationQualityScorer(use_llm_judge=False)
        # Use low coupling_ratio so the baseline score is high,
        # then the cycle penalty is the main deduction.
        result = scorer._score_agent_coupling(workflow, self._make_metrics(coupling_ratio=0.3))
        assert result.evidence.get("has_circular_dependencies") is True
        # Score should be lower due to cycle penalty
        assert result.score < 1.0
