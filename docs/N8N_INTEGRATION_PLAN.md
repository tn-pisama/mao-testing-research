# n8n Integration Plan

## Overview

Add n8n workflow automation platform integration to MAO Testing Platform for detecting failures in AI agent workflows.

## Why n8n Integration?

n8n is a popular low-code workflow automation tool that increasingly incorporates AI/LLM nodes:
- OpenAI nodes (GPT-4, embeddings)
- Anthropic Claude nodes
- LangChain nodes
- Custom AI agent workflows

These workflows can exhibit the same failure patterns as code-based agents:
- Infinite loops (workflow retries, circular triggers)
- State corruption (data transformation errors)
- AI hallucinations (bad LLM outputs propagating)

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          n8n Instance                            │
│                                                                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│  │ Trigger │───→│ OpenAI  │───→│ Process │───→│ Output  │      │
│  │  Node   │    │  Node   │    │  Node   │    │  Node   │      │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘      │
│       │              │              │              │             │
│       └──────────────┴──────────────┴──────────────┘             │
│                           │                                      │
│              Execution Webhook / Polling                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MAO Testing Platform                          │
│                                                                  │
│  ┌────────────────┐    ┌────────────────┐    ┌───────────────┐  │
│  │ n8n Webhook    │───→│ Trace Parser   │───→│ Detection     │  │
│  │ Receiver       │    │ (n8n → OTEL)   │    │ Engine        │  │
│  └────────────────┘    └────────────────┘    └───────────────┘  │
│                                                                  │
│  ┌────────────────┐                                              │
│  │ n8n Poller     │ (Alternative: poll n8n API for executions)  │
│  └────────────────┘                                              │
└──────────────────────────────────────────────────────────────────┘
```

## Integration Methods

### Method 1: Webhook-Based (Recommended)

n8n workflow sends execution data to MAO after each run.

**Pros:**
- Real-time detection
- No n8n API credentials needed
- Works with n8n Cloud and self-hosted

**Cons:**
- Requires modifying n8n workflows
- User must add MAO webhook node

### Method 2: API Polling

MAO polls n8n's API for recent executions.

**Pros:**
- No workflow modifications needed
- Can import historical executions

**Cons:**
- Requires n8n API credentials
- Not real-time (polling interval)
- Only works with n8n instances exposing API

### Method 3: n8n Community Node (Future)

Publish a dedicated `n8n-nodes-mao-testing` package.

**Pros:**
- Best UX for n8n users
- Native integration

**Cons:**
- Requires n8n node development
- Maintenance burden

## Implementation Plan

### Phase 1: Webhook Receiver (Backend)

Add endpoint to receive n8n execution webhooks.

```python
# backend/app/api/v1/n8n.py

