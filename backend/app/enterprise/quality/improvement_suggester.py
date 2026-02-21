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


class DataFlowClarityImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for data flow clarity issues."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.DATA_FLOW_CLARITY.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        if score.score < 0.5:
            connection_coverage = evidence.get("connection_coverage", 1.0)
            if connection_coverage < 0.7:
                improvements.append(QualityImprovement.create(
                    target_type="orchestration",
                    target_id=workflow_id,
                    severity=Severity.MEDIUM,
                    category="data_flow_clarity",
                    title="Add explicit connections between nodes",
                    description=f"Only {connection_coverage:.0%} of nodes have explicit input/output connections defined.",
                    rationale="Nodes without explicit connections rely on implicit data passing, which makes the workflow harder to understand and debug. Explicit connections document the intended data flow.",
                    suggested_change="Add connections between all nodes that exchange data, and remove any orphaned nodes",
                    code_example='''{
  "connections": {
    "AI Agent": {
      "main": [[{"node": "Output Parser", "type": "main", "index": 0}]]
    },
    "Output Parser": {
      "main": [[{"node": "Save Results", "type": "main", "index": 0}]]
    }
  }
}''',
                    estimated_impact="Improve workflow readability and reduce data passing errors",
                    effort=Effort.LOW,
                ))

        state_manipulation_ratio = evidence.get("state_manipulation_ratio", 0)
        if state_manipulation_ratio > 0.3:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="data_flow_clarity",
                title="Replace direct state manipulation with explicit data mapping",
                description=f"High state manipulation ratio ({state_manipulation_ratio:.2f}) indicates nodes are modifying shared state directly.",
                rationale="Direct state manipulation creates hidden dependencies between nodes. Using explicit data mapping through Set or Code nodes makes transformations visible and testable.",
                suggested_change="Use Set nodes or explicit expressions to map data between nodes instead of mutating shared state",
                code_example='''// Instead of modifying $json directly in a Function node:
// $json.result = someTransformation($json.input);

// Use a Set node with explicit field mapping:
{
  "type": "n8n-nodes-base.set",
  "name": "Map Analysis Results",
  "parameters": {
    "values": {
      "string": [
        {"name": "analysis_result", "value": "={{ $json.raw_output.summary }}"},
        {"name": "confidence", "value": "={{ $json.raw_output.score }}"}
      ]
    }
  }
}''',
                estimated_impact="Reduce hidden data dependencies and improve testability",
                effort=Effort.MEDIUM,
            ))

        generic_name_ratio = evidence.get("generic_name_ratio", 0)
        if generic_name_ratio > 0.5:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="data_flow_clarity",
                title="Rename nodes with descriptive names",
                description=f"{generic_name_ratio:.0%} of nodes have generic names (e.g., 'Code', 'HTTP Request', 'Set').",
                rationale="Generic node names make it impossible to understand data flow at a glance. Descriptive names document what each node does and what data it produces.",
                suggested_change="Rename nodes to describe their purpose, e.g., 'HTTP Request' -> 'Fetch Customer Orders', 'Code' -> 'Parse Invoice PDF'",
                code_example='''// Before:
"name": "HTTP Request"   // What does this fetch?
"name": "Code"           // What does this compute?
"name": "Set"            // What is being set?

// After:
"name": "Fetch Customer Profile from CRM"
"name": "Extract Key Metrics from Report"
"name": "Map Agent Output to API Schema"''',
                estimated_impact="Improve workflow readability and onboarding speed",
                effort=Effort.LOW,
            ))

        return improvements


class BestPracticesImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for best practices compliance."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.BEST_PRACTICES.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        if not evidence.get("error_handler_present"):
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.HIGH,
                category="best_practices",
                title="Add a global error handler to the workflow",
                description="No error handling trigger or catch mechanism detected in this workflow.",
                rationale="Without a global error handler, workflow failures are silent and unrecoverable. An error trigger captures failure context and enables alerting, logging, and graceful degradation.",
                suggested_change="Add an Error Trigger node connected to an alerting or logging node",
                code_example='''{
  "nodes": [
    {
      "type": "n8n-nodes-base.errorTrigger",
      "name": "On Workflow Error",
      "position": [250, 0]
    },
    {
      "type": "n8n-nodes-base.slack",
      "name": "Alert Team on Failure",
      "parameters": {
        "channel": "#workflow-alerts",
        "text": "Workflow failed: {{ $json.execution.error.message }}"
      }
    }
  ]
}''',
                estimated_impact="Enable failure detection and prevent silent errors",
                effort=Effort.MEDIUM,
            ))

        error_branch_coverage = evidence.get("error_branch_coverage", 1.0)
        if error_branch_coverage < 0.2:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="best_practices",
                title="Add error output branches to critical nodes",
                description=f"Only {error_branch_coverage:.0%} of nodes have error handling branches configured.",
                rationale="Nodes without error branches halt the entire workflow on failure. Adding error outputs allows the workflow to handle failures gracefully per node.",
                suggested_change="Enable 'Continue on Fail' on critical nodes and route error outputs to fallback logic",
                code_example='''// For each critical node, add error handling:
{
  "name": "AI Agent - Summarize",
  "continueOnFail": true,
  "onError": "continueErrorOutput",
  // Connect error output to fallback node:
  "connections": {
    "error": [[{"node": "Fallback: Use Cached Summary", "type": "main", "index": 0}]]
  }
}''',
                estimated_impact="Prevent complete workflow failure from single node errors",
                effort=Effort.MEDIUM,
            ))

        if not evidence.get("execution_timeout"):
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="best_practices",
                title="Set an execution timeout for the workflow",
                description="No executionTimeout is configured for this workflow.",
                rationale="Without a timeout, stuck workflows (e.g., waiting on an unresponsive API or a hung LLM call) run indefinitely, consuming resources and potentially causing cascading issues.",
                suggested_change="Add executionTimeout to workflow settings (recommended: 120-300 seconds for AI workflows)",
                code_example='''{
  "settings": {
    "executionTimeout": 300,
    "timezone": "UTC",
    "errorWorkflow": "error-handler-workflow-id"
  }
}''',
                estimated_impact="Prevent hung executions and resource exhaustion",
                effort=Effort.LOW,
            ))

        config_uniformity = evidence.get("config_uniformity", 1.0)
        if config_uniformity < 0.5:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="best_practices",
                title="Standardize node configuration patterns",
                description=f"Low configuration uniformity ({config_uniformity:.2f}) across similar node types.",
                rationale="Inconsistent configuration across similar nodes (e.g., different retry settings, different timeout values) makes the workflow unpredictable and harder to maintain.",
                suggested_change="Apply consistent settings (retries, timeouts, error handling) across all nodes of the same type",
                code_example='''// Standardize all AI Agent nodes:
{
  "retryOnFail": true,
  "maxRetries": 3,
  "waitBetweenTries": 1000,
  "continueOnFail": true,
  "timeout": 30000
}

// Standardize all HTTP Request nodes:
{
  "retryOnFail": true,
  "maxRetries": 2,
  "timeout": 15000
}''',
                estimated_impact="Improve workflow predictability and reduce maintenance overhead",
                effort=Effort.LOW,
            ))

        return improvements


class DocumentationQualityImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for documentation quality."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.DOCUMENTATION_QUALITY.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        if score.score < 0.3:
            sticky_note_count = evidence.get("sticky_note_count", 0)
            if sticky_note_count == 0:
                improvements.append(QualityImprovement.create(
                    target_type="orchestration",
                    target_id=workflow_id,
                    severity=Severity.MEDIUM,
                    category="documentation_quality",
                    title="Add sticky note documentation to workflow",
                    description="This workflow has no sticky notes or inline documentation.",
                    rationale="Undocumented workflows are difficult to maintain, debug, and hand off to other team members. Sticky notes provide context about design decisions, expected inputs/outputs, and known limitations.",
                    suggested_change="Add sticky notes for: workflow purpose, each major section, expected inputs/outputs, and any non-obvious logic",
                    code_example='''{
  "type": "n8n-nodes-base.stickyNote",
  "name": "Documentation: Workflow Overview",
  "parameters": {
    "content": "## Customer Feedback Analyzer\\n\\n**Purpose:** Processes incoming customer feedback, classifies sentiment, and routes to appropriate team.\\n\\n**Trigger:** Webhook from support platform\\n**Output:** Slack notification + CRM update\\n\\n**Owner:** Data Team | Last updated: 2025-01"
  },
  "position": [0, -200]
}''',
                    estimated_impact="Reduce onboarding time and prevent knowledge loss",
                    effort=Effort.LOW,
                ))

        workflow_description = evidence.get("workflow_description", "")
        if not workflow_description or len(str(workflow_description)) < 10:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="documentation_quality",
                title="Add a workflow description",
                description="The workflow has no description or a very brief one.",
                rationale="A workflow description appears in the workflow list and search results. It helps team members quickly understand what the workflow does without opening it.",
                suggested_change="Add a 1-2 sentence description in the workflow settings that explains what the workflow does and when it runs",
                code_example='''"meta": {
  "description": "Processes daily customer feedback from Zendesk, classifies sentiment using GPT-4, and routes critical issues to the escalation team via Slack."
}''',
                estimated_impact="Improve discoverability and team understanding",
                effort=Effort.LOW,
            ))

        if score.score < 0.7:
            substantive_notes = evidence.get("substantive_notes", 0)
            if substantive_notes < 2:
                improvements.append(QualityImprovement.create(
                    target_type="orchestration",
                    target_id=workflow_id,
                    severity=Severity.LOW,
                    category="documentation_quality",
                    title="Expand inline documentation with section notes",
                    description=f"Only {substantive_notes} substantive documentation note(s) found in the workflow.",
                    rationale="Complex workflows benefit from section-level documentation that explains the purpose of each group of nodes. This helps with debugging and maintenance.",
                    suggested_change="Add sticky notes at each major workflow section explaining: what it does, expected data shape, and error handling strategy",
                    estimated_impact="Improve maintainability and reduce debugging time",
                    effort=Effort.LOW,
                ))

        return improvements


class AIArchitectureImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for AI architecture design."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.AI_ARCHITECTURE.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        ai_connection_diversity = evidence.get("ai_connection_diversity", 1.0)
        if ai_connection_diversity < 0.5:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="ai_architecture",
                title="Enhance AI agent connections with memory and tools",
                description=f"AI connection diversity is low ({ai_connection_diversity:.2f}). Agents may lack memory or tool integrations.",
                rationale="AI agents that only have simple input/output connections miss opportunities for tool use, memory retrieval, and structured output parsing. Richer connections improve agent capability and reliability.",
                suggested_change="Connect AI agent nodes to memory stores (vector DB, buffer), tool nodes, and output parsers",
                code_example='''{
  "nodes": [
    {
      "type": "@n8n/n8n-nodes-langchain.agent",
      "name": "Research Agent",
      "parameters": {"model": "gpt-4o"}
    },
    {
      "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
      "name": "Conversation Memory",
      "parameters": {"sessionKey": "research_session", "contextWindowLength": 10}
    },
    {
      "type": "@n8n/n8n-nodes-langchain.toolHttpRequest",
      "name": "Search API Tool",
      "parameters": {"url": "https://api.search.example/query"}
    }
  ],
  "connections": {
    "Conversation Memory": {"ai_memory": [[{"node": "Research Agent"}]]},
    "Search API Tool": {"ai_tool": [[{"node": "Research Agent"}]]}
  }
}''',
                estimated_impact="Improve agent capabilities and response quality",
                effort=Effort.MEDIUM,
            ))

        if not evidence.get("guardrails_present"):
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="ai_architecture",
                title="Add output validation guardrails after AI nodes",
                description="No guardrail or validation nodes detected after AI agent outputs.",
                rationale="AI agents can produce hallucinated, malformed, or unsafe outputs. Adding validation nodes between AI outputs and downstream actions prevents bad data from propagating through the workflow.",
                suggested_change="Add a Code or IF node after each AI agent to validate output structure, check for required fields, and filter unsafe content",
                code_example='''// Add after each AI Agent node:
{
  "type": "n8n-nodes-base.code",
  "name": "Guardrail: Validate Agent Output",
  "parameters": {
    "jsCode": "const output = $input.first().json;\\n\\n// Validate required fields\\nif (!output.response || typeof output.response !== 'string') {\\n  throw new Error('Agent output missing required response field');\\n}\\n\\n// Check for common hallucination patterns\\nif (output.response.includes('I cannot') || output.response.length < 10) {\\n  return [{json: {\\n    ...output,\\n    flagged: true,\\n    flag_reason: 'Potential refusal or empty response'\\n  }}];\\n}\\n\\nreturn [{json: {...output, validated: true}}];"
  }
}''',
                estimated_impact="Prevent hallucinated or malformed outputs from reaching users",
                effort=Effort.MEDIUM,
            ))

        expensive_for_simple = evidence.get("expensive_models_for_simple_tasks", False)
        if expensive_for_simple:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="ai_architecture",
                title="Optimize model selection for task complexity",
                description="Expensive models (e.g., GPT-4, Claude Opus) are used for tasks that could be handled by smaller models.",
                rationale="Using powerful models for simple classification, extraction, or formatting tasks wastes cost and adds latency. Smaller models often perform equally well on straightforward tasks.",
                suggested_change="Use smaller models (gpt-4o-mini, claude-3-5-haiku) for simple tasks and reserve powerful models for complex reasoning",
                code_example='''// Task-based model selection:
// Simple classification/extraction -> gpt-4o-mini or claude-3-5-haiku
// Complex reasoning/analysis     -> gpt-4o or claude-3-5-sonnet
// Multi-step planning             -> o1 or claude-opus

// Example: Switch a formatting node from GPT-4 to GPT-4o-mini
{
  "name": "Format Report Output",
  "parameters": {
    "model": "gpt-4o-mini",  // Was: gpt-4 (overkill for formatting)
    "temperature": 0.1
  }
}''',
                estimated_impact="Reduce AI costs by 50-80% for simple tasks with no quality loss",
                effort=Effort.LOW,
            ))

        return improvements


class MaintenanceQualityImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for workflow maintenance quality."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.MAINTENANCE_QUALITY.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        disabled_nodes = evidence.get("disabled_nodes", 0)
        if disabled_nodes > 0:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="maintenance_quality",
                title="Remove or document disabled nodes",
                description=f"{disabled_nodes} disabled node(s) found in the workflow.",
                rationale="Disabled nodes are dead code that clutters the workflow canvas, confuses maintainers, and may contain outdated logic. If they serve as documentation of a removed feature, replace them with a sticky note instead.",
                suggested_change="Delete disabled nodes that are no longer needed, or add a sticky note explaining why they are kept disabled",
                code_example='''// Instead of keeping a disabled node:
// "disabled": true, "name": "Old Slack Notification"

// Either delete it entirely, or replace with documentation:
{
  "type": "n8n-nodes-base.stickyNote",
  "name": "Note: Removed Slack Notification",
  "parameters": {
    "content": "Slack notification was removed 2025-01 in favor of email alerts. See ticket PROJ-456."
  }
}''',
                estimated_impact="Reduce workflow clutter and confusion",
                effort=Effort.LOW,
            ))

        outdated_versions = evidence.get("outdated_versions", 0)
        if outdated_versions > 0:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="maintenance_quality",
                title="Update nodes to latest versions",
                description=f"{outdated_versions} node(s) are running outdated versions.",
                rationale="Outdated node versions may have known bugs, security vulnerabilities, or missing features. Keeping nodes up to date ensures you benefit from fixes and improvements.",
                suggested_change="Update outdated nodes to their latest available versions and verify workflow behavior after update",
                code_example='''// Check node version in the workflow JSON:
{
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 3,  // Current latest might be 4.2
  "name": "Fetch Data"
}

// Update to latest:
{
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "name": "Fetch Data"
}

// After updating, run a test execution to verify behavior is unchanged.''',
                estimated_impact="Reduce bugs and security risks from outdated node versions",
                effort=Effort.MEDIUM,
            ))

        workflow_description = evidence.get("workflow_description", "")
        if not workflow_description:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="maintenance_quality",
                title="Add workflow metadata for maintenance tracking",
                description="Workflow lacks a description and maintenance metadata.",
                rationale="Workflow metadata (description, owner, last review date) helps teams track ownership and schedule regular reviews. Without it, workflows become orphaned and drift from best practices.",
                suggested_change="Add a description and consider using tags or sticky notes to track ownership and review schedule",
                code_example='''"meta": {
  "description": "Processes inbound leads from HubSpot and enriches with Clearbit data",
  "tags": ["production", "marketing-team", "reviewed-2025-01"]
}

// Or add an ownership sticky note:
{
  "type": "n8n-nodes-base.stickyNote",
  "name": "Workflow Ownership",
  "parameters": {
    "content": "**Owner:** Marketing Ops\\n**Last Review:** 2025-01-15\\n**Next Review:** 2025-04-15\\n**Slack:** #marketing-workflows"
  }
}''',
                estimated_impact="Enable workflow lifecycle management and prevent orphaned workflows",
                effort=Effort.LOW,
            ))

        return improvements


class TestCoverageImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for test coverage."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.TEST_COVERAGE.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        test_coverage_ratio = evidence.get("test_coverage_ratio", 0)

        if test_coverage_ratio == 0:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.MEDIUM,
                category="test_coverage",
                title="Add test data using pinData for workflow validation",
                description="No test data or pinned data detected in any workflow nodes.",
                rationale="Workflows without test data cannot be validated before deployment. Using n8n's pinData feature, you can attach sample inputs to nodes and run the workflow in test mode to verify behavior without triggering live integrations.",
                suggested_change="Pin sample data on trigger and key intermediate nodes, then run test executions",
                code_example='''// Add pinData to the workflow trigger node:
{
  "name": "Webhook Trigger",
  "type": "n8n-nodes-base.webhook",
  "pinData": [
    {
      "json": {
        "customer_id": "CUST-001",
        "feedback": "The product quality has declined significantly",
        "rating": 2,
        "timestamp": "2025-01-15T10:30:00Z"
      }
    },
    {
      "json": {
        "customer_id": "CUST-002",
        "feedback": "Excellent support experience, very helpful team",
        "rating": 5,
        "timestamp": "2025-01-15T11:00:00Z"
      }
    }
  ]
}''',
                estimated_impact="Enable pre-deployment validation and regression testing",
                effort=Effort.MEDIUM,
            ))

        elif test_coverage_ratio < 0.5:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="test_coverage",
                title="Increase test coverage for critical workflow paths",
                description=f"Test coverage ratio is {test_coverage_ratio:.0%}. Several nodes lack test data.",
                rationale="Partial test coverage means some execution paths are untested and may fail in production. Focus on adding test data for nodes that handle branching logic, error cases, and external integrations.",
                suggested_change="Add pinData to untested nodes, especially IF/Switch nodes and nodes after error branches",
                code_example='''// Pin data on a branching node to test both paths:
{
  "name": "IF: High Priority",
  "type": "n8n-nodes-base.if",
  "pinData": [
    {"json": {"priority": "high", "escalate": true}},
    {"json": {"priority": "low", "escalate": false}}
  ]
}

// Pin error case data to verify error handling:
{
  "name": "AI Agent - Classify",
  "pinData": [
    {"json": {"error": true, "message": "Rate limit exceeded"}}
  ]
}''',
                estimated_impact="Catch edge case failures before they reach production",
                effort=Effort.LOW,
            ))

        # Always suggest pinning critical nodes if not fully covered
        if test_coverage_ratio < 1.0:
            critical_nodes_unpinned = evidence.get("critical_nodes_unpinned", [])
            if critical_nodes_unpinned:
                node_list = ", ".join(critical_nodes_unpinned[:5])
                improvements.append(QualityImprovement.create(
                    target_type="orchestration",
                    target_id=workflow_id,
                    severity=Severity.LOW,
                    category="test_coverage",
                    title="Pin test data on critical AI and integration nodes",
                    description=f"Critical nodes without pinned test data: {node_list}.",
                    rationale="AI nodes and external integration nodes are the most likely failure points. Pinning representative test data on these nodes enables quick validation after any workflow change.",
                    suggested_change="Add pinData with representative inputs (including edge cases) to all AI agent and HTTP request nodes",
                    estimated_impact="Enable rapid regression testing for high-risk nodes",
                    effort=Effort.LOW,
                ))

        return improvements


