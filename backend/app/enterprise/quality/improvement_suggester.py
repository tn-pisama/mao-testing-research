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


class OutputConsistencyImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for output consistency issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == QualityDimension.OUTPUT_CONSISTENCY.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        agent_id = context.get("agent_id", "unknown")
        agent_name = context.get("agent_name", "Agent")
        evidence = score.evidence

        # Check if JSON is expected but structure varies
        if evidence.get("expects_json") and evidence.get("unique_structures", 1) > 1:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.MEDIUM,
                category="output_consistency",
                title=f"Enforce JSON schema for {agent_name}",
                description=f"Output structure varies across executions ({evidence.get('unique_structures')} different schemas detected).",
                rationale="Inconsistent output schemas break downstream parsing. Using structured output mode or explicit schema validation ensures reliable data flow.",
                suggested_change="Use structured output mode or add explicit JSON schema to system prompt",
                code_example='''Add to system prompt:
"You must respond with valid JSON matching this exact schema:
{
  "result": string,
  "confidence": number (0.0-1.0),
  "metadata": {"source": string, "timestamp": string}
}

Do not include any text outside the JSON object."

Or use n8n's structured output parser node after this agent.''',
                estimated_impact="Eliminate output parsing errors",
                effort=Effort.LOW,
            ))

        elif score.score < 0.6 and evidence.get("execution_samples", 0) < 2:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.LOW,
                category="output_consistency",
                title=f"Validate {agent_name} output consistency",
                description="Insufficient execution history to assess output consistency.",
                rationale="Output consistency can only be measured with multiple executions. Run the workflow several times to gather baseline data.",
                suggested_change="Run 3-5 test executions with varied inputs to establish output pattern baseline",
                estimated_impact="Enable output consistency monitoring",
                effort=Effort.LOW,
            ))

        if evidence.get("expects_json") and score.score < 0.8:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.LOW,
                category="output_consistency",
                title=f"Add output validation node after {agent_name}",
                description="JSON output expected but no validation node present.",
                rationale="Adding a validation node catches malformed outputs early and provides clear error messages.",
                suggested_change="Add a Code node after this agent to validate and normalize output structure",
                code_example='''// Validation node code
const input = $input.first().json;

// Validate required fields
if (!input.result || typeof input.confidence !== 'number') {
  throw new Error('Invalid output structure: missing required fields');
}

// Normalize confidence to 0-1 range
const normalized = {
  ...input,
  confidence: Math.max(0, Math.min(1, input.confidence))
};

return [{json: normalized}];''',
                estimated_impact="Catch output errors before downstream processing",
                effort=Effort.MEDIUM,
            ))

        return improvements


class ToolUsageImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for tool usage issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == QualityDimension.TOOL_USAGE.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        agent_id = context.get("agent_id", "unknown")
        agent_name = context.get("agent_name", "Agent")
        evidence = score.evidence

        tool_count = evidence.get("tool_count", 0)
        tools_with_description = evidence.get("tools_with_description", 0)
        tools_with_schema = evidence.get("tools_with_schema", 0)

        # Agent node without tools
        if tool_count == 0 and "agent" in context.get("agent_type", "").lower():
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.MEDIUM,
                category="tool_usage",
                title=f"Add tools to {agent_name}",
                description="This agent has no tools configured.",
                rationale="Agents without tools are limited to text generation. Tools enable agents to take actions, fetch data, and interact with external systems.",
                suggested_change="Add relevant tools based on the agent's purpose",
                code_example='''"tools": [
  {
    "name": "search_database",
    "description": "Search the product database for items matching criteria",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string", "description": "Search query"},
        "limit": {"type": "integer", "default": 10}
      },
      "required": ["query"]
    }
  }
]''',
                estimated_impact="Enable agent to perform actions beyond text generation",
                effort=Effort.MEDIUM,
            ))

        # Tools missing descriptions
        if tool_count > 0 and tools_with_description < tool_count:
            missing = tool_count - tools_with_description
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.MEDIUM,
                category="tool_usage",
                title=f"Add descriptions to tools in {agent_name}",
                description=f"{missing} of {tool_count} tools lack descriptions.",
                rationale="Tool descriptions help the LLM understand when and how to use each tool. Without descriptions, the agent may misuse tools or fail to use them when appropriate.",
                suggested_change="Add clear, action-oriented descriptions to all tools",
                code_example='''// Instead of:
{"name": "getData"}

// Use:
{
  "name": "getData",
  "description": "Retrieves customer data by ID. Use this when the user asks about a specific customer's order history, preferences, or account details."
}''',
                estimated_impact="Improve tool selection accuracy by 40-60%",
                effort=Effort.LOW,
            ))

        # Tools missing parameter schemas
        if tool_count > 0 and tools_with_schema < tool_count:
            missing = tool_count - tools_with_schema
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.LOW,
                category="tool_usage",
                title=f"Add parameter schemas to tools in {agent_name}",
                description=f"{missing} of {tool_count} tools lack parameter schemas.",
                rationale="Parameter schemas enable type validation and help the LLM construct valid tool calls.",
                suggested_change="Add JSON schema for all tool parameters",
                code_example='''"parameters": {
  "type": "object",
  "properties": {
    "customer_id": {
      "type": "string",
      "description": "The unique customer identifier (format: CUST-XXXXX)"
    },
    "include_history": {
      "type": "boolean",
      "description": "Whether to include order history",
      "default": false
    }
  },
  "required": ["customer_id"]
}''',
                estimated_impact="Reduce tool call errors by 30%",
                effort=Effort.LOW,
            ))

        # Too many tools
        if tool_count > 10:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.MEDIUM,
                category="tool_usage",
                title=f"Reduce tool count in {agent_name}",
                description=f"Agent has {tool_count} tools, which may cause confusion.",
                rationale="Too many tools overwhelm the LLM's ability to select the right one. Consider grouping related tools or splitting into specialized agents.",
                suggested_change="Consolidate related tools or split agent into specialized sub-agents",
                estimated_impact="Improve tool selection accuracy",
                effort=Effort.HIGH,
            ))

        return improvements


class ConfigAppropriatenessImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for configuration appropriateness issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == QualityDimension.CONFIG_APPROPRIATENESS.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        agent_id = context.get("agent_id", "unknown")
        agent_name = context.get("agent_name", "Agent")
        evidence = score.evidence

        temperature = evidence.get("temperature")
        max_tokens = evidence.get("max_tokens")
        model = evidence.get("model", "")
        task_type = evidence.get("inferred_task_type", "default")

        # Temperature recommendations by task type
        temp_recommendations = {
            "code": (0.0, 0.3, "Code generation requires deterministic outputs"),
            "analysis": (0.0, 0.5, "Analysis benefits from focused, factual responses"),
            "creative": (0.5, 0.9, "Creative tasks benefit from more variation"),
            "default": (0.0, 0.7, "General tasks work well with moderate temperature"),
        }

        if temperature is not None:
            rec = temp_recommendations.get(task_type, temp_recommendations["default"])
            if temperature < rec[0] or temperature > rec[1]:
                improvements.append(QualityImprovement.create(
                    target_type="agent",
                    target_id=agent_id,
                    severity=Severity.LOW,
                    category="config_appropriateness",
                    title=f"Adjust temperature for {agent_name}",
                    description=f"Temperature {temperature} may not be optimal for {task_type} tasks.",
                    rationale=f"{rec[2]}. Current temperature ({temperature}) is outside the recommended range of {rec[0]}-{rec[1]}.",
                    suggested_change=f"Set temperature between {rec[0]} and {rec[1]} for {task_type} tasks",
                    code_example=f'''"options": {{
  "temperature": {(rec[0] + rec[1]) / 2:.1f}  // Recommended for {task_type}
}}''',
                    estimated_impact="Improve output quality for task type",
                    effort=Effort.LOW,
                ))

        # Max tokens too low
        if max_tokens is not None and max_tokens < 100:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.MEDIUM,
                category="config_appropriateness",
                title=f"Increase max tokens for {agent_name}",
                description=f"Max tokens ({max_tokens}) is very low and may truncate responses.",
                rationale="Low token limits can cause incomplete responses, especially for complex tasks or detailed outputs.",
                suggested_change="Increase max tokens to at least 500 for most tasks, or 1000+ for complex outputs",
                code_example='''"options": {
  "maxTokens": 1000  // Minimum recommended for complex responses
}''',
                estimated_impact="Prevent response truncation",
                effort=Effort.LOW,
            ))

        # Max tokens very high (cost concern)
        elif max_tokens is not None and max_tokens > 8000:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.INFO,
                category="config_appropriateness",
                title=f"Review high token limit for {agent_name}",
                description=f"Max tokens ({max_tokens}) is very high.",
                rationale="High token limits increase cost. Ensure this is necessary for the task.",
                suggested_change="Review if the task actually requires such long outputs, or add output length guidance to system prompt",
                estimated_impact="Potential cost savings",
                effort=Effort.LOW,
            ))

        # Model tier suggestions
        model_tier = evidence.get("model_tier", "")
        if model_tier == "powerful" and task_type in ["default"]:
            improvements.append(QualityImprovement.create(
                target_type="agent",
                target_id=agent_id,
                severity=Severity.INFO,
                category="config_appropriateness",
                title=f"Consider using faster model for {agent_name}",
                description=f"Using powerful model tier ({model}) for general tasks.",
                rationale="Smaller, faster models often perform well for straightforward tasks at lower cost and latency.",
                suggested_change="Consider using a smaller model (e.g., claude-3-5-haiku, gpt-4o-mini) for simpler tasks",
                estimated_impact="Reduce cost and latency",
                effort=Effort.LOW,
            ))

        return improvements


class ImprovementSuggester:
    """Orchestrates improvement generation across all dimensions."""

    def __init__(self):
        self._generators: List[BaseImprovementGenerator] = []
        self._register_defaults()

    def _register_defaults(self):
        """Register default improvement generators."""
        # Agent quality dimension generators
        self.register(RoleClarityImprovementGenerator())
        self.register(ErrorHandlingImprovementGenerator())
        self.register(OutputConsistencyImprovementGenerator())
        self.register(ToolUsageImprovementGenerator())
        self.register(ConfigAppropriatenessImprovementGenerator())

        # Orchestration quality dimension generators
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
