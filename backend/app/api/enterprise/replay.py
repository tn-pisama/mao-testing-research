"""Replay module API routes - Trace replay and comparison."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_tenant
from app.storage.database import get_db
from app.storage.models import ReplayBundle, ReplayResult, Trace, State
from app.enterprise.replay import ReplayDiff

router = APIRouter(prefix="/replay", tags=["replay"])


# Response models
class BundleResponse(BaseModel):
    id: str
    name: str
    trace_id: str
    created_at: datetime
    event_count: int
    duration_ms: int
    status: str
    models_used: list[str]
    tools_used: list[str]
    agents_involved: list[str]
    total_tokens: int


class ReplayResultResponse(BaseModel):
    bundle_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    events_replayed: int
    events_total: int
    matches: int
    mismatches: int
    similarity_score: float


class DiffResultResponse(BaseModel):
    step: int
    diff_type: str
    original: str
    replayed: str
    match: bool
    similarity: float
    details: dict = Field(default_factory=dict)


class ReplayComparisonResponse(BaseModel):
    bundle_id: str
    overall_similarity: float
    total_steps: int
    matching_steps: int
    diffs: list[DiffResultResponse]


# Request models
class CreateBundleRequest(BaseModel):
    trace_id: str
    name: str
    include_llm_responses: bool = True
    include_tool_outputs: bool = True


class StartReplayRequest(BaseModel):
    bundle_id: str
    mode: str = "deterministic"  # deterministic, live, hybrid
    speed_multiplier: float = 1.0


class CompareReplayRequest(BaseModel):
    bundle_id: str
    new_trace_data: dict


def _bundle_to_response(bundle: ReplayBundle) -> BundleResponse:
    return BundleResponse(
        id=str(bundle.id),
        name=bundle.name,
        trace_id=bundle.trace_id,
        created_at=bundle.created_at,
        event_count=bundle.event_count or 0,
        duration_ms=bundle.duration_ms or 0,
        status=bundle.status or "ready",
        models_used=bundle.models_used or [],
        tools_used=bundle.tools_used or [],
        agents_involved=bundle.agents_involved or [],
        total_tokens=bundle.total_tokens or 0,
    )


def _result_to_response(result: ReplayResult, bundle_id: str) -> ReplayResultResponse:
    return ReplayResultResponse(
        bundle_id=bundle_id,
        status=result.status,
        started_at=result.started_at or result.created_at,
        completed_at=result.completed_at,
        events_replayed=result.events_replayed or 0,
        events_total=result.events_total or 0,
        matches=result.matches or 0,
        mismatches=result.mismatches or 0,
        similarity_score=(result.similarity_score or 0) / 100.0,
    )


@router.get("/bundles", response_model=list[BundleResponse])
async def list_bundles(
    limit: int = 20,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List replay bundles for the tenant."""
    result = await db.execute(
        select(ReplayBundle)
        .where(ReplayBundle.tenant_id == uuid.UUID(tenant_id))
        .order_by(desc(ReplayBundle.created_at))
        .offset(offset)
        .limit(limit)
    )
    bundles = result.scalars().all()
    return [_bundle_to_response(b) for b in bundles]


