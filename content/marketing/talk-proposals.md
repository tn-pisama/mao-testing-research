# Conference Talk Proposals

---

## Talk 1: Technical

**Target conferences:** NeurIPS workshops, AAAI, ICML workshops, MLOps World, AI Engineer Summit

### Title

Agent Forensics: A Tiered Approach to Detecting Failure Modes in Multi-Agent Systems

### Abstract

Multi-agent AI systems fail in ways that single-model systems do not. Agents loop indefinitely, corrupt shared state, drift from assigned personas, hallucinate tool outputs, and silently withhold information from collaborators. These failures are difficult to observe because they emerge from inter-agent dynamics rather than individual model errors, and current monitoring approaches — log inspection, output sampling, LLM-as-judge — either miss them entirely or cost more than the systems they evaluate.

We present Pisama, a detection framework that identifies 20 distinct failure modes in multi-agent systems using a tiered escalation architecture. The first tier applies deterministic checks: hash comparisons for state corruption, cycle detection for loops, and lexical overlap for grounding failures. These zero-cost heuristics resolve the majority of cases. Only ambiguous inputs escalate to a second tier of statistical methods (embedding similarity, token distribution analysis), and a final tier invokes LLM-based judgment for genuinely difficult cases. This architecture achieves 60.1% accuracy on the TRAIL benchmark at effectively zero marginal cost, compared to pure LLM-as-judge approaches that spend $0.02-0.15 per evaluation.

We describe the taxonomy of 20 failure types derived from analysis of production multi-agent traces, the design of tiered detectors for each, and calibration results across 7,212 labeled entries from 13 external data sources. We show that simple heuristics outperform expensive approaches on 12 of 20 failure types, and discuss where LLM escalation remains necessary.

### Outline

| # | Section | Time | Description |
|---|---------|------|-------------|
| 1 | The Failure Zoo | 5 min | Taxonomy of 20 multi-agent failure modes with live examples from production traces. Show how agent loops, state corruption, and persona drift manifest in real systems. Establish that these are not edge cases — they are the norm. |
| 2 | Why LLM-as-Judge Doesn't Scale | 5 min | Cost and latency analysis of evaluating every agent interaction with an LLM. Show the math: at 10,000 interactions/day, LLM-as-judge costs $200-1,500/day. Introduce the 100x cost gap as the core motivation. |
| 3 | Tiered Detection Architecture | 10 min | Walk through the three-tier escalation model. Tier 1: deterministic (hash, cycle detection, regex, word overlap). Tier 2: statistical (embedding similarity, token analysis). Tier 3: LLM judgment for ambiguous cases. Show escalation rates — 70%+ resolved at Tier 1. |
| 4 | Calibration and Results | 7 min | Methodology: 7,212 golden entries from 13 external sources, 5-fold cross-validation. Per-detector F1 scores (mean 0.701 across 18 production detectors). TRAIL benchmark: 60.1% at $0 vs. baselines. Discuss where heuristics beat LLMs and where they don't. |
| 5 | Open Problems | 3 min | Failure modes we can't yet detect cheaply: subtle coordination failures, implicit specification violations, emergent multi-turn degradation. Call to action for the research community. |

**Total: 30 minutes**

### Key Takeaways

- **Simple heuristics outperform LLM-as-judge on the majority of agent failure types.** Hash comparison catches state corruption. Cycle detection catches loops. Word overlap catches grounding failures. These cost nothing and run in milliseconds.
- **Tiered escalation is the right architecture for agent evaluation.** Not every failure needs an LLM to detect it. By routing easy cases to cheap detectors and reserving LLM judgment for genuinely ambiguous inputs, you can monitor agent systems at 1/100th the cost.
- **Multi-agent failures are taxonomically distinct from single-model failures.** Coordination failures, persona drift, and information withholding have no analog in single-model evaluation. The field needs purpose-built detection methods, not repurposed chatbot metrics.

### Speaker Bio

Tuomo Nikulainen is the founder of Pisama (pisama.ai), where he builds failure detection infrastructure for multi-agent AI systems. His work focuses on making agent observability practical — fast enough and cheap enough to run on every interaction, not just sampled evaluations. Before Pisama, Tuomo worked on distributed systems and developer tooling. He is based in San Francisco.

