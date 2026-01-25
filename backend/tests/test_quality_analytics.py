"""Tests for quality analytics endpoint."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.storage.models import WorkflowQualityAssessment


@pytest.mark.asyncio
async def test_quality_analytics_empty(client, test_tenant, db_session):
    """Test quality analytics with no assessments."""
    from unittest.mock import MagicMock

    # Configure mock to return empty list
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db_session.execute.return_value = mock_result

    response = await client.get(
        f"/api/v1/tenants/{test_tenant.id}/analytics/quality",
        headers={"X-Tenant-ID": str(test_tenant.id)},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_assessments"] == 0
    assert data["score_distribution"] == {
        "0-10": 0, "10-20": 0, "20-30": 0, "30-40": 0, "40-50": 0,
        "50-60": 0, "60-70": 0, "70-80": 0, "80-90": 0, "90-100": 0,
    }
    assert data["grade_breakdown"] == {}
    assert data["trend"] == []
    assert data["top_issues"] == []


@pytest.mark.asyncio
async def test_quality_analytics_with_data(client, test_tenant, db_session):
    """Test quality analytics with sample assessments."""
    from unittest.mock import MagicMock

    # Create sample assessments (mock objects)
    assessments = []
    for i in range(5):
        assessment = MagicMock(spec=WorkflowQualityAssessment)
        assessment.tenant_id = test_tenant.id
        assessment.workflow_id = f"workflow-{i}"
        assessment.workflow_name = f"Test Workflow {i}"
        assessment.overall_score = 70 + (i * 5)  # 70, 75, 80, 85, 90
        assessment.overall_grade = "B" if i < 2 else "B+" if i < 4 else "A"
        assessment.agent_scores = []
        assessment.orchestration_score = {
            "dimensions": [
                {
                    "dimension": "data_flow_clarity",
                    "score": 0.8,
                    "issues": ["Minor issue"],
                }
            ]
        }
        assessment.improvements = [
            {
                "title": "Improve error handling",
                "severity": "medium",
            },
            {
                "title": "Add documentation",
                "severity": "low",
            }
        ]
        assessment.total_issues = 2
        assessment.critical_issues_count = 0
        assessment.source = "test"
        assessment.created_at = datetime.utcnow() - timedelta(days=i)
        assessments.append(assessment)

    # Configure mock to return assessments
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = assessments
    db_session.execute.return_value = mock_result

    # Test analytics endpoint
    response = await client.get(
        f"/api/v1/tenants/{test_tenant.id}/analytics/quality",
        headers={"X-Tenant-ID": str(test_tenant.id)},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify total
    assert data["total_assessments"] == 5

    # Verify score distribution
    assert data["score_distribution"]["70-80"] == 2  # 70, 75
    assert data["score_distribution"]["80-90"] == 2  # 80, 85
    assert data["score_distribution"]["90-100"] == 1  # 90

    # Verify grade breakdown
    assert data["grade_breakdown"]["B"] == 2
    assert data["grade_breakdown"]["B+"] == 2
    assert data["grade_breakdown"]["A"] == 1

    # Verify trend exists
    assert len(data["trend"]) > 0
    assert all("date" in t and "avg_score" in t and "count" in t for t in data["trend"])

    # Verify top issues
    assert len(data["top_issues"]) == 2
    issue_titles = [issue["issue"] for issue in data["top_issues"]]
    assert "Improve error handling" in issue_titles
    assert "Add documentation" in issue_titles


@pytest.mark.asyncio
async def test_quality_analytics_pagination(client, test_tenant, db_session):
    """Test quality analytics pagination."""
    from unittest.mock import MagicMock

    # Create many assessments (mock objects)
    assessments = []
    for i in range(150):
        assessment = MagicMock(spec=WorkflowQualityAssessment)
        assessment.tenant_id = test_tenant.id
        assessment.workflow_id = f"workflow-{i}"
        assessment.workflow_name = f"Test Workflow {i}"
        assessment.overall_score = 50 + (i % 50)
        assessment.overall_grade = "C"
        assessment.agent_scores = []
        assessment.orchestration_score = {}
        assessment.improvements = []
        assessment.total_issues = 0
        assessment.critical_issues_count = 0
        assessment.source = "test"
        assessment.created_at = datetime.utcnow() - timedelta(days=i)
        assessments.append(assessment)

    # Configure mock to return assessments
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = assessments
    db_session.execute.return_value = mock_result

    # Test first page
    response = await client.get(
        f"/api/v1/tenants/{test_tenant.id}/analytics/quality?page=1&page_size=100",
        headers={"X-Tenant-ID": str(test_tenant.id)},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_assessments"] == 150
    assert data["page"] == 1
    assert data["page_size"] == 100
    assert data["has_more"] is True
    assert len(data["trend"]) == 100

    # Test second page
    response2 = await client.get(
        f"/api/v1/tenants/{test_tenant.id}/analytics/quality?page=2&page_size=100",
        headers={"X-Tenant-ID": str(test_tenant.id)},
    )

    assert response2.status_code == 200
    data2 = response2.json()

    assert data2["page"] == 2
    assert data2["has_more"] is False
    assert len(data2["trend"]) == 50  # Remaining 50 days


@pytest.mark.asyncio
async def test_quality_analytics_category_breakdown(client, test_tenant, db_session):
    """Test category breakdown in analytics."""
    from unittest.mock import MagicMock

    assessments = []

    # Create AI workflows (mock objects)
    for i in range(3):
        assessment = MagicMock(spec=WorkflowQualityAssessment)
        assessment.tenant_id = test_tenant.id
        assessment.workflow_id = f"ai-workflow-{i}"
        assessment.workflow_name = f"AI Workflow {i}"
        assessment.overall_score = 80
        assessment.overall_grade = "B+"
        assessment.agent_scores = []
        assessment.orchestration_score = {}
        assessment.improvements = []
        assessment.total_issues = 0
        assessment.critical_issues_count = 0
        assessment.source = "test"
        assessment.created_at = datetime.utcnow()
        assessments.append(assessment)

    # Create automation workflows (mock objects)
    for i in range(2):
        assessment = MagicMock(spec=WorkflowQualityAssessment)
        assessment.tenant_id = test_tenant.id
        assessment.workflow_id = f"workflow-{i}"
        assessment.workflow_name = f"Automation Workflow {i}"
        assessment.overall_score = 70
        assessment.overall_grade = "B"
        assessment.agent_scores = []
        assessment.orchestration_score = {}
        assessment.improvements = []
        assessment.total_issues = 0
        assessment.critical_issues_count = 0
        assessment.source = "test"
        assessment.created_at = datetime.utcnow()
        assessments.append(assessment)

    # Configure mock to return assessments
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = assessments
    db_session.execute.return_value = mock_result

    response = await client.get(
        f"/api/v1/tenants/{test_tenant.id}/analytics/quality",
        headers={"X-Tenant-ID": str(test_tenant.id)},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify categories
    assert "ai_multi_agent" in data["category_breakdown"]
    assert "automation" in data["category_breakdown"]
    assert abs(data["category_breakdown"]["ai_multi_agent"] - 0.8) < 0.01
    assert abs(data["category_breakdown"]["automation"] - 0.7) < 0.01
