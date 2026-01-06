"""Healing API endpoints for self-healing fix management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, HealingRecord
from app.core.auth import get_current_tenant
from app.fixes import FixGenerator, LoopFixGenerator, CorruptionFixGenerator, PersonaFixGenerator, DeadlockFixGenerator

router = APIRouter(prefix="/healing", tags=["healing"])


# Request/Response schemas
class TriggerHealingRequest(BaseModel):
    fix_id: Optional[str] = None  # If not specified, use first suggested fix
    approval_required: bool = False


class TriggerHealingResponse(BaseModel):
    healing_id: str
    detection_id: str
    status: str
    fix_type: str
    fix_id: str
    message: str
    approval_required: bool


class HealingStatusResponse(BaseModel):
    id: str
    detection_id: str
    status: str
    fix_type: str
    fix_id: str
    fix_suggestions: List[Dict[str, Any]]
    applied_fixes: Dict[str, Any]
    original_state: Dict[str, Any]
    rollback_available: bool
    validation_status: Optional[str]
    validation_results: Dict[str, Any]
    approval_required: bool
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    rolled_back_at: Optional[datetime]
    created_at: datetime
    error_message: Optional[str]


class ApproveHealingRequest(BaseModel):
    approved: bool
    approver_id: Optional[str] = None
    notes: Optional[str] = None


class ApproveHealingResponse(BaseModel):
    healing_id: str
    approved: bool
    status: str
    message: str


class RollbackResponse(BaseModel):
    healing_id: str
    rolled_back: bool
    previous_status: str
    current_status: str
    message: str


class HealingListResponse(BaseModel):
    items: List[HealingStatusResponse]
    total: int
    page: int
    per_page: int


def get_fix_generator() -> FixGenerator:
    """Create and configure the fix generator."""
    generator = FixGenerator()
    generator.register(LoopFixGenerator())
    generator.register(CorruptionFixGenerator())
    generator.register(PersonaFixGenerator())
    generator.register(DeadlockFixGenerator())
    return generator


@router.post("/trigger/{detection_id}", response_model=TriggerHealingResponse)
async def trigger_healing(
    detection_id: UUID,
    request: TriggerHealingRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Start a healing process for a detected failure.

    This creates a HealingRecord and generates fix suggestions.
    If approval_required is True, the fix won't be applied until approved.
    """
    await set_tenant_context(db, tenant_id)

    # Get the detection
    result = await db.execute(
        select(Detection).where(
            Detection.id == detection_id,
            Detection.tenant_id == UUID(tenant_id),
        )
    )
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")

    # Generate fix suggestions
    detection_dict = {
        "id": str(detection.id),
        "detection_type": detection.detection_type,
        "method": detection.method,
        "details": detection.details,
    }

    generator = get_fix_generator()
    fixes = generator.generate_fixes(detection_dict, context={})

    if not fixes:
        raise HTTPException(
            status_code=400,
            detail="No fix suggestions available for this detection type"
        )

    # Select the fix to apply
    if request.fix_id:
        matching_fix = next((f for f in fixes if f.id == request.fix_id), None)
        if not matching_fix:
            raise HTTPException(status_code=404, detail=f"Fix {request.fix_id} not found")
        selected_fix = matching_fix
    else:
        # Use the first (highest priority) fix
        selected_fix = fixes[0]

    # Capture original state for rollback
    original_state = {
        "detection_validated": detection.validated,
        "detection_false_positive": detection.false_positive,
        "detection_details": detection.details.copy() if detection.details else {},
    }

    # Create healing record
    healing = HealingRecord(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        detection_id=detection_id,
        status="pending" if request.approval_required else "in_progress",
        fix_type=selected_fix.fix_type.value,
        fix_id=selected_fix.id,
        fix_suggestions=[f.to_dict() for f in fixes],
        original_state=original_state,
        approval_required=request.approval_required,
        started_at=None if request.approval_required else datetime.utcnow(),
    )

    db.add(healing)
    await db.commit()
    await db.refresh(healing)

    return TriggerHealingResponse(
        healing_id=str(healing.id),
        detection_id=str(detection_id),
        status=healing.status,
        fix_type=healing.fix_type,
        fix_id=healing.fix_id,
        message=(
            "Healing awaiting approval" if request.approval_required
            else "Healing started. Apply the suggested fix to your codebase."
        ),
        approval_required=healing.approval_required,
    )


