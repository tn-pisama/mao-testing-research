from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection
from app.core.auth import get_verified_tenant
from app.api.v1.schemas import DetectionResponse, PaginatedDetectionResponse, DetectionValidateRequest, FixSuggestionsListResponse, ApplyFixResponse
from app.fixes import FixGenerator, LoopFixGenerator, CorruptionFixGenerator, PersonaFixGenerator, DeadlockFixGenerator
from app.detection.explainer import explain_detection

router = APIRouter(prefix="/detections", tags=["detections"])


def detection_to_response(d: Detection) -> DetectionResponse:
    """Convert Detection model to DetectionResponse with explanations."""
    # Generate explanations
    explanation_data = explain_detection({
        "detection_type": d.detection_type,
        "method": d.method,
        "details": d.details or {},
        "confidence": d.confidence,
    })

    # Map confidence (0-100 int) to tier
    conf_pct = d.confidence / 100.0 if d.confidence else 0.0
    if conf_pct >= 0.80:
        tier = "HIGH"
    elif conf_pct >= 0.60:
        tier = "LIKELY"
    elif conf_pct >= 0.40:
        tier = "POSSIBLE"
    else:
        tier = "LOW"

    return DetectionResponse(
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
        explanation=explanation_data.get("explanation"),
        business_impact=explanation_data.get("business_impact"),
        suggested_action=explanation_data.get("suggested_action"),
        confidence_tier=tier,
        detector_method=d.method,
        quality_score=_compute_quality_score(d),
        quality_dimensions=_compute_quality_dimensions(d),
    )


def _compute_quality_score(d) -> float:
    """Compute continuous quality score from detection confidence.

    quality_score = 1.0 - (confidence / 100). A detection with
    confidence 85 means quality 0.15.  No detection = quality 1.0.
    """
    return round(max(0.0, 1.0 - d.confidence / 100.0), 4)


def _compute_quality_dimensions(d) -> Dict[str, float]:
    """Compute per-dimension quality scores based on detection type."""
    base = 1.0 - d.confidence / 100.0
    dims = {"correctness": 1.0, "completeness": 1.0, "safety": 1.0, "efficiency": 1.0}

    dt = d.detection_type
    if dt in ("hallucination", "grounding"):
        dims["correctness"] = base
    elif dt in ("completion", "decomposition", "specification"):
        dims["completeness"] = base
    elif dt in ("injection", "corruption", "withholding"):
        dims["safety"] = base
    elif dt in ("loop", "overflow", "convergence", "n8n_timeout", "n8n_resource"):
        dims["efficiency"] = base
    elif dt in ("derailment", "context", "persona_drift", "communication"):
        dims["correctness"] = base * 0.7 + 0.3
        dims["completeness"] = base * 0.5 + 0.5
    else:
        # Default: spread across dimensions
        dims["correctness"] = base * 0.5 + 0.5
        dims["efficiency"] = base * 0.5 + 0.5

    return {k: round(v, 4) for k, v in dims.items()}


