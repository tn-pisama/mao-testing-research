from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.n8n_security import redact_sensitive_data, compute_state_hash


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


class N8nParser:
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
    
    def parse_to_states(self, execution: N8nExecution, tenant_id: str) -> List[ParsedN8nState]:
        states = []
        
        for seq, node in enumerate(execution.nodes):
            state_delta = redact_sensitive_data({
                "node_name": node.name,
                "node_type": node.type,
                "parameters": node.parameters,
                "output": node.output,
                "error": node.error,
            })
            
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
                state_hash=compute_state_hash(state_delta),
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
    
    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        if not dt_str:
            return datetime.utcnow()
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return datetime.utcnow()


n8n_parser = N8nParser()
