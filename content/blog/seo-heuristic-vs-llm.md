---
title: "Heuristic Detectors vs LLM Judges: What We Learned Analyzing 7,000 Agent Traces"
published: true
description: "We compared heuristic failure detectors against LLM-as-judge approaches on 7,212 agent traces from 13 sources. Heuristics scored 60.1% on TRAIL at $0 cost vs 11% for the best LLM. Here's when each approach wins and when it doesn't."
tags: ai, machinelearning, testing, llm
canonical_url: https://pisama.ai/blog/seo-heuristic-vs-llm
---

# Heuristic Detectors vs LLM Judges: What We Learned Analyzing 7,000 Agent Traces

The default approach to evaluating AI agents is to use another AI. LLM-as-judge. Feed the trace to a frontier model and ask "what went wrong?" It's intuitive, flexible, and expensive. It also underperforms purpose-built heuristics on most failure categories.

We know this because we tested both approaches systematically. [Pisama](https://pisama.ai) has 18 production-grade heuristic detectors calibrated on 7,212 labeled entries from 13 external data sources. We benchmarked them against LLM judges on two public agent failure benchmarks. The results challenged our assumptions about when you need semantic reasoning and when simple pattern matching is enough.

This article presents the data, explains why heuristics outperform LLMs on structural failures, identifies the categories where LLMs are still essential, and describes the tiered architecture we settled on.

## The Benchmarks

### TRAIL: Single-Trace Failure Detection

[TRAIL](https://arxiv.org/abs/2505.08638), released by Patronus AI, contains 148 real agent execution traces with 841 human-labeled errors spanning 21 failure categories. It's designed to test whether systems can identify *all* failures in a given trace — not just one, but every issue present. This makes it harder than typical binary classification benchmarks.

The best published result from a frontier LLM is 11.0% joint accuracy (Gemini 2.5 Pro). Claude 3.7 Sonnet achieves 4.7%. OpenAI o3 achieves 9.2%. These are capable models performing poorly because the task requires systematic structural analysis, not the open-ended reasoning LLMs are optimized for.

### Who&When: Multi-Agent Failure Attribution

[Who&When](https://arxiv.org/abs/2505.00212), an ICML 2025 spotlight paper, tests a harder question: given a multi-agent conversation that failed, which agent caused the failure and at which step? This combines detection (something went wrong) with attribution (who's responsible and when did it happen).

### Our Calibration Dataset

Separately from these benchmarks, we maintain a golden dataset of 7,212 labeled entries across all 18 production detector categories. These entries come from 13 external sources including MAST-Data (NeurIPS 2025), AgentErrorBench, SWE-bench traces, GAIA traces, and real n8n workflow failures. We use this dataset for cross-validated calibration with per-difficulty stratification.

## The Results

### TRAIL Performance

| Method | Joint Accuracy | Precision | Cost per Trace |
|--------|---------------|-----------|----------------|
| Gemini 2.5 Pro | 11.0% | not reported | ~$0.05-0.15 |
| OpenAI o3 | 9.2% | not reported | ~$0.10-0.30 |
| Claude 3.7 Sonnet | 4.7% | not reported | ~$0.05-0.10 |
| **Pisama heuristic** | **60.1%** | **100%** | **$0.00** |

The headline number: 5.5x better than the best LLM, at zero cost.

But the precision number matters more than the accuracy. When Pisama flags a failure, it's always correct (100% precision on TRAIL). The 40% of failures it misses are genuine misses — cases where the heuristic detectors don't have a matching pattern. These are the cases where LLM escalation adds value.

The per-category breakdown reveals *why* heuristics dominate:

| Failure Category | Pisama F1 | Best LLM F1 |
|-----------------|-----------|-------------|
| Context Handling | 0.978 | 0.00 |
| Specification Compliance | 1.000 | N/A |
| Loop / Resource Abuse | 1.000 | ~0.30 |
| Tool Selection Errors | 1.000 | ~0.57 |
| Hallucination (language) | 0.884 | 0.59 |
| Goal Deviation | 0.829 | 0.70 |

Context handling — where LLMs score literally zero — is where heuristic detectors achieve near-perfect detection. The same pattern holds for loops, specification compliance, and tool errors. These categories have strong structural signals that pattern matchers extract reliably.

### Who&When Performance

| Method | Agent Accuracy | Step Accuracy | Cost per Case |
|--------|---------------|---------------|---------------|
| GPT-4o | 44.9% | 8.7% | ~$0.05 |
| o1 | 53.5% | 14.2% | ~$0.15 |
| Pisama heuristic-only | 31.0% | 16.8% | $0.000 |
| Pisama + Haiku 4.5 | 39.7% | 15.5% | $0.004 |
| **Pisama + Sonnet 4** | **60.3%** | **24.1%** | **$0.021** |

This benchmark tells a more nuanced story. Heuristic-only detection beats o1 on *step localization* (16.8% vs 14.2%) — finding *when* the failure happened is a structural question. But it trails on *agent identification* (31.0% vs 53.5%) — figuring out *who's to blame* requires reading comprehension and causal reasoning.

The hybrid approach — heuristics for detection, a single Sonnet call for attribution — beats every baseline at $0.02 per case.

### Calibration Dataset Performance

Across our 7,212-entry golden dataset, mean F1 across 18 production detectors is 0.701 with cross-validation. The distribution:

**Production tier (F1 >= 0.70):**
- Decomposition: 1.000
- Coordination: 0.914
- Corruption: 0.909
- Context: 0.865
- Hallucination: 0.857
- Specification: 0.857
- Grounding: 0.850
- Persona drift: 0.828

**Beta tier (F1 0.40-0.70):**
- Withholding: 0.800
- Overflow: 0.706
- Completion: 0.703
- Retrieval quality: 0.698
- Communication: 0.667
- Derailment: 0.667
- Injection: 0.667
- Workflow: 0.667
- Loop: 0.652

These numbers represent heuristic-only performance on diverse, real-world data from external sources. No cherry-picking, no synthetic test cases. The variance across detector types is informative: structural failures (decomposition, corruption, coordination) are easier to catch with rules than semantic failures (communication, derailment).

## Why Heuristics Win at Structural Detection

Agent failures leave measurable traces that don't require language understanding to detect:

**Loops are repeated states.** If the same sequence of node visits or tool calls appears three times, that's a loop. A hash comparison catches exact repetition. Subsequence matching catches cycles. You don't need to "understand" that the agent is stuck — you need to measure state repetition. Pisama's loop detector achieves F1 1.000 on TRAIL's loop/resource abuse category.

**Context neglect is missing coverage.** If upstream context contains twelve specific data points — numbers, dates, proper nouns, URLs — and the downstream output references zero of them, context was ignored. This is an element extraction and coverage measurement, not a judgment call. F1: 0.978 on TRAIL's context handling category.

**State corruption is type drift.** If a field that was a float is now a string, or a non-null field just became null, or a value changed direction five times in two seconds, the state is corrupted. These are delta comparisons on structured data. F1: 0.909 on our calibration dataset.

**Specification compliance is requirement coverage.** Extract the requirements from the spec ("REST API", "JWT authentication", "PostgreSQL"). Check whether the output addresses each one. Stem matching and synonym expansion handle paraphrasing. This is information retrieval, not language understanding. F1: 1.000 on TRAIL.

The underlying principle comes from Gerd Gigerenzer's research on decision-making: in uncertain environments with high-dimensional inputs, simple rules that focus on the most diagnostic cue often outperform complex models that try to weight all available information. Agent failure detection is exactly this kind of problem. The traces are long and complex, but the failure signal is usually concentrated in one diagnostic feature — state repetition for loops, element coverage for context neglect, type changes for corruption.

A purpose-built heuristic that knows exactly which signal to extract will beat a general-purpose LLM that has to figure out what to look for in a 50,000-token trace.

## Where LLMs Are Still Essential

Heuristics have clear limits. Two tasks consistently require LLM-level reasoning:

### 1. Blame Attribution in Multi-Agent Systems

When three agents collaborate and the output is wrong, determining *which agent* caused the failure requires causal reasoning. "The WebSurfer clicked an irrelevant link" vs. "The Orchestrator gave unclear instructions" — distinguishing root cause from downstream consequence requires reading comprehension that heuristics can't provide.

This is exactly what the Who&When results show: heuristics match LLMs on step localization (a structural question) but trail on agent identification (a semantic question).

### 2. Novel Failure Modes

Heuristic detectors match known failure patterns. If an agent fails in a way that doesn't match any of the 18 defined patterns — a genuinely new failure mode — heuristics will miss it entirely. An LLM judge serves as a catch-all for out-of-distribution failures, trading cost for coverage.

### 3. Subjective Quality Assessment

"Is this summary good enough?" is not a question heuristics can answer. Detecting that a summary is *incomplete* (missing 4 of 10 required points) is a heuristic problem. Judging whether the summary is *well-written* is a semantic one.

## The Tiered Architecture

The right approach isn't heuristics *or* LLMs. It's heuristics *then* LLMs, with escalation based on confidence.

Pisama uses five detection tiers:

| Tier | Method | Cost | When It Runs |
|------|--------|------|--------------|
| 1 | Hash comparison | ~$0.00 | Always — every trace |
| 2 | State delta analysis | ~$0.00 | Always — every trace |
| 3 | Embedding similarity | $0.01-0.02 | When tiers 1-2 are inconclusive |
| 4 | LLM judge | $0.02-0.10 | Gray-zone cases only |
| 5 | Human review | Variable | High-stakes decisions |

Tiers 1 and 2 are pure heuristics: hash collisions, type changes, pattern matching, coverage counting. They run on every trace and catch the majority of failures at zero marginal cost.

Tier 3 uses embeddings for cases that require fuzzy matching — semantic loop detection (same meaning, different words), persona drift measurement, grounding verification. This costs a few cents per trace.

Tier 4 invokes an LLM only for cases where the lower tiers produced low-confidence results. On TRAIL, approximately 40% of failures require escalation beyond heuristics. But the remaining 60% are caught for free.

The average cost per trace across our production workload is under $0.05. Compare that to running every trace through a frontier LLM at $0.10-0.30 per trace — a 2-6x cost reduction with better accuracy on structural failures.

## What This Means for Agent Evaluation

If you're building evaluation pipelines for AI agents, three takeaways from our data:

**1. Don't default to LLM-as-judge for everything.** It's the most expensive option and underperforms on structural failure categories. Use it where it adds unique value: blame attribution, novel failure detection, subjective quality.

**2. Invest in heuristic detectors for known failure patterns.** Loops, state corruption, context neglect, specification compliance — these have strong structural signals. A well-calibrated heuristic detector will be faster, cheaper, and more accurate than an LLM judge for these categories.

**3. Tier your detection pipeline.** Run cheap checks first. Escalate to expensive checks only when needed. This isn't just a cost optimization — it's an accuracy optimization. Heuristics have higher precision on structural failures because they're measuring the exact signal rather than reasoning about it.

The 60.1% vs 11% gap on TRAIL isn't because frontier LLMs are bad at reasoning. It's because systematic structural analysis is a different skill than open-ended language understanding, and purpose-built tools outperform general-purpose tools on well-defined tasks. This has been true in software engineering for decades. It's equally true for agent evaluation.

## Try It

```bash
pip install pisama
```

```python
from pisama import analyze

result = analyze("trace.json")

for issue in result.issues:
    print(f"[{issue.type}] {issue.summary}")
    print(f"  Severity: {issue.severity}/100")
```

CLI and MCP server for IDE integration:

```bash
pisama analyze trace.json
pisama watch python my_agent.py
pisama detectors
```

Full documentation at [docs.pisama.ai](https://docs.pisama.ai). Source and benchmark reproduction instructions at [github.com/tn-pisama/mao-testing-research](https://github.com/tn-pisama/mao-testing-research).

All calibration data, benchmark scripts, and detector source code are open. We'd rather have the approach scrutinized and improved than accepted on authority.
