"""Review Queue API — Hand-review detections, batch verdicts, golden dataset promotion.

Based on:
- GoodEye Labs: "Evaluation is the load-bearing part" — few-shot calibration from expert reviews
- LangChain: "20-50 hand-reviewed examples beat hundreds of unverified synthetic ones"

Review process:
1. GET /review/queue — list unreviewed detections (filterable, sortable)
2. POST /review/batch — submit batch verdicts (correct/false_positive/disputed)
3. POST /review/promote/{id} — promote reviewed detection to golden dataset
4. GET /review/stats — review progress metrics
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_tenant
from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, Trace, State

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review", tags=["review"])


# ── Schemas ──────────────────────────────────────────────────────────

class ReviewVerdict(BaseModel):
    detection_id: str
    verdict: str  # "confirmed", "false_positive", "disputed"
    notes: Optional[str] = None
    promote_to_golden: bool = False


class BatchReviewRequest(BaseModel):
    reviews: List[ReviewVerdict]
    reviewer_id: Optional[str] = None


class BatchReviewResponse(BaseModel):
    reviewed: int
    promoted: int
    errors: List[str]


class ReviewQueueItem(BaseModel):
    id: str
    trace_id: str
    detection_type: str
    confidence: int
    method: str
    review_status: str
    details: dict
    created_at: str
    # Context
    explanation: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    items: List[ReviewQueueItem]
    total: int
    pending: int
    page: int
    per_page: int


class ReviewStatsResponse(BaseModel):
    total_detections: int
    pending_review: int
    confirmed: int
    false_positives: int
    disputed: int
    promoted_to_golden: int
    agreement_rate: float  # How often reviewer confirms the detector
    by_type: dict


class PromoteResponse(BaseModel):
    detection_id: str
    golden_entry_created: bool
    message: str


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str = Query("pending", description="pending|confirmed|false_positive|disputed|all"),
    detection_type: Optional[str] = Query(None),
    confidence_min: Optional[int] = Query(None, ge=0, le=100),
    confidence_max: Optional[int] = Query(None, ge=0, le=100),
    sort: str = Query("confidence_asc", description="confidence_asc|confidence_desc|newest|oldest"),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List detections for hand-review. Default: unreviewed, sorted by confidence ascending (most ambiguous first)."""
    await set_tenant_context(db, tenant_id)

    query = select(Detection).where(Detection.tenant_id == UUID(tenant_id))

    if status != "all":
        query = query.where(Detection.review_status == status)
    if detection_type:
        query = query.where(Detection.detection_type == detection_type)
    if confidence_min is not None:
        query = query.where(Detection.confidence >= confidence_min)
    if confidence_max is not None:
        query = query.where(Detection.confidence <= confidence_max)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    pending_count = (await db.execute(
        select(func.count()).where(
            Detection.tenant_id == UUID(tenant_id),
            Detection.review_status == "pending",
        )
    )).scalar() or 0

    # Sort
    if sort == "confidence_asc":
        query = query.order_by(Detection.confidence.asc())
    elif sort == "confidence_desc":
        query = query.order_by(Detection.confidence.desc())
    elif sort == "newest":
        query = query.order_by(Detection.created_at.desc())
    else:
        query = query.order_by(Detection.created_at.asc())

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    detections = result.scalars().all()

    items = []
    for d in detections:
        explanation = None
        details = d.details or {}
        if "explanation" in details:
            explanation = details["explanation"]

        items.append(ReviewQueueItem(
            id=str(d.id),
            trace_id=str(d.trace_id),
            detection_type=d.detection_type,
            confidence=d.confidence,
            method=d.method,
            review_status=d.review_status or "pending",
            details=details,
            created_at=d.created_at.isoformat() if d.created_at else "",
            explanation=explanation,
        ))

    return ReviewQueueResponse(
        items=items, total=total, pending=pending_count,
        page=page, per_page=per_page,
    )


