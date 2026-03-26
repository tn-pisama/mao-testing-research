"""Tests for OTEL platform auto-detection and attribute extraction."""
import pytest
from app.ingestion.otel import OTELParser, OTELSpan


def _make_span(name="agent", attributes=None, trace_id="trace-1",
               start_ns=1000000000, end_ns=2000000000):
    """Create an OTEL span dict in the wire format."""
    attrs = []
    for k, v in (attributes or {}).items():
        if isinstance(v, str):
            attrs.append({"key": k, "value": {"stringValue": v}})
        elif isinstance(v, int):
            attrs.append({"key": k, "value": {"intValue": str(v)}})
        elif isinstance(v, bool):
            attrs.append({"key": k, "value": {"boolValue": v}})
        elif isinstance(v, float):
            attrs.append({"key": k, "value": {"doubleValue": v}})
    return {
        "traceId": trace_id,
        "spanId": "span-1",
        "name": name,
        "kind": "SPAN_KIND_INTERNAL",
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": attrs,
        "status": {},
        "events": [],
    }


class TestFrameworkDetection:
    """Test auto-detection of source framework from span attributes."""

    def test_detect_bedrock_from_gen_ai_system(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.system": "aws.bedrock",
            "gen_ai.agent.name": "claims-processor",
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "bedrock"

    def test_detect_bedrock_from_prefix(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "aws.bedrock.agent.id": "AGENT123",
            "aws.bedrock.model_id": "anthropic.claude-3-5-sonnet",
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "bedrock"

    def test_detect_vertex_from_gen_ai_system(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.system": "vertex_ai",
            "gen_ai.agent.name": "research-agent",
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "vertex_ai"

    def test_detect_vertex_from_gcp_prefix(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gcp.project_id": "my-project",
            "gen_ai.agent.name": "vertex-agent",
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "vertex_ai"

    def test_detect_crewai(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "crewai.agent.role": "researcher",
            "crewai.state": '{"task": "search"}',
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "crewai"

    def test_detect_langgraph(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "langgraph.node.name": "supervisor",
            "langgraph.state": '{"messages": []}',
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "langgraph"

    def test_detect_microsoft_agent_framework(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "microsoft.agent_framework.agent_type": "chat",
            "gen_ai.agent.name": "ms-agent",
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "microsoft_agent_framework"

    def test_detect_openai(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.system": "openai",
            "gen_ai.agent.name": "assistant",
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework == "openai"

    def test_unknown_framework_returns_none(self):
        parser = OTELParser()
        spans = [_make_span(name="agent", attributes={
            "gen_ai.agent.name": "generic-agent",
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].framework is None

    def test_detection_from_multiple_spans(self):
        """Framework detected from any span in the batch."""
        parser = OTELParser()
        spans = [
            _make_span(name="init", attributes={"gen_ai.agent.name": "init-step"},
                       start_ns=1000000000, end_ns=1500000000),
            _make_span(name="bedrock-call", attributes={
                "aws.bedrock.agent.id": "AGENT456",
                "gen_ai.agent.name": "processor",
            }, start_ns=1500000000, end_ns=2000000000),
        ]
        states = parser.parse_spans(spans)
        assert all(s.framework == "bedrock" for s in states)


class TestAttributeExtraction:
    """Test platform-specific attribute extraction."""

    def test_bedrock_agent_id_extracted(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "aws.bedrock.agent.id": "AGENTABC",
            "gen_ai.system": "aws.bedrock",
        })]
        states = parser.parse_spans(spans)
        assert states[0].agent_id == "AGENTABC"

    def test_bedrock_model_extracted(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.agent.name": "claims-agent",
            "aws.bedrock.model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "gen_ai.system": "aws.bedrock",
        })]
        states = parser.parse_spans(spans)
        assert states[0].model == "anthropic.claude-3-5-sonnet-20241022-v2:0"

    def test_vertex_project_in_platform_metadata(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.agent.name": "vertex-agent",
            "gen_ai.system": "vertex_ai",
            "gcp.project_id": "my-gcp-project",
            "gcp.region": "us-central1",
        })]
        states = parser.parse_spans(spans)
        meta = states[0].state_delta.get("platform_metadata", {})
        assert meta.get("gcp.project_id") == "my-gcp-project"
        assert meta.get("gcp.region") == "us-central1"

    def test_bedrock_guardrail_in_platform_metadata(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.agent.name": "safe-agent",
            "gen_ai.system": "aws.bedrock",
            "aws.bedrock.guardrail_id": "GUARD123",
            "aws.bedrock.knowledge_base.id": "KB456",
        })]
        states = parser.parse_spans(spans)
        meta = states[0].state_delta.get("platform_metadata", {})
        assert meta.get("aws.bedrock.guardrail_id") == "GUARD123"
        assert meta.get("aws.bedrock.knowledge_base.id") == "KB456"

    def test_standard_gen_ai_model_extracted(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.agent.name": "agent",
            "gen_ai.request.model": "claude-3-5-sonnet",
        })]
        states = parser.parse_spans(spans)
        assert states[0].model == "claude-3-5-sonnet"

    def test_token_count_from_input_plus_output(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.agent.name": "agent",
            "gen_ai.usage.input_tokens": 500,
            "gen_ai.usage.output_tokens": 200,
        })]
        states = parser.parse_spans(spans)
        assert states[0].token_count == 700


