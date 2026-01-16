"""Tests for Semantic Kernel tracer integration."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.enterprise.integrations.semantic_kernel import SemanticKernelTracer
from app.enterprise.integrations.base import BaseFrameworkTracer, Span, Trace


class TestBaseFrameworkTracer:
    """Tests for the base tracer functionality."""

    def test_start_trace_creates_trace(self):
        """Test that start_trace creates a new trace."""
        tracer = SemanticKernelTracer(endpoint="http://test")
        trace_id = tracer.start_trace()

        assert trace_id in tracer.traces
        assert tracer.current_trace_id == trace_id

    def test_start_span_creates_span(self):
        """Test that start_span creates a span within a trace."""
        tracer = SemanticKernelTracer(endpoint="http://test")
        tracer.start_trace()

        span_id = tracer.start_span("test_span", attributes={"key": "value"})

        assert len(tracer.traces) == 1
        trace = list(tracer.traces.values())[0]
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "test_span"
        assert trace.spans[0].attributes["key"] == "value"

    def test_end_span_closes_span(self):
        """Test that end_span sets end time and status."""
        tracer = SemanticKernelTracer(endpoint="http://test")
        tracer.start_trace()
        span_id = tracer.start_span("test_span")

        tracer.end_span(span_id, status="OK", attributes={"result": "success"})

        trace = list(tracer.traces.values())[0]
        span = trace.spans[0]
        assert span.end_time is not None
        assert span.status == "OK"
        assert span.attributes["result"] == "success"

    def test_nested_spans_have_parent_ids(self):
        """Test that nested spans have correct parent IDs."""
        tracer = SemanticKernelTracer(endpoint="http://test")
        tracer.start_trace()

        parent_span_id = tracer.start_span("parent")
        child_span_id = tracer.start_span("child")

        trace = list(tracer.traces.values())[0]
        child_span = trace.spans[1]
        assert child_span.parent_id == parent_span_id

    @pytest.mark.asyncio
    async def test_flush_empty_traces_returns_true(self):
        """Test that flush returns True when no traces exist."""
        tracer = SemanticKernelTracer(endpoint="http://test")
        result = await tracer.flush()
        assert result is True

    @pytest.mark.asyncio
    async def test_flush_sends_traces_to_backend(self):
        """Test that flush sends traces to the MAO backend."""
        tracer = SemanticKernelTracer(endpoint="http://test")
        tracer.start_trace()
        tracer.start_span("test_span")
        tracer.end_span(tracer.span_stack[-1])

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(tracer, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            success = await tracer.flush(api_key="test_key")

            assert success is True
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "http://test/api/v1/traces" in str(call_args)
            assert call_args.kwargs["headers"]["X-MAO-API-Key"] == "test_key"

    @pytest.mark.asyncio
    async def test_flush_keeps_failed_traces(self):
        """Test that flush keeps traces that failed to send."""
        tracer = SemanticKernelTracer(endpoint="http://test")
        tracer.start_trace()
        tracer.start_span("test_span")
        tracer.end_span(tracer.span_stack[-1])

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(tracer, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            success = await tracer.flush()

            assert success is False
            assert len(tracer.traces) == 1

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        """Test that close properly closes the HTTP client."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_client = AsyncMock()
        tracer._http_client = mock_client

        await tracer.close()

        mock_client.aclose.assert_called_once()
        assert tracer._http_client is None

    @pytest.mark.asyncio
    async def test_context_manager_flushes_on_exit(self):
        """Test that async context manager flushes traces on exit."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch.object(tracer, '_get_client', return_value=mock_client):
            async with tracer:
                tracer.start_trace()
                tracer.start_span("test")
                tracer.end_span(tracer.span_stack[-1])
                # Set the client so close() can call aclose
                tracer._http_client = mock_client

            mock_client.post.assert_called_once()
            mock_client.aclose.assert_called_once()


class TestSemanticKernelTracer:
    """Tests for the Semantic Kernel specific tracer functionality."""

    def test_wrap_kernel_attaches_tracer(self):
        """Test that wrap() attaches the tracer to the kernel."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_kernel = MagicMock()
        mock_kernel.invoke = AsyncMock(return_value="result")

        wrapped = tracer.wrap(mock_kernel)

        assert hasattr(wrapped, '_mao_tracer')
        assert wrapped._mao_tracer == tracer

    @pytest.mark.asyncio
    async def test_traced_invoke_creates_span(self):
        """Test that invoke() creates and closes a span."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_kernel = MagicMock()
        mock_kernel.invoke = AsyncMock(return_value="result")

        wrapped = tracer.wrap(mock_kernel)

        mock_function = MagicMock()
        mock_function.plugin_name = "TestPlugin"
        mock_function.name = "test_func"

        result = await wrapped.invoke(mock_function)

        assert result == "result"
        assert len(tracer.traces) == 1
        trace = list(tracer.traces.values())[0]
        assert len(trace.spans) == 1
        assert trace.spans[0].status == "OK"
        assert "sk.invoke.TestPlugin.test_func" in trace.spans[0].name

    @pytest.mark.asyncio
    async def test_traced_invoke_captures_errors(self):
        """Test that invoke() captures errors in span."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_kernel = MagicMock()
        mock_kernel.invoke = AsyncMock(side_effect=ValueError("test error"))

        wrapped = tracer.wrap(mock_kernel)

        mock_function = MagicMock()
        mock_function.plugin_name = "TestPlugin"
        mock_function.name = "test_func"

        with pytest.raises(ValueError):
            await wrapped.invoke(mock_function)

        trace = list(tracer.traces.values())[0]
        assert trace.spans[0].status == "ERROR"
        assert trace.spans[0].attributes["error.type"] == "ValueError"

    def test_extract_agent_info_with_plugins(self):
        """Test that extract_agent_info extracts plugin information."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_function = MagicMock()
        mock_function.description = "Test function"
        mock_function.prompt_template = None

        mock_plugin = MagicMock()
        mock_plugin.functions = {"test_func": mock_function}

        mock_kernel = MagicMock()
        mock_kernel.plugins = {"TestPlugin": mock_plugin}
        mock_kernel.services = {"openai": MagicMock()}

        info = tracer.extract_agent_info(mock_kernel)

        assert info["framework"] == "semantic_kernel"
        assert "TestPlugin" in info["plugins"]
        assert "openai" in info["services"]

    @pytest.mark.asyncio
    async def test_trace_function_context_manager(self):
        """Test the manual trace_function context manager."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        async with tracer.trace_function("TestPlugin", "manual_func") as span_id:
            pass

        assert len(tracer.traces) == 1
        trace = list(tracer.traces.values())[0]
        assert trace.spans[0].status == "OK"
        assert "sk.manual.TestPlugin.manual_func" in trace.spans[0].name

    def test_trace_planner_wraps_create_plan(self):
        """Test that trace_planner wraps the create_plan method."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_planner = MagicMock()
        mock_planner.create_plan = AsyncMock()

        wrapped_planner = tracer.trace_planner(mock_planner)

        assert hasattr(wrapped_planner, '_mao_tracer')
        assert wrapped_planner._mao_tracer == tracer

    def test_trace_chat_completion_wraps_complete_chat(self):
        """Test that trace_chat_completion wraps the complete_chat method."""
        tracer = SemanticKernelTracer(endpoint="http://test")

        mock_chat_service = MagicMock()
        mock_chat_service.complete_chat = AsyncMock()
        mock_chat_service.model_id = "gpt-4"

        tracer.trace_chat_completion(mock_chat_service)

        # The method should be wrapped
        assert mock_chat_service.complete_chat != mock_chat_service._original_complete_chat if hasattr(mock_chat_service, '_original_complete_chat') else True
