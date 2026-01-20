"""Quality assessment module for n8n workflows and agents."""

from .models import (
    QualityDimension,
    OrchestrationDimension,
    Severity,
    Effort,
    DimensionScore,
    AgentQualityScore,
    ComplexityMetrics,
    OrchestrationQualityScore,
    QualityImprovement,
    QualityReport,
)
from .agent_scorer import AgentQualityScorer, is_agent_node
from .orchestration_scorer import OrchestrationQualityScorer
from .improvement_suggester import (
    ImprovementSuggester,
    BaseImprovementGenerator,
)

from typing import Dict, Any, List, Optional
from datetime import datetime


class QualityAssessor:
    """
    Main orchestrator for quality assessment.

    Combines agent scoring, orchestration scoring, and improvement suggestions
    into a comprehensive quality report.
    """

    def __init__(self, use_llm_judge: bool = False):
        """
        Initialize the quality assessor.

        Args:
            use_llm_judge: Whether to use LLM for ambiguous cases (Tier 3 escalation)
        """
        self.agent_scorer = AgentQualityScorer(use_llm_judge=use_llm_judge)
        self.orchestration_scorer = OrchestrationQualityScorer()
        self.improvement_suggester = ImprovementSuggester()

    def assess_workflow(
        self,
        workflow: Dict[str, Any],
        execution_history: Optional[List[Dict[str, Any]]] = None,
        max_suggestions: int = 10,
    ) -> QualityReport:
        """
        Assess the quality of an n8n workflow.

        Args:
            workflow: The n8n workflow JSON
            execution_history: Optional list of past execution data
            max_suggestions: Maximum number of improvement suggestions

        Returns:
            QualityReport with agent scores, orchestration score, and improvements
        """
        workflow_id = workflow.get("id", "unknown")
        workflow_name = workflow.get("name", "Unnamed Workflow")
        nodes = workflow.get("nodes", [])

        # Score individual agents
        agent_scores: List[AgentQualityScore] = []
        for node in nodes:
            if is_agent_node(node):
                # Get node-specific execution history if available
                node_history = None
                if execution_history:
                    node_id = node.get("id", node.get("name"))
                    node_history = [
                        e for e in execution_history
                        if e.get("node_id") == node_id or e.get("node_name") == node.get("name")
                    ]

                score = self.agent_scorer.score_agent(
                    node=node,
                    workflow_context=workflow,
                    execution_history=node_history,
                )
                agent_scores.append(score)

        # Score orchestration
        orchestration_score = self.orchestration_scorer.score_orchestration(
            workflow=workflow,
            execution_history=execution_history,
        )

        # Calculate overall score (weighted average of agent and orchestration)
        if agent_scores:
            avg_agent_score = sum(a.overall_score for a in agent_scores) / len(agent_scores)
            # Weight: 60% agents, 40% orchestration
            overall_score = (avg_agent_score * 0.6) + (orchestration_score.overall_score * 0.4)
        else:
            # No agents - orchestration only
            overall_score = orchestration_score.overall_score

        # Create initial report for improvement generation
        report = QualityReport(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            overall_score=overall_score,
            agent_scores=agent_scores,
            orchestration_score=orchestration_score,
            improvements=[],
            summary="",
            generated_at=datetime.utcnow(),
        )

        # Generate improvements
        improvements = self.improvement_suggester.suggest_improvements(
            report=report,
            max_suggestions=max_suggestions,
        )
        report.improvements = improvements

        # Generate summary
        report.summary = self._generate_summary(report)

        return report

    def assess_agent(
        self,
        node: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None,
        execution_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentQualityScore:
        """
        Assess the quality of a single agent node.

        Args:
            node: The n8n agent node JSON
            workflow_context: Optional workflow context for error handling analysis
            execution_history: Optional execution history for output analysis

        Returns:
            AgentQualityScore with dimension scores
        """
        return self.agent_scorer.score_agent(
            node=node,
            workflow_context=workflow_context,
            execution_history=execution_history,
        )

    def _generate_summary(self, report: QualityReport) -> str:
        """Generate a human-readable summary of the quality report."""
        parts = []

        # Overall assessment
        parts.append(f"Overall quality: {report.overall_grade} ({report.overall_score:.0%})")

        # Agent summary
        if report.agent_scores:
            avg_agent = sum(a.overall_score for a in report.agent_scores) / len(report.agent_scores)
            low_scoring = [a for a in report.agent_scores if a.overall_score < 0.6]
            parts.append(f"{len(report.agent_scores)} agents assessed (avg: {avg_agent:.0%})")
            if low_scoring:
                parts.append(f"{len(low_scoring)} agent(s) need attention")

        # Orchestration summary
        parts.append(f"Orchestration: {report.orchestration_score.grade} ({report.orchestration_score.detected_pattern} pattern)")

        # Critical issues
        if report.critical_issues_count > 0:
            parts.append(f"{report.critical_issues_count} critical issue(s) to address")

        # Top improvement
        if report.improvements:
            top = report.improvements[0]
            parts.append(f"Priority fix: {top.title}")

        return ". ".join(parts) + "."


__all__ = [
    # Models
    "QualityDimension",
    "OrchestrationDimension",
    "Severity",
    "Effort",
    "DimensionScore",
    "AgentQualityScore",
    "ComplexityMetrics",
    "OrchestrationQualityScore",
    "QualityImprovement",
    "QualityReport",
    # Scorers
    "AgentQualityScorer",
    "OrchestrationQualityScorer",
    "is_agent_node",
    # Suggester
    "ImprovementSuggester",
    "BaseImprovementGenerator",
    # Main orchestrator
    "QualityAssessor",
]
