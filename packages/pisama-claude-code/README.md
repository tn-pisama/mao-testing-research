# pisama-claude-code

Trace capture for Claude Code sessions with token usage and cost tracking.

[![PyPI version](https://badge.fury.io/py/pisama-claude-code.svg)](https://pypi.org/project/pisama-claude-code/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install pisama-claude-code
```

## Quick Start

```bash
# Install capture hooks
pisama-cc install

# View recent traces
pisama-cc traces

# Show token usage and cost
pisama-cc usage --by-model --by-tool

# Export traces
pisama-cc export -o traces.jsonl
```

## Overview

Lightweight trace capture client for Claude Code. Captures tool calls, token usage, and costs. Optionally syncs to PISAMA platform for analysis.

**This package captures traces. Analysis happens on the platform.**

```
┌─────────────────────┐         ┌─────────────────────┐
│   Claude Code       │         │   PISAMA Platform   │
│   + pisama-cc       │ ──────▶ │   (analysis)        │
│   (capture)         │  sync   │   (detection)       │
└─────────────────────┘         │   (self-healing)    │
                                └─────────────────────┘
```

## Features

### Local Features (no platform needed)

| Feature | Description |
|---------|-------------|
| Trace capture | Capture all tool calls (Bash, Read, Write, etc.) |
| Token tracking | Input, output, and cache tokens per call |
| Cost calculation | USD cost per trace and session totals |
| Model tracking | Track which Claude model is used |
| Local storage | SQLite + JSONL in `~/.claude/pisama/traces/` |
| Export | JSONL and gzip formats |

### Platform Features (requires connection)

| Feature | Description |
|---------|-------------|
| Failure detection | 28 MAST failure modes |
| Severity scores | Confidence and severity ratings |
| Fix suggestions | AI-powered remediation |
| Self-healing | Automatic intervention |
| Dashboard | Visual analytics |

## CLI Commands

```bash
pisama-cc install       # Install capture hooks to ~/.claude/hooks/
pisama-cc uninstall     # Remove hooks
pisama-cc status        # Show status, token totals, and cost
pisama-cc traces        # View recent traces
pisama-cc traces -v     # Verbose: show tokens and cost per trace
pisama-cc usage         # Token usage and cost breakdown
pisama-cc usage --by-model --by-tool  # Grouped breakdown
pisama-cc export -o FILE  # Export to JSONL
pisama-cc export --compress  # Export to gzip
pisama-cc connect       # Connect to PISAMA platform
pisama-cc sync          # Upload traces to platform
pisama-cc analyze       # Run failure detection (requires platform)
```

## Example Output

### Status
```
📊 PISAMA Status
========================================

🔧 Hook Installation:
   ✅ pisama-capture.py
   ✅ pisama-pre.sh
   ✅ pisama-post.sh
   All hooks installed

📁 Local Traces: 1400
   Input tokens:  9,580
   Output tokens: 79,569
   Total cost:    $43.22
   Models: claude-opus-4-5-20251101
```

### Usage Breakdown
```
📊 Token Usage Summary (last 100 traces)
==================================================
Input tokens:           10,234
Output tokens:          85,421
Cache read tokens:   1,234,567
Total tokens:           95,655
Total cost:        $    52.34

📈 By Model:
--------------------------------------------------
  claude-opus-4-5-20251101            $52.34

🔧 By Tool:
--------------------------------------------------
  Bash                   45 calls  $25.12
  Read                   30 calls  $15.34
  Write                  20 calls  $8.45
  Edit                   5 calls   $3.43
```

## Model Pricing

Supported models and pricing (per 1M tokens):

| Model | Input | Output | Cache Read |
|-------|-------|--------|------------|
| claude-opus-4-5 | $15.00 | $75.00 | $1.50 |
| claude-sonnet-4 | $3.00 | $15.00 | $0.30 |
| claude-3-5-sonnet | $3.00 | $15.00 | $0.30 |
| claude-3-5-haiku | $0.80 | $4.00 | $0.08 |

## Privacy

- Traces stored locally in `~/.claude/pisama/traces/`
- Secrets automatically redacted (API keys, passwords, tokens)
- File paths anonymized (home directory → `~`)
- Platform sync is opt-in

## Requirements

- Python 3.10+
- Claude Code CLI

## Configuration

After installation, add hooks to `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolCall": [
      {
        "command": "~/.claude/hooks/pisama-pre.sh",
        "timeout": 2000
      }
    ],
    "PostToolCall": [
      {
        "command": "~/.claude/hooks/pisama-post.sh",
        "timeout": 2000
      }
    ]
  }
}
```

## License

MIT
