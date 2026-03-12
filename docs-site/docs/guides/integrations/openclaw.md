# OpenClaw Integration

PISAMA integrates with [OpenClaw](https://openclaw.dev) to monitor agent sessions and detect failure modes in OpenClaw-built multi-agent systems.

## Setup

### Register an OpenClaw Instance

```bash
curl -X POST http://localhost:8000/api/v1/openclaw/instances \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-openclaw",
    "url": "https://my-openclaw-instance.com"
  }'
```

### Register Agents

```bash
curl -X POST http://localhost:8000/api/v1/openclaw/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "<instance_id>",
    "agent_id": "research-agent",
    "name": "Research Agent"
  }'
```

### Configure Webhook

Set up your OpenClaw instance to send session data to PISAMA:

```
Webhook URL: https://your-pisama.com/api/v1/openclaw/webhook
Method: POST
Headers:
  X-MAO-API-Key: <your_api_key>
```

## OpenClaw-Specific Attributes

PISAMA recognizes OpenClaw OTEL attributes:

| OTEL Attribute | Description |
|---|---|
| `openclaw.agent.name` | Agent identifier |
| `openclaw.session.state` | Current session state |
| `openclaw.session.id` | Session identifier |

## Detection Capabilities

When monitoring OpenClaw agents, PISAMA detects:

- **Coordination failures**: Agent handoff and communication issues
- **Persona drift**: Agents deviating from their assigned roles
- **Loop detection**: Agents stuck in repeated action patterns
- **State corruption**: Session state anomalies
- **Hallucination**: Unsupported claims in agent outputs
- **Context overflow**: Token accumulation across agent turns

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/openclaw/webhook` | Receive agent session webhook |
| `POST` | `/api/v1/openclaw/instances` | Register an instance |
| `GET` | `/api/v1/openclaw/instances` | List instances |
| `POST` | `/api/v1/openclaw/agents` | Register an agent |
| `GET` | `/api/v1/openclaw/agents` | List agents |
| `GET` | `/api/v1/openclaw/stream` | SSE for real-time updates |
