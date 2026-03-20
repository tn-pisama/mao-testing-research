"""OpenClaw integration API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging
from pydantic import BaseModel, Field

from app.storage.database import get_db, set_tenant_context
from app.storage.models import OpenClawInstance, OpenClawAgent
from app.core.auth import get_current_tenant
from app.ingestion.openclaw_parser import openclaw_parser
from app.core.redis_pubsub import publish_event
from app.config import get_settings
from app.api.v1.provider_base import (
    verify_api_key_and_get_tenant,
    verify_webhook_if_configured,
    create_trace_and_states,
    create_sse_response,
    capture_golden_candidates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/openclaw", tags=["openclaw"])


# --- Request/Response Models ---


class OpenClawWebhookPayload(BaseModel):
    """Webhook payload from OpenClaw instance."""

    session_id: str = Field(..., min_length=1)
    instance_id: str = Field(..., min_length=1)
    agent_name: str = ""
    channel: str = ""  # whatsapp, telegram, slack, discord, etc.
    channel_id: Optional[str] = None
    inbox_type: str = "dm"  # dm, group
    started_at: str
    finished_at: Optional[str] = None
    status: str = "completed"
    message_count: int = 0

    # Multi-agent context
    agents_mapping: Optional[dict] = None
    spawned_sessions: Optional[List[str]] = None

    # Session events (append-only log)
    events: List[dict] = Field(default_factory=list)

    # Security context
    elevated_mode: bool = False
    sandbox_enabled: bool = True

    # Optional OTEL trace correlation
    otel_trace_id: Optional[str] = None


class OpenClawWebhookResponse(BaseModel):
    success: bool
    trace_id: str
    states_created: int
    message: str = "Session received"


class OpenClawInstanceRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gateway_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    otel_endpoint: Optional[str] = None
    otel_enabled: bool = False
    ingestion_mode: str = Field(default="full", pattern="^(full|trace_only)$")


class OpenClawInstanceResponse(BaseModel):
    id: str
    name: str
    gateway_url: str
    otel_enabled: bool
    is_active: bool
    channels_configured: list
    ingestion_mode: str = "full"
    created_at: datetime


class OpenClawAgentRegisterRequest(BaseModel):
    instance_id: str = Field(..., min_length=1)
    agent_key: str = Field(..., min_length=1)
    agent_name: Optional[str] = None
    model: Optional[str] = None
    ingestion_mode: Optional[str] = Field(None, pattern="^(full|trace_only)$")


class OpenClawAgentResponse(BaseModel):
    id: str
    agent_key: str
    agent_name: Optional[str]
    model: Optional[str]
    monitoring_enabled: bool
    ingestion_mode: Optional[str] = None
    total_sessions: int
    total_messages: int
    registered_at: datetime


# --- Endpoints ---


@router.post("/webhook", response_model=OpenClawWebhookResponse)
async def receive_openclaw_webhook(
    request: Request,
    payload: OpenClawWebhookPayload,
    background_tasks: BackgroundTasks,
    x_mao_api_key: str = Header(..., alias="X-MAO-API-Key"),
    x_mao_signature: Optional[str] = Header(None, alias="X-MAO-Signature"),
    x_mao_timestamp: Optional[str] = Header(None, alias="X-MAO-Timestamp"),
    x_mao_nonce: Optional[str] = Header(None, alias="X-MAO-Nonce"),
    db: AsyncSession = Depends(get_db),
):
    """Receive session data from an OpenClaw instance."""
    tenant = await verify_api_key_and_get_tenant(x_mao_api_key, db)
    tenant_id = str(tenant.id)

    # Look up registered agent for signature verification and config
    agent_result = await db.execute(
        select(OpenClawAgent).where(
            OpenClawAgent.tenant_id == tenant.id,
            OpenClawAgent.agent_key == payload.agent_name,
        )
    )
    agent = agent_result.scalar_one_or_none()

    body = await request.body()
    await verify_webhook_if_configured(
        body,
        agent.webhook_secret if agent else None,
        x_mao_signature,
        x_mao_timestamp,
        x_mao_nonce,
        db,
    )

    # Resolve ingestion mode (agent override > instance default > "full")
    ingestion_mode = "full"
    if agent:
        if agent.ingestion_mode:
            ingestion_mode = agent.ingestion_mode
        else:
            instance_result = await db.execute(
                select(OpenClawInstance).where(
                    OpenClawInstance.id == agent.instance_id
                )
            )
            instance = instance_result.scalar_one_or_none()
            if instance and instance.ingestion_mode:
                ingestion_mode = instance.ingestion_mode

    # Parse session data
    session = openclaw_parser.parse_session(payload.model_dump())
    states = openclaw_parser.parse_to_states(session, tenant_id, ingestion_mode=ingestion_mode)

    # Create trace and states
    trace = await create_trace_and_states(
        tenant=tenant,
        session_id=session.session_id,
        framework="openclaw",
        status="completed" if session.status == "completed" else "error",
        created_at=session.started_at,
        completed_at=session.finished_at,
        states=states,
        db=db,
    )

    # Update agent statistics if registered
    if agent:
        agent.total_sessions = (agent.total_sessions or 0) + 1
        agent.total_messages = (agent.total_messages or 0) + payload.message_count
        agent.last_active_at = datetime.utcnow()

    await db.commit()

    # Run background framework detection
    from app.detection_enterprise.background_detect import run_background_detection
    background_tasks.add_task(
        run_background_detection,
        trace_id=str(trace.id),
        tenant_id=tenant_id,
        framework="openclaw",
        states=states,
        metadata={"session": payload.model_dump()},
    )

    # Auto-capture golden dataset candidates
    settings = get_settings()
    if settings.features.is_enabled("golden_auto_capture"):
        background_tasks.add_task(
            capture_golden_candidates,
            tenant_id=tenant_id,
            trace_id=str(trace.id),
            states=states,
            source_id=session.session_id,
            framework="openclaw",
        )

    # Publish real-time event
    await publish_event(
        f"execution:{tenant_id}",
        {
            "type": "openclaw.session.created",
            "trace_id": str(trace.id),
            "session_id": session.session_id,
            "agent_name": session.agent_name,
            "channel": session.channel,
            "status": session.status,
            "started_at": session.started_at.isoformat()
            if session.started_at
            else None,
            "finished_at": session.finished_at.isoformat()
            if session.finished_at
            else None,
        },
    )

    return OpenClawWebhookResponse(
        success=True,
        trace_id=str(trace.id),
        states_created=len(states),
        message=f"Session {session.session_id} imported successfully",
    )


@router.post("/instances", response_model=OpenClawInstanceResponse)
async def register_instance(
    request_data: OpenClawInstanceRegisterRequest,
    request: Request,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Register an OpenClaw instance for monitoring."""
    from app.core.webhook_security import hash_api_key

    await set_tenant_context(db, tenant_id)

    instance = OpenClawInstance(
        tenant_id=UUID(tenant_id),
        name=request_data.name,
        gateway_url=request_data.gateway_url,
        api_key_encrypted=hash_api_key(request_data.api_key),
        otel_endpoint=request_data.otel_endpoint,
        otel_enabled=request_data.otel_enabled,
        ingestion_mode=request_data.ingestion_mode,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    return OpenClawInstanceResponse(
        id=str(instance.id),
        name=instance.name,
        gateway_url=instance.gateway_url,
        otel_enabled=instance.otel_enabled,
        is_active=instance.is_active,
        channels_configured=instance.channels_configured or [],
        ingestion_mode=instance.ingestion_mode,
        created_at=instance.created_at,
    )


@router.get("/instances", response_model=List[OpenClawInstanceResponse])
async def list_instances(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List registered OpenClaw instances."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(OpenClawInstance).where(
            OpenClawInstance.tenant_id == UUID(tenant_id)
        )
    )
    instances = result.scalars().all()

    return [
        OpenClawInstanceResponse(
            id=str(i.id),
            name=i.name,
            gateway_url=i.gateway_url,
            otel_enabled=i.otel_enabled,
            is_active=i.is_active,
            channels_configured=i.channels_configured or [],
            ingestion_mode=i.ingestion_mode,
            created_at=i.created_at,
        )
        for i in instances
    ]


