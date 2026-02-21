"""Agent quality scorer with 5-dimension assessment."""

import re
from typing import Dict, Any, List, Optional
from .models import (
    AgentQualityScore,
    DimensionScore,
    QualityDimension,
    Severity,
)
from .error_codes import get_error_code


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

    Supports two-tier scoring:
    - Tier 1 (fast): Heuristic keyword/config analysis (~1ms)
    - Tier 2 (deep): LLM judge for semantic evaluation (~1-2s)

    When use_llm_judge=True, ALL dimensions get LLM evaluation.
    When use_llm_judge=False but a dimension score falls in the
    escalation_range, it can optionally be escalated to LLM.
    """

    def __init__(
        self,
        use_llm_judge: Optional[bool] = None,
        judge_model: str = "claude-3-5-haiku-20241022",
        escalation_range: tuple = (0.35, 0.65),
    ):
        import os
        if use_llm_judge is None:
            use_llm_judge = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))
        self.use_llm_judge = use_llm_judge
        self.judge_model = judge_model
        self.escalation_range = escalation_range
        self._judge = None
        if use_llm_judge:
            try:
                from ..evals.llm_judge import LLMJudge, JudgeModel
                model = JudgeModel(judge_model) if judge_model in [m.value for m in JudgeModel] else JudgeModel.CLAUDE_HAIKU
                self._judge = LLMJudge(model=model)
            except Exception:
                pass  # LLM judge unavailable, fall back to heuristic-only

    def score_agent(
        self,
        node: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None,
        execution_history: Optional[List[Dict[str, Any]]] = None,
        include_reasoning: bool = False,
    ) -> AgentQualityScore:
        """Score a single agent node across all quality dimensions."""
        agent_id = node.get("id", "unknown")
        agent_name = node.get("name", "Unnamed Agent")
        agent_type = node.get("type", "unknown")

        dimensions: List[DimensionScore] = []

        # Score each dimension (heuristic first, then optionally blend with LLM)
        dim_role = self._score_role_clarity(node)
        dim_output = self._score_output_consistency(node, execution_history)
        dim_error = self._score_error_handling(node, workflow_context)
        dim_tool = self._score_tool_usage(node)
        dim_config = self._score_config_appropriateness(node)

        # LLM blending: if LLM judge is available, enhance scores with semantic evaluation
        if self._judge:
            llm_methods = {
                "role_clarity": (dim_role, self._llm_score_role_clarity),
                "error_handling": (dim_error, self._llm_score_error_handling),
                "tool_usage": (dim_tool, self._llm_score_tool_usage),
                "config_appropriateness": (dim_config, self._llm_score_config),
            }
            for dim_name, (dim_obj, llm_method) in llm_methods.items():
                if self._should_use_llm(dim_obj.score):
                    try:
                        llm_result = llm_method(node)
                        dim_obj.score = self._blend_scores(dim_obj.score, llm_result, dim_obj)
                    except Exception:
                        dim_obj.evidence["scoring_tier"] = "heuristic_fallback"
                else:
                    dim_obj.evidence["scoring_tier"] = "heuristic"

        dimensions = [dim_role, dim_output, dim_error, dim_tool, dim_config]

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

        # Generate reasoning if requested
        reasoning = None
        if include_reasoning:
            reasoning = self._generate_agent_reasoning(
                agent_name, overall_score, dimensions, critical_issues
            )

        return AgentQualityScore(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_type=agent_type,
            overall_score=overall_score,
            dimensions=dimensions,
            issues_count=len(all_issues),
            critical_issues=critical_issues,
            reasoning=reasoning,
            metadata={
                "is_ai_node": agent_type in AI_NODE_TYPES,
                "scored_at": "fast",  # or "llm" if escalated
            },
        )

    def _generate_agent_reasoning(
        self,
        agent_name: str,
        overall_score: float,
        dimensions: List[DimensionScore],
        critical_issues: List[str],
    ) -> str:
        """Generate natural-language reasoning for agent quality score."""
        from .models import _score_to_grade

        grade = _score_to_grade(overall_score)
        parts = [f"Agent '{agent_name}' scored {overall_score:.0%} ({grade})."]

        for dim in dimensions:
            dim_summary = f"{dim.dimension.replace('_', ' ').title()}: {dim.score:.0%}"
            if dim.issues:
                dim_summary += f" — {dim.issues[0]}"
            elif dim.score >= 0.8:
                dim_summary += " — good"
            parts.append(dim_summary)

        if critical_issues:
            parts.append(f"Critical: {'; '.join(critical_issues[:3])}")

        return " ".join(parts)

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
            evidence["error_codes"] = ["QE-RC-001"]
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

        error_codes = []
        if role_matches == 0:
            issues.append("System prompt lacks explicit role definition")
            suggestions.append("Add 'You are a [specific role]' statement")
            error_codes.append("QE-RC-002")

        # Check for output format specification (25% weight)
        output_matches = sum(1 for kw in OUTPUT_FORMAT_KEYWORDS if kw in prompt_lower)
        evidence["output_format_keywords"] = output_matches
        output_score = min(output_matches / 2, 1.0)
        score += output_score * 0.25

        if output_matches == 0:
            issues.append("No output format specification")
            suggestions.append("Specify expected output format (e.g., JSON schema)")
            error_codes.append("QE-RC-003")

        # Check for boundary keywords (20% weight)
        boundary_matches = sum(1 for kw in BOUNDARY_KEYWORDS if kw in prompt_lower)
        evidence["boundary_keywords"] = boundary_matches
        boundary_score = min(boundary_matches / 2, 1.0)
        score += boundary_score * 0.2

        if boundary_matches == 0:
            suggestions.append("Add boundary constraints (e.g., 'Do not...')")
            error_codes.append("QE-RC-004")

        # Check prompt length/detail (15% weight)
        word_count = len(system_prompt.split())
        evidence["word_count"] = word_count
        # 50+ words is ideal, scale from 20-80
        length_score = min(max((word_count - 20) / 60, 0), 1.0)
        score += length_score * 0.15

        if word_count < 30:
            issues.append(f"System prompt is too brief ({word_count} words)")
            suggestions.append("Expand prompt with more specific instructions")
            error_codes.append("QE-RC-005")

        # Check for specificity - named entities or domain terms (10% weight)
        specificity_score = self._assess_specificity(system_prompt)
        evidence["specificity_score"] = specificity_score
        score += specificity_score * 0.1

        # Anti-gaming: detect keyword stuffing
        if self._detect_keyword_stuffing(system_prompt):
            evidence["keyword_stuffing_detected"] = True
            issues.append("Keyword stuffing detected — prompt contains repeated keywords without substance")
            score = min(score, 0.4)  # Cap at 0.4 for stuffed prompts

        if error_codes:
            evidence["error_codes"] = error_codes

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
        score = 0.65  # Neutral provisional — no history means we don't know yet

        # Check if JSON output is expected
        system_prompt = self._extract_system_prompt(node)
        expects_json = False
        if system_prompt:
            expects_json = "json" in system_prompt.lower()
            evidence["expects_json"] = expects_json
            # Bump score if the prompt at least specifies an output format
            if expects_json:
                score = 0.72  # Output format specified but unverified

        if not execution_history:
            evidence["execution_samples"] = 0
            evidence["score_provisional"] = True
            evidence["error_codes"] = ["QE-OC-001"] if not expects_json else ["QE-OC-001", "QE-OC-003"]
            issues.append("No execution history — output consistency is unverified")
            if expects_json:
                suggestions.append("Run executions to validate JSON output consistency")
            else:
                suggestions.append("Add output format specification and run executions to verify consistency")
            return DimensionScore(
                dimension=QualityDimension.OUTPUT_CONSISTENCY.value,
                score=score,
                issues=issues,
                evidence=evidence,
                suggestions=suggestions,
                is_provisional=True,
            )

        evidence["execution_samples"] = len(execution_history)

        # Analyze execution outputs
        outputs = [e.get("output", {}) for e in execution_history if e.get("output")]

        if len(outputs) < 2:
            return DimensionScore(
                dimension=QualityDimension.OUTPUT_CONSISTENCY.value,
                score=0.5,  # Some history but not enough to evaluate
                issues=["Insufficient execution samples for consistency analysis"],
                evidence=evidence,
                suggestions=["Run more executions to build consistency baseline"],
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
                evidence["error_codes"] = ["QE-OC-002"]

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
        Score error handling capability for this individual agent node.

        BOUNDARY CLARIFICATION:
        This scores whether the INDIVIDUAL NODE can recover from failures.
        It answers: "Can this agent gracefully handle its own errors?"

        This is distinct from orchestration-level best practices scoring,
        which evaluates WORKFLOW-WIDE error handling coverage and patterns.

        Agent error handling (this method):
        - Per-node retry, timeout, continueOnFail configuration
        - Individual node's ability to recover from its own failures
        - Error output paths FROM this specific node

        Orchestration best practices (separate scorer):
        - Workflow-wide error handler presence
        - Coverage patterns across all nodes
        - Error branching and recovery flows

        Checks for:
        - continueOnFail flag (25%) - graceful failure handling
        - alwaysOutputData flag (15%) - consistent output even on partial failure
        - Retry settings (20%) - transient error recovery
        - Timeout (15%) - prevent hanging
        - Error output paths (15%) - downstream error handling
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.0

        eh_error_codes = []

        # Check continueOnFail
        continue_on_fail = node.get("continueOnFail", False)
        evidence["continue_on_fail"] = continue_on_fail
        if continue_on_fail:
            score += 0.25
        else:
            suggestions.append("Consider enabling 'Continue on Fail' for graceful error handling")
            eh_error_codes.append("QE-EH-003")

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
        else:
            eh_error_codes.append("QE-EH-001")

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
            eh_error_codes.append("QE-EH-002")

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

        # Anti-gaming: error handling flags without a meaningful system prompt are less meaningful
        system_prompt = self._extract_system_prompt(node)
        if not system_prompt and score > 0.5:
            evidence["no_prompt_penalty"] = True
            issues.append("Error handling configured but agent has no system prompt — recovery behavior is undefined")
            score = min(score, 0.5)
        elif system_prompt and self._detect_keyword_stuffing(system_prompt) and score > 0.5:
            evidence["stuffed_prompt_penalty"] = True
            issues.append("Error handling configured but system prompt is keyword-stuffed — recovery context is unreliable")
            score = min(score, 0.5)

        if score < 0.5:
            issues.append("Limited error handling configuration")

        if eh_error_codes:
            evidence["error_codes"] = eh_error_codes

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

        # Check for tools/functions - handle both list and dict formats
        tools = parameters.get("tools", [])
        if isinstance(tools, dict):
            # Handle n8n format: {"values": [...]}
            tools = tools.get("values", [])
        elif not isinstance(tools, list):
            tools = []

        functions = parameters.get("functions", [])
        if isinstance(functions, dict):
            functions = functions.get("values", [])
        elif not isinstance(functions, list):
            functions = []

        all_tools = tools + functions

        evidence["tool_count"] = len(all_tools)

        if not all_tools:
            # No tools defined - check if agent type should have tools
            node_type = node.get("type", "")
            if "agent" in node_type.lower():
                suggestions.append("Consider adding tools for agent capabilities")
                evidence["error_codes"] = ["QE-TU-001"]
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
        tu_error_codes = []
        if len(all_tools) > 0:
            desc_ratio = tools_with_description / len(all_tools)
            schema_ratio = tools_with_schema / len(all_tools)

            score = (desc_ratio * 0.5) + (schema_ratio * 0.3) + 0.2  # Base 0.2 for having tools

            if desc_ratio < 1.0:
                issues.append(f"{len(all_tools) - tools_with_description} tools missing descriptions")
                suggestions.append("Add descriptions to all tools for better agent understanding")
                tu_error_codes.append("QE-TU-002")

            if schema_ratio < 1.0:
                suggestions.append("Add parameter schemas to tools for type safety")
                tu_error_codes.append("QE-TU-003")

        # Check for excessive tools
        if len(all_tools) > 10:
            issues.append(f"Too many tools ({len(all_tools)}) may confuse the agent")
            suggestions.append("Consider reducing tool count or grouping related tools")
            score *= 0.8
            tu_error_codes.append("QE-TU-004")

        # Anti-gaming: penalize duplicate/near-duplicate descriptions
        dup_penalty = self._detect_duplicate_tool_descriptions(all_tools)
        if dup_penalty < 1.0:
            evidence["duplicate_descriptions_penalty"] = round(dup_penalty, 2)
            issues.append("Some tools have identical or near-identical descriptions")
            score *= dup_penalty

        if tu_error_codes:
            evidence["error_codes"] = tu_error_codes

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

        ca_error_codes = []

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
                ca_error_codes.append("QE-CA-001")

        # Check max tokens
        if max_tokens is not None:
            if max_tokens < 100:
                issues.append(f"Max tokens ({max_tokens}) may be too low")
                suggestions.append("Increase max tokens to avoid truncated responses")
                score -= 0.15
                ca_error_codes.append("QE-CA-002")
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
        else:
            ca_error_codes.append("QE-CA-003")

        if ca_error_codes:
            evidence["error_codes"] = ca_error_codes

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

    # --- LLM-Based Scoring Methods ---

    def _should_use_llm(self, heuristic_score: float) -> bool:
        """Determine if LLM evaluation should be used for this score."""
        if not self._judge:
            return False
        if self.use_llm_judge:
            return True
        # Escalate ambiguous scores
        return self.escalation_range[0] < heuristic_score < self.escalation_range[1]

    def _llm_score_role_clarity(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use LLM to semantically evaluate role clarity."""
        if not self._judge:
            return None
        from .prompts import format_role_clarity_prompt
        prompt = format_role_clarity_prompt(
            system_prompt=self._extract_system_prompt(node) or "",
            agent_name=node.get("name", "Unknown"),
            agent_type=node.get("type", "unknown"),
        )
        result = self._judge.judge(
            eval_type=None,
            output="",
            custom_prompt=prompt,
        )
        return {"score": result.score, "reasoning": result.reasoning, "tokens": result.tokens_used}

    def _llm_score_error_handling(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use LLM to evaluate if error handling is appropriate for this agent's role."""
        if not self._judge:
            return None
        system_prompt = self._extract_system_prompt(node) or "(no prompt)"
        agent_name = node.get("name", "Unknown")
        parameters = node.get("parameters", {})
        options = parameters.get("options", {})

        config_summary = []
        if node.get("continueOnFail"):
            config_summary.append("continueOnFail=true")
        if options.get("retryOnFail"):
            config_summary.append(f"retry={options.get('maxRetries', 0)}")
        if options.get("timeout"):
            config_summary.append(f"timeout={options['timeout']}ms")
        if not config_summary:
            config_summary.append("no error handling configured")

        prompt = (
            f"Evaluate the error handling configuration for this agent.\n\n"
            f"Agent Name: {agent_name}\n"
            f"Agent Type: {node.get('type', 'unknown')}\n"
            f"System Prompt: {system_prompt[:500]}\n"
            f"Error Handling Config: {', '.join(config_summary)}\n\n"
            f"Score from 0.0 to 1.0 based on:\n"
            f"1. Is the error handling appropriate for what this agent does?\n"
            f"2. Are retry counts and timeouts reasonable for the task?\n"
            f"3. Would failures be handled gracefully or cause cascading issues?\n"
            f"4. Is there a meaningful prompt that defines error recovery behavior?\n\n"
            f"A node with all flags enabled but no system prompt should score LOW "
            f"because there's no context for what errors mean.\n\n"
            f'Respond ONLY with valid JSON: {{"score": <float>, "reasoning": "<explanation>"}}'
        )
        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        return {"score": result.score, "reasoning": result.reasoning, "tokens": result.tokens_used}

    def _llm_score_tool_usage(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use LLM to evaluate tool description quality."""
        if not self._judge:
            return None
        parameters = node.get("parameters", {})
        tools = parameters.get("tools", [])
        if isinstance(tools, dict):
            tools = tools.get("values", [])
        functions = parameters.get("functions", [])
        if isinstance(functions, dict):
            functions = functions.get("values", [])
        all_tools = (tools if isinstance(tools, list) else []) + (functions if isinstance(functions, list) else [])

        if not all_tools:
            return None  # No tools to evaluate

        tool_summary = "\n".join(
            f"- {t.get('name', '?')}: {t.get('description', '(no description)')}"
            for t in all_tools[:10] if isinstance(t, dict)
        )
        prompt = (
            f"Evaluate the quality of these tool definitions for an AI agent.\n\n"
            f"Agent: {node.get('name', 'Unknown')}\n"
            f"Tools:\n{tool_summary}\n\n"
            f"Score from 0.0 to 1.0:\n"
            f"- Are descriptions specific enough for the agent to know when to use each tool?\n"
            f"- Are they distinct from each other (not duplicates or near-duplicates)?\n"
            f"- Do they have meaningful parameter schemas?\n"
            f"- Generic descriptions like 'A useful tool' should score very low.\n\n"
            f'Respond ONLY with valid JSON: {{"score": <float>, "reasoning": "<explanation>"}}'
        )
        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        return {"score": result.score, "reasoning": result.reasoning, "tokens": result.tokens_used}

    def _llm_score_config(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use LLM to evaluate configuration appropriateness."""
        if not self._judge:
            return None
        system_prompt = self._extract_system_prompt(node) or "(no prompt)"
        parameters = node.get("parameters", {})
        options = parameters.get("options", {})

        prompt = (
            f"Evaluate if this agent's configuration is appropriate for its task.\n\n"
            f"Agent: {node.get('name', 'Unknown')}\n"
            f"System Prompt (first 300 chars): {system_prompt[:300]}\n"
            f"Temperature: {options.get('temperature', parameters.get('temperature', 'not set'))}\n"
            f"Max Tokens: {options.get('maxTokens', parameters.get('maxTokens', 'not set'))}\n"
            f"Model: {parameters.get('model', options.get('model', 'not set'))}\n\n"
            f"Score from 0.0 to 1.0:\n"
            f"- Is temperature appropriate for the task type?\n"
            f"- Are token limits sufficient for the expected output?\n"
            f"- Is the model tier suitable for task complexity?\n"
            f"- Config without a meaningful prompt should score LOW.\n\n"
            f'Respond ONLY with valid JSON: {{"score": <float>, "reasoning": "<explanation>"}}'
        )
        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        return {"score": result.score, "reasoning": result.reasoning, "tokens": result.tokens_used}

    def _blend_scores(
        self,
        heuristic_score: float,
        llm_result: Optional[Dict[str, Any]],
        dim_score: "DimensionScore",
    ) -> float:
        """Blend heuristic and LLM scores, annotating the dimension with reasoning."""
        if llm_result is None:
            return heuristic_score
        llm_score = llm_result["score"]
        tokens = llm_result.get("tokens", 0)
        reasoning = llm_result.get("reasoning", "")
        # If LLM call failed (0 tokens or API error), fall back to heuristic only
        if tokens == 0 or "API error" in reasoning or "Error" in reasoning[:20]:
            dim_score.evidence["llm_fallback"] = True
            dim_score.evidence["llm_error"] = reasoning
            return heuristic_score
        blended = 0.3 * heuristic_score + 0.7 * llm_score
        dim_score.evidence["llm_score"] = round(llm_score, 3)
        dim_score.evidence["heuristic_score"] = round(heuristic_score, 3)
        dim_score.evidence["llm_reasoning"] = reasoning
        dim_score.evidence["scoring_tier"] = "llm"
        dim_score.evidence["llm_tokens"] = tokens
        return blended

    # --- Anti-Gaming Guards ---

    def _detect_keyword_stuffing(self, text: str) -> bool:
        """Detect keyword repetition gaming in prompts.

        Catches two patterns:
        1. High keyword *occurrence* density — the same scoring keywords
           appear many times relative to total word count.
        2. Repeated phrases — the same keyword phrase appears more than
           twice, which is unlikely in a genuine prompt.
        """
        if not text:
            return False
        text_lower = text.lower()
        words = text_lower.split()
        word_count = len(words)
        if word_count < 10:
            return False

        all_keywords = ROLE_KEYWORDS + OUTPUT_FORMAT_KEYWORDS + BOUNDARY_KEYWORDS

        # Count total keyword *occurrences* (not just presence)
        total_occurrences = 0
        repeated_keywords = 0
        for kw in all_keywords:
            count = text_lower.count(kw)
            total_occurrences += count
            if count >= 2:
                repeated_keywords += 1

        # Pattern 1: multiple keywords are each repeated 2+ times in a SHORT prompt.
        # Long prompts (80+ words) naturally repeat keywords in detailed specifications.
        if repeated_keywords >= 3 and word_count < 80:
            return True

        # Pattern 2: high keyword occurrence density relative to word count
        if total_occurrences > 10 and word_count < 60:
            return True

        # Pattern 3: many distinct keywords present + few unique sentences
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        unique_sentences = len(set(s.lower() for s in sentences))
        distinct_keywords = sum(1 for kw in all_keywords if kw in text_lower)
        if distinct_keywords > 5 and unique_sentences < 3:
            return True

        # Pattern 4: keyword density ratio — catches gaming at any prompt length.
        # Genuine prompts use ~10-15% keyword density; gaming prompts >22%.
        if word_count >= 10:
            density = total_occurrences / word_count
            if density > 0.22:
                return True

        return False

    def _detect_duplicate_tool_descriptions(self, tools: List[Dict[str, Any]]) -> float:
        """Return penalty factor for duplicate/near-duplicate tool descriptions."""
        descriptions = [t.get("description", "").lower().strip() for t in tools if isinstance(t, dict)]
        descriptions = [d for d in descriptions if d]
        if len(descriptions) < 2:
            return 1.0  # No penalty
        unique = len(set(descriptions))
        if unique < len(descriptions):
            # Penalize proportionally
            return max(0.5, unique / len(descriptions))
        return 1.0


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
