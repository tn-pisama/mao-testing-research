<div align="center">

# PISAMA

**Multi-agent failure detection and self-healing for production AI systems.**

[![Build Status](https://img.shields.io/github/actions/workflow/status/pisama/pisama/ci.yml?branch=main&style=flat-square)](https://github.com/pisama/pisama/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg?style=flat-square)](https://pypi.org/project/pisama/)
[![Documentation](https://img.shields.io/badge/docs-pisama.com-8b5cf6.svg?style=flat-square)](https://docs.pisama.com)

</div>

---

PISAMA monitors multi-agent AI systems in real time, detects 42 distinct failure modes across 8 categories, and applies targeted self-healing to keep your agents on track. Built on the [MAST taxonomy](https://docs.pisama.com/mast) (Multi-Agent System Testing), it works with any framework through OpenTelemetry-native trace ingestion.

- **42 calibrated detectors** covering loops, state corruption, persona drift, hallucination, prompt injection, coordination failures, and more -- with F1 scores from 0.667 to 1.000.
- **Self-healing engine** that rolls back corrupted state, retries failed handoffs, and suggests code-level fixes -- all with checkpoint safety and approval policies.
- **Framework-agnostic** integration via a Python SDK, OTEL spans, or webhook ingestion. Drop in alongside your existing observability stack.
- **Cost-aware by design** with tiered detection (hash, delta, embeddings, LLM judge) that keeps per-trace cost under $0.05.

## Quick Start

```bash
pip install pisama
```

```python
from pisama import PisamaClient

client = PisamaClient(api_key="ps_...")

# Analyze a multi-agent trace
result = client.analyze(trace_id="abc-123")

for failure in result.failures:
    print(f"[{failure.type}] {failure.summary} (confidence: {failure.confidence:.0%})")
    print(f"  Fix: {failure.suggested_fix}")
```

## Supported Frameworks

| Framework | Integration | Status |
|-----------|-------------|--------|
| LangGraph | `pisama.integrations.langgraph` | GA |
| CrewAI | `pisama.integrations.crewai` | GA |
| AutoGen | `pisama.integrations.autogen` | GA |
| Claude Code | OTEL exporter | GA |
| n8n | Webhook node | GA |
| Dify | Webhook | GA |
| OpenClaw | `pisama.integrations.openclaw` | Beta |

All integrations produce standard OpenTelemetry spans with `gen_ai.*` semantic conventions. Any OTEL-compatible framework can send traces to PISAMA without a dedicated adapter.

## Detection Capabilities

PISAMA organizes its 42 detectors into 8 categories based on the MAST taxonomy:

| Category | Example Failures | Detectors |
|----------|-----------------|-----------|
| **Agent Coordination** | Deadlocked handoffs, message loss, role confusion | 5 |
| **State Integrity** | State corruption, context neglect, information withholding | 5 |
| **Task Execution** | Infinite loops, premature completion, workflow deviation | 6 |
| **Output Quality** | Hallucination, specification mismatch, persona drift | 6 |
| **Security** | Prompt injection, role usurpation, data exfiltration | 4 |
| **Resource Management** | Context overflow, token budget exhaustion, cost spikes | 4 |
| **Retrieval & Grounding** | Source misattribution, retrieval quality degradation | 4 |
| **Communication** | Task derailment, decomposition failures, goal drift | 8 |

Each detector goes through a five-tier escalation pipeline, starting with fast heuristics and escalating to an LLM judge only when needed:

```
Tier 1 (Hash)  -->  Tier 2 (State Delta)  -->  Tier 3 (Embeddings)  -->  Tier 4 (LLM Judge)  -->  Tier 5 (Human)
  ~0ms                  ~1ms                      ~10ms                     ~200ms                  async
```

## Architecture

```
                          ┌─────────────────────────────────────┐
                          │            PISAMA Cloud              │
                          │         (or self-hosted)             │
                          ├─────────────────────────────────────┤
                          │                                     │
  Traces (OTEL/Webhook)   │  ┌───────────┐   ┌──────────────┐  │
 ─────────────────────────▶  │ Ingestion │──▶│  Detection   │  │
                          │  │ Pipeline  │   │  Engine      │  │
                          │  └───────────┘   │  (42 detectors)│ │
                          │                  └──────┬───────┘  │
                          │                         │          │
                          │                         ▼          │
  Dashboard (Next.js)     │  ┌───────────┐   ┌──────────────┐  │
 ◀─────────────────────────  │  Storage  │◀──│ Self-Healing │  │
                          │  │ Postgres  │   │ Engine       │  │
                          │  │ + pgvector│   └──────────────┘  │
  SDK / API               │  └───────────┘                     │
 ◀─────────────────────────                                    │
                          │       ┌──────────────────┐         │
                          │       │  Fixes Generator │         │
                          │       │  (AI-powered)    │         │
                          │       └──────────────────┘         │
                          └─────────────────────────────────────┘
```

**Backend**: FastAPI + PostgreSQL + pgvector | **Frontend**: Next.js | **SDK**: Python

## Self-Healing

When PISAMA detects a failure, the self-healing engine can automatically intervene. It creates a checkpoint of the current agent state, applies a targeted fix (retry a handoff, roll back corrupted state, re-route a stalled workflow), and verifies the outcome before releasing control. High-risk fixes require explicit approval through configurable policies. Every healing action is logged as an OTEL span so you can audit exactly what happened and why.

## Documentation

| Resource | Link |
|----------|------|
| Getting Started | [docs.pisama.com/quickstart](https://docs.pisama.com/quickstart) |
| API Reference | [docs.pisama.com/api](https://docs.pisama.com/api) |
| Python SDK | [docs.pisama.com/sdk](https://docs.pisama.com/sdk) |
| MAST Taxonomy | [docs.pisama.com/mast](https://docs.pisama.com/mast) |
| Self-Healing Guide | [docs.pisama.com/healing](https://docs.pisama.com/healing) |
| Detector Reference | [docs.pisama.com/detectors](https://docs.pisama.com/detectors) |

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

```bash
# Development setup
git clone https://github.com/pisama/pisama.git
cd pisama
cp .env.example .env
docker compose up -d          # PostgreSQL + pgvector
pip install -e ".[dev]"
pytest backend/tests/
```

## License

MIT. See [LICENSE](LICENSE) for details.
