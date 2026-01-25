"""Tests for quality-detection correlation API endpoint."""

import pytest
from uuid import uuid4
from datetime import datetime

from app.storage.models import WorkflowQualityAssessment, Trace, Detection


@pytest.mark.asyncio
async def test_correlate_with_trace_id(client, test_tenant, db_session):
    """Test correlation endpoint with trace_id."""
    from unittest.mock import MagicMock

    trace_id = uuid4()

    # Create mock trace
    mock_trace = MagicMock(spec=Trace)
    mock_trace.id = trace_id
    mock_trace.tenant_id = test_tenant.id
    mock_trace.session_id = "test-session"
    mock_trace.framework = "n8n"
    mock_trace.status = "completed"
    mock_trace.total_tokens = 1000
    mock_trace.total_cost_cents = 10

    # Create mock quality assessment
    mock_assessment = MagicMock(spec=WorkflowQualityAssessment)
    mock_assessment.tenant_id = test_tenant.id
    mock_assessment.trace_id = trace_id
    mock_assessment.workflow_id = "test-workflow"
    mock_assessment.workflow_name = "Test Workflow"
    mock_assessment.overall_score = 50
    mock_assessment.overall_grade = "C"
    mock_assessment.agent_scores = [
        {
            "agent_id": "agent-1",
            "agent_name": "Test Agent",
            "dimensions": [
                {
                    "dimension": "role_clarity",
                    "score": 0.3,
                    "issues": ["Poor role definition"],
                }
            ]
        }
    ]
    mock_assessment.orchestration_score = {
        "dimensions": [
            {
                "dimension": "complexity_management",
                "score": 0.4,
                "issues": ["High complexity"],
            },
            {
                "dimension": "data_flow_clarity",
                "score": 0.35,
                "issues": ["Unclear data flow"],
            }
        ]
    }
    mock_assessment.improvements = [
        {
            "dimension": "complexity_management",
            "title": "Reduce complexity",
            "severity": "high",
        }
    ]
    mock_assessment.total_issues = 3
    mock_assessment.critical_issues_count = 1
    mock_assessment.source = "test"

    # Create mock detections
    mock_detection1 = MagicMock(spec=Detection)
    mock_detection1.id = uuid4()
    mock_detection1.tenant_id = test_tenant.id
    mock_detection1.trace_id = trace_id
    mock_detection1.detection_type = "infinite_loop"
    mock_detection1.confidence = 85
    mock_detection1.method = "pattern_match"
    mock_detection1.details = {"loop_length": 10}
    mock_detection1.validated = False

    mock_detection2 = MagicMock(spec=Detection)
    mock_detection2.id = uuid4()
    mock_detection2.tenant_id = test_tenant.id
    mock_detection2.trace_id = trace_id
    mock_detection2.detection_type = "persona_drift"
    mock_detection2.confidence = 75
    mock_detection2.method = "semantic_analysis"
    mock_detection2.details = {"drift_score": 0.8}
    mock_detection2.validated = False

    # Configure mock db_session to return these objects
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_assessment
    mock_result.scalars.return_value.all.return_value = [mock_detection1, mock_detection2]
    db_session.execute.return_value = mock_result

    # Test correlation endpoint
    response = await client.post(
        f"/api/v1/quality/tenants/{test_tenant.id}/quality/correlate",
        headers={"X-Tenant-ID": str(test_tenant.id)},
        json={"trace_id": str(trace_id)},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "trace_id" in data
    assert "correlations" in data
    assert "remediation_priorities" in data
    assert "summary" in data

    # Verify correlations exist
    assert len(data["correlations"]) > 0

    # Verify correlation details
    for correlation in data["correlations"]:
        assert "detection_id" in correlation
        assert "detection_type" in correlation
        assert "related_quality_issues" in correlation
        assert "explanation" in correlation
        assert "severity" in correlation

    # Verify remediation priorities
    assert len(data["remediation_priorities"]) > 0


@pytest.mark.asyncio
async def test_correlate_with_quality_report_and_detections(client, test_tenant):
    """Test correlation endpoint with direct quality report and detections."""
    quality_report = {
        "workflow_id": "test-workflow",
        "workflow_name": "Test Workflow",
        "overall_score": 0.5,
        "orchestration_score": {
            "dimensions": [
                {
                    "dimension": "complexity_management",
                    "score": 0.3,
                    "issues": ["High complexity"],
                },
                {
                    "dimension": "data_flow_clarity",
                    "score": 0.4,
                    "issues": ["Unclear data flow"],
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
            "id": str(uuid4()),
            "detection_type": "infinite_loop",
            "confidence": 90,
        },
        {
            "id": str(uuid4()),
            "detection_type": "state_corruption",
            "confidence": 80,
        }
    ]

    response = await client.post(
        f"/api/v1/quality/tenants/{test_tenant.id}/quality/correlate",
        headers={"X-Tenant-ID": str(test_tenant.id)},
        json={
            "quality_report": quality_report,
            "detections": detections,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify correlations
    assert len(data["correlations"]) == 2  # Both detections should correlate

    # Verify infinite_loop correlates with complexity_management and data_flow_clarity
    loop_correlation = next(
        (c for c in data["correlations"] if c["detection_type"] == "infinite_loop"),
        None
    )
    assert loop_correlation is not None
    assert len(loop_correlation["related_quality_issues"]) > 0

    # Check that the related issues include our low-scoring dimensions
    issue_dimensions = [
        issue["dimension"]
        for issue in loop_correlation["related_quality_issues"]
    ]
    assert "complexity_management" in issue_dimensions or "data_flow_clarity" in issue_dimensions


@pytest.mark.asyncio
async def test_correlate_no_quality_issues(client, test_tenant):
    """Test correlation when quality is high (no issues to correlate)."""
    quality_report = {
        "workflow_id": "test-workflow",
        "workflow_name": "Test Workflow",
        "overall_score": 0.9,  # High score
        "orchestration_score": {
            "dimensions": [
                {
                    "dimension": "complexity_management",
                    "score": 0.9,  # Good score
                    "issues": [],
                },
                {
                    "dimension": "data_flow_clarity",
                    "score": 0.95,  # Good score
                    "issues": [],
                }
            ]
        },
        "agent_scores": [],
        "improvements": [],
    }

    detections = [
        {
            "id": str(uuid4()),
            "detection_type": "infinite_loop",
            "confidence": 90,
        }
    ]

    response = await client.post(
        f"/api/v1/quality/tenants/{test_tenant.id}/quality/correlate",
        headers={"X-Tenant-ID": str(test_tenant.id)},
        json={
            "quality_report": quality_report,
            "detections": detections,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # No correlations since quality is high
    assert len(data["correlations"]) == 0
    assert "No direct correlations" in data["summary"]


@pytest.mark.asyncio
async def test_correlate_trace_not_found(client, test_tenant, db_session):
    """Test correlation with non-existent trace."""
    from unittest.mock import MagicMock

    # Configure mock to return None (no assessment found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db_session.execute.return_value = mock_result

    response = await client.post(
        f"/api/v1/quality/tenants/{test_tenant.id}/quality/correlate",
        headers={"X-Tenant-ID": str(test_tenant.id)},
        json={"trace_id": str(uuid4())},
    )

    assert response.status_code == 404
    assert "No quality assessment found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_correlate_missing_input(client, test_tenant):
    """Test correlation without required input."""
    response = await client.post(
        f"/api/v1/quality/tenants/{test_tenant.id}/quality/correlate",
        headers={"X-Tenant-ID": str(test_tenant.id)},
        json={},
    )

    assert response.status_code == 400
    assert "Either trace_id or quality_report must be provided" in response.json()["detail"]


@pytest.mark.asyncio
async def test_remediation_priority_ordering(client, test_tenant):
    """Test that remediation priorities are correctly ordered by impact."""
    quality_report = {
        "workflow_id": "test-workflow",
        "workflow_name": "Test Workflow",
        "overall_score": 0.4,
        "orchestration_score": {
            "dimensions": [
                {
                    "dimension": "complexity_management",
                    "score": 0.3,
                    "issues": ["High complexity"],
                },
                {
                    "dimension": "data_flow_clarity",
                    "score": 0.35,
                    "issues": ["Unclear data flow"],
                },
                {
                    "dimension": "best_practices",
                    "score": 0.4,
                    "issues": ["Missing best practices"],
                }
            ]
        },
        "agent_scores": [],
        "improvements": [
            {
                "dimension": "complexity_management",
                "title": "Reduce complexity",
                "severity": "high",
            },
            {
                "dimension": "data_flow_clarity",
                "title": "Clarify data flow",
                "severity": "medium",
            },
            {
                "dimension": "best_practices",
                "title": "Add error handling",
                "severity": "medium",
            }
        ],
    }

    # Multiple detections that correlate with complexity_management
    detections = [
        {
            "id": str(uuid4()),
            "detection_type": "infinite_loop",
            "confidence": 90,
        },
        {
            "id": str(uuid4()),
            "detection_type": "semantic_loop",
            "confidence": 85,
        },
        {
            "id": str(uuid4()),
            "detection_type": "state_corruption",
            "confidence": 80,
        }
    ]

    response = await client.post(
        f"/api/v1/quality/tenants/{test_tenant.id}/quality/correlate",
        headers={"X-Tenant-ID": str(test_tenant.id)},
        json={
            "quality_report": quality_report,
            "detections": detections,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify remediation priorities are ordered
    priorities = data["remediation_priorities"]
    assert len(priorities) > 0

    # First priority should have highest detection_impact
    if len(priorities) > 1:
        assert priorities[0]["detection_impact"] >= priorities[1]["detection_impact"]
