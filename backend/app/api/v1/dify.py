"""Dify integration API endpoints."""

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
from app.storage.models import Trace, State, DifyInstance, DifyApp, WebhookNonce, Tenant
from app.core.auth import get_current_tenant
from app.core.n8n_security import verify_webhook_signature
from app.ingestion.dify_parser import dify_parser
from app.core.redis_pubsub import publish_event, subscribe_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dify", tags=["dify"])


# --- Request/Response Models ---


class DifyWebhookPayload(BaseModel):
    """Webhook payload from Dify workflow execution."""

    workflow_run_id: str = Field(..., min_length=1)
    app_id: str = Field(..., min_length=1)
    app_name: str = ""
    app_type: str = "workflow"  # chatbot, agent, workflow, chatflow
    started_at: str
    finished_at: Optional[str] = None
    status: str = "succeeded"
    total_tokens: int = 0
    total_steps: int = 0
    nodes: List[dict] = Field(default_factory=list)
    error: Optional[str] = None


class DifyWebhookResponse(BaseModel):
    success: bool
    trace_id: str
    states_created: int
    message: str = "Workflow run received"


class DifyInstanceRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    ingestion_mode: str = Field(default="full", pattern="^(full|trace_only)$")


class DifyInstanceResponse(BaseModel):
    id: str
    name: str
    base_url: str
    is_active: bool
    app_types_configured: list
    ingestion_mode: str = "full"
    created_at: datetime


class DifyAppRegisterRequest(BaseModel):
    instance_id: str = Field(..., min_length=1)
    app_id: str = Field(..., min_length=1)
    app_name: Optional[str] = None
    app_type: str = "workflow"
    ingestion_mode: Optional[str] = Field(None, pattern="^(full|trace_only)$")


class DifyAppResponse(BaseModel):
    id: str
    app_id: str
    app_name: Optional[str]
    app_type: str
    monitoring_enabled: bool
    ingestion_mode: Optional[str] = None
    total_runs: int
    total_tokens: int
    registered_at: datetime


# --- Nonce verification ---


