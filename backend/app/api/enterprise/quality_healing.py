"""Quality healing API endpoints with database persistence."""

import time
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from pydantic import BaseModel, Field

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.healing.engine import QualityHealingEngine
from app.enterprise.quality.healing.models import QualityHealingStatus
from app.core.auth import get_current_tenant
from app.storage.database import get_db, set_tenant_context
from app.storage.models import QualityHealingRecord, WorkflowQualityAssessment

router = APIRouter(prefix="/enterprise/quality-healing", tags=["quality-healing"])


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class TriggerHealingRequest(BaseModel):
    """Request to trigger quality healing on a workflow."""
    workflow: Dict[str, Any] = Field(..., description="The n8n workflow JSON")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Score threshold below which dimensions are targeted")
    auto_apply: bool = Field(default=False, description="Automatically apply fixes without approval")
    execution_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional execution history for quality assessment",
    )
    assessment_id: Optional[str] = Field(
        default=None,
        description="Link to an existing assessment ID",
    )


class TriggerHealingResponse(BaseModel):
    """Response after triggering quality healing."""
    healing_id: str
    status: str
    dimensions_targeted: List[str]
    fix_suggestions_count: int
    before_score: float
    fix_suggestions: List[Dict[str, Any]]


class ApproveHealingRequest(BaseModel):
    """Request to approve specific fixes from a pending healing."""
    selected_fix_ids: List[str] = Field(..., description="IDs of fixes to approve and apply")
    approved_by: Optional[str] = Field(default=None, description="User who approved")


class HealingStatusResponse(BaseModel):
    """Full status of a healing operation."""
    id: str
    status: str
    before_score: float
    after_score: Optional[float] = None
    dimensions_targeted: List[str]
    fix_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    applied_fixes: List[Dict[str, Any]]
    validation_results: List[Dict[str, Any]]
    rollback_available: bool = True
    is_successful: bool
    score_improvement: Optional[float] = None
    workflow_id: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class HealingListResponse(BaseModel):
    """Response for listing healing records."""
    items: List[HealingStatusResponse]
    total: int
    page: int = 1
    page_size: int = 50


class HealingStatsResponse(BaseModel):
    """Aggregate statistics about quality healing operations."""
    total: int
    success_rate: float
    avg_improvement: float
    by_status: Dict[str, int]
    by_dimension: Dict[str, int]


class RollbackResponse(BaseModel):
    """Response after rolling back a healing operation."""
    success: bool
    message: str
    healing_id: str


# ---------------------------------------------------------------------------
# Helper to convert a DB record to response
# ---------------------------------------------------------------------------

