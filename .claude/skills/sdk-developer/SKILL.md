---
name: sdk-developer
description: |
  Patterns for agent instrumentation SDK and framework adapters.
  Use when adding framework support (LangGraph, AutoGen, CrewAI), creating instrumentation, or building adapters.
  Ensures framework-agnostic core with OTEL-compliant span generation.
allowed-tools: Read, Grep, Glob, Write
---

# SDK Developer Skill

You are developing the PISAMA SDK for agent instrumentation. Your goal is to create framework adapters that generate OTEL-compliant traces while maintaining a framework-agnostic core.

## SDK Architecture

```
packages/
├── pisama-core/          # Core types, no framework dependencies
│   ├── types.py         # Detection types, Trace, Span
│   └── protocols.py     # Instrumentation protocols
│
├── pisama-agent-sdk/    # Instrumentation SDK
│   ├── tracer.py        # OTEL tracer wrapper
│   ├── decorators.py    # @traced, @agent, @tool decorators
│   └── adapters/        # Framework-specific adapters
│       ├── langraph.py
│       ├── autogen.py
│       ├── crewai.py
│       └── n8n.py
│
└── pisama-claude-code/  # Claude Code integration
    └── mcp_server.py
```

---

## Core Principles

### 1. Framework-Agnostic Core
- `pisama-core` MUST NOT import any agent framework
- All framework-specific code in `adapters/`
- Use Protocol classes for framework interfaces

### 2. OTEL-First
- All spans use OpenTelemetry SDK
- GenAI semantic conventions (`gen_ai.*` attributes)
- W3C Trace Context propagation

### 3. Zero-Config Instrumentation
- Frameworks should auto-detect and instrument
- Minimal code changes for users
- Fallback to manual instrumentation if auto-detect fails

---

## Adding a New Framework Adapter

### Step 1: Create Adapter File

```python
# packages/pisama-agent-sdk/adapters/newframework.py

from typing import Any, Dict, Optional
from opentelemetry import trace
from pisama_core.protocols import AgentInstrumentor

class NewFrameworkAdapter(AgentInstrumentor):
    """
    Adapter for NewFramework agent library.
    
    Instruments:
    - Agent invocations
    - Tool calls
    - State transitions
    """
    
    def __init__(self, tracer: Optional[trace.Tracer] = None):
        self.tracer = tracer or trace.get_tracer("pisama.newframework")
    
    def instrument_agent(self, agent: Any) -> Any:
        """Wraps agent to add tracing."""
        original_run = agent.run
        
        def traced_run(*args, **kwargs):
            with self.tracer.start_as_current_span(
                "agent.run",
                attributes={
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.agent.name": agent.name,
                    "gen_ai.agent.id": id(agent),
                }
            ) as span:
                try:
                    result = original_run(*args, **kwargs)
                    span.set_attribute("gen_ai.response.finish_reasons", ["stop"])
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        agent.run = traced_run
        return agent
    
    def instrument_tool(self, tool: Any) -> Any:
        """Wraps tool calls to add tracing."""
        original_call = tool.__call__
        
        def traced_call(*args, **kwargs):
            with self.tracer.start_as_current_span(
                "tool.call",
                attributes={
                    "gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": tool.name,
                }
            ) as span:
                result = original_call(*args, **kwargs)
                return result
        
        tool.__call__ = traced_call
        return tool
```

### Step 2: Auto-Detection (Optional)

```python
def auto_instrument():
    """Auto-detects and instruments NewFramework if present."""
    try:
        import newframework
        adapter = NewFrameworkAdapter()
        
        # Patch framework classes
        original_agent_init = newframework.Agent.__init__
        def instrumented_init(self, *args, **kwargs):
            original_agent_init(self, *args, **kwargs)
            adapter.instrument_agent(self)
        
        newframework.Agent.__init__ = instrumented_init
        
    except ImportError:
        pass  # Framework not installed
```

### Step 3: Add Tests

```python
# tests/adapters/test_newframework.py

import pytest
from unittest.mock import Mock, patch
from pisama_agent_sdk.adapters.newframework import NewFrameworkAdapter

def test_instrument_agent():
    """Test agent instrumentation creates spans."""
    adapter = NewFrameworkAdapter()
    
    mock_agent = Mock()
    mock_agent.name = "TestAgent"
    mock_agent.run = Mock(return_value="result")
    
    instrumented = adapter.instrument_agent(mock_agent)
    result = instrumented.run("input")
    
    assert result == "result"
    # Verify span was created
    # (requires OTEL test setup)
```

### Step 4: Document Usage

```markdown
# NewFramework Adapter

## Installation
\```bash
pip install pisama-agent-sdk[newframework]
\```

## Usage

### Auto-Instrumentation
\```python
from pisama_agent_sdk.adapters.newframework import auto_instrument
auto_instrument()

# Now all agents are automatically traced
from newframework import Agent
agent = Agent("my-agent")
agent.run("task")  # Traced!
\```

### Manual Instrumentation
\```python
from pisama_agent_sdk.adapters.newframework import NewFrameworkAdapter

adapter = NewFrameworkAdapter()
agent = Agent("my-agent")
adapter.instrument_agent(agent)
\```
```

---

## Common Patterns

### Pattern 1: State Capture

```python
def capture_state(span: trace.Span, state: Dict[str, Any]):
    """Capture agent state in span attributes."""
    span.set_attribute("mao.state.before", json.dumps(state, default=str))
```

### Pattern 2: Token Tracking

```python
def track_tokens(span: trace.Span, response: Any):
    """Track token usage from LLM response."""
    if hasattr(response, "usage"):
        span.set_attribute("gen_ai.usage.input_tokens", response.usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", response.usage.output_tokens)
```

### Pattern 3: Error Handling

```python
def handle_error(span: trace.Span, error: Exception):
    """Standard error handling for spans."""
    span.set_status(trace.Status(trace.StatusCode.ERROR, str(error)))
    span.record_exception(error)
    span.set_attribute("mao.error.type", type(error).__name__)
```

---

## Adapter Checklist

- [ ] Extends `AgentInstrumentor` protocol
- [ ] Uses OTEL `gen_ai.*` attributes
- [ ] Captures agent name, ID
- [ ] Captures tool calls
- [ ] Captures state transitions (if applicable)
- [ ] Tracks token usage (if using LLM)
- [ ] Error handling with span status
- [ ] Auto-instrumentation function (optional)
- [ ] Unit tests with mocked framework
- [ ] Integration tests with real framework
- [ ] Documentation with usage examples

---

## Resources

For adapter templates and examples:
- `resources/adapter-template.py` - Full adapter template
- `packages/pisama-agent-sdk/adapters/n8n.py` - Reference implementation
- `docs/SDK_DEVELOPMENT.md` - Detailed SDK guide
