import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BlastRadius(str, Enum):
    SINGLE_REQUEST = "single_request"
    SINGLE_AGENT = "single_agent"
    SINGLE_TRACE = "single_trace"
    SINGLE_TENANT = "single_tenant"
    MULTI_TENANT = "multi_tenant"


class SafetyConfig(BaseModel):
    max_blast_radius: BlastRadius = BlastRadius.SINGLE_TENANT
    max_affected_requests: int = Field(default=100, ge=1)
    max_affected_tenants: int = Field(default=1, ge=1)
    max_duration_seconds: int = Field(default=300, ge=1)
    auto_abort_on_cascade: bool = True
    cascade_threshold: int = Field(default=5, ge=1)
    require_sandbox: bool = True
    allowed_environments: list[str] = Field(
        default_factory=lambda: ["development", "staging", "sandbox"]
    )
    cooldown_seconds: int = Field(default=60, ge=0)


class SafetyMonitor:
    def __init__(self, config: SafetyConfig):
        self.config = config
        self.affected_requests: int = 0
        self.affected_tenants: set[str] = set()
        self.cascade_count: int = 0
        self.started_at: Optional[datetime] = None
        self.aborted: bool = False
        self.abort_reason: Optional[str] = None

    def start(self):
        self.started_at = datetime.utcnow()
        self.affected_requests = 0
        self.affected_tenants = set()
        self.cascade_count = 0
        self.aborted = False
        self.abort_reason = None

    def record_affected(self, tenant_id: str) -> bool:
        if self.aborted:
            return False

        self.affected_requests += 1
        self.affected_tenants.add(tenant_id)

        if self.affected_requests > self.config.max_affected_requests:
            self._abort(f"Exceeded max affected requests: {self.config.max_affected_requests}")
            return False

        if len(self.affected_tenants) > self.config.max_affected_tenants:
            self._abort(f"Exceeded max affected tenants: {self.config.max_affected_tenants}")
            return False

        if self._is_expired():
            self._abort(f"Exceeded max duration: {self.config.max_duration_seconds}s")
            return False

        return True

    def record_cascade(self) -> bool:
        if self.aborted:
            return False

        self.cascade_count += 1

        if self.config.auto_abort_on_cascade and self.cascade_count >= self.config.cascade_threshold:
            self._abort(f"Cascade detected: {self.cascade_count} failures")
            return False

        return True

    def check_environment(self, environment: str) -> bool:
        if environment not in self.config.allowed_environments:
            logger.warning(f"Chaos blocked: environment '{environment}' not allowed")
            return False
        return True

    def check_blast_radius(self, requested: BlastRadius) -> bool:
        radius_order = [
            BlastRadius.SINGLE_REQUEST,
            BlastRadius.SINGLE_AGENT,
            BlastRadius.SINGLE_TRACE,
            BlastRadius.SINGLE_TENANT,
            BlastRadius.MULTI_TENANT,
        ]
        max_idx = radius_order.index(self.config.max_blast_radius)
        requested_idx = radius_order.index(requested)

        if requested_idx > max_idx:
            logger.warning(
                f"Chaos blocked: requested radius '{requested}' exceeds max '{self.config.max_blast_radius}'"
            )
            return False
        return True

    def is_safe_to_continue(self) -> bool:
        if self.aborted:
            return False
        if self._is_expired():
            self._abort("Experiment duration expired")
            return False
        return True

    def _is_expired(self) -> bool:
        if not self.started_at:
            return False
        elapsed = datetime.utcnow() - self.started_at
        return elapsed > timedelta(seconds=self.config.max_duration_seconds)

    def _abort(self, reason: str):
        self.aborted = True
        self.abort_reason = reason
        logger.warning(f"Chaos experiment aborted: {reason}")

    def get_status(self) -> dict:
        return {
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "affected_requests": self.affected_requests,
            "affected_tenants": len(self.affected_tenants),
            "cascade_count": self.cascade_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "is_expired": self._is_expired(),
        }


DEFAULT_SAFETY_CONFIG = SafetyConfig()

STRICT_SAFETY_CONFIG = SafetyConfig(
    max_blast_radius=BlastRadius.SINGLE_REQUEST,
    max_affected_requests=10,
    max_affected_tenants=1,
    max_duration_seconds=60,
    auto_abort_on_cascade=True,
    cascade_threshold=2,
    require_sandbox=True,
    allowed_environments=["sandbox"],
)

RELAXED_SAFETY_CONFIG = SafetyConfig(
    max_blast_radius=BlastRadius.SINGLE_TENANT,
    max_affected_requests=1000,
    max_affected_tenants=5,
    max_duration_seconds=3600,
    auto_abort_on_cascade=True,
    cascade_threshold=10,
    require_sandbox=False,
    allowed_environments=["development", "staging", "sandbox", "testing"],
)
