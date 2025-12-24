from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timedelta

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, Trace, State
from app.core.auth import get_current_tenant
from app.api.v1.schemas import AnalyticsLoopResponse, AnalyticsCostResponse

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
            Detection.detection_type == "loop",
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
