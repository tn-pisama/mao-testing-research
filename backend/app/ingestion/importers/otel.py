"""OpenTelemetry (OTEL) trace importer."""

import json
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional
import uuid

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus
from app.ingestion.importers.base import BaseImporter


class OTELImporter(BaseImporter):
    """Importer for OpenTelemetry trace format.

    Handles OTEL export format with resourceSpans, scopeSpans, and spans.
    Supports both JSON and OTLP formats.
    """

    @property
    def format_name(self) -> str:
        return "otel"

    def import_trace(self, content: str) -> UniversalTrace:
        """Import OTEL trace content.

        Args:
            content: Raw OTEL JSON content

        Returns:
            UniversalTrace with parsed spans
        """
        spans = list(self.import_spans(content))

        # Determine trace ID from spans
        trace_id = spans[0].trace_id if spans else str(uuid.uuid4())

        return UniversalTrace(
            trace_id=trace_id,
            spans=spans,
            source_format="otel",
        )

    def import_spans(self, content: str) -> Iterator[UniversalSpan]:
        """Import spans from OTEL content.

        Args:
            content: Raw OTEL JSON content

        Yields:
            UniversalSpan instances
        """
        if len(content) > self.MAX_CONTENT_SIZE:
            raise ValueError(f"Content exceeds maximum size of {self.MAX_CONTENT_SIZE} bytes")

        data = json.loads(content)

        if not self._check_depth(data):
            raise ValueError(f"JSON depth exceeds maximum of {self.MAX_JSON_DEPTH}")

        # Handle different OTEL formats
        if isinstance(data, dict):
            if "resourceSpans" in data:
                # Standard OTEL export format
                yield from self._parse_resource_spans(data["resourceSpans"])
            elif "traceId" in data or "spanId" in data:
                # Single span format
                yield self._parse_single_span(data)
            elif "spans" in data:
                # Simplified spans array
                for span_data in data["spans"]:
                    yield self._parse_single_span(span_data)
            else:
                # Try to extract spans from unknown structure
                yield from self._extract_spans_recursive(data)
        elif isinstance(data, list):
            # Array of resourceSpans or spans
            if len(data) > 0:
                if "scopeSpans" in data[0] or "instrumentationLibrarySpans" in data[0]:
                    yield from self._parse_resource_spans(data)
                else:
                    for item in data:
                        yield self._parse_single_span(item)

    def _parse_resource_spans(self, resource_spans: List[Dict]) -> Iterator[UniversalSpan]:
        """Parse resourceSpans array.

        Args:
            resource_spans: Array of resourceSpans objects

        Yields:
            UniversalSpan instances
        """
        for rs in resource_spans:
            resource = rs.get("resource", {})
            resource_attrs = self._parse_attributes(resource.get("attributes", []))

            # Handle both scopeSpans and instrumentationLibrarySpans (older format)
            scope_spans = rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans", [])

            for ss in scope_spans:
                scope = ss.get("scope") or ss.get("instrumentationLibrary", {})
                scope_name = scope.get("name", "")

                for span_data in ss.get("spans", []):
                    yield self._parse_otel_span(span_data, resource_attrs, scope_name)

    def _parse_otel_span(
        self,
        span_data: Dict,
        resource_attrs: Dict[str, Any],
        scope_name: str = ""
    ) -> UniversalSpan:
        """Parse a single OTEL span.

        Args:
            span_data: Span data dictionary
            resource_attrs: Resource attributes
            scope_name: Instrumentation scope name

        Returns:
            UniversalSpan instance
        """
        # Parse basic fields
        span_id = span_data.get("spanId", str(uuid.uuid4()))
        trace_id = span_data.get("traceId", str(uuid.uuid4()))
        parent_span_id = span_data.get("parentSpanId")
        name = span_data.get("name", "unknown")

        # Parse timestamps (OTEL uses nanoseconds)
        start_time = self._parse_otel_timestamp(span_data.get("startTimeUnixNano"))
        end_time = self._parse_otel_timestamp(span_data.get("endTimeUnixNano"))

        # Parse attributes
        attrs = self._parse_attributes(span_data.get("attributes", []))

        # Determine span type from attributes and name
        span_type = self._infer_otel_span_type(name, attrs, scope_name)

        # Parse status
        status_data = span_data.get("status", {})
        status = self._parse_otel_status(status_data)

        # Extract error information
        error = None
        error_type = None
        if status == SpanStatus.ERROR:
            error = status_data.get("message") or attrs.get("exception.message")
            error_type = attrs.get("exception.type")

        # Extract LLM-specific fields
        prompt = attrs.get("llm.prompt") or attrs.get("gen_ai.prompt") or attrs.get("input")
        response = attrs.get("llm.response") or attrs.get("gen_ai.completion") or attrs.get("output")
        model = attrs.get("llm.model") or attrs.get("gen_ai.model") or attrs.get("model")

        # Extract tool-specific fields
        tool_name = attrs.get("tool.name") or attrs.get("function.name")
        tool_args = attrs.get("tool.arguments") or attrs.get("function.arguments")
        tool_result = attrs.get("tool.result") or attrs.get("function.result")

        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except json.JSONDecodeError:
                tool_args = {"raw": tool_args}

        if isinstance(tool_result, str):
            try:
                tool_result = json.loads(tool_result)
            except json.JSONDecodeError:
                tool_result = {"raw": tool_result}

        # Extract token counts
        tokens_input = int(attrs.get("llm.token_count.prompt", 0) or
                          attrs.get("gen_ai.usage.input_tokens", 0) or 0)
        tokens_output = int(attrs.get("llm.token_count.completion", 0) or
                           attrs.get("gen_ai.usage.output_tokens", 0) or 0)

        # Extract agent ID
        agent_id = (attrs.get("agent.id") or
                   attrs.get("agent.name") or
                   resource_attrs.get("service.name"))

        # Calculate duration
        duration_ms = None
        if start_time and end_time:
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return UniversalSpan(
            id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            span_type=span_type,
            status=status,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            prompt=prompt,
            response=response,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            error=error,
            error_type=error_type,
            metadata={
                **attrs,
                "otel.scope": scope_name,
                "otel.resource": resource_attrs,
            },
        )

    def _parse_single_span(self, span_data: Dict) -> UniversalSpan:
        """Parse a single span without resource context.

        Args:
            span_data: Span data dictionary

        Returns:
            UniversalSpan instance
        """
        return self._parse_otel_span(span_data, {}, "")

    def _parse_otel_timestamp(self, ts: Optional[Any]) -> Optional[datetime]:
        """Parse OTEL timestamp (nanoseconds since epoch).

        Args:
            ts: Timestamp in nanoseconds or string

        Returns:
            Parsed datetime or None
        """
        if ts is None:
            return None

        if isinstance(ts, str):
            try:
                ts = int(ts)
            except ValueError:
                return self._parse_timestamp(ts)

        if isinstance(ts, (int, float)):
            # OTEL uses nanoseconds
            if ts > 1e18:  # Nanoseconds
                ts = ts / 1e9
            elif ts > 1e15:  # Microseconds
                ts = ts / 1e6
            elif ts > 1e12:  # Milliseconds
                ts = ts / 1e3
            return datetime.fromtimestamp(ts)

        return None

    def _parse_attributes(self, attrs: List[Dict]) -> Dict[str, Any]:
        """Parse OTEL attributes array to dictionary.

        Args:
            attrs: Array of {key, value} objects

        Returns:
            Dictionary of attributes
        """
        result = {}

        if isinstance(attrs, dict):
            # Already a dictionary
            return attrs

        for attr in attrs:
            key = attr.get("key", "")
            value_obj = attr.get("value", {})

            # OTEL value types
            if "stringValue" in value_obj:
                result[key] = value_obj["stringValue"]
            elif "intValue" in value_obj:
                result[key] = int(value_obj["intValue"])
            elif "doubleValue" in value_obj:
                result[key] = float(value_obj["doubleValue"])
            elif "boolValue" in value_obj:
                result[key] = value_obj["boolValue"]
            elif "arrayValue" in value_obj:
                result[key] = [
                    self._parse_attribute_value(v)
                    for v in value_obj["arrayValue"].get("values", [])
                ]
            elif "kvlistValue" in value_obj:
                result[key] = {
                    kv.get("key", ""): self._parse_attribute_value(kv.get("value", {}))
                    for kv in value_obj["kvlistValue"].get("values", [])
                }
            else:
                # Fallback: use first value found
                for v_key in value_obj:
                    result[key] = value_obj[v_key]
                    break

        return result

    def _parse_attribute_value(self, value_obj: Dict) -> Any:
        """Parse a single OTEL attribute value.

        Args:
            value_obj: Value object

        Returns:
            Parsed value
        """
        if "stringValue" in value_obj:
            return value_obj["stringValue"]
        elif "intValue" in value_obj:
            return int(value_obj["intValue"])
        elif "doubleValue" in value_obj:
            return float(value_obj["doubleValue"])
        elif "boolValue" in value_obj:
            return value_obj["boolValue"]
        return str(value_obj)

    def _parse_otel_status(self, status_data: Dict) -> SpanStatus:
        """Parse OTEL status to SpanStatus.

        Args:
            status_data: Status object

        Returns:
            SpanStatus
        """
        code = status_data.get("code", 0)

        # OTEL status codes: 0 = UNSET, 1 = OK, 2 = ERROR
        if code == 2:
            return SpanStatus.ERROR
        elif code == 1:
            return SpanStatus.OK

        # Also check string status
        status_str = str(status_data.get("status", "")).upper()
        if status_str == "ERROR":
            return SpanStatus.ERROR

        return SpanStatus.OK

    def _infer_otel_span_type(
        self,
        name: str,
        attrs: Dict[str, Any],
        scope_name: str
    ) -> SpanType:
        """Infer span type from OTEL span data.

        Args:
            name: Span name
            attrs: Span attributes
            scope_name: Instrumentation scope name

        Returns:
            Inferred SpanType
        """
        name_lower = name.lower()
        scope_lower = scope_name.lower()

        # Check for LLM spans
        if any(x in name_lower for x in ["llm", "chat", "completion", "generate"]):
            return SpanType.LLM_CALL
        if any(x in scope_lower for x in ["openai", "anthropic", "langchain.llm"]):
            return SpanType.LLM_CALL
        if attrs.get("llm.model") or attrs.get("gen_ai.model"):
            return SpanType.LLM_CALL

        # Check for tool/function calls
        if any(x in name_lower for x in ["tool", "function", "call"]):
            return SpanType.TOOL_CALL
        if attrs.get("tool.name") or attrs.get("function.name"):
            return SpanType.TOOL_CALL

        # Check for agent spans
        if "agent" in name_lower or "agent" in scope_lower:
            return SpanType.AGENT
        if attrs.get("agent.id") or attrs.get("agent.name"):
            return SpanType.AGENT

        # Check for retrieval/RAG
        if any(x in name_lower for x in ["retriev", "search", "rag", "vector"]):
            return SpanType.RETRIEVAL

        # Check for chain
        if "chain" in name_lower or "langchain.chain" in scope_lower:
            return SpanType.CHAIN

        # Check for handoff
        if any(x in name_lower for x in ["handoff", "transfer", "delegate"]):
            return SpanType.HANDOFF

        return SpanType.UNKNOWN

    def _extract_spans_recursive(self, data: Any, depth: int = 0) -> Iterator[UniversalSpan]:
        """Recursively extract spans from unknown structure.

        Args:
            data: Data to search
            depth: Current depth

        Yields:
            UniversalSpan instances
        """
        if depth > 10:
            return

        if isinstance(data, dict):
            # Check if this looks like a span
            if "spanId" in data or "traceId" in data:
                yield self._parse_single_span(data)
            else:
                for value in data.values():
                    yield from self._extract_spans_recursive(value, depth + 1)
        elif isinstance(data, list):
            for item in data:
                yield from self._extract_spans_recursive(item, depth + 1)