---

## Talk 2: Business/Product

**Target conferences:** SaaStr, ProductCon, AI Summit, TechCrunch Disrupt, Web Summit

### Title

Why 60% of AI Agents Fail Silently in Production

### Abstract

Companies are shipping AI agents into production faster than they can monitor them. Customer service agents that loop on the same question. Research agents that hallucinate citations. Multi-agent workflows where one agent corrupts another's state. These failures don't throw errors — they complete successfully while delivering wrong, incomplete, or harmful results. Your users notice before your engineering team does.

The monitoring gap is real: traditional observability tools track latency and error rates, but agent failures are semantic. An agent that confidently returns fabricated data has perfect uptime metrics. LLM-based evaluation catches these problems but costs $0.02-0.15 per check, making continuous monitoring economically impossible at scale. Most teams resort to spot-checking a fraction of agent outputs and hoping for the best.

Pisama closes this gap by detecting 20 types of agent failure — loops, hallucination, state corruption, persona drift, specification violations, and more — at effectively zero marginal cost. By using fast heuristic checks that only escalate to expensive LLM evaluation when necessary, Pisama makes it practical to monitor every agent interaction, not just a sample. Early deployments have identified failure modes that teams did not know existed in their systems, often within minutes of connecting.

This talk covers the most common ways AI agents fail in production, why existing monitoring misses them, and what a practical observability stack for agent systems looks like today.

### Outline

| # | Section | Time | Description |
|---|---------|------|-------------|
| 1 | The Agent Reliability Crisis | 5 min | Real examples of agent failures in production: the customer service bot that looped for 47 turns, the research agent that cited papers that don't exist, the multi-agent pipeline where agents contradicted each other. Establish the scale of the problem with data. |
| 2 | Why Your Monitoring Doesn't Catch This | 5 min | Traditional APM sees green dashboards while agents deliver garbage. LLM-as-judge is accurate but economically unfeasible for continuous use. Sampling gives you false confidence. Show the gap between what teams think their agent reliability is and what it actually is. |
| 3 | The 20 Ways Agents Break | 8 min | Walk through the taxonomy: loops, state corruption, hallucination, persona drift, coordination failures, specification violations, context overflow, and more. For each, show a concrete example and explain why it's hard to catch with conventional tools. |
| 4 | Making Agent Monitoring Practical | 7 min | The tiered detection approach: cheap checks first, expensive checks only when needed. How to get 100x cost reduction without sacrificing detection quality. Integration patterns: OpenTelemetry traces, SDK instrumentation, framework adapters. What a production agent monitoring setup actually looks like. |
| 5 | Building Trust in Agent Systems | 5 min | The business case: agent reliability directly drives user retention, support costs, and liability risk. How continuous failure detection changes the development loop — from "ship and pray" to "detect and fix." Where the market is heading and what engineering leaders should prioritize now. |

**Total: 30 minutes**

### Key Takeaways

- **Agent failures are semantic, not operational.** Your agents can have 99.9% uptime and still deliver wrong results on 30%+ of interactions. Traditional monitoring tools are blind to this. If you're shipping agents without semantic failure detection, you're flying blind.
- **Continuous agent monitoring is now economically feasible.** Tiered detection — cheap heuristics first, LLM evaluation only for ambiguous cases — reduces monitoring costs by 100x. This makes it practical to check every agent interaction, not just a sample.
- **The teams that invest in agent observability now will have a compounding advantage.** Every detected failure becomes training data. Every fixed failure mode improves the system. Early investment in agent reliability infrastructure compounds into better products, lower support costs, and defensible quality differentiation.

### Speaker Bio

Tuomo Nikulainen is the founder of Pisama (pisama.ai), a platform that detects when AI agents fail silently in production. Pisama monitors multi-agent systems for 20 types of failure — from loops and hallucination to state corruption and persona drift — at a fraction of the cost of LLM-based evaluation. Tuomo is based in San Francisco and is focused on making AI agent systems reliable enough to trust with real work.
