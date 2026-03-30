# Configuration

Pisama is configured through environment variables. This page covers all configuration options for the backend and frontend.

## Backend Environment Variables

### Required

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://localhost:5432/mao` |
| `JWT_SECRET` | JWT signing secret (32+ chars) | `openssl rand -base64 32` |

### Production

| Variable | Description |
|---|---|
| `ENVIRONMENT` | Set to `production` |
| `REDIS_URL` | Redis connection string (default: `redis://localhost:6379`) |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `STRIPE_SECRET_KEY` | Stripe API key (for billing) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |

### Optional / Tuning

| Variable | Default | Description |
|---|---|---|
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Sentence-transformers model for embeddings |
| `LOOP_DETECTION_WINDOW` | `7` | Number of states to check for loops |
| `STRUCTURAL_THRESHOLD` | `0.95` | Structural match threshold |
| `SEMANTIC_THRESHOLD` | `0.85` | Semantic similarity threshold |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window in seconds |
| `N8N_HOST` | -- | n8n instance URL for auto-sync |
| `N8N_API_KEY` | -- | n8n API key |
| `LOG_LEVEL` | `INFO` | Logging level |

### Enterprise Feature Flags

Set these to enable enterprise-tier features:

```bash
# Master switch (required for any enterprise feature)
FEATURE_ENTERPRISE_ENABLED=true

# Individual feature flags
FEATURE_ML_DETECTION=true        # ML-based detection, tiered escalation, LLM judge
FEATURE_OTEL_INGESTION=true      # Native OTEL ingestion
FEATURE_CHAOS_ENGINEERING=true   # Chaos injection testing
FEATURE_TRACE_REPLAY=true        # Historical trace replay
FEATURE_REGRESSION_TESTING=true  # Regression test suite
FEATURE_ADVANCED_EVALS=true      # Quality gates, retrieval quality
FEATURE_AUDIT_LOGGING=true       # Audit log capture
```

## Frontend Environment Variables

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL (e.g., `http://localhost:8000/api/v1`) |
| `NEXTAUTH_SECRET` | Yes | NextAuth signing secret |
| `NEXTAUTH_URL` | Yes | Frontend URL (e.g., `http://localhost:3000`) |
| `GOOGLE_CLIENT_ID` | Prod | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Prod | Google OAuth client secret |

## Detection Threshold Configuration

Detection thresholds can be adjusted per-tenant via the API:

```bash
curl -X PUT http://localhost:8000/api/v1/tenants/TENANT_ID/settings/thresholds \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "structural_threshold": 0.95,
    "semantic_threshold": 0.85,
    "loop_detection_window": 7
  }'
```

To view current defaults:

```bash
curl http://localhost:8000/api/v1/settings/thresholds/defaults
```

To preview changes before applying:

```bash
curl "http://localhost:8000/api/v1/tenants/TENANT_ID/settings/thresholds/preview?structural_threshold=0.90" \
  -H "Authorization: Bearer $TOKEN"
```

## Rate Limiting

| Scope | Limit |
|---|---|
| Global | 1000 requests per 60 seconds per IP |
| Auth endpoints | 10 requests per 60 seconds per IP |
| Exempt paths | `/health`, `/api/v1/health`, `/`, `OPTIONS` |

Rate limiting requires Redis. Without Redis, the app falls back to in-memory rate limiting (not suitable for multi-instance deployments).

## CORS Configuration

The backend accepts these headers:

- `Authorization`
- `Content-Type`
- `Accept`
- `X-MAO-API-Key`
- `X-MAO-Signature`
- `X-MAO-Timestamp`
- `X-MAO-Nonce`

Allowed methods: `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`

Credentials are enabled with a max-age of 3600 seconds.

## Security Checklist

Before deploying to production:

- [ ] `JWT_SECRET` is random, 32+ characters, not shared across environments
- [ ] `ENVIRONMENT=production` is set
- [ ] CORS origins are restricted to your frontend domain
- [ ] HTTPS is enforced (HSTS header auto-enabled in production)
- [ ] Stripe webhook secret is configured
- [ ] Database credentials use strong passwords
- [ ] Rate limiting is active (requires Redis)
- [ ] API keys are rotated periodically
