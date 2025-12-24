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
        """Set an attribute on the span."""
        if isinstance(value, (str, int, float, bool)):
            self._attributes[key] = value
        else:
            self._attributes[key] = json.dumps(value)
        
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
