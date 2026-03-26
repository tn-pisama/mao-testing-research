"""OTEL Span Parser — Universal ingestion for OpenTelemetry traces.

Supports platform-specific attribute mappings for:
- LangGraph, CrewAI, AutoGen, OpenClaw (existing)
- Amazon Bedrock Agents (NEW)
- Google Vertex AI Agent Builder (NEW)
- Microsoft Agent Framework (NEW)

Auto-detects the source framework from span attributes using the
OpenTelemetry GenAI semantic conventions (gen_ai.system, gen_ai.provider.name).
"""

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
    agent_role: Optional[str] = None
    sprint_id: Optional[str] = None
    context_reset: bool = False
    # Platform metadata
    framework: Optional[str] = None
    model: Optional[str] = None


# Framework detection: gen_ai.system / gen_ai.provider.name → framework string
FRAMEWORK_MARKERS = {
    "aws.bedrock": "bedrock",
    "aws_bedrock": "bedrock",
    "bedrock": "bedrock",
    "vertex_ai": "vertex_ai",
    "google_vertex_ai": "vertex_ai",
    "gcp_vertex_ai": "vertex_ai",
    "openai": "openai",
    "anthropic": "anthropic",
    "azure.openai": "azure_openai",
}

# Attribute prefix → framework (fallback detection)
FRAMEWORK_PREFIXES = {
    "aws.bedrock.": "bedrock",
    "google.gen_ai.": "vertex_ai",
    "gcp.": "vertex_ai",
    "crewai.": "crewai",
    "langgraph.": "langgraph",
    "autogen.": "autogen",
    "openclaw.": "openclaw",
    "microsoft.": "microsoft_agent_framework",
    "agent_framework.": "microsoft_agent_framework",
}


