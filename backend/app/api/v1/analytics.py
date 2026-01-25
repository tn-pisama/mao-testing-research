from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timedelta

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, Trace, State, WorkflowQualityAssessment
from app.core.auth import get_current_tenant
from app.api.v1.schemas import (
    AnalyticsLoopResponse,
    AnalyticsCostResponse,
    QualityAnalyticsResponse,
    DailyScore,
    IssueCount,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/loops", response_model=AnalyticsLoopResponse)
async def get_loop_analytics(
    days: int = Query(30, ge=1, le=365),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(Detection).where(
            Detection.tenant_id == UUID(tenant_id),
            Detection.detection_type == "infinite_loop",
            Detection.created_at >= start_date,
        )
    )
    detections = result.scalars().all()
    
    loops_by_method = {}
    total_loop_length = 0
    agent_counts = {}
    
    for d in detections:
        method = d.method or "unknown"
        loops_by_method[method] = loops_by_method.get(method, 0) + 1
        
        if d.details and "loop_length" in d.details:
            total_loop_length += d.details["loop_length"]
    
    for d in detections:
        if d.state_id:
            state_result = await db.execute(
                select(State).where(State.id == d.state_id)
            )
            state = state_result.scalar_one_or_none()
            if state:
                agent_counts[state.agent_id] = agent_counts.get(state.agent_id, 0) + 1
    
    top_agents = sorted(
        [{"agent_id": k, "count": v} for k, v in agent_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]
    
    time_series = []
    for i in range(min(days, 30)):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        count = sum(
            1 for d in detections
            if day_start <= d.created_at < day_end
        )
        
        time_series.append({
            "date": day_start.isoformat(),
            "count": count,
        })
    
    return AnalyticsLoopResponse(
        total_loops_detected=len(detections),
        loops_by_method=loops_by_method,
        avg_loop_length=total_loop_length / len(detections) if detections else 0,
        top_agents_in_loops=top_agents,
        time_series=time_series[::-1],
    )


@router.get("/cost", response_model=AnalyticsCostResponse)
async def get_cost_analytics(
    days: int = Query(30, ge=1, le=365),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(Trace).where(
            Trace.tenant_id == UUID(tenant_id),
            Trace.created_at >= start_date,
        )
    )
    traces = result.scalars().all()
    
    total_cost = sum(t.total_cost_cents for t in traces)
    total_tokens = sum(t.total_tokens for t in traces)
    
    cost_by_framework = {}
    for t in traces:
        cost_by_framework[t.framework] = cost_by_framework.get(t.framework, 0) + t.total_cost_cents
    
    cost_by_day = []
    for i in range(min(days, 30)):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_cost = sum(
            t.total_cost_cents for t in traces
            if day_start <= t.created_at < day_end
        )
        
        cost_by_day.append({
            "date": day_start.isoformat(),
            "cost_cents": day_cost,
        })
    
    top_expensive = sorted(traces, key=lambda t: t.total_cost_cents, reverse=True)[:10]
    top_expensive_data = [
        {
            "trace_id": str(t.id),
            "session_id": t.session_id,
            "cost_cents": t.total_cost_cents,
            "tokens": t.total_tokens,
        }
        for t in top_expensive
    ]
    
    return AnalyticsCostResponse(
        total_cost_cents=total_cost,
        total_tokens=total_tokens,
        cost_by_framework=cost_by_framework,
        cost_by_day=cost_by_day[::-1],
        top_expensive_traces=top_expensive_data,
    )


@router.get("/quality", response_model=QualityAnalyticsResponse)
async def get_quality_analytics(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get quality analytics for all workflow assessments (all-time data).

    Returns:
    - score_distribution: Histogram of quality scores
    - grade_breakdown: Count by grade (A, B, C, D, F)
    - category_breakdown: Average score by workflow category
    - trend: Daily average scores (all time)
    - top_issues: Most common quality issues
    """
    await set_tenant_context(db, tenant_id)

    # Get all assessments for this tenant
    result = await db.execute(
        select(WorkflowQualityAssessment).where(
            WorkflowQualityAssessment.tenant_id == UUID(tenant_id)
        )
    )
    all_assessments = result.scalars().all()

    # Score distribution (0-10, 10-20, ..., 90-100)
    score_distribution = {f"{i}-{i+10}": 0 for i in range(0, 100, 10)}
    for a in all_assessments:
        score_bucket = (a.overall_score // 10) * 10
        if score_bucket >= 100:
            score_bucket = 90
        key = f"{score_bucket}-{score_bucket + 10}"
        score_distribution[key] = score_distribution.get(key, 0) + 1

    # Grade breakdown
    grade_breakdown = {}
    for a in all_assessments:
        grade = a.overall_grade
        grade_breakdown[grade] = grade_breakdown.get(grade, 0) + 1

    # Category breakdown (by workflow type if available)
    category_scores = {}
    category_counts = {}
    for a in all_assessments:
        # Try to infer category from workflow_id or name
        # For now, use a simple categorization
        category = "general"
        if a.workflow_id and "ai" in a.workflow_id.lower():
            category = "ai_multi_agent"
        elif a.workflow_name and "automation" in a.workflow_name.lower():
            category = "automation"

        if category not in category_scores:
            category_scores[category] = 0.0
            category_counts[category] = 0

        category_scores[category] += a.overall_score / 100.0
        category_counts[category] += 1

    category_breakdown = {
        cat: (category_scores[cat] / category_counts[cat]) if category_counts[cat] > 0 else 0.0
        for cat in category_scores
    }

    # Trend (daily average scores)
    daily_scores = {}
    for a in all_assessments:
        date_key = a.created_at.date().isoformat()
        if date_key not in daily_scores:
            daily_scores[date_key] = {"total": 0.0, "count": 0}
        daily_scores[date_key]["total"] += a.overall_score / 100.0
        daily_scores[date_key]["count"] += 1

    trend = [
        DailyScore(
            date=date,
            avg_score=data["total"] / data["count"] if data["count"] > 0 else 0.0,
            count=data["count"]
        )
        for date, data in sorted(daily_scores.items())
    ]

    # Paginate trend
    offset = (page - 1) * page_size
    has_more = len(trend) > offset + page_size
    trend = trend[offset:offset + page_size]

    # Top issues (from improvements)
    issue_counts = {}
    issue_severity = {}
    for a in all_assessments:
        for imp in a.improvements or []:
            issue_title = imp.get("title", "Unknown issue")
            severity = imp.get("severity", "medium")
            issue_counts[issue_title] = issue_counts.get(issue_title, 0) + 1
            if issue_title not in issue_severity:
                issue_severity[issue_title] = severity

    top_issues = [
        IssueCount(
            issue=issue,
            count=count,
            severity=issue_severity.get(issue, "medium")
        )
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    return QualityAnalyticsResponse(
        score_distribution=score_distribution,
        grade_breakdown=grade_breakdown,
        category_breakdown=category_breakdown,
        trend=trend,
        top_issues=top_issues,
        total_assessments=len(all_assessments),
        page=page,
        page_size=page_size,
        has_more=has_more,
    )
