"""Arize Phoenix trace importer.

Imports traces from Phoenix export format. Phoenix uses OpenTelemetry natively,
so this importer handles Phoenix's OTEL-based JSON export format.

Supports:
- Phoenix JSON export (array of spans with OTEL attributes)
- Phoenix DataFrame export (list of span dicts)
- Standard OTEL JSON format forwarded from Phoenix
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus
from .base import BaseImporter


class PhoenixImporter(BaseImporter):
    """Importer for Arize Phoenix trace format.

    Phoenix exports traces as OTEL spans with additional Phoenix-specific
    attributes. This importer handles both Phoenix's native JSON export
    and standard OTEL JSON forwarded from Phoenix.
    """

    @property
    def format_name(self) -> str:
        return "phoenix"

    def import_trace(self, content: str) -> UniversalTrace:
        data = json.loads(content)

        if not self._check_depth(data):
            raise ValueError("JSON depth exceeds limit")

        spans = list(self.import_spans(content))
        if not spans:
            raise ValueError("No spans found in Phoenix trace data")

        trace_id = spans[0].trace_id

        return UniversalTrace(
            trace_id=trace_id,
            spans=spans,
            source_format=self.format_name,
        )

    def import_spans(self, content: str) -> Iterator[UniversalSpan]:
        data = json.loads(content)

        if not self._check_depth(data):
            raise ValueError("JSON depth exceeds limit")

        # Handle OTEL resourceSpans format (forwarded from Phoenix)
        if isinstance(data, dict) and "resourceSpans" in data:
            yield from self._parse_otel_format(data)
            return

        # Handle Phoenix JSON export (array of span objects)
        if isinstance(data, list):
            for item in data:
                yield from self._parse_phoenix_span(item)
            return

        # Handle single span or wrapped data
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    yield from self._parse_phoenix_span(item)
                return
            yield from self._parse_phoenix_span(data)

    def _parse_phoenix_span(self, span: Dict) -> Iterator[UniversalSpan]:
        """Parse a Phoenix span dict into UniversalSpan."""
        if not isinstance(span, dict):
            return

        # Phoenix uses context.trace_id and context.span_id
        context = span.get("context", {})
        trace_id = context.get("trace_id") or span.get("trace_id") or span.get("traceId") or str(uuid.uuid4())
        span_id = context.get("span_id") or span.get("span_id") or span.get("spanId") or str(uuid.uuid4())

        # Extract attributes (Phoenix stores data in attributes dict)
        attributes = span.get("attributes", {})

        # Determine span type from Phoenix span_kind or attributes
        span_kind = span.get("span_kind") or span.get("kind") or ""
        span_type = self._map_span_kind(str(span_kind), attributes)

        # Extract input/output from attributes
        input_data = {}
        output_data = {}

        input_value = attributes.get("input.value") or attributes.get("input")
        if input_value:
            input_data = self._safe_parse_json(input_value) if isinstance(input_value, str) else {"value": input_value}

        output_value = attributes.get("output.value") or attributes.get("output")
        if output_value:
            output_data = self._safe_parse_json(output_value) if isinstance(output_value, str) else {"value": output_value}

        # Extract LLM-specific fields
        model = attributes.get("llm.model_name") or attributes.get("gen_ai.request.model") or attributes.get("model")
        input_tokens = (
            attributes.get("llm.token_count.prompt") or
            attributes.get("gen_ai.usage.prompt_tokens") or
            attributes.get("llm.usage.prompt_tokens") or 0
        )
        output_tokens = (
            attributes.get("llm.token_count.completion") or
            attributes.get("gen_ai.usage.completion_tokens") or
            attributes.get("llm.usage.completion_tokens") or 0
        )

        # Extract tool info
        tool_name = attributes.get("tool.name") or attributes.get("tool_name")

        # Status
        status_obj = span.get("status", {})
        status_code = status_obj.get("status_code", "") if isinstance(status_obj, dict) else str(status_obj)
        status = SpanStatus.ERROR if "error" in str(status_code).lower() else SpanStatus.OK

        error_msg = None
        if isinstance(status_obj, dict):
            error_msg = status_obj.get("message") or status_obj.get("description")
        events = span.get("events", [])
        for event in events:
            if isinstance(event, dict) and event.get("name") == "exception":
                event_attrs = event.get("attributes", {})
                error_msg = event_attrs.get("exception.message") or error_msg
                status = SpanStatus.ERROR

        yield UniversalSpan(
            id=span_id,
            trace_id=trace_id,
            name=span.get("name", "unknown"),
            span_type=span_type,
            status=status,
            start_time=self._parse_timestamp(span.get("start_time")),
            end_time=self._parse_timestamp(span.get("end_time")) if span.get("end_time") else None,
            parent_id=span.get("parent_id") or context.get("parent_id"),
            agent_id=attributes.get("agent.id") or attributes.get("agent_id"),
            agent_name=attributes.get("agent.name") or span.get("name"),
            input_data=input_data,
            output_data=output_data,
            model=model,
            tokens_input=int(input_tokens),
            tokens_output=int(output_tokens),
            tool_name=tool_name,
            error=error_msg,
            source_format="phoenix",
            metadata={
                "span_kind": span_kind,
                "phoenix_project": attributes.get("phoenix.project"),
            },
        )

    def _parse_otel_format(self, data: Dict) -> Iterator[UniversalSpan]:
        """Parse OTEL resourceSpans format (forwarded from Phoenix)."""
        for resource_spans in data.get("resourceSpans", []):
            for scope_spans in resource_spans.get("scopeSpans", []):
                for span in scope_spans.get("spans", []):
                    # Convert OTEL attributes list to dict
                    attributes = {}
                    for attr in span.get("attributes", []):
                        key = attr.get("key", "")
                        value = attr.get("value", {})
                        attributes[key] = (
                            value.get("stringValue") or
                            value.get("intValue") or
                            value.get("doubleValue") or
                            value.get("boolValue") or
                            str(value)
                        )

                    span_type = self._map_span_kind(str(span.get("kind", "")), attributes)

                    yield UniversalSpan(
                        id=span.get("spanId", str(uuid.uuid4())),
                        trace_id=span.get("traceId", str(uuid.uuid4())),
                        name=span.get("name", "unknown"),
                        span_type=span_type,
                        status=SpanStatus.OK,
                        start_time=self._parse_timestamp(span.get("startTimeUnixNano")),
                        end_time=self._parse_timestamp(span.get("endTimeUnixNano")) if span.get("endTimeUnixNano") else None,
                        parent_id=span.get("parentSpanId"),
                        input_data={},
                        output_data={},
                        model=attributes.get("gen_ai.request.model"),
                        source_format="phoenix",
                        metadata={"otel_kind": span.get("kind")},
                    )

    def _map_span_kind(self, kind: str, attributes: Dict) -> SpanType:
        """Map Phoenix/OTEL span kind to SpanType."""
        kind_lower = kind.lower()

        # Phoenix-specific span kinds
        if "llm" in kind_lower:
            return SpanType.LLM_CALL
        if "tool" in kind_lower:
            return SpanType.TOOL_CALL
        if "chain" in kind_lower:
            return SpanType.CHAIN
        if "agent" in kind_lower:
            return SpanType.AGENT
        if "retriever" in kind_lower or "retrieval" in kind_lower:
            return SpanType.RETRIEVAL

        # Check attributes for type hints
        if attributes.get("openinference.span.kind"):
            otel_kind = attributes["openinference.span.kind"].lower()
            if "llm" in otel_kind:
                return SpanType.LLM_CALL
            if "tool" in otel_kind:
                return SpanType.TOOL_CALL
            if "chain" in otel_kind:
                return SpanType.CHAIN
            if "agent" in otel_kind:
                return SpanType.AGENT
            if "retriever" in otel_kind:
                return SpanType.RETRIEVAL

        if "gen_ai" in str(attributes):
            return SpanType.LLM_CALL

        return SpanType.UNKNOWN

    def _safe_parse_json(self, value: str) -> Dict:
        """Try to parse a string as JSON, return as dict."""
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"text": value}
