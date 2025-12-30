"""Tests for Agent Forensics diagnose functionality."""

import pytest
from datetime import datetime
import json

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus
from app.ingestion.importers import import_trace, detect_format
from app.ingestion.importers.raw_json import RawJSONImporter
from app.ingestion.importers.langsmith import LangSmithImporter
from app.detection.orchestrator import DetectionOrchestrator, DetectionCategory, Severity


class TestUniversalSpan:
    """Tests for UniversalSpan abstraction."""

    def test_span_creation(self):
        """Test basic span creation."""
        span = UniversalSpan(
            id="span-1",
            trace_id="trace-1",
            name="test-span",
            span_type=SpanType.TOOL_CALL,
            tool_name="search",
            tool_args={"query": "test"},
        )
        assert span.id == "span-1"
        assert span.span_type == SpanType.TOOL_CALL
        assert span.is_single_agent
        assert not span.is_multi_agent

    def test_span_with_error(self):
        """Test span with error detection."""
        span = UniversalSpan(
            id="span-1",
            trace_id="trace-1",
            name="failed-span",
            span_type=SpanType.TOOL_CALL,
            status=SpanStatus.ERROR,
            error="Connection timeout",
        )
        assert span.has_error
        assert span.error == "Connection timeout"

    def test_span_to_state_snapshot(self):
        """Test conversion to StateSnapshot for detection."""
        span = UniversalSpan(
            id="span-1",
            trace_id="trace-1",
            name="llm-call",
            span_type=SpanType.LLM_CALL,
            prompt="What is 2+2?",
            response="4",
            agent_id="agent-1",
        )
        snapshot = span.to_state_snapshot()
        assert snapshot.agent_id == "agent-1"
        assert "Prompt:" in snapshot.content
        assert "Response:" in snapshot.content


class TestUniversalTrace:
    """Tests for UniversalTrace abstraction."""

    def test_trace_creation(self):
        """Test basic trace creation."""
        trace = UniversalTrace(
            trace_id="trace-1",
            spans=[
                UniversalSpan(
                    id="span-1",
                    trace_id="trace-1",
                    name="span-1",
                    span_type=SpanType.TOOL_CALL,
                    start_time=datetime.utcnow(),
                    tokens_input=100,
                    tokens_output=50,
                ),
            ],
        )
        assert trace.trace_id == "trace-1"
        assert len(trace.spans) == 1
        assert trace.total_tokens == 150

    def test_trace_error_detection(self):
        """Test trace error summary."""
        trace = UniversalTrace(
            trace_id="trace-1",
            spans=[
                UniversalSpan(id="1", trace_id="trace-1", name="ok", span_type=SpanType.TOOL_CALL),
                UniversalSpan(id="2", trace_id="trace-1", name="err", span_type=SpanType.TOOL_CALL, status=SpanStatus.ERROR, error="fail"),
            ],
        )
        assert trace.has_errors
        assert trace.error_count == 1

    def test_get_tool_calls(self):
        """Test filtering tool calls."""
        trace = UniversalTrace(
            trace_id="trace-1",
            spans=[
                UniversalSpan(id="1", trace_id="trace-1", name="llm", span_type=SpanType.LLM_CALL),
                UniversalSpan(id="2", trace_id="trace-1", name="tool1", span_type=SpanType.TOOL_CALL),
                UniversalSpan(id="3", trace_id="trace-1", name="tool2", span_type=SpanType.TOOL_CALL),
            ],
        )
        tool_calls = trace.get_tool_calls()
        assert len(tool_calls) == 2


class TestRawJSONImporter:
    """Tests for raw JSON importer."""

    def test_import_simple_json(self):
        """Test importing simple JSON trace."""
        content = json.dumps([
            {
                "id": "span-1",
                "name": "search",
                "type": "tool",
                "tool_name": "web_search",
                "tool_args": {"query": "test"},
                "tool_result": {"results": []},
            }
        ])

        importer = RawJSONImporter()
        trace = importer.import_trace(content)

        assert len(trace.spans) == 1
        assert trace.spans[0].tool_name == "web_search"
        assert trace.spans[0].span_type == SpanType.TOOL_CALL

    def test_import_jsonl(self):
        """Test importing JSONL format."""
        content = """{"id": "1", "name": "step1", "type": "llm"}
{"id": "2", "name": "step2", "type": "tool", "tool_name": "search"}"""

        importer = RawJSONImporter()
        trace = importer.import_trace(content)

        assert len(trace.spans) == 2

    def test_import_nested_spans(self):
        """Test importing nested spans."""
        content = json.dumps({
            "id": "parent",
            "name": "workflow",
            "children": [
                {"id": "child1", "name": "step1"},
                {"id": "child2", "name": "step2"},
            ]
        })

        importer = RawJSONImporter()
        trace = importer.import_trace(content)

        # Should have parent + 2 children
        assert len(trace.spans) == 3


