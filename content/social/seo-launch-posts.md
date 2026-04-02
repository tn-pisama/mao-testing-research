# Pisama Launch Posts — Social Media

Ready-to-paste posts for Twitter, LinkedIn, Hacker News, and Reddit.

---

## 1. Twitter Launch Thread (5 tweets)

### Tweet 1/5
We built 20 detectors that catch AI agent failures — loops, hallucinations, state corruption, context neglect — without a single LLM call.

Pisama is now open source.

pisama.ai

#AIAgents

### Tweet 2/5
The problem: your agent fails silently. It loops. It ignores context. It corrupts state.

Standard fix: LLM judge at $0.10+/trace.

Our approach: purpose-built heuristics. Hash comparison, word overlap, regex patterns. $0/trace.

### Tweet 3/5
Results on TRAIL benchmark (Patronus AI, 841 labeled errors):

Pisama: 60.1% accuracy, 100% precision
Gemini 2.5 Pro: 11%
o3: 9.2%
Claude 3.7 Sonnet: 4.7%

Heuristics beat frontier LLMs at structural failure detection.

### Tweet 4/5
Works with what you already use:
- Python SDK: `pip install pisama`
- CLI: `pisama analyze trace.json`
- MCP server for Cursor/Claude Desktop
- Integrations: LangGraph, CrewAI, AutoGen, n8n, Dify

No API key needed. Runs locally.

### Tweet 5/5
20 core detectors: loop, corruption, persona drift, hallucination, injection, coordination, context neglect, specification mismatch, decomposition, workflow, completion, convergence, and more.

Try it: pip install pisama

GitHub: github.com/tn-pisama/mao-testing-research

---

## 2. Twitter Technical Insight 1 — Silent Loops

Most agent failures are invisible.

Your agent runs 45 seconds, burns 12k tokens, returns a plausible answer. Except it looped 6 times through the same reasoning chain.

No error. No crash. Just wasted compute and a wrong result.

We detect this with state hashing. $0.

#AIAgents

---

## 3. Twitter Technical Insight 2 — Heuristics vs LLM Detection

We analyzed 7,000+ agent traces from 13 sources.

Heuristics (hash comparison, word overlap, tool success rates) outperform LLM judges at structural failure detection.

Agent failures have mechanical signatures. A loop is repeated state. Context neglect is measurable overlap.

---

## 4. Twitter Technical Insight 3 — State Corruption

State corruption is the #1 agent failure nobody talks about.

Agent updates memory. Downstream step overwrites part of it. Now it runs on a chimera — half old state, half new.

No error. Output looks fine. Every decision after is wrong.

State delta comparison catches it. $0.

---

## 5. Twitter Benchmark Post — TRAIL Results

TRAIL benchmark (Patronus AI, 148 traces, 841 errors):

Pisama: 60.1% accuracy at $0
Gemini 2.5 Pro: 11%
o3: 9.2%
Claude 3.7 Sonnet: 4.7%

Pattern matching > general reasoning for structural failure detection.

Open source: pisama.ai

#LLM #AIAgents

---

## 6. Twitter Benchmark Post 2 — Calibration Results

18 production detectors. Mean F1 of 0.701. Tested on 7,212 real entries from 13 external sources.

8 detectors above 0.80 F1. Zero synthetic data in the eval set.

We publish our calibration numbers because agent testing tools that don't are selling vibes.

pisama.ai

---

## 7. LinkedIn Launch Post

I've been building Pisama for the past year. Today it's open source.

THE PROBLEM

AI agents fail silently. They loop, hallucinate, ignore context, corrupt their own state. The standard fix is to throw an LLM judge at the trace — expensive, slow, and surprisingly inaccurate.

When we benchmarked frontier LLMs on agent failure detection, the best scored 11% accuracy. Most scored under 10%.

THE APPROACH

Pisama uses 20 purpose-built heuristic detectors instead of LLM calls. Hash comparison for loops. State delta analysis for corruption. Word overlap for context neglect. Tool success rate patterns for hallucination.

Simple? Yes. That's the point. Agent failures have structural signatures that don't require reasoning — they require pattern matching.

THE RESULTS

On the TRAIL benchmark (Patronus AI, 841 labeled errors): 60.1% accuracy at $0 cost per trace. On our internal calibration across 7,212 entries from 13 external sources: mean F1 of 0.701 across 18 detectors.

WHAT YOU GET

- Python SDK: pip install pisama
- CLI with watch mode
- MCP server for Cursor and Claude Desktop
- Integrations for LangGraph, CrewAI, AutoGen, n8n, Dify
- No API key required for local detection

MIT licensed. No vendor lock-in.

If you're building with AI agents and want to know when they fail before your users do — give it a look.

pisama.ai

#AIAgents #LLMOps #OpenSource #SoftwareEngineering

---

## 8. LinkedIn Technical Post

Why we bet on heuristics over LLM judges for agent testing

When we started building Pisama, the conventional wisdom was clear: use an LLM to evaluate LLM outputs. Makes intuitive sense. The model understands language, so it should be good at judging language-based failures.

We tried it. The results were bad.

On the TRAIL benchmark, the best frontier LLM scored 11% accuracy on agent failure detection. The reason became clear once we looked at failure signatures: agent failures are structural, not semantic.

