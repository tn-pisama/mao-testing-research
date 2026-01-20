"""Quality-Detection Correlation Module.

Maps quality assessment issues to detection results to provide explanatory
context for why failures may be occurring.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# Mapping from detection types to related quality dimensions
# When a detection of type X occurs, check these quality dimensions for root causes
QUALITY_DETECTION_CORRELATIONS: Dict[str, List[str]] = {
    # Loop detection
    "infinite_loop": ["complexity_management", "data_flow_clarity", "best_practices"],
    "semantic_loop": ["complexity_management", "data_flow_clarity", "role_clarity"],
    "structural_loop": ["complexity_management", "data_flow_clarity"],

    # Coordination failures
    "coordination_failure": ["agent_coupling", "data_flow_clarity", "observability"],
    "deadlock": ["agent_coupling", "complexity_management", "data_flow_clarity"],

    # State issues
    "state_corruption": ["data_flow_clarity", "error_handling", "best_practices"],
    "state_drift": ["data_flow_clarity", "output_consistency"],

    # Agent behavior
    "persona_drift": ["role_clarity", "output_consistency"],
    "hallucination": ["role_clarity", "output_consistency", "config_appropriateness"],
    "task_derailment": ["role_clarity", "data_flow_clarity"],

    # Resource issues
    "cost_anomaly": ["config_appropriateness", "complexity_management"],
    "context_overflow": ["complexity_management", "config_appropriateness"],

    # Communication issues
    "communication_breakdown": ["data_flow_clarity", "agent_coupling", "observability"],

    # Injection/security
    "prompt_injection": ["role_clarity", "error_handling"],
}

# Dimension descriptions for explanations
DIMENSION_DESCRIPTIONS = {
    # Agent dimensions
    "role_clarity": "agent role and purpose definition in system prompt",
    "output_consistency": "consistency of agent output structures",
    "error_handling": "error handling and recovery configuration",
    "tool_usage": "quality of tool integration and descriptions",
    "config_appropriateness": "appropriateness of model configuration (temperature, tokens)",

    # Orchestration dimensions
    "data_flow_clarity": "clarity of data flow between nodes",
    "complexity_management": "management of workflow complexity",
    "agent_coupling": "balance of agent interdependence",
    "observability": "monitoring and checkpoint coverage",
    "best_practices": "adherence to workflow best practices",
}


@dataclass
class QualityCorrelation:
    """A correlation between a detection and quality issues."""
    detection_id: str
    detection_type: str
    detection_confidence: int
    related_quality_issues: List[Dict[str, Any]]
    explanation: str
    severity: str = "medium"


@dataclass
class CorrelationResult:
    """Result of correlating quality with detections."""
    correlations: List[QualityCorrelation] = field(default_factory=list)
    total_detections: int = 0
    correlated_detections: int = 0
    summary: str = ""


def correlate_quality_to_detections(
    quality_report: Dict[str, Any],
    detections: List[Dict[str, Any]],
    min_score_threshold: float = 0.5,
) -> CorrelationResult:
    """
    Find quality issues that may explain detections.

    Args:
        quality_report: Quality assessment report dict
        detections: List of detection dicts with id, detection_type, confidence
        min_score_threshold: Minimum score below which a dimension is flagged

    Returns:
        CorrelationResult with correlations and summary
    """
    correlations = []

    # Extract dimension scores from quality report
    all_dim_scores: Dict[str, Dict[str, Any]] = {}

    # Orchestration dimensions
    orch_score = quality_report.get("orchestration_score", {})
    for dim in orch_score.get("dimensions", []):
        dim_name = dim.get("dimension", "")
        all_dim_scores[dim_name] = {
            "score": dim.get("score", 1.0),
            "issues": dim.get("issues", []),
            "source": "orchestration",
        }

    # Agent dimensions (aggregate across all agents)
    for agent in quality_report.get("agent_scores", []):
        agent_name = agent.get("agent_name", "unknown")
        for dim in agent.get("dimensions", []):
            dim_name = dim.get("dimension", "")
            existing = all_dim_scores.get(dim_name)

            # Use the worst score across all agents
            if not existing or dim.get("score", 1.0) < existing.get("score", 1.0):
                all_dim_scores[dim_name] = {
                    "score": dim.get("score", 1.0),
                    "issues": dim.get("issues", []),
                    "source": f"agent:{agent_name}",
                }

    # Correlate each detection
    for detection in detections:
        detection_id = str(detection.get("id", ""))
        detection_type = detection.get("detection_type", "")
        detection_confidence = detection.get("confidence", 0)

        # Find related quality dimensions for this detection type
        related_dims = QUALITY_DETECTION_CORRELATIONS.get(detection_type, [])
        if not related_dims:
            continue

        # Find low-scoring dimensions
        low_scores = []
        for dim_name in related_dims:
            dim_data = all_dim_scores.get(dim_name)
            if dim_data and dim_data["score"] < min_score_threshold:
                low_scores.append({
                    "dimension": dim_name,
                    "score": dim_data["score"],
                    "issues": dim_data["issues"],
                    "source": dim_data["source"],
                    "description": DIMENSION_DESCRIPTIONS.get(dim_name, ""),
                })

        if low_scores:
            # Build explanation
            dim_names = [d["dimension"].replace("_", " ") for d in low_scores]
            explanation = f"This {detection_type.replace('_', ' ')} may be caused by issues with: {', '.join(dim_names)}"

            # Determine severity based on number and severity of quality issues
            severity = "medium"
            if len(low_scores) >= 3 or any(d["score"] < 0.3 for d in low_scores):
                severity = "high"
            elif len(low_scores) == 1 and all(d["score"] > 0.4 for d in low_scores):
                severity = "low"

            correlations.append(QualityCorrelation(
                detection_id=detection_id,
                detection_type=detection_type,
                detection_confidence=detection_confidence,
                related_quality_issues=low_scores,
                explanation=explanation,
                severity=severity,
            ))

    # Build summary
    if correlations:
        unique_dims = set()
        for c in correlations:
            for issue in c.related_quality_issues:
                unique_dims.add(issue["dimension"])

        summary = (
            f"Found {len(correlations)} of {len(detections)} detections correlated with "
            f"quality issues. Key areas for improvement: {', '.join(sorted(unique_dims)[:3])}"
        )
    else:
        summary = "No direct correlations found between detections and quality issues."

    return CorrelationResult(
        correlations=correlations,
        total_detections=len(detections),
        correlated_detections=len(correlations),
        summary=summary,
    )


def get_remediation_priority(
    quality_report: Dict[str, Any],
    detections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Get prioritized list of quality improvements based on detection frequency.

    Returns improvements ordered by how many detections they could prevent.

    Args:
        quality_report: Quality assessment report dict
        detections: List of detection dicts

    Returns:
        List of improvements with detection_impact score
    """
    # Count detection types
    detection_counts: Dict[str, int] = {}
    for d in detections:
        dtype = d.get("detection_type", "")
        detection_counts[dtype] = detection_counts.get(dtype, 0) + 1

    # Map dimensions to detection impact
    dim_impact: Dict[str, int] = {}
    for dtype, count in detection_counts.items():
        related_dims = QUALITY_DETECTION_CORRELATIONS.get(dtype, [])
        for dim in related_dims:
            dim_impact[dim] = dim_impact.get(dim, 0) + count

    # Get improvements from quality report and add impact score
    improvements = quality_report.get("improvements", [])

    # For each improvement, calculate impact based on related dimensions
    scored_improvements = []
    for imp in improvements:
        # Get dimension from improvement (stored in improvement data)
        imp_dim = imp.get("dimension", "")
        impact = dim_impact.get(imp_dim, 0)

        scored_improvements.append({
            **imp,
            "detection_impact": impact,
            "could_prevent": [
                dtype for dtype, dims in QUALITY_DETECTION_CORRELATIONS.items()
                if imp_dim in dims and dtype in detection_counts
            ],
        })

    # Sort by detection impact (descending), then by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    scored_improvements.sort(
        key=lambda x: (
            -x.get("detection_impact", 0),
            severity_order.get(x.get("severity", "medium"), 2),
        )
    )

    return scored_improvements
