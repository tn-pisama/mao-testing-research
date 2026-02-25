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


class FixRiskLevel(Enum):
    """Risk classification for healing fixes.

    SAFE: Config-only changes (iteration limits, timeouts). Auto-apply allowed.
    MEDIUM: Adds checks/guards that change behavior. Auto-apply with verification.
    DANGEROUS: Alters core logic (prompts, system messages). Requires approval.
    """
    SAFE = "safe"
    MEDIUM = "medium"
    DANGEROUS = "dangerous"


# Maps fix types to their risk levels.
FIX_RISK_MAP: Dict[str, "FixRiskLevel"] = {
    # SAFE: config knobs that don't alter agent behavior
    "retry_limit": FixRiskLevel.SAFE,
    "circuit_breaker": FixRiskLevel.SAFE,
    "execution_timeout": FixRiskLevel.SAFE,
    "loop_breaker": FixRiskLevel.SAFE,
    "timeout_adjustment": FixRiskLevel.SAFE,
    "budget_limiter": FixRiskLevel.SAFE,
    "cost_monitor": FixRiskLevel.SAFE,
    "checkpoint_recovery": FixRiskLevel.SAFE,
    "state_validation": FixRiskLevel.SAFE,
    # MEDIUM: adds guardrails that may restrict behavior
    "exponential_backoff": FixRiskLevel.MEDIUM,
    "context_pruning": FixRiskLevel.MEDIUM,
    "summarization": FixRiskLevel.MEDIUM,
    "window_management": FixRiskLevel.MEDIUM,
    "schema_enforcement": FixRiskLevel.MEDIUM,
    "deadlock_prevention": FixRiskLevel.MEDIUM,
    "task_decomposition": FixRiskLevel.MEDIUM,
    "subtask_validator": FixRiskLevel.MEDIUM,
    "token_optimizer": FixRiskLevel.MEDIUM,
    "state_reset": FixRiskLevel.MEDIUM,
    # DANGEROUS: alters core logic, prompts, or permissions
    "prompt_reinforcement": FixRiskLevel.DANGEROUS,
    "prompt_modification": FixRiskLevel.DANGEROUS,
    "role_boundary": FixRiskLevel.DANGEROUS,
    "input_filtering": FixRiskLevel.DANGEROUS,
    "safety_boundary": FixRiskLevel.DANGEROUS,
    "permission_gate": FixRiskLevel.DANGEROUS,
    "fact_checking": FixRiskLevel.DANGEROUS,
    "source_grounding": FixRiskLevel.DANGEROUS,
    "confidence_calibration": FixRiskLevel.DANGEROUS,
    "transparency_enforcer": FixRiskLevel.DANGEROUS,
    "completeness_check": FixRiskLevel.DANGEROUS,
    "task_anchoring": FixRiskLevel.DANGEROUS,
    "goal_tracking": FixRiskLevel.DANGEROUS,
}


def get_fix_risk_level(fix_type: str) -> "FixRiskLevel":
    """Get the risk level for a fix type. Defaults to MEDIUM if unknown."""
    return FIX_RISK_MAP.get(fix_type, FixRiskLevel.MEDIUM)


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


@dataclass
class HealingConfig:
    """Consolidated configuration for the healing pipeline.

    Centralizes all tunable thresholds that were previously hardcoded
    across verification.py, applicator.py, and auto_apply.py.
    Default values match the original hardcoded ones for backward compatibility.
    """

    # --- Verification thresholds ---
    verification_timeout: float = 60.0
    # Level 1: confidence drops to 0 on pass, or before * this factor on fail
    confidence_fail_factor: float = 0.5
    # Level 2: partial improvement factor (error but controlled)
    partial_improvement_factor: float = 0.7
    # Level 2: pass if after_confidence < before * this
    improvement_threshold: float = 0.5

    # --- Applicator defaults ---
    default_confidence_threshold: float = 0.7
    min_confidence: float = 0.6
    deviation_threshold: float = 0.3
    quality_threshold: float = 0.8
    min_quality_score: float = 0.7
    min_context_coverage: float = 0.8
    min_response_coverage: float = 0.8
    max_output_length: int = 4096
    # Context window ratios
    context_warning_ratio: float = 0.6
    context_critical_ratio: float = 0.5
    context_overflow_ratio: float = 0.4

    # --- Auto-apply (delegates to AutoApplyConfig for runtime use) ---
    max_fixes_per_hour: int = 5
    cooldown_after_rollback_seconds: int = 300
    max_consecutive_failures: int = 3
    healing_loop_threshold: int = 5
    healing_loop_window_minutes: int = 60

    def to_auto_apply_config(self) -> "AutoApplyConfig":
        """Create an AutoApplyConfig from this HealingConfig's auto-apply fields."""
        from .auto_apply import AutoApplyConfig

        return AutoApplyConfig(
            max_fixes_per_hour=self.max_fixes_per_hour,
            cooldown_after_rollback_seconds=self.cooldown_after_rollback_seconds,
            max_consecutive_failures=self.max_consecutive_failures,
            healing_loop_threshold=self.healing_loop_threshold,
            healing_loop_window_minutes=self.healing_loop_window_minutes,
        )
