"""LangGraph integration API endpoints."""

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
from app.storage.models import LangGraphDeployment, LangGraphAssistant
from app.core.auth import get_current_tenant
from app.ingestion.langgraph_parser import langgraph_parser
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

router = APIRouter(prefix="/langgraph", tags=["langgraph"])


# --- Request/Response Models ---


class LangGraphWebhookPayload(BaseModel):
    """Webhook payload from LangGraph deployment."""

    run_id: str = Field(..., min_length=1)
    assistant_id: str = Field(..., min_length=1)
    thread_id: str = Field(..., min_length=1)
    graph_id: str = Field(..., min_length=1)
    started_at: str
    finished_at: Optional[str] = None
    status: str = "completed"
    total_tokens: int = 0
    total_steps: int = 0
    steps: List[dict] = Field(default_factory=list)
    error: Optional[str] = None
    multitask_strategy: Optional[str] = None
    config: Optional[dict] = Field(default_factory=dict)


class LangGraphWebhookResponse(BaseModel):
    success: bool
    trace_id: str
    states_created: int
    message: str = "Graph run received"


class LangGraphDeploymentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    api_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    deployment_id: Optional[str] = None
    graph_name: Optional[str] = None
    ingestion_mode: str = Field(default="full", pattern="^(full|trace_only)$")


class LangGraphDeploymentResponse(BaseModel):
    id: str
    name: str
    api_url: str
    is_active: bool
    deployment_id: Optional[str]
    graph_name: Optional[str]
    ingestion_mode: str = "full"
    created_at: datetime


class LangGraphAssistantRegisterRequest(BaseModel):
    deployment_id: str = Field(..., min_length=1)
    assistant_id: str = Field(..., min_length=1)
    graph_id: str = Field(..., min_length=1)
    name: Optional[str] = None
    ingestion_mode: Optional[str] = Field(None, pattern="^(full|trace_only)$")


class LangGraphAssistantResponse(BaseModel):
    id: str
    assistant_id: str
    graph_id: str
    name: Optional[str]
    monitoring_enabled: bool
    ingestion_mode: Optional[str] = None
    total_runs: int
    registered_at: datetime


# --- Endpoints ---


@router.post("/webhook", response_model=LangGraphWebhookResponse)
async def receive_langgraph_webhook(
    request: Request,
    payload: LangGraphWebhookPayload,
    background_tasks: BackgroundTasks,
    x_mao_api_key: str = Header(..., alias="X-MAO-API-Key"),
    x_mao_signature: Optional[str] = Header(None, alias="X-MAO-Signature"),
    x_mao_timestamp: Optional[str] = Header(None, alias="X-MAO-Timestamp"),
    x_mao_nonce: Optional[str] = Header(None, alias="X-MAO-Nonce"),
    db: AsyncSession = Depends(get_db),
):
    """Receive graph run data from a LangGraph deployment."""
    tenant = await verify_api_key_and_get_tenant(x_mao_api_key, db)
    tenant_id = str(tenant.id)

    # Look up registered assistant for signature verification and config
    assistant_result = await db.execute(
        select(LangGraphAssistant).where(
            LangGraphAssistant.tenant_id == tenant.id,
            LangGraphAssistant.assistant_id == payload.assistant_id,
        )
    )
    assistant = assistant_result.scalar_one_or_none()

    body = await request.body()
    await verify_webhook_if_configured(
        body,
        assistant.webhook_secret if assistant else None,
        x_mao_signature,
        x_mao_timestamp,
        x_mao_nonce,
        db,
    )

    # Resolve ingestion mode (assistant override > deployment default > "full")
    ingestion_mode = "full"
    if assistant:
        if assistant.ingestion_mode:
            ingestion_mode = assistant.ingestion_mode
        else:
            deployment_result = await db.execute(
                select(LangGraphDeployment).where(
                    LangGraphDeployment.id == assistant.deployment_id
                )
            )
            deployment = deployment_result.scalar_one_or_none()
            if deployment and deployment.ingestion_mode:
                ingestion_mode = deployment.ingestion_mode

    # Parse graph run data
    run = langgraph_parser.parse_run(payload.model_dump())
    states = langgraph_parser.parse_to_states(run, tenant_id, ingestion_mode=ingestion_mode)

    # Create trace and states
    trace = await create_trace_and_states(
        tenant=tenant,
        session_id=run.run_id,
        framework="langgraph",
        status="completed" if run.status == "completed" else "error",
        created_at=run.started_at,
        completed_at=run.finished_at,
        states=states,
        db=db,
    )

    # Update assistant statistics if registered
    if assistant:
        assistant.total_runs = (assistant.total_runs or 0) + 1
        assistant.last_active_at = datetime.utcnow()

    await db.commit()

    # Run background framework detection
    from app.detection_enterprise.background_detect import run_background_detection
    background_tasks.add_task(
        run_background_detection,
        trace_id=str(trace.id),
        tenant_id=tenant_id,
        framework="langgraph",
        states=states,
        metadata={"graph_execution": payload.model_dump()},
    )

    # Auto-capture golden dataset candidates
    settings = get_settings()
    if settings.features.is_enabled("golden_auto_capture"):
        background_tasks.add_task(
            capture_golden_candidates,
            tenant_id=tenant_id,
            trace_id=str(trace.id),
            states=states,
            source_id=run.run_id,
            framework="langgraph",
        )

    # Publish real-time event
    await publish_event(
        f"execution:{tenant_id}",
        {
            "type": "langgraph.run.completed",
            "trace_id": str(trace.id),
            "run_id": run.run_id,
            "assistant_id": run.assistant_id,
            "graph_id": run.graph_id,
            "status": run.status,
            "total_steps": run.total_steps,
            "started_at": run.started_at.isoformat()
            if run.started_at
            else None,
            "finished_at": run.finished_at.isoformat()
            if run.finished_at
            else None,
        },
    )

    return LangGraphWebhookResponse(
        success=True,
        trace_id=str(trace.id),
        states_created=len(states),
        message=f"Graph run {run.run_id} imported successfully",
    )


