"""Data models for quality assessment system."""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import List, Dict, Any, Optional
import uuid


class QualityDimension(str, Enum):
    """Agent quality dimensions."""
    ROLE_CLARITY = "role_clarity"
    OUTPUT_CONSISTENCY = "output_consistency"
    ERROR_HANDLING = "error_handling"
    TOOL_USAGE = "tool_usage"
    CONFIG_APPROPRIATENESS = "config_appropriateness"


class OrchestrationDimension(str, Enum):
    """Orchestration quality dimensions."""
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


class Severity(str, Enum):
    """Issue severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Effort(str, Enum):
    """Implementation effort levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def _score_to_grade(score: float, is_provisional: bool = False) -> str:
    """Convert 0.0-1.0 score to health tier.

    Args:
        score: Quality score between 0.0 and 1.0.
        is_provisional: When True and the label would be "Good" or
            "Needs Attention", returns "Needs Data" instead.
    """
    if score >= 0.90:
        label = "Healthy"
    elif score >= 0.80:
        label = "Good"
    elif score >= 0.70:
        label = "Needs Attention"
    elif score >= 0.50:
        label = "At Risk"
    else:
        label = "Critical"
    if is_provisional and label in ("Good", "Needs Attention"):
        return "Needs Data"
    return label


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""
    dimension: str
    score: float  # 0.0 to 1.0
    weight: float = 1.0
    issues: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    reasoning: Optional[str] = None
    is_provisional: bool = False

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "dimension": self.dimension,
            "score": round(self.score, 3),
            "weight": self.weight,
            "issues": self.issues,
            "evidence": self.evidence,
            "suggestions": self.suggestions,
        }
        if self.reasoning is not None:
            result["reasoning"] = self.reasoning
        if self.is_provisional:
            result["is_provisional"] = True
        return result


@dataclass
class AgentQualityScore:
    """Quality score for an individual agent."""
    agent_id: str
    agent_name: str
    agent_type: str
    overall_score: float
    dimensions: List[DimensionScore]
    issues_count: int = 0
    critical_issues: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reasoning: Optional[str] = None

    @property
    def has_provisional_dimensions(self) -> bool:
        return any(d.is_provisional for d in self.dimensions)

    @property
    def grade(self) -> str:
        return _score_to_grade(self.overall_score, is_provisional=self.has_provisional_dimensions)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "overall_score": round(self.overall_score, 3),
            "grade": self.grade,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "issues_count": self.issues_count,
            "critical_issues": self.critical_issues,
            "metadata": self.metadata,
        }
        if self.reasoning is not None:
            result["reasoning"] = self.reasoning
        if self.has_provisional_dimensions:
            result["is_provisional"] = True
        return result


@dataclass
class ComplexityMetrics:
    """Workflow complexity metrics."""
    node_count: int = 0
    agent_count: int = 0
    connection_count: int = 0
    max_depth: int = 0
    cyclomatic_complexity: int = 0
    coupling_ratio: float = 0.0
    ai_node_ratio: float = 0.0
    parallel_branches: int = 0
    conditional_branches: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_count": self.node_count,
            "agent_count": self.agent_count,
            "connection_count": self.connection_count,
            "max_depth": self.max_depth,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "coupling_ratio": round(self.coupling_ratio, 3),
            "ai_node_ratio": round(self.ai_node_ratio, 3),
            "parallel_branches": self.parallel_branches,
            "conditional_branches": self.conditional_branches,
        }


@dataclass
class OrchestrationQualityScore:
    """Quality score for workflow orchestration."""
    workflow_id: str
    workflow_name: str
    overall_score: float
    dimensions: List[DimensionScore]
    complexity_metrics: ComplexityMetrics
    issues_count: int = 0
    critical_issues: List[str] = field(default_factory=list)
    detected_pattern: str = "unknown"
    reasoning: Optional[str] = None

    @property
    def grade(self) -> str:
        return _score_to_grade(self.overall_score)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "overall_score": round(self.overall_score, 3),
            "grade": self.grade,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "complexity_metrics": self.complexity_metrics.to_dict(),
            "issues_count": self.issues_count,
            "critical_issues": self.critical_issues,
            "detected_pattern": self.detected_pattern,
        }
        if self.reasoning is not None:
            result["reasoning"] = self.reasoning
        return result


@dataclass
class QualityImprovement:
    """A suggested improvement for quality issues."""
    id: str
    target_type: str  # "agent" or "orchestration"
    target_id: str
    severity: Severity
    category: str
    title: str
    description: str
    rationale: str
    suggested_change: Optional[str] = None
    code_example: Optional[str] = None
    estimated_impact: str = ""
    effort: Effort = Effort.MEDIUM

    @classmethod
    def create(
        cls,
        target_type: str,
        target_id: str,
        severity: Severity,
        category: str,
        title: str,
        description: str,
        rationale: str,
        **kwargs,
    ) -> "QualityImprovement":
        return cls(
            id=f"imp_{uuid.uuid4().hex[:12]}",
            target_type=target_type,
            target_id=target_id,
            severity=severity,
            category=category,
            title=title,
            description=description,
            rationale=rationale,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "severity": self.severity.value,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "suggested_change": self.suggested_change,
            "code_example": self.code_example,
            "estimated_impact": self.estimated_impact,
            "effort": self.effort.value,
        }


@dataclass
class QualityReport:
    """Complete quality assessment report."""
    workflow_id: str
    workflow_name: str
    overall_score: float
    agent_scores: List[AgentQualityScore]
    orchestration_score: OrchestrationQualityScore
    improvements: List[QualityImprovement]
    summary: str = ""
    reasoning: Optional[str] = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_provisional(self) -> bool:
        return any(a.has_provisional_dimensions for a in self.agent_scores)

    @property
    def overall_grade(self) -> str:
        return _score_to_grade(self.overall_score, is_provisional=self.is_provisional)

    @property
    def total_issues(self) -> int:
        agent_issues = sum(a.issues_count for a in self.agent_scores)
        return agent_issues + self.orchestration_score.issues_count

    @property
    def critical_issues_count(self) -> int:
        agent_critical = sum(len(a.critical_issues) for a in self.agent_scores)
        return agent_critical + len(self.orchestration_score.critical_issues)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "overall_score": round(self.overall_score, 3),
            "overall_grade": self.overall_grade,
            "agent_scores": [a.to_dict() for a in self.agent_scores],
            "orchestration_score": self.orchestration_score.to_dict(),
            "improvements": [i.to_dict() for i in self.improvements],
            "summary": self.summary,
            "total_issues": self.total_issues,
            "critical_issues_count": self.critical_issues_count,
            "generated_at": self.generated_at.isoformat(),
        }
        if self.reasoning is not None:
            result["reasoning"] = self.reasoning
        if self.is_provisional:
            result["is_provisional"] = True
            result["confidence_note"] = (
                "Score includes provisional output_consistency estimate. "
                "Run 3+ executions and re-assess for a verified score."
            )
        return result
