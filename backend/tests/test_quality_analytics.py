"""Tests for quality analytics endpoint."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.storage.models import WorkflowQualityAssessment


@pytest.mark.asyncio
async def test_quality_analytics_empty(client, test_tenant):
    """Test quality analytics with no assessments."""
    response = await client.get(
        f"/api/v1/analytics/quality",
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
    # Create sample assessments
    assessments = []
    for i in range(5):
        assessment = WorkflowQualityAssessment(
            tenant_id=test_tenant.id,
            workflow_id=f"workflow-{i}",
            workflow_name=f"Test Workflow {i}",
            overall_score=70 + (i * 5),  # 70, 75, 80, 85, 90
            overall_grade="B" if i < 2 else "B+" if i < 4 else "A",
            agent_scores=[],
            orchestration_score={
                "dimensions": [
                    {
                        "dimension": "data_flow_clarity",
                        "score": 0.8,
                        "issues": ["Minor issue"],
                    }
                ]
            },
            improvements=[
                {
                    "title": "Improve error handling",
                    "severity": "medium",
                },
                {
                    "title": "Add documentation",
                    "severity": "low",
                }
            ],
            total_issues=2,
            critical_issues_count=0,
            source="test",
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        db_session.add(assessment)
        assessments.append(assessment)

    await db_session.commit()

    # Test analytics endpoint
    response = await client.get(
        f"/api/v1/analytics/quality",
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
    # Create many assessments spread over many days
    for i in range(150):
        assessment = WorkflowQualityAssessment(
            tenant_id=test_tenant.id,
            workflow_id=f"workflow-{i}",
            workflow_name=f"Test Workflow {i}",
            overall_score=50 + (i % 50),
            overall_grade="C",
            agent_scores=[],
            orchestration_score={},
            improvements=[],
            total_issues=0,
            critical_issues_count=0,
            source="test",
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        db_session.add(assessment)

    await db_session.commit()

    # Test first page
    response = await client.get(
        f"/api/v1/analytics/quality?page=1&page_size=100",
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
        f"/api/v1/analytics/quality?page=2&page_size=100",
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
    # Create AI workflows
    for i in range(3):
        assessment = WorkflowQualityAssessment(
            tenant_id=test_tenant.id,
            workflow_id=f"ai-workflow-{i}",
            workflow_name=f"AI Workflow {i}",
            overall_score=80,
            overall_grade="B+",
            agent_scores=[],
            orchestration_score={},
            improvements=[],
            total_issues=0,
            critical_issues_count=0,
            source="test",
        )
        db_session.add(assessment)

    # Create automation workflows
    for i in range(2):
        assessment = WorkflowQualityAssessment(
            tenant_id=test_tenant.id,
            workflow_id=f"workflow-{i}",
            workflow_name=f"Automation Workflow {i}",
            overall_score=70,
            overall_grade="B",
            agent_scores=[],
            orchestration_score={},
            improvements=[],
            total_issues=0,
            critical_issues_count=0,
            source="test",
        )
        db_session.add(assessment)

    await db_session.commit()

    response = await client.get(
        f"/api/v1/analytics/quality",
        headers={"X-Tenant-ID": str(test_tenant.id)},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify categories
    assert "ai_multi_agent" in data["category_breakdown"]
    assert "automation" in data["category_breakdown"]
    assert data["category_breakdown"]["ai_multi_agent"] == 0.8
    assert data["category_breakdown"]["automation"] == 0.7
