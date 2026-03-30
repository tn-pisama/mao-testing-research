# n8n Integration

Pisama integrates with [n8n](https://n8n.io) to detect failures in AI agent workflows built with the n8n workflow automation platform.

## Why Monitor n8n Workflows?

n8n workflows increasingly incorporate AI/LLM nodes (OpenAI, Anthropic, LangChain). These workflows can exhibit the same failure patterns as code-based agents:

- Infinite loops from workflow retries or circular triggers
- State corruption from data transformation errors
- Hallucinations from bad LLM outputs propagating through nodes
- Token limit exhaustion on AI nodes

## Integration Methods

### Method 1: Webhook (Recommended)

The n8n workflow sends execution data to Pisama after each run. This provides real-time detection and works with both n8n Cloud and self-hosted instances.

**Setup:**

1. Add an HTTP Request node at the end of your n8n workflow
2. Configure it to POST to your Pisama instance:

```
URL: https://your-pisama.com/api/v1/n8n/webhook
Method: POST
Headers:
  X-MAO-API-Key: <your_api_key>
  Content-Type: application/json
Body: {{ $json }}
```

**Webhook payload format:**

```json
{
  "executionId": "123",
  "workflowId": "abc",
  "workflowName": "My AI Workflow",
  "mode": "trigger",
  "startedAt": "2024-01-01T00:00:00Z",
  "finishedAt": "2024-01-01T00:00:05Z",
  "status": "success",
  "data": {
    "resultData": {
      "runData": {
        "OpenAI": [{"data": [...], "executionTime": 1500}],
        "Process": [{"data": [...], "executionTime": 50}]
      }
    }
  }
}
```

**Security:** Webhook requests are verified using HMAC-SHA256 signatures with replay protection:

- `X-MAO-Signature`: HMAC signature of the payload
- `X-MAO-Timestamp`: Unix timestamp (must be within 5 minutes)
- `X-MAO-Nonce`: Unique nonce to prevent replay attacks

### Method 2: API Polling

Pisama polls the n8n API for recent executions. No workflow modifications needed, but requires n8n API credentials.

```bash
# Set environment variables
export N8N_HOST=https://your-n8n-instance.com
export N8N_API_KEY=your_n8n_api_key
```

**Sync historical executions:**

```bash
curl -X POST http://localhost:8000/api/v1/n8n/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**Check sync status:**

```bash
curl http://localhost:8000/api/v1/n8n/sync/status \
  -H "Authorization: Bearer $TOKEN"
```

### Method 3: Workflow Discovery

Pisama can automatically discover workflows from a connected n8n instance:

```bash
curl -X POST http://localhost:8000/api/v1/n8n/discover \
  -H "Authorization: Bearer $TOKEN"
```

## n8n-Specific Detectors

Pisama includes 6 detectors designed specifically for n8n workflows:

| Detector | Key | What It Detects |
|---|---|---|
| Schema Mismatch | `n8n_schema` | Type mismatches between connected nodes |
| Workflow Cycles | `n8n_cycle` | Graph cycles in workflow connections |
| Complexity | `n8n_complexity` | Excessive nodes, branching, cyclomatic complexity |
| Error Handling | `n8n_error` | Missing error handling, unprotected AI nodes |
| Resource Usage | `n8n_resource` | Missing maxTokens, unbounded loops, no timeouts |
| Timeout Risk | `n8n_timeout` | Missing workflow/webhook/AI node timeouts |

These detectors analyze workflow structure (JSON definition) rather than execution behavior.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/n8n/webhook` | Receive execution webhook |
| `POST` | `/api/v1/n8n/workflows` | Register a workflow for monitoring |
| `GET` | `/api/v1/n8n/workflows` | List registered workflows |
| `POST` | `/api/v1/n8n/sync` | Pull historical executions |
| `GET` | `/api/v1/n8n/sync/status` | Get sync status |
| `POST` | `/api/v1/n8n/discover` | Discover workflows from connected instance |
| `GET` | `/api/v1/n8n/stream` | SSE endpoint for real-time updates |

## AI Node Detection

Pisama automatically identifies AI/LLM nodes in n8n workflows and extracts token usage data:

| n8n AI Node Parameter | OTEL Attribute |
|---|---|
| `model` | `gen_ai.request.model` |
| `maxTokens` | `gen_ai.request.max_tokens` |
| `temperature` | `gen_ai.request.temperature` |
| `prompt` / `messages` | `gen_ai.prompt` (truncated) |
| `response` | `gen_ai.completion` (truncated) |

Recognized AI node types:

- `n8n-nodes-base.openAi`
- `n8n-nodes-base.anthropic`
- `n8n-nodes-langchain.agent`
- `n8n-nodes-langchain.chainLlm`
- `@n8n/n8n-nodes-langchain.lmChatOpenAi`
- `@n8n/n8n-nodes-langchain.lmChatAnthropic`

## Real-Time Monitoring

Connect to the SSE stream for live updates:

```bash
curl -N http://localhost:8000/api/v1/n8n/stream \
  -H "Authorization: Bearer $TOKEN"
```

Events include:

- Workflow execution started/completed
- Failure detected during execution
- AI node token usage alerts

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `N8N_HOST` | -- | n8n instance URL for auto-sync |
| `N8N_API_KEY` | -- | n8n API key |
| `N8N_WEBHOOK_MAX_PAYLOAD_MB` | `10` | Maximum webhook payload size |
| `N8N_WEBHOOK_RATE_LIMIT` | `100` | Webhook requests per minute per tenant |
