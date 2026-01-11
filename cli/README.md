# MAO Healer

Self-healing agent for n8n workflows. Automatically detects and fixes AI agent failures.

## Quick Start

```bash
# Install
pip install mao-healer

# Initialize config
mao-healer init

# Edit ~/.mao-healer/config.yaml with your n8n settings

# Start server
mao-healer start
```

## Configuration

After running `mao-healer init`, edit `~/.mao-healer/config.yaml`:

```yaml
n8n:
  webhook_secret: "your-webhook-secret"
  api_url: "http://localhost:5678"
  api_key: "your-n8n-api-key"

auto_apply:
  enabled: true
  max_fixes_per_hour: 5
  git_backup: true

notifications:
  discord_webhook: "https://discord.com/api/webhooks/..."
```

## n8n Setup

1. Go to n8n Settings > API > Create API Key
2. Add the API key to your config
3. Create a workflow webhook to send execution results to MAO Healer

## Commands

| Command | Description |
|---------|-------------|
| `mao-healer init` | Create config file |
| `mao-healer start` | Start webhook server |
| `mao-healer status` | Show status and recent activity |
| `mao-healer test` | Send test notification |
| `mao-healer version` | Show version |
| `mao-healer detections` | List recent detections for feedback |
| `mao-healer feedback` | Submit feedback on a detection result |

### Feedback Commands

The feedback commands enable human grader feedback for detection evaluation:

```bash
# List recent detections
mao-healer detections --limit 10

# Submit feedback on a detection
mao-healer feedback <detection_id> --correct --reason "Valid loop detected"
mao-healer feedback <detection_id> --incorrect --reason "False positive - legitimate retry"
```

## Detection Modes

All detection is FREE and pattern-based:

| Mode | Detects |
|------|---------|
| F1 | Specification Mismatch |
| F2 | Context Neglect |
| F3 | Coordination Failure |
| F6 | State Corruption |
| F7 | Derailment |
| F8 | Infinite Loop |
| F12 | Resource Overflow |
| F14 | Communication Breakdown |

## License

MIT
