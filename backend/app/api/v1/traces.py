from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Trace, State, Detection
from app.core.auth import get_current_tenant
from app.core.rate_limit import check_rate_limit
from app.ingestion.otel import otel_parser
from app.ingestion.buffer import AsyncBuffer, BufferConfig, BackpressureController
from app.detection.loop import loop_detector, StateSnapshot
from app.detection.hallucination import hallucination_detector
from app.detection.corruption import corruption_detector, StateSnapshot as CorruptionSnapshot
from app.detection.persona import persona_scorer, Agent
from app.detection.coordination import coordination_analyzer, Message
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
    
    if not traces:
        return TraceListResponse(traces=[], total=total, page=page, per_page=per_page)
    
    trace_ids = [t.id for t in traces]
    
    state_counts_result = await db.execute(
        select(State.trace_id, func.count().label('count'))
        .where(State.trace_id.in_(trace_ids))
        .group_by(State.trace_id)
    )
    state_counts = {row[0]: row[1] for row in state_counts_result.all()}
    
    detection_counts_result = await db.execute(
        select(Detection.trace_id, func.count().label('count'))
        .where(Detection.trace_id.in_(trace_ids))
        .group_by(Detection.trace_id)
    )
    detection_counts = {row[0]: row[1] for row in detection_counts_result.all()}
    
    trace_responses = [
        TraceResponse(
            id=trace.id,
            session_id=trace.session_id,
            framework=trace.framework,
            status=trace.status,
            total_tokens=trace.total_tokens,
            total_cost_cents=trace.total_cost_cents,
            created_at=trace.created_at,
            completed_at=trace.completed_at,
            state_count=state_counts.get(trace.id, 0),
            detection_count=detection_counts.get(trace.id, 0),
        )
        for trace in traces
    ]
    
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
    """Run all detection algorithms on a trace and store results."""
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

    detections = []

    # 1. Loop Detection
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
    if loop_result.detected:
        detection = Detection(
            tenant_id=UUID(tenant_id),
            trace_id=trace_id,
            state_id=states[-1].id if states else None,
            detection_type="infinite_loop",
            confidence=int(loop_result.confidence * 100),
            method=loop_result.method,
            details={
                "loop_start_index": loop_result.loop_start_index,
                "loop_length": loop_result.loop_length,
            },
        )
        db.add(detection)
        detections.append({
            "type": "infinite_loop",
            "confidence": loop_result.confidence,
            "method": loop_result.method,
        })

    # 2. Hallucination Detection (on each agent output)
    for s in states:
        output_text = ""
        if isinstance(s.state_delta, dict):
            output = s.state_delta.get("output", [])
            if isinstance(output, list) and output:
                first_item = output[0] if output else {}
                if isinstance(first_item, dict):
                    json_content = first_item.get("json", {})
                    if isinstance(json_content, dict):
                        output_text = json_content.get("output", str(json_content))
                    else:
                        output_text = str(json_content)

        if output_text and len(output_text) > 50:
            halluc_result = hallucination_detector.detect_hallucination(output_text)
            if halluc_result.detected:
                detection = Detection(
                    tenant_id=UUID(tenant_id),
                    trace_id=trace_id,
                    state_id=s.id,
                    detection_type="hallucination",
                    confidence=int(halluc_result.confidence * 100),
                    method=halluc_result.hallucination_type or "general",
                    details={
                        "grounding_score": halluc_result.grounding_score,
                        "evidence": halluc_result.evidence[:3] if halluc_result.evidence else [],
                        "agent_id": s.agent_id,
                    },
                )
                db.add(detection)
                detections.append({
                    "type": "hallucination",
                    "confidence": halluc_result.confidence,
                    "method": halluc_result.hallucination_type,
                    "agent_id": s.agent_id,
                })

    # 3. State Corruption Detection (comparing sequential states)
    from datetime import datetime
    for i in range(1, len(states)):
        prev_state = states[i-1]
        curr_state = states[i]

        prev_snapshot = CorruptionSnapshot(
            state_delta=prev_state.state_delta or {},
            agent_id=prev_state.agent_id or "unknown",
            timestamp=prev_state.created_at or datetime.utcnow(),
        )
        curr_snapshot = CorruptionSnapshot(
            state_delta=curr_state.state_delta or {},
            agent_id=curr_state.agent_id or "unknown",
            timestamp=curr_state.created_at or datetime.utcnow(),
        )

        corruption_result = corruption_detector.detect_corruption_with_confidence(
            prev_snapshot, curr_snapshot
        )
        if corruption_result.detected and corruption_result.confidence > 0.5:
            detection = Detection(
                tenant_id=UUID(tenant_id),
                trace_id=trace_id,
                state_id=curr_state.id,
                detection_type="state_corruption",
                confidence=int(corruption_result.confidence * 100),
                method=corruption_result.max_severity,
                details={
                    "issue_count": corruption_result.issue_count,
                    "issues": [
                        {"type": i.issue_type, "message": i.message, "severity": i.severity}
                        for i in corruption_result.issues[:3]
                    ],
                    "agent_id": curr_state.agent_id,
                },
            )
            db.add(detection)
            detections.append({
                "type": "state_corruption",
                "confidence": corruption_result.confidence,
                "method": corruption_result.max_severity,
                "agent_id": curr_state.agent_id,
            })

    # 4. Persona Drift Detection (for Safety Scanner and similar agents)
    safety_agents = [s for s in states if s.agent_id and "safety" in s.agent_id.lower()]
    for s in safety_agents:
        agent = Agent(
            id=s.agent_id,
            persona_description="Safety Scanner: Analyze content for security risks and harmful content",
            allowed_actions=["analyze", "flag", "report"],
        )
        output_text = ""
        if isinstance(s.state_delta, dict):
            output = s.state_delta.get("output", [])
            if isinstance(output, list) and output:
                first_item = output[0] if output else {}
                if isinstance(first_item, dict):
                    json_content = first_item.get("json", {})
                    if isinstance(json_content, dict):
                        output_text = json_content.get("output", str(json_content))
                    else:
                        output_text = str(json_content)

        if output_text and len(output_text) > 50:
            persona_result = persona_scorer.score_consistency(agent, output_text)
            if not persona_result.consistent or persona_result.drift_detected:
                detection = Detection(
                    tenant_id=UUID(tenant_id),
                    trace_id=trace_id,
                    state_id=s.id,
                    detection_type="persona_drift",
                    confidence=int(persona_result.confidence * 100),
                    method=persona_result.method,
                    details={
                        "score": persona_result.score,
                        "drift_magnitude": persona_result.drift_magnitude,
                        "issues": persona_result.issues[:3] if persona_result.issues else [],
                        "agent_id": s.agent_id,
                    },
                )
                db.add(detection)
                detections.append({
                    "type": "persona_drift",
                    "confidence": persona_result.confidence,
                    "method": persona_result.method,
                    "agent_id": s.agent_id,
                })

    # 5. Coordination Analysis (for multi-agent workflows)
    agent_ids = list(set(s.agent_id for s in states if s.agent_id))
    if len(agent_ids) > 2:
        messages = []
        for i, s in enumerate(states):
            if i > 0 and states[i-1].agent_id != s.agent_id:
                msg = Message(
                    from_agent=states[i-1].agent_id or "unknown",
                    to_agent=s.agent_id or "unknown",
                    content=str(s.state_delta)[:500],
                    timestamp=float(i),
                    acknowledged=True,
                )
                messages.append(msg)

        if messages:
            coord_result = coordination_analyzer.analyze_coordination_with_confidence(
                messages, agent_ids
            )
            if coord_result.detected and coord_result.confidence > 0.5:
                detection = Detection(
                    tenant_id=UUID(tenant_id),
                    trace_id=trace_id,
                    state_id=states[-1].id if states else None,
                    detection_type="coordination_failure",
                    confidence=int(coord_result.confidence * 100),
                    method="multi_agent_analysis",
                    details={
                        "issue_count": coord_result.issue_count,
                        "issues": [
                            {"type": i.issue_type, "message": i.message, "severity": i.severity}
                            for i in coord_result.issues[:3]
                        ],
                        "metrics": coord_result.metrics,
                    },
                )
                db.add(detection)
                detections.append({
                    "type": "coordination_failure",
                    "confidence": coord_result.confidence,
                    "issue_count": coord_result.issue_count,
                })

    await db.commit()

    # Add confidence_tier to each detection dict
    for det in detections:
        conf = det.get("confidence", 0)
        if conf >= 0.80:
            det["confidence_tier"] = "HIGH"
        elif conf >= 0.60:
            det["confidence_tier"] = "LIKELY"
        elif conf >= 0.40:
            det["confidence_tier"] = "POSSIBLE"
        else:
            det["confidence_tier"] = "LOW"

    return {
        "detections": detections,
        "analyzed_states": len(states),
        "detection_types_run": ["loop", "hallucination", "corruption", "persona", "coordination"],
    }
