"""Conversation trace API endpoints.

Provides endpoints for ingesting and querying multi-turn conversation traces,
supporting MAST-Data and other conversation-based agent frameworks.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from uuid import UUID
import json

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Trace, ConversationTurn, TurnState, State, Detection
from app.core.auth import get_verified_tenant
from app.ingestion.importers import MASTImporter, ConversationImporter
from app.ingestion.conversation_trace import ConversationTrace as ConversationTraceData
from app.detection.turn_aware import (
    TurnSnapshot,
    TurnAwareContextNeglectDetector,
    TurnAwareDerailmentDetector,
    TurnAwareLoopDetector,
    analyze_conversation_turns,
)
from app.api.v1.schemas import (
    ConversationIngestRequest,
    ConversationResponse,
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationTurnResponse,
    ConversationAnalyzeResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/ingest", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def ingest_conversation(
    request: ConversationIngestRequest,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a conversation trace.

    Supports multiple formats:
    - MAST-Data trajectory logs
    - OpenAI messages format
    - Claude conversation format
    - Generic turn-based formats

    The format is auto-detected unless explicitly specified.
    """
    await set_tenant_context(db, tenant_id)

    # Select importer based on format
    if request.format == "mast" or request.format == "mast-data":
        importer = MASTImporter()
    else:
        importer = ConversationImporter()

    # Parse conversation
    try:
        conv_trace = importer.import_conversation(request.content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse conversation: {str(e)}"
        )

    if not conv_trace.turns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No conversation turns found in content"
        )

    # Create Trace record
    trace = Trace(
        tenant_id=UUID(tenant_id),
        session_id=conv_trace.conversation_id,
        framework=conv_trace.framework,
        is_conversation=True,
        total_tokens=conv_trace.total_tokens,
        status="completed",
    )
    db.add(trace)
    await db.flush()

    # Create ConversationTurn records
    for turn in conv_trace.turns:
        db_turn = ConversationTurn(
            trace_id=trace.id,
            tenant_id=UUID(tenant_id),
            conversation_id=conv_trace.conversation_id,
            turn_number=turn.turn_number,
            participant_type=turn.role,
            participant_id=turn.participant_id,
            content=turn.content,
            content_hash=turn.content_hash,
            accumulated_context=conv_trace.get_context_up_to_turn(turn.turn_number),
            accumulated_tokens=turn.accumulated_tokens,
            turn_metadata=turn.extra,
        )
        db.add(db_turn)

    await db.commit()
    await db.refresh(trace)

    # Get failure modes if MAST format
    failure_modes = []
    if hasattr(importer, 'get_failure_modes'):
        failure_modes = importer.get_failure_modes(conv_trace)

    return ConversationResponse(
        trace_id=trace.id,
        conversation_id=conv_trace.conversation_id,
        framework=conv_trace.framework,
        total_turns=conv_trace.total_turns,
        total_tokens=conv_trace.total_tokens,
        participants=conv_trace.participants,
        is_conversation=True,
        failure_modes=failure_modes,
    )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    framework: str = Query(None, description="Filter by framework"),
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all conversation traces."""
    await set_tenant_context(db, tenant_id)

    # Query only conversation traces
    query = select(Trace).where(
        Trace.tenant_id == UUID(tenant_id),
        Trace.is_conversation == True,
    )

    if framework:
        query = query.where(Trace.framework == framework)

    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()

    # Paginate
    query = query.order_by(Trace.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    traces = result.scalars().all()

    # Get turn counts and participants for each trace
    conversations = []
    for trace in traces:
        # Get turns
        turns_result = await db.execute(
            select(ConversationTurn).where(
                ConversationTurn.trace_id == trace.id
            ).order_by(ConversationTurn.turn_number).limit(200)  # M5: cap at 200 turns
        )
        turns = turns_result.scalars().all()

        participants = list(set(t.participant_id for t in turns))

        conversations.append(ConversationResponse(
            trace_id=trace.id,
            conversation_id=trace.session_id,
            framework=trace.framework,
            total_turns=len(turns),
            total_tokens=trace.total_tokens,
            participants=participants,
            is_conversation=True,
            failure_modes=[],
        ))

    return ConversationListResponse(
        conversations=conversations,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{trace_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    trace_id: UUID,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with all its turns."""
    await set_tenant_context(db, tenant_id)

    # Get trace
    result = await db.execute(
        select(Trace).where(
            Trace.id == trace_id,
            Trace.tenant_id == UUID(tenant_id),
        )
    )
    trace = result.scalar_one_or_none()

    if not trace:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get turns
    turns_result = await db.execute(
        select(ConversationTurn).where(
            ConversationTurn.trace_id == trace_id,
            ConversationTurn.tenant_id == UUID(tenant_id),
        ).order_by(ConversationTurn.turn_number)
    )
    turns = turns_result.scalars().all()

    participants = list(set(t.participant_id for t in turns))

    # Get MAST annotations if stored
    mast_annotations = None
    if turns and turns[0].turn_metadata:
        mast_annotations = turns[0].turn_metadata.get("mast_annotations")

    return ConversationDetailResponse(
        trace_id=trace.id,
        conversation_id=trace.session_id,
        framework=trace.framework,
        total_turns=len(turns),
        total_tokens=trace.total_tokens,
        participants=participants,
        turns=[
            ConversationTurnResponse(
                id=t.id,
                turn_number=t.turn_number,
                participant_type=t.participant_type,
                participant_id=t.participant_id,
                content=t.content,
                content_hash=t.content_hash,
                accumulated_tokens=t.accumulated_tokens,
                created_at=t.created_at,
            )
            for t in turns
        ],
        failure_modes=[],
        mast_annotations=mast_annotations,
        created_at=trace.created_at,
    )


