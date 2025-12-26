# MAO Testing - LangGraph Demo Agent

Multi-agent workflow demos showcasing MAO's detection capabilities.

## Quick Start

```bash
cd demo-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -e ../sdk  # Install MAO SDK

# Set API key
export OPENAI_API_KEY=your-key-here

# Run normal workflow
python langgraph_demo.py --mode normal

# Run with MAO tracing
python langgraph_demo.py --mode normal --trace
```

## Demo Modes

| Mode | Description | MAO Detection |
|------|-------------|---------------|
| `normal` | Successful research workflow | Baseline (no issues) |
| `loop` | Infinite loop - analyst always requests more research | `INFINITE_LOOP` |
| `corruption` | State corruption - analyst clears research notes | `STATE_CORRUPTION` |
| `drift` | Persona drift - writer becomes unprofessional | `PERSONA_DRIFT` |
| `all` | Run all scenarios sequentially | All detections |

## Workflow Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  Researcher │────▶│   Analyst    │────▶│   Writer   │
│   (LLM)     │     │    (LLM)     │     │   (LLM)    │
└─────────────┘     └──────────────┘     └────────────┘
       │                   │
       │     ┌─────────────┘
       │     │ (loop mode: always routes back)
       │     ▼
       └─────────────────────────────────────────────────
```

## Examples

### Normal Execution
```bash
python langgraph_demo.py --mode normal --query "Benefits of AI agents"
```

### Infinite Loop Demo
```bash
# Will hit recursion limit after max-iterations
python langgraph_demo.py --mode loop --max-iterations 3
```

### State Corruption Demo
```bash
python langgraph_demo.py --mode corruption
# Watch for: research_notes becomes empty after analyst
```

### Persona Drift Demo
```bash
python langgraph_demo.py --mode drift
# Watch for: writer output becomes casual/unprofessional
```

### Full Demo with MAO Tracing
```bash
# Start MAO backend first
cd ../backend && uvicorn app.main:app --reload

# Run all demos with tracing
python langgraph_demo.py --mode all --trace --endpoint http://localhost:8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `MAO_API_KEY` | MAO API key for tracing | `demo-key` |
| `DEMO_MODEL` | OpenAI model to use | `gpt-4o-mini` |

## What MAO Detects

### Infinite Loop Detection
- Tracks iteration count across nodes
- Detects repeated state patterns
- Alerts when agent revisits same node >3 times

### State Corruption Detection
- Computes hash of state at each step
- Detects when critical fields are cleared/modified unexpectedly
- Tracks state delta consistency

### Persona Drift Detection
- Monitors output style consistency
- Detects deviation from system prompt persona
- Flags unprofessional/off-brand content

## Integration with MAO SDK

The demo uses `LangGraphTracer` for automatic instrumentation:

```python
from mao_testing.integrations.langgraph import LangGraphTracer

tracer = LangGraphTracer(
    api_key="your-mao-key",
    endpoint="http://localhost:8000",
    environment="demo",
)

workflow = create_normal_workflow()
workflow = tracer.instrument(workflow)  # Auto-traces all nodes

result = workflow.compile().invoke(initial_state)
tracer.flush()  # Send traces to MAO backend
```
