# Integration Methods Implementation Plan

## Executive Summary

4 integration methods remain to be implemented. Total effort: ~17.5 days across 4 sprints.

| Method | Effort | Priority | Sprint |
|--------|--------|----------|--------|
| OTEL Collector | 4 days | P1 | 1 |
| Webhooks | 5 days | P2 | 2 |
| Auto-instrumentation | 3.5 days | P3 | 3 |
| Log Ingestion | 5 days | P4 | 4 |

---

## Sprint 1: OTEL Collector (P1 - Enterprise)

**Goal:** Enable enterprises with existing OTEL infrastructure to send traces without SDK.

### Day 1-2: OTLP Endpoint

**Files:**
```
backend/app/api/v1/otlp.py
backend/app/ingestion/otlp_parser.py
```

**Tasks:**
- [ ] Add OTLP/HTTP endpoint (`POST /v1/traces`)
- [ ] Support protobuf and JSON encoding
- [ ] Parse ExportTraceServiceRequest format
- [ ] Map to existing OTELParser flow
- [ ] Add authentication header support
- [ ] Write tests with sample OTLP payloads

**Acceptance:**
```bash
# Should work with standard OTEL exporter
otel-cli exec --endpoint http://localhost:8000/v1/traces "echo test"
```

### Day 3: Collector Config Templates

**Files:**
```
deploy/otel-collector/
├── collector.yaml           # Basic config
├── collector-k8s.yaml       # Kubernetes config
├── collector-docker.yaml    # Docker Compose config
└── README.md
```

**Tasks:**
- [ ] Create collector.yaml with MAO exporter
- [ ] Add processors: batch, memory_limiter
- [ ] Add receivers: otlp, prometheus (optional)
- [ ] Docker Compose with collector + MAO backend
- [ ] Kubernetes manifest with collector DaemonSet

**Acceptance:**
```bash
docker-compose -f deploy/otel-collector/docker-compose.yaml up
# Traces flow through collector to MAO
```

### Day 4: GenAI Semantic Conventions

**Files:**
```
backend/app/ingestion/genai_conventions.py
docs/integration/otel-collector.md
```

**Tasks:**
- [ ] Map all gen_ai.* attributes (per OTEL GenAI semconv)
- [ ] Handle llm.* legacy attributes
- [ ] Graceful degradation for missing attributes
- [ ] Document required vs optional attributes
- [ ] Integration guide with examples

**Semantic Conventions to Support:**
```
gen_ai.system              → framework
gen_ai.operation.name      → span name
gen_ai.request.model       → model info
gen_ai.usage.input_tokens  → token count
gen_ai.usage.output_tokens → token count
gen_ai.response.id         → response tracking
```

---

## Sprint 2: Webhooks (P2 - Real-time)

**Goal:** Enable framework callbacks and outbound alerting.

### Day 1: Webhook Receiver Endpoint

**Files:**
```
backend/app/api/v1/webhooks.py
backend/app/webhooks/__init__.py
backend/app/webhooks/receiver.py
```

**Tasks:**
- [ ] `POST /api/v1/webhooks/{source}` endpoint
- [ ] HMAC signature verification
- [ ] Rate limiting per source
- [ ] Async queue for processing
- [ ] Idempotency key support

### Day 2-3: Framework Adapters

**Files:**
```
backend/app/webhooks/adapters/
├── __init__.py
├── langsmith.py      # LangSmith callback format
├── langgraph.py      # LangGraph interrupt events
├── crewai.py         # CrewAI step callbacks
└── autogen.py        # AutoGen message hooks
```

**Tasks:**
- [ ] LangSmith run format adapter
- [ ] LangGraph state transition adapter
- [ ] CrewAI task completion adapter
- [ ] AutoGen conversation adapter
- [ ] Generic JSON webhook adapter

**LangSmith Format Example:**
```json
{
  "run_id": "...",
  "parent_run_id": "...",
  "name": "agent_node",
  "run_type": "chain",
  "inputs": {...},
  "outputs": {...},
  "start_time": "...",
  "end_time": "..."
}
```

### Day 4: Outbound Webhooks

**Files:**
```
backend/app/webhooks/outbound.py
backend/app/webhooks/templates/
├── slack.py
├── pagerduty.py
└── generic.py
```

**Tasks:**
- [ ] Webhook subscription model (DB)
- [ ] Detection event triggers
- [ ] Retry with exponential backoff
- [ ] Slack message template
- [ ] PagerDuty incident template
- [ ] Generic JSON template

### Day 5: Documentation

**Files:**
```
docs/integration/webhooks.md
docs/integration/alerting.md
```

**Tasks:**
- [ ] Inbound webhook setup guide
- [ ] Framework-specific examples
- [ ] Outbound alerting configuration
- [ ] Security best practices

---

## Sprint 3: Auto-instrumentation (P3 - Quick Start)

**Goal:** Zero-code instrumentation for fastest time-to-value.

### Day 1-2: Instrumentor Package

