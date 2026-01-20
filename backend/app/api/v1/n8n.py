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
