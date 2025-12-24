"""Tests for MAO Testing SDK framework integrations."""

import pytest
from unittest.mock import MagicMock, patch


class TestLangGraphIntegration:
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_langgraph_tracer_creation(self, mock_provider, mock_otel):
        from mao_testing.integrations.langgraph import LangGraphTracer
        
        tracer = LangGraphTracer(api_key="test-key")
        assert tracer._active_session is None
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_trace_node_decorator(self, mock_provider, mock_otel):
        from mao_testing.integrations.langgraph import LangGraphTracer
        
        tracer = LangGraphTracer(api_key="test-key")
        
        @tracer.trace_node("test_node")
        def my_node(state):
            return {"result": state.get("input", "") + "_processed"}
        
        result = my_node({"input": "test"})
        assert result == {"result": "test_processed"}
        
        tracer.shutdown()


class TestAutoGenIntegration:
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_autogen_tracer_creation(self, mock_provider, mock_otel):
        from mao_testing.integrations.autogen import AutoGenTracer
        
        tracer = AutoGenTracer(api_key="test-key")
        assert tracer._active_session is None
        assert tracer._instrumented_agents == {}
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_instrument_agent_requires_autogen(self, mock_provider, mock_otel):
        from mao_testing.integrations.autogen import AutoGenTracer
        
        tracer = AutoGenTracer(api_key="test-key")
        
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        
        with pytest.raises(ImportError) as exc_info:
            tracer.instrument(mock_agent)
        
        assert "pyautogen is required" in str(exc_info.value)
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_instrument_all_requires_autogen(self, mock_provider, mock_otel):
        from mao_testing.integrations.autogen import AutoGenTracer
        
        tracer = AutoGenTracer(api_key="test-key")
        
        agents = [MagicMock(name=f"agent-{i}") for i in range(3)]
        
        with pytest.raises(ImportError) as exc_info:
            tracer.instrument_all(agents)
        
        assert "pyautogen is required" in str(exc_info.value)
        tracer.shutdown()


class TestCrewAIIntegration:
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_crewai_tracer_creation(self, mock_provider, mock_otel):
        from mao_testing.integrations.crewai import CrewAITracer
        
        tracer = CrewAITracer(api_key="test-key")
        assert tracer._active_session is None
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_instrument_agent_mock(self, mock_provider, mock_otel):
        from mao_testing.integrations.crewai import CrewAITracer
        
        tracer = CrewAITracer(api_key="test-key")
        
        mock_agent = MagicMock()
        mock_agent.role = "researcher"
        mock_agent.goal = "Find information"
        mock_agent.execute_task = MagicMock(return_value="task result")
        
        tracer.instrument_agent(mock_agent)
        
        assert hasattr(mock_agent, "execute_task")
        tracer.shutdown()


class TestIntegrationImportErrors:
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_langgraph_import_error(self, mock_provider, mock_otel):
        from mao_testing.integrations.langgraph import LangGraphTracer
        
        tracer = LangGraphTracer(api_key="test-key")
        
        mock_graph = MagicMock()
        mock_graph._nodes = {}
        
        with patch.dict("sys.modules", {"langgraph": None, "langgraph.graph": None}):
            pass
        
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_autogen_import_error(self, mock_provider, mock_otel):
        from mao_testing.integrations.autogen import AutoGenTracer
        
        tracer = AutoGenTracer(api_key="test-key")
        tracer.shutdown()
    
    @patch("mao_testing.tracer.otel_trace")
    @patch("mao_testing.tracer.TracerProvider")
    def test_crewai_import_error(self, mock_provider, mock_otel):
        from mao_testing.integrations.crewai import CrewAITracer
        
        tracer = CrewAITracer(api_key="test-key")
        tracer.shutdown()
