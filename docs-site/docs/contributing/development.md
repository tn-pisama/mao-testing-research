# Development Setup

Get productive with PISAMA development within a day.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 with pgvector extension
- Redis 7+
- Git

## Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies (including dev)
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Set DATABASE_URL and JWT_SECRET at minimum

# Start infrastructure
docker compose up postgres redis -d

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL, NEXTAUTH_SECRET, NEXTAUTH_URL

# Start dev server
npm run dev
```

## Running Tests

```bash
# All backend tests
cd backend && pytest tests/ -v

# Specific detector tests
pytest tests/ -k "test_loop"

# Calibration regression tests
pytest tests/test_calibration_regression.py -v

# Detection enterprise tests
pytest tests/detection_enterprise/

# Frontend E2E tests
cd frontend && npm run test:public
```

## Test Organization

```
backend/tests/
├── unit/                     # Individual detector tests
├── integration/              # Multi-component tests
├── detection_enterprise/     # Enterprise-tier detector tests
├── e2e/                      # End-to-end pipeline tests
└── fixtures/
    └── golden/               # Golden dataset files
```

## Code Style Guidelines

- **No OpenAI**: Claude/Anthropic models only for all LLM calls
- **No mock data**: Use real data or golden dataset entries
- **Simple implementations**: Choose the simplest approach that works
- **Edit over create**: Prefer modifying existing files over creating new ones
- **Security first**: Input validation and authentication on all endpoints
- **Test-driven**: Write tests for new detectors and features
- **Import rules**: ICP code must not import from enterprise modules; enterprise code can import from ICP

## Key Directories

| Directory | Purpose |
|---|---|
| `backend/app/api/v1/` | REST API endpoints |
| `backend/app/detection/` | ICP-tier detection algorithms |
| `backend/app/detection_enterprise/` | Enterprise ML/tiered detection |
| `backend/app/detection/llm_judge/` | LLM-as-Judge verification |
| `backend/app/ingestion/` | Trace parsing |
| `backend/app/storage/` | Database models |
| `backend/app/fixes/` | Fix suggestion generation |
| `backend/app/healing/` | Self-healing orchestration |
| `backend/app/core/` | Auth, security, rate limiting |
| `backend/tests/` | Test suite |
| `frontend/src/app/` | Next.js pages |
| `frontend/src/components/` | React components |
| `packages/` | Python packages |
| `cli/` | CLI with MCP server |

## CI/CD

GitHub Actions workflows:

- **`.github/workflows/ci.yml`**: Runs on PRs -- smoke tests, backend tests (with Postgres/Redis), calibration gate, frontend build, lint, security scan
- **`.github/workflows/deploy.yml`**: Auto-deploys on push to main via Render/Vercel

## Useful Commands

```bash
# Run calibration
cd backend && python -m app.detection_enterprise.calibrate

# Run calibration with multi-trial variance
cd backend && python -m app.detection_enterprise.calibrate --tiered --trials 3

# Generate hard samples for saturated detectors
cd backend && python -m app.detection_enterprise.calibrate --generate-hard --hard-count 10

# View detector status
curl http://localhost:8000/api/v1/diagnostics/detector-status

# Interactive API docs
open http://localhost:8000/docs
```
