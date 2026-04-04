from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.storage.database import get_db, set_tenant_context
from app.storage.models import (
    WorkflowGroup,
    UserGroupPreference,
    WorkflowGroupAssignment,
    WorkflowQualityAssessment,
)
from app.core.auth import get_verified_tenant
from app.core.dependencies import AuthContext, get_current_user_or_tenant

router = APIRouter(prefix="/workflow-groups", tags=["workflow-groups"])


# Pydantic Schemas
class AutoDetectRule(BaseModel):
    type: str = Field(..., description="Rule type: workflow_name_pattern, source, complexity_level, grade, etc.")
    pattern: Optional[str] = None
    value: Optional[str | int | bool] = None
    values: Optional[List[str]] = None
    operator: Optional[str] = Field(None, description="Comparison operator: >=, <=, =, >, <")
    case_sensitive: Optional[bool] = False


class AutoDetectRules(BaseModel):
    rules: List[AutoDetectRule]
    match_mode: str = Field("all", description="'all' (AND) or 'any' (OR)")


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)
    auto_detect_rules: Optional[AutoDetectRules] = None


class UpdateGroupRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)
    auto_detect_rules: Optional[AutoDetectRules] = None


class AssignWorkflowsRequest(BaseModel):
    workflow_ids: List[str] = Field(..., min_items=1)


class WorkflowGroupResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    color: Optional[str]
    icon: Optional[str]
    is_default: bool
    auto_detect_rules: Optional[dict]
    workflow_count: int = 0
    created_at: datetime
    updated_at: datetime
    # User customizations (if applicable)
    custom_name: Optional[str] = None
    is_hidden: bool = False
    sort_order: Optional[int] = None

    class Config:
        from_attributes = True


class AutoDetectResponse(BaseModel):
    assigned_count: int
    workflow_ids: List[str]


@router.get("/", response_model=List[WorkflowGroupResponse])
async def list_groups(
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user_or_tenant),
):
    """
    List all workflow groups for current tenant.

    Returns tenant-wide groups with user-specific customizations applied.
    """
    await set_tenant_context(db, tenant_id)

    # Query workflow groups for tenant
    result = await db.execute(
        select(WorkflowGroup)
        .where(WorkflowGroup.tenant_id == UUID(tenant_id))
        .order_by(WorkflowGroup.name)
    )
    groups = result.scalars().all()

    # Load user preferences if user_id available
    user_prefs = {}
    if auth.user_id:
        prefs_result = await db.execute(
            select(UserGroupPreference).where(
                UserGroupPreference.user_id == UUID(auth.user_id)
            )
        )
        for pref in prefs_result.scalars().all():
            user_prefs[str(pref.group_id)] = pref

    # Build response with workflow counts and user customizations
    response = []
    for group in groups:
        # Count workflows in this group
        count_result = await db.execute(
            select(WorkflowGroupAssignment).where(
                WorkflowGroupAssignment.group_id == group.id
            )
        )
        workflow_count = len(count_result.scalars().all())

        # Apply user preferences
        pref = user_prefs.get(str(group.id))

        response.append(WorkflowGroupResponse(
            id=str(group.id),
            tenant_id=str(group.tenant_id),
            name=group.name,
            description=group.description,
            color=group.color,
            icon=group.icon,
            is_default=group.is_default,
            auto_detect_rules=group.auto_detect_rules,
            workflow_count=workflow_count,
            created_at=group.created_at,
            updated_at=group.updated_at,
            custom_name=pref.custom_name if pref else None,
            is_hidden=pref.is_hidden if pref else False,
            sort_order=pref.sort_order if pref else None,
        ))

    return response


