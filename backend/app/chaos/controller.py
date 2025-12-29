import logging
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from .experiments import (
    ChaosExperiment,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
    LatencyExperiment,
    ErrorExperiment,
    MalformedOutputExperiment,
    ToolUnavailableExperiment,
    UncooperativeAgentExperiment,
    ContextTruncationExperiment,
)
from .targeting import ChaosTarget, TargetType
from .safety import SafetyConfig, SafetyMonitor, BlastRadius, DEFAULT_SAFETY_CONFIG

logger = logging.getLogger(__name__)


class ChaosSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    experiments: list[ChaosExperiment] = Field(default_factory=list)
    target: ChaosTarget
    safety_config: SafetyConfig = Field(default_factory=lambda: DEFAULT_SAFETY_CONFIG)
    status: ExperimentStatus = ExperimentStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: list[ExperimentResult] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class ChaosController:
    def __init__(self, safety_config: Optional[SafetyConfig] = None):
        self.safety_config = safety_config or DEFAULT_SAFETY_CONFIG
        self.active_sessions: dict[str, ChaosSession] = {}
        self.safety_monitors: dict[str, SafetyMonitor] = {}
        self.session_history: list[ChaosSession] = []

    def create_session(
        self,
        name: str,
        target: ChaosTarget,
        experiments: list[ChaosExperiment],
        safety_config: Optional[SafetyConfig] = None,
    ) -> ChaosSession:
        session = ChaosSession(
            name=name,
            target=target,
            experiments=experiments,
            safety_config=safety_config or self.safety_config,
        )
        return session

    def start_session(self, session: ChaosSession) -> bool:
        if session.id in self.active_sessions:
            logger.warning(f"Session {session.id} already active")
            return False

        monitor = SafetyMonitor(session.safety_config)
        
        blast_radius = self._determine_blast_radius(session.target)
        if not monitor.check_blast_radius(blast_radius):
            session.status = ExperimentStatus.FAILED
            return False

        monitor.start()
        self.safety_monitors[session.id] = monitor
        self.active_sessions[session.id] = session
        
        session.status = ExperimentStatus.RUNNING
        session.started_at = datetime.utcnow()
        
        logger.info(f"Started chaos session: {session.name} ({session.id})")
        return True

    def stop_session(self, session_id: str) -> Optional[ChaosSession]:
        session = self.active_sessions.pop(session_id, None)
        if session:
            session.status = ExperimentStatus.COMPLETED
            session.completed_at = datetime.utcnow()
            self.session_history.append(session)
            self.safety_monitors.pop(session_id, None)
            logger.info(f"Stopped chaos session: {session.name} ({session_id})")
        return session

    def abort_session(self, session_id: str, reason: str) -> Optional[ChaosSession]:
        session = self.active_sessions.pop(session_id, None)
        if session:
            session.status = ExperimentStatus.ABORTED
            session.completed_at = datetime.utcnow()
            self.session_history.append(session)
            monitor = self.safety_monitors.pop(session_id, None)
            if monitor:
                monitor._abort(reason)
            logger.warning(f"Aborted chaos session: {session.name} - {reason}")
        return session

    async def apply_chaos(
        self,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        applied_experiments: list[str] = []
        
        for session_id, session in list(self.active_sessions.items()):
            monitor = self.safety_monitors.get(session_id)
            if not monitor or not monitor.is_safe_to_continue():
                self.abort_session(session_id, monitor.abort_reason if monitor else "Unknown")
                continue

            if not session.target.matches(context):
                continue

            tenant_id = context.get("tenant_id", "unknown")
            if not monitor.record_affected(tenant_id):
                self.abort_session(session_id, monitor.abort_reason or "Safety limit exceeded")
                continue

            for experiment in session.experiments:
                if not experiment.should_trigger():
                    continue

                try:
                    context = await experiment.apply(context)
                    applied_experiments.append(
                        f"{experiment.experiment_type.value}:{experiment.id}"
                    )
                    
                    if context.get("chaos_error"):
                        monitor.record_cascade()

                except Exception as e:
                    logger.error(f"Chaos experiment failed: {e}")
                    monitor.record_cascade()

        return context, applied_experiments

    def get_active_sessions(self) -> list[ChaosSession]:
        return list(self.active_sessions.values())

    def get_session_status(self, session_id: str) -> Optional[dict]:
        session = self.active_sessions.get(session_id)
        if not session:
            for hist in self.session_history:
                if hist.id == session_id:
                    return {
                        "session": hist.dict(),
                        "safety": None,
                    }
            return None

        monitor = self.safety_monitors.get(session_id)
        return {
            "session": session.dict(),
            "safety": monitor.get_status() if monitor else None,
        }

    def _determine_blast_radius(self, target: ChaosTarget) -> BlastRadius:
        if target.target_type == TargetType.ALL:
            if target.percentage < 1:
                return BlastRadius.SINGLE_REQUEST
            return BlastRadius.MULTI_TENANT
        
        if target.target_type == TargetType.TRACE:
            return BlastRadius.SINGLE_TRACE
        
        if target.target_type == TargetType.AGENT:
            return BlastRadius.SINGLE_AGENT
        
        if target.target_type == TargetType.TENANT:
            if len(target.tenant_ids) > 1:
                return BlastRadius.MULTI_TENANT
            return BlastRadius.SINGLE_TENANT
        
        if target.target_type == TargetType.PERCENTAGE:
            if target.percentage < 10:
                return BlastRadius.SINGLE_TENANT
            return BlastRadius.MULTI_TENANT
        
        return BlastRadius.SINGLE_TENANT


chaos_controller = ChaosController()


def create_latency_experiment(
    name: str,
    min_delay_ms: int = 100,
    max_delay_ms: int = 5000,
    probability: float = 1.0,
) -> LatencyExperiment:
    return LatencyExperiment(
        name=name,
        description=f"Inject {min_delay_ms}-{max_delay_ms}ms latency",
        min_delay_ms=min_delay_ms,
        max_delay_ms=max_delay_ms,
        probability=probability,
    )


def create_error_experiment(
    name: str,
    error_codes: Optional[list[int]] = None,
    probability: float = 1.0,
) -> ErrorExperiment:
    return ErrorExperiment(
        name=name,
        description="Inject random errors",
        error_codes=error_codes or [500, 502, 503],
        probability=probability,
    )


def create_tool_failure_experiment(
    name: str,
    tools: list[str],
    failure_mode: str = "timeout",
    probability: float = 1.0,
) -> ToolUnavailableExperiment:
    return ToolUnavailableExperiment(
        name=name,
        description=f"Make tools {tools} fail with {failure_mode}",
        target_tools=tools,
        failure_mode=failure_mode,
        probability=probability,
    )


def create_uncooperative_agent_experiment(
    name: str,
    agents: list[str],
    behaviors: Optional[list[str]] = None,
    probability: float = 1.0,
) -> UncooperativeAgentExperiment:
    return UncooperativeAgentExperiment(
        name=name,
        description=f"Make agents {agents} uncooperative",
        target_agents=agents,
        behaviors=behaviors or ["refuse", "delay"],
        probability=probability,
    )
