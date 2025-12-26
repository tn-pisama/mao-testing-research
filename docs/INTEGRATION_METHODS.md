# Integration Methods Analysis

## Overview

MAO Testing Platform supports multiple integration methods to capture agent traces. This document analyzes each method and provides implementation plans for those not yet built.

## Current Status

| Method | Status | Location |
|--------|--------|----------|
| SDK | ✅ Complete | `/sdk/` |
| HTTP API | ✅ Complete | `POST /api/v1/traces/ingest` |
| OTEL Collector | ❌ Not built | - |
| Auto-instrumentation | ❌ Not built | - |
| Log Ingestion | ❌ Not built | - |
| Webhooks | ❌ Not built | - |

---

## Method 1: Custom SDK (Complete)

**Location:** `/sdk/mao_testing/`

### Pros
- Full control over data capture
- Captures state hashes, agent context, framework-specific attributes
- Type-safe API with good developer experience
- Framework integrations: LangGraph, CrewAI, AutoGen
- Batching, retry, sampling built-in
- Best detection accuracy (95%+)

### Cons
- Requires code changes in user's application
- Maintenance burden tracking framework version changes
- Python-only (currently)
- Adoption friction ("yet another SDK")
- Dependency conflicts possible

### Best For
Teams committed to MAO, want best detection quality

---

## Method 2: HTTP API (Complete)

**Endpoint:** `POST /api/v1/traces/ingest`

### Pros
- Maximum flexibility - works from anywhere
- No dependencies whatsoever
- Easy to test with curl
- Works in constrained environments (edge, serverless)
- Simple to understand

### Cons
- User must understand OTEL span format
- No automatic instrumentation
- Must implement retry, batching, error handling manually
- Easy to get format wrong

### Best For
Custom frameworks, edge cases, polyglot environments

---

## Method 3: OTEL Collector (Planned)

### Description
Accept traces from standard OpenTelemetry Collector configured as an exporter.

### Pros
- Zero new dependencies if already using OTEL
- Collector handles batching, retry, sampling, buffering
- Fan-out to multiple backends (MAO + Jaeger + Datadog)
- Language agnostic (Python, JS, Go, Java, Rust)
- Battle-tested at massive scale
- Enterprises already have OTEL infrastructure

### Cons
- Requires OTEL expertise to configure
- GenAI semantic conventions still evolving
- May miss framework-specific state without custom spans
- Configuration complexity

### Best For
Enterprises with existing observability platforms

### Implementation Plan

```
Phase 1: OTLP Endpoint (2 days)
├── Add OTLP/gRPC endpoint alongside HTTP
├── Support OTLP/HTTP with protobuf
├── Handle both JSON and binary encoding
└── Test with otel-collector

Phase 2: Collector Config Templates (1 day)
├── Create sample collector.yaml configs
├── Document setup for common scenarios
└── Add docker-compose with collector

Phase 3: GenAI Semantic Conventions (1 day)
├── Map gen_ai.* attributes to MAO schema
├── Handle missing attributes gracefully
└── Document required vs optional attributes
```

### Files to Create
- `backend/app/api/v1/otlp.py` - OTLP endpoint
- `deploy/otel-collector/collector.yaml` - Sample config
- `docs/integration/otel-collector.md` - Setup guide

---

## Method 4: Auto-instrumentation (Planned)

### Description
Zero-code instrumentation using OpenTelemetry auto-instrumentors.

### Pros
- Zero code changes required
- Fastest time to first trace (minutes)
- Great for evaluation/POC
- Catches LLM calls automatically

### Cons
- Captures HTTP/LLM calls, not agent state transitions
- Missing: state deltas, agent-to-agent messages
- Detection accuracy limited (~60%)
- Monkey-patching can cause subtle bugs

### Best For
Quick evaluation, proof of concept, demos

### Implementation Plan

```
Phase 1: Instrumentor Package (2 days)
├── Create opentelemetry-instrumentation-mao package
├── Auto-patch LangGraph StateGraph
├── Auto-patch CrewAI Crew.kickoff
├── Auto-patch AutoGen ConversableAgent
└── Inject MAO-specific attributes

Phase 2: CLI Tool (1 day)
├── mao-instrument command wrapper
├── Environment variable configuration
└── Quick start examples

Phase 3: Documentation (0.5 days)
├── Quick start guide
├── What's captured vs missing
└── When to upgrade to SDK
```