@router.post("/", response_model=WorkflowGroupResponse)
async def create_group(
    data: CreateGroupRequest,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user_or_tenant),
):
    """Create a new workflow group."""
    await set_tenant_context(db, tenant_id)

    # Check if name already exists for this tenant
    existing = await db.execute(
        select(WorkflowGroup).where(
            WorkflowGroup.tenant_id == UUID(tenant_id),
            WorkflowGroup.name == data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Group name already exists")

    # Create group
    group = WorkflowGroup(
        tenant_id=UUID(tenant_id),
        name=data.name,
        description=data.description,
        color=data.color,
        icon=data.icon,
        auto_detect_rules=data.auto_detect_rules.dict() if data.auto_detect_rules else None,
        created_by=UUID(auth.user_id) if auth.user_id else None,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    return WorkflowGroupResponse(
        id=str(group.id),
        tenant_id=str(group.tenant_id),
        name=group.name,
        description=group.description,
        color=group.color,
        icon=group.icon,
        is_default=group.is_default,
        auto_detect_rules=group.auto_detect_rules,
        workflow_count=0,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.put("/{group_id}", response_model=WorkflowGroupResponse)
async def update_group(
    group_id: str,
    data: UpdateGroupRequest,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update a workflow group."""
    await set_tenant_context(db, tenant_id)

    # Get group
    result = await db.execute(
        select(WorkflowGroup).where(
            WorkflowGroup.id == UUID(group_id),
            WorkflowGroup.tenant_id == UUID(tenant_id),
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Update fields
    if data.name is not None:
        # Check name uniqueness
        existing = await db.execute(
            select(WorkflowGroup).where(
                WorkflowGroup.tenant_id == UUID(tenant_id),
                WorkflowGroup.name == data.name,
                WorkflowGroup.id != UUID(group_id),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Group name already exists")
        group.name = data.name

    if data.description is not None:
        group.description = data.description
    if data.color is not None:
        group.color = data.color
    if data.icon is not None:
        group.icon = data.icon
    if data.auto_detect_rules is not None:
        group.auto_detect_rules = data.auto_detect_rules.dict()

    await db.commit()
    await db.refresh(group)

    # Count workflows
    count_result = await db.execute(
        select(WorkflowGroupAssignment).where(
            WorkflowGroupAssignment.group_id == group.id
        )
    )
    workflow_count = len(count_result.scalars().all())

    return WorkflowGroupResponse(
        id=str(group.id),
        tenant_id=str(group.tenant_id),
        name=group.name,
        description=group.description,
        color=group.color,
        icon=group.icon,
        is_default=group.is_default,
        auto_detect_rules=group.auto_detect_rules,
        workflow_count=workflow_count,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a workflow group (cascades to assignments and preferences)."""
    await set_tenant_context(db, tenant_id)

    # Verify group exists and belongs to tenant
    result = await db.execute(
        select(WorkflowGroup).where(
            WorkflowGroup.id == UUID(group_id),
            WorkflowGroup.tenant_id == UUID(tenant_id),
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Delete group (CASCADE will handle assignments and preferences)
    await db.delete(group)
    await db.commit()

    return {"success": True, "message": "Group deleted"}


@router.post("/{group_id}/assign")
async def assign_workflows(
    group_id: str,
    data: AssignWorkflowsRequest,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user_or_tenant),
):
    """Manually assign workflows to a group."""
    await set_tenant_context(db, tenant_id)

    # Verify group exists
    result = await db.execute(
        select(WorkflowGroup).where(
            WorkflowGroup.id == UUID(group_id),
            WorkflowGroup.tenant_id == UUID(tenant_id),
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Create assignments
    for workflow_id in data.workflow_ids:
        # Upsert assignment (replace auto with manual if exists)
        stmt = pg_insert(WorkflowGroupAssignment).values(
            workflow_id=workflow_id,
            group_id=UUID(group_id),
            assignment_type="manual",
            assigned_by=UUID(auth.user_id) if auth.user_id else None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["workflow_id", "group_id"],
            set_={
                "assignment_type": "manual",
                "assigned_by": UUID(auth.user_id) if auth.user_id else None,
                "assigned_at": datetime.utcnow(),
            },
        )
        await db.execute(stmt)

    await db.commit()

    return {
        "success": True,
        "assigned_count": len(data.workflow_ids),
        "workflow_ids": data.workflow_ids,
    }


@router.post("/{group_id}/auto-detect", response_model=AutoDetectResponse)
async def run_auto_detection(
    group_id: str,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Run auto-detection for a group based on its rules."""
    await set_tenant_context(db, tenant_id)

    # Get group with rules
    result = await db.execute(
        select(WorkflowGroup).where(
            WorkflowGroup.id == UUID(group_id),
            WorkflowGroup.tenant_id == UUID(tenant_id),
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if not group.auto_detect_rules or not group.auto_detect_rules.get("rules"):
        raise HTTPException(status_code=400, detail="Group has no auto-detection rules")

    # Build query to find matching workflows
    query = select(WorkflowQualityAssessment).where(
        WorkflowQualityAssessment.tenant_id == UUID(tenant_id),
        WorkflowQualityAssessment.workflow_id.isnot(None),
    )

    # Apply rules
    rules = group.auto_detect_rules["rules"]
    match_mode = group.auto_detect_rules.get("match_mode", "all")

    for rule in rules:
        rule_type = rule["type"]

        if rule_type == "workflow_name_pattern":
            # Use PostgreSQL SIMILAR TO for pattern matching
            pattern = rule.get("pattern", "")
            if rule.get("case_sensitive", False):
                query = query.where(WorkflowQualityAssessment.workflow_name.op("~")(pattern))
            else:
                query = query.where(WorkflowQualityAssessment.workflow_name.op("~*")(pattern))

        elif rule_type == "source":
            value = rule.get("value")
            query = query.where(WorkflowQualityAssessment.source == value)

        elif rule_type == "grade":
            values = rule.get("values", [])
            query = query.where(WorkflowQualityAssessment.overall_grade.in_(values))

        elif rule_type == "complexity_level":
            # Compare complexity from JSONB field
            operator = rule.get("operator", ">=")
            value = rule.get("value", 5)
            # This is simplified - would need proper JSONB path extraction
            # For now, we'll skip complexity-based filtering
            pass

    # Execute query
    result = await db.execute(query)
    matching_assessments = result.scalars().all()

    # Create auto-assignments
    workflow_ids = []
    for assessment in matching_assessments:
        workflow_id = assessment.workflow_id
        if not workflow_id:
            continue

        # Upsert assignment (only if not manually assigned)
        stmt = pg_insert(WorkflowGroupAssignment).values(
            workflow_id=workflow_id,
            group_id=UUID(group_id),
            assignment_type="auto",
            assigned_by=None,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["workflow_id", "group_id"]
        )
        await db.execute(stmt)
        workflow_ids.append(workflow_id)

    await db.commit()

    return AutoDetectResponse(
        assigned_count=len(workflow_ids),
        workflow_ids=workflow_ids,
    )


@router.get("/{group_id}/workflows")
async def get_group_workflows(
    group_id: str,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get all workflows assigned to a group."""
    await set_tenant_context(db, tenant_id)

    # Verify group exists
    result = await db.execute(
        select(WorkflowGroup).where(
            WorkflowGroup.id == UUID(group_id),
            WorkflowGroup.tenant_id == UUID(tenant_id),
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Get assignments
    assignments_result = await db.execute(
        select(WorkflowGroupAssignment).where(
            WorkflowGroupAssignment.group_id == UUID(group_id)
        )
    )
    assignments = assignments_result.scalars().all()

    # Get quality assessments for these workflows
    workflow_ids = [a.workflow_id for a in assignments]
    if not workflow_ids:
        return []

    assessments_result = await db.execute(
        select(WorkflowQualityAssessment).where(
            WorkflowQualityAssessment.tenant_id == UUID(tenant_id),
            WorkflowQualityAssessment.workflow_id.in_(workflow_ids),
        )
    )
    assessments = assessments_result.scalars().all()

    # Build response
    return [
        {
            "id": str(a.id),
            "workflow_id": a.workflow_id,
            "workflow_name": a.workflow_name,
            "overall_score": a.overall_score,
            "overall_grade": a.overall_grade,
            "total_issues": a.total_issues,
            "critical_issues_count": a.critical_issues_count,
            "created_at": a.created_at.isoformat(),
        }
        for a in assessments
    ]
