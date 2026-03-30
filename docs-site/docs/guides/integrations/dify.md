# Dify Integration

Pisama integrates with [Dify](https://dify.ai) to monitor AI application workflows and detect failure modes in Dify-built agents.

## Setup

### Register a Dify Instance

Connect your Dify instance to Pisama:

```bash
curl -X POST http://localhost:8000/api/v1/dify/instances \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-dify",
    "url": "https://my-dify-instance.com",
    "api_key": "your_dify_api_key"
  }'
```

### Register Apps for Monitoring

```bash
curl -X POST http://localhost:8000/api/v1/dify/apps \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "<instance_id>",
    "app_id": "my-chatbot-app",
    "name": "Customer Support Bot"
  }'
```

### Configure Webhook

In your Dify instance, set up a webhook to send workflow execution data to Pisama:

```
Webhook URL: https://your-pisama.com/api/v1/dify/webhook
Method: POST
Headers:
  X-MAO-API-Key: <your_api_key>
```

## Detection Capabilities

Pisama detects the following failure modes in Dify workflows:

- **Hallucination**: LLM nodes generating unsupported claims
- **Loop detection**: Workflow loops and retry storms
- **Context overflow**: Token accumulation across workflow nodes
- **Task derailment**: Agents going off-topic
- **State corruption**: Data transformation errors between nodes
- **Cost tracking**: Token usage and cost per workflow execution

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/dify/webhook` | Receive workflow execution webhook |
| `POST` | `/api/v1/dify/instances` | Register a Dify instance |
| `GET` | `/api/v1/dify/instances` | List registered instances |
| `POST` | `/api/v1/dify/apps` | Register an app for monitoring |
| `GET` | `/api/v1/dify/apps` | List registered apps |
| `GET` | `/api/v1/dify/stream` | SSE endpoint for real-time updates |

## Real-Time Monitoring

Connect to the SSE stream for live Dify execution updates:

```bash
curl -N http://localhost:8000/api/v1/dify/stream \
  -H "Authorization: Bearer $TOKEN"
```
