"""Parser for OpenClaw session data."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.n8n_security import redact_sensitive_data, compute_state_hash


@dataclass
class OpenClawEvent:
    """A single event from OpenClaw's append-only session log."""

    event_type: str  # message.received, agent.turn, tool.call, tool.result,
    # session.spawn, session.send, error, message.sent
    timestamp: datetime
    agent_name: Optional[str] = None
    channel: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_result: Optional[Any] = None
    error: Optional[str] = None
    token_count: int = 0


@dataclass
class OpenClawSession:
    """Parsed OpenClaw session."""

    session_id: str
    instance_id: str
    agent_name: str
    channel: str
    inbox_type: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    events: List[OpenClawEvent] = field(default_factory=list)
    agents_mapping: Optional[dict] = None
    spawned_sessions: List[str] = field(default_factory=list)
    elevated_mode: bool = False
    sandbox_enabled: bool = True


@dataclass
class ParsedOpenClawState:
    """State record for PISAMA storage. Parallels ParsedN8nState."""

    trace_id: str
    sequence_num: int
    agent_id: str
    state_delta: dict
    state_hash: str
    event_type: str
    latency_ms: int
    timestamp: datetime
    is_agent_event: bool = False
    channel: Optional[str] = None
    token_count: int = 0


class OpenClawParser:
    """Parses OpenClaw session data into PISAMA trace format."""

    AGENT_EVENT_TYPES = [
        "agent.turn",
        "message.sent",
        "session.spawn",
        "session.send",
    ]

    TOOL_EVENT_TYPES = [
        "tool.call",
        "tool.result",
    ]

    def parse_session(self, raw_data: Dict[str, Any]) -> OpenClawSession:
        """Parse raw webhook payload into structured session."""
        started_at = self._parse_datetime(raw_data.get("started_at"))
        finished_at = self._parse_datetime(raw_data.get("finished_at"))

        events = []
        for raw_event in raw_data.get("events", []):
            event = OpenClawEvent(
                event_type=raw_event.get("type", "unknown"),
                timestamp=self._parse_datetime(raw_event.get("timestamp")),
                agent_name=raw_event.get("agent_name"),
                channel=raw_event.get("channel"),
                data=raw_event.get("data", {}),
                tool_name=raw_event.get("tool_name"),
                tool_input=raw_event.get("tool_input"),
                tool_result=raw_event.get("tool_result"),
                error=raw_event.get("error"),
                token_count=raw_event.get("token_count", 0),
            )
            events.append(event)

        return OpenClawSession(
            session_id=raw_data.get("session_id", ""),
            instance_id=raw_data.get("instance_id", ""),
            agent_name=raw_data.get("agent_name", "default"),
            channel=raw_data.get("channel", ""),
            inbox_type=raw_data.get("inbox_type", "dm"),
            started_at=started_at,
            finished_at=finished_at,
            status=raw_data.get("status", "completed"),
            events=events,
            agents_mapping=raw_data.get("agents_mapping"),
            spawned_sessions=raw_data.get("spawned_sessions", []),
            elevated_mode=raw_data.get("elevated_mode", False),
            sandbox_enabled=raw_data.get("sandbox_enabled", True),
        )

    def parse_to_states(
        self, session: OpenClawSession, tenant_id: str
    ) -> List[ParsedOpenClawState]:
        """Convert session events to PISAMA state records."""
        states = []

        for seq, event in enumerate(session.events):
            is_agent_event = event.event_type in self.AGENT_EVENT_TYPES

            state_delta = redact_sensitive_data(
                {
                    "event_type": event.event_type,
                    "agent_name": event.agent_name or session.agent_name,
                    "channel": event.channel or session.channel,
                    "data": event.data,
                    "tool_name": event.tool_name,
                    "tool_input": event.tool_input,
                    "tool_result": event.tool_result,
                    "error": event.error,
                },
                skip_keys=["messages", "prompt", "thinking", "reasoning"],
            )

            # Compute latency from event timestamps
            latency_ms = 0
            if seq > 0 and session.events[seq - 1].timestamp and event.timestamp:
                delta = event.timestamp - session.events[seq - 1].timestamp
                latency_ms = int(delta.total_seconds() * 1000)

            states.append(
                ParsedOpenClawState(
                    trace_id=session.session_id,
                    sequence_num=seq,
                    agent_id=event.agent_name or session.agent_name,
                    state_delta=state_delta,
                    state_hash=compute_state_hash(state_delta),
                    event_type=event.event_type,
                    latency_ms=max(0, latency_ms),
                    timestamp=event.timestamp or session.started_at,
                    is_agent_event=is_agent_event,
                    channel=event.channel or session.channel,
                    token_count=event.token_count,
                )
            )

        return states

    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        if not dt_str:
            return datetime.utcnow()
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return datetime.utcnow()


openclaw_parser = OpenClawParser()
