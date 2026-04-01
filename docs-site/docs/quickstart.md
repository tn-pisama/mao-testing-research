# Quickstart

Get Pisama running and detecting failures in under 5 minutes.

## 1. Start Pisama

```bash
git clone https://github.com/tn-pisama/mao-testing-research.git
cd mao-testing-research
docker compose up
```

This starts PostgreSQL (pgvector), Redis, the FastAPI backend on port 8000, and the Next.js frontend on port 3000.

## 2. Verify the setup

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "healthy", "database": "ok", "redis": "ok"}
```

## 3. Create a tenant and get an API key

```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project"}'
```

Save the `api_key` and `tenant_id` from the response.

## 4. Exchange the API key for a JWT token

```bash
export TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "YOUR_API_KEY"}' | jq -r '.access_token')
```

## 5. Send a test trace

```bash
curl -X POST http://localhost:8000/api/v1/tenants/YOUR_TENANT_ID/traces/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "my-agent"}}
        ]
      },
      "scopeSpans": [{
        "spans": [
          {
            "traceId": "abc123",
            "spanId": "span001",
            "name": "agent_step_1",
            "kind": 1,
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000001000000000",
            "attributes": [
              {"key": "gen_ai.agent.name", "value": {"stringValue": "research-agent"}},
              {"key": "gen_ai.request.model", "value": {"stringValue": "claude-sonnet-4"}},
              {"key": "gen_ai.usage.prompt_tokens", "value": {"intValue": 1500}},
              {"key": "gen_ai.usage.completion_tokens", "value": {"intValue": 800}}
            ],
            "status": {"code": 1}
          }
        ]
      }]
    }]
  }'
```

## 6. Run detection

```bash
curl -X POST http://localhost:8000/api/v1/tenants/YOUR_TENANT_ID/traces/abc123/analyze \
  -H "Authorization: Bearer $TOKEN"
```

The response includes all detected failures with confidence scores, severity levels, and suggested fixes.

## 7. Explore the results

Open [http://localhost:3000](http://localhost:3000) and sign in. The sidebar navigation gives you three views into your results:

- **Dashboard** -- Overview with detection counts, cost analytics, and recent issues. This is your main hub.
- **Runs** -- Lists all ingested traces. Click any run to see a waterfall timeline of its execution, a flow graph of the agent steps, and the detections found in that run.
- **Detections** -- Lists every detected failure across all traces. Click a detection to see what happened, the business impact, a suggested fix, and an option to trigger auto-healing.

From the Detection detail page, you can:

- **Trigger Healing** to generate an auto-fix (with approval workflow for high-risk changes)
- **View the trace** to see the exact execution steps that led to the failure
- **Mark as valid or false positive** to improve detection accuracy over time

---

## Next steps

- [Installation guide](getting-started/installation.md) -- Manual setup without Docker
- [Configuration](getting-started/configuration.md) -- Environment variables and tuning
- [Your first trace](getting-started/first-trace.md) -- Detailed trace ingestion tutorial
- [API reference](api/reference.md) -- Full endpoint documentation
- [n8n integration](guides/integrations/n8n.md) -- Connect your n8n workflows
- [LangGraph integration](guides/integrations/langgraph.md) -- Monitor LangGraph apps
