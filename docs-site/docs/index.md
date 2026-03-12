---
hide:
  - navigation
  - toc
---

# PISAMA

## Multi-agent failure detection & self-healing platform

PISAMA detects **21 failure modes** in LLM agent systems, from infinite loops and hallucinations to coordination breakdowns and prompt injection. Built on the [MAST taxonomy](https://arxiv.org/abs/2503.13657) (NeurIPS 2025 Spotlight), PISAMA provides production-grade observability for any multi-agent framework.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Get started in 5 minutes**

    ---

    Install PISAMA, send your first trace, and see failure detection in action.

    [:octicons-arrow-right-24: Quickstart](quickstart.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---

    Complete REST API documentation for traces, detections, healing, analytics, and integrations.

    [:octicons-arrow-right-24: API docs](api/reference.md)

-   :material-currency-usd:{ .lg .middle } **Pricing**

    ---

    Free tier with 10,000 spans/month. Startup, Growth, and Enterprise plans for teams.

    [:octicons-arrow-right-24: See plans](pricing/index.md)

-   :material-shield-search:{ .lg .middle } **Detection Reference**

    ---

    Detailed documentation for all 21 failure mode detectors with accuracy benchmarks.

    [:octicons-arrow-right-24: Detectors](detection/overview.md)

</div>

---

## Why PISAMA?

### The problem

LLM agents fail silently. A coding agent loops for 40 minutes burning tokens. A research agent hallucinates citations. A customer support agent drifts from its persona. A multi-agent pipeline drops critical context between handoffs. These failures are invisible to standard monitoring tools.

### The solution

PISAMA provides purpose-built failure detection for AI agent systems:

| Capability | Description |
|---|---|
| **21 failure detectors** | Covering planning, execution, verification, and cross-cutting concerns |
| **Tiered detection** | Cost-aware escalation from hash-based ($0.00) to LLM judge ($0.05) |
| **Framework agnostic** | Works with LangGraph, CrewAI, AutoGen, n8n, Dify, OpenClaw, Claude Code |
| **Self-healing** | Automated fix generation, approval workflows, and rollback capabilities |
| **OTEL native** | Built on OpenTelemetry with `gen_ai.*` semantic conventions |
| **Production accuracy** | 10 detectors at F1 >= 0.80, with continuous calibration |

### Supported frameworks

- **LangGraph** -- State graph analysis, node-level detection
- **n8n** -- Workflow validation, AI node monitoring, webhook integration
- **Dify** -- App monitoring, workflow execution tracking
- **CrewAI** -- Agent role validation, task delegation analysis
- **AutoGen** -- Multi-agent conversation monitoring
- **OpenClaw** -- Session and agent tracking
- **Claude Code** -- Tool call capture and session analysis

---

## Architecture at a glance

```
Trace Sources                   PISAMA Platform                    Outputs
--------------                  ---------------                    -------

 LangGraph  ----+
 n8n        ----+---> Ingestion ---> Detection Engine ---> Dashboard
 Dify       ----+     Pipeline       (21 detectors)        Alerts
 CrewAI     ----+     (OTEL/         Tiered escalation     Fix suggestions
 Claude Code ---+      webhook)      LLM Judge             Self-healing
                                                            API / webhooks
```

---

## Quick links

- [Installation](getting-started/installation.md) -- Full setup guide
- [Configuration](getting-started/configuration.md) -- Environment variables reference
- [Failure Modes](concepts/failure-modes.md) -- Understanding what PISAMA detects
- [Integrations](guides/integrations/n8n.md) -- Connect your agent framework
- [Deployment](guides/deployment/docker-compose.md) -- Production deployment options
- [Contributing](contributing/development.md) -- Development setup and guidelines
