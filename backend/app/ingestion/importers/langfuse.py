"""Langfuse trace importer.

Imports traces from Langfuse export format (JSON with traces/observations structure)
into the UniversalTrace abstraction for Pisama detection.

Supports:
- Langfuse JSON export (traces array with nested observations)
- Single trace with observations
- Langfuse API response format
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus
from .base import BaseImporter


class LangfuseImporter(BaseImporter):
    """Importer for Langfuse trace format.

    Langfuse traces contain:
    - traces[].id: Trace ID
    - traces[].observations[]: Observation spans
    - Each observation has: id, name, type, startTime, endTime, input, output, model, usage
    """

    @property
    def format_name(self) -> str:
        return "langfuse"

    def import_trace(self, content: str) -> UniversalTrace:
        data = json.loads(content)

        if not self._check_depth(data):
            raise ValueError("JSON depth exceeds limit")

        traces = self._extract_traces(data)
        if not traces:
            raise ValueError("No Langfuse traces found in content")

        all_spans = []
        trace_id = None

        for trace in traces:
            trace_id = trace.get("id") or trace_id or str(uuid.uuid4())
            for span in self._parse_trace(trace, trace_id):
                all_spans.append(span)

        if not all_spans:
            raise ValueError("No spans found in Langfuse traces")

        return UniversalTrace(
            trace_id=trace_id or str(uuid.uuid4()),
            spans=all_spans,
            source_format=self.format_name,
        )

    def import_spans(self, content: str) -> Iterator[UniversalSpan]:
        data = json.loads(content)

        if not self._check_depth(data):
            raise ValueError("JSON depth exceeds limit")

        traces = self._extract_traces(data)

        for trace in traces:
            trace_id = trace.get("id", str(uuid.uuid4()))
            yield from self._parse_trace(trace, trace_id)

    def _extract_traces(self, data: Any) -> List[Dict]:
        """Extract trace objects from various Langfuse response formats."""
        if isinstance(data, dict):
            if "traces" in data:
                return data["traces"]
            if "observations" in data:
                return [data]
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            if "id" in data and ("input" in data or "output" in data):
                return [{"id": data.get("id"), "observations": [data]}]
        if isinstance(data, list):
            return data
        return []

    def _parse_trace(self, trace: Dict, trace_id: str) -> Iterator[UniversalSpan]:
        """Parse a single Langfuse trace into UniversalSpans."""
        observations = trace.get("observations", [])

        for obs in observations:
            obs_type = (obs.get("type") or "").lower()
            span_type = self._map_observation_type(obs_type)

            input_data = obs.get("input") or {}
            output_data = obs.get("output") or {}
            if isinstance(input_data, str):
                input_data = {"text": input_data}
            if isinstance(output_data, str):
                output_data = {"text": output_data}

            usage = obs.get("usage") or obs.get("usageDetails") or {}
            input_tokens = usage.get("input", 0) or usage.get("promptTokens", 0) or usage.get("prompt_tokens", 0)
            output_tokens = usage.get("output", 0) or usage.get("completionTokens", 0) or usage.get("completion_tokens", 0)

            error_msg, error_type = self._extract_error(obs)
            status = SpanStatus.ERROR if obs.get("level") == "ERROR" or error_msg else SpanStatus.OK

            model = obs.get("model") or obs.get("modelId")

            yield UniversalSpan(
                id=obs.get("id", str(uuid.uuid4())),
                trace_id=trace_id,
                name=obs.get("name", "unknown"),
                span_type=span_type,
                status=status,
                start_time=self._parse_timestamp(obs.get("startTime")),
                end_time=self._parse_timestamp(obs.get("endTime")) if obs.get("endTime") else None,
                parent_id=obs.get("parentObservationId"),
                agent_id=obs.get("name"),
                agent_name=obs.get("name"),
                input_data=input_data,
                output_data=output_data,
                model=model,
                tokens_input=int(input_tokens),
                tokens_output=int(output_tokens),
                error=error_msg,
                error_type=error_type,
                source_format="langfuse",
                metadata={
                    "type": obs.get("type"),
                    "level": obs.get("level"),
                    "version": obs.get("version"),
                    "model_parameters": obs.get("modelParameters"),
                },
            )

    def _map_observation_type(self, obs_type: str) -> SpanType:
        """Map Langfuse observation type to SpanType."""
        mapping = {
            "generation": SpanType.LLM_CALL,
            "span": SpanType.CHAIN,
            "event": SpanType.UNKNOWN,
            "tool": SpanType.TOOL_CALL,
            "retrieval": SpanType.RETRIEVAL,
            "agent": SpanType.AGENT,
        }
        return mapping.get(obs_type, SpanType.UNKNOWN)
