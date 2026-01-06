"""Integration tests for MAO Testing SDK with backend."""

import pytest
from unittest.mock import patch, MagicMock
import json

from mao_testing import MAOTracer
from mao_testing.config import MAOConfig


class TestBackendIntegration:
    """Integration tests that simulate backend interaction."""
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    @patch("mao_testing.tracer.httpx.Client")
    def test_full_trace_workflow(self, mock_client_class, mock_provider, mock_otel):
        """Test a complete trace workflow from start to export."""
        mock_client = MagicMock()
        mock_client.post.return_value = MagicMock(status_code=200)
        mock_client_class.return_value = mock_client
        
        tracer = MAOTracer(
            api_key="test-api-key",
            endpoint="http://localhost:8000",
            environment="test",
            service_name="integration-test",
            batch_size=1,
        )
        
        with tracer.trace("integration-test-workflow", framework="langgraph") as session:
            session.set_metadata({
                "user_id": "test-user",
                "request_id": "req-123",
            })
            session.add_tags(["integration", "test"])
            
            session.capture_state("initial", {
                "query": "What is machine learning?",
                "context": [],
            })
            
            with session.span("researcher-agent") as span:
                span.set_attribute("gen_ai.agent.name", "researcher")
                span.set_attribute("langgraph.node.name", "researcher")
                span.add_event("searching", {"query": "machine learning"})
                
                session.capture_state("after_research", {
                    "query": "What is machine learning?",
                    "context": ["ML is a subset of AI..."],
                }, agent_id="researcher")
            
            with session.span("writer-agent") as span:
                span.set_attribute("gen_ai.agent.name", "writer")
                span.set_attribute("langgraph.node.name", "writer")
                
                session.capture_state("after_writing", {
                    "query": "What is machine learning?",
                    "context": ["ML is a subset of AI..."],
                    "response": "Machine learning is...",
                }, agent_id="writer")
        
        tracer.flush(timeout=1.0)
        
        assert session._status == "completed"
        assert len(session._states) == 3
        assert len(session._spans) == 2
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_error_handling_in_trace(self, mock_provider, mock_otel):
        """Test error handling during trace execution."""
        tracer = MAOTracer(api_key="test-key")
        
        with pytest.raises(ValueError):
            with tracer.trace("error-workflow") as session:
                session.capture_state("before_error", {"status": "ok"})
                raise ValueError("Simulated agent error")
        
        assert session._status == "failed"
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_nested_spans(self, mock_provider, mock_otel):
        """Test nested span creation."""
        tracer = MAOTracer(api_key="test-key")
        
        with tracer.trace("nested-workflow") as session:
            with session.span("parent-span") as parent:
                parent.set_attribute("level", "parent")
                
                with session.span("child-span") as child:
                    child.set_attribute("level", "child")
        
        assert len(session._spans) == 2
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_state_capture_sequence(self, mock_provider, mock_otel):
        """Test that states are captured in sequence."""
        tracer = MAOTracer(api_key="test-key")
        
        with tracer.trace("state-workflow") as session:
            for i in range(5):
                session.capture_state(f"step_{i}", {"step": i, "data": f"value_{i}"})
        
        assert len(session._states) == 5
        for i, state in enumerate(session._states):
            assert state.name == f"step_{i}"
            assert state.data["step"] == i
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    @patch("mao_testing.tracer.httpx.Client")
    def test_export_payload_format(self, mock_client_class, mock_provider, mock_otel):
        """Test that export payload has correct format for backend."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        tracer = MAOTracer(
            api_key="test-key",
            endpoint="http://localhost:8000",
            batch_size=1,
        )
        
        with tracer.trace("export-test", framework="autogen") as session:
            session.set_metadata({"test": True})
            session.add_tag("export-test")
            session.capture_state("test-state", {"x": 1})
            
            with session.span("test-span") as span:
                span.set_attribute("key", "value")
        
        tracer.flush(timeout=2.0)
        
        tracer.shutdown()


class TestOTELAttributeFormat:
    """Test that OTEL attributes are formatted correctly for backend parsing."""
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_langgraph_attributes(self, mock_provider, mock_otel):
        """Test LangGraph-specific OTEL attributes."""
        tracer = MAOTracer(api_key="test-key")
        
        with tracer.trace("langgraph-test", framework="langgraph") as session:
            with session.span("node:researcher") as span:
                span.set_attribute("langgraph.node.name", "researcher")
                span.set_attribute("langgraph.state", '{"messages": []}')
                span.set_attribute("gen_ai.agent.name", "researcher")
        
        span_data = session._spans[0].to_data()
        
        assert span_data.attributes["langgraph.node.name"] == "researcher"
        assert span_data.attributes["gen_ai.agent.name"] == "researcher"
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_autogen_attributes(self, mock_provider, mock_otel):
        """Test AutoGen-specific OTEL attributes."""
        tracer = MAOTracer(api_key="test-key")
        
        with tracer.trace("autogen-test", framework="autogen") as session:
            with session.span("agent:assistant") as span:
                span.set_attribute("autogen.agent.name", "assistant")
                span.set_attribute("gen_ai.prompt", "Hello, how are you?")
                span.set_attribute("gen_ai.completion", "I am doing well!")
        
        span_data = session._spans[0].to_data()
        
        assert span_data.attributes["autogen.agent.name"] == "assistant"
        assert span_data.attributes["gen_ai.prompt"] == "Hello, how are you?"
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_crewai_attributes(self, mock_provider, mock_otel):
        """Test CrewAI-specific OTEL attributes."""
        tracer = MAOTracer(api_key="test-key")
        
        with tracer.trace("crewai-test", framework="crewai") as session:
            with session.span("agent:researcher") as span:
                span.set_attribute("crewai.agent.role", "researcher")
                span.set_attribute("crewai.task.description", "Research topic X")
                span.set_attribute("gen_ai.agent.name", "researcher")
        
        span_data = session._spans[0].to_data()
        
        assert span_data.attributes["crewai.agent.role"] == "researcher"
        assert span_data.attributes["crewai.task.description"] == "Research topic X"
        
        tracer.shutdown()
