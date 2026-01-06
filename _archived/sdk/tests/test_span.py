"""Tests for MAO Testing SDK Span."""

import pytest
import time
from unittest.mock import MagicMock

from mao_testing.span import Span, SpanData


class TestSpan:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.mock_session._tracer = MagicMock()
    
    def test_span_creation(self):
        span = Span(name="test-span", session=self.mock_session)
        assert span.name == "test-span"
        assert span.span_id is not None
        assert span.parent_span_id is None
        assert len(span.span_id) == 16
    
    def test_span_with_parent(self):
        parent = Span(name="parent", session=self.mock_session)
        child = Span(name="child", session=self.mock_session, parent_span=parent)
        
        assert child.parent_span_id == parent.span_id
        assert child in parent._children
    
    def test_set_attribute(self):
        span = Span(name="test", session=self.mock_session)
        
        result = span.set_attribute("key1", "value1")
        assert result is span
        assert span._attributes["key1"] == "value1"
        
        span.set_attribute("key2", 123)
        assert span._attributes["key2"] == 123
        
        span.set_attribute("key3", True)
        assert span._attributes["key3"] is True
    
    def test_set_attribute_complex_value(self):
        span = Span(name="test", session=self.mock_session)
        span.set_attribute("complex", {"nested": "value"})
        assert span._attributes["complex"] == '{"nested": "value"}'
    
    def test_set_attributes(self):
        span = Span(name="test", session=self.mock_session)
        span.set_attributes({"a": 1, "b": 2, "c": 3})
        
        assert span._attributes["a"] == 1
        assert span._attributes["b"] == 2
        assert span._attributes["c"] == 3
    
    def test_add_event(self):
        span = Span(name="test", session=self.mock_session)
        
        result = span.add_event("test-event", {"detail": "value"})
        assert result is span
        assert len(span._events) == 1
        assert span._events[0]["name"] == "test-event"
        assert span._events[0]["attributes"]["detail"] == "value"
        assert "timestamp_ns" in span._events[0]
    
    def test_set_status(self):
        span = Span(name="test", session=self.mock_session)
        
        result = span.set_status("ok")
        assert result is span
        assert span._status == "ok"
        
        span.set_status("error", "Something went wrong")
        assert span._status == "error"
        assert span._status_message == "Something went wrong"
    
    def test_set_status_invalid(self):
        span = Span(name="test", session=self.mock_session)
        with pytest.raises(ValueError) as exc_info:
            span.set_status("invalid")
        assert "Status must be 'ok' or 'error'" in str(exc_info.value)
    
    def test_record_exception(self):
        span = Span(name="test", session=self.mock_session)
        exc = ValueError("Test error")
        
        result = span.record_exception(exc)
        assert result is span
        assert span._status == "error"
        assert span._status_message == "Test error"
        assert len(span._events) == 1
        assert span._events[0]["name"] == "exception"
        assert span._events[0]["attributes"]["exception.type"] == "ValueError"
    
    def test_span_end(self):
        span = Span(name="test", session=self.mock_session)
        assert span._end_time_ns is None
        
        span.end()
        assert span._end_time_ns is not None
    
    def test_span_duration(self):
        span = Span(name="test", session=self.mock_session)
        time.sleep(0.01)
        
        duration = span.duration_ms
        assert duration >= 10
    
    def test_span_context_manager(self):
        with Span(name="test", session=self.mock_session) as span:
            span.set_attribute("inside", True)
        
        assert span._end_time_ns is not None
        assert span._attributes["inside"] is True
    
    def test_span_context_manager_exception(self):
        with pytest.raises(ValueError):
            with Span(name="test", session=self.mock_session) as span:
                raise ValueError("Test error")
        
        assert span._status == "error"
        assert len(span._events) == 1
    
    def test_to_data(self):
        span = Span(name="test", session=self.mock_session)
        span.set_attribute("key", "value")
        span.add_event("event1")
        span.end()
        
        data = span.to_data()
        
        assert isinstance(data, SpanData)
        assert data.name == "test"
        assert data.span_id == span.span_id
        assert data.attributes == {"key": "value"}
        assert len(data.events) == 1
        assert data.end_time_ns is not None
