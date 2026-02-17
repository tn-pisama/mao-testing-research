"""
Quality Assessment System for n8n Workflows and Agents.

This module provides comprehensive quality assessment for multi-agent workflows,
evaluating both individual agent quality and workflow-level orchestration patterns.

## Agent vs Orchestration Quality Differentiation

The assessment system distinguishes between two complementary quality dimensions:

### Agent Quality (60% of overall score)

Evaluates INDIVIDUAL AI NODE COMPETENCE - answers "Can each agent do its job well?"

**Dimensions**:
- `role_clarity`: Quality of system prompt, role definition, output format specification
- `output_consistency`: Structural consistency of agent outputs across executions
- `error_handling`: Individual node's ability to recover from failures (retry, timeout, continueOnFail)
- `tool_usage`: Quality of tool integration, descriptions, and parameter schemas
- `config_appropriateness`: Suitability of model configuration (temperature, tokens, model choice)

**Data Sources**: Node prompts, configuration, execution history

**Conceptual Level**: Micro (component-level)

### Orchestration Quality (40% of overall score)

Evaluates WORKFLOW ARCHITECTURE AND COORDINATION - answers "Do agents work well together?"

**Dimensions**:
- `data_flow_clarity`: Explicitness of data passing between nodes, naming clarity
- `complexity_management`: Appropriate workflow size, depth, cyclomatic complexity
- `agent_coupling`: Balance of agent interdependence, chain length
- `observability`: Debugging capability, checkpoints, error triggers
- `best_practices`: Workflow-level error handling patterns, configuration uniformity

**Data Sources**: Workflow graph structure, connections, patterns

**Conceptual Level**: Macro (system-level)

## The 60/40 Weighting Rationale

The overall score formula is:
    overall = (avg_agent_score * 0.6) + (orchestration_score * 0.4)

**Why 60% Agent Weight?**
1. Agent quality issues (bad prompts, poor config) typically cause MORE SEVERE failures
   - A poorly prompted agent produces wrong outputs regardless of good orchestration
   - Configuration issues like missing retry can cause complete workflow failures
2. Agent problems are often ROOT CAUSES, while orchestration problems are CONTRIBUTING FACTORS
3. Users have more direct control over agent configuration

**Why 40% Orchestration Weight?**
1. Good orchestration can MITIGATE some agent issues (error handling, checkpoints)
2. Orchestration problems often cause INTERMITTENT rather than consistent failures
3. Orchestration fixes are often structural changes requiring more effort

## Error Handling Boundary

To avoid double-penalizing workflows, error handling is evaluated differently at each level:

**Agent-level error handling** (agent_scorer.py):
- Evaluates: "Can THIS NODE recover from its own failures?"
- Checks: Individual node retry, timeout, continueOnFail configuration
- Perspective: Per-node capability

**Orchestration-level best practices** (orchestration_scorer.py):
- Evaluates: "Does the WORKFLOW have robust error handling architecture?"
- Checks: Global error handler presence, error branching patterns, configuration uniformity
- Perspective: Workflow-wide patterns

This separation ensures that a workflow isn't penalized twice for the same missing retry config.

## Usage

```python
from app.enterprise.quality import QualityAssessor

assessor = QualityAssessor(use_llm_judge=False)
report = assessor.assess_workflow(workflow_json, max_suggestions=10)

print(f"Overall: {report.overall_score:.1%} ({report.overall_grade})")
print(f"Agent avg: {sum(a.overall_score for a in report.agent_scores) / len(report.agent_scores):.1%}")
print(f"Orchestration: {report.orchestration_score.overall_score:.1%}")
```
"""

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
from datetime import datetime, UTC


class QualityAssessor:
    """
    Main orchestrator for quality assessment.

    Combines agent scoring, orchestration scoring, and improvement suggestions
    into a comprehensive quality report.
    """

    def __init__(self, use_llm_judge: bool = False, include_reasoning: bool = False):
        """
        Initialize the quality assessor.

        Args:
            use_llm_judge: Whether to use LLM for ambiguous cases (Tier 3 escalation)
            include_reasoning: Whether to generate detailed reasoning for each score
        """
        self.include_reasoning = include_reasoning
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
                    include_reasoning=self.include_reasoning,
                )
                agent_scores.append(score)

        # Score orchestration
        orchestration_score = self.orchestration_scorer.score_orchestration(
            workflow=workflow,
            execution_history=execution_history,
            include_reasoning=self.include_reasoning,
        )

        # Calculate overall score (weighted average of agent and orchestration)
        if agent_scores:
            avg_agent_score = sum(a.overall_score for a in agent_scores) / len(agent_scores)
            # Weight: 60% agents, 40% orchestration
            overall_score = (avg_agent_score * 0.6) + (orchestration_score.overall_score * 0.4)
        else:
            # No agents - orchestration only
            overall_score = orchestration_score.overall_score

        # Generate workflow-level reasoning if requested
        reasoning = None
        if self.include_reasoning:
            reasoning = self._generate_workflow_reasoning(
                workflow_name, overall_score, agent_scores, orchestration_score
            )

        # Create initial report for improvement generation
        report = QualityReport(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            overall_score=overall_score,
            agent_scores=agent_scores,
            orchestration_score=orchestration_score,
            improvements=[],
            summary="",
            reasoning=reasoning,
            generated_at=datetime.now(UTC),
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
            include_reasoning=self.include_reasoning,
        )

    def _generate_workflow_reasoning(
        self,
        workflow_name: str,
        overall_score: float,
        agent_scores: List[AgentQualityScore],
        orchestration_score: "OrchestrationQualityScore",
    ) -> str:
        """Generate workflow-level reasoning summarizing agent and orchestration findings."""
        from .models import _score_to_grade

        grade = _score_to_grade(overall_score)
        parts = [f"Workflow '{workflow_name}' overall quality: {overall_score:.0%} ({grade})."]

        if agent_scores:
            avg_agent = sum(a.overall_score for a in agent_scores) / len(agent_scores)
            parts.append(
                f"Agent quality ({len(agent_scores)} agents, avg {avg_agent:.0%}): "
                f"weighted 60% of overall score."
            )
            low = [a for a in agent_scores if a.overall_score < 0.6]
            if low:
                names = ", ".join(a.agent_name for a in low[:3])
                parts.append(f"Agents needing attention: {names}.")

        parts.append(
            f"Orchestration quality: {orchestration_score.overall_score:.0%} "
            f"({orchestration_score.grade}), weighted 40% of overall score."
        )

        all_critical = []
        for a in agent_scores:
            all_critical.extend(a.critical_issues)
        all_critical.extend(orchestration_score.critical_issues)
        if all_critical:
            parts.append(f"Critical issues ({len(all_critical)}): {'; '.join(all_critical[:3])}.")

        return " ".join(parts)

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
