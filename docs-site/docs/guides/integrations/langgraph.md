# LangGraph Integration

PISAMA monitors [LangGraph](https://langchain-ai.github.io/langgraph/) applications by ingesting traces via webhooks or the OTEL export pipeline.

## Setup

### Webhook-Based Integration

Register your LangGraph deployment with PISAMA and configure it to send execution events:

**Register a deployment:**

```bash
curl -X POST http://localhost:8000/api/v1/langgraph/deployments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-langgraph-app",
    "url": "https://my-langgraph-deployment.com",
    "description": "Production research pipeline"
  }'
```

**Register assistants:**

```bash
curl -X POST http://localhost:8000/api/v1/langgraph/assistants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_id": "<deployment_id>",
    "name": "research-assistant",
    "graph_id": "research_graph"
  }'
```

### OTEL-Based Integration

If your LangGraph app already exports OTEL traces, point the OTEL exporter to PISAMA:

```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

exporter = OTLPSpanExporter(
    endpoint="https://your-pisama.com/api/v1/tenants/TENANT_ID/traces/ingest",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)
```

## LangGraph-Specific Attributes

PISAMA recognizes LangGraph-specific OTEL attributes for agent identification and state tracking:

| OTEL Attribute | Description |
|---|---|
| `langgraph.node.name` | Name of the graph node being executed |
| `langgraph.state` | Current graph state as JSON |
| `langgraph.thread_id` | Thread identifier for multi-turn conversations |
| `langgraph.checkpoint_id` | Checkpoint identifier for state persistence |

These attributes are automatically extracted during trace ingestion and used by PISAMA's detection pipeline.

## Detection Capabilities

When monitoring LangGraph applications, PISAMA detects:

- **Loop detection**: Agents cycling through the same nodes repeatedly
- **State corruption**: State mutations that violate schema or domain constraints
- **Context overflow**: Token accumulation across graph nodes
- **Coordination failures**: Node-to-node handoff issues
- **Task derailment**: Nodes producing output unrelated to their assigned task
- **Persona drift**: Agents deviating from their configured behavior
- **Workflow design issues**: Graph structure problems (unreachable nodes, dead ends)

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/langgraph/webhook` | Receive deployment webhook |
| `POST` | `/api/v1/langgraph/deployments` | Register a deployment |
| `GET` | `/api/v1/langgraph/deployments` | List deployments |
| `POST` | `/api/v1/langgraph/assistants` | Register an assistant |
| `GET` | `/api/v1/langgraph/assistants` | List assistants |
| `GET` | `/api/v1/langgraph/stream` | SSE for real-time updates |

## Example: Instrumenting a LangGraph App

```python
from langgraph.graph import StateGraph, END
from pisama_core import PisamaTracer

# Initialize PISAMA tracer
tracer = PisamaTracer(
    api_url="https://your-pisama.com/api/v1",
    api_key="YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)

# Define your graph
graph = StateGraph(AgentState)
graph.add_node("researcher", research_node)
graph.add_node("writer", writer_node)
graph.add_edge("researcher", "writer")
graph.add_edge("writer", END)

# Compile with PISAMA tracing
app = graph.compile()

# Run with tracing
with tracer.trace("research-pipeline"):
    result = app.invoke({"task": "Research AI agent testing"})
```
