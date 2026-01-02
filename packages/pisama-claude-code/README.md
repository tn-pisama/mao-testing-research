# PISAMA Claude Code Adapter

Claude Code integration for the PISAMA agent forensics platform.

## Overview

This package provides real-time detection and self-healing for Claude Code sessions by:

1. **Capturing traces** from Claude Code tool calls via hooks
2. **Detecting issues** using pisama-core detection algorithms
3. **Injecting fixes** via stderr messages visible to Claude
4. **Blocking** problematic tool calls when severity is high

## Installation

```bash
# Install from packages directory
pip install -e packages/pisama-core
pip install -e packages/pisama-claude-code

# Install hooks to ~/.claude/
python -m pisama_claude_code.install
```

## Configuration

PISAMA configuration lives in `~/.claude/pisama/config.json`:

```json
{
  "self_healing": {
    "enabled": true,
    "mode": "manual",
    "severity_threshold": 40,
    "auto_fix_types": ["break_loop", "add_delay", "switch_strategy"],
    "blocked_fixes": ["delete_file", "git_push", "external_api"],
    "max_auto_fixes": 10,
    "cooldown_seconds": 30
  },
  "monitoring": {
    "enabled": true,
    "pattern_window": 10,
    "alert_on_warning": false
  }
}
```

### Modes

- **manual**: Alerts user and optionally blocks, requires user approval for fixes
- **auto**: Automatically applies approved fix types
- **report**: Logs issues but never blocks

## Hook Setup

Add to `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolCall": [
      {
        "command": "~/.claude/hooks/pisama-pre.sh",
        "timeout": 5000
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

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Claude Code                                │
│                                                                  │
│  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐ │
│  │  Pre Hook    │──────▶│   Guardian   │──────▶│  Post Hook   │ │
│  │  (capture)   │       │  (detect)    │       │  (capture)   │ │
│  └──────────────┘       └──────┬───────┘       └──────────────┘ │
│                                │                                 │
└────────────────────────────────┼─────────────────────────────────┘
                                 │
                                 ▼
                    ┌───────────────────────┐
                    │     pisama-core       │
                    ├───────────────────────┤
                    │  • Detection Engine   │
                    │  • Scoring Engine     │
                    │  • Healing Engine     │
                    │  • Enforcement        │
                    └───────────────────────┘
```

## Components

### ClaudeCodeAdapter

Implements `PlatformAdapter` interface for Claude Code:

```python
from pisama_claude_code import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter()

# Convert hook data to universal span
span = adapter.capture_span(hook_data)

# Store trace
adapter.store_span(span)

# Inject fix directive
adapter.inject_fix(
    directive="Break the loop and try a different approach",
    level=EnforcementLevel.DIRECT,
    session_id="session-123",
)
```

### Guardian

Real-time detection and intervention:

```python
from pisama_claude_code.guardian import Guardian

guardian = Guardian()

# Analyze tool call
result = await guardian.analyze(hook_data, session_id)

if result.should_block:
    sys.exit(1)  # Block the tool call
```

### TraceStorage

Local storage for traces:

```python
from pisama_claude_code import TraceStorage

storage = TraceStorage(traces_dir)

# Get recent tool sequence
tools = storage.get_tool_sequence(limit=10)

# Get recent spans
spans = storage.get_recent(limit=10, session_id="session-123")
```

## Detection Patterns

The guardian detects:

- **Loop patterns**: Same tool repeated consecutively
- **Cyclic patterns**: Repeating sequences of tools
- **Low diversity**: Using the same few tools repeatedly
- **Coordination failures**: Escalation issues
- **Cost anomalies**: Excessive API usage

## Fix Injection

Fixes are injected via stderr which Claude sees in its context:

```
[PISAMA Guardian Alert]
Severity: 65/100
Issues:
  - Loop detected: Read -> Read -> Read (5x)

DIRECTIVE: Break the loop and try a different approach

Use /pisama-intervene to review and decide how to proceed.
```

## Enforcement Levels

1. **SUGGEST** (1-39 severity): Soft suggestion via stderr
2. **DIRECT** (40-59): Direct instruction + MCP alert
3. **BLOCK** (60-79): Block tool call, require acknowledgment
4. **TERMINATE** (80-100): Terminate session

## Audit Logging

All events are logged to `~/.claude/pisama/audit_log.jsonl`:

```json
{"timestamp": "2024-01-02T12:00:00Z", "type": "intervention", "severity": 65, "issues": ["Loop detected"], "action": "blocked_for_approval"}
```

## Development

```bash
# Install dev dependencies
pip install -e "packages/pisama-claude-code[dev]"

# Run tests
pytest packages/pisama-claude-code/tests/
```

## License

MIT
