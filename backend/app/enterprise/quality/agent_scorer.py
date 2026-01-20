"""Agent quality scorer with 5-dimension assessment."""

import re
from typing import Dict, Any, List, Optional
from .models import (
    AgentQualityScore,
    DimensionScore,
    QualityDimension,
    Severity,
)


# Node types that represent AI/LLM agents (nodes that have prompts)
AI_NODE_TYPES = {
    "@n8n/n8n-nodes-langchain.agent",
    "@n8n/n8n-nodes-langchain.chainLlm",
    "@n8n/n8n-nodes-langchain.chainSummarization",
    "@n8n/n8n-nodes-langchain.chainRetrievalQa",
    "n8n-nodes-base.openAi",
    "n8n-nodes-base.anthropic",
}

# LM nodes are just model configuration - they connect to agents
# These don't need system prompts, so we exclude them from scoring
LM_CONFIG_NODE_TYPES = {
    "@n8n/n8n-nodes-langchain.lmChatOpenAi",
    "@n8n/n8n-nodes-langchain.lmChatAnthropic",
    "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
    "@n8n/n8n-nodes-langchain.lmChatAzureOpenAi",
    "@n8n/n8n-nodes-langchain.lmChatOllama",
    "@n8n/n8n-nodes-langchain.lmChatMistral",
    "@n8n/n8n-nodes-langchain.lmChatGroq",
}

# Role definition keywords
ROLE_KEYWORDS = [
    "you are", "your role", "as a", "your task", "your job",
    "you will", "you must", "you should", "your purpose",
]

# Output format keywords
OUTPUT_FORMAT_KEYWORDS = [
    "respond with", "return", "output", "format", "json",
    "provide", "give me", "answer with", "structure",
]

# Boundary keywords
BOUNDARY_KEYWORDS = [
    "do not", "don't", "never", "avoid", "only", "must not",
    "refrain from", "you cannot", "you should not",
]

# Temperature recommendations by task type
TEMPERATURE_RECOMMENDATIONS = {
    "code": (0.0, 0.3),
    "analysis": (0.0, 0.5),
    "creative": (0.5, 0.9),
    "default": (0.0, 0.7),
}


