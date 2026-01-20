"""
Tests for the integrations module - framework tracers for Semantic Kernel and base classes.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from app.enterprise.integrations import SemanticKernelTracer, BaseFrameworkTracer
from app.enterprise.integrations.base import Span, Trace
from app.enterprise.integrations.semantic_kernel import create_semantic_kernel_tracer


# =============================================================================
# Span Tests
# =============================================================================

class TestSpan:
    """Tests for Span dataclass."""

    def test_span_initialization(self):
        """Test span initialization with required fields."""
        span = Span(
            id="span_123",
            trace_id="trace_456",
            parent_id=None,
            name="test_span",
            start_time=datetime.utcnow(),
        )
        assert span.id == "span_123"
        assert span.trace_id == "trace_456"
        assert span.parent_id is None
        assert span.name == "test_span"
        assert span.status == "OK"
        assert span.attributes == {}
        assert span.events == []

    def test_span_with_optional_fields(self):
        """Test span with optional fields."""
        now = datetime.utcnow()
        later = now + timedelta(seconds=1)

        span = Span(
            id="span_123",
            trace_id="trace_456",
            parent_id="parent_789",
            name="test_span",
            start_time=now,
            end_time=later,
            attributes={"key": "value"},
            events=[{"name": "event1"}],
            status="ERROR",
        )
        assert span.parent_id == "parent_789"
        assert span.end_time == later
        assert span.attributes == {"key": "value"}
        assert span.events == [{"name": "event1"}]
        assert span.status == "ERROR"

    def test_span_to_dict(self):
        """Test span serialization to dictionary."""
        now = datetime.utcnow()
        later = now + timedelta(seconds=1)

        span = Span(
            id="span_123",
            trace_id="trace_456",
            parent_id="parent_789",
            name="test_span",
            start_time=now,
            end_time=later,
            attributes={"key": "value"},
            events=[{"name": "event1", "timestamp": "2024-01-01T00:00:00"}],
            status="OK",
        )

        result = span.to_dict()
        assert result["id"] == "span_123"
        assert result["trace_id"] == "trace_456"
        assert result["parent_id"] == "parent_789"
        assert result["name"] == "test_span"
        assert result["start_time"] == now.isoformat()
        assert result["end_time"] == later.isoformat()
        assert result["attributes"] == {"key": "value"}
        assert result["status"] == "OK"

    def test_span_to_dict_without_end_time(self):
        """Test span serialization without end time."""
        now = datetime.utcnow()
        span = Span(
            id="span_123",
            trace_id="trace_456",
            parent_id=None,
            name="test_span",
            start_time=now,
        )

        result = span.to_dict()
        assert result["end_time"] is None


# =============================================================================
# Trace Tests
# =============================================================================

class TestTrace:
    """Tests for Trace dataclass."""

    def test_trace_initialization(self):
        """Test trace initialization."""
        trace = Trace(id="trace_123")
        assert trace.id == "trace_123"
        assert trace.spans == []
        assert trace.metadata == {}

    def test_trace_with_spans(self):
        """Test trace with spans."""
        span1 = Span(
            id="span_1",
            trace_id="trace_123",
            parent_id=None,
            name="root",
            start_time=datetime.utcnow(),
        )
        span2 = Span(
            id="span_2",
            trace_id="trace_123",
            parent_id="span_1",
            name="child",
            start_time=datetime.utcnow(),
        )

        trace = Trace(
            id="trace_123",
            spans=[span1, span2],
            metadata={"service": "test"},
        )

        assert len(trace.spans) == 2
        assert trace.metadata == {"service": "test"}

    def test_trace_to_dict(self):
        """Test trace serialization to dictionary."""
        span = Span(
            id="span_1",
            trace_id="trace_123",
            parent_id=None,
            name="root",
            start_time=datetime.utcnow(),
        )

        trace = Trace(
            id="trace_123",
            spans=[span],
            metadata={"service": "test"},
        )

        result = trace.to_dict()
        assert result["id"] == "trace_123"
        assert len(result["spans"]) == 1
        assert result["spans"][0]["id"] == "span_1"
        assert result["metadata"] == {"service": "test"}


# =============================================================================
# ConcreteFrameworkTracer for testing abstract base class
# =============================================================================

class ConcreteFrameworkTracer(BaseFrameworkTracer):
    """Concrete implementation for testing BaseFrameworkTracer."""

    FRAMEWORK_NAME = "test_framework"
    FRAMEWORK_VERSION = "1.0.0"

    def wrap(self, target):
        return target

    def extract_agent_info(self, obj):
        return {"type": "test"}


# =============================================================================
# BaseFrameworkTracer Tests
# =============================================================================

class TestBaseFrameworkTracer:
    """Tests for BaseFrameworkTracer class."""

    def test_tracer_initialization(self):
        """Test tracer initialization with defaults."""
        tracer = ConcreteFrameworkTracer()
        assert tracer.endpoint == "http://localhost:8000"
        assert tracer.traces == {}
        assert tracer.current_trace_id is None
        assert tracer.span_stack == []

    def test_tracer_initialization_custom_endpoint(self):
        """Test tracer initialization with custom endpoint."""
        tracer = ConcreteFrameworkTracer(endpoint="http://custom:9000")
        assert tracer.endpoint == "http://custom:9000"

    def test_start_trace(self):
        """Test starting a new trace."""
        tracer = ConcreteFrameworkTracer()
        trace_id = tracer.start_trace()

        assert trace_id in tracer.traces
        assert tracer.current_trace_id == trace_id
        trace = tracer.traces[trace_id]
        assert trace.id == trace_id
        assert trace.metadata["framework"] == "test_framework"
        assert trace.metadata["framework_version"] == "1.0.0"

    def test_start_trace_with_metadata(self):
        """Test starting trace with custom metadata."""
        tracer = ConcreteFrameworkTracer()
        trace_id = tracer.start_trace(metadata={"user_id": "123", "session": "abc"})

        trace = tracer.traces[trace_id]
        assert trace.metadata["user_id"] == "123"
        assert trace.metadata["session"] == "abc"
        assert trace.metadata["framework"] == "test_framework"

    def test_start_span(self):
        """Test starting a new span."""
        tracer = ConcreteFrameworkTracer()
        trace_id = tracer.start_trace()
        span_id = tracer.start_span("test_operation")

        assert span_id in tracer.span_stack
        trace = tracer.traces[trace_id]
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "test_operation"
        assert trace.spans[0].parent_id is None

    def test_start_span_with_attributes(self):
        """Test starting span with attributes."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()
        span_id = tracer.start_span(
            "test_operation",
            attributes={"key": "value", "count": 42},
        )

        trace = tracer.traces[tracer.current_trace_id]
        span = trace.spans[0]
        assert span.attributes == {"key": "value", "count": 42}

    def test_start_span_creates_trace_if_needed(self):
        """Test that start_span creates a trace if none exists."""
        tracer = ConcreteFrameworkTracer()
        assert tracer.current_trace_id is None

        span_id = tracer.start_span("auto_trace_span")

        assert tracer.current_trace_id is not None
        assert tracer.current_trace_id in tracer.traces

    def test_nested_spans(self):
        """Test nested span parent-child relationships."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()

        parent_span_id = tracer.start_span("parent")
        child_span_id = tracer.start_span("child")

        trace = tracer.traces[tracer.current_trace_id]
        child_span = [s for s in trace.spans if s.id == child_span_id][0]

        assert child_span.parent_id == parent_span_id

    def test_end_span(self):
        """Test ending a span."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()
        span_id = tracer.start_span("test_operation")

        tracer.end_span(span_id)

        trace = tracer.traces[tracer.current_trace_id]
        span = trace.spans[0]
        assert span.end_time is not None
        assert span.status == "OK"
        assert span_id not in tracer.span_stack

    def test_end_span_with_status(self):
        """Test ending span with custom status."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()
        span_id = tracer.start_span("test_operation")

        tracer.end_span(span_id, status="ERROR")

        trace = tracer.traces[tracer.current_trace_id]
        assert trace.spans[0].status == "ERROR"

    def test_end_span_with_attributes(self):
        """Test ending span with additional attributes."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()
        span_id = tracer.start_span("test_operation", attributes={"initial": "value"})

        tracer.end_span(span_id, attributes={"result": "success", "count": 10})

        trace = tracer.traces[tracer.current_trace_id]
        span = trace.spans[0]
        assert span.attributes["initial"] == "value"
        assert span.attributes["result"] == "success"
        assert span.attributes["count"] == 10

    def test_add_event(self):
        """Test adding event to a span."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()
        span_id = tracer.start_span("test_operation")

        tracer.add_event(span_id, "checkpoint", attributes={"stage": 1})

        trace = tracer.traces[tracer.current_trace_id]
        span = trace.spans[0]
        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"
        assert span.events[0]["attributes"] == {"stage": 1}
        assert "timestamp" in span.events[0]

    def test_add_multiple_events(self):
        """Test adding multiple events to a span."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()
        span_id = tracer.start_span("test_operation")

        tracer.add_event(span_id, "start")
        tracer.add_event(span_id, "middle")
        tracer.add_event(span_id, "end")

        trace = tracer.traces[tracer.current_trace_id]
        span = trace.spans[0]
        assert len(span.events) == 3

    def test_get_trace(self):
        """Test getting a trace by ID."""
        tracer = ConcreteFrameworkTracer()
        trace_id = tracer.start_trace()

        trace = tracer.get_trace(trace_id)
        assert trace is not None
        assert trace.id == trace_id

    def test_get_trace_not_found(self):
        """Test getting non-existent trace returns None."""
        tracer = ConcreteFrameworkTracer()
        trace = tracer.get_trace("nonexistent_id")
        assert trace is None

    def test_on_span_end_callback(self):
        """Test span end callback registration and invocation."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()

        callback_called = []

        def on_span_end(span: Span):
            callback_called.append(span.name)

        tracer.on_span_end(on_span_end)

        span_id = tracer.start_span("callback_test")
        tracer.end_span(span_id)

        assert "callback_test" in callback_called

    def test_multiple_callbacks(self):
        """Test multiple span end callbacks."""
        tracer = ConcreteFrameworkTracer()
        tracer.start_trace()

        callback1_called = []
        callback2_called = []

        tracer.on_span_end(lambda s: callback1_called.append(s.name))
        tracer.on_span_end(lambda s: callback2_called.append(s.name))

        span_id = tracer.start_span("multi_callback_test")
        tracer.end_span(span_id)

        assert "multi_callback_test" in callback1_called
        assert "multi_callback_test" in callback2_called


# =============================================================================
# SemanticKernelTracer Tests
# =============================================================================

class TestSemanticKernelTracer:
    """Tests for SemanticKernelTracer class."""

    def test_tracer_initialization(self):
        """Test tracer initialization."""
        tracer = SemanticKernelTracer()
        assert tracer.FRAMEWORK_NAME == "semantic_kernel"
        assert tracer.FRAMEWORK_VERSION == "1.x"
        assert tracer._function_hooks == {}
        assert tracer._planner_traces == {}

    def test_tracer_custom_endpoint(self):
        """Test tracer with custom endpoint."""
        tracer = SemanticKernelTracer(endpoint="http://custom:8080")
        assert tracer.endpoint == "http://custom:8080"

    def test_wrap_kernel(self):
        """Test wrapping a kernel object."""
        tracer = SemanticKernelTracer()

        # Mock kernel
        original_invoke = AsyncMock(return_value="result")
        mock_kernel = MagicMock()
        mock_kernel.invoke = original_invoke
        mock_kernel.invoke_prompt = AsyncMock(return_value="prompt_result")
        mock_kernel.invoke_stream = AsyncMock()

        wrapped = tracer.wrap(mock_kernel)

        assert hasattr(wrapped, '_mao_tracer')
        assert wrapped._mao_tracer == tracer
        # Verify invoke was replaced with traced version (not the original)
        assert wrapped.invoke != original_invoke

    @pytest.mark.asyncio
    async def test_traced_invoke(self):
        """Test traced invoke method."""
        tracer = SemanticKernelTracer()

        original_invoke = AsyncMock(return_value="result")
        mock_kernel = MagicMock()
        mock_kernel.invoke = original_invoke
        mock_kernel.invoke_prompt = None
        mock_kernel.invoke_stream = None

        wrapped = tracer.wrap(mock_kernel)

        # Create a mock function with plugin_name and name
        mock_function = MagicMock()
        mock_function.plugin_name = "test_plugin"
        mock_function.name = "test_function"

        result = await wrapped.invoke(mock_function, "arg1", key="value")

        assert result == "result"
        original_invoke.assert_called_once_with(mock_function, "arg1", key="value")

        # Verify trace was created
        assert len(tracer.traces) == 1
        trace = list(tracer.traces.values())[0]
        assert len(trace.spans) == 1
        assert "sk.invoke" in trace.spans[0].name

    @pytest.mark.asyncio
    async def test_traced_invoke_with_error(self):
        """Test traced invoke handles errors."""
        tracer = SemanticKernelTracer()

        original_invoke = AsyncMock(side_effect=ValueError("Test error"))
        mock_kernel = MagicMock()
        mock_kernel.invoke = original_invoke
        mock_kernel.invoke_prompt = None
        mock_kernel.invoke_stream = None

        wrapped = tracer.wrap(mock_kernel)
        mock_function = MagicMock()
        mock_function.plugin_name = "test_plugin"
        mock_function.name = "test_function"

        with pytest.raises(ValueError, match="Test error"):
            await wrapped.invoke(mock_function)

        # Verify span was ended with error status
        trace = list(tracer.traces.values())[0]
        assert trace.spans[0].status == "ERROR"
        assert "ValueError" in trace.spans[0].attributes.get("error.type", "")

    @pytest.mark.asyncio
    async def test_traced_invoke_prompt(self):
        """Test traced invoke_prompt method."""
        tracer = SemanticKernelTracer()

        original_invoke_prompt = AsyncMock(return_value="prompt result")
        mock_kernel = MagicMock()
        mock_kernel.invoke = AsyncMock()
        mock_kernel.invoke_prompt = original_invoke_prompt
        mock_kernel.invoke_stream = None

        wrapped = tracer.wrap(mock_kernel)

        result = await wrapped.invoke_prompt("Hello {{$name}}", name="World")

        assert result == "prompt result"
        original_invoke_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_traced_invoke_prompt_not_available(self):
        """Test invoke_prompt is not wrapped when not available."""
        tracer = SemanticKernelTracer()

        mock_kernel = MagicMock()
        mock_kernel.invoke = AsyncMock()
        mock_kernel.invoke_prompt = None  # Not available
        mock_kernel.invoke_stream = None

        wrapped = tracer.wrap(mock_kernel)

        # invoke_prompt should remain None since original was None
        assert wrapped.invoke_prompt is None

    def test_extract_agent_info_empty_kernel(self):
        """Test extracting agent info from empty kernel."""
        tracer = SemanticKernelTracer()

        mock_kernel = MagicMock()
        mock_kernel.plugins = {}
        mock_kernel.services = {}

        info = tracer.extract_agent_info(mock_kernel)

        assert info["framework"] == "semantic_kernel"
        assert info["framework_version"] == "1.x"
        assert info["plugins"] == {}
        assert info["services"] == []

    def test_extract_agent_info_with_plugins(self):
        """Test extracting agent info with plugins."""
        tracer = SemanticKernelTracer()

        # Mock plugin with functions
        mock_func = MagicMock()
        mock_func.description = "Test function"
        mock_func.prompt_template = None  # Not semantic

        mock_plugin = MagicMock()
        mock_plugin.functions = {"func1": mock_func}

        mock_kernel = MagicMock()
        mock_kernel.plugins = {"TestPlugin": mock_plugin}
        mock_kernel.services = MagicMock()
        mock_kernel.services.keys.return_value = ["chat", "text"]

        info = tracer.extract_agent_info(mock_kernel)

        assert "TestPlugin" in info["plugins"]
        assert info["plugins"]["TestPlugin"]["name"] == "TestPlugin"
        assert len(info["plugins"]["TestPlugin"]["functions"]) == 1
        assert info["services"] == ["chat", "text"]

    @pytest.mark.asyncio
    async def test_trace_function_context_manager(self):
        """Test trace_function context manager."""
        tracer = SemanticKernelTracer()

        async with tracer.trace_function("my_plugin", "my_function") as span_id:
            assert span_id is not None
            # Span should be active
            assert span_id in tracer.span_stack

        # Span should be ended
        trace = list(tracer.traces.values())[0]
        assert trace.spans[0].end_time is not None
        assert trace.spans[0].status == "OK"

    @pytest.mark.asyncio
    async def test_trace_function_with_error(self):
        """Test trace_function context manager with error."""
        tracer = SemanticKernelTracer()

        with pytest.raises(RuntimeError, match="Test error"):
            async with tracer.trace_function("plugin", "function"):
                raise RuntimeError("Test error")

        trace = list(tracer.traces.values())[0]
        assert trace.spans[0].status == "ERROR"

    @pytest.mark.asyncio
    async def test_trace_planner(self):
        """Test wrapping a planner for tracing."""
        tracer = SemanticKernelTracer()

        mock_plan = MagicMock()
        mock_plan.steps = ["step1", "step2", "step3"]

        original_create_plan = AsyncMock(return_value=mock_plan)
        mock_planner = MagicMock()
        mock_planner.create_plan = original_create_plan

        wrapped = tracer.trace_planner(mock_planner)

        plan = await wrapped.create_plan("Build a website")

        assert plan == mock_plan
        original_create_plan.assert_called_once_with("Build a website")

        # Verify tracing
        trace = list(tracer.traces.values())[0]
        assert "sk.planner" in trace.spans[0].name
        assert trace.spans[0].attributes["sk.goal"] == "Build a website"

    @pytest.mark.asyncio
    async def test_trace_chat_completion(self):
        """Test wrapping chat completion service."""
        tracer = SemanticKernelTracer()

        mock_result = MagicMock()
        mock_result.usage = {"prompt_tokens": 10, "completion_tokens": 20}

        original_complete = AsyncMock(return_value=mock_result)
        mock_service = MagicMock()
        mock_service.complete_chat = original_complete
        mock_service.model_id = "gpt-4"

        wrapped = tracer.trace_chat_completion(mock_service)

        messages = [{"role": "user", "content": "Hello"}]
        result = await wrapped.complete_chat(messages)

        assert result == mock_result
        original_complete.assert_called_once_with(messages)

        # Verify tracing
        trace = list(tracer.traces.values())[0]
        assert trace.spans[0].name == "sk.chat_completion"
        assert trace.spans[0].attributes["sk.model"] == "gpt-4"


class TestCreateSemanticKernelTracer:
    """Tests for create_semantic_kernel_tracer factory function."""

    def test_create_tracer_defaults(self):
        """Test creating tracer with defaults."""
        tracer = create_semantic_kernel_tracer()
        assert isinstance(tracer, SemanticKernelTracer)
        assert tracer.endpoint == "http://localhost:8000"

    def test_create_tracer_custom_endpoint(self):
        """Test creating tracer with custom endpoint."""
        tracer = create_semantic_kernel_tracer(endpoint="http://custom:9000")
        assert tracer.endpoint == "http://custom:9000"

    def test_create_tracer_no_auto_instrument(self):
        """Test creating tracer without auto-instrumentation."""
        tracer = create_semantic_kernel_tracer(auto_instrument=False)
        assert isinstance(tracer, SemanticKernelTracer)

    def test_create_tracer_auto_instrument_no_import(self):
        """Test auto-instrumentation gracefully handles missing import."""
        # This should not raise even without semantic_kernel installed
        tracer = create_semantic_kernel_tracer(auto_instrument=True)
        assert isinstance(tracer, SemanticKernelTracer)


# =============================================================================
# Module Import Tests
# =============================================================================

class TestModuleImports:
    """Tests for module imports."""

    def test_import_from_integrations_module(self):
        """Test that all exports are importable from integrations module."""
        from app.enterprise.integrations import SemanticKernelTracer, BaseFrameworkTracer

        assert SemanticKernelTracer is not None
        assert BaseFrameworkTracer is not None

    def test_import_from_base_module(self):
        """Test importing from base module."""
        from app.enterprise.integrations.base import Span, Trace, BaseFrameworkTracer

        assert Span is not None
        assert Trace is not None
        assert BaseFrameworkTracer is not None

    def test_import_from_semantic_kernel_module(self):
        """Test importing from semantic_kernel module."""
        from app.enterprise.integrations.semantic_kernel import (
            SemanticKernelTracer,
            create_semantic_kernel_tracer,
        )

        assert SemanticKernelTracer is not None
        assert create_semantic_kernel_tracer is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestTracerIntegration:
    """Integration tests for tracer functionality."""

    def test_full_trace_lifecycle(self):
        """Test complete trace lifecycle with multiple spans."""
        tracer = ConcreteFrameworkTracer()

        # Start trace
        trace_id = tracer.start_trace(metadata={"service": "test"})

        # Create nested spans
        parent_id = tracer.start_span("parent", attributes={"level": 0})
        child1_id = tracer.start_span("child1", attributes={"level": 1})
        tracer.add_event(child1_id, "processing", attributes={"step": 1})
        tracer.end_span(child1_id, status="OK")

        child2_id = tracer.start_span("child2", attributes={"level": 1})
        tracer.end_span(child2_id, status="OK")

        tracer.end_span(parent_id, status="OK", attributes={"completed": True})

        # Verify trace structure
        trace = tracer.get_trace(trace_id)
        assert trace is not None
        assert len(trace.spans) == 3

        # Verify parent-child relationships
        parent_span = [s for s in trace.spans if s.name == "parent"][0]
        child1_span = [s for s in trace.spans if s.name == "child1"][0]
        child2_span = [s for s in trace.spans if s.name == "child2"][0]

        assert parent_span.parent_id is None
        assert child1_span.parent_id == parent_id
        assert child2_span.parent_id == parent_id

        # Verify events
        assert len(child1_span.events) == 1
        assert child1_span.events[0]["name"] == "processing"

    @pytest.mark.asyncio
    async def test_semantic_kernel_full_workflow(self):
        """Test full Semantic Kernel tracing workflow."""
        tracer = SemanticKernelTracer()

        # Mock a complete kernel workflow
        mock_kernel = MagicMock()

        async def mock_invoke(func, *args, **kwargs):
            await asyncio.sleep(0.01)  # Simulate work
            return "invoked"

        mock_kernel.invoke = mock_invoke
        mock_kernel.invoke_prompt = None
        mock_kernel.invoke_stream = None

        wrapped = tracer.wrap(mock_kernel)

        # Simulate multiple function calls
        mock_func1 = MagicMock()
        mock_func1.plugin_name = "math"
        mock_func1.name = "add"

        mock_func2 = MagicMock()
        mock_func2.plugin_name = "text"
        mock_func2.name = "summarize"

        result1 = await wrapped.invoke(mock_func1, 1, 2)
        result2 = await wrapped.invoke(mock_func2, "long text")

        assert result1 == "invoked"
        assert result2 == "invoked"

        # Verify traces
        assert len(tracer.traces) == 1
        trace = list(tracer.traces.values())[0]
        assert len(trace.spans) == 2
        assert "math" in trace.spans[0].name
        assert "text" in trace.spans[1].name
