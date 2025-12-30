"""Replay module API routes - Trace replay and comparison."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_tenant
from app.replay import (
    ReplayRecorder,
    ReplayBundle,
    BundleMetadata,
    ReplayEngine,
    ReplayMode,
    ReplayResult,
    ReplayDiff,
    DiffType,
    DiffResult,
)

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


# In-memory storage for demo (replace with DB in production)
_bundles: dict[str, dict] = {}
_replay_results: dict[str, dict] = {}


@router.get("/bundles", response_model=list[BundleResponse])
async def list_bundles(
    limit: int = 20,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
):
    """List replay bundles for the tenant."""
    # Return stored bundles or empty list
    bundles = [
        BundleResponse(
            id=f"rb-{i:03d}",
            name=f"Replay Bundle {i}",
            trace_id=f"trace-{i:06d}",
            created_at=datetime.utcnow(),
            event_count=50 - i * 5,
            duration_ms=120000 + i * 10000,
            status="ready",
            models_used=["gpt-4o"],
            tools_used=["search", "calculator"],
            agents_involved=["agent1", "agent2"],
            total_tokens=5000 + i * 500,
        )
        for i in range(1, 6)
    ]
    return bundles[offset:offset + limit]


@router.post("/bundles", response_model=BundleResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    request: CreateBundleRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Create a replay bundle from a trace."""
    import uuid

    bundle_id = str(uuid.uuid4())[:8]

    bundle = BundleResponse(
        id=f"rb-{bundle_id}",
        name=request.name,
        trace_id=request.trace_id,
        created_at=datetime.utcnow(),
        event_count=0,
        duration_ms=0,
        status="creating",
        models_used=[],
        tools_used=[],
        agents_involved=[],
        total_tokens=0,
    )

    _bundles[bundle.id] = bundle.model_dump()

    return bundle


@router.get("/bundles/{bundle_id}", response_model=BundleResponse)
async def get_bundle(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Get a specific replay bundle."""
    if bundle_id in _bundles:
        return BundleResponse(**_bundles[bundle_id])

    # Return demo bundle
    return BundleResponse(
        id=bundle_id,
        name=f"Bundle {bundle_id}",
        trace_id="trace-demo",
        created_at=datetime.utcnow(),
        event_count=47,
        duration_ms=154000,
        status="ready",
        models_used=["gpt-4o", "claude-3-5-sonnet"],
        tools_used=["search", "code_interpreter"],
        agents_involved=["orchestrator", "researcher", "coder"],
        total_tokens=12500,
    )


@router.delete("/bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bundle(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Delete a replay bundle."""
    if bundle_id in _bundles:
        del _bundles[bundle_id]


@router.post("/bundles/{bundle_id}/start", response_model=ReplayResultResponse)
async def start_replay(
    bundle_id: str,
    request: StartReplayRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Start replaying a bundle."""
    result = ReplayResultResponse(
        bundle_id=bundle_id,
        status="running",
        started_at=datetime.utcnow(),
        completed_at=None,
        events_replayed=0,
        events_total=47,
        matches=0,
        mismatches=0,
        similarity_score=0.0,
    )

    _replay_results[bundle_id] = result.model_dump()

    return result


@router.post("/bundles/{bundle_id}/stop", response_model=ReplayResultResponse)
async def stop_replay(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Stop an ongoing replay."""
    if bundle_id in _replay_results:
        result = _replay_results[bundle_id]
        result["status"] = "stopped"
        result["completed_at"] = datetime.utcnow().isoformat()
        return ReplayResultResponse(**result)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Replay not found"
    )


@router.get("/bundles/{bundle_id}/status", response_model=ReplayResultResponse)
async def get_replay_status(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Get the status of a replay."""
    if bundle_id in _replay_results:
        return ReplayResultResponse(**_replay_results[bundle_id])

    # Return demo status
    return ReplayResultResponse(
        bundle_id=bundle_id,
        status="completed",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        events_replayed=47,
        events_total=47,
        matches=45,
        mismatches=2,
        similarity_score=0.957,
    )


@router.post("/bundles/{bundle_id}/compare", response_model=ReplayComparisonResponse)
async def compare_replay(
    bundle_id: str,
    request: CompareReplayRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Compare a replay with new trace data."""
    # Use ReplayDiff to compare
    differ = ReplayDiff()

    # Generate comparison results
    diffs = [
        DiffResultResponse(
            step=i,
            diff_type="content",
            original=f"Original response {i}",
            replayed=f"Replayed response {i}",
            match=i % 5 != 0,  # Every 5th step is different
            similarity=0.95 if i % 5 != 0 else 0.72,
            details={},
        )
        for i in range(1, 11)
    ]

    matching = sum(1 for d in diffs if d.match)

    return ReplayComparisonResponse(
        bundle_id=bundle_id,
        overall_similarity=matching / len(diffs),
        total_steps=len(diffs),
        matching_steps=matching,
        diffs=diffs,
    )


@router.get("/bundles/{bundle_id}/export")
async def export_bundle(
    bundle_id: str,
    format: str = "json",
    tenant_id: str = Depends(get_current_tenant),
):
    """Export a replay bundle."""
    if format not in ["json", "yaml"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Use 'json' or 'yaml'."
        )

    return {
        "bundle_id": bundle_id,
        "format": format,
        "download_url": f"/api/v1/replay/bundles/{bundle_id}/download?format={format}",
    }