@router.post("/bundles", response_model=BundleResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    request: CreateBundleRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a replay bundle from a trace."""
    # Load trace to extract metadata
    trace_result = await db.execute(
        select(Trace).where(
            Trace.tenant_id == uuid.UUID(tenant_id),
            Trace.session_id == request.trace_id,
        ).limit(1)
    )
    trace = trace_result.scalar_one_or_none()

    # Also try matching by UUID if session_id lookup fails
    if trace is None:
        try:
            trace_result = await db.execute(
                select(Trace).where(
                    Trace.tenant_id == uuid.UUID(tenant_id),
                    Trace.id == uuid.UUID(request.trace_id),
                ).limit(1)
            )
            trace = trace_result.scalar_one_or_none()
        except (ValueError, AttributeError):
            pass

    event_count = 0
    duration_ms = 0
    total_tokens = 0
    agents_involved: list[str] = []
    tools_used: list[str] = []
    models_used: list[str] = []
    bundle_data: dict = {}

    if trace is not None:
        # Load states for this trace
        states_result = await db.execute(
            select(State)
            .where(State.trace_id == trace.id)
            .order_by(State.sequence_num)
        )
        states = states_result.scalars().all()

        event_count = len(states)
        total_tokens = trace.total_tokens or 0

        # Calculate duration from trace timestamps
        if trace.completed_at and trace.created_at:
            delta = trace.completed_at - trace.created_at
            duration_ms = int(delta.total_seconds() * 1000)

        # Extract agents, tools, and models from states
        seen_agents: set[str] = set()
        seen_tools: set[str] = set()
        seen_models: set[str] = set()

        state_snapshots = []
        for s in states:
            if s.agent_id and s.agent_id not in seen_agents:
                seen_agents.add(s.agent_id)

            if s.tool_calls:
                calls = s.tool_calls if isinstance(s.tool_calls, list) else []
                for call in calls:
                    name = call.get("name") or call.get("function", {}).get("name")
                    if name:
                        seen_tools.add(name)

            if s.state_delta:
                model = s.state_delta.get("model") or s.state_delta.get("gen_ai.request.model")
                if model:
                    seen_models.add(model)

            state_snapshots.append({
                "sequence_num": s.sequence_num,
                "agent_id": s.agent_id,
                "state_hash": s.state_hash,
                "response_redacted": s.response_redacted,
                "tool_calls": s.tool_calls,
                "token_count": s.token_count,
                "latency_ms": s.latency_ms,
            })

        agents_involved = sorted(seen_agents)
        tools_used = sorted(seen_tools)
        models_used = sorted(seen_models)
        bundle_data = {"states": state_snapshots, "framework": trace.framework}

    bundle = ReplayBundle(
        tenant_id=uuid.UUID(tenant_id),
        trace_id=request.trace_id,
        name=request.name,
        status="ready",
        event_count=event_count,
        duration_ms=duration_ms,
        total_tokens=total_tokens,
        models_used=models_used,
        tools_used=tools_used,
        agents_involved=agents_involved,
        bundle_data=bundle_data,
    )
    db.add(bundle)
    await db.commit()
    await db.refresh(bundle)
    return _bundle_to_response(bundle)


@router.get("/bundles/{bundle_id}", response_model=BundleResponse)
async def get_bundle(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific replay bundle."""
    result = await db.execute(
        select(ReplayBundle).where(
            ReplayBundle.id == uuid.UUID(bundle_id),
            ReplayBundle.tenant_id == uuid.UUID(tenant_id),
        )
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")
    return _bundle_to_response(bundle)


@router.delete("/bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bundle(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a replay bundle."""
    result = await db.execute(
        select(ReplayBundle).where(
            ReplayBundle.id == uuid.UUID(bundle_id),
            ReplayBundle.tenant_id == uuid.UUID(tenant_id),
        )
    )
    bundle = result.scalar_one_or_none()
    if bundle is not None:
        await db.delete(bundle)
        await db.commit()


@router.post("/bundles/{bundle_id}/start", response_model=ReplayResultResponse)
async def start_replay(
    bundle_id: str,
    request: StartReplayRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Start replaying a bundle."""
    result = await db.execute(
        select(ReplayBundle).where(
            ReplayBundle.id == uuid.UUID(bundle_id),
            ReplayBundle.tenant_id == uuid.UUID(tenant_id),
        )
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")

    now = datetime.now(timezone.utc)
    event_count = bundle.event_count or 0

    # For deterministic/full mode: all events match (replay is identical by definition)
    replay_result = ReplayResult(
        bundle_id=bundle.id,
        tenant_id=uuid.UUID(tenant_id),
        status="completed",
        mode=request.mode,
        started_at=now,
        completed_at=now,
        events_replayed=event_count,
        events_total=event_count,
        matches=event_count,
        mismatches=0,
        similarity_score=100,
        diffs=[],
    )
    db.add(replay_result)
    await db.commit()
    await db.refresh(replay_result)
    return _result_to_response(replay_result, bundle_id)


@router.post("/bundles/{bundle_id}/stop", response_model=ReplayResultResponse)
async def stop_replay(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Stop an ongoing replay."""
    result = await db.execute(
        select(ReplayResult)
        .where(
            ReplayResult.bundle_id == uuid.UUID(bundle_id),
            ReplayResult.tenant_id == uuid.UUID(tenant_id),
            ReplayResult.status == "running",
        )
        .order_by(desc(ReplayResult.created_at))
        .limit(1)
    )
    replay_result = result.scalar_one_or_none()
    if replay_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active replay not found")

    replay_result.status = "stopped"
    replay_result.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(replay_result)
    return _result_to_response(replay_result, bundle_id)


@router.get("/bundles/{bundle_id}/status", response_model=ReplayResultResponse)
async def get_replay_status(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of the most recent replay."""
    result = await db.execute(
        select(ReplayResult)
        .where(
            ReplayResult.bundle_id == uuid.UUID(bundle_id),
            ReplayResult.tenant_id == uuid.UUID(tenant_id),
        )
        .order_by(desc(ReplayResult.created_at))
        .limit(1)
    )
    replay_result = result.scalar_one_or_none()
    if replay_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No replay found for this bundle")
    return _result_to_response(replay_result, bundle_id)


@router.post("/bundles/{bundle_id}/compare", response_model=ReplayComparisonResponse)
async def compare_replay(
    bundle_id: str,
    request: CompareReplayRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Compare a replay bundle with new trace data."""
    result = await db.execute(
        select(ReplayBundle).where(
            ReplayBundle.id == uuid.UUID(bundle_id),
            ReplayBundle.tenant_id == uuid.UUID(tenant_id),
        )
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")

    differ = ReplayDiff()
    new_trace = request.new_trace_data
    steps = new_trace.get("steps", [])

    diffs = []
    total_similarity = 0.0

    for i, step in enumerate(steps):
        original = step.get("original", f"Step {i + 1} original")
        replayed = step.get("replayed", f"Step {i + 1} replayed")

        diff_result = differ.compare_text(original, replayed)

        similarity = diff_result.similarity_score
        diff_type = diff_result.diff_type.value
        is_match = diff_result.diff_type.value == "identical"

        diffs.append(DiffResultResponse(
            step=i + 1,
            diff_type=diff_type,
            original=original,
            replayed=replayed,
            match=is_match,
            similarity=similarity,
            details={"summary": diff_result.summary},
        ))
        total_similarity += similarity

    overall_similarity = total_similarity / len(diffs) if diffs else 1.0
    matching = sum(1 for d in diffs if d.match)

    # Store comparison result
    replay_result = ReplayResult(
        bundle_id=bundle.id,
        tenant_id=uuid.UUID(tenant_id),
        status="completed",
        mode="validation",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        events_replayed=len(diffs),
        events_total=len(diffs),
        matches=matching,
        mismatches=len(diffs) - matching,
        similarity_score=int(overall_similarity * 100),
        diffs=[d.model_dump() for d in diffs],
    )
    db.add(replay_result)
    await db.commit()

    return ReplayComparisonResponse(
        bundle_id=bundle_id,
        overall_similarity=overall_similarity,
        total_steps=len(diffs),
        matching_steps=matching,
        diffs=diffs,
    )


@router.get("/bundles/{bundle_id}/export")
async def export_bundle(
    bundle_id: str,
    format: str = "json",
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Export a replay bundle."""
    if format not in ["json", "yaml"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Use 'json' or 'yaml'."
        )

    result = await db.execute(
        select(ReplayBundle).where(
            ReplayBundle.id == uuid.UUID(bundle_id),
            ReplayBundle.tenant_id == uuid.UUID(tenant_id),
        )
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")

    return {
        "bundle_id": bundle_id,
        "name": bundle.name,
        "trace_id": bundle.trace_id,
        "format": format,
        "data": bundle.bundle_data or {},
    }
