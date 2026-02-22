"""Agent-dimension quality fix generators.

Provides concrete fix suggestions for the five agent-level quality dimensions:
role_clarity, output_consistency, error_handling, tool_usage, and
config_appropriateness.  Each generator inspects the DimensionScore (including
score value and evidence dict) to decide which fixes to propose, and builds
QualityFixSuggestion objects with actionable ``changes`` dicts that describe
exact modifications to the n8n workflow JSON.
"""

from typing import Dict, Any, List

from ..models import DimensionScore
from .models import QualityFixSuggestion, QualityFixCategory
from .fix_generator import BaseQualityFixGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confidence_from_score(score: float, base: float = 0.7) -> float:
    """Lower dimension score -> higher confidence that the fix will help.

    Maps score 0.0 -> base+0.25 (capped at 0.95), score 0.7 -> base.
    """
    bonus = max(0.0, (0.7 - score)) * 0.35
    return min(round(base + bonus, 3), 0.95)


def _target_id(context: Dict[str, Any]) -> str:
    """Extract the target node / workflow id from the generator context."""
    return context.get("agent_id", context.get("workflow_id", "unknown"))


def _target_type(context: Dict[str, Any]) -> str:
    return context.get("target_type", "agent")


# ---------------------------------------------------------------------------
# 1. Role Clarity
# ---------------------------------------------------------------------------

class RoleClarityFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for the *role_clarity* dimension.

    Addresses missing or weak role definitions, output format specifications,
    and boundary constraints in agent system prompts.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == "role_clarity"

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        score = dimension_score.score
        evidence = dimension_score.evidence
        tid = _target_id(context)
        ttype = _target_type(context)
        agent_name = context.get("agent_name", "Agent")

        # Extract available context for smarter fixes
        system_prompt = context.get("system_prompt", "")
        workflow_name = context.get("workflow_name", "")
        connected_agents = context.get("connected_agents", [])

        # Fix 1 -- Add explicit role definition
        has_role = evidence.get("has_role_definition", False)

        # Check if there's already a role definition in the existing prompt
        _prompt_lower = system_prompt.lower() if system_prompt else ""
        _has_existing_role = any(
            marker in _prompt_lower
            for marker in ("you are a", "you are an", "your role is", "as a ", "as an ")
        )

        if (not has_role or score < 0.5) and not _has_existing_role:
            # Build a context-aware role definition
            role_parts = [f"You are a {agent_name}"]

            if workflow_name:
                role_parts.append(f"operating within the '{workflow_name}' workflow")

            if connected_agents:
                agent_list = ", ".join(connected_agents[:5])
                role_parts.append(
                    f"collaborating with the following agents: {agent_list}"
                )

            # If there's already a partial prompt, complement rather than duplicate
            if system_prompt:
                role_parts.append(
                    "Your role is to complement the instructions below by "
                    "processing inputs accurately and returning structured results"
                )
            else:
                role_parts.append(
                    "responsible for processing inputs accurately and "
                    "returning structured results"
                )

            role_text = ".  ".join(role_parts) + ".  "

            fixes.append(QualityFixSuggestion.create(
                dimension="role_clarity",
                category=QualityFixCategory.ROLE_CLARITY,
                title="Add role definition",
                description=(
                    f"The agent '{agent_name}' lacks a clear role definition in its "
                    "system message.  Prepend an explicit role statement so the LLM "
                    "understands its purpose, responsibilities, and limitations."
                    + (f"  Workflow context: '{workflow_name}'." if workflow_name else "")
                    + (f"  Connected agents: {', '.join(connected_agents[:3])}." if connected_agents else "")
                ),
                confidence=_confidence_from_score(score, base=0.80),
                expected_improvement=0.15 if score < 0.4 else 0.10,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_parameter",
                    "node_id": tid,
                    "parameter": "systemMessage",
                    "mode": "prepend",
                    "value": role_text,
                },
                code_example=(
                    '// n8n node parameter patch\n'
                    '{\n'
                    '  "systemMessage": "You are a [specific role]. '
                    'Your responsibility is ... " + existingMessage\n'
                    '}'
                ),
                effort="low",
            ))

        # Fix 2 -- Add output format specification
        has_format = evidence.get("has_output_format", False)
        if not has_format or score < 0.6:
            # Infer task type from agent name to suggest a relevant format
            _name_lower = agent_name.lower()
            if any(kw in _name_lower for kw in ("classif", "categor", "label", "tag")):
                format_value = (
                    "\n\nAlways respond in the following JSON format:\n"
                    '{"label": "<classification label>", "confidence": <0.0-1.0>, '
                    '"reasoning": "<brief explanation for the classification>"}'
                )
                format_hint = "classification output format"
            elif any(kw in _name_lower for kw in ("extract", "pars", "scrape")):
                format_value = (
                    "\n\nAlways respond in the following JSON format:\n"
                    '{"extracted_data": {<key-value pairs>}, "confidence": <0.0-1.0>, '
                    '"source_reference": "<where the data was found>"}'
                )
                format_hint = "extraction output format"
            elif any(kw in _name_lower for kw in ("summar", "digest")):
                format_value = (
                    "\n\nAlways respond in the following JSON format:\n"
                    '{"summary": "<concise summary>", "key_points": ["<point1>", "<point2>"], '
                    '"confidence": <0.0-1.0>}'
                )
                format_hint = "summarization output format"
            elif any(kw in _name_lower for kw in ("route", "dispatch", "direct")):
                format_value = (
                    "\n\nAlways respond in the following JSON format:\n"
                    '{"route_to": "<target agent or path>", "reasoning": "<why this route>", '
                    '"confidence": <0.0-1.0>}'
                )
                format_hint = "routing output format"
            elif any(kw in _name_lower for kw in ("valid", "check", "verify")):
                format_value = (
                    "\n\nAlways respond in the following JSON format:\n"
                    '{"is_valid": <true/false>, "errors": ["<error1>", "<error2>"], '
                    '"confidence": <0.0-1.0>}'
                )
                format_hint = "validation output format"
            else:
                format_value = (
                    "\n\nAlways respond in the following JSON format:\n"
                    '{"result": "<your answer>", "confidence": <0.0-1.0>, '
                    '"reasoning": "<brief explanation>"}'
                )
                format_hint = "general output format"

            fixes.append(QualityFixSuggestion.create(
                dimension="role_clarity",
                category=QualityFixCategory.ROLE_CLARITY,
                title="Add output format specification",
                description=(
                    f"Append a {format_hint} definition (JSON schema) "
                    "to the system message so downstream nodes receive predictable data."
                ),
                confidence=_confidence_from_score(score, base=0.75),
                expected_improvement=0.12 if score < 0.4 else 0.08,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_parameter",
                    "node_id": tid,
                    "parameter": "systemMessage",
                    "mode": "append",
                    "value": format_value,
                },
                code_example=(
                    '// Append to systemMessage\n'
                    'existingMessage + "\\n\\nAlways respond in the following JSON '
                    'format:\\n{\\"result\\": \\"...\\", \\"confidence\\": 0.0-1.0, '
                    '\\"reasoning\\": \\"...\\"}"'
                ),
                effort="low",
            ))

        # Fix 3 -- Add boundary constraints
        has_boundaries = evidence.get("has_boundaries", False)
        if not has_boundaries or score < 0.55:
            fixes.append(QualityFixSuggestion.create(
                dimension="role_clarity",
                category=QualityFixCategory.ROLE_CLARITY,
                title="Add boundary constraints",
                description=(
                    "Add explicit constraints to the system message that prevent the "
                    "agent from making unsupported assumptions, hallucinating data, or "
                    "exceeding its intended scope."
                ),
                confidence=_confidence_from_score(score, base=0.70),
                expected_improvement=0.08 if score < 0.4 else 0.05,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_parameter",
                    "node_id": tid,
                    "parameter": "systemMessage",
                    "mode": "append",
                    "value": (
                        "\n\nConstraints:\n"
                        "- Do not make assumptions about data you have not been given.\n"
                        "- If you are unsure, say so instead of guessing.\n"
                        "- Stay within your defined role; do not perform tasks "
                        "outside your scope."
                    ),
                },
                code_example=(
                    '// Append boundary constraints\n'
                    'existingMessage + "\\nConstraints:\\n'
                    '- Do not make assumptions...\\n'
                    '- If unsure, say so...\\n'
                    '- Stay within your defined role..."'
                ),
                effort="low",
            ))

        return fixes


