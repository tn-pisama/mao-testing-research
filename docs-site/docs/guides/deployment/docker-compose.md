# Docker Compose Deployment

Docker Compose is the recommended way to run Pisama locally or in staging environments.

## Quick Start

```bash
git clone https://github.com/tn-pisama/mao-testing-research.git
cd mao-testing-research
docker compose up
```

This starts all services:

| Service | Image | Port | Purpose |
|---|---|---|---|
| PostgreSQL | pgvector/pgvector:pg16 | 5432 | Database with vector extension |
| Redis | redis:7-alpine | 6379 | Rate limiting and caching |
| Backend | FastAPI | 8000 | REST API |
| Frontend | Next.js | 3000 | Dashboard |

## Production Configuration

For production deployments, create an override file:

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
    volumes: []

  frontend:
    environment:
      NEXT_PUBLIC_API_URL: https://api.your-domain.com/api/v1
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      NEXTAUTH_URL: https://your-domain.com
    command: npm run start
    volumes: []
```

Run with the override:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Infrastructure Only

If you want to run the backend and frontend outside Docker (for development), start only the infrastructure:

```bash
docker compose up postgres redis -d
```

Then follow the manual setup instructions in [Installation](../../getting-started/installation.md).

## Database Setup

### Enable pgvector

If using a separate PostgreSQL instance:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Run Migrations

```bash
cd backend
alembic upgrade head
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "database": "ok", "redis": "ok"}
```

## Monitoring

```bash
# Prometheus metrics
curl http://localhost:8000/api/v1/metrics

# Detector status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/diagnostics/detector-status
```
