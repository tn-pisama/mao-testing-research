from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_tenant
from app.enterprise.chaos import (
    ChaosController,
    ChaosTarget,
    TargetType,
    SafetyConfig,
    BlastRadius,
)
from app.enterprise.chaos.experiments import (
    ExperimentType,
    LatencyExperiment,
    ErrorExperiment,
    ToolUnavailableExperiment,
    UncooperativeAgentExperiment,
    ContextTruncationExperiment,
)
from app.enterprise.chaos.controller import chaos_controller

router = APIRouter(prefix="/chaos", tags=["chaos"])


class ExperimentCreate(BaseModel):
    experiment_type: ExperimentType
    name: str
    probability: float = Field(default=1.0, ge=0.0, le=1.0)
    min_delay_ms: Optional[int] = None
    max_delay_ms: Optional[int] = None
    error_codes: Optional[list[int]] = None
    target_tools: Optional[list[str]] = None
    target_agents: Optional[list[str]] = None
    failure_mode: Optional[str] = None
    behaviors: Optional[list[str]] = None
    truncation_percent: Optional[float] = None


class TargetCreate(BaseModel):
    target_type: TargetType = TargetType.PERCENTAGE
    agent_names: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    tenant_ids: list[str] = Field(default_factory=list)
    percentage: float = Field(default=10.0, ge=0.0, le=100.0)
    exclude_production: bool = True


class SafetyCreate(BaseModel):
    max_blast_radius: BlastRadius = BlastRadius.SINGLE_TENANT
    max_affected_requests: int = Field(default=100, ge=1)
    max_duration_seconds: int = Field(default=300, ge=1)
    auto_abort_on_cascade: bool = True


class SessionCreate(BaseModel):
    name: str
    experiments: list[ExperimentCreate]
    target: TargetCreate
    safety: Optional[SafetyCreate] = None


class SessionResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    experiment_count: int
    target_description: str


def _create_experiment(config: ExperimentCreate):
    if config.experiment_type == ExperimentType.LATENCY:
        return LatencyExperiment(
            name=config.name,
            description=f"Latency injection",
            min_delay_ms=config.min_delay_ms or 100,
            max_delay_ms=config.max_delay_ms or 5000,
            probability=config.probability,
        )
    elif config.experiment_type == ExperimentType.ERROR:
        return ErrorExperiment(
            name=config.name,
            description="Error injection",
            error_codes=config.error_codes or [500, 502, 503],
            probability=config.probability,
        )
    elif config.experiment_type == ExperimentType.TOOL_UNAVAILABLE:
        return ToolUnavailableExperiment(
            name=config.name,
            description="Tool failure",
            target_tools=config.target_tools or [],
            failure_mode=config.failure_mode or "timeout",
            probability=config.probability,
        )
    elif config.experiment_type == ExperimentType.UNCOOPERATIVE_AGENT:
        return UncooperativeAgentExperiment(
            name=config.name,
            description="Uncooperative agent",
            target_agents=config.target_agents or [],
            behaviors=config.behaviors or ["refuse"],
            probability=config.probability,
        )
    elif config.experiment_type == ExperimentType.CONTEXT_TRUNCATION:
        return ContextTruncationExperiment(
            name=config.name,
            description="Context truncation",
            truncation_percent=config.truncation_percent or 0.5,
            probability=config.probability,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown experiment type: {config.experiment_type}",
        )


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    tenant_id: str = Depends(get_current_tenant),
):
    experiments = [_create_experiment(e) for e in data.experiments]
    
    target = ChaosTarget(
        target_type=data.target.target_type,
        agent_names=data.target.agent_names,
        tool_names=data.target.tool_names,
        tenant_ids=data.target.tenant_ids or [tenant_id],
        percentage=data.target.percentage,
        exclude_production=data.target.exclude_production,
    )
    
    safety_config = None
    if data.safety:
        safety_config = SafetyConfig(
            max_blast_radius=data.safety.max_blast_radius,
            max_affected_requests=data.safety.max_affected_requests,
            max_duration_seconds=data.safety.max_duration_seconds,
            auto_abort_on_cascade=data.safety.auto_abort_on_cascade,
        )
    
    session = chaos_controller.create_session(
        name=data.name,
        target=target,
        experiments=experiments,
        safety_config=safety_config,
    )
    
    return SessionResponse(
        id=session.id,
        name=session.name,
        status=session.status.value,
        created_at=session.created_at,
        started_at=session.started_at,
        completed_at=session.completed_at,
        experiment_count=len(session.experiments),
        target_description=target.describe(),
    )


@router.post("/sessions/{session_id}/start")
async def start_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    status_info = chaos_controller.get_session_status(session_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    session = chaos_controller.active_sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session not in pending state",
        )
    
    if not chaos_controller.start_session(session):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to start session - check safety config",
        )
    
    return {"status": "started", "session_id": session_id}


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    session = chaos_controller.stop_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active session not found",
        )
    
    return {"status": "stopped", "session_id": session_id}


@router.post("/sessions/{session_id}/abort")
async def abort_session(
    session_id: str,
    reason: str = "Manual abort",
    tenant_id: str = Depends(get_current_tenant),
):
    session = chaos_controller.abort_session(session_id, reason)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active session not found",
        )
    
    return {"status": "aborted", "session_id": session_id, "reason": reason}


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    tenant_id: str = Depends(get_current_tenant),
):
    sessions = chaos_controller.get_active_sessions()
    return [
        SessionResponse(
            id=s.id,
            name=s.name,
            status=s.status.value,
            created_at=s.created_at,
            started_at=s.started_at,
            completed_at=s.completed_at,
            experiment_count=len(s.experiments),
            target_description=s.target.describe(),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    status_info = chaos_controller.get_session_status(session_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return status_info


@router.get("/experiment-types")
async def list_experiment_types():
    return [
        {
            "type": ExperimentType.LATENCY,
            "name": "Latency Injection",
            "description": "Add artificial delay to requests",
            "params": ["min_delay_ms", "max_delay_ms"],
        },
        {
            "type": ExperimentType.ERROR,
            "name": "Error Injection",
            "description": "Return random HTTP errors",
            "params": ["error_codes"],
        },
        {
            "type": ExperimentType.TOOL_UNAVAILABLE,
            "name": "Tool Unavailable",
            "description": "Make specific tools fail",
            "params": ["target_tools", "failure_mode"],
        },
        {
            "type": ExperimentType.UNCOOPERATIVE_AGENT,
            "name": "Uncooperative Agent",
            "description": "Make agents refuse or delay",
            "params": ["target_agents", "behaviors"],
        },
        {
            "type": ExperimentType.CONTEXT_TRUNCATION,
            "name": "Context Truncation",
            "description": "Simulate context overflow",
            "params": ["truncation_percent"],
        },
    ]