# ---------------------------------------------------------------------------
# 2. Output Consistency
# ---------------------------------------------------------------------------

class OutputConsistencyFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for the *output_consistency* dimension.

    Targets schema enforcement and post-processing validation so that agent
    outputs are structurally consistent across executions.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == "output_consistency"

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        score = dimension_score.score
        evidence = dimension_score.evidence
        tid = _target_id(context)
        ttype = _target_type(context)

        # Fix 1 -- Add JSON schema enforcement in prompt
        has_schema = evidence.get("has_output_schema", False)
        if not has_schema or score < 0.6:
            fixes.append(QualityFixSuggestion.create(
                dimension="output_consistency",
                category=QualityFixCategory.OUTPUT_CONSISTENCY,
                title="Add JSON schema enforcement",
                description=(
                    "Embed a JSON schema definition directly in the system message "
                    "to enforce a stable output structure.  This significantly "
                    "reduces output format drift between runs."
                ),
                confidence=_confidence_from_score(score, base=0.75),
                expected_improvement=0.15 if score < 0.4 else 0.10,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_parameter",
                    "node_id": tid,
                    "parameter": "systemMessage",
                    "mode": "append",
                    "value": (
                        "\n\nYou MUST respond with valid JSON matching this schema:\n"
                        "{\n"
                        '  "type": "object",\n'
                        '  "required": ["output", "status"],\n'
                        '  "properties": {\n'
                        '    "output": {"type": "string"},\n'
                        '    "status": {"type": "string", "enum": ["success", "error", "partial"]}\n'
                        "  }\n"
                        "}"
                    ),
                },
                code_example=(
                    '// Append schema to systemMessage\n'
                    'systemMessage += "\\nYou MUST respond with valid JSON '
                    'matching this schema:\\n{...}"'
                ),
                effort="low",
            ))

        # Fix 2 -- Add a downstream validation node
        format_variance = evidence.get("format_variance", 0.0)
        if format_variance > 0.3 or score < 0.5:
            fixes.append(QualityFixSuggestion.create(
                dimension="output_consistency",
                category=QualityFixCategory.OUTPUT_CONSISTENCY,
                title="Add validation node",
                description=(
                    "Insert a Code node immediately after this agent to parse and "
                    "validate the output.  Invalid responses are caught before they "
                    "propagate to downstream nodes."
                ),
                confidence=_confidence_from_score(score, base=0.70),
                expected_improvement=0.12 if score < 0.4 else 0.08,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "add_node_after",
                    "after_node_id": tid,
                    "node": {
                        "type": "n8n-nodes-base.code",
                        "name": "Validate Output",
                        "parameters": {
                            "jsCode": (
                                "// Validate agent output structure\n"
                                "const items = $input.all();\n"
                                "for (const item of items) {\n"
                                "  const raw = item.json.output || item.json.text || '';\n"
                                "  try {\n"
                                "    const parsed = JSON.parse(raw);\n"
                                "    if (!parsed.output || !parsed.status) {\n"
                                "      throw new Error('Missing required fields');\n"
                                "    }\n"
                                "    item.json = parsed;\n"
                                "  } catch (e) {\n"
                                "    item.json = {\n"
                                "      output: raw,\n"
                                "      status: 'error',\n"
                                "      validation_error: e.message\n"
                                "    };\n"
                                "  }\n"
                                "}\n"
                                "return items;"
                            ),
                        },
                    },
                },
                code_example=(
                    "// Code node inserted after agent\n"
                    "const parsed = JSON.parse(item.json.output);\n"
                    "if (!parsed.output || !parsed.status) {\n"
                    "  throw new Error('Missing required fields');\n"
                    "}"
                ),
                breaking_changes=True,
                effort="medium",
            ))

        return fixes


