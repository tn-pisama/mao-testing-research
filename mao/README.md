# MAO CLI and MCP Server

Command-line interface and MCP server for the MAO (Multi-Agent Orchestration) Testing Platform.

## Installation

```bash
pip install mao-cli

# With MCP support
pip install mao-cli[mcp]

# With secure credential storage
pip install mao-cli[security]
```

## Quick Start

### CLI Setup

```bash
# Initialize configuration
mao config init

# Analyze a trace
mao debug trace-abc123

# Get fix suggestions
mao fix detection-xyz789
```

### CLI Commands

```bash
# Debug commands (analyze + detect)
mao debug <trace-id>           # Analyze specific trace
mao debug --last 5             # Analyze last 5 traces
mao debug --since 1h           # Analyze traces from last hour
mao debug trace-123 --fix      # Include fix suggestions

# Fix commands
mao fix <detection-id>         # Show fix suggestions
mao fix <detection-id> --apply # Apply recommended fix

# Watch for issues
mao watch                      # Stream new detections
mao watch --severity high      # Only high severity

# CI/CD
mao ci check                   # Run golden dataset checks
mao ci check --threshold 95    # Fail if accuracy < 95%

# Configuration
mao config init                # Interactive setup
mao config show                # Show current config
mao config set api-key         # Update API key (secure prompt)
```

### Command Aliases

```bash
mao d trace-123    # Short for 'debug'
mao w              # Short for 'watch'
mao f det-456      # Short for 'fix'
```

## MCP Server

The MCP server exposes MAO capabilities to AI assistants like Claude.

### Configuration

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "mao": {
      "command": "python",
      "args": ["-m", "mao.mcp.server", "http://localhost:8000", "YOUR_API_KEY"]
    }
  }
}
```

### Available Tools

| Tool | Description |
|------|-------------|
| `mao_analyze_trace` | Analyze a trace for agent failures |
| `mao_get_detections` | Get detections with optional filters |
| `mao_get_fix_suggestions` | Get code fix suggestions |
| `mao_get_trace` | Get full trace details |

### Security

- **Read-only**: No `apply_fix` tool exposed via MCP
- **Rate limited**: 60 requests per minute
- **Input validated**: All parameters validated
- **Audit logged**: All operations logged to `~/.mao/mcp_audit.log`

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success, no issues found |
| 1 | Issues found (detections) |
| 2 | Error (configuration, API, etc.) |

## Configuration

Config stored at `~/.mao/config.yaml`:

```yaml
endpoint: http://localhost:8000
tenant_id: default
output_format: table
colors: true
```

API key stored securely:
- macOS: Keychain
- Windows: Credential Manager
- Linux: Encrypted file (`~/.mao/credentials.enc`)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check .
```
