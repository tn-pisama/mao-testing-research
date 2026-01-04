# pisama-core

Core detection, scoring, and healing engine for PISAMA agent forensics.

## Overview

`pisama-core` provides the foundational components for detecting failures in LLM agent systems using the MAST (Multi-Agent System Testing) taxonomy of 16 failure modes.

## Features

- **Trace Models**: Standardized trace, span, and event models for agent observability
- **Detection Engine**: Pluggable detector architecture for MAST F1-F16 failure modes
- **Scoring Engine**: Configurable severity scoring with thresholds
- **Healing Engine**: Fix recommendation and application framework
- **Audit Logging**: Comprehensive audit trail for all interventions

## Installation

```bash
pip install pisama-core
```

## Quick Start

```python
from pisama_core.traces import Trace, Span, SpanKind, Platform
from pisama_core.detection import DetectorRegistry
from pisama_core.scoring import ScoringEngine

# Create a span
span = Span(
    span_id="span-001",
    name="Read",
    kind=SpanKind.TOOL,
    platform=Platform.CLAUDE_CODE,
)

# Run detection
registry = DetectorRegistry()
results = registry.detect_all(span)

# Score the results
scorer = ScoringEngine()
severity = scorer.calculate_severity(results)
```

## MAST Failure Modes

The detection engine supports 16 failure modes:

| Code | Name | Description |
|------|------|-------------|
| F1 | Infinite Loop | Agent stuck in repetitive pattern |
| F2 | Goal Drift | Agent deviates from original objective |
| F3 | Hallucination | Agent generates factually incorrect info |
| F4 | Tool Misuse | Incorrect or suboptimal tool usage |
| F5 | Context Overflow | Context window exhausted |
| F6 | State Corruption | Internal state becomes inconsistent |
| F7 | Deadlock | Multiple agents waiting on each other |
| F8 | Race Condition | Non-deterministic behavior from timing |
| F9 | Resource Exhaustion | API limits, memory, or budget exceeded |
| F10 | Permission Escalation | Agent attempts unauthorized actions |
| F11 | Data Leakage | Sensitive information exposed |
| F12 | Prompt Injection | Malicious input manipulation |
| F13 | Cascade Failure | Error propagates across components |
| F14 | Silent Failure | Error occurs but isn't reported |
| F15 | Grounding Failure | Loss of connection to external truth |
| F16 | Retrieval Failure | RAG system returns irrelevant data |

## Platform Adapters

pisama-core is designed to work with platform-specific adapters:

- `pisama-claude-code` - Claude Code integration
- `pisama-langchain` - LangChain/LangGraph integration (coming soon)
- `pisama-autogen` - AutoGen integration (coming soon)

## License

MIT