class TestLangSmithImporter:
    """Tests for LangSmith importer."""

    def test_import_langsmith_trace(self):
        """Test importing LangSmith format."""
        content = json.dumps([
            {
                "id": "run-1",
                "session_id": "session-1",
                "run_type": "llm",
                "name": "ChatOpenAI",
                "inputs": {"messages": [{"role": "user", "content": "Hello"}]},
                "outputs": {"generations": [[{"text": "Hi there!"}]]},
            },
            {
                "id": "run-2",
                "session_id": "session-1",
                "run_type": "tool",
                "name": "search",
                "inputs": {"query": "test"},
                "outputs": {"results": []},
            },
        ])

        importer = LangSmithImporter()
        trace = importer.import_trace(content)

        assert trace.trace_id == "session-1"
        assert len(trace.spans) == 2
        assert trace.spans[0].span_type == SpanType.LLM_CALL
        assert trace.spans[1].span_type == SpanType.TOOL_CALL


class TestFormatDetection:
    """Tests for format auto-detection."""

    def test_detect_langsmith(self):
        """Test detecting LangSmith format."""
        content = json.dumps([{"run_type": "llm", "inputs": {}}])
        assert detect_format(content) == "langsmith"

    def test_detect_otel(self):
        """Test detecting OTEL format."""
        content = json.dumps({"resourceSpans": []})
        assert detect_format(content) == "otel"

    def test_detect_generic(self):
        """Test falling back to generic."""
        content = json.dumps([{"id": "1", "name": "test"}])
        assert detect_format(content) == "generic"


class TestDetectionOrchestrator:
    """Tests for detection orchestrator."""

    def test_detect_no_issues(self):
        """Test healthy trace with no issues."""
        trace = UniversalTrace(
            trace_id="trace-1",
            spans=[
                UniversalSpan(
                    id="1",
                    trace_id="trace-1",
                    name="llm",
                    span_type=SpanType.LLM_CALL,
                    start_time=datetime.utcnow(),
                ),
            ],
        )

        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        # May or may not have failures depending on content
        assert result.trace_id == "trace-1"
        assert result.total_spans == 1

    def test_detect_tool_errors(self):
        """Test detecting tool errors."""
        trace = UniversalTrace(
            trace_id="trace-1",
            spans=[
                UniversalSpan(
                    id="1",
                    trace_id="trace-1",
                    name="search",
                    span_type=SpanType.TOOL_CALL,
                    tool_name="web_search",
                    status=SpanStatus.ERROR,
                    error="API rate limit exceeded",
                ),
            ],
        )

        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        assert result.has_failures
        assert result.failure_count >= 1
        # Should detect tool error
        tool_errors = [d for d in result.all_detections if d.category == DetectionCategory.TOOL_PROVISION]
        assert len(tool_errors) >= 1

    def test_detect_repeated_tools(self):
        """Test detecting repeated tool calls."""
        trace = UniversalTrace(
            trace_id="trace-1",
            spans=[
                UniversalSpan(id="1", trace_id="trace-1", name="s1", span_type=SpanType.TOOL_CALL, tool_name="search"),
                UniversalSpan(id="2", trace_id="trace-1", name="s2", span_type=SpanType.TOOL_CALL, tool_name="search"),
                UniversalSpan(id="3", trace_id="trace-1", name="s3", span_type=SpanType.TOOL_CALL, tool_name="search"),
            ],
        )

        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        # Should detect loop/repeated tool pattern
        assert result.has_failures
        loop_detections = [d for d in result.all_detections if d.category == DetectionCategory.LOOP]
        assert len(loop_detections) >= 1

    def test_self_healing_available(self):
        """Test that self-healing is flagged when fix available."""
        trace = UniversalTrace(
            trace_id="trace-1",
            spans=[
                UniversalSpan(
                    id="1",
                    trace_id="trace-1",
                    name="failed",
                    span_type=SpanType.TOOL_CALL,
                    tool_name="api_call",
                    status=SpanStatus.ERROR,
                    error="timeout",
                ),
            ],
        )

        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        if result.has_failures and result.primary_failure and result.primary_failure.suggested_fix:
            assert result.self_healing_available


class TestImportTrace:
    """Tests for import_trace convenience function."""

    def test_import_with_auto_detect(self):
        """Test importing with auto format detection."""
        content = json.dumps([
            {"id": "1", "name": "test", "type": "llm", "prompt": "hello", "response": "hi"}
        ])

        trace = import_trace(content, "auto")
        assert len(trace.spans) == 1

    def test_import_with_explicit_format(self):
        """Test importing with explicit format."""
        content = json.dumps([
            {"run_type": "llm", "id": "1", "name": "test"}
        ])

        trace = import_trace(content, "langsmith")
        assert trace.source_format == "langsmith"