### Files to Create
- `sdk/opentelemetry-instrumentation-mao/` - Instrumentor package
- `sdk/mao_testing/cli.py` - CLI wrapper
- `docs/integration/auto-instrumentation.md` - Guide

---

## Method 5: Log Ingestion (Planned)

### Description
Parse structured JSON logs to extract agent behavior.

### Pros
- Works with existing logging infrastructure
- No code changes if structured logs exist
- Can analyze historical data
- Non-invasive approach

### Cons
- Logs lack timing precision
- Missing span relationships and causality
- Hard to reconstruct agent state
- Detection accuracy significantly compromised (~50%)

### Best For
Historical analysis, compliance/audit, legacy systems

### Implementation Plan

```
Phase 1: Log Parser (2 days)
├── JSON log parser with configurable schema
├── Support common formats (structlog, python-json-logger)
├── LangSmith log format support
├── Timestamp normalization
└── Trace ID extraction/generation

Phase 2: Ingestion Endpoint (1 day)
├── POST /api/v1/logs/ingest endpoint
├── Batch processing
├── Async processing queue
└── Deduplication

Phase 3: Connectors (2 days)
├── Fluentd output plugin
├── Vector sink configuration
├── CloudWatch Logs integration
└── Documentation
```

### Files to Create
- `backend/app/ingestion/log_parser.py` - Log parsing logic
- `backend/app/api/v1/logs.py` - Log ingestion endpoint
- `deploy/fluentd/fluent.conf` - Fluentd config
- `docs/integration/log-ingestion.md` - Guide

---

## Method 6: Webhooks/Callbacks (Planned)

### Description
Framework-native callbacks that POST events to MAO.

### Pros
- Framework-native integration
- Rich context provided by framework
- Real-time streaming
- Simple to configure

### Cons
- Must implement separate handler per framework
- No standard format across frameworks
- Can add latency to critical path
- Error handling complexity

### Best For
Single-framework deployments, real-time alerts

### Implementation Plan

```
Phase 1: Webhook Receiver (1 day)
├── POST /api/v1/webhooks/{framework} endpoint
├── Signature verification
├── Async processing
└── Rate limiting

Phase 2: Framework Adapters (3 days)
├── LangSmith callback adapter
├── LangGraph interrupt handler
├── CrewAI step callback
├── AutoGen message hook
└── Generic webhook format

Phase 3: Outbound Webhooks (1 day)
├── Detection alert webhooks
├── Configurable triggers
├── Retry with backoff
└── Slack/Discord/PagerDuty templates
```

### Files to Create
- `backend/app/api/v1/webhooks.py` - Webhook endpoints
- `backend/app/webhooks/adapters/` - Framework adapters
- `backend/app/webhooks/outbound.py` - Alert webhooks
- `docs/integration/webhooks.md` - Guide

---

## Priority Matrix

| Method | Priority | Effort | Impact | Target User |
|--------|----------|--------|--------|-------------|
| OTEL Collector | P1 | 4 days | High | Enterprise |
| Webhooks | P2 | 5 days | Medium | Real-time alerts |
| Auto-instrumentation | P3 | 3.5 days | Medium | Quick start |
| Log Ingestion | P4 | 5 days | Low | Legacy/audit |

---

## Recommended Implementation Order

### Sprint 1: Enterprise Ready (Week 1)
1. OTEL Collector support
2. Collector configuration templates
3. Enterprise documentation

### Sprint 2: Developer Experience (Week 2)
1. Webhook receivers
2. Framework callback adapters
3. Outbound alert webhooks

### Sprint 3: Onboarding (Week 3)
1. Auto-instrumentation package
2. CLI tooling
3. Quick start guide

### Sprint 4: Completeness (Week 4)
1. Log ingestion
2. Fluentd/Vector plugins
3. Historical import tools

---

## Detection Accuracy by Method

| Method | Loop Detection | State Corruption | Persona Drift | Deadlock |
|--------|---------------|------------------|---------------|----------|
| SDK | 95% | 95% | 90% | 85% |
| HTTP API | 95% | 95% | 90% | 85% |
| OTEL Collector | 85% | 80% | 75% | 70% |
| Webhooks | 80% | 75% | 70% | 65% |
| Auto-instrument | 60% | 50% | 40% | 30% |
| Log Ingestion | 50% | 40% | 30% | 20% |

*Accuracy depends on data completeness. SDK/HTTP capture full state; others have gaps.*
