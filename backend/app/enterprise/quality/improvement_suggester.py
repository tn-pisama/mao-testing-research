"""Improvement suggester with pluggable generators."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from .models import (
    QualityImprovement,
    AgentQualityScore,
    OrchestrationQualityScore,
    DimensionScore,
    QualityDimension,
    OrchestrationDimension,
    Severity,
    Effort,
    QualityReport,
)


class BaseImprovementGenerator(ABC):
    """Base class for improvement generators."""

    @abstractmethod
    def can_handle(self, dimension: str) -> bool:
        """Check if this generator handles the given dimension."""
        pass

    @abstractmethod
    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        """Generate improvements for a dimension score."""
        pass


class RoleClarityImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for role clarity issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == QualityDimension.ROLE_CLARITY.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        agent_id = context.get("agent_id", "unknown")
        agent_name = context.get("agent_name", "Agent")

        if score.score < 0.3:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.CRITICAL,
                category="role_clarity",
                title=f"Add system prompt to {agent_name}",
                description="This agent has no system prompt, making its behavior unpredictable.",
                rationale="System prompts define agent behavior, constraints, and output format. Without one, the agent may produce inconsistent or off-topic responses.",
                suggested_change="Add a system prompt that includes:\n1. Clear role definition ('You are a...')\n2. Task boundaries\n3. Output format specification",
                code_example='''System prompt example:
"You are a code review assistant. Your role is to analyze code changes and provide constructive feedback.

Output your review in JSON format:
{
  "summary": "Overall assessment",
  "issues": [{"severity": "high|medium|low", "description": "...", "suggestion": "..."}],
  "approved": true/false
}

Do not execute code or make changes directly. Only provide review feedback."''',
                estimated_impact="Significantly improve response relevance and consistency",
                effort=Effort.LOW,
            ))

        elif score.score < 0.5:
            evidence = score.evidence

            if not evidence.get("role_keywords_found", 0):
                improvements.append(QualityImprovement.create(
                    target_type="agent",
                    target_id=agent_id,
                    severity=Severity.HIGH,
                    category="role_clarity",
                    title=f"Add explicit role definition to {agent_name}",
                    description="The system prompt lacks a clear role statement.",
                    rationale="Starting with 'You are a [specific role]' helps the model understand its purpose and constraints.",
                    suggested_change="Add 'You are a [specific role]' at the beginning of the system prompt.",
                    code_example='Example: "You are a data validation specialist..."',
                    estimated_impact="Improve task focus by 30-40%",
                    effort=Effort.LOW,
                ))

            if not evidence.get("output_format_keywords", 0):
                improvements.append(QualityImprovement.create(
                    target_type="agent",
                    target_id=agent_id,
                    severity=Severity.MEDIUM,
                    category="role_clarity",
                    title=f"Specify output format for {agent_name}",
                    description="No output format is specified in the system prompt.",
                    rationale="Defining expected output format (JSON, markdown, etc.) ensures consistent, parseable responses.",
                    suggested_change="Add output format specification to the system prompt.",
                    code_example='"Respond in JSON format: {\"result\": ..., \"confidence\": 0.0-1.0}"',
                    estimated_impact="Reduce output parsing errors by 50%",
                    effort=Effort.LOW,
                ))

        elif score.score < 0.7:
            if not score.evidence.get("boundary_keywords", 0):
                improvements.append(QualityImprovement.create(
                    target_type="agent",
                    target_id=agent_id,
                    severity=Severity.LOW,
                    category="role_clarity",
                    title=f"Add boundary constraints to {agent_name}",
                    description="The system prompt lacks explicit constraints.",
                    rationale="Adding 'Do not...' or 'Avoid...' statements prevents off-topic behavior.",
                    suggested_change="Add boundary statements like 'Do not make assumptions about...' or 'Only respond to...'",
                    estimated_impact="Reduce off-topic responses",
                    effort=Effort.LOW,
                ))

        return improvements


class ErrorHandlingImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for error handling issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == QualityDimension.ERROR_HANDLING.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        agent_id = context.get("agent_id", "unknown")
        agent_name = context.get("agent_name", "Agent")
        evidence = score.evidence

        if score.score < 0.5:
            if not evidence.get("continue_on_fail"):
                improvements.append(QualityImprovement.create(
                    target_type="agent",
                    target_id=agent_id,
                    severity=Severity.HIGH,
                    category="error_handling",
                    title=f"Enable continue on fail for {agent_name}",
                    description="This agent will halt the entire workflow on failure.",
                    rationale="LLM calls can fail due to rate limits, network issues, or content filters. Enabling 'Continue on Fail' allows graceful degradation.",
                    suggested_change="Set 'continueOnFail: true' in node settings",
                    code_example='"continueOnFail": true,\n"alwaysOutputData": true',
                    estimated_impact="Prevent complete workflow failures",
                    effort=Effort.LOW,
                ))

            if not evidence.get("timeout_ms"):
                improvements.append(QualityImprovement.create(
                    target_type="agent",
                    target_id=agent_id,
                    severity=Severity.MEDIUM,
                    category="error_handling",
                    title=f"Add timeout to {agent_name}",
                    description="No timeout configured for this agent.",
                    rationale="Without a timeout, stuck LLM calls can hang indefinitely, blocking the workflow.",
                    suggested_change="Add timeout in milliseconds to node options",
                    code_example='"options": {\n  "timeout": 30000\n}',
                    estimated_impact="Prevent hanging executions",
                    effort=Effort.LOW,
                ))

        if not evidence.get("retry_on_fail"):
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.LOW if score.score > 0.5 else Severity.MEDIUM,
                category="error_handling",
                title=f"Enable retry for {agent_name}",
                description="No retry configuration for transient failures.",
                rationale="LLM API calls often have transient failures (rate limits, timeouts). Automatic retry improves reliability.",
                suggested_change="Enable 'Retry on Fail' with max retries (2-3 recommended)",
                code_example='"options": {\n  "retryOnFail": true,\n  "maxRetries": 3,\n  "waitBetweenTries": 1000\n}',
                estimated_impact="Improve success rate by 10-20%",
                effort=Effort.LOW,
            ))

        return improvements


class ObservabilityImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for observability issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.OBSERVABILITY.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        if evidence.get("observability_nodes", 0) == 0:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="observability",
                title="Add checkpoint nodes for debugging",
                description="No checkpoint or state capture nodes in workflow.",
                rationale="Checkpoints allow you to inspect intermediate state during debugging and enable trace replay.",
                suggested_change="Add Set nodes between major processing stages to capture state",
                code_example='''{
  "type": "n8n-nodes-base.set",
  "name": "Checkpoint: After Analysis",
  "parameters": {
    "values": {
      "string": [{"name": "checkpoint", "value": "analysis_complete"}]
    }
  },
  "alwaysOutputData": true
}''',
                estimated_impact="Reduce debugging time by 50%",
                effort=Effort.LOW,
            ))

        if evidence.get("error_triggers", 0) == 0:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="observability",
                title="Add error trigger for failure alerting",
                description="No error handling trigger in workflow.",
                rationale="Error triggers allow you to be notified when workflows fail and capture error context.",
                suggested_change="Add Error Trigger node connected to notification/logging",
                estimated_impact="Enable proactive failure monitoring",
                effort=Effort.MEDIUM,
            ))

        if evidence.get("monitoring_webhooks", 0) == 0 and evidence.get("observability_nodes", 0) < 2:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="observability",
                title="Add MAO webhook for trace analysis",
                description="Workflow not sending traces to MAO for analysis.",
                rationale="Sending execution traces to MAO enables detection of failures and quality degradation.",
                suggested_change="Add HTTP Request node at workflow end to send execution data to MAO webhook",
                estimated_impact="Enable automated failure detection",
                effort=Effort.MEDIUM,
            ))

        return improvements


class ComplexityImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for complexity issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.COMPLEXITY_MANAGEMENT.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        if evidence.get("node_count", 0) > 15:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="complexity",
                title="Consider breaking workflow into sub-workflows",
                description=f"Workflow has {evidence.get('node_count')} nodes, which may be difficult to maintain.",
                rationale="Large workflows are harder to debug, test, and maintain. Sub-workflows enable reuse and isolation.",
                suggested_change="Extract logical groups of nodes into separate sub-workflows",
                estimated_impact="Improve maintainability and enable reuse",
                effort=Effort.HIGH,
            ))

        if evidence.get("cyclomatic_complexity", 0) > 8:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="complexity",
                title="Reduce workflow branching complexity",
                description=f"Cyclomatic complexity of {evidence.get('cyclomatic_complexity')} indicates many execution paths.",
                rationale="High branching complexity makes testing difficult and increases chance of untested paths.",
                suggested_change="Consolidate conditional branches or extract into separate workflows",
                estimated_impact="Easier testing and fewer edge case bugs",
                effort=Effort.MEDIUM,
            ))

        if evidence.get("max_depth", 0) > 6:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="complexity",
                title="Flatten deep workflow nesting",
                description=f"Workflow has depth of {evidence.get('max_depth')}, which may indicate sequential bottlenecks.",
                rationale="Deep sequential chains create latency and single points of failure.",
                suggested_change="Consider parallelizing independent operations or extracting sub-workflows",
                estimated_impact="Reduce latency and improve fault tolerance",
                effort=Effort.MEDIUM,
            ))

        return improvements


class CouplingImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for agent coupling issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.AGENT_COUPLING.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        coupling_ratio = evidence.get("coupling_ratio", 0)
        if coupling_ratio > 0.6:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="coupling",
                title="Reduce direct agent-to-agent coupling",
                description=f"High coupling ratio ({coupling_ratio:.2f}) between agents.",
                rationale="Tight coupling means failures propagate easily. Adding intermediate processing reduces cascading failures.",
                suggested_change="Add validation or transformation nodes between agent chains",
                estimated_impact="Reduce cascading failure probability",
                effort=Effort.MEDIUM,
            ))

        chain_length = evidence.get("max_agent_chain", 0)
        if chain_length > 4:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="coupling",
                title="Break up long agent chains",
                description=f"Agent chain of {chain_length} consecutive agents detected.",
                rationale="Long chains accumulate errors and latency. Consider fan-out or checkpointing.",
                suggested_change="Add checkpoints every 2-3 agents or fan-out parallel processing where possible",
                estimated_impact="Improve reliability and debuggability",
                effort=Effort.MEDIUM,
            ))

        return improvements


class ImprovementSuggester:
    """Orchestrates improvement generation across all dimensions."""

    def __init__(self):
        self._generators: List[BaseImprovementGenerator] = []
        self._register_defaults()

    def _register_defaults(self):
        """Register default improvement generators."""
        self.register(RoleClarityImprovementGenerator())
        self.register(ErrorHandlingImprovementGenerator())
        self.register(ObservabilityImprovementGenerator())
        self.register(ComplexityImprovementGenerator())
        self.register(CouplingImprovementGenerator())

    def register(self, generator: BaseImprovementGenerator) -> None:
        """Register an improvement generator."""
        self._generators.append(generator)

    def suggest_improvements(
        self,
        report: QualityReport,
        max_suggestions: int = 10,
        min_severity: Severity = Severity.LOW,
    ) -> List[QualityImprovement]:
        """Generate prioritized improvement suggestions from a quality report."""
        all_improvements: List[QualityImprovement] = []

        # Generate improvements for agents
        for agent_score in report.agent_scores:
            agent_improvements = self.suggest_for_agent(agent_score)
            all_improvements.extend(agent_improvements)

        # Generate improvements for orchestration
        orchestration_improvements = self.suggest_for_orchestration(report.orchestration_score)
        all_improvements.extend(orchestration_improvements)

        # Filter by minimum severity
        severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        min_severity_index = severity_order.index(min_severity)

        filtered = [
            imp for imp in all_improvements
            if severity_order.index(imp.severity) <= min_severity_index
        ]

        # Sort by severity (critical first) then effort (low first)
        filtered.sort(key=lambda i: (
            severity_order.index(i.severity),
            [Effort.LOW, Effort.MEDIUM, Effort.HIGH].index(i.effort),
        ))

        return filtered[:max_suggestions]

    def suggest_for_agent(
        self,
        agent_score: AgentQualityScore,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> List[QualityImprovement]:
        """Generate improvements for a single agent."""
        context = {
            "agent_id": agent_score.agent_id,
            "agent_name": agent_score.agent_name,
            "agent_type": agent_score.agent_type,
            **(workflow_context or {}),
        }

        improvements = []
        for dimension in agent_score.dimensions:
            for generator in self._generators:
                if generator.can_handle(dimension.dimension):
                    dim_improvements = generator.generate(dimension, context)
                    improvements.extend(dim_improvements)

        return improvements

    def suggest_for_orchestration(
        self,
        orchestration_score: OrchestrationQualityScore,
    ) -> List[QualityImprovement]:
        """Generate improvements for orchestration."""
        context = {
            "workflow_id": orchestration_score.workflow_id,
            "workflow_name": orchestration_score.workflow_name,
            "detected_pattern": orchestration_score.detected_pattern,
        }

        improvements = []
        for dimension in orchestration_score.dimensions:
            for generator in self._generators:
                if generator.can_handle(dimension.dimension):
                    dim_improvements = generator.generate(dimension, context)
                    improvements.extend(dim_improvements)

        return improvements