@router.get("", response_model=PaginatedDetectionResponse)
async def list_detections(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    detection_type: Optional[str] = Query(None),
    validated: Optional[bool] = Query(None),
    confidence_min: Optional[int] = Query(None, ge=0, le=100),
    confidence_max: Optional[int] = Query(None, ge=0, le=100),
    trace_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)

    base_query = select(Detection).where(Detection.tenant_id == UUID(tenant_id))

    if detection_type:
        base_query = base_query.where(Detection.detection_type == detection_type)
    if validated is not None:
        base_query = base_query.where(Detection.validated == validated)
    if confidence_min is not None:
        base_query = base_query.where(Detection.confidence >= confidence_min)
    if confidence_max is not None:
        base_query = base_query.where(Detection.confidence <= confidence_max)
    if trace_id:
        base_query = base_query.where(Detection.trace_id == trace_id)
    if date_from:
        base_query = base_query.where(Detection.created_at >= date_from)
    if date_to:
        base_query = base_query.where(Detection.created_at <= date_to)

    # Get total count
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar()

    # Get paginated results
    query = base_query.order_by(Detection.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    detections = result.scalars().all()

    return PaginatedDetectionResponse(
        items=[detection_to_response(d) for d in detections],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{detection_id}", response_model=DetectionResponse)
async def get_detection(
    detection_id: UUID,
    tenant_id: str = Depends(get_verified_tenant),
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

    return detection_to_response(detection)


@router.post("/{detection_id}/validate", response_model=DetectionResponse)
async def validate_detection(
    detection_id: UUID,
    request: DetectionValidateRequest,
    tenant_id: str = Depends(get_verified_tenant),
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

    return detection_to_response(detection)


def get_fix_generator() -> FixGenerator:
    generator = FixGenerator()
    generator.register(LoopFixGenerator())
    generator.register(CorruptionFixGenerator())
    generator.register(PersonaFixGenerator())
    generator.register(DeadlockFixGenerator())
    # Register all remaining generators for full coverage
    try:
        from app.fixes.hallucination_fixes import HallucinationFixGenerator
        from app.fixes.injection_fixes import InjectionFixGenerator
        from app.fixes.overflow_fixes import OverflowFixGenerator
        from app.fixes.derailment_fixes import DerailmentFixGenerator
        from app.fixes.context_neglect_fixes import ContextNeglectFixGenerator
        from app.fixes.communication_fixes import CommunicationFixGenerator
        from app.fixes.specification_fixes import SpecificationFixGenerator
        from app.fixes.decomposition_fixes import DecompositionFixGenerator
        from app.fixes.workflow_fixes import WorkflowFixGenerator
        from app.fixes.withholding_fixes import WithholdingFixGenerator
        from app.fixes.completion_fixes import CompletionFixGenerator
        from app.fixes.cost_fixes import CostFixGenerator
        from app.fixes.convergence_fixes import ConvergenceFixGenerator
        from app.fixes.grounding_fixes import GroundingFixGenerator
        from app.fixes.delegation_fixes import DelegationFixGenerator
        from app.fixes.framework_fixes import (
            N8nFixGenerator, OpenClawFixGenerator, DifyFixGenerator, LangGraphFixGenerator,
        )
        for gen_cls in [
            HallucinationFixGenerator, InjectionFixGenerator, OverflowFixGenerator,
            DerailmentFixGenerator, ContextNeglectFixGenerator, CommunicationFixGenerator,
            SpecificationFixGenerator, DecompositionFixGenerator, WorkflowFixGenerator,
            WithholdingFixGenerator, CompletionFixGenerator, CostFixGenerator,
            ConvergenceFixGenerator, GroundingFixGenerator, DelegationFixGenerator,
            N8nFixGenerator, OpenClawFixGenerator, DifyFixGenerator, LangGraphFixGenerator,
        ]:
            generator.register(gen_cls())
    except ImportError:
        pass  # Graceful degradation if some generators not available
    return generator


@router.get("/{detection_id}/fixes", response_model=FixSuggestionsListResponse)
async def get_fix_suggestions(
    detection_id: UUID,
    tenant_id: str = Depends(get_verified_tenant),
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
    
    detection_dict = {
        "id": str(detection.id),
        "detection_type": detection.detection_type,
        "method": detection.method,
        "details": detection.details,
    }
    
    generator = get_fix_generator()
    fixes = generator.generate_fixes(detection_dict, context={})
    
    return FixSuggestionsListResponse(
        detection_id=str(detection_id),
        suggestions=[f.to_dict() for f in fixes],
        total=len(fixes),
    )


@router.post("/{detection_id}/fixes/{fix_id}/apply", response_model=ApplyFixResponse)
async def apply_fix(
    detection_id: UUID,
    fix_id: str,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Apply a suggested fix to address a detected failure.

    This endpoint records the fix application and marks the detection as addressed.
    The actual fix application depends on the fix type:
    - Code fixes: Returns the fix details for the user to apply
    - Configuration fixes: Can be applied automatically if permissions allow
    - Prompt fixes: Returns the updated prompt for the user to apply
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

    # Generate fixes to validate the fix_id
    detection_dict = {
        "id": str(detection.id),
        "detection_type": detection.detection_type,
        "method": detection.method,
        "details": detection.details,
    }

    generator = get_fix_generator()
    fixes = generator.generate_fixes(detection_dict, context={})

    # Find the requested fix
    matching_fix = None
    for fix in fixes:
        if fix.id == fix_id:
            matching_fix = fix
            break

    if not matching_fix:
        raise HTTPException(status_code=404, detail=f"Fix {fix_id} not found for this detection")

    # Record the fix application in detection details
    applied_at = datetime.utcnow()
    detection.details = {
        **detection.details,
        "applied_fix": {
            "fix_id": fix_id,
            "fix_type": matching_fix.fix_type,
            "title": matching_fix.title,
            "applied_at": applied_at.isoformat(),
            "applied_by": tenant_id,
        }
    }
    detection.validated = True

    await db.commit()
    await db.refresh(detection)

    return ApplyFixResponse(
        success=True,
        fix_id=fix_id,
        detection_id=str(detection_id),
        applied_at=applied_at,
        message=f"Fix '{matching_fix.title}' has been recorded as applied. Review the code changes and apply them to your codebase.",
        rollback_available=True,
    )
