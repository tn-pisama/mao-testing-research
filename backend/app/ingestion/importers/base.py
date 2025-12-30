"""Base importer class for trace formats."""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus


class BaseImporter(ABC):
    """Abstract base class for trace importers.

    All importers must implement the import_trace method to convert
    their specific format into UniversalTrace.
    """

    MAX_JSON_DEPTH = 50
    MAX_CONTENT_SIZE = 50 * 1024 * 1024  # 50MB limit

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the name of this format."""
        pass

    @abstractmethod
    def import_trace(self, content: str) -> UniversalTrace:
        """Import trace content and return UniversalTrace.

        Args:
            content: Raw trace content (usually JSON)

        Returns:
            UniversalTrace with parsed spans
        """
        pass

    @abstractmethod
    def import_spans(self, content: str) -> Iterator[UniversalSpan]:
        """Import spans from content as iterator.

        Args:
            content: Raw trace content

        Yields:
            UniversalSpan instances
        """
        pass

    @classmethod
    def detect_format(cls, content: str) -> str:
        """Detect the format of trace content.

        Args:
            content: Raw content to analyze

        Returns:
            Detected format name
        """
        try:
            # Try to parse as JSON
            sample = content.strip()
            if sample.startswith('['):
                data = json.loads(sample)
                if isinstance(data, list) and len(data) > 0:
                    sample_item = data[0]
                else:
                    return "generic"
            elif sample.startswith('{'):
                sample_item = json.loads(sample.split('\n')[0])
            else:
                return "generic"

            # Check for LangSmith format markers
            if "run_type" in sample_item or "session_id" in sample_item:
                return "langsmith"

            # Check for LangFuse format markers
            if "traces" in sample_item or "observations" in sample_item:
                return "langfuse"

            # Check for OTEL format markers
            if "resourceSpans" in sample_item or "traceId" in sample_item:
                return "otel"

            # Check for n8n format markers
            if "executionId" in sample_item or "workflowId" in sample_item:
                return "n8n"

            return "generic"
        except (json.JSONDecodeError, IndexError, KeyError):
            return "generic"

    def _parse_timestamp(self, ts: Any) -> datetime:
        """Parse timestamp from various formats.

        Args:
            ts: Timestamp in various formats (datetime, int, float, str)

        Returns:
            Parsed datetime
        """
        if isinstance(ts, datetime):
            return ts

        if isinstance(ts, (int, float)):
            # Handle milliseconds vs seconds
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts)

        if isinstance(ts, str):
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]
            for fmt in formats:
                try:
                    cleaned = ts.replace("+00:00", "Z").replace("Z", "")
                    if "." in cleaned:
                        date_part, frac = cleaned.rsplit(".", 1)
                        # Truncate microseconds to 6 digits
                        frac = frac[:6].ljust(6, "0")
                        cleaned = f"{date_part}.{frac}"
                    return datetime.strptime(cleaned, fmt.replace("Z", "").replace("%fZ", "%f"))
                except ValueError:
                    continue

        return datetime.utcnow()

    def _check_depth(self, obj: Any, depth: int = 0) -> bool:
        """Check if JSON depth is within limits.

        Args:
            obj: Object to check
            depth: Current depth

        Returns:
            True if depth is OK, False otherwise
        """
        if depth > self.MAX_JSON_DEPTH:
            return False
        if isinstance(obj, dict):
            return all(self._check_depth(v, depth + 1) for v in obj.values())
        if isinstance(obj, list):
            return all(self._check_depth(v, depth + 1) for v in obj)
        return True

    def _infer_span_type(self, data: Dict[str, Any]) -> SpanType:
        """Infer span type from data fields.

        Args:
            data: Span data dictionary

        Returns:
            Inferred SpanType
        """
        # Check explicit type fields
        type_field = data.get("type") or data.get("span_type") or data.get("run_type") or ""
        type_lower = type_field.lower()

        if "tool" in type_lower or "function" in type_lower:
            return SpanType.TOOL_CALL
        if "llm" in type_lower or "chat" in type_lower or "completion" in type_lower:
            return SpanType.LLM_CALL
        if "chain" in type_lower:
            return SpanType.CHAIN
        if "agent" in type_lower:
            return SpanType.AGENT
        if "retriev" in type_lower or "rag" in type_lower:
            return SpanType.RETRIEVAL
        if "handoff" in type_lower or "transfer" in type_lower:
            return SpanType.HANDOFF

        # Check for tool-related fields
        if "tool_calls" in data or "function_call" in data or "tool_name" in data:
            return SpanType.TOOL_CALL

        # Check for LLM-related fields
        if "prompt" in data or "completion" in data or "model" in data:
            return SpanType.LLM_CALL

        return SpanType.UNKNOWN

    def _infer_status(self, data: Dict[str, Any]) -> SpanStatus:
        """Infer span status from data fields.

        Args:
            data: Span data dictionary

        Returns:
            Inferred SpanStatus
        """
        # Check explicit status fields
        if data.get("error") or data.get("exception") or data.get("error_message"):
            return SpanStatus.ERROR

        status = data.get("status", "").lower()
        if status in ["error", "failed", "failure"]:
            return SpanStatus.ERROR
        if status in ["timeout", "timed_out"]:
            return SpanStatus.TIMEOUT
        if status in ["cancelled", "canceled", "aborted"]:
            return SpanStatus.CANCELLED

        return SpanStatus.OK

    def _extract_error(self, data: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """Extract error message and type from data.

        Args:
            data: Span data dictionary

        Returns:
            Tuple of (error_message, error_type)
        """
        error_msg = None
        error_type = None

        # Check various error field names
        for key in ["error", "error_message", "exception", "exception_message", "failure_reason"]:
            if key in data:
                val = data[key]
                if isinstance(val, dict):
                    error_msg = val.get("message") or str(val)
                    error_type = val.get("type") or val.get("name")
                elif isinstance(val, str):
                    error_msg = val
                break

        return error_msg, error_type

    def _extract_tokens(self, data: Dict[str, Any]) -> tuple[int, int]:
        """Extract token counts from data.

        Args:
            data: Span data dictionary

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        # Check various token field patterns
        usage = data.get("usage") or data.get("token_usage") or {}

        input_tokens = (
            usage.get("prompt_tokens") or
            usage.get("input_tokens") or
            data.get("prompt_tokens") or
            data.get("input_tokens") or
            0
        )

        output_tokens = (
            usage.get("completion_tokens") or
            usage.get("output_tokens") or
            data.get("completion_tokens") or
            data.get("output_tokens") or
            0
        )

        return int(input_tokens), int(output_tokens)