class TestBackwardCompatibility:
    """Ensure existing integrations still work."""

    def test_existing_langgraph_span(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "langgraph.node.name": "supervisor",
            "langgraph.state": '{"messages": ["hello"]}',
            "gen_ai.usage.total_tokens": 150,
        })]
        states = parser.parse_spans(spans)
        assert len(states) == 1
        assert states[0].agent_id == "supervisor"
        assert states[0].token_count == 150
        assert states[0].framework == "langgraph"

    def test_existing_crewai_span(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "crewai.agent.role": "researcher",
            "crewai.state": '{"task": "search web"}',
        })]
        states = parser.parse_spans(spans)
        assert states[0].agent_id == "researcher"
        assert states[0].framework == "crewai"

    def test_existing_autogen_span(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "autogen.agent.name": "assistant",
        })]
        states = parser.parse_spans(spans)
        assert states[0].agent_id == "assistant"

    def test_existing_openclaw_span(self):
        parser = OTELParser()
        spans = [_make_span(name="openclaw.session", attributes={
            "openclaw.agent.name": "whatsapp-bot",
        })]
        states = parser.parse_spans(spans)
        assert states[0].agent_id == "whatsapp-bot"
        assert states[0].framework == "openclaw"

    def test_harness_aware_fields_preserved(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.agent.name": "planner",
            "pisama.agent.role": "planner",
            "pisama.sprint.id": "sprint-3",
            "pisama.context.reset": "true",
        })]
        states = parser.parse_spans(spans)
        assert states[0].agent_role == "planner"
        assert states[0].sprint_id == "sprint-3"
        assert states[0].context_reset is True


class TestMultiPlatformTrace:
    """Test traces with spans from multiple platforms."""

    def test_mixed_platform_spans_use_first_detected(self):
        """When spans come from different platforms, use the first detected."""
        parser = OTELParser()
        spans = [
            _make_span(name="bedrock-agent", attributes={
                "gen_ai.system": "aws.bedrock",
                "gen_ai.agent.name": "orchestrator",
            }, start_ns=1000000000, end_ns=1500000000),
            _make_span(name="tool-call", attributes={
                "gen_ai.agent.name": "tool-executor",
            }, start_ns=1500000000, end_ns=2000000000),
        ]
        states = parser.parse_spans(spans)
        # Both states get the framework detected from the first span
        assert all(s.framework == "bedrock" for s in states)

    def test_latency_calculation(self):
        parser = OTELParser()
        spans = [_make_span(attributes={
            "gen_ai.agent.name": "agent",
        }, start_ns=1000000000, end_ns=3500000000)]  # 2.5 seconds
        states = parser.parse_spans(spans)
        assert states[0].latency_ms == 2500
