# Claude Code Integration

Pisama captures and analyzes traces from [Claude Code](https://claude.com/claude-code) CLI sessions, detecting failure modes in Claude's tool-use patterns.

## Overview

The Claude Code integration captures every tool call (Bash, Read, Edit, Write, Grep, etc.) as a span, enabling Pisama to detect:

- **Infinite loops**: Agent repeating the same tool calls without progress
- **Task derailment**: Agent going off-topic from the assigned task
- **Context overflow**: Token accumulation approaching model limits
- **Cost tracking**: Token usage and estimated costs per session
- **Hallucination**: Code suggestions that don't match the codebase

## Installation

Install the Pisama Claude Code package:

```bash
pip install pisama-claude-code
```

Initialize in your project:

```bash
pisama-cc init
```

This installs the necessary hooks and creates a `.pisama` configuration directory.

## CLI Commands

| Command | Description |
|---|---|
| `pisama-cc init` | Install hooks, create config |
| `pisama-cc status` | Show connection status |
| `pisama-cc analyze` | Run local detection on captured traces |
| `pisama-cc sync` | Upload traces to Pisama platform (requires API key) |
| `pisama-cc export` | Export traces to file |
| `pisama-cc connect` | Connect to the Pisama platform |
| `pisama-cc disconnect` | Remove API key |

## Features by Mode

| Feature | Local (Free) | Cloud (Premium) |
|---|---|---|
| Trace capture | Yes | Yes |
| Failure detection (F1-F16) | Yes | Yes |
| Self-healing (loop break) | Yes | Yes |
| Export/share traces | Yes | Yes |
| Sync to platform | -- | Yes |
| Team dashboard | -- | Yes |
| Cross-session analytics | -- | Yes |
| AI fix suggestions | -- | Yes |

## Trace Ingestion Endpoint

For direct API integration, use the Claude Code ingestion endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/traces/claude-code/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-11T10:00:00Z",
    "tool_name": "Bash",
    "hook_type": "post_tool",
    "session_id": "session-abc-123",
    "tool_input": {"command": "pytest tests/"},
    "tool_output": "5 passed, 0 failed",
    "working_dir": "/home/user/project",
    "trace_type": "tool_call",
    "model": "claude-sonnet-4",
    "tokens_in": 1500,
    "tokens_out": 800,
    "cost_usd": 0.012
  }'
```

## Span Data Captured

Each tool call generates a span containing:

| Data Type | Description | Typical Size |
|---|---|---|
| **Tool Input** | Parameters passed to the tool | 100-1,000 chars |
| **Tool Output** | Result from tool execution | 100-50,000 chars |
| **Metadata** | Session ID, timestamp, model, tokens, cost | ~500 chars |
| **Working Directory** | Current project directory | ~100 chars |

## Package Architecture

```
┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  pisama-claude-code │  │   pisama-core   │  │  pisama-skills  │
│      (PyPI)         │  │     (PyPI)      │  │   (Optional)    │
│                     │  │                 │  │                 │
│  - CLI (pisama-cc)  │  │  - Span format  │  │  - /diagnose    │
│  - Hook installer   │  │  - Storage      │  │  - /fix         │
│  - Local detection  │  │  - Detectors    │  │  - /config      │
│  - Cloud sync       │  │  - Converters   │  │  - /guardian    │
└─────────────────────┘  └─────────────────┘  └─────────────────┘
         │                       │                     │
         └───────────────────────┼─────────────────────┘
                                 ▼
         ┌──────────────────────────────────────────┐
         │           Pisama Platform                 │
         │  Dashboard - Analytics - Alerts - Fixes  │
         └──────────────────────────────────────────┘
```
