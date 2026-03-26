from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.webhook_security import redact_sensitive_data, compute_state_hash
from app.ingestion.base_provider import BaseProviderParser


@dataclass
class N8nNode:
    name: str
    type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    output: Any = None
    error: Optional[str] = None


@dataclass
class N8nExecution:
    id: str
    workflow_id: str
    workflow_name: str
    mode: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    nodes: List[N8nNode] = field(default_factory=list)


@dataclass
class ParsedN8nState:
    trace_id: str
    sequence_num: int
    agent_id: str
    state_delta: dict
    state_hash: str
    node_type: str
    latency_ms: int
    timestamp: datetime
    is_ai_node: bool = False
    ai_model: Optional[str] = None
    token_count: int = 0


class N8nParser(BaseProviderParser):
    # Substring patterns for identifying AI-relevant nodes during ingestion.
    # Uses `in` matching (not exact lookup) — includes partial type names.
    # For exact-match sets, see app.core.n8n_constants.
    AI_NODE_TYPES = [
        "n8n-nodes-base.openAi",
        "n8n-nodes-base.anthropic",
        "n8n-nodes-langchain.agent",
        "n8n-nodes-langchain.chainLlm",
        "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "@n8n/n8n-nodes-langchain.lmChatAnthropic",
        "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
        "n8n-nodes-base.httpRequest",
    ]

    def parse_raw(self, raw_data: Dict[str, Any]) -> N8nExecution:
        return self.parse_execution(raw_data)

    def extract_states(self, execution: N8nExecution, tenant_id: str, ingestion_mode: str = "full") -> List[ParsedN8nState]:
        return self.parse_to_states(execution, tenant_id, ingestion_mode=ingestion_mode)

    def parse_execution(self, raw_data: Dict[str, Any]) -> N8nExecution:
        started_at = self._parse_datetime(raw_data.get("startedAt"))
        finished_at = self._parse_datetime(raw_data.get("finishedAt"))

        nodes = []
        run_data = raw_data.get("data", {}).get("resultData", {}).get("runData", {})

        for node_name, node_runs in run_data.items():
            if not node_runs:
                continue

            for run in node_runs:
                node = N8nNode(
                    name=node_name,
                    type=run.get("source", [{}])[0].get("type", "unknown") if run.get("source") else "unknown",
                    parameters=run.get("parameters", {}),
                    execution_time_ms=run.get("executionTime", 0),
                    output=run.get("data", {}).get("main", [[]])[0] if run.get("data") else None,
                    error=run.get("error", {}).get("message") if run.get("error") else None,
                )
                nodes.append(node)

        return N8nExecution(
            id=raw_data.get("executionId", raw_data.get("id", "")),
            workflow_id=raw_data.get("workflowId", ""),
            workflow_name=raw_data.get("workflowName", ""),
            mode=raw_data.get("mode", "manual"),
            started_at=started_at,
            finished_at=finished_at,
            status=raw_data.get("status", "unknown"),
            nodes=nodes,
        )

    def parse_to_states(self, execution: N8nExecution, tenant_id: str, ingestion_mode: str = "full") -> List[ParsedN8nState]:
        states = []

        for seq, node in enumerate(execution.nodes):
            # Extract model config before redaction
            model_config = self._extract_model_config(node.parameters)

            # Extract thinking/reasoning from custom Claude node output
            reasoning = self._extract_reasoning(node.output)

            state_delta = self._redact_and_filter(
                {
                    "node_name": node.name,
                    "node_type": node.type,
                    "parameters": node.parameters,
                    "output": node.output,
                    "error": node.error,
                    "model_config": model_config,
                    "reasoning": reasoning,
                },
                skip_keys=["messages", "systemMessage", "prompt", "thinking", "reasoning"],
                content_keys=["parameters", "output", "reasoning"],
                ingestion_mode=ingestion_mode,
            )

            is_ai = self._is_ai_node(node)
            ai_model = None
            token_count = 0

            if is_ai:
                ai_model = node.parameters.get("model", node.parameters.get("modelId"))
                token_count = self._extract_token_count(node)

            states.append(ParsedN8nState(
                trace_id=execution.id,
                sequence_num=seq,
                agent_id=node.name,
                state_delta=state_delta,
                state_hash=self._compute_hash(state_delta),
                node_type=node.type,
                latency_ms=node.execution_time_ms,
                timestamp=execution.started_at,
                is_ai_node=is_ai,
                ai_model=ai_model,
                token_count=token_count,
            ))

        return states

    def _is_ai_node(self, node: N8nNode) -> bool:
        if any(ai_type in node.type for ai_type in self.AI_NODE_TYPES):
            return True

        if "openai" in node.name.lower() or "anthropic" in node.name.lower():
            return True
        if "llm" in node.name.lower() or "gpt" in node.name.lower():
            return True
        if "langchain" in node.type.lower():
            return True

        return False

    def _extract_token_count(self, node: N8nNode) -> int:
        if isinstance(node.output, list) and node.output:
            first_output = node.output[0] if node.output else {}
            if isinstance(first_output, dict):
                usage = first_output.get("usage", {})
                return usage.get("total_tokens", 0)
        return 0

    def _extract_model_config(self, parameters: dict) -> dict:
        """Extract model configuration from node parameters."""
        config = {}

        # Common LLM config fields
        if "temperature" in parameters:
            config["temperature"] = parameters["temperature"]
        if "maxTokens" in parameters:
            config["max_tokens"] = parameters["maxTokens"]
        if "topP" in parameters:
            config["top_p"] = parameters["topP"]
        if "topK" in parameters:
            config["top_k"] = parameters["topK"]
        if "frequencyPenalty" in parameters:
            config["frequency_penalty"] = parameters["frequencyPenalty"]
        if "presencePenalty" in parameters:
            config["presence_penalty"] = parameters["presencePenalty"]
        if "stop" in parameters:
            config["stop_sequences"] = parameters["stop"]

        # Extended thinking flag (if present)
        if "extendedThinking" in parameters or "extended_thinking" in parameters:
            config["extended_thinking"] = parameters.get("extendedThinking", parameters.get("extended_thinking"))

        return config

    def _extract_reasoning(self, output: list) -> Optional[str]:
        """Extract thinking/reasoning from node output (custom Claude node)."""
        if not isinstance(output, list) or not output:
            return None

        for item in output:
            if isinstance(item, dict) and "json" in item:
                json_data = item["json"]
                # Check for thinking field from custom Claude node
                if isinstance(json_data, dict) and "thinking" in json_data:
                    thinking = json_data["thinking"]
                    if thinking:
                        return thinking

        return None

    def extract_sub_workflow_links(
        self, execution: N8nExecution
    ) -> List[Dict[str, str]]:
        """Extract sub-workflow invocations from Execute Workflow nodes.

        Returns list of dicts with:
            parent_execution_id: this execution's ID
            child_workflow_id: the invoked workflow's ID
            node_name: which node triggered the invocation
        """
        links = []
        for node in execution.nodes:
            # n8n Execute Workflow node type
            if "executeWorkflow" in node.type or "ExecuteWorkflow" in node.name:
                child_wf_id = node.parameters.get("workflowId", "")
                if not child_wf_id:
                    # Try nested value format
                    wf_val = node.parameters.get("workflowId", {})
                    if isinstance(wf_val, dict):
                        child_wf_id = wf_val.get("value", "")
                if child_wf_id:
                    links.append({
                        "parent_execution_id": execution.id,
                        "child_workflow_id": str(child_wf_id),
                        "node_name": node.name,
                    })
        return links


n8n_parser = N8nParser()
