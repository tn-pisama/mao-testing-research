"""OpenClaw integration API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from starlette.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging
from pydantic import BaseModel, Field

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Trace, State, OpenClawInstance, OpenClawAgent, WebhookNonce, Tenant
from app.core.auth import get_current_tenant
from app.core.n8n_security import verify_webhook_signature
from app.ingestion.openclaw_parser import openclaw_parser
from app.core.redis_pubsub import publish_event, subscribe_events

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


class OpenClawInstanceResponse(BaseModel):
    id: str
    name: str
    gateway_url: str
    otel_enabled: bool
    is_active: bool
    channels_configured: list
    created_at: datetime


class OpenClawAgentRegisterRequest(BaseModel):
    instance_id: str = Field(..., min_length=1)
    agent_key: str = Field(..., min_length=1)
    agent_name: Optional[str] = None
    model: Optional[str] = None


class OpenClawAgentResponse(BaseModel):
    id: str
    agent_key: str
    agent_name: Optional[str]
    model: Optional[str]
    monitoring_enabled: bool
    total_sessions: int
    total_messages: int
    registered_at: datetime


# --- Nonce verification (reused from n8n pattern) ---


async def verify_nonce(nonce: str, timestamp: int, db: AsyncSession) -> bool:
    result = await db.execute(
        select(WebhookNonce).where(WebhookNonce.nonce == nonce)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Replay attack detected")

    await db.execute(insert(WebhookNonce).values(nonce=nonce, timestamp=timestamp))
    return True


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
    from app.core.auth import verify_api_key
    from app.storage.models import ApiKey

    if not x_mao_api_key.startswith("mao_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    key_prefix = x_mao_api_key[:12]

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix, ApiKey.revoked_at.is_(None)
        )
    )
    api_key_record = result.scalar_one_or_none()

    tenant = None
    if api_key_record and verify_api_key(x_mao_api_key, api_key_record.key_hash):
        result = await db.execute(
            select(Tenant).where(Tenant.id == api_key_record.tenant_id)
        )
        tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")

    tenant_id = str(tenant.id)
    await set_tenant_context(db, tenant_id)

    # Verify webhook signature if agent has a secret configured
    agent_result = await db.execute(
        select(OpenClawAgent).where(
            OpenClawAgent.tenant_id == tenant.id,
            OpenClawAgent.agent_key == payload.agent_name,
        )
    )
    agent = agent_result.scalar_one_or_none()

    if agent and agent.webhook_secret:
        if not x_mao_signature or not x_mao_timestamp:
            raise HTTPException(
                status_code=401,
                detail="Webhook signature required for registered agents",
            )
        body = await request.body()
        verify_webhook_signature(
            body, x_mao_signature, agent.webhook_secret, x_mao_timestamp
        )

        if x_mao_nonce:
            await verify_nonce(x_mao_nonce, int(x_mao_timestamp), db)

    # Parse session data
    session = openclaw_parser.parse_session(payload.model_dump())
    states = openclaw_parser.parse_to_states(session, tenant_id)

    # Create trace
    trace = Trace(
        tenant_id=tenant.id,
        session_id=session.session_id,
        framework="openclaw",
        status="completed" if session.status == "completed" else "error",
        created_at=session.started_at,
        completed_at=session.finished_at,
    )
    db.add(trace)
    await db.flush()

    # Create state records
    for state in states:
        db_state = State(
            trace_id=trace.id,
            tenant_id=tenant.id,
            sequence_num=state.sequence_num,
            agent_id=state.agent_id,
            state_delta=state.state_delta,
            state_hash=state.state_hash,
            token_count=state.token_count,
            latency_ms=state.latency_ms,
        )
        db.add(db_state)

    # Update agent statistics if registered
    if agent:
        agent.total_sessions = (agent.total_sessions or 0) + 1
        agent.total_messages = (agent.total_messages or 0) + payload.message_count
        agent.last_active_at = datetime.utcnow()

    await db.commit()

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
    from app.core.n8n_security import encrypt_api_key

    await set_tenant_context(db, tenant_id)

    instance = OpenClawInstance(
        tenant_id=UUID(tenant_id),
        name=request_data.name,
        gateway_url=request_data.gateway_url,
        api_key_encrypted=encrypt_api_key(request_data.api_key),
        otel_endpoint=request_data.otel_endpoint,
        otel_enabled=request_data.otel_enabled,
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
        )
        .on_conflict_do_update(
            constraint="uq_openclaw_agent",
            set_={
                "agent_name": request_data.agent_name,
                "model": request_data.model,
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

    async def event_generator():
        try:
            async for event in subscribe_events(f"execution:{tenant_id}"):
                yield event
        except Exception as e:
            logger.error(f"Error in OpenClaw SSE stream: {e}")
            import json

            error_data = json.dumps(
                {"type": "error", "message": "Stream interrupted"}
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
