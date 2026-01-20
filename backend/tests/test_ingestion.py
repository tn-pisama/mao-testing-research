"""Comprehensive tests for ingestion modules (otel, import_parsers, buffer)."""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.ingestion.otel import OTELParser, OTELSpan, ParsedState, otel_parser
from app.ingestion.import_parsers import (
    ImportParser,
    LangSmithParser,
    LangfuseParser,
    GenericParser,
    ParsedRecord,
    get_parser,
    compute_file_hash,
    count_records,
)
from app.ingestion.buffer import AsyncBuffer, BufferConfig, BackpressureController


# ============================================================================
# OTELSpan Tests
# ============================================================================

class TestOTELSpan:
    """Tests for OTELSpan dataclass."""

    def test_create_span(self):
        """Should create OTELSpan with all fields."""
        span = OTELSpan(
            trace_id="trace123",
            span_id="span456",
            parent_span_id="parent789",
            name="test_span",
            kind="SPAN_KIND_INTERNAL",
            start_time_unix_nano=1000000000000000000,
            end_time_unix_nano=1000000001000000000,
            attributes={"key": "value"},
            status={"code": "OK"},
            events=[{"name": "event1"}],
        )

        assert span.trace_id == "trace123"
        assert span.span_id == "span456"
        assert span.parent_span_id == "parent789"
        assert span.name == "test_span"
        assert span.attributes == {"key": "value"}

    def test_create_span_without_parent(self):
        """Should create root span without parent."""
        span = OTELSpan(
            trace_id="trace123",
            span_id="span456",
            parent_span_id=None,
            name="root_span",
            kind="SPAN_KIND_SERVER",
            start_time_unix_nano=1000000000000000000,
            end_time_unix_nano=1000000001000000000,
            attributes={},
            status={},
            events=[],
        )

        assert span.parent_span_id is None


# ============================================================================
# OTELParser Tests
# ============================================================================

