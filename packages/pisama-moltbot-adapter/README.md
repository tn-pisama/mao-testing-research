# PISAMA Moltbot Adapter

Observability bridge that connects Moltbot agent deployments to PISAMA for real-time failure detection and monitoring.

## Overview

The Moltbot Adapter taps into the Moltbot WebSocket gateway, converts agent events to PISAMA trace format (OTEL), and streams them to the PISAMA backend for analysis.

```
Moltbot Gateway → Adapter → PISAMA Backend → Detection Engine
```

## Features

- **Non-invasive monitoring**: WebSocket tap requires no changes to Moltbot
- **Real-time conversion**: Transforms Moltbot events to OTEL traces
- **Automatic export**: Periodically sends traces to PISAMA API
- **Graceful shutdown**: Ensures all traces are exported before exit

## Installation

### As a standalone package

```bash
pip install pisama-moltbot-adapter
```

### From source

```bash
cd packages/pisama-moltbot-adapter
pip install -e .
```

### Docker

```bash
docker build -t pisama-moltbot-adapter .
```

## Configuration

Set environment variables:

```bash
# Required
export PISAMA_API_KEY=your-api-key

# Optional (defaults shown)
export MOLTBOT_GATEWAY_URL=ws://127.0.0.1:18789
export PISAMA_API_URL=http://localhost:8000/api/v1
export PISAMA_TENANT_ID=  # For multi-tenant PISAMA
export LOG_LEVEL=INFO
```

## Usage

### Standalone

```bash
python -m pisama_moltbot_adapter.main
```

### Docker Compose

See `docker-compose.moltbot.yml` in the repo root.

### Programmatic

```python
import asyncio
from pisama_moltbot_adapter import MoltbotAdapter

adapter = MoltbotAdapter(
    moltbot_url="ws://localhost:18789",
    pisama_api_url="http://localhost:8000/api/v1",
    pisama_api_key="your-key",
)

asyncio.run(adapter.run())
```

## Event Mapping

| Moltbot Event | PISAMA Span Kind |
|---------------|------------------|
| `session.created` | Trace metadata |
| `message.received` | `USER_INPUT` |
| `agent.thinking` | `AGENT_TURN` |
| `tool.call` | `TOOL` |
| `tool.result` | `TOOL` (completion) |
| `message.sent` | `USER_OUTPUT` |
| `session.ended` | Trace finalization |
| `error` | `SYSTEM` with error status |

## Architecture

### Components

1. **MoltbotClient** (`client.py`)
   - WebSocket client for gateway connection
   - Event subscription and streaming

2. **MoltbotTraceConverter** (`converter.py`)
   - Converts Moltbot events to PISAMA traces
   - Maintains session-to-trace mapping
   - Handles span lifecycle

3. **PISAMAExporter** (`exporter.py`)
   - Sends traces to PISAMA API
   - Handles authentication and retries
   - Batches export for efficiency

4. **MoltbotAdapter** (`main.py`)
   - Orchestrates the pipeline
   - Periodic export scheduler
   - Graceful shutdown handling

## Development

### Run tests

```bash
pytest tests/
```

### Type checking

```bash
mypy src/
```

### Linting

```bash
ruff check src/
```

## Troubleshooting

### Cannot connect to Moltbot
- Verify Moltbot is running: `curl http://localhost:18789/`
- Check gateway URL configuration
- Review Moltbot logs for connection issues

### Traces not appearing in PISAMA
- Verify PISAMA_API_KEY is valid
- Check adapter logs for export errors
- Ensure PISAMA backend is accessible
- Test API manually: `curl -H "Authorization: Bearer $PISAMA_API_KEY" $PISAMA_API_URL/health`

### High memory usage
- Reduce export interval (default: 30s)
- Enable `clear_completed_traces()` more frequently
- Monitor active trace count

## License

MIT
