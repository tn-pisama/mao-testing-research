# Framework Adapter Template

Use this template when creating a new framework adapter for PISAMA.

```python
"""
Adapter for {FrameworkName} agent library.

Provides OTEL-compliant instrumentation for {FrameworkName} agents.
"""

from typing import Any, Dict, Optional, List
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pisama_core.protocols import AgentInstrumentor
import json


class {FrameworkName}Adapter(AgentInstrumentor):
    """
    Instruments {FrameworkName} agents with OTEL tracing.
    
    Features:
    - Agent invocation tracing
    - Tool call tracing
    - State transition capture
    - Token usage tracking
    - Error handling
    """
    
    def __init__(self, tracer: Optional[trace.Tracer] = None):
        """
        Initialize adapter.
        
        Args:
            tracer: Optional OTEL tracer. If None, uses default tracer.
        """
        self.tracer = tracer or trace.get_tracer("pisama.{framework_name}")
    
    def instrument_agent(self, agent: Any) -> Any:
        """
        Instrument an agent instance.
        
        Args:
            agent: {FrameworkName} agent instance
            
        Returns:
            Instrumented agent
        """
        original_run = agent.run  # Adjust method name as needed
        
        def traced_run(*args, **kwargs):
            with self.tracer.start_as_current_span(
                "agent.run",
                attributes=self._get_agent_attributes(agent),
            ) as span:
                try:
                    # Capture input
                    if args:
                        span.set_attribute("gen_ai.input.messages", 
                                          json.dumps(args[0], default=str))
                    
                    # Execute agent
                    result = original_run(*args, **kwargs)
                    
                    # Capture output
                    span.set_attribute("gen_ai.output.messages", 
                                      json.dumps(result, default=str))
                    span.set_attribute("gen_ai.response.finish_reasons", ["stop"])
                    
                    # Track tokens if available
                    if hasattr(result, "usage"):
                        self._track_tokens(span, result.usage)
                    
                    return result
                    
                except Exception as e:
                    self._handle_error(span, e)
                    raise
        
        agent.run = traced_run
        return agent
    
    def instrument_tool(self, tool: Any) -> Any:
        """
        Instrument a tool instance.
        
        Args:
            tool: {FrameworkName} tool instance
            
        Returns:
            Instrumented tool
        """
        original_call = tool.__call__
        
        def traced_call(*args, **kwargs):
            with self.tracer.start_as_current_span(
                "tool.call",
                attributes=self._get_tool_attributes(tool),
            ) as span:
                try:
                    result = original_call(*args, **kwargs)
                    span.set_attribute("mao.tool.result", json.dumps(result, default=str))
                    return result
                except Exception as e:
                    self._handle_error(span, e)
                    raise
        
        tool.__call__ = traced_call
        return tool
    
    def capture_state(self, state: Dict[str, Any]) -> None:
        """
        Capture agent state in current span.
        
        Args:
            state: Current agent state
        """
        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("mao.state.after", json.dumps(state, default=str))
    
    def _get_agent_attributes(self, agent: Any) -> Dict[str, str]:
        """Extract agent attributes for span."""
        return {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": getattr(agent, "name", "unknown"),
            "gen_ai.agent.id": str(id(agent)),
            "mao.agent.type": agent.__class__.__name__,
        }
    
    def _get_tool_attributes(self, tool: Any) -> Dict[str, str]:
        """Extract tool attributes for span."""
        return {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": getattr(tool, "name", tool.__class__.__name__),
            "gen_ai.tool.call.id": str(id(tool)),
        }
    
    def _track_tokens(self, span: trace.Span, usage: Any) -> None:
        """Track token usage in span."""
        if hasattr(usage, "input_tokens"):
            span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
        if hasattr(usage, "output_tokens"):
            span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
        if hasattr(usage, "total_tokens"):
            span.set_attribute("gen_ai.usage.total_tokens", usage.total_tokens)
    
    def _handle_error(self, span: trace.Span, error: Exception) -> None:
        """Handle errors in span."""
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)
        span.set_attribute("mao.error.type", type(error).__name__)
        span.set_attribute("mao.error.message", str(error))


# Auto-instrumentation (optional)
def auto_instrument():
    """
    Automatically instrument {FrameworkName} if installed.
    
    Call this at module import to enable automatic tracing.
    """
    try:
        import {framework_module}
        
        adapter = {FrameworkName}Adapter()
        
        # Patch framework classes
        original_agent_init = {framework_module}.Agent.__init__
        
        def instrumented_init(self, *args, **kwargs):
            original_agent_init(self, *args, **kwargs)
            adapter.instrument_agent(self)
        
        {framework_module}.Agent.__init__ = instrumented_init
        
        print(f"{FrameworkName} auto-instrumentation enabled")
        
    except ImportError:
        # Framework not installed, skip
        pass


# Public API
__all__ = ["{FrameworkName}Adapter", "auto_instrument"]
```

## Usage Example

```python
# Basic usage
from pisama_agent_sdk.adapters.{framework_name} import {FrameworkName}Adapter

adapter = {FrameworkName}Adapter()
agent = MyAgent()
adapter.instrument_agent(agent)

# Auto-instrumentation
from pisama_agent_sdk.adapters.{framework_name} import auto_instrument
auto_instrument()

# All agents now automatically traced
agent = MyAgent()
agent.run("task")
```

## Testing Template

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from pisama_agent_sdk.adapters.{framework_name} import {FrameworkName}Adapter

@pytest.fixture
def mock_tracer():
    """Mock OTEL tracer."""
    tracer = Mock()
    span = Mock()
    span.set_attribute = Mock()
    span.set_status = Mock()
    span.record_exception = Mock()
    span.is_recording = Mock(return_value=True)
    
    tracer.start_as_current_span = MagicMock()
    tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=span)
    tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
    
    return tracer

def test_instrument_agent(mock_tracer):
    """Test agent instrumentation."""
    adapter = {FrameworkName}Adapter(tracer=mock_tracer)
    
    mock_agent = Mock()
    mock_agent.name = "TestAgent"
    mock_agent.run = Mock(return_value="result")
    
    instrumented = adapter.instrument_agent(mock_agent)
    result = instrumented.run("input")
    
    assert result == "result"
    mock_tracer.start_as_current_span.assert_called()

def test_instrument_tool(mock_tracer):
    """Test tool instrumentation."""
    adapter = {FrameworkName}Adapter(tracer=mock_tracer)
    
    mock_tool = Mock()
    mock_tool.name = "TestTool"
    mock_tool.__call__ = Mock(return_value="tool_result")
    
    instrumented = adapter.instrument_tool(mock_tool)
    result = instrumented("input")
    
    assert result == "tool_result"
    mock_tracer.start_as_current_span.assert_called()

def test_error_handling(mock_tracer):
    """Test error handling in spans."""
    adapter = {FrameworkName}Adapter(tracer=mock_tracer)
    
    mock_agent = Mock()
    mock_agent.run = Mock(side_effect=ValueError("test error"))
    
    instrumented = adapter.instrument_agent(mock_agent)
    
    with pytest.raises(ValueError):
        instrumented.run("input")
    
    # Verify error was recorded
    span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
    span.set_status.assert_called()
    span.record_exception.assert_called()
```