A loop is repeated state — detectable by comparing hashes of consecutive states. Context neglect is a measurable gap between input elements and output coverage. State corruption is a delta between expected and actual state transitions.

These are pattern-matching problems. An LLM is processing the entire trace as natural language and trying to reason about it. A purpose-built detector skips the reasoning and looks directly at the signal.

The tradeoff: heuristics can't do blame attribution. When three agents are collaborating and something fails, you need semantic reasoning to determine which agent caused it. That's where we still use LLMs — but only for that narrow task, at $0.02/case instead of $0.10+ for everything.

We built 20 detectors this way. 18 are in production with a mean F1 of 0.701 on real data from 13 external sources. Not perfect. But reliable, fast, and free to run.

If you're evaluating agent testing tools, ask one question: what happens when you run 10,000 traces? If the answer involves per-trace LLM costs, you have a scaling problem.

pisama.ai

---

## 9. Show HN Post

**Title:** Show HN: Pisama -- 20 heuristic detectors that beat frontier LLMs at catching agent failures

**Body:**

GitHub: https://github.com/tn-pisama/mao-testing-research

Pisama is an open-source library of 20 core failure detectors (plus 24 platform-specific ones) for AI agent systems. It catches loops, hallucinations, context neglect, state corruption, coordination failures, and 15 other failure types — using heuristics, not LLM calls.

**Why this exists:** When your agent fails in production, the standard approach is LLM-as-judge — feed the trace to GPT-4 and ask "what went wrong?" We found that simple heuristics (word overlap, hash comparison, regex patterns, tool success rates) consistently outperform frontier LLMs at this task.

**Benchmark results:**

On the TRAIL benchmark (Patronus AI, 148 traces, 841 labeled errors):
- Pisama: 60.1% joint accuracy, 100% precision, $0 cost
- Gemini 2.5 Pro: 11%
- o3: 9.2%
- Claude 3.7 Sonnet: 4.7%

On Who&When (ICML 2025, multi-agent failure attribution):
- Pisama + Sonnet 4: 60.3% agent accuracy, 24.1% step accuracy
- o1 all-at-once: 53.5% agent accuracy, 14.2% step accuracy

**Why heuristics win here:** Agent failures have structural signatures. A loop is repeated state — detectable via hash comparison. Context neglect is measurable element overlap between input and output. Hallucination correlates with tool failure rates. These are pattern-matching problems, not reasoning problems.

**Where LLMs still win:** Blame attribution in multi-agent conversations requires semantic reasoning. Pisama tiers the approach — heuristics for detection ($0), LLM judge only for attribution ($0.02/case).

```bash
pip install pisama
```

```python
from pisama import analyze
result = analyze("trace.json")
for issue in result.issues:
    print(f"[{issue.type}] {issue.summary}")
```

Also works as a CLI (`pisama analyze trace.json`, `pisama watch python agent.py`) and MCP server for Cursor/Claude Desktop.

Integrates with LangGraph, CrewAI, AutoGen, n8n, Dify, and OpenClaw. MIT licensed. No API key needed for local detection.

We calibrated on 7,212 real entries from 13 external sources — no synthetic data in the eval set. 18 detectors in production with mean F1 of 0.701.

Would love feedback — especially on what agent failure modes we should prioritize next.

---

## 10. Reddit r/MachineLearning Post

**Title:** [P] Pisama: open-source heuristic detectors for multi-agent system failures (beats frontier LLMs on TRAIL benchmark)

**Body:**

I've been working on detecting failure modes in multi-agent LLM systems. The standard approach is LLM-as-judge, but we found that simple heuristics significantly outperform frontier models at this task.

Pisama is a library of 20 core failure detectors — loop detection (state hashing), hallucination (tool success rate patterns), context neglect (word overlap), state corruption (delta comparison), coordination failures, persona drift, prompt injection, and more.

**Results on TRAIL benchmark** (Patronus AI, 148 agent traces, 841 labeled errors):
- Pisama (heuristics only): 60.1% joint accuracy, 100% precision
- Gemini 2.5 Pro: 11%
- o3: 9.2%

The performance gap is large enough that I think it points to something fundamental: agent failures are structural, not semantic. A loop is repeated state. Context neglect is a measurable gap between input elements and output coverage. Pattern matching finds these more reliably than general-purpose reasoning.

On internal calibration (7,212 entries from 13 external sources, no synthetic data): mean F1 of 0.701 across 18 production detectors. Not state-of-the-art on any individual task, but the coverage across failure types is the point.

Limitations worth noting:
- Heuristics can't do blame attribution in multi-agent conversations — we still need LLMs for that
- Some failure types (subtle hallucination, nuanced persona drift) are inherently hard for heuristics
- The TRAIL benchmark is relatively new and may not be representative of all production failure distributions

We tier the approach: heuristics for detection ($0/trace), LLM judge only for attribution when needed ($0.02/case).

GitHub: https://github.com/tn-pisama/mao-testing-research
Website: https://pisama.ai
Install: `pip install pisama`

Integrates with LangGraph, CrewAI, AutoGen, n8n, Dify. MIT licensed.

Happy to discuss the detection algorithms in detail — curious what failure modes others are seeing in production agent systems.
