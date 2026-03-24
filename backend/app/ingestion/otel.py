from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import json


@dataclass
class OTELSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: Dict[str, Any]
    status: Dict[str, Any]
    events: List[Dict[str, Any]]


@dataclass
class ParsedState:
    trace_id: str
    sequence_num: int
    agent_id: str
    state_delta: dict
    state_hash: str
    prompt: Optional[str]
    response: Optional[str]
    tool_calls: Optional[List[dict]]
    token_count: int
    latency_ms: int
    timestamp: datetime
    # Harness-aware fields
    agent_role: Optional[str] = None  # planner/generator/evaluator/orchestrator/tool
    sprint_id: Optional[str] = None
    context_reset: bool = False


class OTELParser:
    AGENT_ATTRIBUTES = [
        "gen_ai.agent.name",
        "langgraph.node.name",
        "crewai.agent.role",
        "autogen.agent.name",
        "openclaw.agent.name",
    ]

    STATE_ATTRIBUTES = [
        "gen_ai.state",
        "langgraph.state",
        "crewai.state",
        "openclaw.session.state",
    ]
    
    def parse_spans(self, spans: List[Dict[str, Any]]) -> List[ParsedState]:
        parsed_states = []
        trace_sequence = {}
        
        sorted_spans = sorted(spans, key=lambda s: s.get("startTimeUnixNano", 0))
        
        for span in sorted_spans:
            otel_span = self._normalize_span(span)
            
            if not self._is_agent_span(otel_span):
                continue
            
            trace_id = otel_span.trace_id
            if trace_id not in trace_sequence:
                trace_sequence[trace_id] = 0
            
            state_delta = self._extract_state_delta(otel_span)
            agent_id = self._extract_agent_id(otel_span)
            prompt = self._extract_prompt(otel_span)
            response = self._extract_response(otel_span)
            tool_calls = self._extract_tool_calls(otel_span)
            token_count = self._extract_token_count(otel_span)
            
            latency_ms = (otel_span.end_time_unix_nano - otel_span.start_time_unix_nano) // 1_000_000
            
            # Extract harness-aware fields from OTEL attributes
            attrs = otel_span.attributes
            agent_role = (
                attrs.get("gen_ai.agent.role")
                or attrs.get("pisama.agent.role")
                or None
            )
            sprint_id = attrs.get("pisama.sprint.id") or None
            context_reset = attrs.get("pisama.context.reset", "false") in ("true", "True", True, "1")

            parsed_states.append(ParsedState(
                trace_id=trace_id,
                sequence_num=trace_sequence[trace_id],
                agent_id=agent_id,
                state_delta=state_delta,
                state_hash=self._compute_hash(state_delta),
                prompt=prompt,
                response=response,
                tool_calls=tool_calls,
                token_count=token_count,
                latency_ms=latency_ms,
                timestamp=datetime.fromtimestamp(otel_span.start_time_unix_nano / 1e9),
                agent_role=agent_role,
                sprint_id=sprint_id,
                context_reset=context_reset,
            ))
            
            trace_sequence[trace_id] += 1
        
        return parsed_states
    
    def _normalize_span(self, span: Dict[str, Any]) -> OTELSpan:
        attributes = {}
        for attr in span.get("attributes", []):
            key = attr.get("key", "")
            value = attr.get("value", {})
            if "stringValue" in value:
                attributes[key] = value["stringValue"]
            elif "intValue" in value:
                attributes[key] = int(value["intValue"])
            elif "boolValue" in value:
                attributes[key] = value["boolValue"]
            elif "doubleValue" in value:
                attributes[key] = value["doubleValue"]
        
        return OTELSpan(
            trace_id=span.get("traceId", ""),
            span_id=span.get("spanId", ""),
            parent_span_id=span.get("parentSpanId"),
            name=span.get("name", ""),
            kind=span.get("kind", "SPAN_KIND_INTERNAL"),
            start_time_unix_nano=int(span.get("startTimeUnixNano", 0)),
            end_time_unix_nano=int(span.get("endTimeUnixNano", 0)),
            attributes=attributes,
            status=span.get("status", {}),
            events=span.get("events", []),
        )
    
    def _is_agent_span(self, span: OTELSpan) -> bool:
        for attr in self.AGENT_ATTRIBUTES:
            if attr in span.attributes:
                return True
        if span.name.startswith("openclaw."):
            return True
        if "agent" in span.name.lower() or "node" in span.name.lower():
            return True
        return False
    
    def _extract_agent_id(self, span: OTELSpan) -> str:
        for attr in self.AGENT_ATTRIBUTES:
            if attr in span.attributes:
                return span.attributes[attr]
        return span.name
    
    def _extract_state_delta(self, span: OTELSpan) -> dict:
        for attr in self.STATE_ATTRIBUTES:
            if attr in span.attributes:
                state_str = span.attributes[attr]
                try:
                    return json.loads(state_str)
                except json.JSONDecodeError:
                    return {"raw": state_str}
        return {}
    
    def _extract_prompt(self, span: OTELSpan) -> Optional[str]:
        prompt_keys = ["gen_ai.prompt", "llm.prompt", "input"]
        for key in prompt_keys:
            if key in span.attributes:
                return span.attributes[key]
        return None
    
    def _extract_response(self, span: OTELSpan) -> Optional[str]:
        response_keys = ["gen_ai.completion", "llm.completion", "output"]
        for key in response_keys:
            if key in span.attributes:
                return span.attributes[key]
        return None
    
    def _extract_tool_calls(self, span: OTELSpan) -> Optional[List[dict]]:
        tool_keys = ["gen_ai.tool_calls", "llm.tool_calls"]
        for key in tool_keys:
            if key in span.attributes:
                try:
                    return json.loads(span.attributes[key])
                except json.JSONDecodeError:
                    return None
        return None
    
    def _extract_token_count(self, span: OTELSpan) -> int:
        token_keys = ["gen_ai.usage.total_tokens", "llm.token_count"]
        for key in token_keys:
            if key in span.attributes:
                return int(span.attributes[key])
        return 0
    
    def _compute_hash(self, state_delta: dict) -> str:
        normalized = json.dumps(state_delta, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


otel_parser = OTELParser()
