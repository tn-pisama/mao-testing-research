from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from uuid import UUID

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection
from app.core.auth import get_current_tenant
from app.api.v1.schemas import DetectionResponse, DetectionValidateRequest

router = APIRouter(prefix="/detections", tags=["detections"])


@router.get("", response_model=List[DetectionResponse])
async def list_detections(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    detection_type: str = Query(None),
    validated: bool = Query(None),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    query = select(Detection).where(Detection.tenant_id == UUID(tenant_id))
    
    if detection_type:
        query = query.where(Detection.detection_type == detection_type)
    if validated is not None:
        query = query.where(Detection.validated == validated)
    
    query = query.order_by(Detection.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    detections = result.scalars().all()
    
    return [
        DetectionResponse(
            id=d.id,
            trace_id=d.trace_id,
            state_id=d.state_id,
            detection_type=d.detection_type,
            confidence=d.confidence,
            method=d.method,
            details=d.details,
            validated=d.validated,
            false_positive=d.false_positive,
            created_at=d.created_at,
        )
        for d in detections
    ]


@router.get("/{detection_id}", response_model=DetectionResponse)
async def get_detection(
    detection_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(Detection).where(
            Detection.id == detection_id,
            Detection.tenant_id == UUID(tenant_id),
        )
    )
    detection = result.scalar_one_or_none()
    
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    return DetectionResponse(
        id=detection.id,
        trace_id=detection.trace_id,
        state_id=detection.state_id,
        detection_type=detection.detection_type,
        confidence=detection.confidence,
        method=detection.method,
        details=detection.details,
        validated=detection.validated,
        false_positive=detection.false_positive,
        created_at=detection.created_at,
    )


@router.post("/{detection_id}/validate", response_model=DetectionResponse)
async def validate_detection(
    detection_id: UUID,
    request: DetectionValidateRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(Detection).where(
            Detection.id == detection_id,
            Detection.tenant_id == UUID(tenant_id),
        )
    )
    detection = result.scalar_one_or_none()
    
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    detection.validated = True
    detection.false_positive = request.false_positive
    detection.validated_by = tenant_id
    
    if request.notes:
        detection.details = {**detection.details, "validation_notes": request.notes}
    
    await db.commit()
    await db.refresh(detection)
    
    return DetectionResponse(
        id=detection.id,
        trace_id=detection.trace_id,
        state_id=detection.state_id,
        detection_type=detection.detection_type,
        confidence=detection.confidence,
        method=detection.method,
        details=detection.details,
        validated=detection.validated,
        false_positive=detection.false_positive,
        created_at=detection.created_at,
    )
