# Deployment Guide

PISAMA supports multiple deployment targets. This guide covers Docker Compose (local/staging) and Fly.io.

---

## Prerequisites

- Docker & Docker Compose
- PostgreSQL 16 with pgvector extension
- Redis 7+
- Domain name (production)

---

## Option 1: Docker Compose (Recommended for Local/Staging)

```bash
git clone https://github.com/tn-pisama/mao-testing-research.git
cd mao-testing-research
docker compose up
```

Services started:
- **PostgreSQL** (pgvector/pgvector:pg16) on port 5432
- **Redis** (redis:7-alpine) on port 6379
- **Backend** (FastAPI) on port 8000
- **Frontend** (Next.js) on port 3000

### Production Docker Compose

For production, override the defaults:

```yaml
# docker-compose.prod.yml
services:
  backend:
    environment:
      DATABASE_URL: postgresql+asyncpg://user:${DB_PASSWORD}@postgres:5432/mao
      JWT_SECRET: ${JWT_SECRET}
      REDIS_URL: redis://redis:6379
      ENVIRONMENT: production
      CORS_ORIGINS: https://your-domain.com
      GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID}
      GOOGLE_CLIENT_SECRET: ${GOOGLE_CLIENT_SECRET}
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    # Remove volume mount for production
    volumes: []

  frontend:
    environment:
      NEXT_PUBLIC_API_URL: https://api.your-domain.com/api/v1
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      NEXTAUTH_URL: https://your-domain.com
    command: npm run start
    volumes: []
```

Run with:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Option 2: Fly.io

### Backend

```bash
cd backend

# Create app
fly launch --name pisama-api --no-deploy

# Set secrets
fly secrets set \
  JWT_SECRET=$(openssl rand -base64 32) \
  DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/mao" \
  REDIS_URL="redis://host:6379" \
  ENVIRONMENT=production \
  CORS_ORIGINS="https://your-frontend.vercel.app"

# Deploy
fly deploy
```

The `backend/Dockerfile` is production-ready:
- Python 3.11-slim base
- Non-root user (`mao`)
- CPU-only PyTorch for sentence-transformers
- Built-in health check on `/health`
- Configurable port via `$PORT`

### Scaling

```bash
# Scale to 2 instances
fly scale count 2

# Set memory (embedding models need ~1GB)
fly scale memory 1024
```

---

## Database Setup

### Managed PostgreSQL

Use any PostgreSQL 16+ provider with pgvector support:
- **Fly Postgres** (`fly postgres create`)
- **Supabase** (pgvector pre-installed)
- **Neon** (pgvector available)
- **AWS RDS** (enable pgvector extension)

### Enable pgvector

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Run Migrations

```bash
cd backend
alembic upgrade head
```

---

## Database Migrations

All schema changes use Alembic. Migrations live in `backend/alembic/versions/`.

### Common Commands

```bash
cd backend

# Apply all pending migrations
alembic upgrade head

# Check current migration version
alembic current

# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade <revision_id>

# View migration history
alembic history --verbose

# Generate a new migration from model changes
alembic revision --autogenerate -m "description of change"
```

### Pre-Deployment Checklist

1. **Backup the database** before any migration:
   ```bash
   pg_dump -U mao -h localhost mao > backup_$(date +%Y%m%d_%H%M%S).sql
   ```
2. **Test the migration on staging** — run `alembic upgrade head` against a staging DB first.
3. **Review the generated SQL** — run `alembic upgrade head --sql` to inspect without applying.
4. **Run the migration** on production.
5. **Verify** — check `alembic current` matches the expected head revision.
6. **Smoke test** — hit `/health` and run a few API calls to confirm the app works.

### Rollback Plan

If a migration fails or causes issues:

```bash
# Rollback the last migration
alembic downgrade -1

# Restore from backup if needed
psql -U mao -h localhost mao < backup_YYYYMMDD_HHMMSS.sql
```

### Common Issues

| Problem | Solution |
|---------|----------|
| `FAILED: Target database is not up to date` | Run `alembic upgrade head` before generating new migrations |
| `FAILED: Can't locate revision` | Check `alembic history`; you may have divergent heads — run `alembic merge heads` |
| Migration hangs | Another connection holds a lock — check `pg_stat_activity` and terminate idle transactions |
| `relation already exists` | Migration was partially applied — check `alembic current`, manually fix or stamp: `alembic stamp <revision>` |
| pgvector extension missing | Run `CREATE EXTENSION IF NOT EXISTS vector;` before the migration |

---

## Redis Setup

Redis is used for rate limiting and caching. Options:
- **Upstash** — serverless Redis, free tier available
- **Redis Cloud** — managed Redis

If Redis is unavailable, the app falls back to in-memory rate limiting (not suitable for multi-instance deployments).

---

## Environment Variables Reference

### Backend (Required)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | JWT signing secret (32+ chars, `openssl rand -base64 32`) |
| `REDIS_URL` | Redis connection string (default: `redis://localhost:6379`) |

### Backend (Production)

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | Set to `production` |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `STRIPE_SECRET_KEY` | Stripe API key (for billing) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |

### Backend (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Sentence-transformers model |
| `LOOP_DETECTION_WINDOW` | `7` | States to check for loops |
| `STRUCTURAL_THRESHOLD` | `0.95` | Structural match threshold |
| `SEMANTIC_THRESHOLD` | `0.85` | Semantic similarity threshold |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window |
| `N8N_HOST` | — | n8n instance URL for auto-sync |
| `N8N_API_KEY` | — | n8n API key |
| `LOG_LEVEL` | `INFO` | Logging level |

### Frontend

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL (e.g., `https://api.pisama.com/api/v1`) |
| `NEXTAUTH_SECRET` | NextAuth signing secret |
| `NEXTAUTH_URL` | Frontend URL |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

---

## Security Checklist

- [ ] `JWT_SECRET` is random, 32+ characters, not shared
- [ ] `ENVIRONMENT=production` is set
- [ ] CORS origins are restricted to your frontend domain
- [ ] HTTPS is enforced (HSTS header auto-enabled)
- [ ] Stripe webhook secret is configured
- [ ] Database credentials use strong passwords
- [ ] Rate limiting is active (requires Redis)
- [ ] API keys are rotated periodically

---

## Monitoring

### Health Check

```bash
curl https://api.your-domain.com/health
# {"status": "healthy", "database": "ok", "redis": "ok"}
```

### Prometheus Metrics

```bash
curl https://api.your-domain.com/api/v1/metrics
```

### Detector Status

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.your-domain.com/api/v1/diagnostics/detector-status
```

---

## CI/CD

GitHub Actions workflows are included:

- **`.github/workflows/ci.yml`** — Runs on PRs: smoke tests, backend tests (with Postgres/Redis), calibration gate, frontend build, lint, security scan
- **`.github/workflows/deploy.yml`** — Auto-deploys on push to main via Fly.io/Vercel