class AgentQualityScorer:
    """
    Scores individual agent quality across five dimensions:
    1. Role Clarity - How well-defined is the agent's purpose?
    2. Output Consistency - Does output match expected structure?
    3. Error Handling - Are error cases covered?
    4. Tool Usage - Are tools properly integrated?
    5. Config Appropriateness - Are temperature/tokens reasonable?
    """

    def __init__(self, use_llm_judge: bool = False, judge_model: str = "claude-3-5-haiku-20241022"):
        self.use_llm_judge = use_llm_judge
        self.judge_model = judge_model

    def score_agent(
        self,
        node: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None,
        execution_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentQualityScore:
        """Score a single agent node across all quality dimensions."""
        agent_id = node.get("id", "unknown")
        agent_name = node.get("name", "Unnamed Agent")
        agent_type = node.get("type", "unknown")

        dimensions: List[DimensionScore] = []

        # Score each dimension
        dimensions.append(self._score_role_clarity(node))
        dimensions.append(self._score_output_consistency(node, execution_history))
        dimensions.append(self._score_error_handling(node, workflow_context))
        dimensions.append(self._score_tool_usage(node))
        dimensions.append(self._score_config_appropriateness(node))

        # Calculate overall score (weighted average)
        total_weight = sum(d.weight for d in dimensions)
        overall_score = sum(d.score * d.weight for d in dimensions) / total_weight if total_weight > 0 else 0.0

        # Collect issues
        all_issues = []
        critical_issues = []
        for dim in dimensions:
            all_issues.extend(dim.issues)
            # Low scores on important dimensions are critical
            if dim.score < 0.4 and dim.dimension in [
                QualityDimension.ROLE_CLARITY.value,
                QualityDimension.ERROR_HANDLING.value,
            ]:
                critical_issues.extend(dim.issues[:1])  # First issue as critical

        return AgentQualityScore(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_type=agent_type,
            overall_score=overall_score,
            dimensions=dimensions,
            issues_count=len(all_issues),
            critical_issues=critical_issues,
            metadata={
                "is_ai_node": agent_type in AI_NODE_TYPES,
                "scored_at": "fast",  # or "llm" if escalated
            },
        )

    def _score_role_clarity(self, node: Dict[str, Any]) -> DimensionScore:
        """
        Score role clarity based on system prompt analysis.

        Checks for:
        - Explicit role definition keywords
        - Clear boundaries and constraints
        - Output format specification
        - Sufficient detail (word count)
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.0

        # Extract system prompt from various locations
        system_prompt = self._extract_system_prompt(node)
        evidence["has_system_prompt"] = bool(system_prompt)
        evidence["prompt_length"] = len(system_prompt) if system_prompt else 0

        if not system_prompt:
            issues.append("No system prompt defined")
            suggestions.append("Add a system prompt with clear role definition")
            return DimensionScore(
                dimension=QualityDimension.ROLE_CLARITY.value,
                score=0.0,
                issues=issues,
                evidence=evidence,
                suggestions=suggestions,
            )

        prompt_lower = system_prompt.lower()

        # Check for role definition keywords (30% weight)
        role_matches = sum(1 for kw in ROLE_KEYWORDS if kw in prompt_lower)
        evidence["role_keywords_found"] = role_matches
        role_score = min(role_matches / 2, 1.0)  # 2+ keywords = full score
        score += role_score * 0.3

        if role_matches == 0:
            issues.append("System prompt lacks explicit role definition")
            suggestions.append("Add 'You are a [specific role]' statement")

        # Check for output format specification (25% weight)
        output_matches = sum(1 for kw in OUTPUT_FORMAT_KEYWORDS if kw in prompt_lower)
        evidence["output_format_keywords"] = output_matches
        output_score = min(output_matches / 2, 1.0)
        score += output_score * 0.25

        if output_matches == 0:
            issues.append("No output format specification")
            suggestions.append("Specify expected output format (e.g., JSON schema)")

        # Check for boundary keywords (20% weight)
        boundary_matches = sum(1 for kw in BOUNDARY_KEYWORDS if kw in prompt_lower)
        evidence["boundary_keywords"] = boundary_matches
        boundary_score = min(boundary_matches / 2, 1.0)
        score += boundary_score * 0.2

        if boundary_matches == 0:
            suggestions.append("Add boundary constraints (e.g., 'Do not...')")

        # Check prompt length/detail (15% weight)
        word_count = len(system_prompt.split())
        evidence["word_count"] = word_count
        # 50+ words is ideal, scale from 20-80
        length_score = min(max((word_count - 20) / 60, 0), 1.0)
        score += length_score * 0.15

        if word_count < 30:
            issues.append(f"System prompt is too brief ({word_count} words)")
            suggestions.append("Expand prompt with more specific instructions")

        # Check for specificity - named entities or domain terms (10% weight)
        specificity_score = self._assess_specificity(system_prompt)
        evidence["specificity_score"] = specificity_score
        score += specificity_score * 0.1

        return DimensionScore(
            dimension=QualityDimension.ROLE_CLARITY.value,
            score=min(score, 1.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_output_consistency(
        self,
        node: Dict[str, Any],
        execution_history: Optional[List[Dict[str, Any]]] = None,
    ) -> DimensionScore:
        """
        Score output consistency based on execution history analysis.

        Checks for:
        - Consistent output structure across executions
        - JSON schema adherence
        - Field presence consistency
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.7  # Default score when no execution history

        # Check if JSON output is expected
        system_prompt = self._extract_system_prompt(node)
        expects_json = False
        if system_prompt:
            expects_json = "json" in system_prompt.lower()
            evidence["expects_json"] = expects_json

        if not execution_history:
            evidence["execution_samples"] = 0
            if expects_json:
                suggestions.append("Run executions to validate JSON output consistency")
            return DimensionScore(
                dimension=QualityDimension.OUTPUT_CONSISTENCY.value,
                score=score,
                issues=issues,
                evidence=evidence,
                suggestions=suggestions,
            )

        evidence["execution_samples"] = len(execution_history)

        # Analyze execution outputs
        outputs = [e.get("output", {}) for e in execution_history if e.get("output")]

        if len(outputs) < 2:
            return DimensionScore(
                dimension=QualityDimension.OUTPUT_CONSISTENCY.value,
                score=0.7,
                issues=issues,
                evidence=evidence,
                suggestions=suggestions,
            )

        # Check structural consistency
        structures = []
        for output in outputs:
            if isinstance(output, dict):
                structures.append(frozenset(output.keys()))
            elif isinstance(output, str):
                # Try to parse as JSON
                try:
                    import json
                    parsed = json.loads(output)
                    if isinstance(parsed, dict):
                        structures.append(frozenset(parsed.keys()))
                except (json.JSONDecodeError, TypeError):
                    pass

        if structures:
            unique_structures = len(set(structures))
            evidence["unique_structures"] = unique_structures
            consistency_ratio = 1 / unique_structures if unique_structures > 0 else 0
            score = consistency_ratio

            if unique_structures > 1:
                issues.append(f"Output structure varies ({unique_structures} different schemas)")
                suggestions.append("Enforce consistent output schema in system prompt")

        return DimensionScore(
            dimension=QualityDimension.OUTPUT_CONSISTENCY.value,
            score=score,
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_error_handling(
        self,
        node: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> DimensionScore:
        """
        Score error handling coverage.

        Checks for:
        - continueOnFail flag
        - Error output paths
        - Fallback configurations
        - Timeout settings
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.0

        # Check continueOnFail
        continue_on_fail = node.get("continueOnFail", False)
        evidence["continue_on_fail"] = continue_on_fail
        if continue_on_fail:
            score += 0.25
        else:
            suggestions.append("Consider enabling 'Continue on Fail' for graceful error handling")

        # Check for always output data
        always_output = node.get("alwaysOutputData", False)
        evidence["always_output_data"] = always_output
        if always_output:
            score += 0.15

        # Check for retry settings
        parameters = node.get("parameters", {})
        options = parameters.get("options", {})

        retry_on_fail = options.get("retryOnFail", False)
        evidence["retry_on_fail"] = retry_on_fail
        if retry_on_fail:
            score += 0.2

        max_retries = options.get("maxRetries", 0)
        evidence["max_retries"] = max_retries
        if max_retries > 0:
            score += 0.1

        # Check for timeout
        timeout = options.get("timeout", 0)
        evidence["timeout_ms"] = timeout
        if timeout > 0:
            score += 0.15
        else:
            suggestions.append("Add timeout to prevent hanging executions")

        # Check workflow context for error paths
        if workflow_context:
            connections = workflow_context.get("connections", {})
            node_id = node.get("id", "")
            node_connections = connections.get(node_id, {})

            has_error_output = "error" in node_connections or any(
                "error" in str(conn).lower() for conn in node_connections.values()
            )
            evidence["has_error_output"] = has_error_output
            if has_error_output:
                score += 0.15

        # Normalize score
        score = min(score, 1.0)

        if score < 0.5:
            issues.append("Limited error handling configuration")

        return DimensionScore(
            dimension=QualityDimension.ERROR_HANDLING.value,
            score=score,
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_tool_usage(self, node: Dict[str, Any]) -> DimensionScore:
        """
        Score tool integration quality.

        Checks for:
        - Tool definitions present
        - Tool descriptions
        - Parameter schemas
        - Tool count appropriateness
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.7  # Default for nodes without tools

        parameters = node.get("parameters", {})

        # Check for tools/functions
        tools = parameters.get("tools", [])
        functions = parameters.get("functions", [])
        all_tools = tools + functions

        evidence["tool_count"] = len(all_tools)

        if not all_tools:
            # No tools defined - check if agent type should have tools
            node_type = node.get("type", "")
            if "agent" in node_type.lower():
                suggestions.append("Consider adding tools for agent capabilities")
                return DimensionScore(
                    dimension=QualityDimension.TOOL_USAGE.value,
                    score=0.5,
                    issues=["Agent has no tools defined"],
                    evidence=evidence,
                    suggestions=suggestions,
                )
            return DimensionScore(
                dimension=QualityDimension.TOOL_USAGE.value,
                score=0.8,  # Non-agent nodes don't need tools
                issues=issues,
                evidence=evidence,
                suggestions=suggestions,
            )

        # Score tool quality
        tools_with_description = 0
        tools_with_schema = 0

        for tool in all_tools:
            if isinstance(tool, dict):
                if tool.get("description"):
                    tools_with_description += 1
                if tool.get("parameters") or tool.get("schema"):
                    tools_with_schema += 1

        evidence["tools_with_description"] = tools_with_description
        evidence["tools_with_schema"] = tools_with_schema

        # Calculate score
        if len(all_tools) > 0:
            desc_ratio = tools_with_description / len(all_tools)
            schema_ratio = tools_with_schema / len(all_tools)

            score = (desc_ratio * 0.5) + (schema_ratio * 0.3) + 0.2  # Base 0.2 for having tools

            if desc_ratio < 1.0:
                issues.append(f"{len(all_tools) - tools_with_description} tools missing descriptions")
                suggestions.append("Add descriptions to all tools for better agent understanding")

            if schema_ratio < 1.0:
                suggestions.append("Add parameter schemas to tools for type safety")

        # Check for excessive tools
        if len(all_tools) > 10:
            issues.append(f"Too many tools ({len(all_tools)}) may confuse the agent")
            suggestions.append("Consider reducing tool count or grouping related tools")
            score *= 0.8

        return DimensionScore(
            dimension=QualityDimension.TOOL_USAGE.value,
            score=min(score, 1.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_config_appropriateness(self, node: Dict[str, Any]) -> DimensionScore:
        """
        Score configuration settings appropriateness.

        Checks for:
        - Temperature setting for task type
        - Token limits
        - Model selection
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.7  # Default reasonable score

        parameters = node.get("parameters", {})
        options = parameters.get("options", {})

        # Extract model config
        model = parameters.get("model", options.get("model", ""))
        temperature = options.get("temperature", parameters.get("temperature"))
        max_tokens = options.get("maxTokens", parameters.get("maxTokens"))

        evidence["model"] = model
        evidence["temperature"] = temperature
        evidence["max_tokens"] = max_tokens

        # Check temperature
        if temperature is not None:
            # Infer task type from system prompt
            system_prompt = self._extract_system_prompt(node)
            task_type = self._infer_task_type(system_prompt)
            evidence["inferred_task_type"] = task_type

            recommended_range = TEMPERATURE_RECOMMENDATIONS.get(task_type, TEMPERATURE_RECOMMENDATIONS["default"])

            if recommended_range[0] <= temperature <= recommended_range[1]:
                score += 0.15
            else:
                issues.append(f"Temperature {temperature} may not be optimal for {task_type} tasks")
                suggestions.append(f"Consider temperature in range {recommended_range[0]}-{recommended_range[1]}")
                score -= 0.1

        # Check max tokens
        if max_tokens is not None:
            if max_tokens < 100:
                issues.append(f"Max tokens ({max_tokens}) may be too low")
                suggestions.append("Increase max tokens to avoid truncated responses")
                score -= 0.15
            elif max_tokens > 8000:
                suggestions.append("Consider if high token limit is necessary (cost implications)")

        # Check model selection
        if model:
            # Prefer specific models over auto-select
            if "auto" not in model.lower():
                score += 0.1

            # Check for appropriate model tier
            if any(term in model.lower() for term in ["haiku", "mini", "small"]):
                evidence["model_tier"] = "fast"
            elif any(term in model.lower() for term in ["opus", "pro", "large"]):
                evidence["model_tier"] = "powerful"
            else:
                evidence["model_tier"] = "standard"

        return DimensionScore(
            dimension=QualityDimension.CONFIG_APPROPRIATENESS.value,
            score=min(max(score, 0.0), 1.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _extract_system_prompt(self, node: Dict[str, Any]) -> Optional[str]:
        """Extract system prompt from various node configuration locations."""
        parameters = node.get("parameters", {})

        # Try common locations
        locations = [
            parameters.get("systemMessage"),
            parameters.get("systemPrompt"),
            parameters.get("system"),
            parameters.get("options", {}).get("systemMessage"),
            parameters.get("options", {}).get("systemPrompt"),
            parameters.get("text"),  # For some chat nodes
        ]

        for loc in locations:
            if loc and isinstance(loc, str):
                return loc

        return None

    def _assess_specificity(self, text: str) -> float:
        """Assess how specific/detailed the text is (vs generic)."""
        if not text:
            return 0.0

        # Check for specific indicators
        indicators = 0

        # Numbers and quantities
        if re.search(r'\d+', text):
            indicators += 1

        # Technical terms (capitalized words that aren't sentence starts)
        technical_terms = len(re.findall(r'(?<!^)(?<!\. )[A-Z][a-z]+', text))
        if technical_terms > 2:
            indicators += 1

        # Specific formats mentioned
        if any(fmt in text.lower() for fmt in ['json', 'xml', 'csv', 'markdown', 'yaml']):
            indicators += 1

        # Step-by-step or numbered instructions
        if re.search(r'(step \d|1\.|2\.|first|second|then)', text.lower()):
            indicators += 1

        # Domain-specific terminology
        if any(term in text.lower() for term in [
            'api', 'database', 'query', 'endpoint', 'schema',
            'function', 'parameter', 'return', 'validate',
        ]):
            indicators += 1

        return min(indicators / 3, 1.0)

    def _infer_task_type(self, system_prompt: Optional[str]) -> str:
        """Infer task type from system prompt for config recommendations."""
        if not system_prompt:
            return "default"

        prompt_lower = system_prompt.lower()

        if any(kw in prompt_lower for kw in ['code', 'programming', 'function', 'debug', 'implement']):
            return "code"
        elif any(kw in prompt_lower for kw in ['analyze', 'evaluate', 'assess', 'review', 'examine']):
            return "analysis"
        elif any(kw in prompt_lower for kw in ['creative', 'story', 'imagine', 'generate ideas', 'brainstorm']):
            return "creative"

        return "default"


def is_agent_node(node: Dict[str, Any]) -> bool:
    """Check if a node is an AI/agent node that should be scored.

    Returns True for agent nodes that have prompts.
    Returns False for LM config nodes (model configuration only).
    """
    node_type = node.get("type", "")
    # Exclude LM config nodes - they're just model settings
    if node_type in LM_CONFIG_NODE_TYPES:
        return False
    return node_type in AI_NODE_TYPES
