# Pisama Competitive Analysis - Executive Summary

*Last updated: March 2026. Full analysis: [docs/COMPETITIVE_LANDSCAPE_MATRIX.md](docs/COMPETITIVE_LANDSCAPE_MATRIX.md)*

---

## Positioning

**"Your agents are running. Pisama tells you when they're failing -- and fixes them."**

Pisama is the failure detection and self-healing layer for production AI agent systems. Not observability (Datadog). Not evaluation (DeepEval). Not security scanning (Promptfoo). It identifies *what went wrong* and *fixes it automatically*.

---

## Competitive Matrix

```
                    Agent-Specific <----------------------> General-Purpose
                    |                                                  |
  Detection/Healing |  PISAMA          Patronus    Galileo            |
                    |                                                  |
  Evaluation/       |  LangWatch                   Braintrust         |
  Simulation        |                  Promptfoo    DeepEval           |
                    |                              W&B Weave          |
                    |                                                  |
  Observability     |  AgentOps        LangSmith   Datadog            |
                    |                  Langfuse    New Relic           |
                    |                  Phoenix     Logfire             |
```

---

## Key Competitors

| Competitor | What They Do | Funding | Threat |
|---|---|---|---|
| **Patronus AI** | 20+ failure modes, agent-as-judge with memory | $40M | Closest direct competitor |
| **Galileo AI** | Prevention-first guardrails, runtime blocking | $68M | Could expand into detection |
| **Datadog** | Auto-instrumented agent observability | Public co | Biggest long-term threat (distribution) |
| **Promptfoo** | 134 security plugins, red teaming | Acquired by OpenAI (Mar 2026) | Validates market; security-focused, not operational |
| **Langfuse** | Open-source tracing | Acquired by ClickHouse (Jan 2026) | No failure detection |
| **DeepEval** | Open-source eval (50+ metrics) | Growing OSS | Generic eval, not failure-specific |

---

## Pisama's Advantages

1. **42 failure detectors** vs Patronus' 20 -- deepest coverage in the market
2. **Self-healing** -- only platform with automated fix generation + rollback + approval
3. **Cost-aware detection** -- tiered pipeline keeps cost under $0.05/trace
4. **All detectors free** -- no feature-gating; competitors hide pricing
5. **OTEL-native** -- framework-agnostic, not locked to LangChain or OpenAI
6. **Calibration transparency** -- published F1 scores; no competitor does this

## Pisama's Vulnerabilities

1. **Zero market traction** -- no customers, no stars, no funding
2. **Unknown brand** -- invisible in a market of household names
3. **No pre-production testing** -- Patronus has Generative Simulators
4. **No memory/learning** -- Patronus' agent learns from previous failures
5. **No open-source strategy** -- every major competitor is OSS
6. **No developer community** -- no Discord, no content, no advocacy

---

## Market Context

- **Agentic AI Testing**: $8.56B (2025) -> $100.2B (2033) at 36% CAGR
- **89% have observability, only 52% have evaluation** -- 37-point gap Pisama addresses
- **Consolidation accelerating**: Langfuse -> ClickHouse, Promptfoo -> OpenAI
- **Window**: 12-18 months before general-purpose platforms add "good enough" failure detection

---

## Strategic Priorities

| Priority | Action | Timeline |
|---|---|---|
| 1 | Open-source core detectors | Months 1-3 |
| 2 | Langfuse/Phoenix trace import | Months 1-3 |
| 3 | Get 5-10 real users | Months 1-3 |
| 4 | Pre-production simulation | Months 3-6 |
| 5 | Detection memory/learning | Months 3-6 |

---

## Bottom Line

Technically excellent product with genuine differentiation (42 detectors, self-healing, cost-aware architecture). Zero market traction in a space with $40-68M funded competitors. The single most important thing is getting real users in the next 3 months. Everything else is secondary.

**Most dangerous competitor**: Datadog (distribution, not capability).
**Most interesting opportunity**: The 89%/52% observability-to-evaluation gap.

*Full analysis with deep dives on Patronus, Datadog, Galileo, and Promptfoo: [docs/COMPETITIVE_LANDSCAPE_MATRIX.md](docs/COMPETITIVE_LANDSCAPE_MATRIX.md)*
