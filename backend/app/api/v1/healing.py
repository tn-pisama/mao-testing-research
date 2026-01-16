"""Healing API endpoints for self-healing fix management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, HealingRecord, N8nConnection, Trace, WorkflowVersion
from sqlalchemy import func, desc
from app.core.auth import get_current_tenant
from app.core.encryption import encrypt_value, decrypt_value
from app.fixes import FixGenerator, LoopFixGenerator, CorruptionFixGenerator, PersonaFixGenerator, DeadlockFixGenerator
from app.integrations.n8n_client import N8nApiClient, N8nApiError, N8nWorkflowDiff

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
    """Rollback an applied healing fix.

    If the healing was applied to an n8n workflow, this will restore
    the original workflow configuration in n8n.
    """
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
    n8n_rolled_back = False

    # If this was an n8n fix, actually push the rollback to n8n
    if healing.original_state and healing.workflow_id and healing.n8n_connection_id:
        conn_result = await db.execute(
            select(N8nConnection).where(N8nConnection.id == healing.n8n_connection_id)
        )
        connection = conn_result.scalar_one_or_none()

        if connection:
            api_key = decrypt_value(connection.api_key_encrypted)

            try:
                async with N8nApiClient(
                    instance_url=connection.instance_url,
                    api_key=api_key,
                ) as client:
                    # Filter original_state to only include fields n8n accepts
                    original = healing.original_state
                    update_payload = {
                        "name": original.get("name"),
                        "nodes": original.get("nodes", []),
                        "connections": original.get("connections", {}),
                        "settings": original.get("settings", {}),
                    }
                    await client.update_workflow(healing.workflow_id, update_payload)
                    n8n_rolled_back = True

                # Create version record for rollback
                version_result = await db.execute(
                    select(func.coalesce(func.max(WorkflowVersion.version_number), 0))
                    .where(
                        WorkflowVersion.tenant_id == UUID(tenant_id),
                        WorkflowVersion.workflow_id == healing.workflow_id,
                    )
                )
                next_version = version_result.scalar() + 1

                version = WorkflowVersion(
                    id=uuid4(),
                    tenant_id=UUID(tenant_id),
                    workflow_id=healing.workflow_id,
                    connection_id=connection.id,
                    version_number=next_version,
                    workflow_snapshot=healing.original_state,
                    healing_id=healing.id,
                    change_type="rollback",
                    change_description="Rolled back applied fix to original state",
                )
                db.add(version)

            except N8nApiError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to rollback workflow in n8n: {e.message}"
                )

    # Restore original state to detection if possible (for non-n8n healings)
    if healing.original_state and not n8n_rolled_back:
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
    if healing.deployment_stage:
        healing.deployment_stage = "rolled_back"

    await db.commit()
    await db.refresh(healing)

    message = "Healing has been rolled back."
    if n8n_rolled_back:
        message = "Healing has been rolled back. Original workflow restored in n8n."

    return RollbackResponse(
        healing_id=str(healing.id),
        rolled_back=True,
        previous_status=previous_status,
        current_status=healing.status,
        message=message,
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


# ============================================================================
# n8n Connection Management
# ============================================================================


class N8nConnectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    instance_url: str = Field(..., min_length=1, max_length=512)
    api_key: str = Field(..., min_length=1)


class N8nConnectionResponse(BaseModel):
    id: str
    name: str
    instance_url: str
    is_active: bool
    last_verified_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime


class N8nConnectionListResponse(BaseModel):
    items: List[N8nConnectionResponse]
    total: int


@router.post("/n8n/connections", response_model=N8nConnectionResponse)
async def create_n8n_connection(
    request: N8nConnectionCreateRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new n8n connection for this tenant.

    The API key is encrypted before storage.
    """
    await set_tenant_context(db, tenant_id)

    # Encrypt the API key
    encrypted_key = encrypt_value(request.api_key)

    # Create connection record
    connection = N8nConnection(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name=request.name,
        instance_url=request.instance_url.rstrip("/"),
        api_key_encrypted=encrypted_key,
        is_active=True,
    )

    # Test the connection
    try:
        async with N8nApiClient(
            instance_url=connection.instance_url,
            api_key=request.api_key,
        ) as client:
            if await client.test_connection():
                connection.last_verified_at = datetime.utcnow()
            else:
                connection.last_error = "Connection test failed"
    except N8nApiError as e:
        connection.last_error = str(e)

    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    return N8nConnectionResponse(
        id=str(connection.id),
        name=connection.name,
        instance_url=connection.instance_url,
        is_active=connection.is_active,
        last_verified_at=connection.last_verified_at,
        last_error=connection.last_error,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.get("/n8n/connections", response_model=N8nConnectionListResponse)
async def list_n8n_connections(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all n8n connections for this tenant."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(N8nConnection).where(
            N8nConnection.tenant_id == UUID(tenant_id)
        ).order_by(N8nConnection.created_at.desc())
    )
    connections = result.scalars().all()

    return N8nConnectionListResponse(
        items=[
            N8nConnectionResponse(
                id=str(c.id),
                name=c.name,
                instance_url=c.instance_url,
                is_active=c.is_active,
                last_verified_at=c.last_verified_at,
                last_error=c.last_error,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in connections
        ],
        total=len(connections),
    )


@router.delete("/n8n/connections/{connection_id}")
async def delete_n8n_connection(
    connection_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete an n8n connection."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(N8nConnection).where(
            N8nConnection.id == connection_id,
            N8nConnection.tenant_id == UUID(tenant_id),
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    await db.delete(connection)
    await db.commit()

    return {"message": "Connection deleted"}


@router.post("/n8n/connections/{connection_id}/test")
async def test_n8n_connection(
    connection_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Test an n8n connection."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(N8nConnection).where(
            N8nConnection.id == connection_id,
            N8nConnection.tenant_id == UUID(tenant_id),
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Decrypt API key and test
    api_key = decrypt_value(connection.api_key_encrypted)

    try:
        async with N8nApiClient(
            instance_url=connection.instance_url,
            api_key=api_key,
        ) as client:
            success = await client.test_connection()

        if success:
            connection.last_verified_at = datetime.utcnow()
            connection.last_error = None
        else:
            connection.last_error = "Connection test failed"

        await db.commit()

        return {
            "success": success,
            "message": "Connection verified" if success else "Connection test failed",
        }

    except N8nApiError as e:
        connection.last_error = str(e)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"n8n API error: {e}")


# ============================================================================
# Apply Fix to n8n
# ============================================================================


class ApplyFixToN8nRequest(BaseModel):
    connection_id: UUID
    dry_run: bool = True
    stage: bool = False  # If true, apply but keep workflow deactivated for testing


class ApplyFixToN8nResponse(BaseModel):
    status: str  # "preview", "applied", "staged", "failed"
    healing_id: Optional[str] = None
    fix: Optional[Dict[str, Any]] = None
    diff: Optional[Dict[str, Any]] = None
    backup_commit: Optional[str] = None
    workflow_version: Optional[int] = None
    deployment_stage: Optional[str] = None  # "staged", "promoted", "rejected"
    error: Optional[str] = None


@router.post("/apply-to-n8n/{detection_id}", response_model=ApplyFixToN8nResponse)
async def apply_fix_to_n8n(
    detection_id: UUID,
    request: ApplyFixToN8nRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply a recommended fix to an n8n workflow.

    Steps:
    1. Get detection and associated trace
    2. Get fix recommendation
    3. Connect to n8n instance via API
    4. If dry_run: return diff preview
    5. If not dry_run: apply fix, return result
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

    # Get the trace to find workflow ID
    trace_result = await db.execute(
        select(Trace).where(Trace.id == detection.trace_id)
    )
    trace = trace_result.scalar_one_or_none()

    if not trace:
        raise HTTPException(status_code=404, detail="Associated trace not found")

    # Get workflow ID from trace session_id (n8n execution ID format)
    # The workflow ID should be in the trace metadata or session
    workflow_id = trace.session_id

    # Get the n8n connection
    conn_result = await db.execute(
        select(N8nConnection).where(
            N8nConnection.id == request.connection_id,
            N8nConnection.tenant_id == UUID(tenant_id),
        )
    )
    connection = conn_result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="n8n connection not found")

    if not connection.is_active:
        raise HTTPException(status_code=400, detail="n8n connection is not active")

    # Generate fix suggestions
    detection_dict = {
        "id": str(detection.id),
        "detection_type": detection.detection_type,
        "method": detection.method,
        "details": detection.details,
    }

    generator = get_fix_generator()
    fixes = generator.generate_fixes(detection_dict, context={"framework": "n8n"})

    if not fixes:
        return ApplyFixToN8nResponse(
            status="failed",
            error="No fix suggestions available for this detection type",
        )

    selected_fix = fixes[0]

    # Decrypt API key and connect to n8n
    api_key = decrypt_value(connection.api_key_encrypted)

    try:
        async with N8nApiClient(
            instance_url=connection.instance_url,
            api_key=api_key,
        ) as client:
            # Get current workflow
            try:
                current_workflow = await client.get_workflow(workflow_id)
            except N8nApiError as e:
                if e.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Workflow {workflow_id} not found in n8n"
                    )
                raise

            # Apply fix to workflow (generate modified version)
            modified_workflow = _apply_fix_to_workflow(
                current_workflow,
                selected_fix.to_dict(),
                detection.detection_type,
            )

            # Generate diff
            diff = N8nWorkflowDiff.generate_diff(current_workflow, modified_workflow)

            if request.dry_run:
                # Return preview only
                return ApplyFixToN8nResponse(
                    status="preview",
                    fix={
                        "type": selected_fix.fix_type.value,
                        "description": selected_fix.description,
                        "confidence": selected_fix.confidence.value,
                    },
                    diff=diff,
                )

            # Apply the fix
            updated_workflow = await client.update_workflow(
                workflow_id,
                modified_workflow,
            )

            # Determine status based on staging
            if request.stage:
                # Deactivate workflow for staged testing
                await client.deactivate_workflow(workflow_id)
                status = "staged"
                deployment_stage = "staged"
            else:
                status = "applied"
                deployment_stage = None

            # Create healing record with n8n workflow tracking
            healing = HealingRecord(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                detection_id=detection_id,
                status=status,
                fix_type=selected_fix.fix_type.value,
                fix_id=selected_fix.id,
                fix_suggestions=[f.to_dict() for f in fixes],
                applied_fixes={
                    "workflow_id": workflow_id,
                    "connection_id": str(connection.id),
                    "fix_applied": selected_fix.to_dict(),
                    "diff": diff,
                },
                original_state=current_workflow,
                rollback_available=True,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow() if not request.stage else None,
                # n8n workflow tracking for staged deployment
                workflow_id=workflow_id,
                n8n_connection_id=connection.id,
                deployment_stage=deployment_stage,
                staged_at=datetime.utcnow() if request.stage else None,
            )

            db.add(healing)

            # Create version record
            version_result = await db.execute(
                select(func.coalesce(func.max(WorkflowVersion.version_number), 0))
                .where(
                    WorkflowVersion.tenant_id == UUID(tenant_id),
                    WorkflowVersion.workflow_id == workflow_id,
                )
            )
            next_version = version_result.scalar() + 1

            version = WorkflowVersion(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                workflow_id=workflow_id,
                connection_id=connection.id,
                version_number=next_version,
                workflow_snapshot=current_workflow,  # Store original before fix
                healing_id=healing.id,
                change_type="staged" if request.stage else "fix_applied",
                change_description=f"Applied {selected_fix.fix_type.value}: {selected_fix.description}",
            )
            db.add(version)

            # Mark detection as addressed (only if not staging)
            if not request.stage:
                detection.validated = True
            detection.details = {
                **(detection.details or {}),
                "healed_by": str(healing.id),
                "healed_at": datetime.utcnow().isoformat(),
                "healed_via_n8n": True,
                "staged": request.stage,
            }

            await db.commit()

            return ApplyFixToN8nResponse(
                status=status,
                healing_id=str(healing.id),
                fix={
                    "type": selected_fix.fix_type.value,
                    "description": selected_fix.description,
                    "confidence": selected_fix.confidence.value,
                },
                diff=diff,
                workflow_version=updated_workflow.get("versionId"),
                deployment_stage=deployment_stage,
            )

    except N8nApiError as e:
        return ApplyFixToN8nResponse(
            status="failed",
            error=f"n8n API error: {e.message}",
        )


def _apply_fix_to_workflow(
    workflow: Dict[str, Any],
    fix: Dict[str, Any],
    detection_type: str,
) -> Dict[str, Any]:
    """
    Apply a fix to a workflow configuration.

    This modifies the workflow based on the fix type and detection type.
    """
    import copy
    modified = copy.deepcopy(workflow)

    fix_type = fix.get("fix_type", "")
    nodes = modified.get("nodes", [])

    if detection_type == "infinite_loop":
        # Add loop breaker - find any Loop node and add maxIterations
        for node in nodes:
            if node.get("type") == "n8n-nodes-base.loop" or "loop" in node.get("name", "").lower():
                if "parameters" not in node:
                    node["parameters"] = {}
                # Set max iterations to prevent infinite loops
                node["parameters"]["maxIterations"] = fix.get("max_iterations", 100)

        # Add a global execution timeout if not present
        if "settings" not in modified:
            modified["settings"] = {}
        if "executionTimeout" not in modified["settings"]:
            modified["settings"]["executionTimeout"] = fix.get("timeout_seconds", 300)

    elif detection_type == "state_corruption":
        # Add data validation node at the start
        validation_node = {
            "name": "MAO_DataValidator",
            "type": "n8n-nodes-base.function",
            "typeVersion": 1,
            "position": [50, 200],
            "parameters": {
                "functionCode": """
// MAO Auto-generated validation
const items = $input.all();
for (const item of items) {
    if (!item.json || typeof item.json !== 'object') {
        throw new Error('Invalid data structure detected');
    }
}
return items;
"""
            }
        }
        nodes.insert(0, validation_node)

    elif detection_type == "coordination_failure":
        # Add error handling wrapper
        if "settings" not in modified:
            modified["settings"] = {}
        modified["settings"]["errorWorkflow"] = fix.get("error_workflow_id", "")

    elif detection_type == "persona_drift":
        # Add system prompt reinforcement for AI nodes
        for node in nodes:
            if "openai" in node.get("type", "").lower() or "anthropic" in node.get("type", "").lower():
                if "parameters" not in node:
                    node["parameters"] = {}
                existing_prompt = node["parameters"].get("systemMessage", "")
                node["parameters"]["systemMessage"] = (
                    existing_prompt + "\n\n[IMPORTANT: Maintain consistent tone and persona throughout.]"
                )

    return modified


# ============================================================================
# Staged Deployment: Promote, Reject, Rollback
# ============================================================================


class PromoteResponse(BaseModel):
    healing_id: str
    status: str
    deployment_stage: str
    workflow_id: str
    message: str


@router.post("/{healing_id}/promote", response_model=PromoteResponse)
async def promote_staged_fix(
    healing_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Promote a staged fix by activating the workflow.

    This endpoint activates a workflow that was previously staged (deactivated)
    after applying a fix, allowing it to run in production.
    """
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

    if healing.deployment_stage != "staged":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot promote: healing is not staged (current stage: {healing.deployment_stage})"
        )

    if not healing.workflow_id or not healing.n8n_connection_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot promote: missing workflow or connection information"
        )

    # Get connection
    conn_result = await db.execute(
        select(N8nConnection).where(N8nConnection.id == healing.n8n_connection_id)
    )
    connection = conn_result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="n8n connection not found")

    # Activate the workflow
    api_key = decrypt_value(connection.api_key_encrypted)

    try:
        async with N8nApiClient(
            instance_url=connection.instance_url,
            api_key=api_key,
        ) as client:
            await client.activate_workflow(healing.workflow_id)

    except N8nApiError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate workflow: {e.message}"
        )

    # Update healing record
    healing.deployment_stage = "promoted"
    healing.promoted_at = datetime.utcnow()
    healing.status = "applied"
    healing.completed_at = datetime.utcnow()

    # Create version record
    version_result = await db.execute(
        select(func.coalesce(func.max(WorkflowVersion.version_number), 0))
        .where(
            WorkflowVersion.tenant_id == UUID(tenant_id),
            WorkflowVersion.workflow_id == healing.workflow_id,
        )
    )
    next_version = version_result.scalar() + 1

    # Get current workflow state for version snapshot
    try:
        async with N8nApiClient(
            instance_url=connection.instance_url,
            api_key=api_key,
        ) as client:
            current_workflow = await client.get_workflow(healing.workflow_id)
    except N8nApiError:
        current_workflow = {}  # Fallback if we can't get current state

    version = WorkflowVersion(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        workflow_id=healing.workflow_id,
        connection_id=connection.id,
        version_number=next_version,
        workflow_snapshot=current_workflow,
        healing_id=healing.id,
        change_type="promoted",
        change_description="Promoted staged fix to production",
    )
    db.add(version)

    # Mark detection as fully validated
    detection_result = await db.execute(
        select(Detection).where(Detection.id == healing.detection_id)
    )
    detection = detection_result.scalar_one_or_none()
    if detection:
        detection.validated = True

    await db.commit()

    return PromoteResponse(
        healing_id=str(healing.id),
        status="applied",
        deployment_stage="promoted",
        workflow_id=healing.workflow_id,
        message="Staged fix promoted to production. Workflow is now active.",
    )


class RejectResponse(BaseModel):
    healing_id: str
    status: str
    deployment_stage: str
    workflow_id: str
    rolled_back: bool
    message: str


@router.post("/{healing_id}/reject", response_model=RejectResponse)
async def reject_staged_fix(
    healing_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a staged fix by rolling back to the original workflow and reactivating.

    This endpoint restores the original workflow configuration and activates it,
    effectively undoing the staged fix.
    """
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

    if healing.deployment_stage != "staged":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject: healing is not staged (current stage: {healing.deployment_stage})"
        )

    if not healing.original_state:
        raise HTTPException(
            status_code=400,
            detail="Cannot reject: no original state available for rollback"
        )

    if not healing.workflow_id or not healing.n8n_connection_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot reject: missing workflow or connection information"
        )

    # Get connection
    conn_result = await db.execute(
        select(N8nConnection).where(N8nConnection.id == healing.n8n_connection_id)
    )
    connection = conn_result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="n8n connection not found")

    # Restore original workflow and activate
    api_key = decrypt_value(connection.api_key_encrypted)

    try:
        async with N8nApiClient(
            instance_url=connection.instance_url,
            api_key=api_key,
        ) as client:
            # Filter original_state to only include fields n8n accepts
            original = healing.original_state
            update_payload = {
                "name": original.get("name"),
                "nodes": original.get("nodes", []),
                "connections": original.get("connections", {}),
                "settings": original.get("settings", {}),
            }
            await client.update_workflow(healing.workflow_id, update_payload)
            await client.activate_workflow(healing.workflow_id)

    except N8nApiError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore workflow: {e.message}"
        )

    # Update healing record
    healing.deployment_stage = "rejected"
    healing.status = "rolled_back"
    healing.rolled_back_at = datetime.utcnow()
    healing.rollback_available = False

    # Create version record
    version_result = await db.execute(
        select(func.coalesce(func.max(WorkflowVersion.version_number), 0))
        .where(
            WorkflowVersion.tenant_id == UUID(tenant_id),
            WorkflowVersion.workflow_id == healing.workflow_id,
        )
    )
    next_version = version_result.scalar() + 1

    version = WorkflowVersion(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        workflow_id=healing.workflow_id,
        connection_id=connection.id,
        version_number=next_version,
        workflow_snapshot=healing.original_state,
        healing_id=healing.id,
        change_type="rejected",
        change_description="Rejected staged fix and restored original workflow",
    )
    db.add(version)

    await db.commit()

    return RejectResponse(
        healing_id=str(healing.id),
        status="rolled_back",
        deployment_stage="rejected",
        workflow_id=healing.workflow_id,
        rolled_back=True,
        message="Staged fix rejected. Original workflow restored and activated.",
    )


