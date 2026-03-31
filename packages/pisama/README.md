# Pisama

**Find and fix failures in AI agent systems. No LLM calls required.**

[![PyPI](https://img.shields.io/pypi/v/pisama?color=blue)](https://pypi.org/project/pisama/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Pisama detects 32 types of agent failures using heuristic detectors that run locally, with zero LLM cost. On the [TRAIL benchmark](https://arxiv.org/abs/2505.08638), Pisama achieves **60.1% joint accuracy** vs. 11% for the best frontier model — with 100% precision (zero false positives).

## Install

```bash
pip install pisama
```

## Usage

```python
from pisama import analyze

result = analyze("trace.json")  # also accepts dicts and JSON strings

for issue in result.issues:
    print(f"[{issue.type}] {issue.summary} (severity: {issue.severity})")
    print(f"  Fix: {issue.recommendation}")
```

## CLI

```bash
pisama analyze trace.json          # Analyze a trace
pisama watch python my_agent.py    # Watch a live agent (pip install pisama[auto])
pisama replay <trace-id>           # Re-run detection on stored traces
pisama smoke-test --last 50        # Batch test recent traces
pisama detectors                   # List all 18 detectors
pisama mcp-server                  # Start MCP server (pip install pisama[mcp])
```

## MCP Server

Works in Cursor, Claude Desktop, Windsurf — no API key needed:

```json
{
  "mcpServers": {
    "pisama": { "command": "pisama", "args": ["mcp-server"] }
  }
}
```

## Detectors

| Detector | What It Catches |
|----------|----------------|
| `loop` | Infinite loops, retry storms, stuck patterns |
| `coordination` | Deadlocked handoffs, message storms |
| `hallucination` | Factual errors, fabricated tool results |
| `injection` | Prompt injection, jailbreak attempts |
| `corruption` | State corruption, type drift |
| `persona` | Persona drift, role confusion |
| `derailment` | Task deviation, goal drift |
| `context` | Context neglect, ignored instructions |
| `specification` | Output vs. requirement mismatch |
| `communication` | Inter-agent message breakdown |
| `decomposition` | Poor task breakdown, circular dependencies |
| `workflow` | Unreachable nodes, missing error handling |
| `completion` | Premature completion, unfinished work |
| `withholding` | Suppressed findings, hidden errors |
| `convergence` | Metric plateau, regression, thrashing |
| `overflow` | Context window exhaustion |
| `cost` | Token budget overrun |
| `repetition` | Tool dominance, low diversity |
| `routing` | Input sent to wrong specialist/route |
| `propagation` | Silent error propagation across steps |
| `critic_quality` | Rubber-stamping critics in reflection loops |
| `escalation_loop` | Escalation loops without resolution |
| `citation` | Fabricated citations |
| `parallel_consistency` | Contradictory parallel results |
| `memory_staleness` | Outdated memory retrieval |
| `approval_bypass` | High-risk actions without approval |
| `model_selection` | Wrong model for task complexity |
| `mcp_protocol` | MCP tool/schema/auth failures |
| `reasoning_consistency` | Contradictory reasoning, abandoned CoT |
| `entity_confusion` | Entity mix-ups from context |
| `task_starvation` | Planned tasks never executed |
| `exploration_safety` | Risky actions in trial-and-error |

## Benchmark Results

**TRAIL** (trace-level failure detection, 148 traces):

| Method | Joint Accuracy | Precision |
|--------|---------------|-----------|
| Gemini 2.5 Pro | 11.0% | -- |
| OpenAI o3 | 9.2% | -- |
| **Pisama** | **60.1%** | **100%** |

**Who&When** (ICML 2025, multi-agent attribution):

| Method | Agent Accuracy | Step Accuracy |
|--------|---------------|---------------|
| o1 | 53.5% | 14.2% |
| **Pisama + Sonnet 4** | **60.3%** | **24.1%** |

## Links

- [Documentation](https://docs.pisama.ai)
- [GitHub](https://github.com/tn-pisama/mao-testing-research)
- [Platform](https://pisama.ai)

## License

MIT
