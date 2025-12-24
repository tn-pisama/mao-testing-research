from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from uuid import UUID

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Trace, State, Detection
from app.core.auth import get_current_tenant
from app.core.rate_limit import check_rate_limit
from app.ingestion.otel import otel_parser
from app.ingestion.buffer import AsyncBuffer, BufferConfig, BackpressureController
from app.detection.loop import loop_detector, StateSnapshot
from app.core.security import sanitize_text
from app.api.v1.schemas import (
    TraceIngestRequest,
    TraceResponse,
    TraceListResponse,
    StateResponse,
)

router = APIRouter(prefix="/traces", tags=["traces"])

backpressure = BackpressureController()


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_traces(
    request: TraceIngestRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    if not backpressure.should_accept():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System under load, please retry",
        )
    
    await set_tenant_context(db, tenant_id)
    
    spans = []
    for resource_span in request.resourceSpans:
        for scope_span in resource_span.get("scopeSpans", []):
            spans.extend(scope_span.get("spans", []))
    
    parsed_states = otel_parser.parse_spans(spans)
    
    backpressure.record_pending(len(parsed_states))
    
    traces_created = set()
    for parsed in parsed_states:
        if parsed.trace_id not in traces_created:
            existing = await db.execute(
                select(Trace).where(
                    Trace.session_id == parsed.trace_id,
                    Trace.tenant_id == UUID(tenant_id),
                )
            )
            if not existing.scalar_one_or_none():
                trace = Trace(
                    tenant_id=UUID(tenant_id),
                    session_id=parsed.trace_id,
                )
                db.add(trace)
                await db.flush()
            traces_created.add(parsed.trace_id)
        
        trace_result = await db.execute(
            select(Trace).where(
                Trace.session_id == parsed.trace_id,
                Trace.tenant_id == UUID(tenant_id),
            )
        )
        trace = trace_result.scalar_one()
        
        response_redacted = sanitize_text(parsed.response) if parsed.response else None
        
        state = State(
            trace_id=trace.id,
            tenant_id=UUID(tenant_id),
            sequence_num=parsed.sequence_num,
            agent_id=parsed.agent_id,
            state_delta=parsed.state_delta,
            state_hash=parsed.state_hash,
            prompt_hash=parsed.state_hash if parsed.prompt else None,
            response_redacted=response_redacted,
            tool_calls=parsed.tool_calls,
            token_count=parsed.token_count,
            latency_ms=parsed.latency_ms,
        )
        db.add(state)
        
        trace.total_tokens += parsed.token_count
    
    await db.commit()
    backpressure.record_processed(len(parsed_states))
    
    return {"accepted": len(parsed_states), "traces": len(traces_created)}


@router.get("", response_model=TraceListResponse)
async def list_traces(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str = Query(None),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    query = select(Trace).where(Trace.tenant_id == UUID(tenant_id))
    
    if status_filter:
        query = query.where(Trace.status == status_filter)
    
    count_result = await db.execute(
        select(func.count()).select_from(
            query.subquery()
        )
    )
    total = count_result.scalar()
    
    query = query.order_by(Trace.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    traces = result.scalars().all()
    
    trace_responses = []
    for trace in traces:
        state_count = await db.execute(
            select(func.count()).where(State.trace_id == trace.id)
        )
        detection_count = await db.execute(
            select(func.count()).where(Detection.trace_id == trace.id)
        )
        
        trace_responses.append(TraceResponse(
            id=trace.id,
            session_id=trace.session_id,
            framework=trace.framework,
            status=trace.status,
            total_tokens=trace.total_tokens,
            total_cost_cents=trace.total_cost_cents,
            created_at=trace.created_at,
            completed_at=trace.completed_at,
            state_count=state_count.scalar(),
            detection_count=detection_count.scalar(),
        ))
    
    return TraceListResponse(
        traces=trace_responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(Trace).where(
            Trace.id == trace_id,
            Trace.tenant_id == UUID(tenant_id),
        )
    )
    trace = result.scalar_one_or_none()
    
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    state_count = await db.execute(
        select(func.count()).where(State.trace_id == trace.id)
    )
    detection_count = await db.execute(
        select(func.count()).where(Detection.trace_id == trace.id)
    )
    
    return TraceResponse(
        id=trace.id,
        session_id=trace.session_id,
        framework=trace.framework,
        status=trace.status,
        total_tokens=trace.total_tokens,
        total_cost_cents=trace.total_cost_cents,
        created_at=trace.created_at,
        completed_at=trace.completed_at,
        state_count=state_count.scalar(),
        detection_count=detection_count.scalar(),
    )


@router.get("/{trace_id}/states", response_model=List[StateResponse])
async def get_trace_states(
    trace_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(State).where(
            State.trace_id == trace_id,
            State.tenant_id == UUID(tenant_id),
        ).order_by(State.sequence_num)
    )
    states = result.scalars().all()
    
    return [
        StateResponse(
            id=s.id,
            sequence_num=s.sequence_num,
            agent_id=s.agent_id,
            state_delta=s.state_delta,
            state_hash=s.state_hash,
            token_count=s.token_count,
            latency_ms=s.latency_ms,
            created_at=s.created_at,
        )
        for s in states
    ]


@router.post("/{trace_id}/analyze")
async def analyze_trace(
    trace_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(State).where(
            State.trace_id == trace_id,
            State.tenant_id == UUID(tenant_id),
        ).order_by(State.sequence_num)
    )
    states = result.scalars().all()
    
    if not states:
        raise HTTPException(status_code=404, detail="No states found for trace")
    
    state_snapshots = [
        StateSnapshot(
            agent_id=s.agent_id,
            state_delta=s.state_delta,
            content=str(s.state_delta),
            sequence_num=s.sequence_num,
        )
        for s in states
    ]
    
    loop_result = loop_detector.detect_loop(state_snapshots)
    
    detections = []
    if loop_result.detected:
        detection = Detection(
            tenant_id=UUID(tenant_id),
            trace_id=trace_id,
            state_id=states[-1].id if states else None,
            detection_type="loop",
            confidence=int(loop_result.confidence * 100),
            method=loop_result.method,
            details={
                "loop_start_index": loop_result.loop_start_index,
                "loop_length": loop_result.loop_length,
            },
        )
        db.add(detection)
        detections.append({
            "type": "loop",
            "confidence": loop_result.confidence,
            "method": loop_result.method,
        })
    
    await db.commit()
    
    return {"detections": detections, "analyzed_states": len(states)}
