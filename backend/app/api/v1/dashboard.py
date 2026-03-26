"""Combined dashboard endpoint — returns all dashboard data in a single request."""

import asyncio
import json
import logging
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Float, text
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.sql.expression import literal_column
from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, Trace, State, WorkflowQualityAssessment
from app.core.auth import get_current_tenant
from app.core.rate_limit import rate_limiter
from app.api.v1.detections import detection_to_response

logger = logging.getLogger(__name__)

DASHBOARD_CACHE_TTL = 300  # 5 minutes

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardResponse(BaseModel):
    loop_analytics: Dict[str, Any]
    cost_analytics: Dict[str, Any]
    detections: Dict[str, Any]
    traces: Dict[str, Any]
    quality_assessments: Dict[str, Any]


async def _loop_analytics(db: AsyncSession, tid: UUID, start_date: datetime) -> dict:
    base_filter = [
        Detection.tenant_id == tid,
        Detection.detection_type == "infinite_loop",
        Detection.created_at >= start_date,
    ]

    method_expr = func.coalesce(Detection.method, literal_column("'unknown'"))
    method_result = await db.execute(
        select(
            method_expr.label("method"),
            func.count().label("cnt"),
        ).where(*base_filter).group_by(method_expr)
    )
    method_rows = method_result.all()
    total = sum(r.cnt for r in method_rows)

    avg_result = await db.execute(
        select(func.avg(cast(Detection.details["loop_length"].as_string(), Float)))
        .where(*base_filter)
        .where(Detection.details["loop_length"] != None)  # noqa: E711
    )

    agent_result = await db.execute(
        select(State.agent_id, func.count().label("cnt"))
        .select_from(Detection).join(State, Detection.state_id == State.id)
        .where(*base_filter)
        .group_by(State.agent_id).order_by(func.count().desc()).limit(10)
    )

    ts_result = await db.execute(
        select(func.date_trunc("day", Detection.created_at).label("day"), func.count().label("cnt"))
        .where(*base_filter).group_by(text("1")).order_by(text("1"))
    )
    ts_map = {r.day.date(): r.cnt for r in ts_result.all()}
    days = min(30, (datetime.utcnow().date() - start_date.date()).days + 1)
    time_series = []
    for i in range(days):
        d = (start_date + timedelta(days=i)).date()
        time_series.append({"date": datetime(d.year, d.month, d.day).isoformat(), "count": ts_map.get(d, 0)})

    return {
        "total_loops_detected": total,
        "loops_by_method": {r.method: r.cnt for r in method_rows},
        "avg_loop_length": float(avg_result.scalar() or 0),
        "top_agents_in_loops": [{"agent_id": r.agent_id, "count": r.cnt} for r in agent_result.all()],
        "time_series": time_series,
    }


async def _cost_analytics(db: AsyncSession, tid: UUID, start_date: datetime) -> dict:
    base_filter = [Trace.tenant_id == tid, Trace.created_at >= start_date]

    fw_result = await db.execute(
        select(Trace.framework, func.sum(Trace.total_cost_cents).label("cost"), func.sum(Trace.total_tokens).label("tokens"))
        .where(*base_filter).group_by(Trace.framework)
    )
    fw_rows = fw_result.all()

    daily_result = await db.execute(
        select(func.date_trunc("day", Trace.created_at).label("day"), func.sum(Trace.total_cost_cents).label("cost"))
        .where(*base_filter).group_by(text("1")).order_by(text("1"))
    )
    daily_map = {r.day.date(): r.cost or 0 for r in daily_result.all()}
    days = min(30, (datetime.utcnow().date() - start_date.date()).days + 1)
    cost_by_day = []
    for i in range(days):
        d = (start_date + timedelta(days=i)).date()
        cost_by_day.append({"date": datetime(d.year, d.month, d.day).isoformat(), "cost_cents": daily_map.get(d, 0)})

    top_result = await db.execute(
        select(Trace.id, Trace.session_id, Trace.total_cost_cents, Trace.total_tokens)
        .where(*base_filter).order_by(Trace.total_cost_cents.desc()).limit(10)
    )

    return {
        "total_cost_cents": sum(r.cost or 0 for r in fw_rows),
        "total_tokens": sum(r.tokens or 0 for r in fw_rows),
        "cost_by_framework": {r.framework: r.cost or 0 for r in fw_rows},
        "cost_by_day": cost_by_day,
        "top_expensive_traces": [
            {"trace_id": str(r.id), "session_id": r.session_id, "cost_cents": r.total_cost_cents, "tokens": r.total_tokens}
            for r in top_result.all()
        ],
    }


