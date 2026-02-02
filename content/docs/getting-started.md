---
title: "Getting Started with PISAMA"
category: documentation
audience: developers
---

# Getting Started with PISAMA

Get PISAMA running in your multi-agent system in 5 minutes.

## Prerequisites

- Python 3.9+
- Existing agent system (LangGraph, CrewAI, AutoGen, n8n, or custom)
- pip or poetry for package management

## Installation

### Via pip
```bash
pip install pisama-claude-code
```

### Via poetry
```bash
poetry add pisama-claude-code
```

### From source
```bash
git clone https://github.com/tn-pisama/mao-testing-research
cd mao-testing-research/packages/pisama-claude-code
pip install -e .
```

## Quick Start

### 1. Get Your API Key

Sign up at [app.pisama.ai](https://app.pisama.ai) to get a free API key (1,000 traces/month included).

Or set up self-hosted:
```bash
docker run -p 8000:8000 pisama/pisama-server
export PISAMA_API_URL=http://localhost:8000
```

### 2. Configure Environment

```bash
export PISAMA_API_KEY="pis_your_key_here"
export PISAMA_API_URL="https://api.pisama.ai"  # Optional, defaults to cloud
```

### 3. Instrument Your Code

#### Option A: Automatic (Recommended)

Add PISAMA to your entry point:

```python
from pisama import PisamaTracer

# Initialize once at application startup
tracer = PisamaTracer(
    api_key="your-key-here",  # or set PISAMA_API_KEY env var
    project_name="my-agent-app"
)

# Wrap your workflow
with tracer.trace_workflow("customer-support"):
    result = my_agent_system.run(user_message)
```

#### Option B: Manual Span Tracking

For more control:

```python
from pisama import PisamaTracer

tracer = PisamaTracer()

# Start a workflow trace
workflow_span = tracer.start_workflow("research-task")

try:
    # Track individual agents
    planner_span = tracer.start_agent("planner", parent=workflow_span)
    plan = planner_agent.run(query)
    tracer.end_span(planner_span)

    researcher_span = tracer.start_agent("researcher", parent=workflow_span)
    results = researcher_agent.run(plan)
    tracer.end_span(researcher_span)

    # Mark workflow complete
    tracer.end_workflow(workflow_span, result=results)

except Exception as e:
    tracer.mark_failed(workflow_span, error=e)
    raise
```

### 4. Run Your Tests

```bash
pytest tests/
```

PISAMA automatically analyzes traces during test runs and reports failures.

### 5. View Results

Visit [app.pisama.ai](https://app.pisama.ai) to see:
- All traces
- Detected failures
- Performance metrics
- Cost tracking

---

## Framework-Specific Guides

### LangGraph

```python
from langgraph.graph import StateGraph
from pisama.integrations.langgraph import PisamaLangGraphTracer

# Wrap your graph
tracer = PisamaLangGraphTracer()
graph = tracer.wrap_graph(my_graph)

# Run as normal
result = graph.invoke({"input": "Hello"})
```

### CrewAI

```python
from crewai import Crew
from pisama.integrations.crewai import PisamaCrewTracer

crew = Crew(agents=[...], tasks=[...])

# Wrap the crew
tracer = PisamaCrewTracer()
traced_crew = tracer.wrap_crew(crew)

# Run as normal
result = traced_crew.kickoff()
```

### AutoGen

```python
from autogen import AssistantAgent, UserProxyAgent
from pisama.integrations.autogen import PisamaAutogenTracer

# Wrap your agents
tracer = PisamaAutogenTracer()
assistant = tracer.wrap_agent(AssistantAgent(...))
user_proxy = tracer.wrap_agent(UserProxyAgent(...))

# Run as normal
user_proxy.initiate_chat(assistant, message="Hello")
```

### n8n Workflows

```python
from pisama.integrations.n8n import PisamaN8NTracer

# Parse n8n workflow execution
tracer = PisamaN8NTracer()
workflow_data = load_n8n_execution_json()
tracer.trace_n8n_workflow(workflow_data)
```

---

## Configuration Options

### Tracer Configuration

```python
from pisama import PisamaTracer

tracer = PisamaTracer(
    # Required
    api_key="your-key",

    # Optional
    project_name="my-project",
    environment="staging",  # development, staging, production
    detection_tier="auto",  # auto, tier1, tier2, tier3, tier4
    cost_limit_dollars=1.0,  # Stop if execution exceeds this cost
    iteration_limit=100,  # Stop if execution exceeds this many steps
    enable_auto_fix=False,  # Experimental: auto-apply suggested fixes
    batch_size=10,  # Number of traces to batch before sending
    flush_interval=5,  # Seconds between batch flushes
)
```

### Detection Configuration

Enable/disable specific detectors:

```python
tracer = PisamaTracer(
    detectors={
        "loop": True,
        "state_corruption": True,
        "persona_drift": True,
        "hallucination": False,  # Disable hallucination detection
        "injection": True,
        "cost_overrun": True,
    }
)
```

---

## Testing Integration

### pytest

Add to `pytest.ini` or `pyproject.toml`:

```ini
[tool.pytest.ini_options]
addopts = "--pisama-detect=all --pisama-fail-on-detection"
```

Or use command line:

```bash
pytest --pisama-detect=all --pisama-fail-on-detection
```

Options:
- `--pisama-detect=all`: Enable all detectors
- `--pisama-detect=loop,state`: Enable specific detectors
- `--pisama-fail-on-detection`: Fail tests if failures detected
- `--pisama-report=html`: Generate HTML report

### CI/CD Integration

#### GitHub Actions

```yaml
name: Test with PISAMA

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pisama-claude-code pytest

      - name: Run tests with PISAMA
        env:
          PISAMA_API_KEY: ${{ secrets.PISAMA_API_KEY }}
        run: |
          pytest --pisama-detect=all --pisama-fail-on-detection

      - name: Upload PISAMA report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: pisama-report
          path: pisama-report.html
```

#### GitLab CI

```yaml
test:
  image: python:3.11
  script:
    - pip install -r requirements.txt pisama-claude-code pytest
    - pytest --pisama-detect=all --pisama-fail-on-detection
  artifacts:
    when: always
    paths:
      - pisama-report.html
```

---

## Troubleshooting

### Common Issues

#### "API key not found"
```bash
# Check env var is set
echo $PISAMA_API_KEY

# Or pass explicitly
tracer = PisamaTracer(api_key="your-key-here")
```

#### "No traces appearing in dashboard"
```python
# Make sure to flush before exit
tracer.flush()

# Or use context manager (auto-flushes)
with PisamaTracer() as tracer:
    # your code here
```

#### "Detection too slow"
```python
# Use lower detection tier for faster results
tracer = PisamaTracer(detection_tier="tier1")
```

#### "Too many false positives"
```python
# Adjust thresholds
tracer = PisamaTracer(
    loop_detection_threshold=5,  # Default: 3
    similarity_threshold=0.9,  # Default: 0.85
)
```

---

## Next Steps

- **Read the tutorials**: [Loop Detection Guide](/blog/loop-detection-guide)
- **Explore examples**: [GitHub examples/](https://github.com/tn-pisama/mao-testing-research/tree/main/examples)
- **Join Discord**: Get help from the community [discord.gg/pisama](https://discord.gg/pisama)
- **Upgrade to Startup plan**: Unlock ML detection and custom rules at [pisama.ai/pricing](https://pisama.ai/pricing)

---

## API Reference

Full API documentation: [docs.pisama.ai/api](https://docs.pisama.ai/api)

Quick reference:

### PisamaTracer
- `start_workflow(name: str) -> Span`
- `end_workflow(span: Span, result: Any)`
- `start_agent(name: str, parent: Span) -> Span`
- `end_span(span: Span)`
- `mark_failed(span: Span, error: Exception)`
- `flush()`

### Integrations
- `pisama.integrations.langgraph.PisamaLangGraphTracer`
- `pisama.integrations.crewai.PisamaCrewTracer`
- `pisama.integrations.autogen.PisamaAutogenTracer`
- `pisama.integrations.n8n.PisamaN8NTracer`

---

## Support

- 📧 **Email**: support@pisama.ai
- 💬 **Discord**: [discord.gg/pisama](https://discord.gg/pisama)
- 🐛 **Issues**: [GitHub Issues](https://github.com/tn-pisama/mao-testing-research/issues)
- 📚 **Docs**: [docs.pisama.ai](https://docs.pisama.ai)
