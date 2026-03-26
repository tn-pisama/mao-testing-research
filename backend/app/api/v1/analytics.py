from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float, text
from sqlalchemy.sql import label
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
    tid = UUID(tenant_id)
    start_date = datetime.utcnow() - timedelta(days=days)

    base_filter = [
        Detection.tenant_id == tid,
        Detection.detection_type == "infinite_loop",
        Detection.created_at >= start_date,
    ]

    # Total count + avg loop length + method breakdown — single query
    method_result = await db.execute(
        select(
            func.coalesce(Detection.method, "unknown").label("method"),
            func.count().label("cnt"),
        )
        .where(*base_filter)
        .group_by(func.coalesce(Detection.method, "unknown"))
    )
    method_rows = method_result.all()
    loops_by_method = {row.method: row.cnt for row in method_rows}
    total_loops = sum(row.cnt for row in method_rows)

    # Avg loop length from JSONB
    avg_result = await db.execute(
        select(
            func.avg(cast(Detection.details["loop_length"].as_string(), Float))
        )
        .where(*base_filter)
        .where(Detection.details["loop_length"] != None)  # noqa: E711
    )
    avg_loop_length = avg_result.scalar() or 0

    # Top agents — JOIN instead of N+1
    agent_result = await db.execute(
        select(
            State.agent_id,
            func.count().label("cnt"),
        )
        .select_from(Detection)
        .join(State, Detection.state_id == State.id)
        .where(*base_filter)
        .group_by(State.agent_id)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_agents = [
        {"agent_id": row.agent_id, "count": row.cnt}
        for row in agent_result.all()
    ]

    # Time series — SQL date_trunc
    ts_result = await db.execute(
        select(
            func.date_trunc("day", Detection.created_at).label("day"),
            func.count().label("cnt"),
        )
        .where(*base_filter)
        .group_by(text("1"))
        .order_by(text("1"))
    )
    ts_map = {row.day.date(): row.cnt for row in ts_result.all()}

    # Fill in all days (including zeros)
    time_series = []
    for i in range(min(days, 30)):
        day = (datetime.utcnow() - timedelta(days=min(days, 30) - 1 - i)).date()
        time_series.append({
            "date": datetime(day.year, day.month, day.day).isoformat(),
            "count": ts_map.get(day, 0),
        })

    return AnalyticsLoopResponse(
        total_loops_detected=total_loops,
        loops_by_method=loops_by_method,
        avg_loop_length=float(avg_loop_length),
        top_agents_in_loops=top_agents,
        time_series=time_series,
    )


@router.get("/cost", response_model=AnalyticsCostResponse)
async def get_cost_analytics(
    days: int = Query(30, ge=1, le=365),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    tid = UUID(tenant_id)
    start_date = datetime.utcnow() - timedelta(days=days)

    base_filter = [
        Trace.tenant_id == tid,
        Trace.created_at >= start_date,
    ]

    # Totals + framework breakdown — single query
    fw_result = await db.execute(
        select(
            Trace.framework,
            func.sum(Trace.total_cost_cents).label("cost"),
            func.sum(Trace.total_tokens).label("tokens"),
        )
        .where(*base_filter)
        .group_by(Trace.framework)
    )
    fw_rows = fw_result.all()
    total_cost = sum(row.cost or 0 for row in fw_rows)
    total_tokens = sum(row.tokens or 0 for row in fw_rows)
    cost_by_framework = {row.framework: row.cost or 0 for row in fw_rows}

    # Daily cost — SQL date_trunc
    daily_result = await db.execute(
        select(
            func.date_trunc("day", Trace.created_at).label("day"),
            func.sum(Trace.total_cost_cents).label("cost"),
        )
        .where(*base_filter)
        .group_by(text("1"))
        .order_by(text("1"))
    )
    daily_map = {row.day.date(): row.cost or 0 for row in daily_result.all()}

    cost_by_day = []
    for i in range(min(days, 30)):
        day = (datetime.utcnow() - timedelta(days=min(days, 30) - 1 - i)).date()
        cost_by_day.append({
            "date": datetime(day.year, day.month, day.day).isoformat(),
            "cost_cents": daily_map.get(day, 0),
        })

    # Top 10 expensive traces — just ORDER BY + LIMIT
    top_result = await db.execute(
        select(
            Trace.id,
            Trace.session_id,
            Trace.total_cost_cents,
            Trace.total_tokens,
        )
        .where(*base_filter)
        .order_by(Trace.total_cost_cents.desc())
        .limit(10)
    )
    top_expensive_data = [
        {
            "trace_id": str(row.id),
            "session_id": row.session_id,
            "cost_cents": row.total_cost_cents,
            "tokens": row.total_tokens,
        }
        for row in top_result.all()
    ]

    return AnalyticsCostResponse(
        total_cost_cents=total_cost,
        total_tokens=total_tokens,
        cost_by_framework=cost_by_framework,
        cost_by_day=cost_by_day,
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
