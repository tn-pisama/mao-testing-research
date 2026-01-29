# Moltbot Integration for PISAMA

This directory contains Docker configuration for running Moltbot as a testing target for PISAMA.

## Architecture

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   Moltbot    │◄────────│   Adapter    │────────►│   PISAMA     │
│   Gateway    │ WS tap  │  (Observer)  │  HTTP   │   Backend    │
│  :18789      │         │              │         │   :8000      │
└──────────────┘         └──────────────┘         └──────────────┘
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Anthropic API key

### 1. Set environment variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export PISAMA_API_KEY=your-pisama-api-key
```

### 2. Launch PISAMA + Moltbot

```bash
# From repo root
docker-compose -f docker-compose.yml -f docker-compose.moltbot.yml up
```

### 3. Access services

- **Moltbot Dashboard**: http://localhost:18789
- **PISAMA Dashboard**: http://localhost:3000
- **PISAMA API**: http://localhost:8000/api/v1

## Testing Moltbot

### Test WebChat

1. Open Moltbot dashboard: http://localhost:18789
2. Send a message via WebChat
3. Check PISAMA dashboard for trace capture

### Trigger Test Scenarios

See `../../benchmarks/mast/moltbot/` for failure scenario scripts.

## Configuration

- **Moltbot config**: `./moltbot.json`
- **Adapter config**: Via environment variables in `docker-compose.moltbot.yml`

## Troubleshooting

### Moltbot not starting
- Verify ANTHROPIC_API_KEY is set
- Check logs: `docker-compose logs moltbot`

### Adapter not connecting
- Verify Moltbot is healthy: `docker-compose ps`
- Check adapter logs: `docker-compose logs moltbot-adapter`

### No traces in PISAMA
- Verify PISAMA_API_KEY is valid
- Check backend logs for ingestion errors
