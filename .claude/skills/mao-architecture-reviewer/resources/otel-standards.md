# MAO OTEL Standards

## Required Span Attributes

All MAO spans MUST include these standard OTEL attributes:

### Service Attributes
```
service.name          = "mao-testing"
service.version       = "0.1.0"
deployment.environment = "production" | "staging" | "development"
```

### Span Attributes
```
span.kind = "client" | "server" | "producer" | "consumer" | "internal"
```

## MAO Custom Attributes

All MAO-specific attributes MUST be prefixed with `mao.`:

### Agent Attributes
```
mao.agent.name        = "researcher"           # Agent identifier
mao.agent.role        = "data_collector"       # Functional role
mao.agent.framework   = "langgraph"            # Source framework
mao.agent.input       = "Find pricing..."      # Input (truncated)
mao.agent.output      = "Found 3 tiers..."     # Output (truncated)
mao.agent.persona     = "You are a..."         # System prompt (hash or truncated)
```

### Workflow Attributes
```
mao.workflow.id       = "uuid"                 # Workflow instance ID
mao.workflow.name     = "customer-support"     # Workflow type name
mao.workflow.step     = 3                      # Current step number
mao.workflow.total_steps = 5                   # Total steps (if known)
```

### State Attributes
```
mao.state.before      = "{json}"               # State before agent execution
mao.state.after       = "{json}"               # State after agent execution
mao.state.delta       = "{json}"               # Computed delta
mao.state.hash        = "abc123"               # Hash for dedup
```

### Cost Attributes
```
mao.cost.tokens_input  = 1523                  # Input tokens
mao.cost.tokens_output = 456                   # Output tokens
mao.cost.model         = "claude-3-5-sonnet"   # Model used
mao.cost.usd           = 0.0234                # Estimated cost
```

### Detection Attributes (added by MAO)
```
mao.detection.type     = "loop"                # Detection type
mao.detection.tier     = 2                     # Detection tier used
mao.detection.confidence = 0.95                # Confidence score
mao.detection.severity = "high"                # Severity level
```

## Span Naming Conventions

Format: `{component}.{operation}`

### Agent Spans
```
agent.{name}.execute       # Main agent execution
agent.{name}.think         # Reasoning/planning phase
agent.{name}.tool.{tool}   # Tool invocation
```

### Workflow Spans
```
workflow.{name}.start      # Workflow initiation
workflow.{name}.step       # Step execution
workflow.{name}.handoff    # Agent-to-agent handoff
workflow.{name}.complete   # Workflow completion
```

### Detection Spans (internal)
```
mao.detect.loop            # Loop detection
mao.detect.state           # State corruption detection
mao.detect.persona         # Persona drift detection
mao.detect.coordination    # Coordination failure detection
```

## Trace Context Propagation

MUST follow W3C Trace Context specification:

```
traceparent: 00-{trace-id}-{span-id}-{flags}
tracestate: mao=org:{org_id};proj:{project_id}
```

## Event Naming

Span events for significant occurrences:

```
agent.input_received       # Agent received input
agent.output_generated     # Agent produced output
agent.tool_called          # Tool invocation started
agent.tool_returned        # Tool invocation completed
agent.error                # Error occurred
state.mutated              # Shared state changed
handoff.initiated          # Handoff to another agent
handoff.completed          # Handoff accepted
```

## Attribute Size Limits

| Attribute Type | Max Size |
|----------------|----------|
| String value | 4KB |
| JSON value | 64KB |
| Array items | 128 |
| Total attributes | 128 |

For larger values, store in database and reference by ID.

## Example Span

```json
{
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "spanId": "00f067aa0ba902b7",
  "parentSpanId": "a3ce929d0e0e4736",
  "name": "agent.researcher.execute",
  "kind": "INTERNAL",
  "startTime": "2025-12-01T10:00:00.000Z",
  "endTime": "2025-12-01T10:00:05.234Z",
  "attributes": {
    "service.name": "mao-testing",
    "mao.agent.name": "researcher",
    "mao.agent.role": "data_collector",
    "mao.agent.framework": "langgraph",
    "mao.agent.input": "Find pricing for competitor X",
    "mao.agent.output": "Found 3 pricing tiers: Basic $10, Pro $50, Enterprise $200",
    "mao.state.before": "{\"query\": \"competitor pricing\"}",
    "mao.state.after": "{\"query\": \"competitor pricing\", \"results\": [...]}",
    "mao.cost.tokens_input": 156,
    "mao.cost.tokens_output": 89,
    "mao.cost.model": "claude-3-5-sonnet",
    "mao.cost.usd": 0.0012
  },
  "events": [
    {
      "name": "agent.tool_called",
      "time": "2025-12-01T10:00:01.000Z",
      "attributes": {
        "tool.name": "web_search",
        "tool.input": "competitor X pricing 2025"
      }
    },
    {
      "name": "agent.tool_returned",
      "time": "2025-12-01T10:00:04.500Z",
      "attributes": {
        "tool.name": "web_search",
        "tool.output_size": 2456
      }
    }
  ]
}
```
