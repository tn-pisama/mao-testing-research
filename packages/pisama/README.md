# Pisama

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Multi-agent failure detection for production AI systems. Runs locally, no API key needed.

## Install

```bash
pip install pisama
```

## Quick Start

```python
import pisama

result = pisama.analyze("trace.json")
for issue in result.issues:
    print(f"[{issue.type}] {issue.summary} (severity={issue.severity})")
```

## CLI

```bash
# Analyze a trace file
pisama analyze trace.json

# List available detectors
pisama detectors
```

## Detectors

Pisama ships with 18 failure detectors that run locally:

| Detector | Catches |
|---|---|
| loop | Exact, structural, and semantic loops |
| corruption | State corruption and invalid transitions |
| persona_drift | Persona drift and role confusion |
| coordination | Agent handoff and communication failures |
| hallucination | Factual inaccuracy in agent output |
| injection | Prompt injection attempts |
| overflow | Context window exhaustion |
| derailment | Task focus deviation |
| context | Context neglect in responses |
| communication | Inter-agent communication breakdown |
| specification | Output vs specification mismatch |
| decomposition | Task breakdown failures |
| workflow | Workflow execution issues |
| withholding | Information withholding |
| completion | Premature or delayed task completion |
| cost | Token and cost budget overruns |
| convergence | Metric plateau, regression, and divergence |
| repetition | Repetitive output patterns |

## Docs

Full documentation: [pisama.dev/docs](https://pisama.dev/docs)

## License

MIT
