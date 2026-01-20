"""Quality assessment API endpoints."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.enterprise.quality import (
    QualityAssessor,
    QualityReport,
    AgentQualityScore,
    OrchestrationQualityScore,
    Severity,
)
from app.core.auth import get_current_tenant

router = APIRouter(prefix="/quality", tags=["quality"])


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
            "A": "90-100% - Excellent",
            "B+": "80-89% - Very Good",
            "B": "70-79% - Good",
            "C+": "60-69% - Satisfactory",
            "C": "50-59% - Needs Improvement",
            "D": "40-49% - Poor",
            "F": "0-39% - Failing",
        },
    }
