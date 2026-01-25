"""Tests for Phase 5 quality dimensions: test_coverage and layout_quality."""

import pytest
from app.enterprise.quality import QualityAssessor


def test_test_coverage_no_pindata():
    """Test test_coverage dimension with no pinData."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    # Find test_coverage dimension
    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    assert "test_coverage" in orch_dims

    test_cov = orch_dims["test_coverage"]
    assert test_cov.score == 0.4  # Low score for no test data
    assert "No test data (pinData) found" in test_cov.issues
    assert "Add test data to key nodes" in test_cov.suggestions[0]


def test_test_coverage_partial():
    """Test test_coverage dimension with partial pinData coverage."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
                "pinData": {"output": [{"test": "data"}]},  # Has test data
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            },
            {
                "id": "node3",
                "name": "Agent 3",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 300, "y": 100},
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    test_cov = orch_dims["test_coverage"]

    # 1 out of 3 nodes = 0.33 coverage
    # score = 0.5 + (0.33 * 0.5) = 0.665
    assert test_cov.score > 0.5
    assert test_cov.score < 0.7
    assert test_cov.evidence["nodes_with_test_data"] == 1
    assert test_cov.evidence["total_nodes"] == 3
    assert test_cov.evidence["coverage_ratio"] == pytest.approx(0.333, abs=0.01)


def test_test_coverage_good():
    """Test test_coverage dimension with good pinData coverage."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
                "pinData": {"output": [{"test": "data"}]},
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
                "pinData": {"output": [{"test": "data2"}]},
            },
            {
                "id": "node3",
                "name": "Agent 3",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 300, "y": 100},
                "pinData": {"output": [{"test": "data3"}]},
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    test_cov = orch_dims["test_coverage"]

    # 3 out of 3 nodes = 1.0 coverage
    # score = 0.5 + (1.0 * 0.5) = 1.0
    assert test_cov.score == 1.0
    assert test_cov.evidence["nodes_with_test_data"] == 3
    assert test_cov.evidence["coverage_ratio"] == 1.0
    assert len(test_cov.issues) == 0


def test_layout_quality_overlapping_nodes():
    """Test layout_quality dimension with overlapping node positions."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},  # Same position as node1
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    assert "layout_quality" in orch_dims

    layout = orch_dims["layout_quality"]
    assert "Overlapping node positions detected" in layout.issues
    assert layout.score < 1.0
    assert layout.evidence["total_nodes"] == 2
    assert layout.evidence["unique_positions"] == 1


def test_layout_quality_scattered():
    """Test layout_quality dimension with scattered layout."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 10000, "y": 0},  # Very far away
            },
            {
                "id": "node3",
                "name": "Agent 3",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 0, "y": 10000},  # Very far away
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    layout = orch_dims["layout_quality"]

    # Should detect scattered layout
    assert "Scattered horizontal layout" in layout.issues or len(layout.suggestions) > 0
    assert layout.score < 1.0
    assert layout.evidence["x_variance"] > 100000


def test_layout_quality_organized():
    """Test layout_quality dimension with organized layout."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            },
            {
                "id": "node3",
                "name": "Agent 3",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 300, "y": 100},
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    layout = orch_dims["layout_quality"]

    # Should have good layout score
    assert layout.score >= 0.9  # High score for organized layout
    assert layout.evidence["unique_positions"] == 3
    assert layout.evidence["x_variance"] < 100000  # Low variance


def test_layout_quality_single_node():
    """Test layout_quality dimension with single node (should return None)."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    # Layout quality should not be scored for single node
    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    assert "layout_quality" not in orch_dims


def test_phase5_dimensions_in_total_count():
    """Test that Phase 5 dimensions are included in total dimension count."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
                "pinData": {"output": [{"test": "data"}]},
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            }
        ],
        "connections": {
            "Agent 1": {
                "main": [
                    [
                        {
                            "node": "Agent 2",
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            }
        }
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    dimension_names = [d.dimension for d in report.orchestration_score.dimensions]

    # Verify Phase 5 dimensions are present
    assert "test_coverage" in dimension_names
    assert "layout_quality" in dimension_names

    # Verify we now have 10 orchestration dimensions total
    # 5 base + 3 Phase 4 + 2 Phase 5 = 10
    # Base: data_flow_clarity, complexity_management, agent_coupling, observability, best_practices
    # Phase 4: documentation_quality, ai_architecture, maintenance_quality
    # Phase 5: test_coverage, layout_quality
    assert len(report.orchestration_score.dimensions) == 10


def test_phase5_dimensions_weight():
    """Test that Phase 5 dimensions have appropriate weights."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
                "pinData": {"output": [{"test": "data"}]},
            },
            {
                "id": "node2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            }
        ],
        "connections": {}
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}

    # Test coverage weight should be 0.6
    assert orch_dims["test_coverage"].weight == 0.6

    # Layout quality weight should be 0.4 (lower priority)
    assert orch_dims["layout_quality"].weight == 0.4


def test_real_world_workflow_with_phase5():
    """Test Phase 5 dimensions on a realistic workflow."""
    workflow = {
        "id": "real-workflow",
        "name": "Customer Support AI",
        "nodes": [
            {
                "id": "1",
                "name": "Classify Intent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 200},
                "pinData": {"output": [{"intent": "billing"}]},
            },
            {
                "id": "2",
                "name": "Extract Details",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 300, "y": 200},
                "pinData": {"output": [{"customer_id": "123"}]},
            },
            {
                "id": "3",
                "name": "Generate Response",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 500, "y": 200},
            },
            {
                "id": "4",
                "name": "Send Email",
                "type": "n8n-nodes-base.emailSend",
                "position": {"x": 700, "y": 200},
            }
        ],
        "connections": {
            "Classify Intent": {
                "main": [[{"node": "Extract Details", "type": "main", "index": 0}]]
            },
            "Extract Details": {
                "main": [[{"node": "Generate Response", "type": "main", "index": 0}]]
            },
            "Generate Response": {
                "main": [[{"node": "Send Email", "type": "main", "index": 0}]]
            }
        }
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    orch_dims = {d.dimension: d for d in report.orchestration_score.dimensions}

    # Test coverage: 2 out of 4 nodes = 50%
    test_cov = orch_dims["test_coverage"]
    assert test_cov.score > 0.5  # Should be reasonable
    assert test_cov.evidence["nodes_with_test_data"] == 2
    assert test_cov.evidence["coverage_ratio"] == 0.5

    # Layout quality: organized horizontal layout
    layout = orch_dims["layout_quality"]
    assert layout.score >= 0.8  # Should be good for organized layout
    assert layout.evidence["unique_positions"] == 4

    # Overall score should be reasonable (workflow has some quality issues but isn't failing)
    assert report.overall_score > 0.4
