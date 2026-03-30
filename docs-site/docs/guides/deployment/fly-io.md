# Fly.io Deployment

Deploy the Pisama backend to [Fly.io](https://fly.io) for low-latency, globally distributed hosting.

## Backend Deployment

```bash
cd backend

# Create the app
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

## Dockerfile

The `backend/Dockerfile` is production-ready:

- Python 3.11-slim base image
- Non-root user (`mao`) for security
- CPU-only PyTorch for sentence-transformers (smaller image)
- Built-in health check on `/health`
- Configurable port via `$PORT` environment variable

## Scaling

```bash
# Scale to 2 instances
fly scale count 2

# Increase memory (embedding models need ~1GB)
fly scale memory 1024

# View current scaling
fly scale show
```

## Database Options

Fly.io does not provide managed PostgreSQL with pgvector. Options:

| Provider | Recommended For | pgvector |
|---|---|---|
| Supabase | Hobby / Startup | Pre-installed |
| Neon | Serverless workloads | Available |
| AWS RDS | Enterprise | Manual enable |
| Fly Postgres | Simple setup | Manual enable |

Ensure you enable the pgvector extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Frontend Deployment

Deploy the frontend to Vercel (recommended) or as a separate Fly.io app:

=== "Vercel (Recommended)"

    ```bash
    cd frontend
    vercel --prod
    ```

    Set `NEXT_PUBLIC_API_URL` to your Fly.io backend URL.

=== "Fly.io"

    ```bash
    cd frontend
    fly launch --name pisama-web --no-deploy
    fly secrets set \
      NEXT_PUBLIC_API_URL="https://pisama-api.fly.dev/api/v1" \
      NEXTAUTH_SECRET=$(openssl rand -base64 32) \
      NEXTAUTH_URL="https://pisama-web.fly.dev"
    fly deploy
    ```

## Health Check

```bash
curl https://pisama-api.fly.dev/health
# {"status": "healthy", "database": "ok", "redis": "ok"}
```

## Monitoring

Fly.io provides built-in logging and metrics:

```bash
# View logs
fly logs

# View metrics
fly dashboard
```

Pisama also exposes Prometheus metrics:

```bash
curl https://pisama-api.fly.dev/api/v1/metrics
```