@router.get("/{healing_id}/status", response_model=HealingStatusResponse)
async def get_healing_status(
    healing_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of a healing operation."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(HealingRecord).where(
            HealingRecord.id == healing_id,
            HealingRecord.tenant_id == UUID(tenant_id),
        )
    )
    healing = result.scalar_one_or_none()

    if not healing:
        raise HTTPException(status_code=404, detail="Healing record not found")

    return HealingStatusResponse(
        id=str(healing.id),
        detection_id=str(healing.detection_id),
        status=healing.status,
        fix_type=healing.fix_type,
        fix_id=healing.fix_id,
        fix_suggestions=healing.fix_suggestions or [],
        applied_fixes=healing.applied_fixes or {},
        original_state=healing.original_state or {},
        rollback_available=healing.rollback_available,
        validation_status=healing.validation_status,
        validation_results=healing.validation_results or {},
        approval_required=healing.approval_required,
        approved_by=healing.approved_by,
        approved_at=healing.approved_at,
        started_at=healing.started_at,
        completed_at=healing.completed_at,
        rolled_back_at=healing.rolled_back_at,
        created_at=healing.created_at,
        error_message=healing.error_message,
    )


@router.post("/{healing_id}/approve", response_model=ApproveHealingResponse)
async def approve_healing(
    healing_id: UUID,
    request: ApproveHealingRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a pending healing operation."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(HealingRecord).where(
            HealingRecord.id == healing_id,
            HealingRecord.tenant_id == UUID(tenant_id),
        )
    )
    healing = result.scalar_one_or_none()

    if not healing:
        raise HTTPException(status_code=404, detail="Healing record not found")

    if healing.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve healing with status '{healing.status}'"
        )

    if request.approved:
        healing.status = "in_progress"
        healing.approved_by = request.approver_id or tenant_id
        healing.approved_at = datetime.utcnow()
        healing.started_at = datetime.utcnow()
        message = "Healing approved and started"
    else:
        healing.status = "rejected"
        healing.approved_by = request.approver_id or tenant_id
        healing.approved_at = datetime.utcnow()
        healing.completed_at = datetime.utcnow()
        message = "Healing rejected"

    if request.notes:
        healing.validation_results = {
            **(healing.validation_results or {}),
            "approval_notes": request.notes
        }

    await db.commit()
    await db.refresh(healing)

    return ApproveHealingResponse(
        healing_id=str(healing.id),
        approved=request.approved,
        status=healing.status,
        message=message,
    )


@router.post("/{healing_id}/rollback", response_model=RollbackResponse)
async def rollback_healing(
    healing_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Rollback an applied healing fix."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(HealingRecord).where(
            HealingRecord.id == healing_id,
            HealingRecord.tenant_id == UUID(tenant_id),
        )
    )
    healing = result.scalar_one_or_none()

    if not healing:
        raise HTTPException(status_code=404, detail="Healing record not found")

    if not healing.rollback_available:
        raise HTTPException(
            status_code=400,
            detail="Rollback not available for this healing record"
        )

    if healing.status == "rolled_back":
        raise HTTPException(status_code=400, detail="Healing already rolled back")

    previous_status = healing.status

    # Restore original state to detection if possible
    if healing.original_state:
        detection_result = await db.execute(
            select(Detection).where(Detection.id == healing.detection_id)
        )
        detection = detection_result.scalar_one_or_none()
        if detection:
            orig = healing.original_state
            detection.validated = orig.get("detection_validated", False)
            detection.false_positive = orig.get("detection_false_positive")
            detection.details = orig.get("detection_details", {})

    healing.status = "rolled_back"
    healing.rolled_back_at = datetime.utcnow()
    healing.rollback_available = False

    await db.commit()
    await db.refresh(healing)

    return RollbackResponse(
        healing_id=str(healing.id),
        rolled_back=True,
        previous_status=previous_status,
        current_status=healing.status,
        message="Healing has been rolled back. Manual changes may still need to be reverted.",
    )


