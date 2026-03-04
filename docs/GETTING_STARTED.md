# Getting Started with PISAMA

PISAMA is a multi-agent orchestration testing platform that detects failure modes in LLM agent systems.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 with pgvector extension
- Redis 7+
- Git

## Quick Start (Docker)

The fastest way to get PISAMA running locally:

```bash
git clone https://github.com/tn-pisama/mao-testing-research.git
cd mao-testing-research
docker compose up
```

This starts:
- **PostgreSQL** (pgvector) on port 5432
- **Redis** on port 6379
- **Backend** (FastAPI) on http://localhost:8000
- **Frontend** (Next.js) on http://localhost:3000

## Manual Setup

### 1. Database & Redis

```bash
# Start only infrastructure services
docker compose up postgres redis -d
```

Or install natively:
```bash
# macOS
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis

# Create database
createdb mao
psql mao -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — at minimum set:
#   DATABASE_URL=postgresql+asyncpg://localhost:5432/mao
#   JWT_SECRET=<run: openssl rand -base64 32>

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now available at http://localhost:8000. Check health at http://localhost:8000/health.

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local — at minimum set:
#   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
#   NEXTAUTH_SECRET=<run: openssl rand -base64 32>
#   NEXTAUTH_URL=http://localhost:3000

# Start the dev server
npm run dev
```

The frontend is now available at http://localhost:3000.

## Verify Setup

1. Open http://localhost:8000/health — should return `{"status": "healthy"}`
2. Open http://localhost:8000/docs — interactive API documentation (Swagger UI)
3. Open http://localhost:3000 — PISAMA dashboard

## Running Tests

```bash
# Backend tests
cd backend
pytest tests/ -v

# Calibration regression tests
pytest tests/test_calibration_regression.py -v

# Frontend E2E tests (public pages)
cd frontend
npm run test:public
```

## Project Structure

```
mao-testing-research/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/v1/         # REST API endpoints
│   │   ├── detection/      # Detection algorithms (41 detectors)
│   │   ├── detection_enterprise/  # Calibration, golden datasets
│   │   ├── ingestion/      # Trace parsing (OTEL, n8n)
│   │   ├── storage/        # Database models, migrations
│   │   ├── fixes/          # AI-powered fix suggestions
│   │   └── healing/        # Self-healing orchestration
│   └── tests/              # pytest test suite
├── frontend/               # Next.js 16 frontend
│   ├── src/app/            # App Router pages
│   ├── src/components/     # React components
│   └── tests/e2e/          # Playwright tests
├── packages/               # Python packages
│   ├── pisama-core/        # Core SDK
│   └── pisama-claude-code/ # Claude Code integration
├── cli/                    # CLI with MCP server
└── docs/                   # Documentation
```

## Key Environment Variables

### Backend (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | JWT signing secret (32+ chars) |
| `REDIS_URL` | No | Redis URL (default: redis://localhost:6379) |
| `GOOGLE_CLIENT_ID` | Prod | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Prod | Google OAuth client secret |
| `STRIPE_SECRET_KEY` | Prod | Stripe billing API key |
| `EMBEDDING_MODEL` | No | Sentence-transformers model (default: BAAI/bge-m3) |
| `N8N_HOST` | No | n8n instance URL for auto-sync |
| `N8N_API_KEY` | No | n8n API key |

### Frontend (`.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL |
| `NEXTAUTH_SECRET` | Yes | NextAuth signing secret |
| `NEXTAUTH_URL` | Yes | Frontend URL (http://localhost:3000) |
| `GOOGLE_CLIENT_ID` | Prod | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Prod | Google OAuth client secret |

## Next Steps

- [API Reference](./API_REFERENCE.md) — REST API documentation
- [Deployment Guide](./DEPLOYMENT.md) — Production deployment
- [Failure Modes Reference](./failure-modes-reference.md) — Detection algorithms
- [Testing Guide](./user-guide/testing-your-agents.md) — SDK & agent testing
