<div align="center">

# Pisama

**Find and fix failures in AI agent systems. No LLM calls required.**

[![PyPI](https://img.shields.io/pypi/v/pisama?style=flat-square&color=blue)](https://pypi.org/project/pisama/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg?style=flat-square)](https://pypi.org/project/pisama/)

</div>

---

## Benchmark Results

Pisama's heuristic detectors outperform frontier LLMs on agent failure detection — at zero cost per trace.

**[TRAIL Benchmark](https://arxiv.org/abs/2505.08638)** — Trace-level failure detection (148 traces, 841 errors):

| Method | Joint Accuracy | Cost |
|--------|---------------|------|
| Gemini 2.5 Pro | 11.0% | $$$ |
| OpenAI o3 | 9.2% | $$$ |
| Claude 3.7 Sonnet | 4.7% | $$$ |
| **Pisama (heuristic)** | **60.1%** | **$0** |

100% precision — zero false positives across all categories.

**[Who&When Benchmark](https://arxiv.org/abs/2505.00212)** (ICML 2025) — Multi-agent failure attribution:

| Method | Agent Accuracy | Step Accuracy | Cost/case |
|--------|---------------|---------------|-----------|
| o1 all-at-once | 53.5% | 14.2% | $$$ |
| GPT-4o | 44.9% | 8.7% | $$ |
| **Pisama + Sonnet 4** | **60.3%** | **24.1%** | **$0.02** |
| Pisama heuristic-only | 31.0% | 16.8% | $0 |

## Quick Start

```bash
pip install pisama
```

```python
from pisama import analyze

result = analyze("trace.json")

for issue in result.issues:
    print(f"[{issue.type}] {issue.summary} (severity: {issue.severity})")
    print(f"  {issue.recommendation}")
```

### CLI

```bash
# Analyze a trace file
pisama analyze trace.json

# Watch a running agent for failures
pisama watch python my_agent.py

# Re-run detection on a stored trace
pisama replay <trace-id>

# Batch test recent traces
pisama smoke-test --last 50

# List available detectors
pisama detectors
```

### MCP Server (Cursor / Claude Desktop)

```json
{
  "mcpServers": {
    "pisama": {
      "command": "pisama",
      "args": ["mcp-server"]
    }
  }
}
```

No API key needed. Runs locally.

## How It Works

Pisama uses a tiered detection pipeline. Fast heuristics handle 90%+ of detections at zero cost. LLM judges escalate only when needed.

```
Tier 1 (Hash)    Tier 2 (Delta)    Tier 3 (Embeddings)    Tier 4 (LLM Judge)    Tier 5 (Human)
  ~0ms              ~1ms               ~10ms                  ~200ms               async
  $0                $0                 $0                     ~$0.02               --
```

### 18 Failure Detectors

| Detector | What It Catches |
|----------|----------------|
| `loop` | Infinite loops, retry storms, stuck patterns |
| `coordination` | Deadlocked handoffs, message storms, agent dominance |
| `hallucination` | Factual errors, fabricated tool results |
| `injection` | Prompt injection, jailbreak attempts |
| `corruption` | State corruption, type drift, invalid transitions |
| `persona` | Persona drift, role confusion |
| `derailment` | Task deviation, goal drift |
| `context` | Context neglect, ignored instructions |
| `specification` | Output vs. requirement mismatch |
| `communication` | Inter-agent message breakdown |
| `decomposition` | Poor task breakdown, circular dependencies |
| `workflow` | Unreachable nodes, missing error handling |
| `completion` | Premature completion claims, unfinished work |
| `withholding` | Suppressed findings, hidden errors |
| `convergence` | Metric plateau, regression, thrashing |
| `overflow` | Context window exhaustion |
| `cost` | Token budget overrun |
| `repetition` | Tool dominance, low diversity |

All detectors are available on the free tier. No feature gating.

## Supported Frameworks

Works with any framework that produces OpenTelemetry spans. Native adapters for:

| Framework | Integration | Status |
|-----------|-------------|--------|
| LangGraph | SDK adapter | GA |
| CrewAI | SDK adapter | GA |
| AutoGen | SDK adapter | GA |
| Claude Code | OTEL + MCP | GA |
| n8n | Webhook | GA |
| Dify | Webhook | GA |
| OpenClaw | SDK adapter | Beta |

## Architecture

```
Traces (OTEL / Webhook / SDK)
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                   Pisama                             │
│                                                     │
│  Ingestion ──▶ Detection (18 detectors) ──▶ Fixes  │
│                    │                          │     │
│                    ▼                          ▼     │
│              Self-Healing            Fix Generator  │
│              (rollback, retry,      (code-level     │
│               re-route)             suggestions)    │
│                                                     │
│  Storage: PostgreSQL + pgvector                     │
│  API: FastAPI  │  Dashboard: Next.js                │
└─────────────────────────────────────────────────────┘
```

**Self-healing** creates a checkpoint, applies a targeted fix, and verifies the outcome before releasing control. High-risk fixes require approval. Every action is logged as an OTEL span.

## Platform

The hosted platform at [pisama.ai](https://pisama.ai) adds:

- Dashboard with real-time trace analytics
- Detection history and trend analysis
- Team collaboration and alerting (Slack, PagerDuty)
- Episodic memory (detectors learn from your feedback)
- Cost analytics and token tracking

| | Free | Pro | Team | Enterprise |
|---|---|---|---|---|
| Price | $0 | $29/mo | $79/mo | Custom |
| Projects | 1 | 3 | 10 | Unlimited |
| All 18 detectors | Yes | Yes | Yes | Yes |
| Code-level fixes | -- | Yes | Yes | Yes |
| Self-healing | -- | -- | -- | Yes |

## Documentation

- [Getting Started](https://docs.pisama.ai/quickstart)
- [API Reference](https://docs.pisama.ai/api/reference)
- [Detection Reference](https://docs.pisama.ai/detection/overview)
- [Failure Modes](https://docs.pisama.ai/concepts/failure-modes)
- [Integrations](https://docs.pisama.ai/guides/integrations)

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/tn-pisama/mao-testing-research.git
cd mao-testing-research
pip install -e "packages/pisama[dev]"
pytest packages/pisama-core/tests/
```

## License

MIT
