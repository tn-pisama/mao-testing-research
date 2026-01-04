# pisama-claude-code

> **Coming Soon** - This package is in private development.

Trace capture for Claude Code sessions.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Lightweight trace capture client for Claude Code. Captures tool calls and syncs to PISAMA platform for analysis.

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

| Feature | pisama-claude-code | Platform |
|---------|-------------------|----------|
| Trace capture | ✅ | - |
| Local storage | ✅ | - |
| Export to JSONL | ✅ | - |
| Sync to platform | ✅ | ✅ |
| Failure detection (28 modes) | - | ✅ |
| Severity & explanations | - | ✅ |
| Fix suggestions | - | ✅ |
| Self-healing | - | ✅ |
| Dashboard | - | ✅ |

## CLI Commands

```bash
pisama-cc install     # Install capture hooks
pisama-cc uninstall   # Remove hooks
pisama-cc status      # Show status
pisama-cc traces      # View local traces
pisama-cc export      # Export to file
pisama-cc connect     # Connect to platform
pisama-cc sync        # Upload traces
pisama-cc analyze     # Run analysis (requires platform)
```

## Privacy

- Traces stored locally in `~/.claude/pisama/traces/`
- Secrets automatically redacted
- Paths anonymized
- Platform sync is opt-in

## Requirements

- Python 3.10+
- Claude Code CLI

## Status

Private beta. Contact team@pisama.dev for early access.

## License

MIT