class LayoutQualityImprovementGenerator(BaseImprovementGenerator):
    """Generate improvements for workflow layout quality."""

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.LAYOUT_QUALITY.value

    def generate(
        self,
        score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityImprovement]:
        improvements = []
        workflow_id = context.get("workflow_id", "unknown")
        evidence = score.evidence

        overlapping_nodes = evidence.get("overlapping_nodes", 0)
        if overlapping_nodes > 0:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.LOW,
                category="layout_quality",
                title="Fix overlapping node positions",
                description=f"{overlapping_nodes} node(s) have overlapping positions on the canvas.",
                rationale="Overlapping nodes obscure connections and make the workflow difficult to read. They often result from copy-paste operations or imports where positions were not adjusted.",
                suggested_change="Reposition overlapping nodes to maintain at least 200px horizontal and 100px vertical spacing",
                code_example='''// Ensure consistent spacing between nodes:
// Horizontal flow (left to right): 250px between nodes
// Vertical branches: 150px between parallel paths

// Example layout for a 3-node sequence:
{"name": "Trigger",    "position": [250, 300]}
{"name": "Process",    "position": [500, 300]}  // +250 horizontal
{"name": "Output",     "position": [750, 300]}  // +250 horizontal

// Parallel branches:
{"name": "Branch A",   "position": [500, 200]}  // -100 vertical
{"name": "Branch B",   "position": [500, 400]}  // +100 vertical''',
                estimated_impact="Improve workflow readability and reduce editing errors",
                effort=Effort.LOW,
            ))

        alignment_score = evidence.get("alignment_score", 1.0)
        if alignment_score < 0.5:
            improvements.append(QualityImprovement.create(
                target_type="orchestration",
                target_id=workflow_id,
                severity=Severity.INFO,
                category="layout_quality",
                title="Align nodes to a grid for visual consistency",
                description=f"Node alignment score is low ({alignment_score:.2f}), indicating nodes are placed irregularly.",
                rationale="Grid-aligned nodes create clean visual flow that makes workflows easier to scan and understand. Consistent alignment also makes it easier to add new nodes without disrupting the layout.",
                suggested_change="Snap all nodes to a 50px grid and arrange in a left-to-right flow with consistent vertical alignment for branches",
                code_example='''// Snap positions to nearest 50px grid:
// Before: {"position": [237, 418]}
// After:  {"position": [250, 400]}

// Use consistent vertical alignment for sequential nodes:
{"name": "Step 1", "position": [250, 300]}
{"name": "Step 2", "position": [500, 300]}  // Same Y for sequential
{"name": "Step 3", "position": [750, 300]}

// Use n8n's built-in "Tidy Up" feature (Ctrl+Shift+T) for automatic alignment''',
                estimated_impact="Improve visual clarity and workflow navigation",
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

        # Additional orchestration dimension generators
        self.register(DataFlowClarityImprovementGenerator())
        self.register(BestPracticesImprovementGenerator())
        self.register(DocumentationQualityImprovementGenerator())
        self.register(AIArchitectureImprovementGenerator())
        self.register(MaintenanceQualityImprovementGenerator())
        self.register(TestCoverageImprovementGenerator())
        self.register(LayoutQualityImprovementGenerator())

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
