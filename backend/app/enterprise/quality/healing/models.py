"""Data models for quality healing pipeline."""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import List, Dict, Any, Optional
import uuid


class QualityHealingStatus(str, Enum):
    """Status of a quality healing operation."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    APPLYING = "applying"
    VALIDATING = "validating"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class QualityFixCategory(str, Enum):
    """Quality dimensions that can be fixed."""
    # Agent dimensions
    ROLE_CLARITY = "role_clarity"
    OUTPUT_CONSISTENCY = "output_consistency"
    ERROR_HANDLING = "error_handling"
    TOOL_USAGE = "tool_usage"
    CONFIG_APPROPRIATENESS = "config_appropriateness"
    # Orchestration dimensions
    DATA_FLOW_CLARITY = "data_flow_clarity"
    COMPLEXITY_MANAGEMENT = "complexity_management"
    AGENT_COUPLING = "agent_coupling"
    OBSERVABILITY = "observability"
    BEST_PRACTICES = "best_practices"
    DOCUMENTATION_QUALITY = "documentation_quality"
    AI_ARCHITECTURE = "ai_architecture"
    MAINTENANCE_QUALITY = "maintenance_quality"
    TEST_COVERAGE = "test_coverage"
    LAYOUT_QUALITY = "layout_quality"


@dataclass
class QualityFixSuggestion:
    """A concrete fix for a quality dimension."""
    id: str
    dimension: str
    category: QualityFixCategory
    title: str
    description: str
    confidence: float
    expected_improvement: float
    target_type: str  # "agent" or "orchestration"
    target_id: str
    changes: Dict[str, Any]
    code_example: Optional[str] = None
    breaking_changes: bool = False
    effort: str = "low"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        dimension: str,
        category: QualityFixCategory,
        title: str,
        description: str,
        confidence: float,
        expected_improvement: float,
        target_type: str,
        target_id: str,
        changes: Dict[str, Any],
        **kwargs,
    ) -> "QualityFixSuggestion":
        return cls(
            id=f"qfix_{uuid.uuid4().hex[:12]}",
            dimension=dimension,
            category=category,
            title=title,
            description=description,
            confidence=confidence,
            expected_improvement=expected_improvement,
            target_type=target_type,
            target_id=target_id,
            changes=changes,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dimension": self.dimension,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "expected_improvement": round(self.expected_improvement, 3),
            "target_type": self.target_type,
            "target_id": self.target_id,
            "changes": self.changes,
            "code_example": self.code_example,
            "breaking_changes": self.breaking_changes,
            "effort": self.effort,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityFixSuggestion":
        """Reconstruct a QualityFixSuggestion from a dict (e.g. stored in metadata)."""
        return cls(
            id=data["id"],
            dimension=data["dimension"],
            category=QualityFixCategory(data["category"]),
            title=data["title"],
            description=data["description"],
            confidence=data["confidence"],
            expected_improvement=data["expected_improvement"],
            target_type=data["target_type"],
            target_id=data["target_id"],
            changes=data["changes"],
            code_example=data.get("code_example"),
            breaking_changes=data.get("breaking_changes", False),
            effort=data.get("effort", "low"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class QualityAppliedFix:
    """Record of a fix that was applied."""
    fix_id: str
    dimension: str
    applied_at: datetime
    target_component: str
    original_state: Dict[str, Any]
    modified_state: Dict[str, Any]
    rollback_available: bool = True
    generation_method: str = "heuristic"  # "heuristic" or "llm"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fix_id": self.fix_id,
            "dimension": self.dimension,
            "applied_at": self.applied_at.isoformat(),
            "target_component": self.target_component,
            "rollback_available": self.rollback_available,
            "generation_method": self.generation_method,
        }


@dataclass
class QualityValidationResult:
    """Result of quality re-assessment after fix."""
    success: bool
    dimension: str
    before_score: float
    after_score: float
    improvement: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "dimension": self.dimension,
            "before_score": round(self.before_score, 3),
            "after_score": round(self.after_score, 3),
            "improvement": round(self.improvement, 3),
            "details": self.details,
        }


@dataclass
class QualityHealingResult:
    """Complete result of a quality healing operation."""
    id: str
    assessment_id: str
    status: QualityHealingStatus
    started_at: datetime
    completed_at: Optional[datetime]
    dimensions_targeted: List[str]
    applied_fixes: List[QualityAppliedFix]
    validation_results: List[QualityValidationResult]
    before_score: float
    after_score: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        assessment_id: str,
        before_score: float,
        dimensions_targeted: Optional[List[str]] = None,
    ) -> "QualityHealingResult":
        return cls(
            id=f"qheal_{uuid.uuid4().hex[:12]}",
            assessment_id=assessment_id,
            status=QualityHealingStatus.ANALYZING,
            started_at=datetime.now(UTC),
            completed_at=None,
            dimensions_targeted=dimensions_targeted or [],
            applied_fixes=[],
            validation_results=[],
            before_score=before_score,
        )

    @property
    def is_successful(self) -> bool:
        return self.status in (QualityHealingStatus.SUCCESS, QualityHealingStatus.PARTIAL_SUCCESS)

    @property
    def score_improvement(self) -> Optional[float]:
        if self.after_score is not None:
            return self.after_score - self.before_score
        return None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "assessment_id": self.assessment_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "dimensions_targeted": self.dimensions_targeted,
            "applied_fixes": [f.to_dict() for f in self.applied_fixes],
            "validation_results": [v.to_dict() for v in self.validation_results],
            "before_score": round(self.before_score, 3),
            "after_score": round(self.after_score, 3) if self.after_score is not None else None,
            "is_successful": self.is_successful,
            "score_improvement": round(self.score_improvement, 3) if self.score_improvement is not None else None,
            "metadata": self.metadata,
        }
        if self.error:
            result["error"] = self.error
        return result
