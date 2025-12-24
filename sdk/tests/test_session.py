"""Tests for MAO Testing SDK TraceSession."""

import pytest
import time
from unittest.mock import MagicMock, patch

from mao_testing.session import TraceSession, StateSnapshot, SessionData
from mao_testing.config import MAOConfig
from mao_testing.errors import TracingError


class TestTraceSession:
    def setup_method(self):
        self.mock_tracer = MagicMock()
        self.mock_tracer._config = MAOConfig(
            api_key="test-key",
            environment="test",
            service_name="test-service",
        )
    
    def test_session_creation(self):
        session = TraceSession(name="test-session", tracer=self.mock_tracer)
        
        assert session.name == "test-session"
        assert session.trace_id is not None
        assert len(session.trace_id) == 32
        assert session._status == "running"
    
    def test_session_with_framework(self):
        session = TraceSession(
            name="test", 
            tracer=self.mock_tracer, 
            framework="langgraph"
        )
        assert session._framework == "langgraph"
    
    def test_set_metadata(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        
        result = session.set_metadata({"user_id": "123", "request_id": "abc"})
        assert result is session
        assert session._metadata["user_id"] == "123"
        assert session._metadata["request_id"] == "abc"
    
    def test_add_tag(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        
        result = session.add_tag("production")
        assert result is session
        assert "production" in session._tags
        
        session.add_tag("production")
        assert session._tags.count("production") == 1
    
    def test_add_tags(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        session.add_tags(["tag1", "tag2", "tag3"])
        
        assert "tag1" in session._tags
        assert "tag2" in session._tags
        assert "tag3" in session._tags
    
    @patch("mao_testing.session.otel_trace")
    def test_create_span(self, mock_otel):
        mock_otel.get_tracer.return_value.start_span.return_value = MagicMock()
        
        session = TraceSession(name="test", tracer=self.mock_tracer)
        span = session.span("child-span")
        
        assert span.name == "child-span"
        assert span in session._spans
    
    def test_capture_state(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        
        result = session.capture_state("initial", {"x": 1, "y": 2})
        assert result is session
        assert len(session._states) == 1
        
        state = session._states[0]
        assert state.name == "initial"
        assert state.data == {"x": 1, "y": 2}
        assert state.timestamp_ns is not None
    
    def test_capture_state_with_agent(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        session.capture_state("step", {"action": "search"}, agent_id="researcher")
        
        state = session._states[0]
        assert state.agent_id == "researcher"
    
    def test_set_framework(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        result = session.set_framework("autogen")
        
        assert result is session
        assert session._framework == "autogen"
    
    def test_set_status(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        
        result = session.set_status("completed")
        assert result is session
        assert session._status == "completed"
    
    def test_set_status_invalid(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        
        with pytest.raises(TracingError) as exc_info:
            session.set_status("invalid")
        assert "Invalid status" in str(exc_info.value)
    
    def test_session_duration(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        time.sleep(0.01)
        
        duration = session.duration_ms
        assert duration >= 10
    
    def test_session_end(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        session.end()
        
        assert session._end_time_ns is not None
        assert session._status == "completed"
        self.mock_tracer._on_session_end.assert_called_once_with(session)
    
    def test_session_end_with_status(self):
        session = TraceSession(name="test", tracer=self.mock_tracer)
        session.end(status="failed")
        
        assert session._status == "failed"
    
    @patch("mao_testing.session.otel_trace")
    def test_session_context_manager(self, mock_otel):
        mock_span = MagicMock()
        mock_otel.get_tracer.return_value.start_span.return_value = mock_span
        
        with TraceSession(name="test", tracer=self.mock_tracer) as session:
            session.set_metadata({"inside": True})
        
        assert session._end_time_ns is not None
        assert session._status == "completed"
    
    @patch("mao_testing.session.otel_trace")
    def test_session_context_manager_exception(self, mock_otel):
        mock_span = MagicMock()
        mock_otel.get_tracer.return_value.start_span.return_value = mock_span
        
        with pytest.raises(ValueError):
            with TraceSession(name="test", tracer=self.mock_tracer) as session:
                raise ValueError("Test error")
        
        assert session._status == "failed"
    
    def test_to_data(self):
        session = TraceSession(
            name="test", 
            tracer=self.mock_tracer,
            framework="langgraph",
        )
        session.set_metadata({"key": "value"})
        session.add_tag("prod")
        session.capture_state("init", {"x": 1})
        session.end()
        
        data = session.to_data()
        
        assert isinstance(data, SessionData)
        assert data.trace_id == session.trace_id
        assert data.name == "test"
        assert data.framework == "langgraph"
        assert data.metadata == {"key": "value"}
        assert data.tags == ["prod"]
        assert len(data.states) == 1
        assert data.status == "completed"
        assert data.environment == "test"
        assert data.service_name == "test-service"


class TestStateSnapshot:
    def test_state_snapshot_creation(self):
        state = StateSnapshot(
            name="test",
            data={"x": 1},
            timestamp_ns=12345,
            agent_id="agent1",
        )
        
        assert state.name == "test"
        assert state.data == {"x": 1}
        assert state.timestamp_ns == 12345
        assert state.agent_id == "agent1"