class TestOTELParser:
    """Tests for OTELParser class."""

    def test_parse_empty_spans(self):
        """Empty spans should return empty list."""
        parser = OTELParser()
        result = parser.parse_spans([])
        assert result == []

    def test_parse_single_agent_span(self):
        """Should parse a single agent span."""
        parser = OTELParser()
        spans = [{
            "traceId": "abc123",
            "spanId": "span1",
            "name": "agent_step",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000001000000000",
            "attributes": [
                {"key": "gen_ai.agent.name", "value": {"stringValue": "TestAgent"}},
                {"key": "gen_ai.prompt", "value": {"stringValue": "Hello"}},
                {"key": "gen_ai.completion", "value": {"stringValue": "Hi there"}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert len(result) == 1
        assert result[0].trace_id == "abc123"
        assert result[0].agent_id == "TestAgent"
        assert result[0].prompt == "Hello"
        assert result[0].response == "Hi there"

    def test_parse_langgraph_span(self):
        """Should parse LangGraph spans."""
        parser = OTELParser()
        spans = [{
            "traceId": "trace1",
            "spanId": "span1",
            "name": "graph_node",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000002000000000",
            "attributes": [
                {"key": "langgraph.node.name", "value": {"stringValue": "summarizer"}},
                {"key": "langgraph.state", "value": {"stringValue": "{\"key\": \"value\"}"}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert len(result) == 1
        assert result[0].agent_id == "summarizer"
        assert result[0].state_delta == {"key": "value"}
        assert result[0].latency_ms == 2000

    def test_parse_crewai_span(self):
        """Should parse CrewAI spans."""
        parser = OTELParser()
        spans = [{
            "traceId": "crew_trace",
            "spanId": "crew_span",
            "name": "crew_step",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000000500000000",
            "attributes": [
                {"key": "crewai.agent.role", "value": {"stringValue": "researcher"}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert len(result) == 1
        assert result[0].agent_id == "researcher"

    def test_parse_autogen_span(self):
        """Should parse AutoGen spans."""
        parser = OTELParser()
        spans = [{
            "traceId": "autogen_trace",
            "spanId": "autogen_span",
            "name": "autogen_step",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000000100000000",
            "attributes": [
                {"key": "autogen.agent.name", "value": {"stringValue": "assistant"}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert len(result) == 1
        assert result[0].agent_id == "assistant"

    def test_filter_non_agent_spans(self):
        """Should filter out non-agent spans."""
        parser = OTELParser()
        spans = [
            {
                "traceId": "trace1",
                "spanId": "span1",
                "name": "http_request",
                "startTimeUnixNano": "1000000000000000000",
                "endTimeUnixNano": "1000000001000000000",
                "attributes": [],
                "status": {},
                "events": [],
            },
            {
                "traceId": "trace1",
                "spanId": "span2",
                "name": "agent_step",
                "startTimeUnixNano": "1000000001000000000",
                "endTimeUnixNano": "1000000002000000000",
                "attributes": [],
                "status": {},
                "events": [],
            },
        ]

        result = parser.parse_spans(spans)

        assert len(result) == 1
        assert result[0].agent_id == "agent_step"

    def test_parse_span_with_all_attribute_types(self):
        """Should handle all attribute value types."""
        parser = OTELParser()
        spans = [{
            "traceId": "trace1",
            "spanId": "span1",
            "name": "agent_step",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000001000000000",
            "attributes": [
                {"key": "string_attr", "value": {"stringValue": "test"}},
                {"key": "int_attr", "value": {"intValue": "42"}},
                {"key": "bool_attr", "value": {"boolValue": True}},
                {"key": "double_attr", "value": {"doubleValue": 3.14}},
                {"key": "gen_ai.usage.total_tokens", "value": {"intValue": "100"}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert len(result) == 1
        assert result[0].token_count == 100

    def test_parse_tool_calls(self):
        """Should parse tool calls from span."""
        parser = OTELParser()
        tool_calls = [{"name": "search", "args": {"query": "test"}}]
        spans = [{
            "traceId": "trace1",
            "spanId": "span1",
            "name": "agent_step",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000001000000000",
            "attributes": [
                {"key": "gen_ai.tool_calls", "value": {"stringValue": json.dumps(tool_calls)}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert result[0].tool_calls == tool_calls

    def test_parse_invalid_tool_calls_json(self):
        """Should handle invalid JSON in tool calls."""
        parser = OTELParser()
        spans = [{
            "traceId": "trace1",
            "spanId": "span1",
            "name": "agent_step",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000001000000000",
            "attributes": [
                {"key": "gen_ai.tool_calls", "value": {"stringValue": "invalid json"}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert result[0].tool_calls is None

    def test_parse_invalid_state_json(self):
        """Should handle invalid JSON in state."""
        parser = OTELParser()
        spans = [{
            "traceId": "trace1",
            "spanId": "span1",
            "name": "agent_step",
            "startTimeUnixNano": "1000000000000000000",
            "endTimeUnixNano": "1000000001000000000",
            "attributes": [
                {"key": "gen_ai.state", "value": {"stringValue": "not valid json"}},
            ],
            "status": {},
            "events": [],
        }]

        result = parser.parse_spans(spans)

        assert result[0].state_delta == {"raw": "not valid json"}

    def test_sequence_numbering(self):
        """Should assign correct sequence numbers per trace."""
        parser = OTELParser()
        spans = [
            {
                "traceId": "trace1",
                "spanId": "span1",
                "name": "agent_step",
                "startTimeUnixNano": "1000000000000000000",
                "endTimeUnixNano": "1000000001000000000",
                "attributes": [],
                "status": {},
                "events": [],
            },
            {
                "traceId": "trace1",
                "spanId": "span2",
                "name": "agent_step",
                "startTimeUnixNano": "1000000001000000000",
                "endTimeUnixNano": "1000000002000000000",
                "attributes": [],
                "status": {},
                "events": [],
            },
            {
                "traceId": "trace2",
                "spanId": "span3",
                "name": "agent_step",
                "startTimeUnixNano": "1000000000500000000",
                "endTimeUnixNano": "1000000001500000000",
                "attributes": [],
                "status": {},
                "events": [],
            },
        ]

        result = parser.parse_spans(spans)

        assert result[0].sequence_num == 0
        assert result[1].sequence_num == 0  # Different trace, sorted by time
        assert result[2].sequence_num == 1

    def test_compute_state_hash(self):
        """Should compute consistent state hashes."""
        parser = OTELParser()

        hash1 = parser._compute_hash({"a": 1, "b": 2})
        hash2 = parser._compute_hash({"b": 2, "a": 1})  # Same content, different order
        hash3 = parser._compute_hash({"a": 1, "b": 3})  # Different content

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 16

    def test_singleton_parser(self):
        """otel_parser should be a singleton instance."""
        assert isinstance(otel_parser, OTELParser)


# ============================================================================
# ImportParser Tests
# ============================================================================

class TestImportParser:
    """Tests for ImportParser base class."""

    def test_detect_langsmith_format(self):
        """Should detect LangSmith format."""
        content = json.dumps({"run_type": "chain", "inputs": {}})
        assert ImportParser.detect_format(content) == "langsmith"

    def test_detect_langfuse_format(self):
        """Should detect Langfuse format with traces."""
        content = json.dumps({"traces": []})
        assert ImportParser.detect_format(content) == "langfuse"

    def test_detect_langfuse_observations_format(self):
        """Should detect Langfuse format with observations."""
        content = json.dumps({"observations": []})
        assert ImportParser.detect_format(content) == "langfuse"

    def test_detect_otlp_format(self):
        """Should detect OTLP format."""
        content = json.dumps({"resourceSpans": []})
        assert ImportParser.detect_format(content) == "otlp"

    def test_detect_otlp_trace_format(self):
        """Should detect OTLP format with traceId."""
        content = json.dumps({"traceId": "abc123"})
        assert ImportParser.detect_format(content) == "otlp"

    def test_detect_generic_format(self):
        """Should detect generic format with agent_id."""
        content = json.dumps({"agent_id": "test"})
        assert ImportParser.detect_format(content) == "generic"

    def test_detect_fallback_generic(self):
        """Should fall back to generic for unknown formats."""
        content = json.dumps({"some_field": "value"})
        assert ImportParser.detect_format(content) == "generic"

    def test_detect_invalid_json(self):
        """Should return None for invalid JSON."""
        content = "not valid json"
        assert ImportParser.detect_format(content) is None

    def test_detect_empty_content(self):
        """Should return None for empty content."""
        content = ""
        assert ImportParser.detect_format(content) is None


class TestLangSmithParser:
    """Tests for LangSmithParser class."""

    def test_parse_simple_record(self):
        """Should parse simple LangSmith record."""
        parser = LangSmithParser()
        content = json.dumps({
            "id": "run123",
            "session_id": "session456",
            "name": "TestChain",
            "run_type": "chain",
            "inputs": {"query": "test"},
            "outputs": {"result": "success"},
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T00:00:01Z",
        })

        records = list(parser.parse(content))

        assert len(records) == 1
        assert records[0].trace_id == "session456"
        assert records[0].span_id == "run123"
        assert records[0].name == "TestChain"
        assert records[0].inputs == {"query": "test"}
        assert records[0].outputs == {"result": "success"}

    def test_parse_with_tokens(self):
        """Should extract token counts."""
        parser = LangSmithParser()
        content = json.dumps({
            "id": "run123",
            "name": "LLM",
            "inputs": {},
            "outputs": {},
            "extra": {"tokens": 150},
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T00:00:01Z",
        })

        records = list(parser.parse(content))

        assert records[0].token_count == 150

    def test_parse_with_usage(self):
        """Should extract tokens from usage field."""
        parser = LangSmithParser()
        content = json.dumps({
            "id": "run123",
            "name": "LLM",
            "inputs": {},
            "outputs": {},
            "extra": {"usage": {"total_tokens": 200}},
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T00:00:01Z",
        })

        records = list(parser.parse(content))

        assert records[0].token_count == 200

    def test_parse_multiline(self):
        """Should parse multiple lines."""
        parser = LangSmithParser()
        line1 = json.dumps({"id": "1", "name": "A", "inputs": {}, "outputs": {}, "start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-01T00:00:01Z"})
        line2 = json.dumps({"id": "2", "name": "B", "inputs": {}, "outputs": {}, "start_time": "2024-01-01T00:00:01Z", "end_time": "2024-01-01T00:00:02Z"})
        content = f"{line1}\n{line2}"

        records = list(parser.parse(content))

        assert len(records) == 2
        assert records[0].name == "A"
        assert records[1].name == "B"

    def test_parse_invalid_json_line(self):
        """Should raise error for invalid JSON."""
        parser = LangSmithParser()
        content = "invalid json"

        with pytest.raises(ValueError, match="Invalid JSON"):
            list(parser.parse(content))

    def test_parse_with_parent_run_id(self):
        """Should capture parent run ID."""
        parser = LangSmithParser()
        content = json.dumps({
            "id": "child123",
            "parent_run_id": "parent456",
            "name": "ChildChain",
            "inputs": {},
            "outputs": {},
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T00:00:01Z",
        })

        records = list(parser.parse(content))

        assert records[0].parent_span_id == "parent456"


class TestLangfuseParser:
    """Tests for LangfuseParser class."""

    def test_parse_single_trace(self):
        """Should parse single Langfuse trace."""
        parser = LangfuseParser()
        content = json.dumps({
            "id": "trace123",
            "observations": [
                {
                    "id": "obs1",
                    "name": "llm-call",
                    "type": "generation",
                    "input": {"prompt": "Hello"},
                    "output": {"response": "Hi"},
                    "startTime": "2024-01-01T00:00:00Z",
                    "endTime": "2024-01-01T00:00:01Z",
                    "usage": {"totalTokens": 50},
                }
            ],
        })

        records = list(parser.parse(content))

        assert len(records) == 1
        assert records[0].trace_id == "trace123"
        assert records[0].span_id == "obs1"
        assert records[0].token_count == 50

    def test_parse_multiple_traces(self):
        """Should parse multiple Langfuse traces."""
        parser = LangfuseParser()
        content = json.dumps({
            "traces": [
                {
                    "id": "trace1",
                    "observations": [
                        {"id": "obs1", "name": "A", "startTime": "2024-01-01T00:00:00Z", "endTime": "2024-01-01T00:00:01Z"},
                    ],
                },
                {
                    "id": "trace2",
                    "observations": [
                        {"id": "obs2", "name": "B", "startTime": "2024-01-01T00:00:01Z", "endTime": "2024-01-01T00:00:02Z"},
                    ],
                },
            ],
        })

        records = list(parser.parse(content))

        assert len(records) == 2
        assert records[0].trace_id == "trace1"
        assert records[1].trace_id == "trace2"

    def test_parse_with_parent_observation(self):
        """Should capture parent observation ID."""
        parser = LangfuseParser()
        content = json.dumps({
            "id": "trace1",
            "observations": [
                {"id": "parent", "name": "parent", "startTime": "2024-01-01T00:00:00Z", "endTime": "2024-01-01T00:00:01Z"},
                {"id": "child", "name": "child", "parentObservationId": "parent", "startTime": "2024-01-01T00:00:00Z", "endTime": "2024-01-01T00:00:01Z"},
            ],
        })

        records = list(parser.parse(content))

        assert records[1].parent_span_id == "parent"

    def test_parse_invalid_json(self):
        """Should raise error for invalid JSON."""
        parser = LangfuseParser()
        content = "invalid json"

        with pytest.raises(ValueError, match="Invalid JSON"):
            list(parser.parse(content))

    def test_extract_tokens_total(self):
        """Should extract tokens from total field."""
        parser = LangfuseParser()
        content = json.dumps({
            "id": "trace1",
            "observations": [
                {"id": "obs1", "name": "test", "usage": {"total": 100}, "startTime": "2024-01-01T00:00:00Z", "endTime": "2024-01-01T00:00:01Z"},
            ],
        })

        records = list(parser.parse(content))

        assert records[0].token_count == 100


class TestGenericParser:
    """Tests for GenericParser class."""

    def test_parse_minimal_record(self):
        """Should parse minimal generic record."""
        parser = GenericParser()
        content = json.dumps({
            "name": "step1",
            "timestamp": "2024-01-01T00:00:00Z",
        })

        records = list(parser.parse(content))

        assert len(records) == 1
        assert records[0].name == "step1"

    def test_parse_full_record(self):
        """Should parse full generic record."""
        parser = GenericParser()
        content = json.dumps({
            "trace_id": "trace123",
            "span_id": "span456",
            "parent_span_id": "parent789",
            "agent_id": "test_agent",
            "name": "test_step",
            "inputs": {"key": "value"},
            "outputs": {"result": "success"},
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T00:00:01Z",
            "tokens": 100,
            "metadata": {"extra": "info"},
        })

        records = list(parser.parse(content))

        assert records[0].trace_id == "trace123"
        assert records[0].span_id == "span456"
        assert records[0].agent_id == "test_agent"
        assert records[0].token_count == 100

    def test_parse_alternative_field_names(self):
        """Should handle alternative field names."""
        parser = GenericParser()
        content = json.dumps({
            "session_id": "session1",
            "id": "id1",
            "parent_id": "parent1",
            "agent": "agent1",
            "event": "event1",
            "input": {"k": "v"},
            "output": {"r": "s"},
            "timestamp": "2024-01-01T00:00:00Z",
            "token_count": 50,
        })

        records = list(parser.parse(content))

        assert records[0].trace_id == "session1"
        assert records[0].span_id == "id1"
        assert records[0].parent_span_id == "parent1"
        assert records[0].agent_id == "agent1"
        assert records[0].token_count == 50

    def test_parse_multiline(self):
        """Should parse multiple lines."""
        parser = GenericParser()
        line1 = json.dumps({"name": "A", "timestamp": "2024-01-01T00:00:00Z"})
        line2 = json.dumps({"name": "B", "timestamp": "2024-01-01T00:00:01Z"})
        content = f"{line1}\n{line2}"

        records = list(parser.parse(content))

        assert len(records) == 2

    def test_skip_empty_lines(self):
        """Should skip empty lines."""
        parser = GenericParser()
        line1 = json.dumps({"name": "A", "timestamp": "2024-01-01T00:00:00Z"})
        content = f"{line1}\n\n\n"

        records = list(parser.parse(content))

        assert len(records) == 1


class TestTimestampParsing:
    """Tests for timestamp parsing in ImportParser."""

    def test_parse_iso_timestamp_with_z(self):
        """Should parse ISO timestamp with Z suffix."""
        parser = GenericParser()
        ts = parser._parse_timestamp("2024-01-15T10:30:00Z")
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 15

    def test_parse_iso_timestamp_with_ms(self):
        """Should parse ISO timestamp with milliseconds."""
        parser = GenericParser()
        ts = parser._parse_timestamp("2024-01-15T10:30:00.123Z")
        assert ts.year == 2024

    def test_parse_unix_timestamp_seconds(self):
        """Should parse Unix timestamp in seconds."""
        parser = GenericParser()
        ts = parser._parse_timestamp(1705315800)  # 2024-01-15 10:30:00
        assert ts.year == 2024

    def test_parse_unix_timestamp_milliseconds(self):
        """Should parse Unix timestamp in milliseconds."""
        parser = GenericParser()
        ts = parser._parse_timestamp(1705315800000)  # 2024-01-15 10:30:00
        assert ts.year == 2024

    def test_parse_datetime_passthrough(self):
        """Should pass through datetime objects."""
        parser = GenericParser()
        dt = datetime(2024, 1, 15, 10, 30, 0)
        ts = parser._parse_timestamp(dt)
        assert ts == dt


class TestJSONDepthCheck:
    """Tests for JSON depth checking."""

    def test_shallow_object_passes(self):
        """Shallow objects should pass depth check."""
        parser = GenericParser()
        obj = {"a": {"b": {"c": 1}}}
        assert parser._check_depth(obj) is True

    def test_deep_object_fails(self):
        """Very deep objects should fail depth check."""
        parser = GenericParser()
        # Create deeply nested object
        obj = {"value": 1}
        for _ in range(60):
            obj = {"nested": obj}
        assert parser._check_depth(obj) is False

    def test_deep_list_fails(self):
        """Very deep lists should fail depth check."""
        parser = GenericParser()
        obj = [1]
        for _ in range(60):
            obj = [obj]
        assert parser._check_depth(obj) is False


class TestHelperFunctions:
    """Tests for module helper functions."""

    def test_get_parser_langsmith(self):
        """Should return LangSmithParser."""
        parser = get_parser("langsmith")
        assert isinstance(parser, LangSmithParser)

    def test_get_parser_langfuse(self):
        """Should return LangfuseParser."""
        parser = get_parser("langfuse")
        assert isinstance(parser, LangfuseParser)

    def test_get_parser_generic(self):
        """Should return GenericParser."""
        parser = get_parser("generic")
        assert isinstance(parser, GenericParser)

    def test_get_parser_unknown(self):
        """Should return GenericParser for unknown formats."""
        parser = get_parser("unknown")
        assert isinstance(parser, GenericParser)

    def test_compute_file_hash(self):
        """Should compute consistent file hash."""
        content = b"test content"
        hash1 = compute_file_hash(content)
        hash2 = compute_file_hash(content)
        hash3 = compute_file_hash(b"different content")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 64  # SHA256 hex length

    def test_count_records_langfuse(self):
        """Should count Langfuse records correctly."""
        content = json.dumps({
            "traces": [
                {"observations": [{}, {}, {}]},
                {"observations": [{}, {}]},
            ],
        })

        count = count_records(content, "langfuse")
        assert count == 5

    def test_count_records_langfuse_single(self):
        """Should count single Langfuse trace."""
        content = json.dumps({
            "observations": [{}, {}, {}],
        })

        count = count_records(content, "langfuse")
        assert count == 3

    def test_count_records_langsmith(self):
        """Should count JSONL records."""
        content = "{}\n{}\n{}"
        count = count_records(content, "langsmith")
        assert count == 3

    def test_count_records_generic(self):
        """Should count generic JSONL records."""
        content = "{}\n{}\n\n{}"  # With empty line
        count = count_records(content, "generic")
        assert count == 3

    def test_count_records_invalid_langfuse(self):
        """Should return 0 for invalid Langfuse JSON."""
        content = "invalid json"
        count = count_records(content, "langfuse")
        assert count == 0


# ============================================================================
# AsyncBuffer Tests
# ============================================================================

class TestBufferConfig:
    """Tests for BufferConfig dataclass."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = BufferConfig()
        assert config.max_size == 1000
        assert config.flush_interval_seconds == 1.0
        assert config.max_retries == 3

    def test_custom_config(self):
        """Should accept custom values."""
        config = BufferConfig(max_size=500, flush_interval_seconds=2.0, max_retries=5)
        assert config.max_size == 500
        assert config.flush_interval_seconds == 2.0
        assert config.max_retries == 5


class TestAsyncBuffer:
    """Tests for AsyncBuffer class."""

    @pytest.mark.asyncio
    async def test_add_single_item(self):
        """Should add single item to buffer."""
        buffer = AsyncBuffer()
        await buffer.add("item1")
        assert buffer.size == 1

    @pytest.mark.asyncio
    async def test_add_batch(self):
        """Should add batch of items."""
        buffer = AsyncBuffer()
        await buffer.add_batch(["item1", "item2", "item3"])
        assert buffer.size == 3

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self):
        """Should handle flushing empty buffer."""
        callback = AsyncMock()
        buffer = AsyncBuffer(flush_callback=callback)
        await buffer.flush()
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_with_callback(self):
        """Should call flush callback with items."""
        callback = AsyncMock()
        buffer = AsyncBuffer(flush_callback=callback)

        await buffer.add("item1")
        await buffer.add("item2")
        await buffer.flush()

        callback.assert_called_once_with(["item1", "item2"])
        assert buffer.size == 0

    @pytest.mark.asyncio
    async def test_auto_flush_on_max_size(self):
        """Should auto-flush when max size reached."""
        callback = AsyncMock()
        config = BufferConfig(max_size=3)
        buffer = AsyncBuffer(config=config, flush_callback=callback)

        await buffer.add("item1")
        await buffer.add("item2")
        callback.assert_not_called()

        await buffer.add("item3")
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_flush_batch_on_max_size(self):
        """Should auto-flush batch when max size reached."""
        callback = AsyncMock()
        config = BufferConfig(max_size=3)
        buffer = AsyncBuffer(config=config, flush_callback=callback)

        await buffer.add_batch(["item1", "item2", "item3", "item4"])
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_flush_failure(self):
        """Should retry on flush failure."""
        callback = AsyncMock(side_effect=[Exception("fail"), None])
        config = BufferConfig(max_retries=3)
        buffer = AsyncBuffer(config=config, flush_callback=callback)

        await buffer.add("item1")
        await buffer.flush()

        assert callback.call_count == 2

    @pytest.mark.asyncio
    async def test_drop_items_after_max_retries(self):
        """Should drop items after max retries."""
        callback = AsyncMock(side_effect=Exception("always fail"))
        config = BufferConfig(max_retries=2)
        buffer = AsyncBuffer(config=config, flush_callback=callback)

        await buffer.add("item1")
        await buffer.flush()

        assert callback.call_count == 2
        assert buffer.size == 0  # Items dropped

    @pytest.mark.asyncio
    async def test_start_creates_flush_loop(self):
        """Should create flush loop task on start."""
        buffer = AsyncBuffer()
        await buffer.start()

        assert buffer._running is True
        assert buffer._flush_task is not None

        await buffer.stop()

    @pytest.mark.asyncio
    async def test_stop_flushes_remaining(self):
        """Should flush remaining items on stop."""
        callback = AsyncMock()
        buffer = AsyncBuffer(flush_callback=callback)

        await buffer.start()
        await buffer.add("item1")
        await buffer.stop()

        callback.assert_called_with(["item1"])

    @pytest.mark.asyncio
    async def test_size_property(self):
        """Should return correct buffer size."""
        buffer = AsyncBuffer()

        assert buffer.size == 0
        await buffer.add("item1")
        assert buffer.size == 1
        await buffer.add_batch(["item2", "item3"])
        assert buffer.size == 3


# ============================================================================
# BackpressureController Tests
# ============================================================================

class TestBackpressureController:
    """Tests for BackpressureController class."""

    def test_default_config(self):
        """Should have sensible defaults."""
        controller = BackpressureController()
        assert controller.max_pending == 10000
        assert controller.sample_rate_min == 0.1

    def test_initial_accept_all(self):
        """Should accept all initially."""
        controller = BackpressureController()
        assert controller.should_accept() is True
        assert controller.current_sample_rate == 1.0

    def test_reject_at_max_pending(self):
        """Should reject when at max pending."""
        controller = BackpressureController(max_pending=100)
        controller._pending_count = 100
        assert controller.should_accept() is False

    def test_record_pending(self):
        """Should increment pending count."""
        controller = BackpressureController()
        controller.record_pending(5)
        assert controller.pending_count == 5

    def test_record_processed(self):
        """Should decrement pending count."""
        controller = BackpressureController()
        controller._pending_count = 10
        controller.record_processed(3)
        assert controller.pending_count == 7

    def test_record_processed_floor(self):
        """Should not go below zero."""
        controller = BackpressureController()
        controller._pending_count = 5
        controller.record_processed(10)
        assert controller.pending_count == 0

    def test_sample_rate_full(self):
        """Should use full sample rate at low utilization."""
        controller = BackpressureController(max_pending=100)
        controller._pending_count = 40  # 40% utilization
        controller._adjust_sample_rate()
        assert controller.current_sample_rate == 1.0

    def test_sample_rate_75_percent(self):
        """Should use 75% sample rate at medium utilization."""
        controller = BackpressureController(max_pending=100)
        controller._pending_count = 55  # 55% utilization
        controller._adjust_sample_rate()
        assert controller.current_sample_rate == 0.75

    def test_sample_rate_50_percent(self):
        """Should use 50% sample rate at high utilization."""
        controller = BackpressureController(max_pending=100)
        controller._pending_count = 75  # 75% utilization
        controller._adjust_sample_rate()
        assert controller.current_sample_rate == 0.5

    def test_sample_rate_minimum(self):
        """Should use minimum sample rate at very high utilization."""
        controller = BackpressureController(max_pending=100, sample_rate_min=0.1)
        controller._pending_count = 95  # 95% utilization
        controller._adjust_sample_rate()
        assert controller.current_sample_rate == 0.1

    def test_sampling_behavior(self):
        """Should sample probabilistically when rate < 1."""
        controller = BackpressureController(max_pending=100)
        controller._pending_count = 75  # Force 50% sample rate
        controller._adjust_sample_rate()

        # Run many times and check rough sampling
        accepts = sum(1 for _ in range(1000) if controller.should_accept())
        # Should be roughly 50% (allow some variance)
        assert 350 < accepts < 650


# ============================================================================
# Integration Tests
# ============================================================================

class TestIngestionIntegration:
    """Integration tests for ingestion pipeline."""

    def test_otel_to_parsed_state_workflow(self):
        """Should parse OTEL spans through full workflow."""
        spans = [
            {
                "traceId": "integration_trace",
                "spanId": "span1",
                "name": "agent_step",
                "startTimeUnixNano": "1000000000000000000",
                "endTimeUnixNano": "1000000001000000000",
                "attributes": [
                    {"key": "gen_ai.agent.name", "value": {"stringValue": "IntegrationAgent"}},
                    {"key": "gen_ai.prompt", "value": {"stringValue": "Test prompt"}},
                    {"key": "gen_ai.completion", "value": {"stringValue": "Test response"}},
                    {"key": "gen_ai.state", "value": {"stringValue": "{\"step\": 1}"}},
                    {"key": "gen_ai.usage.total_tokens", "value": {"intValue": "100"}},
                ],
                "status": {"code": "OK"},
                "events": [],
            },
        ]

        parser = OTELParser()
        result = parser.parse_spans(spans)

        assert len(result) == 1
        state = result[0]
        assert state.agent_id == "IntegrationAgent"
        assert state.prompt == "Test prompt"
        assert state.response == "Test response"
        assert state.state_delta == {"step": 1}
        assert state.token_count == 100
        assert state.latency_ms == 1000

    def test_format_detection_and_parsing(self):
        """Should detect format and parse correctly."""
        # LangSmith format
        langsmith_content = json.dumps({
            "run_type": "chain",
            "inputs": {"query": "test"},
            "name": "TestChain",
            "id": "123",
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T00:00:01Z",
        })

        format_type = ImportParser.detect_format(langsmith_content)
        assert format_type == "langsmith"

        parser = get_parser(format_type)
        records = list(parser.parse(langsmith_content))
        assert len(records) == 1
        assert records[0].name == "TestChain"

    @pytest.mark.asyncio
    async def test_buffer_with_backpressure(self):
        """Should integrate buffer with backpressure control."""
        flushed_items = []

        async def capture_flush(items):
            flushed_items.extend(items)

        # Use high max_pending to avoid sample rate drops during test
        # (sample rate drops to 0.75 when pending > 50% of max_pending)
        controller = BackpressureController(max_pending=100)
        buffer = AsyncBuffer(
            config=BufferConfig(max_size=5),
            flush_callback=capture_flush,
        )

        # Add items with backpressure tracking
        for i in range(7):
            if controller.should_accept():
                await buffer.add(f"item{i}")
                controller.record_pending()

        await buffer.flush()
        controller.record_processed(len(flushed_items))

        assert len(flushed_items) == 7
        assert controller.pending_count == 0
