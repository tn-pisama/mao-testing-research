# pisama-claude-code

Trace capture and failure detection for Claude Code sessions.

[![PyPI version](https://badge.fury.io/py/pisama-claude-code.svg)](https://badge.fury.io/py/pisama-claude-code)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick Start

```bash
# Install
pip install pisama-claude-code

# Install hooks to ~/.claude/
pisama-cc install

# Use Claude Code normally - traces are captured automatically
claude

# Analyze captured traces for failures
pisama-cc analyze --last 100
```

## Features

| Feature | Free (Local) | Platform (Connected) |
|---------|--------------|----------------------|
| Trace capture | ✅ | ✅ |
| Failure detection (detected/ok) | ✅ | ✅ |
| Severity scores & explanations | ❌ | ✅ |
| Fix suggestions | ❌ | ✅ |
| Self-healing | ❌ | ✅ |
| Export traces | ✅ | ✅ |
| Sync to platform | ❌ | ✅ |
| Team dashboard | ❌ | ✅ |
| Cross-session analytics | ❌ | ✅ |

### Free Tier
- **Trace capture**: Full local trace storage
- **Detection**: Boolean results (detected/not detected)
- **Export**: Export traces to JSONL files

### Platform Tier
- **Full detection**: Severity scores, explanations, fix suggestions
- **Self-healing**: Automatic fix injection for common issues
- **Platform sync**: Upload traces for team collaboration
- **Dashboard**: Visual analytics and cross-session insights

## Detection Modes

The package detects MAST failure modes including:

- **F4 Tool Misuse**: Using Bash for file operations instead of dedicated tools
- **F6 Loop**: Consecutive repeated tool calls
- **F8 Context Overflow**: Token usage anomalies
- **F12 Cascade Failure**: Error propagation patterns
- **F15 Grounding Failure**: Outputs not supported by sources
- **F16 Retrieval Quality**: Poor document retrieval

## CLI Commands

```bash
pisama-cc install         # Install hooks to ~/.claude/hooks/
pisama-cc uninstall       # Remove hooks
pisama-cc status          # Show installation and connection status
pisama-cc config          # View/edit configuration
pisama-cc traces          # View recent traces
pisama-cc analyze         # Run local failure detection
pisama-cc export          # Export traces to file
pisama-cc connect         # Connect to MAO Testing platform
pisama-cc sync            # Upload traces to platform
```

## Usage Examples

### Analyze Recent Session

```bash
# Analyze last 100 traces for failures
pisama-cc analyze --last 100

# Output:
# F4 Tool Misuse: OK
# F6 Loop: 12 consecutive repeats detected
# F15 Grounding: OK
```

### Export Traces

```bash
# Export last 50 traces to file
pisama-cc export --last 50 -o traces.jsonl

# Export with filtering
pisama-cc export --last 100 --tool Bash -o bash-traces.jsonl
```

### Connect to Platform

```bash
# Connect with API key
pisama-cc connect --api-key pk_live_xxx

# Sync traces to platform
pisama-cc sync --last 100
```

## Privacy

- **Local by default**: All traces stored locally in `~/.claude/pisama/traces/`
- **Automatic redaction**: API keys, passwords, and secrets are automatically redacted
- **Path anonymization**: Home directory paths are replaced with `~/`
- **Opt-in cloud**: Sync to platform requires explicit connection

### What Is Captured

| Data | Captured | Synced to Cloud |
|------|----------|-----------------|
| Tool names | :white_check_mark: | :white_check_mark: |
| Timestamps | :white_check_mark: | :white_check_mark: |
| Session IDs | :white_check_mark: | :white_check_mark: |
| Tool inputs | :white_check_mark: | :white_check_mark: (sanitized) |
| File contents | :x: | :x: |
| Secrets/API keys | :x: (redacted) | :x: |

## Configuration

Configuration lives in `~/.claude/pisama/config.json`:

```json
{
  "self_healing": {
    "enabled": true,
    "mode": "manual",
    "severity_threshold": 40
  },
  "monitoring": {
    "enabled": true,
    "pattern_window": 10
  }
}
```

### Modes

- **manual**: Alerts and requires user approval for fixes
- **auto**: Automatically applies approved fix types
- **report**: Logs issues but never blocks

## Requirements

- Python 3.10+
- Claude Code CLI

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [Documentation](https://docs.maotesting.com/claude-code/)
- [MAO Testing Platform](https://app.maotesting.com/)
- [GitHub Issues](https://github.com/mao-testing/pisama-claude-code/issues)
