# MAO Testing SDK

Python SDK for the MAO Testing Platform - Multi-Agent Orchestration failure detection.

## Installation

```bash
pip install mao-testing
```

With framework-specific integrations:

```bash
pip install mao-testing[langgraph]
pip install mao-testing[autogen]
pip install mao-testing[crewai]
pip install mao-testing[all]
```

## Quick Start

```python
from mao_testing import MAOTracer

# Initialize the tracer
tracer = MAOTracer(
    api_key="your-api-key",  # Or set MAO_API_KEY env var
    environment="production",
    service_name="my-agent-system",
)

# Trace a workflow
with tracer.trace("my-workflow") as session:
    session.capture_state("initial", {"query": "Hello"})
    
    with session.span("researcher-agent") as span:
        span.set_attribute("gen_ai.agent.name", "researcher")
        # Your agent logic here
        result = do_research()
        session.capture_state("after_research", result)
    
    with session.span("writer-agent") as span:
        span.set_attribute("gen_ai.agent.name", "writer")
        # Your agent logic here
        output = generate_output()
        session.capture_state("final", output)
```

## Framework Integrations

### LangGraph

```python
from mao_testing.integrations.langgraph import LangGraphTracer
from langgraph.graph import StateGraph

tracer = LangGraphTracer()

# Your graph definition
graph = StateGraph(AgentState)
graph.add_node("researcher", researcher_agent)
graph.add_node("writer", writer_agent)

# Instrument the graph
graph = tracer.instrument(graph)

# All nodes are now automatically traced
result = graph.compile().invoke(initial_state)
```

### AutoGen

```python
from mao_testing.integrations.autogen import AutoGenTracer
import autogen

tracer = AutoGenTracer()

# Instrument agents
assistant = tracer.instrument(
    autogen.AssistantAgent("assistant", llm_config=config)
)
user_proxy = tracer.instrument(
    autogen.UserProxyAgent("user_proxy")
)

# Conversations are automatically traced
user_proxy.initiate_chat(assistant, message="Hello")
```

### CrewAI

```python
from mao_testing.integrations.crewai import CrewAITracer
from crewai import Crew, Agent, Task

tracer = CrewAITracer()

# Your crew setup
crew = Crew(agents=[researcher, writer], tasks=[research_task])

# Instrument the crew
crew = tracer.instrument(crew)

# Kickoff is automatically traced
result = crew.kickoff()
```

## Configuration

```python
from mao_testing import MAOTracer, MAOConfig
from mao_testing.config import SamplingRule

config = MAOConfig(
    api_key="your-api-key",
    endpoint="https://api.mao-testing.com",
    environment="production",
    service_name="my-service",
    sample_rate=1.0,  # Sample all traces
    batch_size=100,
    flush_interval=5.0,
    on_error="log",  # "log", "raise", or "ignore"
    sampling_rules=[
        SamplingRule(condition="status == 'error'", rate=1.0),
        SamplingRule(condition="duration > 30s", rate=1.0),
    ],
)

tracer = MAOTracer(config=config)
```

### Environment Variables

- `MAO_API_KEY` - API key for authentication
- `MAO_ENDPOINT` - API endpoint URL
- `MAO_ENVIRONMENT` - Environment name (development, staging, production)
- `MAO_SERVICE_NAME` - Service identifier
- `MAO_SAMPLE_RATE` - Trace sampling rate (0.0-1.0)

## API Reference

### MAOTracer

```python
tracer = MAOTracer(
    api_key="...",
    endpoint="...",
    environment="...",
    service_name="...",
    sample_rate=1.0,
    batch_size=100,
    flush_interval=5.0,
    on_error="log",
)

# Create a trace session
session = tracer.trace("workflow-name", framework="langgraph")

# Flush pending exports
tracer.flush(timeout=30.0)

# Shutdown
tracer.shutdown()
```

### TraceSession

```python
with tracer.trace("workflow") as session:
    # Set metadata
    session.set_metadata({"user_id": "123", "request_id": "abc"})
    
    # Add tags
    session.add_tag("production")
    session.add_tags(["critical", "retry"])
    
    # Capture state snapshots
    session.capture_state("step_name", {"key": "value"}, agent_id="agent1")
    
    # Create spans
    with session.span("operation") as span:
        # span operations...
        pass
```

### Span

```python
with session.span("operation-name") as span:
    # Set attributes
    span.set_attribute("key", "value")
    span.set_attributes({"a": 1, "b": 2})
    
    # Add events
    span.add_event("event-name", {"detail": "value"})
    
    # Set status
    span.set_status("ok")
    span.set_status("error", "Error message")
    
    # Record exception
    try:
        risky_operation()
    except Exception as e:
        span.record_exception(e)
        raise
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=mao_testing --cov-report=html
```

## License

MIT
