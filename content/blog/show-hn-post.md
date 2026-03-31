# Show HN: Pisama – heuristic detectors that beat o1 at catching agent failures (open source)

GitHub: https://github.com/tn-pisama/mao-testing-research

Pisama is an open-source library of 18 failure detectors for AI agent systems. It finds loops, hallucinations, context neglect, coordination failures, and 14 other failure types — using heuristics, not LLM calls.

**Why this exists:** When your agent fails in production, the standard approach is LLM-as-judge — feed the trace to GPT-4 and ask "what went wrong?" We found that simple heuristics (word overlap, hash comparison, regex patterns, tool success rates) outperform frontier LLMs at this task.

**The numbers:**

On the TRAIL benchmark (Patronus AI, 148 traces, 841 labeled errors):
- Pisama: 60.1% joint accuracy, 100% precision
- Gemini 2.5 Pro: 11%
- o3: 9.2%
- Claude 3.7 Sonnet: 4.7%

On Who&When (ICML 2025, multi-agent failure attribution):
- Pisama + Sonnet 4: 60.3% agent accuracy, 24.1% step accuracy
- o1 all-at-once: 53.5% agent accuracy, 14.2% step accuracy

**Why heuristics win here:** Agent failures have structural signatures. Loops are repeated state (hash match). Context neglect is measurable element overlap. Hallucination correlates with tool failure rates. A purpose-built pattern matcher extracts these signals more reliably than a general-purpose LLM trying to reason about them.

**Where LLMs still win:** Blame attribution in multi-agent conversations ("which agent caused this?") needs semantic reasoning. Pisama tiers the approach — heuristics for detection ($0), LLM judge for attribution ($0.02/case).

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

18 detectors: loop, coordination, hallucination, injection, corruption, persona drift, derailment, context neglect, specification mismatch, communication breakdown, decomposition, workflow, completion, withholding, convergence, overflow, cost, repetition.

MIT licensed. No API key needed for local detection.

Would love feedback — what agent failure modes should we add detectors for?
