"""Base framework tracer for MAO integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import uuid


@dataclass
class Span:
    """A single span in a trace."""
    id: str
    trace_id: str
    parent_id: Optional[str]
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "OK"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
        }


@dataclass
class Trace:
    """A complete trace with multiple spans."""
    id: str
    spans: List[Span] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }


class BaseFrameworkTracer(ABC):
    """Base class for framework-specific tracers."""
    
    FRAMEWORK_NAME: str = "base"
    FRAMEWORK_VERSION: str = "0.0.0"
    
    def __init__(self, endpoint: str = "http://localhost:8000"):
        self.endpoint = endpoint
        self.traces: Dict[str, Trace] = {}
        self.current_trace_id: Optional[str] = None
        self.span_stack: List[str] = []
        self._callbacks: List[Callable[[Span], None]] = []
    
    def start_trace(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())
        self.traces[trace_id] = Trace(
            id=trace_id,
            metadata={
                "framework": self.FRAMEWORK_NAME,
                "framework_version": self.FRAMEWORK_VERSION,
                **(metadata or {}),
            },
        )
        self.current_trace_id = trace_id
        return trace_id
    
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Start a new span."""
        tid = trace_id or self.current_trace_id
        if not tid or tid not in self.traces:
            tid = self.start_trace()
        
        span_id = str(uuid.uuid4())
        parent_id = self.span_stack[-1] if self.span_stack else None
        
        span = Span(
            id=span_id,
            trace_id=tid,
            parent_id=parent_id,
            name=name,
            start_time=datetime.utcnow(),
            attributes=attributes or {},
        )
        
        self.traces[tid].spans.append(span)
        self.span_stack.append(span_id)
        
        return span_id
    
    def end_span(
        self,
        span_id: str,
        status: str = "OK",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """End a span."""
        for trace in self.traces.values():
            for span in trace.spans:
                if span.id == span_id:
                    span.end_time = datetime.utcnow()
                    span.status = status
                    if attributes:
                        span.attributes.update(attributes)
                    
                    for callback in self._callbacks:
                        callback(span)
                    
                    if self.span_stack and self.span_stack[-1] == span_id:
                        self.span_stack.pop()
                    return
    
    def add_event(
        self,
        span_id: str,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an event to a span."""
        for trace in self.traces.values():
            for span in trace.spans:
                if span.id == span_id:
                    span.events.append({
                        "name": name,
                        "timestamp": datetime.utcnow().isoformat(),
                        "attributes": attributes or {},
                    })
                    return
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        return self.traces.get(trace_id)
    
    def on_span_end(self, callback: Callable[[Span], None]) -> None:
        """Register a callback for when spans end."""
        self._callbacks.append(callback)
    
    @abstractmethod
    def wrap(self, target: Any) -> Any:
        """Wrap a framework-specific object for tracing."""
        pass
    
    @abstractmethod
    def extract_agent_info(self, obj: Any) -> Dict[str, Any]:
        """Extract agent information from framework-specific objects."""
        pass
