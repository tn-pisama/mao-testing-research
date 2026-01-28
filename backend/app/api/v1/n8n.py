from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
import time
import logging
from pydantic import BaseModel, Field

from app.storage.database import get_db, set_tenant_context, async_session_maker
from app.storage.models import Trace, State, N8nWorkflow, WebhookNonce, Tenant, WorkflowQualityAssessment
from app.core.auth import get_current_tenant
from app.core.n8n_security import verify_webhook_signature, redact_sensitive_data
from app.ingestion.n8n_parser import n8n_parser
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/n8n", tags=["n8n"])


class N8nWebhookPayload(BaseModel):
    executionId: str = Field(..., min_length=1)
    workflowId: str = Field(..., min_length=1)
    workflowName: str = ""
    mode: str = "manual"
    startedAt: str
    finishedAt: Optional[str] = None
    status: str = "success"
    data: dict = Field(default_factory=dict)
    # Optional workflow definition for quality assessment
    workflow: Optional[dict] = Field(default=None, description="Full workflow JSON for quality assessment")


class N8nWebhookResponse(BaseModel):
    success: bool
    trace_id: str
    states_created: int
    message: str = "Execution received"
    quality_assessment_triggered: bool = False


class N8nWorkflowRegisterRequest(BaseModel):
    workflow_id: str = Field(..., min_length=1)
    workflow_name: Optional[str] = None


class N8nWorkflowResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: Optional[str]
    webhook_url: str
    registered_at: datetime


