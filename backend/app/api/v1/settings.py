"""Tenant settings API endpoints.

Allows tenants to customize detection thresholds and other settings.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Tenant
from app.core.auth import get_verified_tenant
from app.config import (
    FRAMEWORK_THRESHOLDS,
    FrameworkThresholds,
    get_framework_thresholds,
    get_tenant_thresholds,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class ThresholdConfig(BaseModel):
    """Threshold configuration for a framework."""
    structural_threshold: Optional[float] = Field(
        None, ge=0.5, le=0.99,
        description="Threshold for structural (hash-based) loop detection"
    )
    semantic_threshold: Optional[float] = Field(
        None, ge=0.5, le=0.99,
        description="Threshold for semantic (embedding-based) loop detection"
    )
    loop_detection_window: Optional[int] = Field(
        None, ge=3, le=20,
        description="Number of recent states to analyze for loops"
    )
    min_matches_for_loop: Optional[int] = Field(
        None, ge=2, le=10,
        description="Minimum matching states to trigger loop detection"
    )
    confidence_scaling: Optional[float] = Field(
        None, ge=0.5, le=1.5,
        description="Scale factor for detection confidence (1.0 = no change)"
    )


class DetectionThresholdsRequest(BaseModel):
    """Request model for updating detection thresholds."""
    global_thresholds: Optional[ThresholdConfig] = Field(
        None, description="Global thresholds applied to all frameworks"
    )
    framework_thresholds: Optional[Dict[str, ThresholdConfig]] = Field(
        None, description="Per-framework threshold overrides"
    )


class ThresholdResponse(BaseModel):
    """Response model for threshold configuration."""
    structural_threshold: float
    semantic_threshold: float
    loop_detection_window: int
    min_matches_for_loop: int
    confidence_scaling: float


class DetectionThresholdsResponse(BaseModel):
    """Response model for all detection thresholds."""
    global_thresholds: Optional[ThresholdConfig]
    framework_thresholds: Dict[str, ThresholdConfig]
    effective_thresholds: Dict[str, ThresholdResponse]
    available_frameworks: List[str]


@router.get("/thresholds", response_model=DetectionThresholdsResponse)
async def get_detection_thresholds(
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get current detection threshold settings.

    Returns both the tenant's custom settings and the effective thresholds
    (tenant settings merged with framework defaults).
    """
    await set_tenant_context(db, tenant_id)

    # Get tenant
    result = await db.execute(
        select(Tenant).where(Tenant.id == UUID(tenant_id))
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    tenant_settings = tenant.settings or {}
    detection_config = tenant_settings.get("detection_thresholds", {})

    # Parse tenant's current settings
    global_config = detection_config.get("global", {})
    framework_configs = detection_config.get("frameworks", {})

    # Convert to response models
    global_thresholds = ThresholdConfig(**global_config) if global_config else None
    framework_thresholds = {
        fw: ThresholdConfig(**cfg) for fw, cfg in framework_configs.items()
    }

    # Calculate effective thresholds for each framework
    effective = {}
    for framework in FRAMEWORK_THRESHOLDS.keys():
        thresholds = get_tenant_thresholds(tenant_settings, framework)
        effective[framework] = ThresholdResponse(
            structural_threshold=thresholds.structural_threshold,
            semantic_threshold=thresholds.semantic_threshold,
            loop_detection_window=thresholds.loop_detection_window,
            min_matches_for_loop=thresholds.min_matches_for_loop,
            confidence_scaling=thresholds.confidence_scaling,
        )

    return DetectionThresholdsResponse(
        global_thresholds=global_thresholds,
        framework_thresholds=framework_thresholds,
        effective_thresholds=effective,
        available_frameworks=list(FRAMEWORK_THRESHOLDS.keys()),
    )


@router.put("/thresholds", response_model=DetectionThresholdsResponse)
async def update_detection_thresholds(
    request: DetectionThresholdsRequest,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update detection threshold settings.

    Thresholds can be set globally or per-framework. Per-framework settings
    override global settings, which override framework defaults.
    """
    await set_tenant_context(db, tenant_id)

    # Get tenant
    result = await db.execute(
        select(Tenant).where(Tenant.id == UUID(tenant_id))
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Validate framework names
    if request.framework_thresholds:
        valid_frameworks = set(FRAMEWORK_THRESHOLDS.keys())
        for fw in request.framework_thresholds.keys():
            if fw.lower() not in valid_frameworks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown framework: {fw}. Valid: {list(valid_frameworks)}",
                )

    # Build new detection config
    tenant_settings = dict(tenant.settings or {})
    detection_config = tenant_settings.get("detection_thresholds", {
        "global": {},
        "frameworks": {},
    })

    # Update global thresholds
    if request.global_thresholds:
        global_dict = request.global_thresholds.model_dump(exclude_none=True)
        detection_config["global"] = global_dict
    elif request.global_thresholds is None and "global" in detection_config:
        # Keep existing global config
        pass

    # Update framework thresholds
    if request.framework_thresholds:
        frameworks_dict = {}
        for fw, cfg in request.framework_thresholds.items():
            cfg_dict = cfg.model_dump(exclude_none=True)
            if cfg_dict:  # Only include if there are actual values
                frameworks_dict[fw.lower()] = cfg_dict
        detection_config["frameworks"] = frameworks_dict
    elif request.framework_thresholds is None and "frameworks" in detection_config:
        # Keep existing framework config
        pass

    # Save to tenant settings
    tenant_settings["detection_thresholds"] = detection_config
    tenant.settings = tenant_settings

    await db.commit()
    await db.refresh(tenant)

    # Return updated thresholds
    return await get_detection_thresholds(tenant_id, db)


@router.delete("/thresholds")
async def reset_detection_thresholds(
    framework: Optional[str] = None,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Reset detection thresholds to defaults.

    If framework is specified, only reset that framework's thresholds.
    Otherwise, reset all custom thresholds.
    """
    await set_tenant_context(db, tenant_id)

    # Get tenant
    result = await db.execute(
        select(Tenant).where(Tenant.id == UUID(tenant_id))
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    tenant_settings = dict(tenant.settings or {})

    if framework:
        # Reset specific framework
        framework_key = framework.lower().strip()
        if framework_key not in FRAMEWORK_THRESHOLDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown framework: {framework}",
            )
        detection_config = tenant_settings.get("detection_thresholds", {})
        frameworks = detection_config.get("frameworks", {})
        if framework_key in frameworks:
            del frameworks[framework_key]
            detection_config["frameworks"] = frameworks
            tenant_settings["detection_thresholds"] = detection_config
    else:
        # Reset all thresholds
        tenant_settings["detection_thresholds"] = {
            "global": {},
            "frameworks": {},
        }

    tenant.settings = tenant_settings
    await db.commit()

    return {"message": f"Thresholds reset{' for ' + framework if framework else ''}"}


@router.get("/thresholds/defaults", response_model=Dict[str, ThresholdResponse])
async def get_default_thresholds():
    """Get the default thresholds for all frameworks.

    This endpoint is public and doesn't require authentication.
    Useful for displaying defaults in the UI.
    """
    return {
        framework: ThresholdResponse(
            structural_threshold=thresholds.structural_threshold,
            semantic_threshold=thresholds.semantic_threshold,
            loop_detection_window=thresholds.loop_detection_window,
            min_matches_for_loop=thresholds.min_matches_for_loop,
            confidence_scaling=thresholds.confidence_scaling,
        )
        for framework, thresholds in FRAMEWORK_THRESHOLDS.items()
    }


@router.get("/thresholds/preview", response_model=ThresholdResponse)
async def preview_effective_thresholds(
    framework: str,
    structural_threshold: Optional[float] = None,
    semantic_threshold: Optional[float] = None,
    loop_detection_window: Optional[int] = None,
    min_matches_for_loop: Optional[int] = None,
    confidence_scaling: Optional[float] = None,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Preview effective thresholds with proposed changes.

    Useful for showing users what their detection behavior would look like
    before saving changes.
    """
    await set_tenant_context(db, tenant_id)

    # Get tenant
    result = await db.execute(
        select(Tenant).where(Tenant.id == UUID(tenant_id))
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Start with tenant's current effective thresholds
    current = get_tenant_thresholds(tenant.settings, framework)

    # Apply proposed changes
    return ThresholdResponse(
        structural_threshold=structural_threshold if structural_threshold is not None else current.structural_threshold,
        semantic_threshold=semantic_threshold if semantic_threshold is not None else current.semantic_threshold,
        loop_detection_window=loop_detection_window if loop_detection_window is not None else current.loop_detection_window,
        min_matches_for_loop=min_matches_for_loop if min_matches_for_loop is not None else current.min_matches_for_loop,
        confidence_scaling=confidence_scaling if confidence_scaling is not None else current.confidence_scaling,
    )
