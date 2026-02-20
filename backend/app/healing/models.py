"""Data models for self-healing system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class HealingStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING_FIX = "generating_fix"
    APPLYING_FIX = "applying_fix"
    VALIDATING = "validating"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    ROLLBACK = "rollback"


class FailureCategory(Enum):
    INFINITE_LOOP = "infinite_loop"
    STATE_CORRUPTION = "state_corruption"
    PERSONA_DRIFT = "persona_drift"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    COORDINATION_DEADLOCK = "coordination_deadlock"
    MEMORY_OVERFLOW = "memory_overflow"
    API_FAILURE = "api_failure"
    HALLUCINATION = "hallucination"
    INJECTION = "injection"
    CONTEXT_OVERFLOW = "context_overflow"
    TASK_DERAILMENT = "task_derailment"
    CONTEXT_NEGLECT = "context_neglect"
    COMMUNICATION_BREAKDOWN = "communication_breakdown"
    SPECIFICATION_MISMATCH = "specification_mismatch"
    POOR_DECOMPOSITION = "poor_decomposition"
    FLAWED_WORKFLOW = "flawed_workflow"
    INFORMATION_WITHHOLDING = "information_withholding"
    COMPLETION_MISJUDGMENT = "completion_misjudgment"
    COST_OVERRUN = "cost_overrun"


@dataclass
class FailureSignature:
    category: FailureCategory
    pattern: str
    confidence: float
    indicators: List[str]
    root_cause: Optional[str] = None
    affected_components: List[str] = field(default_factory=list)


@dataclass
class AppliedFix:
    fix_id: str
    fix_type: str
    applied_at: datetime
    target_component: str
    original_state: Dict[str, Any]
    modified_state: Dict[str, Any]
    rollback_available: bool = True


@dataclass
class ValidationResult:
    success: bool
    validation_type: str
    details: Dict[str, Any]
    error_message: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class HealingResult:
    id: str
    detection_id: str
    status: HealingStatus
    started_at: datetime
    completed_at: Optional[datetime]
    failure_signature: Optional[FailureSignature]
    applied_fixes: List[AppliedFix]
    validation_results: List[ValidationResult]
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "detection_id": self.detection_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failure_signature": {
                "category": self.failure_signature.category.value,
                "pattern": self.failure_signature.pattern,
                "confidence": self.failure_signature.confidence,
                "indicators": self.failure_signature.indicators,
                "root_cause": self.failure_signature.root_cause,
                "affected_components": self.failure_signature.affected_components,
            } if self.failure_signature else None,
            "applied_fixes": [
                {
                    "fix_id": f.fix_id,
                    "fix_type": f.fix_type,
                    "applied_at": f.applied_at.isoformat(),
                    "target_component": f.target_component,
                    "rollback_available": f.rollback_available,
                }
                for f in self.applied_fixes
            ],
            "validation_results": [
                {
                    "success": v.success,
                    "validation_type": v.validation_type,
                    "details": v.details,
                    "error_message": v.error_message,
                    "metrics": v.metrics,
                }
                for v in self.validation_results
            ],
            "error": self.error,
            "metadata": self.metadata,
        }
    
    @property
    def is_successful(self) -> bool:
        return self.status in (HealingStatus.SUCCESS, HealingStatus.PARTIAL_SUCCESS)
    
    @property
    def all_validations_passed(self) -> bool:
        return all(v.success for v in self.validation_results)