class OTELParser:
    # Agent identification attributes (checked in priority order)
    AGENT_ATTRIBUTES = [
        "gen_ai.agent.name",         # GenAI standard (all platforms)
        "gen_ai.agent.id",           # GenAI standard agent ID
        "langgraph.node.name",       # LangGraph
        "crewai.agent.role",         # CrewAI
        "autogen.agent.name",        # AutoGen / Microsoft AF legacy
        "openclaw.agent.name",       # OpenClaw
        "aws.bedrock.agent.id",      # Bedrock agent ID
        "aws.bedrock.agent.alias",   # Bedrock agent alias
    ]

    # State attributes
    STATE_ATTRIBUTES = [
        "gen_ai.state",              # GenAI standard
        "gen_ai.system",             # GenAI system state (Bedrock, Vertex)
        "langgraph.state",           # LangGraph
        "crewai.state",              # CrewAI
        "openclaw.session.state",    # OpenClaw
    ]

    # Model identification
    MODEL_ATTRIBUTES = [
        "gen_ai.request.model",      # GenAI standard
        "gen_ai.response.model",     # Actual model used
        "aws.bedrock.model_id",      # Bedrock model ID
    ]

    # Provider/system identification
    PROVIDER_ATTRIBUTES = [
        "gen_ai.system",             # Primary: "aws.bedrock", "vertex_ai", "openai"
        "gen_ai.provider.name",      # Alternative
    ]

    # Platform-specific metadata to extract
    PLATFORM_METADATA = {
        "bedrock": [
            "aws.bedrock.invocation_id",
            "aws.bedrock.guardrail_id",
            "aws.bedrock.knowledge_base.id",
            "aws.bedrock.agent.collaborator.name",
        ],
        "vertex_ai": [
            "gcp.project_id",
            "gcp.region",
            "google.gen_ai.session_id",
            "google.gen_ai.memory_bank_id",
        ],
        "microsoft_agent_framework": [
            "microsoft.agent_framework.agent_type",
            "microsoft.agent_framework.session_id",
        ],
    }

    def parse_spans(self, spans: List[Dict[str, Any]]) -> List[ParsedState]:
        parsed_states = []
        trace_sequence = {}

        sorted_spans = sorted(spans, key=lambda s: s.get("startTimeUnixNano", 0))

        # Detect framework from all spans
        otel_spans = [self._normalize_span(s) for s in sorted_spans]
        detected_framework = self._detect_framework(otel_spans)

        for otel_span in otel_spans:
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
            model = self._extract_model(otel_span)

            latency_ms = (otel_span.end_time_unix_nano - otel_span.start_time_unix_nano) // 1_000_000

            attrs = otel_span.attributes
            agent_role = (
                attrs.get("gen_ai.agent.role")
                or attrs.get("pisama.agent.role")
                or None
            )
            sprint_id = attrs.get("pisama.sprint.id") or None
            context_reset = attrs.get("pisama.context.reset", "false") in ("true", "True", True, "1")

            # Extract platform-specific metadata into state_delta
            platform_meta = self._extract_platform_metadata(otel_span, detected_framework)
            if platform_meta:
                state_delta["platform_metadata"] = platform_meta

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
                framework=detected_framework,
                model=model,
            ))

            trace_sequence[trace_id] += 1

        return parsed_states

    def _detect_framework(self, spans: List[OTELSpan]) -> Optional[str]:
        """Auto-detect the source framework from span attributes.

        Checks (in priority order):
        1. gen_ai.system / gen_ai.provider.name for known platform values
        2. Attribute prefix scanning for framework-specific attributes
        """
        for span in spans:
            attrs = span.attributes

            # Check standard provider attributes
            for provider_attr in self.PROVIDER_ATTRIBUTES:
                provider = attrs.get(provider_attr, "")
                if provider:
                    framework = FRAMEWORK_MARKERS.get(str(provider).lower())
                    if framework:
                        return framework

            # Check attribute prefixes
            for attr_key in attrs:
                for prefix, framework in FRAMEWORK_PREFIXES.items():
                    if attr_key.startswith(prefix):
                        return framework

        return None

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
        for key in ["gen_ai.prompt", "gen_ai.content.prompt", "llm.prompt", "input"]:
            if key in span.attributes:
                return span.attributes[key]
        return None

    def _extract_response(self, span: OTELSpan) -> Optional[str]:
        for key in ["gen_ai.completion", "gen_ai.content.completion", "llm.completion", "output"]:
            if key in span.attributes:
                return span.attributes[key]
        return None

    def _extract_tool_calls(self, span: OTELSpan) -> Optional[List[dict]]:
        for key in ["gen_ai.tool_calls", "llm.tool_calls"]:
            if key in span.attributes:
                try:
                    return json.loads(span.attributes[key])
                except json.JSONDecodeError:
                    return None
        return None

    def _extract_token_count(self, span: OTELSpan) -> int:
        # Prefer explicit total
        for key in ["gen_ai.usage.total_tokens", "llm.token_count"]:
            if key in span.attributes:
                return int(span.attributes[key])
        # Sum input + output if both present
        inp = span.attributes.get("gen_ai.usage.input_tokens", 0)
        out = span.attributes.get("gen_ai.usage.output_tokens", 0)
        if inp or out:
            return int(inp) + int(out)
        return 0

    def _extract_model(self, span: OTELSpan) -> Optional[str]:
        """Extract the model name/ID from span attributes."""
        for attr in self.MODEL_ATTRIBUTES:
            if attr in span.attributes:
                return span.attributes[attr]
        return None

    def _extract_platform_metadata(
        self, span: OTELSpan, framework: Optional[str]
    ) -> Dict[str, Any]:
        """Extract platform-specific metadata for the detected framework."""
        if not framework:
            return {}
        meta_keys = self.PLATFORM_METADATA.get(framework, [])
        meta = {}
        for key in meta_keys:
            if key in span.attributes:
                meta[key] = span.attributes[key]
        return meta

    def _compute_hash(self, state_delta: dict) -> str:
        normalized = json.dumps(state_delta, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


otel_parser = OTELParser()