async def _recent_detections(db: AsyncSession, tid: UUID, limit: int = 10) -> dict:
    count_result = await db.execute(
        select(func.count()).where(Detection.tenant_id == tid)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Detection).where(Detection.tenant_id == tid)
        .order_by(Detection.created_at.desc()).limit(limit)
    )
    detections = result.scalars().all()

    return {
        "items": [_detection_dict(d) for d in detections],
        "total": total,
        "page": 1,
        "per_page": limit,
    }


def _detection_dict(d: Detection) -> dict:
    """Lightweight detection serialization for dashboard (skip heavy explanations)."""
    conf_pct = d.confidence / 100.0 if d.confidence else 0.0
    tier = "HIGH" if conf_pct >= 0.80 else "LIKELY" if conf_pct >= 0.60 else "POSSIBLE" if conf_pct >= 0.40 else "LOW"
    return {
        "id": str(d.id),
        "trace_id": str(d.trace_id),
        "state_id": str(d.state_id) if d.state_id else None,
        "detection_type": d.detection_type,
        "confidence": d.confidence,
        "method": d.method,
        "details": d.details,
        "validated": d.validated,
        "false_positive": d.false_positive,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "confidence_tier": tier,
        "detector_method": d.method,
    }


async def _recent_traces(db: AsyncSession, tid: UUID, limit: int = 10) -> dict:
    count_result = await db.execute(
        select(func.count()).where(Trace.tenant_id == tid)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Trace).where(Trace.tenant_id == tid)
        .order_by(Trace.created_at.desc()).limit(limit)
    )
    traces = result.scalars().all()

    if not traces:
        return {"traces": [], "total": total, "page": 1, "per_page": limit}

    trace_ids = [t.id for t in traces]
    state_counts = dict((await db.execute(
        select(State.trace_id, func.count().label("c")).where(State.trace_id.in_(trace_ids)).group_by(State.trace_id)
    )).all())
    det_counts = dict((await db.execute(
        select(Detection.trace_id, func.count().label("c")).where(Detection.trace_id.in_(trace_ids)).group_by(Detection.trace_id)
    )).all())

    return {
        "traces": [
            {
                "id": str(t.id),
                "session_id": t.session_id,
                "framework": t.framework,
                "status": t.status,
                "total_tokens": t.total_tokens,
                "total_cost_cents": t.total_cost_cents,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "state_count": state_counts.get(t.id, 0),
                "detection_count": det_counts.get(t.id, 0),
            }
            for t in traces
        ],
        "total": total,
        "page": 1,
        "per_page": limit,
    }


