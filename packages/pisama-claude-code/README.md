# pisama-claude-code

> **Coming Soon** - This package is in private development and not yet available for public use.

Trace capture and failure detection for Claude Code sessions.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Status

This package is currently in **private beta**. Public release coming soon.

To join the waitlist or request early access, contact: team@pisama.dev

## Overview

PISAMA Claude Code provides:

- **Trace Capture**: Automatic capture of Claude Code tool calls and sessions
- **Failure Detection**: MAST-based detection of agent failure modes (F4-F16)
- **Self-Healing**: Automatic fix injection for common issues (platform tier)
- **Privacy-First**: Local storage by default, opt-in cloud sync

## Planned Features

| Feature | Free (Local) | Platform |
|---------|--------------|----------|
| Trace capture | Yes | Yes |
| Basic detection (pass/fail) | Yes | Yes |
| Severity scores & explanations | - | Yes |
| Fix suggestions | - | Yes |
| Self-healing | - | Yes |
| Team dashboard | - | Yes |

## Detection Capabilities

Based on the MAST (Multi-Agent System Testing) taxonomy:

- **F4 Tool Misuse**: Wrong tool selection patterns
- **F6 Loop**: Infinite loop and repetition detection
- **F8 Context Overflow**: Token usage anomalies
- **F12 Cascade Failure**: Error propagation patterns
- **F15 Grounding Failure**: Outputs not supported by sources
- **F16 Retrieval Quality**: Poor document retrieval

## Requirements

- Python 3.10+
- Claude Code CLI

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [MAO Testing Platform](https://maotesting.com/)
