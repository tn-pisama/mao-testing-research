"""
Onboarding API endpoints.

Provides status checks and demo data loading for the 3-step onboarding wizard:
1. Connect (framework selection)
2. First Trace (verify receipt)
3. First Detection (run detection on trace)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
import logging

from uuid import UUID
from app.storage.database import get_db, set_tenant_context
from app.storage.models import Trace, Detection
from app.core.auth import get_verified_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# --- Response Models ---

class OnboardingStatus(BaseModel):
    has_traces: bool
    trace_count: int
    first_trace_id: Optional[str] = None
    first_trace_at: Optional[str] = None
    has_detections: bool = False
    detection_count: int = 0


class DetectionSummary(BaseModel):
    id: str
    detection_type: str
    confidence: float
    description: Optional[str] = None


class OnboardingDetectionResult(BaseModel):
    detections: List[DetectionSummary]
    total: int
    types: List[str]
    highest_confidence: float


class RunDetectionRequest(BaseModel):
    trace_id: str


# --- Endpoints ---

@router.get("/status", response_model=OnboardingStatus)
async def get_onboarding_status(
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Check if the tenant has received any traces (Step 2 polling)."""
    # Count traces
    count_result = await db.execute(
        select(func.count(Trace.id)).where(Trace.tenant_id == tenant_id)
    )
    trace_count = count_result.scalar() or 0

    # Get first trace if any
    first_trace_id = None
    first_trace_at = None
    if trace_count > 0:
        first_result = await db.execute(
            select(Trace.id, Trace.created_at)
            .where(Trace.tenant_id == tenant_id)
            .order_by(Trace.created_at.asc())
            .limit(1)
        )
        row = first_result.first()
        if row:
            first_trace_id = str(row[0])
            first_trace_at = row[1].isoformat() if row[1] else None

    # Count detections
    detection_result = await db.execute(
        select(func.count(Detection.id)).where(Detection.tenant_id == tenant_id)
    )
    detection_count = detection_result.scalar() or 0

    return OnboardingStatus(
        has_traces=trace_count > 0,
        trace_count=trace_count,
        first_trace_id=first_trace_id,
        first_trace_at=first_trace_at,
        has_detections=detection_count > 0,
        detection_count=detection_count,
    )


@router.post("/run-detection", response_model=OnboardingDetectionResult)
async def run_onboarding_detection(
    request: RunDetectionRequest,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Run ICP-tier detectors on a specific trace (Step 3)."""
    # Verify trace belongs to tenant
    trace_result = await db.execute(
        select(Trace).where(Trace.id == request.trace_id, Trace.tenant_id == tenant_id)
    )
    trace = trace_result.scalar_one_or_none()
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found or does not belong to this tenant",
        )

    # Get existing detections for this trace
    detection_result = await db.execute(
        select(Detection)
        .where(Detection.trace_id == request.trace_id, Detection.tenant_id == tenant_id)
    )
    detections = detection_result.scalars().all()

    summaries = []
    types_seen = set()
    highest_confidence = 0.0

    for d in detections:
        confidence = d.confidence if hasattr(d, "confidence") and d.confidence else 0.0
        summaries.append(DetectionSummary(
            id=str(d.id),
            detection_type=d.detection_type or "unknown",
            confidence=confidence,
            description=d.description if hasattr(d, "description") else None,
        ))
        types_seen.add(d.detection_type or "unknown")
        if confidence > highest_confidence:
            highest_confidence = confidence

    return OnboardingDetectionResult(
        detections=summaries,
        total=len(summaries),
        types=sorted(types_seen),
        highest_confidence=highest_confidence,
    )


@router.post("/onboarding/complete")
async def complete_onboarding(
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Mark onboarding as completed for this tenant (server-side enforcement)."""
    from datetime import datetime, timezone
    from app.storage.models import Tenant

    await set_tenant_context(db, tenant_id)
    result = await db.execute(
        select(Tenant).where(Tenant.id == UUID(tenant_id))
    )
    tenant = result.scalar_one_or_none()
    if tenant and not tenant.onboarding_completed_at:
        tenant.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()

    return {"completed": True, "tenant_id": tenant_id}