# ============================================================================
# Version History
# ============================================================================


class WorkflowVersionResponse(BaseModel):
    id: str
    version_number: int
    change_type: str
    change_description: Optional[str]
    healing_id: Optional[str]
    created_at: str


class VersionHistoryResponse(BaseModel):
    workflow_id: str
    connection_id: str
    versions: List[WorkflowVersionResponse]
    total: int


@router.get("/versions/{workflow_id}", response_model=VersionHistoryResponse)
async def get_workflow_versions(
    workflow_id: str,
    connection_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get version history for a workflow."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.tenant_id == UUID(tenant_id),
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.connection_id == connection_id,
        )
        .order_by(desc(WorkflowVersion.version_number))
        .limit(limit)
    )
    versions = result.scalars().all()

    count_result = await db.execute(
        select(func.count(WorkflowVersion.id))
        .where(
            WorkflowVersion.tenant_id == UUID(tenant_id),
            WorkflowVersion.workflow_id == workflow_id,
        )
    )
    total = count_result.scalar()

    return VersionHistoryResponse(
        workflow_id=workflow_id,
        connection_id=str(connection_id),
        versions=[
            WorkflowVersionResponse(
                id=str(v.id),
                version_number=v.version_number,
                change_type=v.change_type,
                change_description=v.change_description,
                healing_id=str(v.healing_id) if v.healing_id else None,
                created_at=v.created_at.isoformat() if v.created_at else "",
            )
            for v in versions
        ],
        total=total,
    )


