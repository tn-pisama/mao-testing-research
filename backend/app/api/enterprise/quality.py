"""Quality assessment API endpoints."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
import time

from fastapi import APIRouter, HTTPException, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from app.enterprise.quality import (
    QualityAssessor,
    QualityReport,
    AgentQualityScore,
    OrchestrationQualityScore,
    Severity,
)
from app.detection.quality_correlation import (
    correlate_quality_to_detections,
    get_remediation_priority,
)
from app.core.auth import get_current_tenant
from app.storage.database import get_db, set_tenant_context
from app.storage.models import WorkflowQualityAssessment, Trace, Detection, WorkflowGroup, WorkflowGroupAssignment

router = APIRouter(prefix="/enterprise/quality", tags=["quality"])


class WorkflowQualityRequest(BaseModel):
    """Request to assess workflow quality."""
    workflow_json: dict = Field(..., description="The n8n workflow JSON")
    execution_history: Optional[List[dict]] = Field(
        default=None,
        description="Optional execution history for output consistency analysis"
    )
    max_suggestions: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of improvement suggestions"
    )
    use_llm_analysis: bool = Field(
        default=False,
        description="Use LLM for ambiguous cases (Tier 3 escalation)"
    )


class WorkflowQualityResponse(BaseModel):
    """Response with workflow quality assessment."""
    workflow_id: str
    workflow_name: str
    overall_score: float
    overall_grade: str
    agent_scores: List[dict]
    orchestration_score: dict
    improvements: List[dict]
    summary: str
    total_issues: int
    critical_issues_count: int


class AgentQualityRequest(BaseModel):
    """Request to assess single agent quality."""
    node_json: dict = Field(..., description="The n8n agent node JSON")
    workflow_context: Optional[dict] = Field(
        default=None,
        description="Optional workflow context for error handling analysis"
    )
    execution_samples: Optional[List[dict]] = Field(
        default=None,
        description="Optional execution samples for output consistency"
    )


class AgentQualityResponse(BaseModel):
    """Response with agent quality assessment."""
    agent_id: str
    agent_name: str
    agent_type: str
    overall_score: float
    grade: str
    dimensions: List[dict]
    issues_count: int
    critical_issues: List[str]


class SuggestionsRequest(BaseModel):
    """Request for improvement suggestions."""
    quality_report: dict = Field(..., description="Quality report from workflow assessment")
    max_suggestions: int = Field(default=10, ge=1, le=50)
    min_severity: str = Field(default="low", description="Minimum severity: info, low, medium, high, critical")


class SuggestionsResponse(BaseModel):
    """Response with improvement suggestions."""
    suggestions: List[dict]
    count: int


@router.post("/workflow", response_model=WorkflowQualityResponse)
async def assess_workflow_quality(
    request: WorkflowQualityRequest,
    tenant=Depends(get_current_tenant),
):
    """
    Assess the quality of an n8n workflow.

    Returns comprehensive quality scores for:
    - Each agent node (role clarity, output consistency, error handling, tool usage, config)
    - Overall orchestration (data flow, complexity, coupling, observability, best practices)
    - Prioritized improvement suggestions
    """
    try:
        assessor = QualityAssessor(use_llm_judge=request.use_llm_analysis)

        report = assessor.assess_workflow(
            workflow=request.workflow_json,
            execution_history=request.execution_history,
            max_suggestions=request.max_suggestions,
        )

        return WorkflowQualityResponse(
            workflow_id=report.workflow_id,
            workflow_name=report.workflow_name,
            overall_score=round(report.overall_score, 3),
            overall_grade=report.overall_grade,
            agent_scores=[a.to_dict() for a in report.agent_scores],
            orchestration_score=report.orchestration_score.to_dict(),
            improvements=[i.to_dict() for i in report.improvements],
            summary=report.summary,
            total_issues=report.total_issues,
            critical_issues_count=report.critical_issues_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quality assessment failed: {str(e)}")


@router.post("/agent", response_model=AgentQualityResponse)
async def assess_agent_quality(
    request: AgentQualityRequest,
    tenant=Depends(get_current_tenant),
):
    """
    Assess the quality of a single agent node.

    Returns scores across 5 dimensions:
    - Role Clarity: System prompt quality
    - Output Consistency: Output structure consistency
    - Error Handling: Error coverage
    - Tool Usage: Tool integration quality
    - Config Appropriateness: Temperature/token settings
    """
    try:
        assessor = QualityAssessor()

        score = assessor.assess_agent(
            node=request.node_json,
            workflow_context=request.workflow_context,
            execution_history=request.execution_samples,
        )

        return AgentQualityResponse(
            agent_id=score.agent_id,
            agent_name=score.agent_name,
            agent_type=score.agent_type,
            overall_score=round(score.overall_score, 3),
            grade=score.grade,
            dimensions=[d.to_dict() for d in score.dimensions],
            issues_count=score.issues_count,
            critical_issues=score.critical_issues,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent assessment failed: {str(e)}")


@router.post("/suggestions", response_model=SuggestionsResponse)
async def get_improvement_suggestions(
    request: SuggestionsRequest,
    tenant=Depends(get_current_tenant),
):
    """
    Get improvement suggestions from a quality report.

    Filter by minimum severity level:
    - info: All suggestions
    - low: Low severity and above
    - medium: Medium severity and above
    - high: High and critical only
    - critical: Critical only
    """
    try:
        # Parse severity
        severity_map = {
            "info": Severity.INFO,
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }
        min_severity = severity_map.get(request.min_severity.lower(), Severity.LOW)

        # Get suggestions from the report
        suggestions = request.quality_report.get("improvements", [])

        # Filter by severity
        severity_order = ["critical", "high", "medium", "low", "info"]
        min_severity_index = severity_order.index(min_severity.value)

        filtered = [
            s for s in suggestions
            if severity_order.index(s.get("severity", "low")) <= min_severity_index
        ]

        # Limit
        filtered = filtered[:request.max_suggestions]

        return SuggestionsResponse(
            suggestions=filtered,
            count=len(filtered),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.get("/dimensions")
async def list_quality_dimensions():
    """List all quality dimensions and their descriptions."""
    return {
        "agent_dimensions": {
            "role_clarity": {
                "description": "How well the agent's role and purpose are defined in the system prompt",
                "weight": 1.0,
                "checks": ["Role keywords", "Output format", "Boundary constraints", "Prompt detail"],
            },
            "output_consistency": {
                "description": "Whether the agent produces consistent output structures",
                "weight": 1.0,
                "checks": ["Schema consistency", "Field presence", "Type consistency"],
            },
            "error_handling": {
                "description": "How well errors are handled",
                "weight": 1.0,
                "checks": ["Continue on fail", "Timeout", "Retry config", "Error paths"],
            },
            "tool_usage": {
                "description": "Quality of tool integration",
                "weight": 1.0,
                "checks": ["Tool descriptions", "Parameter schemas", "Tool count"],
            },
            "config_appropriateness": {
                "description": "Whether configuration settings are appropriate",
                "weight": 1.0,
                "checks": ["Temperature", "Max tokens", "Model selection"],
            },
        },
        "orchestration_dimensions": {
            "data_flow_clarity": {
                "description": "How explicit and clear the data flow is",
                "weight": 1.0,
                "checks": ["Connection coverage", "State manipulation", "Node naming"],
            },
            "complexity_management": {
                "description": "Whether complexity is appropriate for the task",
                "weight": 1.0,
                "checks": ["Node count", "Cyclomatic complexity", "Depth"],
            },
            "agent_coupling": {
                "description": "Balance of agent interdependence",
                "weight": 1.0,
                "checks": ["Coupling ratio", "Agent chains"],
            },
            "observability": {
                "description": "Coverage of checkpoints and monitoring",
                "weight": 1.0,
                "checks": ["Checkpoint nodes", "Error triggers", "Monitoring webhooks"],
            },
            "best_practices": {
                "description": "Adherence to best practices",
                "weight": 1.0,
                "checks": ["Retry config", "Timeout config", "Continue on fail"],
            },
        },
        "grades": {
            "Healthy":  "90-100% - System operating normally",
            "Degraded": "70-89%  - Performance below optimal",
            "At Risk":  "50-69%  - Issues require attention",
            "Critical": "0-49%   - Severe issues detected",
        },
    }


# Persistence models
class StoredAssessmentResponse(BaseModel):
    """Response for a stored quality assessment."""
    id: str
    workflow_id: Optional[str]
    workflow_name: Optional[str]
    trace_id: Optional[str]
    overall_score: int
    overall_grade: str
    agent_scores: List[dict]
    orchestration_score: dict
    improvements: List[dict]
    complexity_metrics: dict
    total_issues: int
    critical_issues_count: int
    source: str
    assessment_time_ms: Optional[int]
    summary: Optional[str]
    created_at: datetime


class AssessmentListResponse(BaseModel):
    """Response for listing assessments."""
    assessments: List[StoredAssessmentResponse]
    total: int
    page: int
    page_size: int


class AssessAndSaveRequest(BaseModel):
    """Request to assess and save workflow quality."""
    workflow_json: dict = Field(..., description="The n8n workflow JSON")
    trace_id: Optional[str] = Field(default=None, description="Optional trace ID to link assessment")
    max_suggestions: int = Field(default=10, ge=1, le=50)
    use_llm_analysis: bool = Field(default=False)


# Correlation schemas

class CorrelationRequest(BaseModel):
    """Request to correlate quality with detections."""
    trace_id: Optional[str] = Field(default=None, description="Trace ID to get detections from")
    quality_report: Optional[dict] = Field(default=None, description="Quality report dict (if not using trace_id)")
    detections: Optional[List[dict]] = Field(default=None, description="List of detection dicts (if not using trace_id)")


class QualityDetectionCorrelation(BaseModel):
    """A single quality-detection correlation."""
    detection_id: str
    detection_type: str
    detection_confidence: int
    related_quality_issues: List[dict]
    explanation: str
    severity: str


class RemediationPriority(BaseModel):
    """Prioritized remediation item."""
    dimension: str
    detection_type: str
    priority_score: float
    rationale: str
    suggested_action: str


class CorrelationResponse(BaseModel):
    """Response from correlation endpoint."""
    trace_id: Optional[str]
    correlations: List[QualityDetectionCorrelation]
    remediation_priorities: List[dict]
    summary: str


# Persistence endpoints

@router.get("/tenants/{tenant_id}/assessments", response_model=AssessmentListResponse)
async def list_assessments(
    tenant_id: UUID = Path(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    workflow_id: Optional[str] = Query(None),
    min_grade: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """List quality assessments for a tenant with pagination and filtering."""
    await set_tenant_context(db, str(tenant_id))

    # Build query
    query = select(WorkflowQualityAssessment).where(
        WorkflowQualityAssessment.tenant_id == tenant_id
    )

    if workflow_id:
        query = query.where(WorkflowQualityAssessment.workflow_id == workflow_id)

    if min_grade:
        # Tier ordering: best → worst
        grade_order = ["Healthy", "Degraded", "At Risk", "Critical"]
        if min_grade in grade_order:
            min_index = grade_order.index(min_grade)
            valid_grades = grade_order[:min_index + 1]
            query = query.where(WorkflowQualityAssessment.overall_grade.in_(valid_grades))

    if group_id:
        if group_id == "ungrouped":
            # Workflows NOT in any group
            subquery = select(WorkflowGroupAssignment.workflow_id).where(
                WorkflowGroupAssignment.group_id.in_(
                    select(WorkflowGroup.id).where(WorkflowGroup.tenant_id == tenant_id)
                )
            )
            query = query.where(WorkflowQualityAssessment.workflow_id.not_in(subquery))
        else:
            # Workflows in specific group
            subquery = select(WorkflowGroupAssignment.workflow_id).where(
                WorkflowGroupAssignment.group_id == UUID(group_id)
            )
            query = query.where(WorkflowQualityAssessment.workflow_id.in_(subquery))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(WorkflowQualityAssessment.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    assessments = result.scalars().all()

    return AssessmentListResponse(
        assessments=[
            StoredAssessmentResponse(
                id=str(a.id),
                workflow_id=a.workflow_id,
                workflow_name=a.workflow_name,
                trace_id=str(a.trace_id) if a.trace_id else None,
                overall_score=a.overall_score,
                overall_grade=a.overall_grade,
                agent_scores=a.agent_scores or [],
                orchestration_score=a.orchestration_score or {},
                improvements=a.improvements or [],
                complexity_metrics=a.complexity_metrics or {},
                total_issues=a.total_issues,
                critical_issues_count=a.critical_issues_count,
                source=a.source,
                assessment_time_ms=a.assessment_time_ms,
                summary=a.summary,
                created_at=a.created_at,
            )
            for a in assessments
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tenants/{tenant_id}/assessments/{assessment_id}", response_model=StoredAssessmentResponse)
async def get_assessment(
    tenant_id: UUID = Path(...),
    assessment_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Get a specific quality assessment by ID."""
    await set_tenant_context(db, str(tenant_id))

    result = await db.execute(
        select(WorkflowQualityAssessment).where(
            WorkflowQualityAssessment.id == assessment_id,
            WorkflowQualityAssessment.tenant_id == tenant_id,
        )
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    return StoredAssessmentResponse(
        id=str(assessment.id),
        workflow_id=assessment.workflow_id,
        workflow_name=assessment.workflow_name,
        trace_id=str(assessment.trace_id) if assessment.trace_id else None,
        overall_score=assessment.overall_score,
        overall_grade=assessment.overall_grade,
        agent_scores=assessment.agent_scores or [],
        orchestration_score=assessment.orchestration_score or {},
        improvements=assessment.improvements or [],
        complexity_metrics=assessment.complexity_metrics or {},
        total_issues=assessment.total_issues,
        critical_issues_count=assessment.critical_issues_count,
        source=assessment.source,
        assessment_time_ms=assessment.assessment_time_ms,
        summary=assessment.summary,
        created_at=assessment.created_at,
    )


@router.get("/tenants/{tenant_id}/assessments/by-trace/{trace_id}", response_model=StoredAssessmentResponse)
async def get_assessment_by_trace(
    tenant_id: UUID = Path(...),
    trace_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Get quality assessment linked to a specific trace."""
    await set_tenant_context(db, str(tenant_id))

    result = await db.execute(
        select(WorkflowQualityAssessment).where(
            WorkflowQualityAssessment.trace_id == trace_id,
            WorkflowQualityAssessment.tenant_id == tenant_id,
        ).order_by(WorkflowQualityAssessment.created_at.desc())
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found for this trace")

    return StoredAssessmentResponse(
        id=str(assessment.id),
        workflow_id=assessment.workflow_id,
        workflow_name=assessment.workflow_name,
        trace_id=str(assessment.trace_id) if assessment.trace_id else None,
        overall_score=assessment.overall_score,
        overall_grade=assessment.overall_grade,
        agent_scores=assessment.agent_scores or [],
        orchestration_score=assessment.orchestration_score or {},
        improvements=assessment.improvements or [],
        complexity_metrics=assessment.complexity_metrics or {},
        total_issues=assessment.total_issues,
        critical_issues_count=assessment.critical_issues_count,
        source=assessment.source,
        assessment_time_ms=assessment.assessment_time_ms,
        summary=assessment.summary,
        created_at=assessment.created_at,
    )


@router.post("/tenants/{tenant_id}/assess-and-save", response_model=StoredAssessmentResponse)
async def assess_and_save(
    request: AssessAndSaveRequest,
    tenant_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """
    Assess workflow quality and save the results to the database.

    This combines assessment with persistence for workflows submitted via API.
    """
    await set_tenant_context(db, str(tenant_id))

    try:
        start_time = time.time()
        assessor = QualityAssessor(use_llm_judge=request.use_llm_analysis)

        report = assessor.assess_workflow(
            workflow=request.workflow_json,
            max_suggestions=request.max_suggestions,
        )
        assessment_time_ms = int((time.time() - start_time) * 1000)

        # Create assessment record
        assessment = WorkflowQualityAssessment(
            tenant_id=tenant_id,
            trace_id=UUID(request.trace_id) if request.trace_id else None,
            workflow_id=report.workflow_id,
            workflow_name=report.workflow_name,
            overall_score=int(report.overall_score * 100),
            overall_grade=report.overall_grade,
            agent_scores=[a.to_dict() for a in report.agent_scores],
            orchestration_score=report.orchestration_score.to_dict(),
            improvements=[i.to_dict() for i in report.improvements],
            complexity_metrics=report.orchestration_score.complexity_metrics.to_dict() if report.orchestration_score.complexity_metrics else {},
            total_issues=report.total_issues,
            critical_issues_count=report.critical_issues_count,
            source="api",
            assessment_time_ms=assessment_time_ms,
            summary=report.summary,
        )
        db.add(assessment)
        await db.commit()
        await db.refresh(assessment)

        return StoredAssessmentResponse(
            id=str(assessment.id),
            workflow_id=assessment.workflow_id,
            workflow_name=assessment.workflow_name,
            trace_id=str(assessment.trace_id) if assessment.trace_id else None,
            overall_score=assessment.overall_score,
            overall_grade=assessment.overall_grade,
            agent_scores=assessment.agent_scores or [],
            orchestration_score=assessment.orchestration_score or {},
            improvements=assessment.improvements or [],
            complexity_metrics=assessment.complexity_metrics or {},
            total_issues=assessment.total_issues,
            critical_issues_count=assessment.critical_issues_count,
            source=assessment.source,
            assessment_time_ms=assessment.assessment_time_ms,
            summary=assessment.summary,
            created_at=assessment.created_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")


@router.post("/tenants/{tenant_id}/quality/correlate", response_model=CorrelationResponse)
async def correlate_quality_to_detection(
    request: CorrelationRequest,
    tenant_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """
    Correlate quality issues with detection findings.

    Input: trace_id OR (quality_report + detections)
    Output: Root cause mapping + prioritized remediation
    """
    await set_tenant_context(db, str(tenant_id))

    try:
        quality_report = request.quality_report
        detections = request.detections or []

        # If trace_id provided, fetch quality assessment and detections
        if request.trace_id:
            trace_uuid = UUID(request.trace_id)

            # Get quality assessment for this trace
            assessment_result = await db.execute(
                select(WorkflowQualityAssessment).where(
                    WorkflowQualityAssessment.trace_id == trace_uuid,
                    WorkflowQualityAssessment.tenant_id == tenant_id,
                ).order_by(WorkflowQualityAssessment.created_at.desc())
            )
            assessment = assessment_result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=404,
                    detail=f"No quality assessment found for trace {request.trace_id}"
                )

            # Build quality report dict
            quality_report = {
                "workflow_id": assessment.workflow_id,
                "workflow_name": assessment.workflow_name,
                "overall_score": assessment.overall_score / 100.0,
                "overall_grade": assessment.overall_grade,
                "agent_scores": assessment.agent_scores or [],
                "orchestration_score": assessment.orchestration_score or {},
                "improvements": assessment.improvements or [],
            }

            # Get detections for this trace
            detections_result = await db.execute(
                select(Detection).where(
                    Detection.trace_id == trace_uuid,
                    Detection.tenant_id == tenant_id,
                )
            )
            detection_objs = detections_result.scalars().all()

            detections = [
                {
                    "id": str(d.id),
                    "detection_type": d.detection_type,
                    "confidence": d.confidence,
                    "details": d.details,
                }
                for d in detection_objs
            ]

        if not quality_report:
            raise HTTPException(
                status_code=400,
                detail="Either trace_id or quality_report must be provided"
            )

        # Perform correlation
        correlation_result = correlate_quality_to_detections(
            quality_report=quality_report,
            detections=detections,
        )

        # Get remediation priorities
        remediation = get_remediation_priority(
            quality_report=quality_report,
            detections=detections,
        )

        # Convert correlations to response format
        correlations = [
            QualityDetectionCorrelation(
                detection_id=c.detection_id,
                detection_type=c.detection_type,
                detection_confidence=c.detection_confidence,
                related_quality_issues=c.related_quality_issues,
                explanation=c.explanation,
                severity=c.severity,
            )
            for c in correlation_result.correlations
        ]

        return CorrelationResponse(
            trace_id=request.trace_id,
            correlations=correlations,
            remediation_priorities=remediation,
            summary=correlation_result.summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Correlation failed: {str(e)}")
