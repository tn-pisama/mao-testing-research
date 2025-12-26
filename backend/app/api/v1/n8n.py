from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Trace, State, N8nWorkflow, WebhookNonce, Tenant
from app.core.auth import get_current_tenant
from app.core.n8n_security import verify_webhook_signature, redact_sensitive_data
from app.ingestion.n8n_parser import n8n_parser

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


class N8nWebhookResponse(BaseModel):
    success: bool
    trace_id: str
    states_created: int
    message: str = "Execution received"


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


@router.post("/webhook", response_model=N8nWebhookResponse)
async def receive_n8n_webhook(
    request: Request,
    payload: N8nWebhookPayload,
    x_mao_api_key: str = Header(..., alias="X-MAO-API-Key"),
    x_mao_signature: Optional[str] = Header(None, alias="X-MAO-Signature"),
    x_mao_timestamp: Optional[str] = Header(None, alias="X-MAO-Timestamp"),
    x_mao_nonce: Optional[str] = Header(None, alias="X-MAO-Nonce"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Tenant).where(Tenant.api_key_hash == x_mao_api_key)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        from app.core.auth import hash_api_key
        hashed = hash_api_key(x_mao_api_key)
        result = await db.execute(
            select(Tenant).where(Tenant.api_key_hash == hashed)
        )
        tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    tenant_id = str(tenant.id)
    await set_tenant_context(db, tenant_id)
    
    if x_mao_signature and x_mao_timestamp:
        workflow_result = await db.execute(
            select(N8nWorkflow).where(
                N8nWorkflow.tenant_id == tenant.id,
                N8nWorkflow.workflow_id == payload.workflowId,
            )
        )
        workflow = workflow_result.scalar_one_or_none()
        
        if workflow and workflow.webhook_secret:
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
    
    return N8nWebhookResponse(
        success=True,
        trace_id=str(trace.id),
        states_created=len(states),
        message=f"Execution {execution.id} imported successfully",
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
