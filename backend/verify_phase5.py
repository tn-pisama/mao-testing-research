#!/usr/bin/env python3
"""Verification script for Phase 5 implementation."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.models import OrchestrationDimension
from app.detection.quality_correlation import (
    correlate_quality_to_detections,
    get_remediation_priority,
)


def test_new_dimensions():
    """Test that new dimensions are registered."""
    print("Testing new dimension enums...")

    # Check enum values
    assert hasattr(OrchestrationDimension, 'TEST_COVERAGE')
    assert hasattr(OrchestrationDimension, 'LAYOUT_QUALITY')

    print("✓ TEST_COVERAGE dimension enum exists")
    print("✓ LAYOUT_QUALITY dimension enum exists")

    return True


def test_test_coverage_scoring():
    """Test test_coverage dimension scoring."""
    print("\nTesting test_coverage dimension scoring...")

    workflow = {
        "id": "test",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Node 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
                "pinData": {"output": [{"test": "data"}]},
            },
            {
                "id": "2",
                "name": "Node 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            },
        ],
        "connections": {},
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    # Check that test_coverage dimension exists
    dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    assert "test_coverage" in dims

    test_cov = dims["test_coverage"]
    print(f"✓ test_coverage dimension found")
    print(f"  Score: {test_cov.score:.2f}")
    print(f"  Evidence: {test_cov.evidence}")

    # Should have 1 node with test data out of 2
    assert test_cov.evidence["nodes_with_test_data"] == 1
    assert test_cov.evidence["total_nodes"] == 2

    print("✓ test_coverage scoring works correctly")

    return True


def test_layout_quality_scoring():
    """Test layout_quality dimension scoring."""
    print("\nTesting layout_quality dimension scoring...")

    workflow = {
        "id": "test",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Node 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
            },
            {
                "id": "2",
                "name": "Node 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            },
        ],
        "connections": {},
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    # Check that layout_quality dimension exists
    dims = {d.dimension: d for d in report.orchestration_score.dimensions}
    assert "layout_quality" in dims

    layout = dims["layout_quality"]
    print(f"✓ layout_quality dimension found")
    print(f"  Score: {layout.score:.2f}")
    print(f"  Evidence: {layout.evidence}")

    # Should have 2 unique positions
    assert layout.evidence["unique_positions"] == 2

    print("✓ layout_quality scoring works correctly")

    return True


def test_total_dimension_count():
    """Test that we have 10 orchestration dimensions total."""
    print("\nTesting total dimension count...")

    workflow = {
        "id": "test",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Agent 1",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 100, "y": 100},
                "pinData": {"output": [{"test": "data"}]},
            },
            {
                "id": "2",
                "name": "Agent 2",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "position": {"x": 200, "y": 100},
            },
        ],
        "connections": {
            "Agent 1": {
                "main": [[{"node": "Agent 2", "type": "main", "index": 0}]]
            }
        },
    }

    assessor = QualityAssessor()
    report = assessor.assess_workflow(workflow)

    dimension_names = [d.dimension for d in report.orchestration_score.dimensions]

    print(f"Total orchestration dimensions: {len(dimension_names)}")
    print(f"Dimensions: {dimension_names}")

    # Should have 10 dimensions:
    # 5 base + 3 Phase 4 + 2 Phase 5
    assert len(dimension_names) == 10

    # Verify all expected dimensions are present
    expected = [
        "data_flow_clarity",
        "complexity_management",
        "agent_coupling",
        "observability",
        "best_practices",
        "documentation_quality",
        "ai_architecture",
        "maintenance_quality",
        "test_coverage",
        "layout_quality",
    ]

    for exp in expected:
        assert exp in dimension_names, f"Missing dimension: {exp}"

    print("✓ All 10 orchestration dimensions present")

    return True


def test_correlation_functions():
    """Test that correlation functions exist and work."""
    print("\nTesting correlation functions...")

    quality_report = {
        "workflow_id": "test",
        "workflow_name": "Test",
        "overall_score": 0.4,
        "orchestration_score": {
            "dimensions": [
                {
                    "dimension": "complexity_management",
                    "score": 0.3,
                    "issues": ["High complexity"],
                }
            ]
        },
        "agent_scores": [],
        "improvements": [
            {
                "dimension": "complexity_management",
                "title": "Reduce complexity",
                "severity": "high",
            }
        ],
    }

    detections = [
        {
            "id": "det-1",
            "detection_type": "infinite_loop",
            "confidence": 90,
        }
    ]

    # Test correlation
    result = correlate_quality_to_detections(quality_report, detections)
    print(f"✓ correlate_quality_to_detections works")
    print(f"  Correlations found: {len(result.correlations)}")
    print(f"  Summary: {result.summary}")

    # Test remediation priority
    priorities = get_remediation_priority(quality_report, detections)
    print(f"✓ get_remediation_priority works")
    print(f"  Priorities returned: {len(priorities)}")

    return True


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Phase 5 Implementation Verification")
    print("=" * 60)

    tests = [
        test_new_dimensions,
        test_test_coverage_scoring,
        test_layout_quality_scoring,
        test_total_dimension_count,
        test_correlation_functions,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✓ All Phase 5 verification tests passed!")
        return 0
    else:
        print(f"\n✗ {failed} verification test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
