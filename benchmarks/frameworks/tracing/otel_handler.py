"""OpenTelemetry callback handler for LangChain tracing."""

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode


def setup_tracing(
    service_name: str = "langchain-agents",
    otlp_endpoint: str | None = None,
    use_console: bool = True,
) -> trace.Tracer:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Name of the service for traces
        otlp_endpoint: OTLP exporter endpoint (optional)
        use_console: Whether to also export to console

    Returns:
        Configured tracer instance
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if use_console:
        console_processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(console_processor)

    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        otlp_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(otlp_processor)

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


class OpenTelemetryCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that creates OpenTelemetry spans."""

    def __init__(self, tracer: trace.Tracer | None = None) -> None:
        """Initialize the handler with an optional tracer."""
        super().__init__()
        self.tracer = tracer or trace.get_tracer("langchain-agents")
        self._spans: dict[UUID, trace.Span] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Start a span when LLM call begins."""
        model_name = serialized.get("kwargs", {}).get("model", "unknown")

        span = self.tracer.start_span(
            name=f"llm.{model_name}",
            attributes={
                "langchain.component": "llm",
                "llm.model": model_name,
                "llm.prompt_count": len(prompts),
                "llm.prompts": str(prompts)[:1000],  # Truncate for safety
            },
        )
        self._spans[run_id] = span

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """End the LLM span with response details."""
        span = self._spans.pop(run_id, None)
        if span:
            token_usage = response.llm_output or {}
            if "token_usage" in token_usage:
                usage = token_usage["token_usage"]
                span.set_attribute("llm.input_tokens", usage.get("prompt_tokens", 0))
                span.set_attribute("llm.output_tokens", usage.get("completion_tokens", 0))
                span.set_attribute("llm.total_tokens", usage.get("total_tokens", 0))

            span.set_attribute("llm.generation_count", len(response.generations))
            span.set_status(Status(StatusCode.OK))
            span.end()

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record error on LLM span."""
        span = self._spans.pop(run_id, None)
        if span:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.end()

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Start a span for chain execution."""
        chain_name = serialized.get("name", serialized.get("id", ["unknown"])[-1])

        span = self.tracer.start_span(
            name=f"chain.{chain_name}",
            attributes={
                "langchain.component": "chain",
                "chain.name": chain_name,
                "chain.input_keys": str(list(inputs.keys())),
            },
        )
        self._spans[run_id] = span

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """End the chain span."""
        span = self._spans.pop(run_id, None)
        if span:
            span.set_attribute("chain.output_keys", str(list(outputs.keys())))
            span.set_status(Status(StatusCode.OK))
            span.end()

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record error on chain span."""
        span = self._spans.pop(run_id, None)
        if span:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.end()

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record agent action as a span event."""
        span = self._spans.get(run_id)
        if span:
            span.add_event(
                "agent_action",
                attributes={
                    "action.tool": getattr(action, "tool", "unknown"),
                    "action.tool_input": str(getattr(action, "tool_input", ""))[:500],
                },
            )

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record agent finish as a span event."""
        span = self._spans.get(run_id)
        if span:
            span.add_event(
                "agent_finish",
                attributes={
                    "output": str(getattr(finish, "return_values", ""))[:500],
                },
            )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Start a span for tool execution."""
        tool_name = serialized.get("name", "unknown_tool")

        span = self.tracer.start_span(
            name=f"tool.{tool_name}",
            attributes={
                "langchain.component": "tool",
                "tool.name": tool_name,
                "tool.input": input_str[:500],
            },
        )
        self._spans[run_id] = span

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """End the tool span."""
        span = self._spans.pop(run_id, None)
        if span:
            span.set_attribute("tool.output", str(output)[:500])
            span.set_status(Status(StatusCode.OK))
            span.end()

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record error on tool span."""
        span = self._spans.pop(run_id, None)
        if span:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.end()