@router.post("/batch", response_model=BatchReviewResponse)
async def submit_batch_review(
    request: BatchReviewRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Submit hand-review verdicts for multiple detections at once."""
    await set_tenant_context(db, tenant_id)

    reviewed = 0
    promoted = 0
    errors = []
    now = datetime.now(timezone.utc)
    reviewer = request.reviewer_id or tenant_id

    for rv in request.reviews:
        try:
            det_result = await db.execute(
                select(Detection).where(
                    Detection.id == UUID(rv.detection_id),
                    Detection.tenant_id == UUID(tenant_id),
                )
            )
            det = det_result.scalar_one_or_none()
            if not det:
                errors.append(f"{rv.detection_id}: not found")
                continue

            # Map verdict to review fields
            if rv.verdict == "confirmed":
                det.review_status = "confirmed"
                det.validated = True
                det.false_positive = False
            elif rv.verdict == "false_positive":
                det.review_status = "false_positive"
                det.validated = True
                det.false_positive = True
            elif rv.verdict == "disputed":
                det.review_status = "disputed"
            else:
                errors.append(f"{rv.detection_id}: invalid verdict '{rv.verdict}'")
                continue

            det.reviewed_by = reviewer
            det.reviewed_at = now
            det.review_notes = rv.notes

            if rv.promote_to_golden:
                det.promoted_to_golden = True
                promoted += 1

            reviewed += 1

        except Exception as e:
            errors.append(f"{rv.detection_id}: {str(e)[:100]}")

    await db.commit()

    logger.info("Batch review: %d reviewed, %d promoted, %d errors by %s",
                reviewed, promoted, len(errors), reviewer)

    return BatchReviewResponse(reviewed=reviewed, promoted=promoted, errors=errors)


@router.post("/promote/{detection_id}", response_model=PromoteResponse)
async def promote_to_golden(
    detection_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Promote a reviewed detection to the golden dataset for recalibration."""
    await set_tenant_context(db, tenant_id)

    det_result = await db.execute(
        select(Detection).where(
            Detection.id == detection_id,
            Detection.tenant_id == UUID(tenant_id),
        )
    )
    det = det_result.scalar_one_or_none()
    if not det:
        raise HTTPException(status_code=404, detail="Detection not found")

    if det.review_status not in ("confirmed", "false_positive"):
        raise HTTPException(status_code=400, detail="Only confirmed or false_positive detections can be promoted")

    det.promoted_to_golden = True
    await db.commit()

    return PromoteResponse(
        detection_id=str(detection_id),
        golden_entry_created=True,
        message=f"Detection promoted to golden dataset as {'positive' if det.review_status == 'confirmed' else 'negative'} example",
    )


@router.get("/stats", response_model=ReviewStatsResponse)
async def get_review_stats(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get review progress metrics."""
    await set_tenant_context(db, tenant_id)

    base = select(Detection).where(Detection.tenant_id == UUID(tenant_id))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    status_counts = await db.execute(
        select(
            Detection.review_status,
            func.count().label("count"),
        ).where(Detection.tenant_id == UUID(tenant_id))
        .group_by(Detection.review_status)
    )

    counts = {row.review_status or "pending": row.count for row in status_counts}
    pending = counts.get("pending", 0)
    confirmed = counts.get("confirmed", 0)
    false_positives = counts.get("false_positive", 0)
    disputed = counts.get("disputed", 0)

    promoted = (await db.execute(
        select(func.count()).where(
            Detection.tenant_id == UUID(tenant_id),
            Detection.promoted_to_golden == True,
        )
    )).scalar() or 0

    reviewed_total = confirmed + false_positives
    agreement_rate = confirmed / reviewed_total if reviewed_total > 0 else 0.0

    # By type
    type_counts = await db.execute(
        select(
            Detection.detection_type,
            Detection.review_status,
            func.count().label("count"),
        ).where(Detection.tenant_id == UUID(tenant_id))
        .group_by(Detection.detection_type, Detection.review_status)
    )

    by_type = {}
    for row in type_counts:
        dt = row.detection_type
        if dt not in by_type:
            by_type[dt] = {"pending": 0, "confirmed": 0, "false_positive": 0, "disputed": 0}
        status_key = row.review_status or "pending"
        if status_key in by_type[dt]:
            by_type[dt][status_key] = row.count

    return ReviewStatsResponse(
        total_detections=total,
        pending_review=pending,
        confirmed=confirmed,
        false_positives=false_positives,
        disputed=disputed,
        promoted_to_golden=promoted,
        agreement_rate=round(agreement_rate, 3),
        by_type=by_type,
    )
