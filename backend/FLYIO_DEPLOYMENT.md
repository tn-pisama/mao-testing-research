# Fly.io Deployment Guide - Multi-Provider LLM Setup

## Required API Keys for Production

After implementing multi-provider LLM support, you need to set the following secrets in Fly.io:

### Set API Keys

```bash
# Navigate to backend directory
cd backend

# Set Anthropic API key (Claude - Tier 2/3)
fly secrets set ANTHROPIC_API_KEY="your-anthropic-api-key"

# Set Google API key (Gemini - Tier 1 low-cost)
fly secrets set GOOGLE_API_KEY="your-google-api-key"

# Set OpenAI API key (GPT/O3 - Tier 2 cost-optimized)
fly secrets set OPENAI_API_KEY="your-openai-api-key"
```

### Verify Secrets

```bash
# List all secrets (values are hidden)
fly secrets list
```

Expected output:
```
NAME                    DIGEST          CREATED AT
ANTHROPIC_API_KEY       xxxxx...        2026-01-22T...
GOOGLE_API_KEY          xxxxx...        2026-01-22T...
OPENAI_API_KEY          xxxxx...        2026-01-22T...
DATABASE_URL            xxxxx...        ...
JWT_SECRET              xxxxx...        ...
...
```

### Deploy Updated Code

```bash
# Deploy to Fly.io
fly deploy

# Monitor deployment
fly logs
```

## Multi-Provider Tier Configuration

### Tier 1: Low-Stakes Detection (Gemini Flash Lite)
- **Failure Modes**: F3, F7, F11, F12
- **Cost**: $0.0001/judgment (87% cheaper than Haiku 3.5)
- **Provider**: Google Gemini
- **Fallback**: Haiku 4.5 if Gemini rate-limited

### Tier 2: Default Detection (Claude Sonnet 4)
- **Failure Modes**: F1, F2, F4, F5, F10, F13
- **Cost**: $0.0048/judgment
- **Provider**: Anthropic Claude
- **Alternative**: OpenAI O3 (cost-optimized mode, 33% savings)

### Tier 3: High-Stakes Detection (Claude Sonnet 4 + Thinking)
- **Failure Modes**: F6, F8, F9, F14
- **Cost**: $0.0163/judgment
- **Provider**: Anthropic Claude with extended thinking
- **Use Case**: Complex failures requiring deep reasoning

## Environment Variables Reference

| Variable | Provider | Required | Purpose |
|----------|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic | Yes | Claude models (Tier 2/3) |
| `GOOGLE_API_KEY` | Google | Yes | Gemini models (Tier 1) |
| `OPENAI_API_KEY` | OpenAI | Optional | O3 cost-optimized (Tier 2 alt) |

## Cost Monitoring

After deployment, monitor costs via:

```bash
# View application logs with cost tracking
fly logs --app mao-api | grep "MAST Judge"
```

Look for log entries like:
```
MAST Judge (gemini-flash-lite, google): F3 -> NO (conf=0.95, tokens=600, cost=$0.0001)
MAST Judge (sonnet-4, anthropic): F1 -> YES (conf=0.88, tokens=1000, cost=$0.0048)
```

## Troubleshooting

### Gemini Rate Limits
If you see "Gemini API overloaded" errors:
- This is normal during high load
- System automatically falls back to Haiku 4.5
- No action needed, but costs will be 5x higher during fallback

### Missing API Keys
If deployment fails with "No API key" errors:
```bash
# Verify secrets are set
fly secrets list

# Re-set any missing keys
fly secrets set GOOGLE_API_KEY="your-key"
```

### Cost Verification
Check cost breakdown per provider:
```python
from app.detection.llm_judge import get_cost_tracker

tracker = get_cost_tracker()
summary = tracker.get_provider_summary()
print(summary)
```

## Rollback Plan

If multi-provider causes issues:

1. **Quick Fix**: Change Tier 1 to use Haiku instead of Gemini
   ```bash
   # Edit backend/app/detection/llm_judge/_models.py
   # Change: LOW_STAKES_MODEL_KEY = "gemini-flash-lite"
   # To:     LOW_STAKES_MODEL_KEY = "haiku-4.5"

   fly deploy
   ```

2. **Full Rollback**: Revert to previous commit
   ```bash
   git revert fe7ecac2
   fly deploy
   ```

## Production Checklist

- [ ] Set `ANTHROPIC_API_KEY` in Fly.io secrets
- [ ] Set `GOOGLE_API_KEY` in Fly.io secrets
- [ ] Set `OPENAI_API_KEY` in Fly.io secrets (optional)
- [ ] Deploy updated code: `fly deploy`
- [ ] Verify all 3 tiers working in logs
- [ ] Monitor cost per provider
- [ ] Set up alerts for API failures
- [ ] Document fallback behavior for team