# ---------------------------------------------------------------------------
# 3. Error Handling
# ---------------------------------------------------------------------------

class ErrorHandlingFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for the *error_handling* dimension.

    Ensures individual agent nodes have continueOnFail, retry policies,
    and appropriate timeouts configured.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == "error_handling"

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        score = dimension_score.score
        evidence = dimension_score.evidence
        tid = _target_id(context)
        ttype = _target_type(context)

        # Fix 1 -- Enable continueOnFail + alwaysOutputData
        has_continue = evidence.get("has_continue_on_fail", False)
        if not has_continue or score < 0.5:
            fixes.append(QualityFixSuggestion.create(
                dimension="error_handling",
                category=QualityFixCategory.ERROR_HANDLING,
                title="Enable continueOnFail",
                description=(
                    "Enable 'Continue On Fail' and 'Always Output Data' so the "
                    "workflow does not halt entirely when this node encounters an "
                    "error.  Downstream nodes can then inspect the error and decide "
                    "how to proceed."
                ),
                confidence=_confidence_from_score(score, base=0.85),
                expected_improvement=0.15 if score < 0.3 else 0.10,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_settings",
                    "node_id": tid,
                    "settings": {
                        "continueOnFail": True,
                        "alwaysOutputData": True,
                    },
                },
                code_example=(
                    '// Node settings patch\n'
                    '{\n'
                    '  "settings": {\n'
                    '    "continueOnFail": true,\n'
                    '    "alwaysOutputData": true\n'
                    '  }\n'
                    '}'
                ),
                effort="low",
            ))

        # Fix 2 -- Add retry configuration
        has_retry = evidence.get("has_retry", False)
        if not has_retry or score < 0.6:
            fixes.append(QualityFixSuggestion.create(
                dimension="error_handling",
                category=QualityFixCategory.ERROR_HANDLING,
                title="Add retry configuration",
                description=(
                    "Configure automatic retries with exponential back-off.  "
                    "Transient LLM API errors (rate limits, timeouts) are the most "
                    "common cause of agent failures and retries resolve the majority."
                ),
                confidence=_confidence_from_score(score, base=0.80),
                expected_improvement=0.12 if score < 0.3 else 0.08,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_settings",
                    "node_id": tid,
                    "settings": {
                        "retryOnFail": True,
                        "maxRetries": 3,
                        "waitBetweenTries": 1000,
                    },
                },
                code_example=(
                    '// Node settings patch\n'
                    '{\n'
                    '  "settings": {\n'
                    '    "retryOnFail": true,\n'
                    '    "maxRetries": 3,\n'
                    '    "waitBetweenTries": 1000\n'
                    '  }\n'
                    '}'
                ),
                effort="low",
            ))

        # Fix 3 -- Add timeout
        has_timeout = evidence.get("has_timeout", False)
        if not has_timeout or score < 0.55:
            fixes.append(QualityFixSuggestion.create(
                dimension="error_handling",
                category=QualityFixCategory.ERROR_HANDLING,
                title="Add execution timeout",
                description=(
                    "Set a 30-second execution timeout to prevent the node from "
                    "hanging indefinitely when the upstream LLM API is slow or "
                    "unresponsive."
                ),
                confidence=_confidence_from_score(score, base=0.75),
                expected_improvement=0.08 if score < 0.3 else 0.05,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_options",
                    "node_id": tid,
                    "options": {
                        "timeout": 30000,
                    },
                },
                code_example=(
                    '// Node options patch\n'
                    '{\n'
                    '  "options": {\n'
                    '    "timeout": 30000\n'
                    '  }\n'
                    '}'
                ),
                effort="low",
            ))

        return fixes


# ---------------------------------------------------------------------------
# 4. Tool Usage
# ---------------------------------------------------------------------------

class ToolUsageFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for the *tool_usage* dimension.

    Improves how agent nodes expose and describe the tools available to them,
    ensuring the LLM can discover and invoke them reliably.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == "tool_usage"

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        score = dimension_score.score
        evidence = dimension_score.evidence
        tid = _target_id(context)
        ttype = _target_type(context)

        # Fix 1 -- Add / improve tool descriptions
        tools_missing_desc = evidence.get("tools_missing_descriptions", 0)
        has_descriptions = evidence.get("has_tool_descriptions", True)
        if tools_missing_desc > 0 or not has_descriptions or score < 0.6:
            fixes.append(QualityFixSuggestion.create(
                dimension="tool_usage",
                category=QualityFixCategory.TOOL_USAGE,
                title="Add tool descriptions",
                description=(
                    "One or more tools connected to this agent lack human-readable "
                    "descriptions.  Adding clear descriptions helps the LLM select "
                    "the right tool and supply correct arguments."
                ),
                confidence=_confidence_from_score(score, base=0.75),
                expected_improvement=0.12 if score < 0.4 else 0.08,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_tools",
                    "node_id": tid,
                    "add_descriptions": True,
                },
                code_example=(
                    '// For each tool attached to the agent, ensure a description '
                    'is set:\n'
                    '{\n'
                    '  "tools": [\n'
                    '    {\n'
                    '      "name": "search_database",\n'
                    '      "description": "Search the product database by keyword. '
                    'Returns up to 10 matching results with id, name, and price.",\n'
                    '      ...\n'
                    '    }\n'
                    '  ]\n'
                    '}'
                ),
                effort="medium",
            ))

        # Fix 2 -- Add parameter schemas to tools
        tools_missing_schema = evidence.get("tools_missing_schemas", 0)
        has_schemas = evidence.get("has_parameter_schemas", True)
        if tools_missing_schema > 0 or not has_schemas or score < 0.55:
            fixes.append(QualityFixSuggestion.create(
                dimension="tool_usage",
                category=QualityFixCategory.TOOL_USAGE,
                title="Add parameter schemas",
                description=(
                    "Define explicit JSON Schema parameter definitions for each tool "
                    "so the LLM knows the expected argument types, required fields, "
                    "and valid value ranges."
                ),
                confidence=_confidence_from_score(score, base=0.70),
                expected_improvement=0.10 if score < 0.4 else 0.06,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_tools",
                    "node_id": tid,
                    "add_schemas": True,
                },
                code_example=(
                    '// Add JSON Schema for tool parameters:\n'
                    '{\n'
                    '  "tools": [\n'
                    '    {\n'
                    '      "name": "search_database",\n'
                    '      "parameters": {\n'
                    '        "type": "object",\n'
                    '        "required": ["query"],\n'
                    '        "properties": {\n'
                    '          "query": {"type": "string", '
                    '"description": "Search keyword"},\n'
                    '          "limit": {"type": "integer", "default": 10}\n'
                    '        }\n'
                    '      }\n'
                    '    }\n'
                    '  ]\n'
                    '}'
                ),
                effort="medium",
            ))

        return fixes


# ---------------------------------------------------------------------------
# 5. Config Appropriateness
# ---------------------------------------------------------------------------

class ConfigAppropriatenessFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for the *config_appropriateness* dimension.

    Recommends adjustments to temperature, max tokens, and model selection
    based on the agent's role and observed issues.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == "config_appropriateness"

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        score = dimension_score.score
        evidence = dimension_score.evidence
        tid = _target_id(context)
        ttype = _target_type(context)
        agent_type = context.get("agent_type", "")

        # Determine recommended temperature based on agent role
        current_temp = evidence.get("temperature", None)
        # Classification / extraction agents need low temp; creative agents higher
        is_deterministic_role = agent_type in (
            "classifier", "extractor", "validator", "router", "code",
        )
        recommended_temp = 0.1 if is_deterministic_role else 0.4

        # Fix 1 -- Adjust temperature
        temp_issue = evidence.get("temperature_issue", False)
        if temp_issue or current_temp is None or score < 0.6:
            fixes.append(QualityFixSuggestion.create(
                dimension="config_appropriateness",
                category=QualityFixCategory.CONFIG_APPROPRIATENESS,
                title="Adjust temperature",
                description=(
                    f"Set temperature to {recommended_temp} for this "
                    f"{'deterministic' if is_deterministic_role else 'general'} "
                    "agent.  The current value "
                    f"({'not set' if current_temp is None else current_temp}) "
                    "may cause inconsistent or overly creative outputs."
                ),
                confidence=_confidence_from_score(score, base=0.75),
                expected_improvement=0.10 if score < 0.4 else 0.06,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_options",
                    "node_id": tid,
                    "options": {
                        "temperature": recommended_temp,
                    },
                },
                code_example=(
                    f'// Set temperature for {"deterministic" if is_deterministic_role else "general"} agent\n'
                    '{\n'
                    '  "options": {\n'
                    f'    "temperature": {recommended_temp}\n'
                    '  }\n'
                    '}'
                ),
                effort="low",
            ))

        # Fix 2 -- Adjust max tokens
        current_tokens = evidence.get("max_tokens", None)
        # Use larger budget for complex agents, smaller for simple ones
        recommended_tokens = 1024 if is_deterministic_role else 2048
        tokens_issue = evidence.get("max_tokens_issue", False)
        if tokens_issue or current_tokens is None or score < 0.55:
            fixes.append(QualityFixSuggestion.create(
                dimension="config_appropriateness",
                category=QualityFixCategory.CONFIG_APPROPRIATENESS,
                title="Adjust max tokens",
                description=(
                    f"Set maxTokens to {recommended_tokens}.  Without an explicit "
                    "limit the model may produce excessively long responses that "
                    "waste tokens and slow down the workflow, or may truncate "
                    "important output prematurely."
                ),
                confidence=_confidence_from_score(score, base=0.70),
                expected_improvement=0.08 if score < 0.4 else 0.05,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_options",
                    "node_id": tid,
                    "options": {
                        "maxTokens": recommended_tokens,
                    },
                },
                code_example=(
                    '// Set max tokens\n'
                    '{\n'
                    '  "options": {\n'
                    f'    "maxTokens": {recommended_tokens}\n'
                    '  }\n'
                    '}'
                ),
                effort="low",
            ))

        # Fix 3 -- Optimize model selection
        current_model = evidence.get("model", None)
        model_issue = evidence.get("model_issue", False)
        # Recommend cost-effective defaults
        recommended_model = (
            "gpt-4o-mini" if is_deterministic_role else "gpt-4o"
        )
        if model_issue or score < 0.5:
            fixes.append(QualityFixSuggestion.create(
                dimension="config_appropriateness",
                category=QualityFixCategory.CONFIG_APPROPRIATENESS,
                title="Optimize model selection",
                description=(
                    f"Switch to '{recommended_model}' for this agent.  "
                    f"{'Deterministic tasks (classification, extraction) perform well with smaller, faster models.' if is_deterministic_role else 'Complex reasoning tasks benefit from more capable models.'}"
                    f"{(' Current model: ' + str(current_model) + '.') if current_model else ''}"
                ),
                confidence=_confidence_from_score(score, base=0.65),
                expected_improvement=0.10 if score < 0.4 else 0.06,
                target_type=ttype,
                target_id=tid,
                changes={
                    "action": "modify_options",
                    "node_id": tid,
                    "options": {
                        "model": recommended_model,
                    },
                },
                code_example=(
                    f'// Optimize model selection\n'
                    '{\n'
                    '  "options": {\n'
                    f'    "model": "{recommended_model}"\n'
                    '  }\n'
                    '}'
                ),
                effort="low",
                metadata={"previous_model": current_model},
            ))

        return fixes


# ---------------------------------------------------------------------------
# Convenience: register all agent fix generators at once
# ---------------------------------------------------------------------------

ALL_AGENT_FIX_GENERATORS: List[BaseQualityFixGenerator] = [
    RoleClarityFixGenerator(),
    OutputConsistencyFixGenerator(),
    ErrorHandlingFixGenerator(),
    ToolUsageFixGenerator(),
    ConfigAppropriatenessFixGenerator(),
]
