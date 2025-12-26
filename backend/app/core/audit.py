from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import AuthAudit


async def log_auth_event(
    db: AsyncSession,
    tenant_id: Optional[str],
    user_id: Optional[str],
    action: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    success: bool,
    error_code: Optional[str] = None
):
    audit = AuthAudit(
        tenant_id=UUID(tenant_id) if tenant_id else None,
        user_id=UUID(user_id) if user_id else None,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        success=success,
        error_code=error_code
    )
    db.add(audit)
    await db.commit()
