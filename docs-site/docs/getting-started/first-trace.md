# Your First Run

This tutorial walks you through sending a run to Pisama, running detection, and interpreting the results.

!!! info "Terminology"
    In Pisama, a **run** is a complete execution of your agent or workflow. Under the hood, runs are stored as [OpenTelemetry traces](https://opentelemetry.io/docs/concepts/signals/traces/) — a collection of spans sharing the same `traceId`. The API uses `trace` in endpoint paths and payloads for OTEL compatibility.

## Prerequisites

- Pisama running locally (see [Installation](installation.md))
- `curl` and `jq` installed

## Step 1: Create a tenant

Every run belongs to a tenant. Create one:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "my-first-project"}' | jq .
```

Save the values from the response:

```bash
export TENANT_ID="<tenant_id from response>"
export API_KEY="<api_key from response>"
```

## Step 2: Get a JWT token

Exchange your API key for a bearer token:

```bash
export TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"api_key\": \"$API_KEY\"}" | jq -r '.access_token')
```

## Step 3: Send an OpenTelemetry trace

PISAMA accepts traces in the standard OTEL span export format. Here is a minimal example with two agent steps:

```bash
curl -s -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/traces/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "demo-pipeline"}}
        ]
      },
      "scopeSpans": [{
        "spans": [
          {
            "traceId": "demo-trace-001",
            "spanId": "span-001",
            "name": "research_step",
            "kind": 1,
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000002000000000",
            "attributes": [
              {"key": "gen_ai.agent.name", "value": {"stringValue": "researcher"}},
              {"key": "gen_ai.request.model", "value": {"stringValue": "claude-sonnet-4"}},
              {"key": "gen_ai.usage.prompt_tokens", "value": {"intValue": 2000}},
              {"key": "gen_ai.usage.completion_tokens", "value": {"intValue": 1500}},
              {"key": "gen_ai.state", "value": {"stringValue": "{\"task\": \"research pricing\", \"status\": \"complete\"}"}}
            ],
            "status": {"code": 1}
          },
          {
            "traceId": "demo-trace-001",
            "spanId": "span-002",
            "parentSpanId": "span-001",
            "name": "writing_step",
            "kind": 1,
            "startTimeUnixNano": "1700000002000000000",
            "endTimeUnixNano": "1700000005000000000",
            "attributes": [
              {"key": "gen_ai.agent.name", "value": {"stringValue": "writer"}},
              {"key": "gen_ai.request.model", "value": {"stringValue": "claude-sonnet-4"}},
              {"key": "gen_ai.usage.prompt_tokens", "value": {"intValue": 3000}},
              {"key": "gen_ai.usage.completion_tokens", "value": {"intValue": 2000}},
              {"key": "gen_ai.state", "value": {"stringValue": "{\"task\": \"write report\", \"status\": \"complete\"}"}}
            ],
            "status": {"code": 1}
          }
        ]
      }]
    }]
  }' | jq .
```

You should receive a `202 Accepted` response.

## Step 4: Run detection analysis

Trigger the detection pipeline on your trace:

```bash
curl -s -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/traces/demo-trace-001/analyze" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

The response contains:

- `has_failures` -- whether any failure modes were detected
- `failure_count` -- total number of detections
- `primary_failure` -- the most severe/confident detection
- `all_detections` -- full list with confidence, severity, evidence, and suggested fixes
- `detection_time_ms` -- how long the analysis took

## Step 5: View detections

List all detections for your tenant:

```bash
curl -s "http://localhost:8000/api/v1/tenants/$TENANT_ID/detections" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {type: .detection_type, confidence: .confidence, severity: .severity}'
```

## Step 6: Provide feedback

If a detection is a false positive or true positive, submit feedback to improve future accuracy:

```bash
curl -s -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/feedback" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "detection_id": "<detection_id>",
    "feedback_type": "true_positive",
    "comment": "Correctly identified the loop"
  }'
```

## Understanding OTEL attributes

PISAMA uses standard OpenTelemetry semantic conventions with `gen_ai.*` extensions:

| Attribute | Description |
|---|---|
| `gen_ai.agent.name` | Name of the agent that produced this span |
| `gen_ai.request.model` | LLM model used |
| `gen_ai.usage.prompt_tokens` | Input tokens consumed |
| `gen_ai.usage.completion_tokens` | Output tokens generated |
| `gen_ai.state` | Agent state as JSON string |
| `gen_ai.prompt` | The prompt sent (optional, for debugging) |
| `gen_ai.completion` | The LLM response (optional, for debugging) |

Framework-specific attributes are also supported:

| Framework | Agent attribute | State attribute |
|---|---|---|
| LangGraph | `langgraph.node.name` | `langgraph.state` |
| CrewAI | `crewai.agent.role` | `crewai.state` |
| AutoGen | `autogen.agent.name` | -- |
| OpenClaw | `openclaw.agent.name` | `openclaw.session.state` |

## Next steps

- [API Reference](../api/reference.md) -- Full endpoint documentation
- [Failure Modes](../concepts/failure-modes.md) -- What PISAMA detects
- [n8n Integration](../guides/integrations/n8n.md) -- Webhook-based ingestion for n8n
- [Detection Tiers](../concepts/detection-tiers.md) -- How tiered escalation works
