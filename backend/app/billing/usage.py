"""Usage enforcement for billing plan limits.

Provides a FastAPI dependency that checks daily run limits before
accepting new traces. Apply to trace ingestion endpoints.
"""

import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database import get_db
from app.storage.models import Tenant, State
from app.core.auth import get_current_tenant
from app.billing.constants import get_daily_run_limit

logger = logging.getLogger(__name__)


async def enforce_daily_usage(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """FastAPI dependency that enforces daily run limits.

    Raises HTTPException 429 if tenant has exceeded their plan's daily limit.
    """
    result = await db.execute(select(Tenant.plan).where(Tenant.id == tenant_id))
    plan = result.scalar_one_or_none() or "free"

    limit = get_daily_run_limit(plan)
    if limit >= 999_999_999:
        return  # Unlimited (enterprise)

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    count_result = await db.execute(
        select(func.count(State.id))
        .where(State.tenant_id == tenant_id)
        .where(State.created_at >= today_start)
    )
    daily_runs = count_result.scalar() or 0

    if daily_runs >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily run limit ({limit}) exceeded. Upgrade your plan at /billing for more capacity.",
            headers={"Retry-After": "3600"},
        )


async def enforce_daily_usage_check(
    tenant_id: str,
    plan: str,
    db: AsyncSession,
) -> None:
    """Standalone usage check for endpoints that don't use get_current_tenant.

    Call directly when tenant/plan are already resolved (e.g., n8n webhook).
    """
    limit = get_daily_run_limit(plan)
    if limit >= 999_999_999:
        return

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    count_result = await db.execute(
        select(func.count(State.id))
        .where(State.tenant_id == tenant_id)
        .where(State.created_at >= today_start)
    )
    daily_runs = count_result.scalar() or 0

    if daily_runs >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily run limit ({limit}) exceeded. Upgrade your plan at /billing for more capacity.",
            headers={"Retry-After": "3600"},
        )