@router.post("/n8n/webhook/{tenant_id}")
async def receive_n8n_execution(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive n8n workflow execution data.
    
    n8n workflow should have a final HTTP Request node that POSTs to:
    POST /api/v1/n8n/webhook/{tenant_id}
    
    Headers:
      X-MAO-API-Key: <api_key>
      Content-Type: application/json
    
    Body: n8n execution data (see N8nExecutionPayload)
    """
```

### Phase 2: Execution Parser

Convert n8n execution format to MAO trace format.

```python
# backend/app/ingestion/n8n_parser.py

@dataclass
class N8nNode:
    name: str
    type: str  # e.g., "n8n-nodes-base.openAi", "n8n-nodes-langchain.agent"
    parameters: Dict[str, Any]
    execution_time_ms: int
    output: Any
    error: Optional[str]

@dataclass
class N8nExecution:
    id: str
    workflow_id: str
    workflow_name: str
    mode: str  # "manual", "trigger", "webhook"
    started_at: datetime
    finished_at: datetime
    status: str  # "success", "error", "waiting"
    nodes: List[N8nNode]

class N8nParser:
    """Parse n8n execution data into MAO traces."""
    
    AI_NODE_TYPES = [
        "n8n-nodes-base.openAi",
        "n8n-nodes-base.anthropic", 
        "n8n-nodes-langchain.agent",
        "n8n-nodes-langchain.chainLlm",
        "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "@n8n/n8n-nodes-langchain.lmChatAnthropic",
    ]
    
    def parse(self, execution: N8nExecution) -> ParsedTrace:
        """Convert n8n execution to MAO trace format."""
        spans = []
        
        for node in execution.nodes:
            span = self._node_to_span(node, execution.id)
            spans.append(span)
            
            # Extract AI-specific data for AI nodes
            if self._is_ai_node(node):
                span.attributes["gen_ai.system"] = self._get_ai_system(node)
                span.attributes["gen_ai.request.model"] = node.parameters.get("model")
                span.attributes["gen_ai.usage.prompt_tokens"] = self._extract_tokens(node, "prompt")
                span.attributes["gen_ai.usage.completion_tokens"] = self._extract_tokens(node, "completion")
        
        return ParsedTrace(
            trace_id=execution.id,
            framework="n8n",
            spans=spans,
        )
```

### Phase 3: AI Node Detection

Identify and analyze AI/LLM nodes in n8n workflows.

```python
# backend/app/detection/n8n_ai.py

class N8nAIDetector:
    """Detect AI-specific failures in n8n workflows."""
    
    def detect_loop(self, execution: N8nExecution) -> Optional[Detection]:
        """Detect execution loops (workflow triggered multiple times rapidly)."""
        # Check for rapid re-executions of same workflow
        
    def detect_ai_errors(self, node: N8nNode) -> List[Detection]:
        """Detect AI node failures."""
        detections = []
        
        # Rate limit errors
        if "rate limit" in str(node.error).lower():
            detections.append(Detection(type="rate_limit", node=node.name))
        
        # Token limit exceeded
        if "token" in str(node.error).lower() and "limit" in str(node.error).lower():
            detections.append(Detection(type="token_limit", node=node.name))
        
        # Hallucination indicators (JSON parse errors from structured output)
        if node.type in self.AI_NODE_TYPES:
            if self._output_parse_failed(node):
                detections.append(Detection(type="output_parse_error", node=node.name))
        
        return detections
```

### Phase 4: SDK Integration

Python SDK for instrumenting n8n API calls.

```python
# sdk/mao_testing/integrations/n8n.py

class N8nTracer(BaseFrameworkTracer):
    """Tracer for n8n workflow executions."""
    
    FRAMEWORK_NAME = "n8n"
    FRAMEWORK_VERSION = "1.x"
    
    def __init__(self, n8n_url: str, api_key: str, **kwargs):
        super().__init__(**kwargs)
        self.n8n_url = n8n_url
        self.api_key = api_key
    
    async def poll_executions(self, since: datetime) -> List[N8nExecution]:
        """Poll n8n API for recent executions."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.n8n_url}/api/v1/executions",
                headers={"X-N8N-API-KEY": self.api_key},
                params={"startedAfter": since.isoformat()},
            )
            return [N8nExecution(**e) for e in resp.json()["data"]]
    
    async def import_execution(self, execution_id: str) -> Trace:
        """Import a specific execution as a trace."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.n8n_url}/api/v1/executions/{execution_id}",
                headers={"X-N8N-API-KEY": self.api_key},
            )
            execution = N8nExecution(**resp.json())
            return self._execution_to_trace(execution)
```

## Data Model (Updated per Agent Feedback)

### CRITICAL: Tenant Context Validation
All n8n data MUST be validated against tenant context:

```python
async def validate_tenant_context(
    tenant_id: str,
    workflow_id: str,
    db: AsyncSession
) -> bool:
    """Validate workflow belongs to tenant."""
    # Check if workflow is registered for this tenant
    result = await db.execute(
        select(N8nWorkflow).where(
            N8nWorkflow.tenant_id == UUID(tenant_id),
            N8nWorkflow.workflow_id == workflow_id,
        )
    )
    if not result.scalar_one_or_none():
        # Auto-register new workflows (first-use pattern)
        await db.execute(
            insert(N8nWorkflow).values(
                tenant_id=UUID(tenant_id),
                workflow_id=workflow_id,
                registered_at=datetime.utcnow(),
            )
        )
        await db.commit()
    return True
```

### n8n Execution → MAO Trace Mapping (Corrected)

| n8n Field | MAO Field | Notes |
|-----------|-----------|-------|
| `execution.id` | `trace.session_id` | Must be unique per tenant |
| `execution.workflowId` | `trace.metadata.workflow_id` | Validated against tenant |
| `execution.workflowName` | `trace.metadata.workflow_name` | |
| `execution.mode` | `trace.metadata.trigger_mode` | |
| `node.name` | `state.agent_id` | |
| `node.type` | `state.metadata.node_type` | |
| `node.executionTime` | `state.latency_ms` | Convert to int |
| `node.data` | `state.state_delta` | Redact sensitive data |
| `tenant_id` | `trace.tenant_id` | **REQUIRED** - from auth |
| `tenant_id` | `state.tenant_id` | **REQUIRED** - from auth |

### State Hash Algorithm (per backend-architect)
Use SHA-256 truncated to 16 chars (matching existing `otel.py:_compute_hash`):

```python
def compute_state_hash(state_delta: dict) -> str:
    """Compute deterministic hash of state delta."""
    normalized = json.dumps(state_delta, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
```

### AI Node Attribute Mapping

| n8n AI Node Parameter | OTEL Semantic Convention |
|----------------------|--------------------------|
| `model` | `gen_ai.request.model` |
| `maxTokens` | `gen_ai.request.max_tokens` |
| `temperature` | `gen_ai.request.temperature` |
| `prompt` / `messages` | `gen_ai.prompt` (truncated) |
| `response` | `gen_ai.completion` (truncated) |

## API Endpoints

### Webhook Receiver

```
POST /api/v1/n8n/webhook/{tenant_id}
Headers:
  X-MAO-API-Key: <api_key>
  Content-Type: application/json

Body:
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

### Execution Import (SDK)

```
POST /api/v1/n8n/import
Headers:
  Authorization: Bearer <jwt>
  Content-Type: application/json

Body:
{
  "n8n_url": "https://my-n8n.example.com",
  "n8n_api_key": "...",
  "execution_ids": ["123", "456"]
}
```

## Security Considerations (Updated per Agent Feedback)

### CRITICAL: HMAC Signature Verification
Webhook requests MUST include HMAC-SHA256 signature to prevent spoofing:

```python
# backend/app/core/n8n_security.py

import hmac
import hashlib
from fastapi import HTTPException

def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    timestamp: str,
) -> bool:
    """Verify n8n webhook HMAC signature with replay protection."""
    # Check timestamp freshness (5 minute window)
    import time
    ts = int(timestamp)
    if abs(time.time() - ts) > 300:
        raise HTTPException(status_code=401, detail="Webhook timestamp expired")
    
    # Compute expected signature
    message = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    return True
```

### CRITICAL: SSRF Prevention for n8n URL
User-provided n8n URLs MUST be validated against allowlist:

```python
# backend/app/core/n8n_security.py

import urllib.parse
from ipaddress import ip_address

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
BLOCKED_PORTS = {22, 25, 445, 3306, 5432, 6379, 27017}  # SSH, SMTP, SMB, DBs

def validate_n8n_url(url: str) -> str:
    """Validate n8n URL to prevent SSRF attacks."""
    parsed = urllib.parse.urlparse(url)
    
    # Only allow HTTPS
    if parsed.scheme != "https":
        raise ValueError("n8n URL must use HTTPS")
    
    # Block internal hosts
    hostname = parsed.hostname.lower()
    if hostname in BLOCKED_HOSTS:
        raise ValueError("Internal hosts not allowed")
    
    # Block private IP ranges
    try:
        ip = ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved:
            raise ValueError("Private/internal IPs not allowed")
    except ValueError:
        pass  # Not an IP, hostname is ok
    
    # Block dangerous ports
    port = parsed.port or 443
    if port in BLOCKED_PORTS:
        raise ValueError(f"Port {port} not allowed")
    
    return url
```

### HIGH: Replay Attack Protection
Use timestamp + nonce to prevent replay attacks:

```python
# Track used nonces (Redis or DB)
async def check_replay(nonce: str, timestamp: int, db: AsyncSession) -> bool:
    """Check if webhook has been replayed."""
    # Store nonces with TTL matching timestamp window
    existing = await db.execute(
        select(WebhookNonce).where(WebhookNonce.nonce == nonce)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Replay detected")
    
    # Store nonce
    await db.execute(
        insert(WebhookNonce).values(nonce=nonce, timestamp=timestamp)
    )
    await db.commit()
    return True
```

### HIGH: Sensitive Data Redaction
Redact prompts/responses before storage:

```python
def redact_sensitive_data(node_data: dict) -> dict:
    """Redact PII and secrets from n8n node data."""
    sensitive_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # emails
        r'\bsk-[a-zA-Z0-9]{32,}\b',  # OpenAI keys
        r'\bxai-[a-zA-Z0-9]{32,}\b',  # Grok keys
    ]
    # Truncate and hash prompts/responses
    if "prompt" in node_data:
        node_data["prompt_hash"] = hashlib.sha256(
            node_data.pop("prompt").encode()
        ).hexdigest()[:16]
    return node_data
```

### Original Security Requirements
1. **API Key Validation**: Validate MAO API key on webhook requests
2. **n8n Credentials**: Store n8n API keys encrypted (for polling mode)
3. **Payload Size Limits**: Limit webhook payload size (max 10MB)
4. **Rate Limiting**: Rate limit webhook endpoint per tenant
5. **Input Validation**: Validate n8n execution payload schema

## Detection Capabilities

| Failure Type | Detection Method |
|--------------|------------------|
| Infinite Loop | Rapid re-executions of same workflow |
| Rate Limit Errors | AI node error message parsing |
| Token Limit Exceeded | AI node error + token count analysis |
| Output Parse Errors | JSON/schema validation failures |
| Timeout | Execution time > threshold |
| Node Failures | Error status on any node |
| Workflow Errors | Execution status = "error" |

## File Structure

```
backend/app/
├── api/v1/
│   └── n8n.py              # Webhook endpoint
├── ingestion/
│   └── n8n_parser.py       # Execution parser
├── detection/
│   └── n8n_ai.py           # AI node detection
└── integrations/
    └── n8n.py              # n8n API client

sdk/mao_testing/
└── integrations/
    └── n8n.py              # SDK tracer
```

## Environment Variables

```bash
# Optional: Default n8n instance for polling
N8N_DEFAULT_URL=https://n8n.example.com
N8N_DEFAULT_API_KEY=<encrypted>

# Webhook settings
N8N_WEBHOOK_MAX_PAYLOAD_MB=10
N8N_WEBHOOK_RATE_LIMIT=100  # per minute per tenant
```

## Testing Strategy

1. **Unit Tests**: Parser, detector, API client
2. **Integration Tests**: Webhook endpoint with sample payloads
3. **E2E Tests**: Full flow with mock n8n execution data

## Success Criteria

- [ ] Webhook endpoint receives n8n executions
- [ ] Executions parsed to MAO trace format
- [ ] AI nodes identified and attributed correctly
- [ ] Loop detection works for rapid re-executions
- [ ] Error detection works for AI node failures
- [ ] SDK can poll n8n API for executions
- [ ] Tests pass

## Timeline

| Phase | Tasks | Duration |
|-------|-------|----------|
| 1 | Webhook endpoint + basic parser | 2 hours |
| 2 | AI node detection + attribution | 2 hours |
| 3 | SDK integration (polling) | 2 hours |
| 4 | Tests + documentation | 1 hour |

**Total: ~7 hours**
