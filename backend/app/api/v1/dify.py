"""Dify integration API endpoints."""

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
from app.storage.models import DifyInstance, DifyApp
from app.core.auth import get_current_tenant
from app.ingestion.dify_parser import dify_parser
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
    tenant = await verify_api_key_and_get_tenant(x_mao_api_key, db)
    tenant_id = str(tenant.id)

    # Look up registered app for signature verification and config
    app_result = await db.execute(
        select(DifyApp).where(
            DifyApp.tenant_id == tenant.id,
            DifyApp.app_id == payload.app_id,
        )
    )
    app = app_result.scalar_one_or_none()

    body = await request.body()
    await verify_webhook_if_configured(
        body,
        app.webhook_secret if app else None,
        x_mao_signature,
        x_mao_timestamp,
        x_mao_nonce,
        db,
    )

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

    # Create trace and states
    trace = await create_trace_and_states(
        tenant=tenant,
        session_id=run.workflow_run_id,
        framework="dify",
        status="completed" if run.status == "succeeded" else "error",
        created_at=run.started_at,
        completed_at=run.finished_at,
        states=states,
        db=db,
    )

    # Update app statistics if registered
    if app:
        app.total_runs = (app.total_runs or 0) + 1
        app.total_tokens = (app.total_tokens or 0) + payload.total_tokens
        app.last_active_at = datetime.utcnow()

    await db.commit()

    # Auto-capture golden dataset candidates
    settings = get_settings()
    if settings.features.is_enabled("golden_auto_capture"):
        background_tasks.add_task(
            capture_golden_candidates,
            tenant_id=tenant_id,
            trace_id=str(trace.id),
            states=states,
            source_id=run.workflow_run_id,
            framework="dify",
        )

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
    from app.core.webhook_security import encrypt_api_key

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
    return create_sse_response(tenant_id, "Dify")
