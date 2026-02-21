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
        """Parse JSON from LLM response text."""
        import re
        try:
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    @staticmethod
    def _parse_json_field(text: str, field: str) -> Optional[str]:
        """Parse a specific field from JSON in LLM response."""
        import re
        try:
            # Try to find the outermost JSON object
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                return parsed.get(field)
        except (json.JSONDecodeError, ValueError):
            pass
        return None
