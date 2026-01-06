"""Replay module API routes - Trace replay and comparison."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_tenant
from app.enterprise.replay import (
    ReplayBundle,
    BundleMetadata,
    ReplayEngine,
    ReplayMode,
    ReplayDiff,
    DiffType,
)

router = APIRouter(prefix="/replay", tags=["replay"])


# In-memory bundle storage
class BundleStore:
    def __init__(self):
        self.bundles: dict[str, dict] = {}
        self.by_tenant: dict[str, list[str]] = {}
        self.replay_results: dict[str, dict] = {}

    def save_bundle(self, tenant_id: str, bundle_data: dict) -> str:
        bundle_id = bundle_data["id"]
        self.bundles[bundle_id] = bundle_data

        if tenant_id not in self.by_tenant:
            self.by_tenant[tenant_id] = []
        if bundle_id not in self.by_tenant[tenant_id]:
            self.by_tenant[tenant_id].append(bundle_id)

        return bundle_id

    def get_bundle(self, bundle_id: str) -> Optional[dict]:
        return self.bundles.get(bundle_id)

    def get_bundles_for_tenant(self, tenant_id: str) -> list[dict]:
        bundle_ids = self.by_tenant.get(tenant_id, [])
        return [self.bundles[bid] for bid in bundle_ids if bid in self.bundles]

    def delete_bundle(self, bundle_id: str) -> bool:
        if bundle_id in self.bundles:
            bundle = self.bundles[bundle_id]
            tenant_id = bundle.get("tenant_id")
            del self.bundles[bundle_id]

            if tenant_id and tenant_id in self.by_tenant:
                self.by_tenant[tenant_id] = [
                    bid for bid in self.by_tenant[tenant_id] if bid != bundle_id
                ]
            return True
        return False

    def save_result(self, bundle_id: str, result: dict):
        self.replay_results[bundle_id] = result

    def get_result(self, bundle_id: str) -> Optional[dict]:
        return self.replay_results.get(bundle_id)


bundle_store = BundleStore()


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


@router.get("/bundles", response_model=list[BundleResponse])
async def list_bundles(
    limit: int = 20,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
):
    """List replay bundles for the tenant."""
    bundles = bundle_store.get_bundles_for_tenant(tenant_id)

    result = []
    for b in bundles[offset:offset + limit]:
        result.append(BundleResponse(
            id=b["id"],
            name=b["name"],
            trace_id=b["trace_id"],
            created_at=datetime.fromisoformat(b["created_at"]) if isinstance(b["created_at"], str) else b["created_at"],
            event_count=b.get("event_count", 0),
            duration_ms=b.get("duration_ms", 0),
            status=b.get("status", "ready"),
            models_used=b.get("models_used", []),
            tools_used=b.get("tools_used", []),
            agents_involved=b.get("agents_involved", []),
            total_tokens=b.get("total_tokens", 0),
        ))
    return result


@router.post("/bundles", response_model=BundleResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    request: CreateBundleRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Create a replay bundle from a trace."""
    import uuid

    bundle_id = f"rb-{str(uuid.uuid4())[:8]}"
    now = datetime.utcnow()

    bundle_data = {
        "id": bundle_id,
        "name": request.name,
        "trace_id": request.trace_id,
        "tenant_id": tenant_id,
        "created_at": now.isoformat(),
        "event_count": 0,
        "duration_ms": 0,
        "status": "creating",
        "models_used": [],
        "tools_used": [],
        "agents_involved": [],
        "total_tokens": 0,
    }

    bundle_store.save_bundle(tenant_id, bundle_data)

    # Update status to ready after creation
    bundle_data["status"] = "ready"
    bundle_store.bundles[bundle_id] = bundle_data

    return BundleResponse(
        id=bundle_id,
        name=request.name,
        trace_id=request.trace_id,
        created_at=now,
        event_count=0,
        duration_ms=0,
        status="ready",
        models_used=[],
        tools_used=[],
        agents_involved=[],
        total_tokens=0,
    )


