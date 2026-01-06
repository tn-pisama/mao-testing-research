"""MAO Testing SDK Span implementation."""

from __future__ import annotations
import time
import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from .session import TraceSession

# Attribute size limits for conversation trace support
# Increased from standard 4KB to support multi-turn conversations
MAX_ATTRIBUTE_LENGTH = 16384  # 16KB for standard attributes
MAX_ACCUMULATED_CONTEXT = 65536  # 64KB for accumulated conversation context
MAX_CONTENT_LENGTH = 32768  # 32KB for content fields


@dataclass
class SpanData:
    """Data captured for a span."""
    name: str
    span_id: str
    parent_span_id: Optional[str]
    start_time_ns: int
    end_time_ns: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"
    status_message: Optional[str] = None


class Span:
    """A span representing a single operation within a trace."""
    
    def __init__(
        self,
        name: str,
        session: "TraceSession",
        parent_span: Optional["Span"] = None,
        otel_span: Optional[otel_trace.Span] = None,
    ):
        self.name = name
        self._session = session
        self._parent = parent_span
        self._otel_span = otel_span
        self._start_time_ns = time.time_ns()
        self._end_time_ns: Optional[int] = None
        self._attributes: Dict[str, Any] = {}
        self._events: List[Dict[str, Any]] = []
        self._status = "ok"
        self._status_message: Optional[str] = None
        self._children: List[Span] = []
        self._span_id = self._generate_span_id()
        
        if parent_span:
            parent_span._children.append(self)
    
    def _generate_span_id(self) -> str:
        import secrets
        return secrets.token_hex(8)
    
    @property
    def span_id(self) -> str:
        return self._span_id
    
    @property
    def parent_span_id(self) -> Optional[str]:
        return self._parent.span_id if self._parent else None
    
    @property
    def duration_ms(self) -> float:
        end = self._end_time_ns or time.time_ns()
        return (end - self._start_time_ns) / 1_000_000
    
    def set_attribute(self, key: str, value: Any) -> "Span":
        """Set an attribute on the span with smart truncation.

        Applies appropriate size limits based on the attribute type:
        - accumulated_context: 64KB limit (for full conversation history)
        - content/prompt/response: 32KB limit
        - Other string attributes: 16KB limit
        """
        if isinstance(value, str):
            # Apply size limits based on attribute type
            if key == "accumulated_context":
                max_len = MAX_ACCUMULATED_CONTEXT
            elif key in ("content", "prompt", "response", "input", "output"):
                max_len = MAX_CONTENT_LENGTH
            else:
                max_len = MAX_ATTRIBUTE_LENGTH

            if len(value) > max_len:
                # Truncate with indicator
                value = value[:max_len - 20] + "\n[...truncated...]"

            self._attributes[key] = value
        elif isinstance(value, (int, float, bool)):
            self._attributes[key] = value
        else:
            serialized = json.dumps(value)
            if len(serialized) > MAX_ATTRIBUTE_LENGTH:
                serialized = serialized[:MAX_ATTRIBUTE_LENGTH - 20] + "...truncated"
            self._attributes[key] = serialized

        if self._otel_span:
            self._otel_span.set_attribute(key, self._attributes[key])

        return self
    
    def set_attributes(self, attributes: Dict[str, Any]) -> "Span":
        """Set multiple attributes on the span."""
        for key, value in attributes.items():
            self.set_attribute(key, value)
        return self
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> "Span":
        """Add an event to the span."""
        event = {
            "name": name,
            "timestamp_ns": time.time_ns(),
            "attributes": attributes or {},
        }
        self._events.append(event)
        
        if self._otel_span:
            self._otel_span.add_event(name, attributes=attributes)
        
        return self
    
    def set_status(self, status: str, message: Optional[str] = None) -> "Span":
        """Set the span status."""
        if status not in ("ok", "error"):
            raise ValueError(f"Status must be 'ok' or 'error', got {status}")
        
        self._status = status
        self._status_message = message
        
        if self._otel_span:
            if status == "error":
                self._otel_span.set_status(Status(StatusCode.ERROR, message))
            else:
                self._otel_span.set_status(Status(StatusCode.OK))
        
        return self
    
    def record_exception(self, exception: Exception) -> "Span":
        """Record an exception on the span."""
        self.set_status("error", str(exception))
        self.add_event("exception", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
        })
        
        if self._otel_span:
            self._otel_span.record_exception(exception)
        
        return self
    
    def end(self) -> None:
        """End the span."""
        self._end_time_ns = time.time_ns()
        
        if self._otel_span:
            self._otel_span.end()
    
    def to_data(self) -> SpanData:
        """Convert span to data object."""
        return SpanData(
            name=self.name,
            span_id=self._span_id,
            parent_span_id=self.parent_span_id,
            start_time_ns=self._start_time_ns,
            end_time_ns=self._end_time_ns,
            attributes=self._attributes.copy(),
            events=self._events.copy(),
            status=self._status,
            status_message=self._status_message,
        )
    
    def __enter__(self) -> "Span":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_val:
            self.record_exception(exc_val)
        self.end()