**Files:**
```
sdk/opentelemetry-instrumentation-mao/
├── pyproject.toml
├── src/
│   └── opentelemetry_instrumentation_mao/
│       ├── __init__.py
│       ├── instrumentor.py
│       ├── langgraph.py
│       ├── crewai.py
│       └── autogen.py
└── tests/
```

**Tasks:**
- [ ] Create package structure
- [ ] LangGraph StateGraph.compile() patch
- [ ] LangGraph node execution wrapper
- [ ] CrewAI Crew.kickoff() patch
- [ ] AutoGen ConversableAgent patch
- [ ] Inject MAO-specific span attributes
- [ ] State extraction where possible

**Patching Strategy:**
```python
# Wrap LangGraph node functions
original_invoke = StateGraph.compile
def patched_compile(self, *args, **kwargs):
    graph = original_invoke(self, *args, **kwargs)
    return InstrumentedGraph(graph, tracer)
```

### Day 3: CLI Tool

**Files:**
```
sdk/mao_testing/cli.py
sdk/mao_testing/scripts/mao_instrument.py
```

**Tasks:**
- [ ] `mao-instrument` CLI command
- [ ] Environment variable configuration
- [ ] `mao-instrument python app.py` wrapper
- [ ] `mao-instrument --list` show instrumentations
- [ ] Quick validation command

**Usage:**
```bash
# Auto-instrument and run
mao-instrument --endpoint https://mao.example.com python my_agent.py

# Or via environment
export MAO_ENDPOINT=https://mao.example.com
mao-instrument python my_agent.py
```

### Day 3.5: Documentation

**Files:**
```
docs/integration/auto-instrumentation.md
docs/quickstart.md (update)
```

**Tasks:**
- [ ] Quick start guide (5-minute setup)
- [ ] What's captured vs what's missing
- [ ] When to upgrade to full SDK
- [ ] Troubleshooting guide

---

## Sprint 4: Log Ingestion (P4 - Legacy)

**Goal:** Extract traces from existing structured logs.

### Day 1-2: Log Parser

**Files:**
```
backend/app/ingestion/log_parser.py
backend/app/ingestion/log_formats/
├── __init__.py
├── structlog.py
├── json_logger.py
├── langsmith.py
└── custom.py
```

**Tasks:**
- [ ] Generic JSON log parser
- [ ] Configurable field mappings
- [ ] structlog format support
- [ ] python-json-logger format
- [ ] LangSmith export format
- [ ] Timestamp normalization (multiple formats)
- [ ] Trace ID extraction/generation
- [ ] Session correlation logic

**Field Mapping Config:**
```yaml
formats:
  structlog:
    trace_id: "trace_id"
    span_id: "span_id"
    agent_id: "agent"
    timestamp: "timestamp"
    message: "event"
    state: "state"
```

### Day 3: Ingestion Endpoint

**Files:**
```
backend/app/api/v1/logs.py
backend/app/workers/log_processor.py
```

**Tasks:**
- [ ] `POST /api/v1/logs/ingest` endpoint
- [ ] Batch upload support (JSONL)
- [ ] Async processing queue (Redis/SQS)
- [ ] Deduplication by log hash
- [ ] Progress tracking for large imports
- [ ] Rate limiting

**API:**
```bash
# Single log
POST /api/v1/logs/ingest
{"timestamp": "...", "agent": "researcher", "event": "step_complete", ...}

# Batch (JSONL)
POST /api/v1/logs/ingest/batch
Content-Type: application/x-ndjson
{"timestamp": "...", ...}
{"timestamp": "...", ...}
```

### Day 4-5: Connectors

**Files:**
```
deploy/fluentd/
├── fluent.conf
├── Dockerfile
└── README.md

deploy/vector/
├── vector.toml
└── README.md

docs/integration/log-ingestion.md
```

**Tasks:**
- [ ] Fluentd output plugin configuration
- [ ] Vector sink configuration
- [ ] CloudWatch Logs subscription filter
- [ ] S3 bucket import script
- [ ] Historical import CLI tool
- [ ] Documentation with examples

**Fluentd Config:**
```
<match agent.**>
  @type http
  endpoint https://mao.example.com/api/v1/logs/ingest/batch
  headers {"Authorization": "Bearer ${MAO_API_KEY}"}
  json_array true
</match>
```

---

## Definition of Done

Each integration method is complete when:

1. **Functional:** Traces flow from source to detection
2. **Tested:** Unit tests + integration test with sample data
3. **Documented:** Setup guide with working examples
4. **Validated:** Detection algorithms produce results on ingested data

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| OTEL semconv changes | Pin to specific version, document |
| Framework breaking changes | Version detection, graceful degradation |
| Webhook reliability | Retry queue, dead letter handling |
| Log format variations | Configurable parsers, validation |

---

## Success Metrics

| Method | Success Metric | Target |
|--------|---------------|--------|
| OTEL Collector | Enterprise adoption | 3 pilots |
| Webhooks | Alert delivery rate | 99.9% |
| Auto-instrumentation | Time to first trace | < 5 min |
| Log Ingestion | Historical import volume | 1M logs/hr |