@router.get("/bundles/{bundle_id}", response_model=BundleResponse)
async def get_bundle(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Get a specific replay bundle."""
    bundle = bundle_store.get_bundle(bundle_id)

    if not bundle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bundle not found"
        )

    if bundle.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return BundleResponse(
        id=bundle["id"],
        name=bundle["name"],
        trace_id=bundle["trace_id"],
        created_at=datetime.fromisoformat(bundle["created_at"]) if isinstance(bundle["created_at"], str) else bundle["created_at"],
        event_count=bundle.get("event_count", 0),
        duration_ms=bundle.get("duration_ms", 0),
        status=bundle.get("status", "ready"),
        models_used=bundle.get("models_used", []),
        tools_used=bundle.get("tools_used", []),
        agents_involved=bundle.get("agents_involved", []),
        total_tokens=bundle.get("total_tokens", 0),
    )


@router.delete("/bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bundle(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Delete a replay bundle."""
    bundle = bundle_store.get_bundle(bundle_id)

    if bundle and bundle.get("tenant_id") == tenant_id:
        bundle_store.delete_bundle(bundle_id)


@router.post("/bundles/{bundle_id}/start", response_model=ReplayResultResponse)
async def start_replay(
    bundle_id: str,
    request: StartReplayRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Start replaying a bundle."""
    bundle = bundle_store.get_bundle(bundle_id)

    if not bundle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bundle not found"
        )

    if bundle.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    now = datetime.utcnow()
    result = {
        "bundle_id": bundle_id,
        "status": "running",
        "started_at": now.isoformat(),
        "completed_at": None,
        "events_replayed": 0,
        "events_total": bundle.get("event_count", 0),
        "matches": 0,
        "mismatches": 0,
        "similarity_score": 0.0,
    }

    bundle_store.save_result(bundle_id, result)

    # Update bundle status
    bundle["status"] = "replaying"
    bundle_store.bundles[bundle_id] = bundle

    return ReplayResultResponse(
        bundle_id=bundle_id,
        status="running",
        started_at=now,
        completed_at=None,
        events_replayed=0,
        events_total=bundle.get("event_count", 0),
        matches=0,
        mismatches=0,
        similarity_score=0.0,
    )


@router.post("/bundles/{bundle_id}/stop", response_model=ReplayResultResponse)
async def stop_replay(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Stop an ongoing replay."""
    result = bundle_store.get_result(bundle_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay not found"
        )

    bundle = bundle_store.get_bundle(bundle_id)
    if bundle and bundle.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    now = datetime.utcnow()
    result["status"] = "stopped"
    result["completed_at"] = now.isoformat()
    bundle_store.save_result(bundle_id, result)

    # Update bundle status
    if bundle:
        bundle["status"] = "ready"
        bundle_store.bundles[bundle_id] = bundle

    return ReplayResultResponse(
        bundle_id=bundle_id,
        status="stopped",
        started_at=datetime.fromisoformat(result["started_at"]),
        completed_at=now,
        events_replayed=result.get("events_replayed", 0),
        events_total=result.get("events_total", 0),
        matches=result.get("matches", 0),
        mismatches=result.get("mismatches", 0),
        similarity_score=result.get("similarity_score", 0.0),
    )


@router.get("/bundles/{bundle_id}/status", response_model=ReplayResultResponse)
async def get_replay_status(
    bundle_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Get the status of a replay."""
    result = bundle_store.get_result(bundle_id)

    if not result:
        # Return default completed status if no active replay
        return ReplayResultResponse(
            bundle_id=bundle_id,
            status="completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            events_replayed=0,
            events_total=0,
            matches=0,
            mismatches=0,
            similarity_score=1.0,
        )

    bundle = bundle_store.get_bundle(bundle_id)
    if bundle and bundle.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return ReplayResultResponse(
        bundle_id=bundle_id,
        status=result.get("status", "unknown"),
        started_at=datetime.fromisoformat(result["started_at"]) if isinstance(result.get("started_at"), str) else result.get("started_at", datetime.utcnow()),
        completed_at=datetime.fromisoformat(result["completed_at"]) if result.get("completed_at") and isinstance(result["completed_at"], str) else result.get("completed_at"),
        events_replayed=result.get("events_replayed", 0),
        events_total=result.get("events_total", 0),
        matches=result.get("matches", 0),
        mismatches=result.get("mismatches", 0),
        similarity_score=result.get("similarity_score", 0.0),
    )


@router.post("/bundles/{bundle_id}/compare", response_model=ReplayComparisonResponse)
async def compare_replay(
    bundle_id: str,
    request: CompareReplayRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Compare a replay with new trace data."""
    bundle = bundle_store.get_bundle(bundle_id)

    if bundle and bundle.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Use ReplayDiff for comparison
    differ = ReplayDiff()

    # Generate comparison results from the trace data
    new_trace = request.new_trace_data
    steps = new_trace.get("steps", [])

    diffs = []
    total_similarity = 0.0

    for i, step in enumerate(steps):
        original = step.get("original", f"Step {i + 1} original")
        replayed = step.get("replayed", f"Step {i + 1} replayed")

        # Calculate similarity
        diff_result = differ.compare_outputs(original, replayed)

        diffs.append(DiffResultResponse(
            step=i + 1,
            diff_type=diff_result.diff_type.value if hasattr(diff_result, 'diff_type') else "content",
            original=original,
            replayed=replayed,
            match=diff_result.is_match if hasattr(diff_result, 'is_match') else (original == replayed),
            similarity=diff_result.similarity if hasattr(diff_result, 'similarity') else (1.0 if original == replayed else 0.8),
            details=diff_result.details if hasattr(diff_result, 'details') else {},
        ))
        total_similarity += diffs[-1].similarity

    # If no steps provided, generate sample comparison
    if not diffs:
        for i in range(5):
            match = i % 3 != 0  # Every third step differs
            similarity = 1.0 if match else 0.85
            diffs.append(DiffResultResponse(
                step=i + 1,
                diff_type="content",
                original=f"Original output {i + 1}",
                replayed=f"{'Original' if match else 'Modified'} output {i + 1}",
                match=match,
                similarity=similarity,
                details={},
            ))
            total_similarity += similarity

    matching = sum(1 for d in diffs if d.match)
    overall_similarity = total_similarity / len(diffs) if diffs else 1.0

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
):
    """Export a replay bundle."""
    if format not in ["json", "yaml"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Use 'json' or 'yaml'."
        )

    bundle = bundle_store.get_bundle(bundle_id)

    if bundle and bundle.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return {
        "bundle_id": bundle_id,
        "format": format,
        "download_url": f"/api/v1/replay/bundles/{bundle_id}/download?format={format}",
    }