def _record_to_status(record: QualityHealingRecord) -> HealingStatusResponse:
    after_score = record.after_score
    before_score = record.before_score or 0.0
    is_successful = record.status in ("success", "partial_success")
    score_improvement = None
    if after_score is not None:
        score_improvement = round(after_score - before_score, 3)

    return HealingStatusResponse(
        id=str(record.id),
        status=record.status,
        before_score=round(before_score, 3),
        after_score=round(after_score, 3) if after_score is not None else None,
        dimensions_targeted=record.dimensions_targeted or [],
        fix_suggestions=record.fix_suggestions or [],
        applied_fixes=record.applied_fixes or [],
        validation_results=record.validation_results or [],
        rollback_available=record.rollback_available or False,
        is_successful=is_successful,
        score_improvement=score_improvement,
        workflow_id=record.workflow_id,
        error_message=record.error_message,
        started_at=record.started_at,
        completed_at=record.completed_at,
        created_at=record.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/tenants/{tenant_id}/trigger", response_model=TriggerHealingResponse)
async def trigger_healing(
    request: TriggerHealingRequest,
    tenant_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """
    Trigger quality healing on a workflow.

    Runs a quality assessment, then generates fix suggestions for dimensions
    scoring below the given threshold. If ``auto_apply`` is True the fixes
    are applied immediately; otherwise the healing is left in PENDING status
    awaiting approval.
    """
    await set_tenant_context(db, str(tenant_id))

    try:
        started_at = datetime.now(timezone.utc)

        # Step 1: Run quality assessment
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(
            workflow=request.workflow,
            execution_history=request.execution_history,
        )

        # Step 2: Run healing engine
        engine = QualityHealingEngine(
            auto_apply=request.auto_apply,
            score_threshold=request.threshold,
        )
        result = engine.heal(
            quality_report=report,
            workflow_config=request.workflow,
        )

        fix_suggestions = result.metadata.get("fix_suggestions", [])

        # Step 3: Persist to database
        assessment_id = None
        if request.assessment_id:
            assessment_id = UUID(request.assessment_id)

        record = QualityHealingRecord(
            tenant_id=tenant_id,
            assessment_id=assessment_id or UUID("00000000-0000-0000-0000-000000000000"),
            status=result.status.value,
            before_score=result.before_score,
            after_score=result.after_score,
            dimensions_targeted=result.dimensions_targeted,
            fix_suggestions=fix_suggestions,
            applied_fixes=[f.to_dict() for f in result.applied_fixes],
            original_state=request.workflow,
            modified_state=(
                result.applied_fixes[-1].modified_state
                if result.applied_fixes
                else {}
            ),
            rollback_available=bool(result.applied_fixes),
            validation_results=[v.to_dict() for v in result.validation_results],
            approval_required=not request.auto_apply,
            started_at=started_at,
            completed_at=result.completed_at,
            workflow_id=request.workflow.get("id"),
            error_message=result.error,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return TriggerHealingResponse(
            healing_id=str(record.id),
            status=record.status,
            dimensions_targeted=record.dimensions_targeted or [],
            fix_suggestions_count=len(fix_suggestions),
            before_score=round(result.before_score, 3),
            fix_suggestions=fix_suggestions,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quality healing failed: {str(e)}")


@router.get("/tenants/{tenant_id}/stats", response_model=HealingStatsResponse)
async def get_healing_stats(
    tenant_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Get aggregate statistics about quality healing operations."""
    await set_tenant_context(db, str(tenant_id))

    try:
        # Total count
        total_result = await db.execute(
            select(func.count()).select_from(
                select(QualityHealingRecord).where(
                    QualityHealingRecord.tenant_id == tenant_id
                ).subquery()
            )
        )
        total = total_result.scalar() or 0

        if total == 0:
            return HealingStatsResponse(
                total=0, success_rate=0.0, avg_improvement=0.0,
                by_status={}, by_dimension={},
            )

        # By status
        status_result = await db.execute(
            select(
                QualityHealingRecord.status,
                func.count().label("count"),
            ).where(
                QualityHealingRecord.tenant_id == tenant_id
            ).group_by(QualityHealingRecord.status)
        )
        by_status = {row.status: row.count for row in status_result}

        # Success rate
        success_count = by_status.get("success", 0) + by_status.get("partial_success", 0)
        success_rate = success_count / total if total > 0 else 0.0

        # Average improvement
        avg_result = await db.execute(
            select(
                func.avg(QualityHealingRecord.after_score - QualityHealingRecord.before_score)
            ).where(
                QualityHealingRecord.tenant_id == tenant_id,
                QualityHealingRecord.after_score.isnot(None),
            )
        )
        avg_improvement = avg_result.scalar() or 0.0

        # By dimension (aggregate from JSONB dimensions_targeted)
        all_records = await db.execute(
            select(QualityHealingRecord.dimensions_targeted).where(
                QualityHealingRecord.tenant_id == tenant_id
            )
        )
        by_dimension: Dict[str, int] = {}
        for row in all_records:
            dims = row[0] or []
            for dim in dims:
                by_dimension[dim] = by_dimension.get(dim, 0) + 1

        return HealingStatsResponse(
            total=total,
            success_rate=round(success_rate, 3),
            avg_improvement=round(float(avg_improvement), 3),
            by_status=by_status,
            by_dimension=by_dimension,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get healing stats: {str(e)}")


@router.get("/tenants/{tenant_id}/healings/{healing_id}", response_model=HealingStatusResponse)
async def get_healing_status(
    tenant_id: UUID = Path(...),
    healing_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Get the full status of a healing operation."""
    await set_tenant_context(db, str(tenant_id))

    result = await db.execute(
        select(QualityHealingRecord).where(
            QualityHealingRecord.id == healing_id,
            QualityHealingRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail=f"Healing record {healing_id} not found")

    return _record_to_status(record)


@router.post("/tenants/{tenant_id}/healings/{healing_id}/approve", response_model=HealingStatusResponse)
async def approve_healing(
    request: ApproveHealingRequest,
    tenant_id: UUID = Path(...),
    healing_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Approve and apply selected fixes from a pending healing operation."""
    await set_tenant_context(db, str(tenant_id))

    result = await db.execute(
        select(QualityHealingRecord).where(
            QualityHealingRecord.id == healing_id,
            QualityHealingRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail=f"Healing record {healing_id} not found")

    if record.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Healing is not pending (status: {record.status})",
        )

    try:
        # Re-run engine with auto_apply on the original workflow using selected fixes
        engine = QualityHealingEngine(auto_apply=True)
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(workflow=record.original_state or {})
        heal_result = engine.heal(report, record.original_state or {})

        now = datetime.now(timezone.utc)
        record.status = heal_result.status.value
        record.applied_fixes = [f.to_dict() for f in heal_result.applied_fixes]
        record.validation_results = [v.to_dict() for v in heal_result.validation_results]
        record.after_score = heal_result.after_score
        record.modified_state = (
            heal_result.applied_fixes[-1].modified_state
            if heal_result.applied_fixes
            else {}
        )
        record.approved_by = request.approved_by
        record.approved_at = now
        record.completed_at = now

        await db.commit()
        await db.refresh(record)

        return _record_to_status(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@router.post("/tenants/{tenant_id}/healings/{healing_id}/rollback", response_model=RollbackResponse)
async def rollback_healing(
    tenant_id: UUID = Path(...),
    healing_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Rollback all applied quality fixes for a healing operation."""
    await set_tenant_context(db, str(tenant_id))

    result = await db.execute(
        select(QualityHealingRecord).where(
            QualityHealingRecord.id == healing_id,
            QualityHealingRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail=f"Healing record {healing_id} not found")

    if not record.applied_fixes:
        raise HTTPException(status_code=400, detail="No applied fixes to rollback")

    now = datetime.now(timezone.utc)
    record.status = "rolled_back"
    record.rolled_back_at = now
    record.modified_state = {}  # Clear modified state
    record.rollback_available = False

    await db.commit()
    await db.refresh(record)

    return RollbackResponse(
        success=True,
        message=f"Successfully rolled back healing {healing_id}",
        healing_id=str(record.id),
    )


@router.get("/tenants/{tenant_id}/healings", response_model=HealingListResponse)
async def list_healings(
    tenant_id: UUID = Path(...),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Page size"),
    status: Optional[str] = Query(default=None, description="Filter by healing status"),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """List healing records with pagination and optional status filter."""
    await set_tenant_context(db, str(tenant_id))

    try:
        query = select(QualityHealingRecord).where(
            QualityHealingRecord.tenant_id == tenant_id
        )

        if status:
            valid_statuses = [s.value for s in QualityHealingStatus]
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status '{status}'. Valid values: {valid_statuses}",
                )
            query = query.where(QualityHealingRecord.status == status)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.order_by(QualityHealingRecord.created_at.desc()).offset(offset).limit(page_size)

        result = await db.execute(query)
        records = result.scalars().all()

        items = [_record_to_status(r) for r in records]
        return HealingListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list healings: {str(e)}")


@router.post("/tenants/{tenant_id}/healings/{healing_id}/verify", response_model=HealingStatusResponse)
async def verify_healing(
    tenant_id: UUID = Path(...),
    healing_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Re-verify a healing by running a fresh quality assessment on the modified workflow."""
    await set_tenant_context(db, str(tenant_id))

    result = await db.execute(
        select(QualityHealingRecord).where(
            QualityHealingRecord.id == healing_id,
            QualityHealingRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail=f"Healing record {healing_id} not found")

    if not record.applied_fixes:
        raise HTTPException(status_code=400, detail="No applied fixes to verify")

    try:
        modified_workflow = record.modified_state or {}

        # Re-run quality assessment on modified workflow
        assessor = QualityAssessor(use_llm_judge=False)
        new_report = assessor.assess_workflow(workflow=modified_workflow)

        record.after_score = new_report.overall_score

        # Determine status based on score improvement
        if record.after_score is not None and record.after_score > (record.before_score or 0):
            record.status = "success"
        else:
            record.status = "failed"

        await db.commit()
        await db.refresh(record)

        return _record_to_status(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
