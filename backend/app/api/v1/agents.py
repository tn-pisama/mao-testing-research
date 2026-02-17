"""Agent listing endpoint — derives agents from trace state data."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_tenant
from app.storage.database import get_db, set_tenant_context
from app.storage.models import State

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentSummary(BaseModel):
    id: str
    name: str
    type: str
    status: str
    tokensUsed: int
    latencyMs: int
    stepCount: int
    errorCount: int
    lastActiveAt: str


class AgentListResponse(BaseModel):
    agents: list[AgentSummary]
    total: int


@router.get("", response_model=AgentListResponse)
async def list_agents(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List agents derived from trace state data."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        text("""
            SELECT
                agent_id,
                count(*)           AS step_count,
                sum(token_count)   AS tokens_used,
                avg(latency_ms)    AS avg_latency_ms,
                max(created_at)    AS last_active_at
            FROM states
            WHERE tenant_id = :tenant_id
            GROUP BY agent_id
            ORDER BY last_active_at DESC
        """),
        {"tenant_id": tenant_id},
    )
    rows = result.mappings().all()

    now = datetime.now(timezone.utc)
    agents = []
    for row in rows:
        last_active = row["last_active_at"]
        if last_active and last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        seconds_ago = (now - last_active).total_seconds() if last_active else 99999
        status = "running" if seconds_ago < 300 else "idle"

        agents.append(AgentSummary(
            id=row["agent_id"],
            name=row["agent_id"].replace("_", " ").title(),
            type="worker",
            status=status,
            tokensUsed=int(row["tokens_used"] or 0),
            latencyMs=int(row["avg_latency_ms"] or 0),
            stepCount=int(row["step_count"] or 0),
            errorCount=0,
            lastActiveAt=last_active.isoformat() if last_active else now.isoformat(),
        ))

    return AgentListResponse(agents=agents, total=len(agents))
