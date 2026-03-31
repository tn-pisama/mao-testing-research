# Twitter/X Thread (7 tweets)

## Tweet 1 (Hook)
We built 18 heuristic detectors that beat GPT-4 and o1 at catching AI agent failures.

No LLM calls. Zero cost. Open source.

60.1% accuracy vs 11% for the best frontier model.

Here's what we found:

[attach: TRAIL benchmark comparison table image]

## Tweet 2 (The result)
On Patronus AI's TRAIL benchmark (148 traces, 841 human-labeled errors):

Gemini 2.5 Pro: 11%
o3: 9.2%
Claude 3.7 Sonnet: 4.7%

Pisama (heuristics): 60.1%

100% precision — zero false positives.

No LLM calls. 21 seconds for all 148 traces.

## Tweet 3 (Why)
Why do simple heuristics beat frontier LLMs?

Agent failures have structural signatures:
- Loops = repeated state (hash match)
- Context neglect = low element overlap
- Hallucination = tool failure rate
- Spec mismatch = keyword coverage

Pattern matchers > reasoning for structural signals.

## Tweet 4 (Multi-agent)
But what about "who's to blame" in multi-agent systems?

On Who&When (ICML 2025):
- Heuristics alone: 31% agent accuracy
- + one Sonnet 4 call: 60.3% (beats o1's 53.5%)
- Cost: $0.02 per case

Heuristics detect. LLMs attribute. Tier them.

## Tweet 5 (The cost argument)
The economics:

LLM-as-judge: ~$0.05-0.50 per trace, seconds of latency
Pisama heuristics: $0, <10ms

For a team running 10K agent traces/day:
- LLM judge: $500-5,000/day
- Pisama: $0/day (+ $0.02/case for attribution when needed)

## Tweet 6 (Try it)
pip install pisama

from pisama import analyze
result = analyze("trace.json")
for issue in result.issues:
    print(issue.type, issue.summary)

Also: CLI, MCP server for Cursor/Claude Desktop, trace replay.
18 detectors. MIT licensed. No API key.

## Tweet 7 (CTA)
GitHub: github.com/tn-pisama/mao-testing-research
PyPI: pypi.org/project/pisama
Blog: [link to full post]

What agent failure modes are you seeing that we should add detectors for?