async def verify_nonce(nonce: str, timestamp: int, db: AsyncSession) -> bool:
    result = await db.execute(
        select(WebhookNonce).where(WebhookNonce.nonce == nonce)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Replay attack detected")

    await db.execute(insert(WebhookNonce).values(nonce=nonce, timestamp=timestamp))
    return True


# --- Endpoints ---


@router.post("/webhook", response_model=DifyWebhookResponse)
async def receive_dify_webhook(
    request: Request,
    payload: DifyWebhookPayload,
    background_tasks: BackgroundTasks,
    x_mao_api_key: str = Header(..., alias="X-MAO-API-Key"),
    x_mao_signature: Optional[str] = Header(None, alias="X-MAO-Signature"),
    x_mao_timestamp: Optional[str] = Header(None, alias="X-MAO-Timestamp"),
    x_mao_nonce: Optional[str] = Header(None, alias="X-MAO-Nonce"),
    db: AsyncSession = Depends(get_db),
):
    """Receive workflow run data from a Dify instance."""
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

    # Verify webhook signature if app has a secret configured
    app_result = await db.execute(
        select(DifyApp).where(
            DifyApp.tenant_id == tenant.id,
            DifyApp.app_id == payload.app_id,
        )
    )
    app = app_result.scalar_one_or_none()

    if app and app.webhook_secret:
        if not x_mao_signature or not x_mao_timestamp:
            raise HTTPException(
                status_code=401,
                detail="Webhook signature required for registered apps",
            )
        body = await request.body()
        verify_webhook_signature(
            body, x_mao_signature, app.webhook_secret, x_mao_timestamp
        )

        if x_mao_nonce:
            await verify_nonce(x_mao_nonce, int(x_mao_timestamp), db)

    # Resolve ingestion mode (app override > instance default > "full")
    ingestion_mode = "full"
    if app:
        if app.ingestion_mode:
            ingestion_mode = app.ingestion_mode
        else:
            instance_result = await db.execute(
                select(DifyInstance).where(
                    DifyInstance.id == app.instance_id
                )
            )
            instance = instance_result.scalar_one_or_none()
            if instance and instance.ingestion_mode:
                ingestion_mode = instance.ingestion_mode

    # Parse workflow run data
    run = dify_parser.parse_workflow_run(payload.model_dump())
    states = dify_parser.parse_to_states(run, tenant_id, ingestion_mode=ingestion_mode)

    # Create trace
    trace = Trace(
        tenant_id=tenant.id,
        session_id=run.workflow_run_id,
        framework="dify",
        status="completed" if run.status == "succeeded" else "error",
        created_at=run.started_at,
        completed_at=run.finished_at,
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

    # Update app statistics if registered
    if app:
        app.total_runs = (app.total_runs or 0) + 1
        app.total_tokens = (app.total_tokens or 0) + payload.total_tokens
        app.last_active_at = datetime.utcnow()

    await db.commit()

    # Publish real-time event
    await publish_event(
        f"execution:{tenant_id}",
        {
            "type": "dify.workflow.completed",
            "trace_id": str(trace.id),
            "workflow_run_id": run.workflow_run_id,
            "app_name": run.app_name,
            "app_type": run.app_type,
            "status": run.status,
            "total_tokens": run.total_tokens,
            "total_steps": run.total_steps,
            "started_at": run.started_at.isoformat()
            if run.started_at
            else None,
            "finished_at": run.finished_at.isoformat()
            if run.finished_at
            else None,
        },
    )

    return DifyWebhookResponse(
        success=True,
        trace_id=str(trace.id),
        states_created=len(states),
        message=f"Workflow run {run.workflow_run_id} imported successfully",
    )


@router.post("/instances", response_model=DifyInstanceResponse)
async def register_instance(
    request_data: DifyInstanceRegisterRequest,
    request: Request,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Register a Dify instance for monitoring."""
    from app.core.n8n_security import encrypt_api_key

    await set_tenant_context(db, tenant_id)

    instance = DifyInstance(
        tenant_id=UUID(tenant_id),
        name=request_data.name,
        base_url=request_data.base_url,
        api_key_encrypted=encrypt_api_key(request_data.api_key),
        ingestion_mode=request_data.ingestion_mode,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    return DifyInstanceResponse(
        id=str(instance.id),
        name=instance.name,
        base_url=instance.base_url,
        is_active=instance.is_active,
        app_types_configured=instance.app_types_configured or [],
        ingestion_mode=instance.ingestion_mode,
        created_at=instance.created_at,
    )


@router.get("/instances", response_model=List[DifyInstanceResponse])
async def list_instances(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List registered Dify instances."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(DifyInstance).where(
            DifyInstance.tenant_id == UUID(tenant_id)
        )
    )
    instances = result.scalars().all()

    return [
        DifyInstanceResponse(
            id=str(i.id),
            name=i.name,
            base_url=i.base_url,
            is_active=i.is_active,
            app_types_configured=i.app_types_configured or [],
            ingestion_mode=i.ingestion_mode,
            created_at=i.created_at,
        )
        for i in instances
    ]


@router.post("/apps", response_model=DifyAppResponse)
async def register_app(
    request_data: DifyAppRegisterRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Register a Dify app for monitoring."""
    import secrets

    await set_tenant_context(db, tenant_id)

    # Verify instance exists
    instance_result = await db.execute(
        select(DifyInstance).where(
            DifyInstance.tenant_id == UUID(tenant_id),
            DifyInstance.id == UUID(request_data.instance_id),
        )
    )
    instance = instance_result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    webhook_secret = secrets.token_urlsafe(32)

    stmt = (
        pg_insert(DifyApp)
        .values(
            tenant_id=UUID(tenant_id),
            instance_id=UUID(request_data.instance_id),
            app_id=request_data.app_id,
            app_name=request_data.app_name,
            app_type=request_data.app_type,
            webhook_secret=webhook_secret,
            ingestion_mode=request_data.ingestion_mode,
        )
        .on_conflict_do_update(
            constraint="uq_dify_app",
            set_={
                "app_name": request_data.app_name,
                "app_type": request_data.app_type,
                "ingestion_mode": request_data.ingestion_mode,
            },
        )
        .returning(DifyApp)
    )

    result = await db.execute(stmt)
    app = result.scalar_one()
    await db.commit()

    return DifyAppResponse(
        id=str(app.id),
        app_id=app.app_id,
        app_name=app.app_name,
        app_type=app.app_type,
        monitoring_enabled=app.monitoring_enabled,
        ingestion_mode=app.ingestion_mode,
        total_runs=app.total_runs or 0,
        total_tokens=app.total_tokens or 0,
        registered_at=app.registered_at,
    )


@router.get("/apps", response_model=List[DifyAppResponse])
async def list_apps(
    instance_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List registered Dify apps."""
    await set_tenant_context(db, tenant_id)

    query = select(DifyApp).where(
        DifyApp.tenant_id == UUID(tenant_id)
    )
    if instance_id:
        query = query.where(DifyApp.instance_id == UUID(instance_id))

    result = await db.execute(query)
    apps = result.scalars().all()

    return [
        DifyAppResponse(
            id=str(a.id),
            app_id=a.app_id,
            app_name=a.app_name,
            app_type=a.app_type,
            monitoring_enabled=a.monitoring_enabled,
            ingestion_mode=a.ingestion_mode,
            total_runs=a.total_runs or 0,
            total_tokens=a.total_tokens or 0,
            registered_at=a.registered_at,
        )
        for a in apps
    ]


@router.get("/stream")
async def stream_workflow_events(
    tenant_id: str = Depends(get_current_tenant),
):
    """SSE endpoint for real-time Dify workflow events."""
    logger.info(f"Dify SSE stream started for tenant: {tenant_id}")

    async def event_generator():
        try:
            async for event in subscribe_events(f"execution:{tenant_id}"):
                yield event
        except Exception as e:
            logger.error(f"Error in Dify SSE stream: {e}")
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
