# Installation

Pisama can be installed via Docker Compose (recommended) or manually.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 with pgvector extension
- Redis 7+
- Git

## Docker Compose (Recommended)

The fastest way to get Pisama running locally:

```bash
git clone https://github.com/tn-pisama/mao-testing-research.git
cd mao-testing-research
docker compose up
```

This starts:

| Service | Image | Port |
|---|---|---|
| **PostgreSQL** | pgvector/pgvector:pg16 | 5432 |
| **Redis** | redis:7-alpine | 6379 |
| **Backend** | FastAPI | 8000 |
| **Frontend** | Next.js | 3000 |

## Manual Setup

### 1. Database and Redis

Start only infrastructure services via Docker:

```bash
docker compose up postgres redis -d
```

Or install natively on macOS:

```bash
# Install and start services
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis

# Create database with pgvector
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
# Edit .env -- at minimum set:
#   DATABASE_URL=postgresql+asyncpg://localhost:5432/mao
#   JWT_SECRET=<run: openssl rand -base64 32>

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now available at [http://localhost:8000](http://localhost:8000). Check health at [http://localhost:8000/health](http://localhost:8000/health).

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local -- at minimum set:
#   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
#   NEXTAUTH_SECRET=<run: openssl rand -base64 32>
#   NEXTAUTH_URL=http://localhost:3000

# Start the dev server
npm run dev
```

The frontend is now available at [http://localhost:3000](http://localhost:3000).

## Verify Setup

1. Open [http://localhost:8000/health](http://localhost:8000/health) -- should return `{"status": "healthy"}`
2. Open [http://localhost:8000/docs](http://localhost:8000/docs) -- interactive API documentation (Swagger UI)
3. Open [http://localhost:3000](http://localhost:3000) -- Pisama dashboard

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
│   │   ├── detection/      # Detection algorithms (21 detectors)
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