@router.get("/{trace_id}/turns", response_model=List[ConversationTurnResponse])
async def get_conversation_turns(
    trace_id: UUID,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get all turns in a conversation."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(ConversationTurn).where(
            ConversationTurn.trace_id == trace_id,
            ConversationTurn.tenant_id == UUID(tenant_id),
        ).order_by(ConversationTurn.turn_number)
    )
    turns = result.scalars().all()

    if not turns:
        raise HTTPException(status_code=404, detail="Conversation not found or has no turns")

    return [
        ConversationTurnResponse(
            id=t.id,
            turn_number=t.turn_number,
            participant_type=t.participant_type,
            participant_id=t.participant_id,
            content=t.content,
            content_hash=t.content_hash,
            accumulated_tokens=t.accumulated_tokens,
            created_at=t.created_at,
        )
        for t in turns
    ]


@router.get("/{trace_id}/turns/{turn_number}", response_model=ConversationTurnResponse)
async def get_conversation_turn(
    trace_id: UUID,
    turn_number: int,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific turn in a conversation."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(ConversationTurn).where(
            ConversationTurn.trace_id == trace_id,
            ConversationTurn.tenant_id == UUID(tenant_id),
            ConversationTurn.turn_number == turn_number,
        )
    )
    turn = result.scalar_one_or_none()

    if not turn:
        raise HTTPException(status_code=404, detail=f"Turn {turn_number} not found")

    return ConversationTurnResponse(
        id=turn.id,
        turn_number=turn.turn_number,
        participant_type=turn.participant_type,
        participant_id=turn.participant_id,
        content=turn.content,
        content_hash=turn.content_hash,
        accumulated_tokens=turn.accumulated_tokens,
        created_at=turn.created_at,
    )