async def verify_nonce(nonce: str, timestamp: int, db: AsyncSession) -> bool:
    result = await db.execute(
        select(WebhookNonce).where(WebhookNonce.nonce == nonce)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Replay attack detected")

    await db.execute(
        insert(WebhookNonce).values(nonce=nonce, timestamp=timestamp)
    )
    return True


async def assess_workflow_quality_task(
    tenant_id: str,
    trace_id: str,
    workflow_json: dict,
    workflow_id: str,
    workflow_name: str,
):
    """Background task to assess workflow quality and store results."""
    try:
        from app.enterprise.quality import QualityAssessor

        start_time = time.time()
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(workflow_json, max_suggestions=10)
        assessment_time_ms = int((time.time() - start_time) * 1000)

        # Store assessment in database
        async with async_session_maker() as db:
            await set_tenant_context(db, tenant_id)

            assessment = WorkflowQualityAssessment(
                tenant_id=UUID(tenant_id),
                trace_id=UUID(trace_id),
                workflow_id=workflow_id,
                workflow_name=workflow_name or report.workflow_name,
                overall_score=int(report.overall_score * 100),
                overall_grade=report.overall_grade,
                agent_scores=[a.to_dict() for a in report.agent_scores],
                orchestration_score=report.orchestration_score.to_dict(),
                improvements=[i.to_dict() for i in report.improvements],
                complexity_metrics=report.orchestration_score.complexity_metrics.to_dict() if report.orchestration_score.complexity_metrics else {},
                total_issues=report.total_issues,
                critical_issues_count=report.critical_issues_count,
                source="webhook",
                assessment_time_ms=assessment_time_ms,
                summary=report.summary,
            )
            db.add(assessment)
            await db.commit()

            logger.info(
                f"Quality assessment completed for workflow {workflow_id}: "
                f"score={report.overall_score:.1%}, grade={report.overall_grade}, "
                f"issues={report.total_issues}"
            )
    except Exception as e:
        logger.error(f"Quality assessment failed for workflow {workflow_id}: {e}")


@router.post("/webhook", response_model=N8nWebhookResponse)
async def receive_n8n_webhook(
    request: Request,
    payload: N8nWebhookPayload,
    background_tasks: BackgroundTasks,
    x_mao_api_key: str = Header(..., alias="X-MAO-API-Key"),
    x_mao_signature: Optional[str] = Header(None, alias="X-MAO-Signature"),
    x_mao_timestamp: Optional[str] = Header(None, alias="X-MAO-Timestamp"),
    x_mao_nonce: Optional[str] = Header(None, alias="X-MAO-Nonce"),
    db: AsyncSession = Depends(get_db),
):
    from app.core.auth import verify_api_key
    
    if not x_mao_api_key.startswith("mao_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    key_prefix = x_mao_api_key[:12]
    
    from app.storage.models import ApiKey
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.revoked_at.is_(None)
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
    
    workflow_result = await db.execute(
        select(N8nWorkflow).where(
            N8nWorkflow.tenant_id == tenant.id,
            N8nWorkflow.workflow_id == payload.workflowId,
        )
    )
    workflow = workflow_result.scalar_one_or_none()
    
    if workflow and workflow.webhook_secret:
        if not x_mao_signature or not x_mao_timestamp:
            raise HTTPException(
                status_code=401,
                detail="Webhook signature required for registered workflows"
            )
        body = await request.body()
        verify_webhook_signature(body, x_mao_signature, workflow.webhook_secret, x_mao_timestamp)
        
        if x_mao_nonce:
            await verify_nonce(x_mao_nonce, int(x_mao_timestamp), db)
    
    execution = n8n_parser.parse_execution(payload.model_dump())
    states = n8n_parser.parse_to_states(execution, tenant_id)
    
    trace = Trace(
        tenant_id=tenant.id,
        session_id=execution.id,
        framework="n8n",
        status="completed" if execution.status == "success" else "error",
        created_at=execution.started_at,
        completed_at=execution.finished_at,
    )
    db.add(trace)
    await db.flush()
    
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
    
    await db.commit()

    # Trigger quality assessment if workflow definition is provided and feature is enabled
    quality_assessment_triggered = False
    settings = get_settings()
    if payload.workflow and settings.features.is_enabled("quality_assessment"):
        background_tasks.add_task(
            assess_workflow_quality_task,
            tenant_id=tenant_id,
            trace_id=str(trace.id),
            workflow_json=payload.workflow,
            workflow_id=payload.workflowId,
            workflow_name=payload.workflowName,
        )
        quality_assessment_triggered = True

    return N8nWebhookResponse(
        success=True,
        trace_id=str(trace.id),
        states_created=len(states),
        message=f"Execution {execution.id} imported successfully",
        quality_assessment_triggered=quality_assessment_triggered,
    )


@router.post("/workflows", response_model=N8nWorkflowResponse)
async def register_workflow(
    request_data: N8nWorkflowRegisterRequest,
    request: Request,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    import secrets
    webhook_secret = secrets.token_urlsafe(32)
    
    stmt = pg_insert(N8nWorkflow).values(
        tenant_id=UUID(tenant_id),
        workflow_id=request_data.workflow_id,
        workflow_name=request_data.workflow_name,
        webhook_secret=webhook_secret,
    ).on_conflict_do_update(
        constraint="uq_n8n_workflow_tenant",
        set_={"workflow_name": request_data.workflow_name},
    ).returning(N8nWorkflow)
    
    result = await db.execute(stmt)
    workflow = result.scalar_one()
    await db.commit()
    
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/n8n/webhook"
    
    return N8nWorkflowResponse(
        id=str(workflow.id),
        workflow_id=workflow.workflow_id,
        workflow_name=workflow.workflow_name,
        webhook_url=webhook_url,
        registered_at=workflow.registered_at,
    )


@router.get("/workflows", response_model=List[N8nWorkflowResponse])
async def list_workflows(
    request: Request,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)

    result = await db.execute(
        select(N8nWorkflow).where(N8nWorkflow.tenant_id == UUID(tenant_id))
    )
    workflows = result.scalars().all()

    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/n8n/webhook"

    return [
        N8nWorkflowResponse(
            id=str(w.id),
            workflow_id=w.workflow_id,
            workflow_name=w.workflow_name,
            webhook_url=webhook_url,
            registered_at=w.registered_at,
        )
        for w in workflows
    ]


class N8nSyncRequest(BaseModel):
    workflow_id: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class N8nSyncResponse(BaseModel):
    synced_count: int
    traces_created: int
    errors: List[str] = Field(default_factory=list)


class N8nSyncStatusResponse(BaseModel):
    auto_sync_enabled: bool
    sync_interval_minutes: int
    n8n_configured: bool


@router.post("/sync", response_model=N8nSyncResponse)
async def sync_n8n_executions(
    request_data: N8nSyncRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Pull recent executions from n8n cloud and store as traces.

    This provides an alternative to push-based webhooks by allowing
    the MAO platform to pull historical execution data from n8n.
    """
    import os
    from app.integrations.n8n_client import N8nApiClient, N8nApiError

    await set_tenant_context(db, tenant_id)

    n8n_host = os.getenv("N8N_HOST")
    n8n_api_key = os.getenv("N8N_API_KEY")

    if not n8n_host or not n8n_api_key:
        raise HTTPException(
            status_code=400,
            detail="n8n integration not configured. Set N8N_HOST and N8N_API_KEY environment variables."
        )

    synced_count = 0
    traces_created = 0
    errors: List[str] = []

    try:
        async with N8nApiClient(n8n_host, n8n_api_key) as client:
            executions = await client.get_executions(
                workflow_id=request_data.workflow_id,
                limit=request_data.limit,
            )

            for execution in executions:
                try:
                    # Check if we already have this execution
                    exec_id = execution.get("id", "")
                    existing = await db.execute(
                        select(Trace).where(
                            Trace.tenant_id == UUID(tenant_id),
                            Trace.session_id == str(exec_id),
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue  # Skip already imported executions

                    # Parse execution to MAO format
                    workflow_name = execution.get("workflowData", {}).get("name", "Unknown Workflow")
                    workflow_id = execution.get("workflowId", "")
                    started_at = execution.get("startedAt")
                    finished_at = execution.get("stoppedAt")
                    status = execution.get("status", "unknown")

                    # Create trace
                    trace = Trace(
                        tenant_id=UUID(tenant_id),
                        session_id=str(exec_id),
                        framework="n8n",
                        status="completed" if status == "success" else "error",
                        created_at=datetime.fromisoformat(started_at.replace("Z", "+00:00")) if started_at else datetime.utcnow(),
                        completed_at=datetime.fromisoformat(finished_at.replace("Z", "+00:00")) if finished_at else None,
                    )
                    db.add(trace)
                    await db.flush()

                    # Parse execution data to states if available
                    exec_data = execution.get("data", {})
                    result_data = exec_data.get("resultData", {})
                    run_data = result_data.get("runData", {})

                    seq = 0
                    for node_name, node_runs in run_data.items():
                        for run in node_runs:
                            state = State(
                                trace_id=trace.id,
                                tenant_id=UUID(tenant_id),
                                sequence_num=seq,
                                agent_id=node_name,
                                state_delta={
                                    "node": node_name,
                                    "startTime": run.get("startTime"),
                                    "executionTime": run.get("executionTime"),
                                },
                                state_hash=f"{exec_id}_{node_name}_{seq}",
                                latency_ms=run.get("executionTime", 0),
                            )
                            db.add(state)
                            seq += 1

                    synced_count += 1
                    traces_created += 1

                except Exception as e:
                    errors.append(f"Failed to import execution {execution.get('id', 'unknown')}: {str(e)}")
                    logger.warning(f"Failed to import n8n execution: {e}")

            await db.commit()

    except N8nApiError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch executions from n8n: {e.message}"
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )

    return N8nSyncResponse(
        synced_count=synced_count,
        traces_created=traces_created,
        errors=errors,
    )


@router.get("/sync/status", response_model=N8nSyncStatusResponse)
async def get_sync_status(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current n8n sync status and configuration.

    Returns information about auto-sync configuration, including whether
    n8n is configured, the sync interval, and if auto-sync is enabled.
    """
    import os

    await set_tenant_context(db, tenant_id)

    # Get tenant settings
    result = await db.execute(
        select(Tenant).where(Tenant.id == UUID(tenant_id))
    )
    tenant = result.scalar_one_or_none()

    settings = tenant.settings if tenant else {}

    return N8nSyncStatusResponse(
        auto_sync_enabled=settings.get("n8n_auto_sync_enabled", True),
        sync_interval_minutes=int(os.getenv("N8N_SYNC_INTERVAL_MINUTES", "5")),
        n8n_configured=bool(os.getenv("N8N_HOST") and os.getenv("N8N_API_KEY")),
    )


class DiscoverWorkflowsRequest(BaseModel):
    connection_id: str = Field(..., description="The n8n connection ID to use")


class DiscoveredWorkflow(BaseModel):
    id: str
    name: str
    active: bool
    created_at: str
    updated_at: str
    nodes_count: int


class DiscoverWorkflowsResponse(BaseModel):
    workflows: List[DiscoveredWorkflow]
    connection_name: str


@router.post("/discover", response_model=DiscoverWorkflowsResponse)
async def discover_workflows(
    request_data: DiscoverWorkflowsRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Discover workflows from a connected n8n instance.

    This endpoint fetches all workflows from the specified n8n connection
    so they can be registered for monitoring.
    """
    from app.integrations.n8n_client import N8nApiClient, N8nApiError
    from app.storage.models import N8nConnection

    await set_tenant_context(db, tenant_id)

    # Get the connection
    result = await db.execute(
        select(N8nConnection).where(
            N8nConnection.tenant_id == UUID(tenant_id),
            N8nConnection.id == UUID(request_data.connection_id),
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        async with N8nApiClient(connection.instance_url, connection.api_key) as client:
            workflows = await client.list_workflows(limit=100)

            discovered = [
                DiscoveredWorkflow(
                    id=w.get("id", ""),
                    name=w.get("name", "Unnamed Workflow"),
                    active=w.get("active", False),
                    created_at=w.get("createdAt", ""),
                    updated_at=w.get("updatedAt", ""),
                    nodes_count=len(w.get("nodes", [])),
                )
                for w in workflows
            ]

            return DiscoverWorkflowsResponse(
                workflows=discovered,
                connection_name=connection.name,
            )

    except N8nApiError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch workflows from n8n: {e.message}"
        )
