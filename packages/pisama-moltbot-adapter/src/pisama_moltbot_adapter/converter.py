"""Convert Moltbot events to PISAMA trace format."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pisama_core.traces.enums import Platform, SpanKind, SpanStatus
from pisama_core.traces.models import Event, Span, Trace, TraceMetadata

logger = logging.getLogger(__name__)


class MoltbotTraceConverter:
    """Converts Moltbot gateway events to PISAMA trace format."""

    def __init__(self):
        """Initialize the converter."""
        self._active_traces: dict[str, Trace] = {}
        self._session_to_trace: dict[str, str] = {}

    def convert_event(self, event: dict[str, Any]) -> Optional[Trace]:
        """Convert a Moltbot event to a PISAMA trace update.

        Args:
            event: Moltbot gateway event

        Returns:
            Updated trace if the event created/modified a trace, None otherwise
        """
        event_type = event.get("type")
        logger.debug(f"Processing event type: {event_type}")

        if event_type == "session.created":
            return self._handle_session_created(event)
        elif event_type == "message.received":
            return self._handle_message_received(event)
        elif event_type == "agent.thinking":
            return self._handle_agent_thinking(event)
        elif event_type == "tool.call":
            return self._handle_tool_call(event)
        elif event_type == "tool.result":
            return self._handle_tool_result(event)
        elif event_type == "message.sent":
            return self._handle_message_sent(event)
        elif event_type == "session.ended":
            return self._handle_session_ended(event)
        elif event_type == "error":
            return self._handle_error(event)
        else:
            logger.debug(f"Unhandled event type: {event_type}")
            return None

    def _handle_session_created(self, event: dict[str, Any]) -> Trace:
        """Handle session creation event."""
        session_id = event.get("session_id")
        user_id = event.get("user_id")

        metadata = TraceMetadata(
            session_id=session_id,
            user_id=user_id,
            platform=Platform.MOLTBOT,
            platform_version=event.get("gateway_version"),
            environment=event.get("environment", "production"),
            host=event.get("host"),
            tags={
                "channel": event.get("channel", "unknown"),
                "channel_type": event.get("channel_type", "unknown"),
            },
        )

        trace = Trace(
            trace_id=session_id,
            metadata=metadata,
        )

        self._active_traces[session_id] = trace
        self._session_to_trace[session_id] = session_id
        logger.info(f"Created trace for session: {session_id}")

        return trace

    def _handle_message_received(self, event: dict[str, Any]) -> Optional[Trace]:
        """Handle incoming message event."""
        session_id = event.get("session_id")
        trace = self._get_or_create_trace(session_id, event)

        span = Span(
            name="user_message",
            kind=SpanKind.USER_INPUT,
            platform=Platform.MOLTBOT,
            start_time=self._parse_timestamp(event.get("timestamp")),
            input_data={
                "message": event.get("message", {}).get("text"),
                "channel": event.get("channel"),
                "sender": event.get("sender"),
            },
            attributes={
                "message_id": event.get("message_id"),
                "channel_type": event.get("channel_type"),
            },
        )
        span.end(SpanStatus.OK)

        trace.add_span(span)
        return trace

    def _handle_agent_thinking(self, event: dict[str, Any]) -> Optional[Trace]:
        """Handle agent reasoning/thinking event."""
        session_id = event.get("session_id")
        trace = self._get_or_create_trace(session_id, event)

        span = Span(
            name="agent_turn",
            kind=SpanKind.AGENT_TURN,
            platform=Platform.MOLTBOT,
            start_time=self._parse_timestamp(event.get("timestamp")),
            attributes={
                "model": event.get("model"),
                "turn_id": event.get("turn_id"),
            },
        )

        trace.add_span(span)
        return trace

    def _handle_tool_call(self, event: dict[str, Any]) -> Optional[Trace]:
        """Handle tool execution event."""
        session_id = event.get("session_id")
        trace = self._get_or_create_trace(session_id, event)

        tool_name = event.get("tool", {}).get("name", "unknown_tool")
        span = Span(
            name=tool_name,
            kind=SpanKind.TOOL,
            platform=Platform.MOLTBOT,
            start_time=self._parse_timestamp(event.get("timestamp")),
            input_data=event.get("tool", {}).get("input"),
            attributes={
                "tool_id": event.get("tool_id"),
                "tool_type": event.get("tool", {}).get("type"),
            },
        )

        trace.add_span(span)
        return trace

    def _handle_tool_result(self, event: dict[str, Any]) -> Optional[Trace]:
        """Handle tool result event."""
        session_id = event.get("session_id")
        trace = self._get_or_create_trace(session_id, event)

        tool_id = event.get("tool_id")
        for span in reversed(trace.spans):
            if (
                span.kind == SpanKind.TOOL
                and span.attributes.get("tool_id") == tool_id
                and not span.is_complete
            ):
                span.output_data = event.get("result")
                span.end_time = self._parse_timestamp(event.get("timestamp"))
                span.status = (
                    SpanStatus.ERROR if event.get("error") else SpanStatus.OK
                )
                if event.get("error"):
                    span.error_message = event.get("error")
                break

        return trace

    def _handle_message_sent(self, event: dict[str, Any]) -> Optional[Trace]:
        """Handle outgoing message event."""
        session_id = event.get("session_id")
        trace = self._get_or_create_trace(session_id, event)

        span = Span(
            name="agent_response",
            kind=SpanKind.USER_OUTPUT,
            platform=Platform.MOLTBOT,
            start_time=self._parse_timestamp(event.get("timestamp")),
            output_data={
                "message": event.get("message", {}).get("text"),
                "channel": event.get("channel"),
            },
            attributes={
                "message_id": event.get("message_id"),
            },
        )
        span.end(SpanStatus.OK)

        trace.add_span(span)

        # Close any open agent turn spans
        for span in reversed(trace.spans):
            if span.kind == SpanKind.AGENT_TURN and not span.is_complete:
                span.end(SpanStatus.OK)
                break

        return trace

    def _handle_session_ended(self, event: dict[str, Any]) -> Optional[Trace]:
        """Handle session end event."""
        session_id = event.get("session_id")
        trace = self._active_traces.get(session_id)

        if trace:
            # Mark all incomplete spans as ended
            for span in trace.spans:
                if not span.is_complete:
                    span.end(SpanStatus.OK)

            # Clean up
            del self._active_traces[session_id]
            if session_id in self._session_to_trace:
                del self._session_to_trace[session_id]

            logger.info(f"Ended trace for session: {session_id}")
            return trace

        return None

    def _handle_error(self, event: dict[str, Any]) -> Optional[Trace]:
        """Handle error event."""
        session_id = event.get("session_id")
        trace = self._get_or_create_trace(session_id, event)

        # Find the most recent incomplete span and mark it as errored
        for span in reversed(trace.spans):
            if not span.is_complete:
                span.end(SpanStatus.ERROR, error=event.get("error"))
                break
        else:
            # No incomplete span, create error event
            span = Span(
                name="error",
                kind=SpanKind.SYSTEM,
                platform=Platform.MOLTBOT,
                start_time=self._parse_timestamp(event.get("timestamp")),
            )
            span.end(SpanStatus.ERROR, error=event.get("error"))
            trace.add_span(span)

        return trace

    def _get_or_create_trace(
        self, session_id: str, event: dict[str, Any]
    ) -> Trace:
        """Get existing trace or create a new one."""
        if session_id in self._active_traces:
            return self._active_traces[session_id]

        # Create trace from event context
        metadata = TraceMetadata(
            session_id=session_id,
            platform=Platform.MOLTBOT,
            tags={"channel": event.get("channel", "unknown")},
        )

        trace = Trace(trace_id=session_id, metadata=metadata)
        self._active_traces[session_id] = trace
        self._session_to_trace[session_id] = session_id

        return trace

    def _parse_timestamp(self, timestamp: Optional[str]) -> datetime:
        """Parse timestamp string to datetime."""
        if timestamp:
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        return datetime.now(timezone.utc)

    def get_active_traces(self) -> list[Trace]:
        """Get all currently active traces."""
        return list(self._active_traces.values())

    def clear_completed_traces(self) -> None:
        """Remove completed traces from memory."""
        completed_sessions = [
            session_id
            for session_id, trace in self._active_traces.items()
            if all(span.is_complete for span in trace.spans)
        ]

        for session_id in completed_sessions:
            del self._active_traces[session_id]
            if session_id in self._session_to_trace:
                del self._session_to_trace[session_id]

        if completed_sessions:
            logger.info(f"Cleared {len(completed_sessions)} completed traces")