@router.post("/agents", response_model=OpenClawAgentResponse)
async def register_agent(
    request_data: OpenClawAgentRegisterRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Register an OpenClaw agent for monitoring."""
    import secrets

    await set_tenant_context(db, tenant_id)

    # Verify instance exists
    instance_result = await db.execute(
        select(OpenClawInstance).where(
            OpenClawInstance.tenant_id == UUID(tenant_id),
            OpenClawInstance.id == UUID(request_data.instance_id),
        )
    )
    instance = instance_result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    webhook_secret = secrets.token_urlsafe(32)

    stmt = (
        pg_insert(OpenClawAgent)
        .values(
            tenant_id=UUID(tenant_id),
            instance_id=UUID(request_data.instance_id),
            agent_key=request_data.agent_key,
            agent_name=request_data.agent_name,
            model=request_data.model,
            webhook_secret=webhook_secret,
            ingestion_mode=request_data.ingestion_mode,
        )
        .on_conflict_do_update(
            constraint="uq_openclaw_agent",
            set_={
                "agent_name": request_data.agent_name,
                "model": request_data.model,
                "ingestion_mode": request_data.ingestion_mode,
            },
        )
        .returning(OpenClawAgent)
    )

    result = await db.execute(stmt)
    agent = result.scalar_one()
    await db.commit()

    return OpenClawAgentResponse(
        id=str(agent.id),
        agent_key=agent.agent_key,
        agent_name=agent.agent_name,
        model=agent.model,
        monitoring_enabled=agent.monitoring_enabled,
        ingestion_mode=agent.ingestion_mode,
        total_sessions=agent.total_sessions or 0,
        total_messages=agent.total_messages or 0,
        registered_at=agent.registered_at,
    )


@router.get("/agents", response_model=List[OpenClawAgentResponse])
async def list_agents(
    instance_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List registered OpenClaw agents."""
    await set_tenant_context(db, tenant_id)

    query = select(OpenClawAgent).where(
        OpenClawAgent.tenant_id == UUID(tenant_id)
    )
    if instance_id:
        query = query.where(OpenClawAgent.instance_id == UUID(instance_id))

    result = await db.execute(query)
    agents = result.scalars().all()

    return [
        OpenClawAgentResponse(
            id=str(a.id),
            agent_key=a.agent_key,
            agent_name=a.agent_name,
            model=a.model,
            monitoring_enabled=a.monitoring_enabled,
            ingestion_mode=a.ingestion_mode,
            total_sessions=a.total_sessions or 0,
            total_messages=a.total_messages or 0,
            registered_at=a.registered_at,
        )
        for a in agents
    ]


@router.get("/stream")
async def stream_sessions(
    tenant_id: str = Depends(get_current_tenant),
):
    """SSE endpoint for real-time OpenClaw session events."""
    logger.info(f"OpenClaw SSE stream started for tenant: {tenant_id}")
    return create_sse_response(tenant_id, "OpenClaw")
