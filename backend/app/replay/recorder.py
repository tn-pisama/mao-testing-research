"""
Replay Recorder - Captures all events for deterministic replay.

Records:
- LLM responses with exact tokens
- Tool call inputs and outputs
- State transitions
- Timestamps and random seeds
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    STATE_TRANSITION = "state_transition"
    AGENT_HANDOFF = "agent_handoff"
    ERROR = "error"
    CHECKPOINT = "checkpoint"


class RecordedEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sequence_number: int
    agent_name: Optional[str] = None
    span_id: Optional[str] = None
    
    input_data: Optional[dict[str, Any]] = None
    output_data: Optional[dict[str, Any]] = None
    
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    
    random_seed: Optional[int] = None
    checksum: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def compute_checksum(self) -> str:
        data = {
            "event_type": self.event_type.value,
            "agent_name": self.agent_name,
            "input_data": self.input_data,
            "output_data": self.output_data,
        }
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class ReplayRecorder:
    """
    Records events during trace execution for later replay.
    
    Captures all LLM responses, tool outputs, and state transitions
    to enable deterministic replay.
    """
    
    def __init__(self, trace_id: str, tenant_id: str):
        self.trace_id = trace_id
        self.tenant_id = tenant_id
        self.events: list[RecordedEvent] = []
        self.sequence = 0
        self.started_at = datetime.utcnow()
        self.current_agent: Optional[str] = None
        self.current_span: Optional[str] = None

    def set_context(
        self,
        agent_name: Optional[str] = None,
        span_id: Optional[str] = None,
    ):
        if agent_name:
            self.current_agent = agent_name
        if span_id:
            self.current_span = span_id

    def record_llm_request(
        self,
        messages: list[dict],
        model: str,
        parameters: Optional[dict] = None,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.LLM_REQUEST,
            sequence_number=self._next_sequence(),
            agent_name=self.current_agent,
            span_id=self.current_span,
            input_data={
                "messages": messages,
                "parameters": parameters or {},
            },
            model=model,
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        return event

    def record_llm_response(
        self,
        content: str,
        model: str,
        tokens_used: int,
        latency_ms: int,
        request_id: Optional[str] = None,
        tool_calls: Optional[list[dict]] = None,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.LLM_RESPONSE,
            sequence_number=self._next_sequence(),
            agent_name=self.current_agent,
            span_id=self.current_span,
            output_data={
                "content": content,
                "tool_calls": tool_calls,
                "request_id": request_id,
            },
            model=model,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        return event

    def record_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        tool_call_id: Optional[str] = None,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.TOOL_CALL,
            sequence_number=self._next_sequence(),
            agent_name=self.current_agent,
            span_id=self.current_span,
            input_data={
                "tool_name": tool_name,
                "arguments": arguments,
                "tool_call_id": tool_call_id,
            },
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        return event

    def record_tool_response(
        self,
        tool_name: str,
        result: Any,
        latency_ms: int,
        success: bool = True,
        error: Optional[str] = None,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.TOOL_RESPONSE,
            sequence_number=self._next_sequence(),
            agent_name=self.current_agent,
            span_id=self.current_span,
            input_data={"tool_name": tool_name},
            output_data={
                "result": result,
                "success": success,
                "error": error,
            },
            latency_ms=latency_ms,
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        return event

    def record_state_transition(
        self,
        from_state: dict,
        to_state: dict,
        trigger: Optional[str] = None,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.STATE_TRANSITION,
            sequence_number=self._next_sequence(),
            agent_name=self.current_agent,
            span_id=self.current_span,
            input_data={"from_state": from_state, "trigger": trigger},
            output_data={"to_state": to_state},
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        return event

    def record_handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: dict,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.AGENT_HANDOFF,
            sequence_number=self._next_sequence(),
            agent_name=from_agent,
            span_id=self.current_span,
            input_data={
                "from_agent": from_agent,
                "to_agent": to_agent,
            },
            output_data={"context": context},
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        self.current_agent = to_agent
        return event

    def record_error(
        self,
        error_type: str,
        message: str,
        stack_trace: Optional[str] = None,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.ERROR,
            sequence_number=self._next_sequence(),
            agent_name=self.current_agent,
            span_id=self.current_span,
            output_data={
                "error_type": error_type,
                "message": message,
                "stack_trace": stack_trace,
            },
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        return event

    def create_checkpoint(
        self,
        name: str,
        state: dict,
    ) -> RecordedEvent:
        event = RecordedEvent(
            event_type=EventType.CHECKPOINT,
            sequence_number=self._next_sequence(),
            agent_name=self.current_agent,
            span_id=self.current_span,
            input_data={"name": name},
            output_data={"state": state},
        )
        event.checksum = event.compute_checksum()
        self.events.append(event)
        return event

    def _next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def get_events(self) -> list[RecordedEvent]:
        return self.events

    def get_llm_responses(self) -> list[RecordedEvent]:
        return [e for e in self.events if e.event_type == EventType.LLM_RESPONSE]

    def get_tool_responses(self) -> list[RecordedEvent]:
        return [e for e in self.events if e.event_type == EventType.TOOL_RESPONSE]

    def get_checkpoints(self) -> list[RecordedEvent]:
        return [e for e in self.events if e.event_type == EventType.CHECKPOINT]

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat(),
            "event_count": len(self.events),
            "events": [e.dict() for e in self.events],
        }