async def _quality_assessments(db: AsyncSession, tid: UUID, limit: int = 20) -> dict:
    count_result = await db.execute(
        select(func.count()).where(WorkflowQualityAssessment.tenant_id == tid)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(WorkflowQualityAssessment).where(WorkflowQualityAssessment.tenant_id == tid)
        .order_by(WorkflowQualityAssessment.created_at.desc()).limit(limit)
    )
    assessments = result.scalars().all()

    return {
        "assessments": [
            {
                "id": str(a.id),
                "workflow_id": a.workflow_id,
                "workflow_name": a.workflow_name,
                "trace_id": str(a.trace_id) if a.trace_id else None,
                "overall_score": a.overall_score,
                "overall_grade": a.overall_grade,
                "agent_scores": a.agent_scores or [],
                "orchestration_score": a.orchestration_score or {},
                "improvements": a.improvements or [],
                "complexity_metrics": a.complexity_metrics or {},
                "total_issues": a.total_issues,
                "critical_issues_count": a.critical_issues_count,
                "source": a.source,
                "assessment_time_ms": a.assessment_time_ms,
                "summary": a.summary,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assessments
        ],
        "total": total,
        "page": 1,
        "page_size": limit,
    }


async def _get_cached_dashboard(tenant_id: str, days: int) -> dict | None:
    """Read dashboard from Redis cache."""
    try:
        await rate_limiter.connect()
        if rate_limiter._redis:
            cached = await rate_limiter._redis.get(f"dashboard:{tenant_id}:{days}")
            if cached:
                return json.loads(cached)
    except Exception as e:
        logger.debug("Dashboard cache read failed: %s", e)
    return None


async def _set_cached_dashboard(tenant_id: str, days: int, data: dict) -> None:
    """Write dashboard to Redis cache with TTL."""
    try:
        await rate_limiter.connect()
        if rate_limiter._redis:
            await rate_limiter._redis.setex(
                f"dashboard:{tenant_id}:{days}",
                DASHBOARD_CACHE_TTL,
                json.dumps(data, default=str),
            )
    except Exception as e:
        logger.debug("Dashboard cache write failed: %s", e)


async def invalidate_dashboard_cache(tenant_id: str) -> None:
    """Invalidate dashboard cache for a tenant. Call after trace/detection ingest."""
    try:
        await rate_limiter.connect()
        if rate_limiter._redis:
            keys = []
            async for key in rate_limiter._redis.scan_iter(f"dashboard:{tenant_id}:*"):
                keys.append(key)
            if keys:
                await rate_limiter._redis.delete(*keys)
    except Exception as e:
        logger.debug("Dashboard cache invalidation failed: %s", e)


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    days: int = Query(30, ge=1, le=365),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Return all dashboard data in a single request. Cached in Redis for 5 minutes."""
    # Try Redis cache first
    cached = await _get_cached_dashboard(tenant_id, days)
    if cached:
        return DashboardResponse(**cached)

    # Cache miss — run DB queries
    await set_tenant_context(db, tenant_id)
    tid = UUID(tenant_id)
    start_date = datetime.utcnow() - timedelta(days=days)

    empty_loop = {"total_loops_detected": 0, "loops_by_method": {}, "avg_loop_length": 0, "top_agents_in_loops": [], "time_series": []}
    empty_cost = {"total_cost_cents": 0, "total_tokens": 0, "cost_by_framework": {}, "cost_by_day": [], "top_expensive_traces": []}
    empty_detections = {"items": [], "total": 0, "page": 1, "per_page": 10}
    empty_traces = {"traces": [], "total": 0, "page": 1, "per_page": 10}
    empty_assessments = {"assessments": [], "total": 0, "page": 1, "page_size": 20}

    async def safe(fn, *args, fallback=None):
        try:
            return await fn(*args)
        except Exception as e:
            logger.warning(f"Dashboard query {fn.__name__} failed: {e}")
            return fallback

    loop, cost, detections, traces, assessments = await asyncio.gather(
        safe(_loop_analytics, db, tid, start_date, fallback=empty_loop),
        safe(_cost_analytics, db, tid, start_date, fallback=empty_cost),
        safe(_recent_detections, db, tid, fallback=empty_detections),
        safe(_recent_traces, db, tid, fallback=empty_traces),
        safe(_quality_assessments, db, tid, fallback=empty_assessments),
    )

    result = DashboardResponse(
        loop_analytics=loop,
        cost_analytics=cost,
        detections=detections,
        traces=traces,
        quality_assessments=assessments,
    )

    # Cache the result in Redis (fire-and-forget)
    await _set_cached_dashboard(tenant_id, days, result.model_dump())

    return result


@router.get("/quality-assessments")
async def list_quality_assessments_lightweight(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight quality assessments list — no heavy enterprise imports."""
    await set_tenant_context(db, tenant_id)
    tid = UUID(tenant_id)
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count()).where(WorkflowQualityAssessment.tenant_id == tid)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(WorkflowQualityAssessment).where(WorkflowQualityAssessment.tenant_id == tid)
        .order_by(WorkflowQualityAssessment.created_at.desc())
        .offset(offset).limit(page_size)
    )
    assessments = result.scalars().all()

    return {
        "assessments": [
            {
                "id": str(a.id),
                "workflow_id": a.workflow_id,
                "workflow_name": a.workflow_name,
                "trace_id": str(a.trace_id) if a.trace_id else None,
                "overall_score": a.overall_score,
                "overall_grade": a.overall_grade,
                "agent_scores": a.agent_scores or [],
                "orchestration_score": a.orchestration_score or {},
                "improvements": a.improvements or [],
                "complexity_metrics": a.complexity_metrics or {},
                "total_issues": a.total_issues,
                "critical_issues_count": a.critical_issues_count,
                "source": a.source,
                "assessment_time_ms": a.assessment_time_ms,
                "summary": a.summary,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assessments
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/agent-quality")
async def get_agent_quality(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate agent quality scores across all assessments."""
    await set_tenant_context(db, tenant_id)
    tid = UUID(tenant_id)

    result = await db.execute(
        select(WorkflowQualityAssessment).where(WorkflowQualityAssessment.tenant_id == tid)
        .order_by(WorkflowQualityAssessment.created_at.desc())
    )
    assessments = result.scalars().all()

    # Aggregate per agent_id across all assessments
    agent_map: dict = {}
    for a in assessments:
        for agent in (a.agent_scores or []):
            aid = agent.get("agent_id", "unknown")
            if aid not in agent_map:
                agent_map[aid] = {
                    "agent_id": aid,
                    "agent_name": agent.get("agent_name", aid),
                    "agent_type": agent.get("agent_type", ""),
                    "scores": [],
                    "total_runs": 0,
                    "issues_count": 0,
                }
            agent_map[aid]["scores"].append(agent.get("overall_score", 0))
            agent_map[aid]["total_runs"] += 1
            agent_map[aid]["issues_count"] += agent.get("issues_count", 0)

    agents = []
    for aid, data in agent_map.items():
        scores = data["scores"]
        avg_score = sum(scores) / len(scores) if scores else 0
        if avg_score >= 90: grade = "Healthy"
        elif avg_score >= 70: grade = "Degraded"
        elif avg_score >= 50: grade = "At Risk"
        else: grade = "Critical"
        agents.append({
            "agent_id": data["agent_id"],
            "agent_name": data["agent_name"],
            "agent_type": data["agent_type"],
            "avg_score": round(avg_score, 1),
            "grade": grade,
            "total_runs": data["total_runs"],
            "issues_count": data["issues_count"],
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
        })

    agents.sort(key=lambda a: a["avg_score"])
    return {"agents": agents, "total": len(agents)}


# Agent role inference from name
_AGENT_ROLES = {
    "researcher": "Researches topics and gathers information from available sources",
    "writer": "Generates written content, reports, and documentation",
    "analyst": "Analyzes data and extracts insights from available information",
    "coordinator": "Orchestrates workflow and delegates tasks between agents",
    "validator": "Validates output quality, correctness, and completeness",
    "reviewer": "Reviews and provides feedback on other agents' output",
    "planner": "Plans task decomposition and execution strategy",
    "coder": "Writes and modifies code based on requirements",
    "summarizer": "Summarizes long content into concise outputs",
    "classifier": "Categorizes and labels input data",
    "extractor": "Extracts structured data from unstructured sources",
    "translator": "Translates content between languages or formats",
    "editor": "Edits and refines content for clarity and quality",
    "assistant": "General-purpose assistant that handles varied tasks",
}

_DETECTION_DESCRIPTIONS = {
    "infinite_loop": "Agent repeated the same action in a loop",
    "state_corruption": "Agent's internal state became inconsistent or corrupted",
    "persona_drift": "Agent deviated from its assigned role or personality",
    "coordination_deadlock": "Agent got stuck waiting for another agent",
    "hallucination": "Agent produced information not grounded in source data",
    "context_neglect": "Agent ignored relevant context in its response",
    "task_derailment": "Agent drifted from the assigned task",
    "communication_breakdown": "Agent failed to communicate clearly with other agents",
    "specification_mismatch": "Agent output didn't match the task specification",
    "poor_decomposition": "Task was broken down poorly into subtasks",
    "flawed_workflow": "Workflow execution had structural issues",
    "prompt_injection": "Potential prompt injection attempt detected",
    "information_withholding": "Agent withheld information it should have shared",
    "premature_completion": "Agent stopped too early without completing the task",
}


def _infer_role(agent_id: str) -> str:
    """Infer agent role from its name."""
    name = agent_id.lower().strip()
    for key, desc in _AGENT_ROLES.items():
        if key in name:
            return desc
    return f"Agent responsible for '{agent_id}' tasks in the workflow"


@router.get("/agent-quality/{agent_id}")
async def get_agent_detail(
    agent_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Per-run quality details for a specific agent with role summary and failure breakdown."""
    await set_tenant_context(db, tenant_id)
    tid = UUID(tenant_id)

    # Get assessments
    result = await db.execute(
        select(WorkflowQualityAssessment).where(WorkflowQualityAssessment.tenant_id == tid)
        .order_by(WorkflowQualityAssessment.created_at.desc())
    )
    assessments = result.scalars().all()

    # Get detections for this tenant to cross-reference with agent runs
    det_result = await db.execute(
        select(Detection.trace_id, Detection.detection_type)
        .where(Detection.tenant_id == tid)
    )
    # Map trace_id → list of detection types
    trace_detections: dict = {}
    for trace_id, det_type in det_result.all():
        trace_detections.setdefault(trace_id, []).append(det_type)

    runs = []
    scores = []
    failure_counts: dict = {}
    runs_with_issues = 0

    for a in assessments:
        for agent in (a.agent_scores or []):
            if agent.get("agent_id") == agent_id:
                score = agent.get("overall_score", 0)
                scores.append(score)

                # Check detections for this run's trace
                run_detections = trace_detections.get(a.trace_id, [])
                if run_detections:
                    runs_with_issues += 1
                for dt in run_detections:
                    failure_counts[dt] = failure_counts.get(dt, 0) + 1

                runs.append({
                    "assessment_id": str(a.id),
                    "workflow_name": a.workflow_name,
                    "workflow_id": a.workflow_id,
                    "score": score,
                    "grade": agent.get("grade", ""),
                    "dimensions": agent.get("dimensions", []),
                    "issues_count": agent.get("issues_count", 0),
                    "critical_issues": agent.get("critical_issues", []),
                    "detections": run_detections,
                    "improvements": a.improvements or [],
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                })
                break

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    grade = "Healthy" if avg_score >= 90 else "Degraded" if avg_score >= 70 else "At Risk" if avg_score >= 50 else "Critical"

    # Build failure summary
    failure_by_type = sorted([
        {
            "type": dt,
            "count": count,
            "description": _DETECTION_DESCRIPTIONS.get(dt, f"Detection: {dt}"),
        }
        for dt, count in failure_counts.items()
    ], key=lambda x: x["count"], reverse=True)

    return {
        "agent_id": agent_id,
        "agent_name": agent_id,
        "role_summary": _infer_role(agent_id),
        "avg_score": avg_score,
        "grade": grade,
        "total_runs": len(runs),
        "runs": runs[:50],
        "failure_summary": {
            "total_failures": sum(failure_counts.values()),
            "runs_with_issues": runs_with_issues,
            "by_type": failure_by_type,
        },
        "score_explanation": (
            "Quality score starts at 100 for each run. "
            "Deductions: -10 per failure detection found (max -40), "
            "-15 for very short executions (<2 agent steps). "
            "Grade: Healthy (90+), Degraded (70-89), At Risk (50-69), Critical (<50)."
        ),
    }
