"""LLM-powered contextual fix generator for quality healing.

Replaces generic boilerplate fixes with context-aware suggestions
that understand the agent's role, tools, and position in the workflow.
"""

import json
from typing import Dict, Any, List, Optional

from .models import QualityFixSuggestion, QualityFixCategory


class LLMContextualFixGenerator:
    """Generates agent-specific fixes using LLM analysis of workflow context.

    Unlike template-based generators that produce identical fixes for all
    agents of the same type, this generator analyzes:
    - The agent's current prompt and configuration
    - Connected tools and their descriptions
    - Downstream consumers (what nodes receive this agent's output)
    - The agent's role in the overall workflow graph
    """

    def __init__(self, judge=None):
        """
        Args:
            judge: LLMJudge instance. If None, will try to create one.
        """
        self._judge = judge
        if self._judge is None:
            try:
                from ...evals.llm_judge import LLMJudge, JudgeModel
                judge = LLMJudge(model=JudgeModel.CLAUDE_HAIKU)
                if judge.api_key:
                    self._judge = judge
            except Exception:
                pass

    @property
    def available(self) -> bool:
        """Whether LLM generation is available."""
        return self._judge is not None

    def generate_role_fix(
        self,
        node: Dict[str, Any],
        workflow_context: Dict[str, Any],
    ) -> Optional[QualityFixSuggestion]:
        """Generate a context-aware role clarity fix."""
        if not self._judge:
            return None

        agent_name = node.get("name", "Unknown")
        agent_type = node.get("type", "unknown")
        current_prompt = self._extract_prompt(node) or ""
        connected_tools = self._get_connected_tools(node, workflow_context)
        downstream = self._get_downstream_nodes(node, workflow_context)

        prompt = (
            f"Generate an improved system prompt for this agent.\n\n"
            f"Agent Name: {agent_name}\n"
            f"Agent Type: {agent_type}\n"
            f"Current Prompt: {current_prompt[:500] if current_prompt else '(empty)'}\n"
            f"Connected Tools: {', '.join(connected_tools) if connected_tools else 'none'}\n"
            f"Downstream Consumers: {', '.join(downstream) if downstream else 'none'}\n\n"
            f"Requirements:\n"
            f"1. Define a specific role based on the agent's name and tools\n"
            f"2. Specify output format appropriate for downstream consumers\n"
            f"3. Add task boundaries (what it should NOT do)\n"
            f"4. If the agent has tools, describe when to use each\n"
            f"5. Keep it concise but specific (60-120 words)\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"prompt": "<the improved system prompt>", '
            f'"reasoning": "<why this prompt is better>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)

        # Parse the generated prompt
        generated_prompt = self._parse_json_field(result.raw_response, "prompt")
        if not generated_prompt:
            return None

        return QualityFixSuggestion.create(
            dimension="role_clarity",
            category=QualityFixCategory.ROLE_CLARITY,
            title=f"LLM-generated role definition for {agent_name}",
            description=f"Context-aware prompt based on agent's tools ({len(connected_tools)}) and downstream consumers ({len(downstream)})",
            confidence=min(result.confidence, 0.85),
            expected_improvement=0.2,
            target_type="agent",
            target_id=node.get("id", agent_name),
            changes={
                "action": "set_system_prompt",
                "systemMessage": generated_prompt,
                "mode": "replace" if not current_prompt else "enhance",
            },
            metadata={
                "generation_method": "llm",
                "llm_reasoning": result.reasoning,
                "connected_tools": connected_tools,
                "downstream_consumers": downstream,
            },
        )

    def generate_error_handling_fix(
        self,
        node: Dict[str, Any],
        workflow_context: Dict[str, Any],
    ) -> Optional[QualityFixSuggestion]:
        """Generate context-aware error handling configuration."""
        if not self._judge:
            return None

        agent_name = node.get("name", "Unknown")
        current_prompt = self._extract_prompt(node) or "(no prompt)"
        connected_tools = self._get_connected_tools(node, workflow_context)

        prompt = (
            f"Recommend error handling configuration for this agent.\n\n"
            f"Agent: {agent_name}\n"
            f"Role: {current_prompt[:200]}\n"
            f"Tools: {', '.join(connected_tools) if connected_tools else 'none'}\n\n"
            f"Determine appropriate:\n"
            f"1. retryOnFail (true/false) and maxRetries (1-5)\n"
            f"2. timeout in ms (appropriate for the task type)\n"
            f"3. continueOnFail (true for non-critical, false for validators)\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"retryOnFail": <bool>, "maxRetries": <int>, "timeout": <int>, '
            f'"continueOnFail": <bool>, "reasoning": "<why these settings>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed:
            return None

        return QualityFixSuggestion.create(
            dimension="error_handling",
            category=QualityFixCategory.ERROR_HANDLING,
            title=f"Role-appropriate error handling for {agent_name}",
            description=f"Error handling tailored to agent's task: {parsed.get('reasoning', 'LLM-recommended')}",
            confidence=min(result.confidence, 0.8),
            expected_improvement=0.15,
            target_type="agent",
            target_id=node.get("id", agent_name),
            changes={
                "action": "configure_error_handling",
                "options": {
                    "retryOnFail": parsed.get("retryOnFail", True),
                    "maxRetries": min(max(parsed.get("maxRetries", 2), 1), 5),
                    "timeout": min(max(parsed.get("timeout", 30000), 5000), 300000),
                },
                "continueOnFail": parsed.get("continueOnFail", True),
            },
            metadata={"generation_method": "llm", "llm_reasoning": result.reasoning},
        )

    def generate_output_format_fix(
        self,
        node: Dict[str, Any],
        workflow_context: Dict[str, Any],
    ) -> Optional[QualityFixSuggestion]:
        """Generate context-aware output format specification."""
        if not self._judge:
            return None

        agent_name = node.get("name", "Unknown")
        current_prompt = self._extract_prompt(node) or ""
        downstream = self._get_downstream_nodes(node, workflow_context)

        prompt = (
            f"Generate an output format specification for this agent.\n\n"
            f"Agent: {agent_name}\n"
            f"Current Prompt: {current_prompt[:300] if current_prompt else '(empty)'}\n"
            f"Downstream Consumers: {', '.join(downstream) if downstream else 'unknown'}\n\n"
            f"Generate a JSON schema or format instruction that:\n"
            f"1. Matches what downstream nodes likely expect\n"
            f"2. Is specific to the agent's apparent task\n"
            f"3. Includes error/confidence fields\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"format_instruction": "<text to append to prompt>", '
            f'"reasoning": "<why this format>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        instruction = self._parse_json_field(result.raw_response, "format_instruction")
        if not instruction:
            return None

        return QualityFixSuggestion.create(
            dimension="output_consistency",
            category=QualityFixCategory.OUTPUT_CONSISTENCY,
            title=f"Output format spec for {agent_name}",
            description=f"Format specification based on downstream consumers: {', '.join(downstream[:3])}",
            confidence=min(result.confidence, 0.75),
            expected_improvement=0.15,
            target_type="agent",
            target_id=node.get("id", agent_name),
            changes={
                "action": "append_to_prompt",
                "text": f"\n\n## Output Format\n{instruction}",
            },
            metadata={"generation_method": "llm", "downstream": downstream},
        )

    def generate_tool_usage_fix(
        self,
        node: Dict[str, Any],
        workflow_context: Dict[str, Any],
    ) -> Optional[QualityFixSuggestion]:
        """Generate context-aware tool descriptions and schemas based on the agent's role."""
        if not self._judge:
            return None

        agent_name = node.get("name", "Unknown")
        agent_type = node.get("type", "unknown")
        current_prompt = self._extract_prompt(node) or "(no prompt)"
        connected_tools = self._get_connected_tools(node, workflow_context)

        prompt = (
            f"Suggest tool descriptions and parameter schemas for this agent.\n\n"
            f"Agent Name: {agent_name}\n"
            f"Agent Type: {agent_type}\n"
            f"Agent Role: {current_prompt[:300]}\n"
            f"Connected Tools: {', '.join(connected_tools) if connected_tools else 'none'}\n\n"
            f"For each connected tool (or suggest new ones if none exist):\n"
            f"1. Write a clear, concise description of what the tool does\n"
            f"2. Define input parameter schemas (JSON Schema format)\n"
            f"3. Explain when the agent should use this tool vs others\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"tools": [{{"name": "<tool_name>", "description": "<clear description>", '
            f'"parameters": {{"type": "object", "properties": {{...}}, "required": [...]}}, '
            f'"usage_guidance": "<when to use>"}}], '
            f'"reasoning": "<why these descriptions help>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed or "tools" not in parsed:
            return None

        tool_suggestions = parsed.get("tools", [])
        if not tool_suggestions:
            return None

        return QualityFixSuggestion.create(
            dimension="tool_usage",
            category=QualityFixCategory.TOOL_USAGE,
            title=f"LLM-generated tool descriptions for {agent_name}",
            description=f"Context-aware tool descriptions and schemas based on agent role: {parsed.get('reasoning', 'LLM-recommended')}",
            confidence=min(result.confidence, 0.80),
            expected_improvement=0.15,
            target_type="agent",
            target_id=node.get("id", agent_name),
            changes={
                "action": "modify_tools",
                "node_id": node.get("id", agent_name),
                "tool_definitions": tool_suggestions,
                "add_descriptions": True,
                "add_schemas": True,
            },
            metadata={
                "generation_method": "llm",
                "llm_reasoning": result.reasoning,
                "connected_tools": connected_tools,
                "suggested_tool_count": len(tool_suggestions),
            },
        )

    def generate_config_fix(
        self,
        node: Dict[str, Any],
        workflow_context: Dict[str, Any],
    ) -> Optional[QualityFixSuggestion]:
        """Generate context-aware temperature/model configuration based on the task type."""
        if not self._judge:
            return None

        agent_name = node.get("name", "Unknown")
        agent_type = node.get("type", "unknown")
        current_prompt = self._extract_prompt(node) or "(no prompt)"
        connected_tools = self._get_connected_tools(node, workflow_context)
        downstream = self._get_downstream_nodes(node, workflow_context)

        # Extract current config values
        params = node.get("parameters", {})
        options = params.get("options", {})
        current_temp = options.get("temperature")
        current_model = options.get("model")
        current_max_tokens = options.get("maxTokens")

        prompt = (
            f"Recommend optimal LLM configuration for this agent.\n\n"
            f"Agent Name: {agent_name}\n"
            f"Agent Type: {agent_type}\n"
            f"Agent Role: {current_prompt[:300]}\n"
            f"Connected Tools: {', '.join(connected_tools) if connected_tools else 'none'}\n"
            f"Downstream Consumers: {', '.join(downstream) if downstream else 'none'}\n"
            f"Current Config: temperature={current_temp}, model={current_model}, maxTokens={current_max_tokens}\n\n"
            f"Based on the agent's task type, recommend:\n"
            f"1. temperature (0.0-1.0): Lower for deterministic tasks like classification/extraction, "
            f"higher for creative tasks like writing/brainstorming\n"
            f"2. model: Best cost/performance tradeoff for this task type "
            f"(e.g., gpt-4o-mini for simple tasks, gpt-4o for complex reasoning)\n"
            f"3. maxTokens: Appropriate output length for the task\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"temperature": <float>, "model": "<model_name>", "maxTokens": <int>, '
            f'"task_type": "<classification|extraction|generation|reasoning|routing|other>", '
            f'"reasoning": "<why these settings match the task>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed:
            return None

        recommended_temp = parsed.get("temperature", 0.4)
        recommended_model = parsed.get("model", "gpt-4o")
        recommended_tokens = parsed.get("maxTokens", 2048)
        task_type = parsed.get("task_type", "other")

        # Clamp values to safe ranges
        recommended_temp = min(max(float(recommended_temp), 0.0), 1.0)
        recommended_tokens = min(max(int(recommended_tokens), 256), 8192)

        return QualityFixSuggestion.create(
            dimension="config_appropriateness",
            category=QualityFixCategory.CONFIG_APPROPRIATENESS,
            title=f"LLM-recommended config for {agent_name} ({task_type})",
            description=f"Configuration tuned for {task_type} task: {parsed.get('reasoning', 'LLM-recommended')}",
            confidence=min(result.confidence, 0.80),
            expected_improvement=0.12,
            target_type="agent",
            target_id=node.get("id", agent_name),
            changes={
                "action": "modify_options",
                "node_id": node.get("id", agent_name),
                "options": {
                    "temperature": recommended_temp,
                    "model": recommended_model,
                    "maxTokens": recommended_tokens,
                },
            },
            metadata={
                "generation_method": "llm",
                "llm_reasoning": result.reasoning,
                "task_type": task_type,
                "previous_config": {
                    "temperature": current_temp,
                    "model": current_model,
                    "maxTokens": current_max_tokens,
                },
            },
        )

    # --- Orchestration Dimension Generators ---

    def generate_data_flow_fix(
        self,
        workflow_context: Dict[str, Any],
        dimension_score: float,
        issues: List[str],
    ) -> Optional[QualityFixSuggestion]:
        """Generate a fix for data_flow_clarity issues (disconnected nodes, generic names, implicit state)."""
        if not self._judge:
            return None

        nodes = workflow_context.get("nodes", [])
        connections = workflow_context.get("connections", {})
        node_names = [n.get("name", "Unknown") for n in nodes[:20]]

        prompt = (
            f"Suggest fixes for data flow clarity issues in this n8n workflow.\n\n"
            f"Current Score: {dimension_score:.0%}\n"
            f"Issues: {'; '.join(issues) if issues else 'none flagged'}\n"
            f"Node Names: {', '.join(node_names)}\n"
            f"Connection Count: {len(connections)}\n"
            f"Node Count: {len(nodes)}\n\n"
            f"Provide n8n-specific fixes:\n"
            f"1. Identify disconnected or orphaned nodes\n"
            f"2. Suggest descriptive renames for generic node names\n"
            f"3. Replace implicit state passing with explicit connections\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"changes": [{{"type": "rename"|"connect"|"remove", '
            f'"node": "<name>", "value": "<new_name or target>"}}], '
            f'"explanation": "<why these fixes improve data flow>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed:
            return None

        return QualityFixSuggestion.create(
            dimension="data_flow_clarity",
            category=QualityFixCategory.DATA_FLOW_CLARITY,
            title="Improve workflow data flow clarity",
            description=parsed.get("explanation", "LLM-recommended data flow improvements"),
            confidence=min(result.confidence, 0.80),
            expected_improvement=0.15,
            target_type="orchestration",
            target_id="workflow",
            changes={
                "action": "fix_data_flow",
                "modifications": parsed.get("changes", []),
            },
            metadata={"generation_method": "llm", "llm_reasoning": result.reasoning},
        )

    def generate_complexity_fix(
        self,
        workflow_context: Dict[str, Any],
        dimension_score: float,
        issues: List[str],
    ) -> Optional[QualityFixSuggestion]:
        """Generate a fix for complexity_management issues (too many nodes, deep nesting, high branching)."""
        if not self._judge:
            return None

        nodes = workflow_context.get("nodes", [])
        node_types = [n.get("type", "unknown") for n in nodes]

        prompt = (
            f"Suggest fixes for workflow complexity issues in this n8n workflow.\n\n"
            f"Current Score: {dimension_score:.0%}\n"
            f"Issues: {'; '.join(issues) if issues else 'none flagged'}\n"
            f"Total Nodes: {len(nodes)}\n"
            f"Node Types: {', '.join(set(node_types))}\n\n"
            f"Provide n8n-specific fixes:\n"
            f"1. Identify groups of nodes to extract into sub-workflows\n"
            f"2. Suggest flattening deeply nested conditional branches\n"
            f"3. Recommend consolidating branching logic into Code nodes\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"changes": [{{"type": "extract_subworkflow"|"flatten"|"consolidate", '
            f'"nodes": ["<node_name>", ...], "description": "<what to do>"}}], '
            f'"explanation": "<why these changes reduce complexity>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed:
            return None

        return QualityFixSuggestion.create(
            dimension="complexity_management",
            category=QualityFixCategory.COMPLEXITY_MANAGEMENT,
            title="Reduce workflow complexity",
            description=parsed.get("explanation", "LLM-recommended complexity reduction"),
            confidence=min(result.confidence, 0.75),
            expected_improvement=0.18,
            target_type="orchestration",
            target_id="workflow",
            changes={
                "action": "reduce_complexity",
                "modifications": parsed.get("changes", []),
            },
            metadata={"generation_method": "llm", "llm_reasoning": result.reasoning},
        )

    def generate_observability_fix(
        self,
        workflow_context: Dict[str, Any],
        dimension_score: float,
        issues: List[str],
    ) -> Optional[QualityFixSuggestion]:
        """Generate a fix for observability issues (missing logging, error triggers, monitoring)."""
        if not self._judge:
            return None

        nodes = workflow_context.get("nodes", [])
        node_types = [n.get("type", "unknown") for n in nodes]
        has_error_trigger = any("errorTrigger" in t for t in node_types)

        prompt = (
            f"Suggest observability improvements for this n8n workflow.\n\n"
            f"Current Score: {dimension_score:.0%}\n"
            f"Issues: {'; '.join(issues) if issues else 'none flagged'}\n"
            f"Total Nodes: {len(nodes)}\n"
            f"Has Error Trigger: {has_error_trigger}\n"
            f"Node Types: {', '.join(set(node_types))}\n\n"
            f"Provide n8n-specific fixes:\n"
            f"1. Where to add checkpoint/logging nodes\n"
            f"2. Error Trigger configuration if missing\n"
            f"3. Monitoring integration (Datadog, Slack alerts, etc.)\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"changes": [{{"type": "add_checkpoint"|"add_error_trigger"|"add_monitoring", '
            f'"after_node": "<node_name>", "config": {{...}}}}], '
            f'"explanation": "<why these improve observability>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed:
            return None

        return QualityFixSuggestion.create(
            dimension="observability",
            category=QualityFixCategory.OBSERVABILITY,
            title="Improve workflow observability",
            description=parsed.get("explanation", "LLM-recommended observability improvements"),
            confidence=min(result.confidence, 0.80),
            expected_improvement=0.20,
            target_type="orchestration",
            target_id="workflow",
            changes={
                "action": "improve_observability",
                "modifications": parsed.get("changes", []),
            },
            metadata={
                "generation_method": "llm",
                "llm_reasoning": result.reasoning,
                "has_error_trigger": has_error_trigger,
            },
        )

    def generate_best_practices_fix(
        self,
        workflow_context: Dict[str, Any],
        dimension_score: float,
        issues: List[str],
    ) -> Optional[QualityFixSuggestion]:
        """Generate a fix for best_practices issues (missing global error handler, inconsistent retries, no timeout)."""
        if not self._judge:
            return None

        nodes = workflow_context.get("nodes", [])
        settings = workflow_context.get("settings", {})
        execution_timeout = settings.get("executionTimeout", "not set")

        # Gather retry configs across agent nodes
        retry_configs = []
        for n in nodes:
            opts = n.get("parameters", {}).get("options", {})
            if opts.get("retryOnFail") is not None:
                retry_configs.append(
                    f"{n.get('name', '?')}: maxTries={opts.get('maxRetries', 0)}, "
                    f"wait={opts.get('waitBetweenTries', 0)}"
                )

        prompt = (
            f"Suggest best-practice improvements for this n8n workflow.\n\n"
            f"Current Score: {dimension_score:.0%}\n"
            f"Issues: {'; '.join(issues) if issues else 'none flagged'}\n"
            f"Execution Timeout: {execution_timeout}\n"
            f"Retry Configs: {'; '.join(retry_configs) if retry_configs else 'none'}\n"
            f"Total Nodes: {len(nodes)}\n\n"
            f"Provide n8n-specific fixes:\n"
            f"1. Global error handler configuration\n"
            f"2. Standardized retry policy across all agents\n"
            f"3. Workflow-level execution timeout\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"changes": [{{"type": "set_timeout"|"standardize_retries"|"add_error_handler", '
            f'"config": {{...}}}}], '
            f'"explanation": "<why these align with best practices>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed:
            return None

        return QualityFixSuggestion.create(
            dimension="best_practices",
            category=QualityFixCategory.BEST_PRACTICES,
            title="Apply workflow best practices",
            description=parsed.get("explanation", "LLM-recommended best practice improvements"),
            confidence=min(result.confidence, 0.80),
            expected_improvement=0.15,
            target_type="orchestration",
            target_id="workflow",
            changes={
                "action": "apply_best_practices",
                "modifications": parsed.get("changes", []),
            },
            metadata={"generation_method": "llm", "llm_reasoning": result.reasoning},
        )

    def generate_ai_architecture_fix(
        self,
        workflow_context: Dict[str, Any],
        dimension_score: float,
        issues: List[str],
    ) -> Optional[QualityFixSuggestion]:
        """Generate a fix for ai_architecture issues (model selection, agent topology, prompt chaining)."""
        if not self._judge:
            return None

        nodes = workflow_context.get("nodes", [])
        # Collect agent-specific info
        agent_info = []
        for n in nodes:
            ntype = n.get("type", "")
            if "agent" in ntype.lower() or "chain" in ntype.lower():
                params = n.get("parameters", {})
                model = params.get("model", params.get("options", {}).get("model", "not set"))
                agent_info.append(f"{n.get('name', '?')}: type={ntype}, model={model}")

        prompt = (
            f"Suggest AI architecture improvements for this n8n workflow.\n\n"
            f"Current Score: {dimension_score:.0%}\n"
            f"Issues: {'; '.join(issues) if issues else 'none flagged'}\n"
            f"Agents: {'; '.join(agent_info) if agent_info else 'none'}\n"
            f"Total Nodes: {len(nodes)}\n\n"
            f"Provide n8n-specific fixes:\n"
            f"1. Model selection per agent (cost vs capability tradeoff)\n"
            f"2. Agent topology improvements (parallel vs serial, specialist vs generalist)\n"
            f"3. Prompt chaining and context window management\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"changes": [{{"type": "change_model"|"restructure_agents"|"optimize_prompts", '
            f'"agent": "<name>", "config": {{...}}}}], '
            f'"explanation": "<why these improve the AI architecture>"}}'
        )

        result = self._judge.judge(eval_type=None, output="", custom_prompt=prompt)
        parsed = self._parse_json(result.raw_response)
        if not parsed:
            return None

        return QualityFixSuggestion.create(
            dimension="ai_architecture",
            category=QualityFixCategory.AI_ARCHITECTURE,
            title="Improve AI architecture design",
            description=parsed.get("explanation", "LLM-recommended AI architecture improvements"),
            confidence=min(result.confidence, 0.75),
            expected_improvement=0.20,
            target_type="orchestration",
            target_id="workflow",
            changes={
                "action": "improve_ai_architecture",
                "modifications": parsed.get("changes", []),
            },
            metadata={
                "generation_method": "llm",
                "llm_reasoning": result.reasoning,
                "agent_count": len(agent_info),
            },
        )

    def enrich_fix(
        self,
        template_fix: QualityFixSuggestion,
        node: Dict[str, Any],
        workflow_context: Dict[str, Any],
    ) -> QualityFixSuggestion:
        """Enrich a template-generated fix with contextual LLM details.

        This is the bridge between template and LLM generators:
        take a generic fix and add context-specific content.
        """
        if not self._judge:
            return template_fix

        dimension = template_fix.dimension
        if dimension == "role_clarity":
            llm_fix = self.generate_role_fix(node, workflow_context)
            if llm_fix:
                # Replace the generic prompt with the LLM-generated one
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True
        elif dimension == "error_handling":
            llm_fix = self.generate_error_handling_fix(node, workflow_context)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.metadata["generation_method"] = "llm"
        elif dimension == "output_consistency":
            llm_fix = self.generate_output_format_fix(node, workflow_context)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.metadata["generation_method"] = "llm"
        elif dimension == "tool_usage":
            llm_fix = self.generate_tool_usage_fix(node, workflow_context)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True
        elif dimension == "config_appropriateness":
            llm_fix = self.generate_config_fix(node, workflow_context)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True
        # Orchestration dimensions
        elif dimension == "data_flow_clarity":
            issues = template_fix.metadata.get("issues", [])
            score = template_fix.metadata.get("score", 0.5)
            llm_fix = self.generate_data_flow_fix(workflow_context, score, issues)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True
        elif dimension == "complexity_management":
            issues = template_fix.metadata.get("issues", [])
            score = template_fix.metadata.get("score", 0.5)
            llm_fix = self.generate_complexity_fix(workflow_context, score, issues)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True
        elif dimension == "observability":
            issues = template_fix.metadata.get("issues", [])
            score = template_fix.metadata.get("score", 0.5)
            llm_fix = self.generate_observability_fix(workflow_context, score, issues)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True
        elif dimension == "best_practices":
            issues = template_fix.metadata.get("issues", [])
            score = template_fix.metadata.get("score", 0.5)
            llm_fix = self.generate_best_practices_fix(workflow_context, score, issues)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True
        elif dimension == "ai_architecture":
            issues = template_fix.metadata.get("issues", [])
            score = template_fix.metadata.get("score", 0.5)
            llm_fix = self.generate_ai_architecture_fix(workflow_context, score, issues)
            if llm_fix:
                template_fix.changes = llm_fix.changes
                template_fix.description = llm_fix.description
                template_fix.metadata["generation_method"] = "llm"
                template_fix.metadata["llm_enriched"] = True

        return template_fix

    # --- Helper Methods ---

    @staticmethod
    def _extract_prompt(node: Dict[str, Any]) -> Optional[str]:
        """Extract system prompt from node."""
        params = node.get("parameters", {})
        for key in ("systemMessage", "systemPrompt", "system", "text"):
            val = params.get(key) or params.get("options", {}).get(key)
            if val and isinstance(val, str):
                return val
        return None

    @staticmethod
    def _get_connected_tools(node: Dict[str, Any], workflow: Dict[str, Any]) -> List[str]:
        """Get names of tools connected to this agent."""
        tools = []
        params = node.get("parameters", {})
        tool_defs = params.get("tools", [])
        if isinstance(tool_defs, dict):
            tool_defs = tool_defs.get("values", [])
        if isinstance(tool_defs, list):
            for t in tool_defs:
                if isinstance(t, dict) and t.get("name"):
                    tools.append(t["name"])
        return tools

    @staticmethod
    def _get_downstream_nodes(node: Dict[str, Any], workflow: Dict[str, Any]) -> List[str]:
        """Get names of nodes that receive output from this node."""
        node_id = node.get("id", node.get("name", ""))
        downstream = []
        connections = workflow.get("connections", {})
        for src, outputs in connections.items():
            if src == node_id or src == node.get("name", ""):
                for output_group in outputs.get("main", []):
                    if isinstance(output_group, list):
                        for conn in output_group:
                            if isinstance(conn, dict):
                                downstream.append(conn.get("node", "unknown"))
        return downstream

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response text.

        Tries direct json.loads first, then falls back to extracting
        a JSON object by finding balanced braces. This handles nested
        objects correctly unlike regex-based approaches.
        """
        # Try parsing the entire text directly
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Fall back to extracting a JSON object by finding balanced braces
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except (json.JSONDecodeError, ValueError):
                        return None
        return None

    @staticmethod
    def _parse_json_field(text: str, field: str) -> Optional[str]:
        """Parse a specific field from JSON in LLM response.

        Uses proper json.loads with balanced-brace extraction instead
        of regex, which cannot handle nested JSON objects correctly.
        """
        # Try parsing the entire text directly
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict):
                return parsed.get(field)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fall back to extracting a JSON object by finding balanced braces
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start:i + 1])
                        return parsed.get(field)
                    except (json.JSONDecodeError, ValueError):
                        return None
        return None
