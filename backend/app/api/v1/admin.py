"""Admin endpoints for audit log querying."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_user_or_tenant
from app.storage.database import get_db
from app.storage.models import ApiAudit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-log")
async def list_audit_log(
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
    method: Optional[str] = Query(None, description="Filter by HTTP method (POST, PUT, DELETE)"),
    path_contains: Optional[str] = Query(None, description="Filter by path substring"),
    since: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    until: Optional[datetime] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Query API audit log entries for the current tenant."""
    conditions = [ApiAudit.tenant_id == auth.tenant_id]

    if method:
        conditions.append(ApiAudit.method == method.upper())
    if path_contains:
        conditions.append(ApiAudit.path.contains(path_contains))
    if since:
        conditions.append(ApiAudit.created_at >= since)
    if until:
        conditions.append(ApiAudit.created_at <= until)

    where = and_(*conditions)

    # Count
    count_q = select(func.count()).select_from(ApiAudit).where(where)
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch page
    q = (
        select(ApiAudit)
        .where(where)
        .order_by(ApiAudit.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": str(item.id),
                "method": item.method,
                "path": item.path,
                "status_code": item.status_code,
                "correlation_id": item.correlation_id,
                "ip_address": item.ip_address,
                "duration_ms": item.duration_ms,
                "user_id": str(item.user_id) if item.user_id else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
