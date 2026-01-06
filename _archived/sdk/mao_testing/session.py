"""MAO Testing SDK TraceSession implementation."""

from __future__ import annotations
import time
import json
import secrets
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from opentelemetry import trace as otel_trace
from opentelemetry.trace import SpanKind

from .span import Span, SpanData
from .errors import TracingError

if TYPE_CHECKING:
    from .tracer import MAOTracer


@dataclass
class StateSnapshot:
    """A snapshot of agent state at a point in time."""
    name: str
    data: Dict[str, Any]
    timestamp_ns: int
    agent_id: Optional[str] = None


@dataclass 
class SessionData:
    """Complete data for a trace session."""
    trace_id: str
    name: str
    start_time_ns: int
    end_time_ns: Optional[int]
    metadata: Dict[str, Any]
    tags: List[str]
    spans: List[SpanData]
    states: List[StateSnapshot]
    status: str
    framework: Optional[str]
    environment: str
    service_name: str


class TraceSession:
    """A trace session representing a complete workflow execution."""
    
    def __init__(
        self,
        name: str,
        tracer: "MAOTracer",
        framework: Optional[str] = None,
    ):
        self.name = name
        self._tracer = tracer
        self._trace_id = self._generate_trace_id()
        self._start_time_ns = time.time_ns()
        self._end_time_ns: Optional[int] = None
        self._metadata: Dict[str, Any] = {}
        self._tags: List[str] = []
        self._spans: List[Span] = []
        self._states: List[StateSnapshot] = []
        self._current_span: Optional[Span] = None
        self._root_span: Optional[Span] = None
        self._status = "running"
        self._framework = framework
        self._otel_tracer = otel_trace.get_tracer("mao-testing")
        self._otel_context = None
    
    def _generate_trace_id(self) -> str:
        return secrets.token_hex(16)
    
    @property
    def trace_id(self) -> str:
        return self._trace_id
    
    @property
    def duration_ms(self) -> float:
        end = self._end_time_ns or time.time_ns()
        return (end - self._start_time_ns) / 1_000_000
    
    def set_metadata(self, metadata: Dict[str, Any]) -> "TraceSession":
        """Set metadata key-value pairs on the trace."""
        self._metadata.update(metadata)
        return self
    
    def add_tag(self, tag: str) -> "TraceSession":
        """Add a tag to the trace for filtering."""
        if tag not in self._tags:
            self._tags.append(tag)
        return self
    
    def add_tags(self, tags: List[str]) -> "TraceSession":
        """Add multiple tags to the trace."""
        for tag in tags:
            self.add_tag(tag)
        return self
    
    def span(self, name: str) -> Span:
        """Create a child span within the trace."""
        otel_span = self._otel_tracer.start_span(
            name,
            kind=SpanKind.INTERNAL,
        )
        
        span = Span(
            name=name,
            session=self,
            parent_span=self._current_span or self._root_span,
            otel_span=otel_span,
        )
        
        span.set_attribute("mao.trace_id", self._trace_id)
        span.set_attribute("mao.session_name", self.name)
        
        if self._framework:
            span.set_attribute("mao.framework", self._framework)
        
        self._spans.append(span)
        return span
    
    def capture_state(self, name: str, data: Dict[str, Any], agent_id: Optional[str] = None) -> "TraceSession":
        """Capture a state snapshot at the current point."""
        state = StateSnapshot(
            name=name,
            data=data,
            timestamp_ns=time.time_ns(),
            agent_id=agent_id,
        )
        self._states.append(state)
        
        if self._current_span or self._root_span:
            active_span = self._current_span or self._root_span
            active_span.add_event(f"state:{name}", {
                "mao.state_name": name,
                "mao.state_data": json.dumps(data)[:4096],
                "mao.agent_id": agent_id or "",
            })
        
        return self
    
    def set_framework(self, framework: str) -> "TraceSession":
        """Set the agent framework being used."""
        self._framework = framework
        return self
    
    def set_status(self, status: str) -> "TraceSession":
        """Set the session status."""
        if status not in ("running", "completed", "failed"):
            raise TracingError(f"Invalid status: {status}")
        self._status = status
        return self
    
    def end(self, status: Optional[str] = None) -> None:
        """End the trace session."""
        self._end_time_ns = time.time_ns()
        
        if status:
            self._status = status
        elif self._status == "running":
            self._status = "completed"
        
        if self._root_span:
            self._root_span.set_attribute("mao.status", self._status)
            self._root_span.set_attribute("mao.duration_ms", self.duration_ms)
            self._root_span.set_attribute("mao.state_count", len(self._states))
            self._root_span.set_attribute("mao.span_count", len(self._spans))
            self._root_span.end()
        
        for span in self._spans:
            if span._end_time_ns is None:
                span.end()
        
        self._tracer._on_session_end(self)
    
    def to_data(self) -> SessionData:
        """Convert session to data object."""
        return SessionData(
            trace_id=self._trace_id,
            name=self.name,
            start_time_ns=self._start_time_ns,
            end_time_ns=self._end_time_ns,
            metadata=self._metadata.copy(),
            tags=self._tags.copy(),
            spans=[s.to_data() for s in self._spans],
            states=self._states.copy(),
            status=self._status,
            framework=self._framework,
            environment=self._tracer._config.environment,
            service_name=self._tracer._config.service_name,
        )
    
    def __enter__(self) -> "TraceSession":
        otel_span = self._otel_tracer.start_span(
            self.name,
            kind=SpanKind.INTERNAL,
        )
        
        self._root_span = Span(
            name=self.name,
            session=self,
            otel_span=otel_span,
        )
        
        self._root_span.set_attribute("mao.trace_id", self._trace_id)
        self._root_span.set_attribute("mao.session_name", self.name)
        self._root_span.set_attribute("mao.environment", self._tracer._config.environment)
        self._root_span.set_attribute("mao.service_name", self._tracer._config.service_name)
        
        if self._framework:
            self._root_span.set_attribute("mao.framework", self._framework)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_val:
            self._status = "failed"
            if self._root_span:
                self._root_span.record_exception(exc_val)
        self.end()