@router.post("/deployments", response_model=LangGraphDeploymentResponse)
async def register_deployment(
    request_data: LangGraphDeploymentRegisterRequest,
    request: Request,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Register a LangGraph deployment for monitoring."""
    from app.core.webhook_security import hash_api_key

    await set_tenant_context(db, tenant_id)

    deployment = LangGraphDeployment(
        tenant_id=UUID(tenant_id),
        name=request_data.name,
        api_url=request_data.api_url,
        api_key_encrypted=hash_api_key(request_data.api_key),
        deployment_id=request_data.deployment_id,
        graph_name=request_data.graph_name,
        ingestion_mode=request_data.ingestion_mode,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    return LangGraphDeploymentResponse(
        id=str(deployment.id),
        name=deployment.name,
        api_url=deployment.api_url,
        is_active=deployment.is_active,
        deployment_id=deployment.deployment_id,
        graph_name=deployment.graph_name,
        ingestion_mode=deployment.ingestion_mode,
        created_at=deployment.created_at,
    )


@router.get("/deployments", response_model=List[LangGraphDeploymentResponse])
async def list_deployments(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List registered LangGraph deployments."""
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(LangGraphDeployment).where(
            LangGraphDeployment.tenant_id == UUID(tenant_id)
        )
    )
    deployments = result.scalars().all()

    return [
        LangGraphDeploymentResponse(
            id=str(d.id),
            name=d.name,
            api_url=d.api_url,
            is_active=d.is_active,
            deployment_id=d.deployment_id,
            graph_name=d.graph_name,
            ingestion_mode=d.ingestion_mode,
            created_at=d.created_at,
        )
        for d in deployments
    ]


@router.post("/assistants", response_model=LangGraphAssistantResponse)
async def register_assistant(
    request_data: LangGraphAssistantRegisterRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Register a LangGraph assistant for monitoring."""
    import secrets

    await set_tenant_context(db, tenant_id)

    # Verify deployment exists
    deployment_result = await db.execute(
        select(LangGraphDeployment).where(
            LangGraphDeployment.tenant_id == UUID(tenant_id),
            LangGraphDeployment.id == UUID(request_data.deployment_id),
        )
    )
    deployment = deployment_result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    webhook_secret = secrets.token_urlsafe(32)

    stmt = (
        pg_insert(LangGraphAssistant)
        .values(
            tenant_id=UUID(tenant_id),
            deployment_id=UUID(request_data.deployment_id),
            assistant_id=request_data.assistant_id,
            graph_id=request_data.graph_id,
            name=request_data.name,
            webhook_secret=webhook_secret,
            ingestion_mode=request_data.ingestion_mode,
        )
        .on_conflict_do_update(
            constraint="uq_lg_assistant",
            set_={
                "name": request_data.name,
                "graph_id": request_data.graph_id,
                "ingestion_mode": request_data.ingestion_mode,
            },
        )
        .returning(LangGraphAssistant)
    )

    result = await db.execute(stmt)
    assistant = result.scalar_one()
    await db.commit()

    return LangGraphAssistantResponse(
        id=str(assistant.id),
        assistant_id=assistant.assistant_id,
        graph_id=assistant.graph_id,
        name=assistant.name,
        monitoring_enabled=assistant.monitoring_enabled,
        ingestion_mode=assistant.ingestion_mode,
        total_runs=assistant.total_runs or 0,
        registered_at=assistant.registered_at,
    )


@router.get("/assistants", response_model=List[LangGraphAssistantResponse])
async def list_assistants(
    deployment_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List registered LangGraph assistants."""
    await set_tenant_context(db, tenant_id)

    query = select(LangGraphAssistant).where(
        LangGraphAssistant.tenant_id == UUID(tenant_id)
    )
    if deployment_id:
        query = query.where(LangGraphAssistant.deployment_id == UUID(deployment_id))

    result = await db.execute(query)
    assistants = result.scalars().all()

    return [
        LangGraphAssistantResponse(
            id=str(a.id),
            assistant_id=a.assistant_id,
            graph_id=a.graph_id,
            name=a.name,
            monitoring_enabled=a.monitoring_enabled,
            ingestion_mode=a.ingestion_mode,
            total_runs=a.total_runs or 0,
            registered_at=a.registered_at,
        )
        for a in assistants
    ]


@router.get("/stream")
async def stream_run_events(
    tenant_id: str = Depends(get_current_tenant),
):
    """SSE endpoint for real-time LangGraph run events."""
    logger.info(f"LangGraph SSE stream started for tenant: {tenant_id}")
    return create_sse_response(tenant_id, "LangGraph")
