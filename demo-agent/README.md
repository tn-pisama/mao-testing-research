# MAO Testing - Multi-Agent Demo Agents

Multi-agent workflow demos showcasing MAO's detection capabilities using **LangGraph** and **CrewAI**.

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

# Run LangGraph demo
python langgraph_demo.py --mode normal

# Run CrewAI demo
python crewai_demo.py --mode normal

# Run with MAO tracing
python langgraph_demo.py --mode all --trace
python crewai_demo.py --mode all --trace
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

### LangGraph Integration

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

### CrewAI Integration

```python
from mao_testing.integrations.crewai import CrewAITracer

tracer = CrewAITracer(
    api_key="your-mao-key",
    endpoint="http://localhost:8000",
    environment="demo",
)

crew = Crew(agents=[researcher, analyst, writer], tasks=[...])
crew = tracer.instrument(crew)  # Auto-traces all agents

result = crew.kickoff()
tracer.flush()  # Send traces to MAO backend
```

---

## CrewAI Demo

### Crew Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Senior Researcher│────▶│ Research Analyst │────▶│ Technical Writer │
│   (research)     │     │   (analyze)      │     │   (write)        │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                               │
                        [loop mode: 🔄]
                        [corruption: 💀]
                                               [drift mode: 🎭]
```

### CrewAI Examples

```bash
# Normal execution
python crewai_demo.py --mode normal

# Infinite loop (analyst keeps requesting more research)
python crewai_demo.py --mode loop

# State corruption (corrupted tool injects garbage)
python crewai_demo.py --mode corruption

# Persona drift (writer becomes unprofessional blogger)
python crewai_demo.py --mode drift

# Run all with tracing
python crewai_demo.py --mode all --trace
```

### CrewAI Failure Modes

| Mode | Agent Affected | Bug Description |
|------|---------------|-----------------|
| `loop` | Analyst | Uses `InfiniteLoopTool` that always requests more research |
| `corruption` | Analyst | Uses `CorruptedTool` that injects error messages |
| `drift` | Writer | Becomes "Unprofessional Blogger" with casual persona |
