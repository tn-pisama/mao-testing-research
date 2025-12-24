"""Tests for MAO Testing SDK Tracer."""

import pytest
import time
from unittest.mock import MagicMock, patch, PropertyMock

from mao_testing.tracer import MAOTracer
from mao_testing.config import MAOConfig, SamplingRule
from mao_testing.session import TraceSession


class TestMAOTracer:
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_tracer_creation(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key")
        
        assert tracer._config.api_key == "test-key"
        assert tracer._sessions == []
        assert tracer._export_thread is not None
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_tracer_with_config(self, mock_provider, mock_otel):
        config = MAOConfig(
            api_key="custom-key",
            endpoint="http://localhost:8000",
            environment="production",
        )
        tracer = MAOTracer(config=config)
        
        assert tracer._config.api_key == "custom-key"
        assert tracer._config.endpoint == "http://localhost:8000"
        assert tracer._config.environment == "production"
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_trace_creates_session(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key")
        
        session = tracer.trace("test-workflow")
        
        assert isinstance(session, TraceSession)
        assert session.name == "test-workflow"
        assert session in tracer._sessions
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_trace_with_framework(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key")
        
        session = tracer.trace("workflow", framework="langgraph")
        
        assert session._framework == "langgraph"
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_sampling_rate(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key", sample_rate=0.0)
        
        sampled_count = 0
        for _ in range(100):
            if tracer._should_sample():
                sampled_count += 1
        
        assert sampled_count == 0
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_sampling_rule_status_error(self, mock_provider, mock_otel):
        tracer = MAOTracer(
            api_key="test-key",
            sample_rate=0.0,
            sampling_rules=[
                SamplingRule(condition="status == 'error'", rate=1.0),
            ],
        )
        
        assert tracer._should_sample({"status": "error"}) is True
        assert tracer._should_sample({"status": "ok"}) is False
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_sampling_rule_duration(self, mock_provider, mock_otel):
        tracer = MAOTracer(
            api_key="test-key",
            sample_rate=0.0,
            sampling_rules=[
                SamplingRule(condition="duration > 30s", rate=1.0),
            ],
        )
        
        assert tracer._should_sample({"duration_s": 45}) is True
        assert tracer._should_sample({"duration_s": 15}) is False
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_tracer_context_manager(self, mock_provider, mock_otel):
        with MAOTracer(api_key="test-key") as tracer:
            session = tracer.trace("test")
            assert session is not None
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_session_to_dict(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key")
        
        with tracer.trace("test-workflow", framework="langgraph") as session:
            session.set_metadata({"user": "test"})
            session.add_tag("prod")
            session.capture_state("init", {"x": 1})
        
        data = session.to_data()
        result = tracer._session_to_dict(data)
        
        assert result["name"] == "test-workflow"
        assert result["framework"] == "langgraph"
        assert result["metadata"] == {"user": "test"}
        assert result["tags"] == ["prod"]
        assert len(result["states"]) == 1
        assert result["status"] == "completed"
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_flush(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key")
        
        tracer.flush(timeout=0.1)
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_shutdown(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key")
        
        tracer.shutdown()
        
        assert tracer._shutdown.is_set()


class TestMAOTracerErrorHandling:
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_on_error_log(self, mock_provider, mock_otel, caplog):
        tracer = MAOTracer(api_key="test-key", on_error="log")
        
        from mao_testing.errors import ExportError
        tracer._handle_error(ExportError("Test error"))
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_on_error_raise(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key", on_error="raise")
        
        from mao_testing.errors import ExportError
        with pytest.raises(ExportError):
            tracer._handle_error(ExportError("Test error"))
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_on_error_ignore(self, mock_provider, mock_otel):
        tracer = MAOTracer(api_key="test-key", on_error="ignore")
        
        from mao_testing.errors import ExportError
        tracer._handle_error(ExportError("Test error"))
        
        tracer.shutdown()