@router.get("/{trace_id}/context/{turn_number}")
async def get_accumulated_context(
    trace_id: UUID,
    turn_number: int,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get accumulated context up to a specific turn.

    Useful for understanding what context was available to the agent
    at a specific point in the conversation.
    """
    await set_tenant_context(db, tenant_id)

    # Get the specific turn
    result = await db.execute(
        select(ConversationTurn).where(
            ConversationTurn.trace_id == trace_id,
            ConversationTurn.tenant_id == UUID(tenant_id),
            ConversationTurn.turn_number == turn_number,
        )
    )
    turn = result.scalar_one_or_none()

    if not turn:
        raise HTTPException(status_code=404, detail=f"Turn {turn_number} not found")

    return {
        "turn_number": turn_number,
        "accumulated_context": turn.accumulated_context,
        "accumulated_tokens": turn.accumulated_tokens,
    }


@router.post("/{trace_id}/analyze", response_model=ConversationAnalyzeResponse)
async def analyze_conversation(
    trace_id: UUID,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Analyze a conversation for failures.

    Runs turn-aware detection algorithms to identify issues like:
    - Context neglect between turns (F7)
    - Task derailment over the conversation (F6)
    - Infinite loops and repetitive behavior (F5)
    """
    await set_tenant_context(db, tenant_id)

    # Get trace
    trace_result = await db.execute(
        select(Trace).where(
            Trace.id == trace_id,
            Trace.tenant_id == UUID(tenant_id),
        )
    )
    trace = trace_result.scalar_one_or_none()

    if not trace:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get turns
    turns_result = await db.execute(
        select(ConversationTurn).where(
            ConversationTurn.trace_id == trace_id,
        ).order_by(ConversationTurn.turn_number)
    )
    db_turns = turns_result.scalars().all()

    if not db_turns:
        raise HTTPException(status_code=404, detail="Conversation has no turns")

    # Convert database turns to TurnSnapshots for detection
    turn_snapshots = [
        TurnSnapshot(
            turn_number=t.turn_number,
            participant_type=t.participant_type,
            participant_id=t.participant_id,
            content=t.content,
            content_hash=t.content_hash,
            accumulated_context=t.accumulated_context,
            accumulated_tokens=t.accumulated_tokens,
            turn_metadata=t.turn_metadata or {},
        )
        for t in db_turns
    ]

    # Run turn-aware detectors
    detection_results = analyze_conversation_turns(
        turns=turn_snapshots,
        conversation_metadata={
            "trace_id": str(trace_id),
            "framework": trace.framework,
        },
    )

    # Convert detection results to API response format
    detections = []
    turn_issues = []
    failure_modes_detected = []

    for result in detection_results:
        # Add to detections list
        detections.append({
            "type": result.detector_name,
            "confidence": result.confidence,
            "description": result.explanation,
            "severity": result.severity.value,
            "evidence": result.evidence,
        })

        # Track failure modes
        if result.failure_mode and result.failure_mode not in failure_modes_detected:
            failure_modes_detected.append(result.failure_mode)

        # Add turn-specific issues
        for turn_num in result.affected_turns:
            turn_issues.append({
                "turn_number": turn_num,
                "issue": result.failure_mode or "unknown",
                "description": f"{result.detector_name}: {result.explanation}",
                "severity": result.severity.value,
            })

        # Store detection in database
        detection = Detection(
            tenant_id=UUID(tenant_id),
            trace_id=trace_id,
            detection_type=result.failure_mode or result.detector_name,
            confidence=int(result.confidence * 100),
            method="turn_aware_analysis",
            details={
                "detector": result.detector_name,
                "detector_version": result.detector_version,
                "explanation": result.explanation,
                "affected_turns": result.affected_turns,
                "evidence": result.evidence,
                "suggested_fix": result.suggested_fix,
            },
        )
        db.add(detection)

    await db.commit()

    return ConversationAnalyzeResponse(
        trace_id=trace_id,
        analyzed_turns=len(db_turns),
        detections=detections,
        failure_modes_detected=failure_modes_detected,
        turn_issues=turn_issues,
    )


@router.delete("/{trace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    trace_id: UUID,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its turns."""
    await set_tenant_context(db, tenant_id)

    # Get trace
    result = await db.execute(
        select(Trace).where(
            Trace.id == trace_id,
            Trace.tenant_id == UUID(tenant_id),
        )
    )
    trace = result.scalar_one_or_none()

    if not trace:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete (cascade will handle turns)
    await db.delete(trace)
    await db.commit()