class RestoreVersionResponse(BaseModel):
    version_id: str
    workflow_id: str
    restored_from_version: int
    new_version_number: int
    message: str


@router.post("/versions/{version_id}/restore", response_model=RestoreVersionResponse)
async def restore_version(
    version_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Restore workflow to a specific version."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.tenant_id == UUID(tenant_id),
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    if not version.workflow_snapshot:
        raise HTTPException(status_code=400, detail="No workflow snapshot available for this version")

    # Get connection
    conn_result = await db.execute(
        select(N8nConnection).where(N8nConnection.id == version.connection_id)
    )
    connection = conn_result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="n8n connection not found")

    # Restore workflow
    api_key = decrypt_value(connection.api_key_encrypted)

    try:
        async with N8nApiClient(
            instance_url=connection.instance_url,
            api_key=api_key,
        ) as client:
            snapshot = version.workflow_snapshot
            update_payload = {
                "name": snapshot.get("name"),
                "nodes": snapshot.get("nodes", []),
                "connections": snapshot.get("connections", {}),
                "settings": snapshot.get("settings", {}),
            }
            await client.update_workflow(version.workflow_id, update_payload)

    except N8nApiError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore workflow: {e.message}"
        )

    # Create new version record
    version_result = await db.execute(
        select(func.coalesce(func.max(WorkflowVersion.version_number), 0))
        .where(
            WorkflowVersion.tenant_id == UUID(tenant_id),
            WorkflowVersion.workflow_id == version.workflow_id,
        )
    )
    next_version = version_result.scalar() + 1

    new_version = WorkflowVersion(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        workflow_id=version.workflow_id,
        connection_id=version.connection_id,
        version_number=next_version,
        workflow_snapshot=version.workflow_snapshot,
        healing_id=None,
        change_type="restored",
        change_description=f"Restored from version {version.version_number}",
    )
    db.add(new_version)

    await db.commit()

    return RestoreVersionResponse(
        version_id=str(version_id),
        workflow_id=version.workflow_id,
        restored_from_version=version.version_number,
        new_version_number=next_version,
        message=f"Workflow restored to version {version.version_number}",
    )