@router.get("", response_model=HealingListResponse)
async def list_healing_records(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    detection_id: Optional[UUID] = Query(None),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List healing records with optional filtering."""
    await set_tenant_context(db, tenant_id)

    query = select(HealingRecord).where(
        HealingRecord.tenant_id == UUID(tenant_id)
    )

    if status:
        query = query.where(HealingRecord.status == status)
    if detection_id:
        query = query.where(HealingRecord.detection_id == detection_id)

    # Count total
    count_query = select(HealingRecord.id).where(
        HealingRecord.tenant_id == UUID(tenant_id)
    )
    if status:
        count_query = count_query.where(HealingRecord.status == status)
    if detection_id:
        count_query = count_query.where(HealingRecord.detection_id == detection_id)

    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Get paginated results
    query = query.order_by(HealingRecord.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    healings = result.scalars().all()

    items = [
        HealingStatusResponse(
            id=str(h.id),
            detection_id=str(h.detection_id),
            status=h.status,
            fix_type=h.fix_type,
            fix_id=h.fix_id,
            fix_suggestions=h.fix_suggestions or [],
            applied_fixes=h.applied_fixes or {},
            original_state=h.original_state or {},
            rollback_available=h.rollback_available,
            validation_status=h.validation_status,
            validation_results=h.validation_results or {},
            approval_required=h.approval_required,
            approved_by=h.approved_by,
            approved_at=h.approved_at,
            started_at=h.started_at,
            completed_at=h.completed_at,
            rolled_back_at=h.rolled_back_at,
            created_at=h.created_at,
            error_message=h.error_message,
        )
        for h in healings
    ]

    return HealingListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/{healing_id}/complete", response_model=HealingStatusResponse)
async def complete_healing(
    healing_id: UUID,
    validation_passed: bool = True,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Mark a healing operation as complete after the fix has been applied."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(HealingRecord).where(
            HealingRecord.id == healing_id,
            HealingRecord.tenant_id == UUID(tenant_id),
        )
    )
    healing = result.scalar_one_or_none()

    if not healing:
        raise HTTPException(status_code=404, detail="Healing record not found")

    if healing.status not in ("in_progress", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete healing with status '{healing.status}'"
        )

    healing.status = "applied" if validation_passed else "failed"
    healing.completed_at = datetime.utcnow()
    healing.validation_status = "passed" if validation_passed else "failed"

    # Mark detection as addressed
    if validation_passed:
        detection_result = await db.execute(
            select(Detection).where(Detection.id == healing.detection_id)
        )
        detection = detection_result.scalar_one_or_none()
        if detection:
            detection.validated = True
            detection.details = {
                **(detection.details or {}),
                "healed_by": str(healing.id),
                "healed_at": datetime.utcnow().isoformat(),
            }

    await db.commit()
    await db.refresh(healing)

    return HealingStatusResponse(
        id=str(healing.id),
        detection_id=str(healing.detection_id),
        status=healing.status,
        fix_type=healing.fix_type,
        fix_id=healing.fix_id,
        fix_suggestions=healing.fix_suggestions or [],
        applied_fixes=healing.applied_fixes or {},
        original_state=healing.original_state or {},
        rollback_available=healing.rollback_available,
        validation_status=healing.validation_status,
        validation_results=healing.validation_results or {},
        approval_required=healing.approval_required,
        approved_by=healing.approved_by,
        approved_at=healing.approved_at,
        started_at=healing.started_at,
        completed_at=healing.completed_at,
        rolled_back_at=healing.rolled_back_at,
        created_at=healing.created_at,
        error_message=healing.error_message,
    )
