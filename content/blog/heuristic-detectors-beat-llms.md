# Why Heuristic Detectors Beat LLMs at Finding Agent Failures

**TL;DR:** We built 18 rule-based detectors that find failures in AI agent traces. On the [TRAIL benchmark](https://arxiv.org/abs/2505.08638) (Patronus AI), they achieve 60.1% accuracy vs. 11% for the best LLM. Zero false positives. Zero LLM cost. On [Who&When](https://arxiv.org/abs/2505.00212) (ICML 2025), combined with a single Sonnet call for attribution, they beat o1 on both agent identification (60.3% vs. 53.5%) and step localization (24.1% vs. 14.2%).

```bash
pip install pisama
```

---

## The assumption everyone makes

When an AI agent fails in production — it hallucinates, gets stuck in a loop, ignores instructions, drops context — the standard approach is to throw another LLM at the problem. LLM-as-judge. Agent-as-judge. Feed the trace to GPT-4 and ask "what went wrong?"

We tested this assumption. The answer is surprising: for most agent failures, simple heuristics work better.

## The benchmarks

### TRAIL: Trace-level failure detection

Patronus AI's [TRAIL benchmark](https://arxiv.org/abs/2505.08638) contains 148 real agent execution traces with 841 human-labeled errors across 21 failure categories. It's the hardest agent failure detection benchmark available — the best frontier model (Gemini 2.5 Pro) finds only 11% of failures. Claude 3.7 Sonnet finds 4.7%.

We ran Pisama's 18 heuristic detectors on TRAIL:

| Method | Joint Accuracy | Precision | Cost | Latency |
|--------|---------------|-----------|------|---------|
| Gemini 2.5 Pro | 11.0% | -- | $$$ | ~seconds |
| OpenAI o3 | 9.2% | -- | $$$ | ~seconds |
| Claude 3.7 Sonnet | 4.7% | -- | $$$ | ~seconds |
| **Pisama (heuristic)** | **60.1%** | **100%** | **$0** | **21s total** |

60.1% joint accuracy. 5.5x better than SOTA. And 100% precision — when Pisama says something is wrong, it's always right.

The per-category breakdown shows where heuristics dominate:

| Category | Pisama F1 | TRAIL SOTA |
|----------|-----------|-----------|
| Context Handling | **0.978** | 0.00 |
| Specification | **1.000** | N/A |
| Loop / Resource Abuse | **1.000** | ~0.30 |
| Tool Selection | **1.000** | ~0.57 |
| Hallucination (language) | **0.884** | 0.59 |
| Goal Deviation | **0.829** | 0.70 |

Context handling and task orchestration — categories where LLMs score literally 0.00 — are where heuristic detectors excel.

### Who&When: Multi-agent failure attribution

[Who&When](https://arxiv.org/abs/2505.00212) (ICML 2025 Spotlight) tests a harder question: in a multi-agent conversation that failed, which agent caused the failure and at which step?

Heuristic detectors alone can find *when* the failure happened (step accuracy: 16.8%, competitive with o1's 14.2%) but struggle with *who's to blame* (agent accuracy: 31.0% vs. o1's 53.5%). Blame attribution requires reading comprehension — understanding that "WebSurfer clicked the wrong link" is different from "Orchestrator planned poorly."

But here's the key: you don't need to choose between heuristics and LLMs. You can tier them. Run heuristics first (free, fast), then use a single LLM call only for attribution:

| Method | Agent Accuracy | Step Accuracy | Cost/case |
|--------|---------------|---------------|-----------|
| Pisama heuristic-only | 31.0% | 16.8% | $0.000 |
| Pisama + Haiku 4.5 | 39.7% | 15.5% | $0.004 |
| **Pisama + Sonnet 4** | **60.3%** | **24.1%** | **$0.021** |
| o1 all-at-once | 53.5% | 14.2% | $$$ |
| GPT-4o all-at-once | 44.9% | 8.7% | $$ |

Sonnet 4 at the attribution tier beats every baseline in the paper at $0.02 per case.

## Why heuristics win at detection

Agent failures have structural signatures that don't require semantic understanding:

**Loops** are repeated state. A hash comparison catches them instantly — no need to "understand" that the agent is stuck. Pisama's loop detector counts consecutive tool repetitions and cyclic patterns. F1: 1.000 on TRAIL.

**Context neglect** is measurable overlap. If the input mentions specific dates, numbers, and names, and the output references none of them, the context was ignored. Pisama's context detector extracts weighted elements (numbers, dates, proper nouns, URLs) and measures utilization. F1: 0.978 on TRAIL.

**Hallucination** correlates with tool failure. When an agent claims it searched the web but the search tool returned an error, that's a fabricated result. Pisama's hallucination detector checks tool call success rates and source-output overlap. F1: 0.884 on TRAIL.

**Specification mismatch** is requirement coverage. If the user asked for "a REST API with JWT authentication and PostgreSQL" and the output describes an HTML contact form, keyword coverage is low. Pisama's specification detector extracts requirements and measures coverage with synonym and stem matching. F1: 1.000 on TRAIL.

The pattern: agent failures leave measurable traces. LLMs try to reason about whether something went wrong. Heuristics directly measure the signatures of failure. When the signal is structural, a purpose-built pattern matcher extracts it more reliably than a general-purpose language model.

This echoes [Gigerenzer's research](https://en.wikipedia.org/wiki/Gerd_Gigerenzer#Heuristics) on decision-making: in uncertain environments, simple rules that focus on the most diagnostic cue often outperform complex models that try to weight all available information. Agent failure detection is exactly this kind of problem — high-dimensional traces where a single diagnostic signal (state repetition, element coverage, tool success rate) carries most of the information.

## Where LLMs are still needed

Heuristics can't do everything. Two things require semantic reasoning:

1. **Blame attribution** in multi-agent systems. "WebSurfer clicked an irrelevant link" vs. "Orchestrator gave unclear instructions" — determining which agent caused a cascade requires understanding the causal chain. This is where Pisama's LLM judge tier ($0.02/case with Sonnet 4) adds value.

2. **Novel failure modes.** Heuristic detectors match known patterns. A completely new type of failure that doesn't match any of the 18 detectors will be missed. The LLM judge serves as a catch-all for out-of-distribution failures.

The right architecture isn't heuristics *or* LLMs. It's heuristics *then* LLMs — cheap, fast pattern matching for 90%+ of detections, with LLM escalation for the cases that need semantic reasoning.

## Try it

```bash
pip install pisama
```

```python
from pisama import analyze

result = analyze("trace.json")

for issue in result.issues:
    print(f"[{issue.type}] {issue.summary}")
    print(f"  Severity: {issue.severity}/100")
    print(f"  Fix: {issue.recommendation}")
```

CLI:

```bash
pisama analyze trace.json
pisama watch python my_agent.py
pisama detectors
```

MCP server (Cursor / Claude Desktop):

```json
{
  "mcpServers": {
    "pisama": { "command": "pisama", "args": ["mcp-server"] }
  }
}
```

Source: [github.com/tn-pisama/mao-testing-research](https://github.com/tn-pisama/mao-testing-research)

PyPI: [pypi.org/project/pisama](https://pypi.org/project/pisama/)

---

*What failure modes are you seeing in your agent systems? We'd love to hear what detectors we should add — [open an issue](https://github.com/tn-pisama/mao-testing-research/issues) or reach out at team@pisama.ai.*
