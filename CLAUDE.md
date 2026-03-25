# PISAMA

Multi-Agent Orchestration Testing Platform - Failure detection for LLM agent systems.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PISAMA Platform                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Frontend   │  │   Backend    │  │     SDK      │  │     CLI      │    │
│  │   (Next.js)  │  │  (FastAPI)   │  │   (Python)   │  │   (Python)   │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         └────────────────┼─────────────────┴─────────────────┘             │
│                          │                                                  │
│                          ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Core Services                                 │  │
│  ├──────────────┬──────────────┬──────────────┬──────────────────────── │  │
│  │  Detection   │   Ingestion  │   Storage    │   Fixes Generator      │  │
│  │  Engine      │   Pipeline   │   Layer      │   (AI-powered)         │  │
│  │  - Loop      │   - OTEL     │   - Postgres │   - Code suggestions   │  │
│  │  - Corrupt   │   - n8n      │   - pgvector │   - Best practices     │  │
│  │  - Persona   │   - Custom   │   - SQLAlch  │                        │  │
│  │  - Deadlock  │              │              │                        │  │
│  └──────────────┴──────────────┴──────────────┴────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, pgvector, Alembic
- **Frontend**: Next.js 16 (App Router), React 18, TailwindCSS, NextAuth (Google OAuth)
- **SDK**: Python package with LangGraph/AutoGen/CrewAI/n8n/Dify/OpenClaw integrations
- **CLI**: Click-based CLI with MCP server support
- **Infrastructure**: Fly.io (backend), Vercel (frontend + docs), PostgreSQL 16 + pgvector

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `backend/app/api/v1/` | REST API endpoints |
| `backend/app/detection/` | ICP-tier detection algorithms |
| `backend/app/detection_enterprise/` | Enterprise ML/tiered detection |
| `backend/app/detection/llm_judge/` | LLM-as-Judge verification |
| `backend/app/ingestion/` | Trace parsing (OTEL, n8n, universal) |
| `backend/app/storage/` | Database models and migrations |
| `backend/app/fixes/` | AI-powered fix suggestions |
| `backend/app/healing/` | Self-healing orchestration |
| `backend/app/benchmark/` | MAST benchmark tooling |
| `backend/app/core/` | Auth, security, rate limiting |
| `backend/tests/` | pytest tests (87 files) |
| `frontend/src/app/` | Next.js pages and components |
| `packages/` | Python packages (pisama-core, agent-sdk) |
| `cli/` | CLI with MCP server support |
| `docs/` | Technical documentation (25+ files) |

## Detection Algorithms

### ICP Tier (Always Available)
| Detector | Purpose |
|----------|---------|
| loop | Exact, structural, semantic loop detection |
| corruption | State corruption and invalid transitions |
| persona | Persona drift and role confusion |
| coordination | Agent handoff and communication failures |
| hallucination | Factual inaccuracy detection |
| injection | Prompt injection attempts |
| overflow | Context window exhaustion |
| derailment | Task focus deviation |
| context | Context neglect in responses |
| communication | Inter-agent communication breakdown |
| specification | Output vs spec mismatch |
| decomposition | Task breakdown failures |
| workflow | Workflow execution issues |
| withholding | Information withholding |
| completion | Premature/delayed task completion |
| cost | Token/cost budget tracking |
| convergence | Metric plateau, regression, thrashing, divergence |

### Enterprise Tier (Feature Flags Required)
- `ml_detection` flag: ML-based detection (ml_detector_v4), tiered escalation, LLM judge
- `advanced_evals` flag: Quality gates, retrieval quality, role usurpation

## Feature Flags

| Flag | Tier | Features Enabled |
|------|------|------------------|
| (none) | ICP | All base detectors, basic healing |
| `ml_detection` | Enterprise | ML detector v4, tiered detection, LLM judge |
| `advanced_evals` | Enterprise | Quality gates, retrieval quality |

## Testing

- Test files: `test_*.py` in `backend/tests/` (104 files)
- Golden datasets: `backend/tests/fixtures/golden/` + `backend/data/golden_dataset_expanded.json`
- Run tests: `pytest backend/tests/`
- Test organization: unit, integration, e2e, detection_enterprise
- Calibration: 42 detectors, 31 production (F1 ≥ 0.70), 11 beta
- E2E strategy: See `docs/E2E_TESTING_STRATEGY.md`

## Architecture Principles

1. **Tiered Detection**: Always start at Tier 1 (hash), escalate only if needed (Tier 2: state delta, Tier 3: embeddings, Tier 4: LLM, Tier 5: human)
2. **OTEL-First**: All traces use OpenTelemetry with `gen_ai.*` semantic conventions
3. **Framework-Agnostic Core**: No LangGraph/CrewAI/AutoGen imports in core - use adapters in packages/
4. **Cost-Aware**: Track tokens, compute time, $ cost per detection (target: $0.05/trace)
5. **Safety-First Healing**: Require checkpoints, rollback capability, approval policies for high-risk fixes

## Deployment

### Production Topology
- **Backend**: Fly.io (`mao-api.fly.dev`), 2 machines, auto-scale, config in `backend/fly.toml`
- **Frontend**: Vercel (auto-deploy on push to main), config in root `vercel.json`
- **Docs**: Vercel (`docs.pisama.com`), MkDocs Material, auto-deploy on push
- **Database**: Fly Postgres (connected via `DATABASE_URL` secret)
- **Redis**: Fly Redis (connected via `REDIS_URL` secret)

### Backend Deployment (Fly.io)

```bash
cd backend && flyctl deploy --remote-only -a mao-api
```

**Pre-deploy checklist:**
1. Run `pytest tests/test_detection.py tests/test_tier1_capabilities.py -q` locally
2. If you added a Python dependency, add it to BOTH `requirements.txt` AND `requirements-prod.txt`
3. If you added a new detection module, verify it imports: `JWT_SECRET=... python3 -c "from app.main import app"`
4. If you modified models.py, create an Alembic migration in `app/storage/migrations/versions/`

**How it works:**
- `fly.toml` defines the app config (port 8000, health check, auto-scale)
- `Dockerfile` uses `requirements-prod.txt` (NOT `requirements.txt`)
- `.dockerignore` excludes `data/`, `tests/`, `scripts/` (keeps image under 900MB)
- Release command runs `python -m alembic upgrade head` before starting
- Health check: `GET /api/v1/health` must return `{"status":"healthy"}`

**Common issues:**
- `NameError: name 'Dict' is not defined` → Python 3.11 needs `from typing import Dict` (not `dict` lowercase)
- `alembic_version column too short` → Run `ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)` on DB
- Health check timeout → App crashed on startup. Run `flyctl logs -a mao-api` to see the import error

**Secrets (set via `flyctl secrets set -a mao-api KEY=value`):**
- `DATABASE_URL` — PostgreSQL connection string (asyncpg)
- `JWT_SECRET` — Min 32 chars, no word "secret"
- `ANTHROPIC_API_KEY` — For LLM judge + agent-as-judge
- `REDIS_URL` — For rate limiting + caching
- `N8N_API_KEY`, `N8N_HOST` — For n8n healing integration
- `CORS_ORIGINS` — Frontend URL(s)

### Frontend Deployment (Vercel)

```bash
cd frontend && npm run build && cd .. && vercel --prod
```

**Pre-deploy checklist:**
1. Run `cd frontend && npx tsc --noEmit` — zero TypeScript errors required
2. Run `npm run build` locally — Vercel will reject if build fails
3. Verify component variant types match (Button, Badge, etc.)

**How it works:**
- Root `vercel.json` tells Vercel to `cd frontend && npm install` and `cd frontend && npm run build`
- Output directory is `frontend/.next`
- Framework: Next.js (auto-detected)
- Region: `iad1` (US East)
- Auto-deploys on push to main (if GitHub integration is connected)

**Common issues:**
- `npm install` exits 254 → Vercel tried to install from repo root. The root `vercel.json` must have `"installCommand": "cd frontend && npm install"`
- TypeScript error on deploy → Always run `npx tsc --noEmit` before pushing
- Component variant mismatch → Button supports `primary|secondary|ghost|danger|success|warning`, Badge supports `default|success|warning|error|info`

**Environment variables (set in Vercel dashboard):**
- `NEXT_PUBLIC_API_URL` — Backend URL (`https://mao-api.fly.dev`)
- `NEXT_PUBLIC_DEMO_MODE` — Set to `true` for demo mode
- `NEXTAUTH_SECRET` — For NextAuth sessions
- `NEXTAUTH_URL` — Frontend URL

### Quick Deploy (both)

```bash
# 1. Backend
cd backend && flyctl deploy --remote-only -a mao-api

# 2. Frontend
cd .. && vercel --prod

# 3. Verify
curl -s https://mao-api.fly.dev/api/v1/health | python3 -m json.tool
```

### Deployment Lessons Learned
1. **`requirements-prod.txt` is the source of truth** for backend dependencies. If you `pip install` something new, add it to both files
2. **Sentry frontend incompatible**: `@sentry/nextjs` v9 has peer dep conflicts with Next.js 16. Backend sentry-sdk works fine
3. **`mark_startup_complete()`** must exist in `app.api.v1.health` — the lifespan imports it
4. **Golden datasets are NOT in the Docker image** — `.dockerignore` excludes `data/`. Detection runs against the database, not local files
5. **Alembic migrations run automatically** on deploy via `release_command`. New migrations must chain correctly (check `down_revision`)
6. **The Docker image is ~900MB** — includes PyTorch CPU, sentence-transformers, and the MiniLM model. Build takes ~8 min on Depot

## Development Guidelines

- **Never use OpenAI. Claude/Anthropic models only for all LLM calls.** No GPT-4o, no OpenAI fallbacks.
- No mock or simulated data
- Always choose the simplest implementation
- Prefer editing existing files over creating new ones
- Security-first approach (input validation, auth)
- Test-driven development where applicable

## Frontend Development

### Tech Stack
- Next.js 16 (App Router), React 18, TypeScript
- TailwindCSS 3.4, Zustand, TanStack Query 5
- Recharts, ReactFlow, D3 for visualization
- NextAuth with Google OAuth

### Key Directories
| Directory | Purpose |
|-----------|---------|
| `frontend/src/app/` | Next.js App Router pages (~35 pages) |
| `frontend/src/components/ui/` | Shared UI components (Button, Card, Badge, etc.) |
| `frontend/src/components/` | Domain components (agents, traces, healing, charts) |
| `frontend/src/hooks/` | Custom React hooks (useApiWithFallback, useSafeAuth, etc.) |
| `frontend/src/lib/api.ts` | API client (1400+ lines, tenant-aware) |
| `frontend/src/stores/` | Zustand state stores |
| `frontend/tests/e2e/` | Playwright tests |

### Conventions
- All interactive components use `'use client'` directive
- UI components use CVA (class-variance-authority) + `cn()` from `@/lib/utils`
- API client factory: `createApiClient(token, tenantId)`
- Demo mode fallback only when `NEXT_PUBLIC_DEMO_MODE=true` or `?demo=true` URL param (not on every API error)
- Protected routes require authentication (middleware.ts)

### State Management
- **Zustand**: UI state (sidebar, selections, theme, filters)
- **TanStack Query**: Server state (60s staleTime, no refetchOnWindowFocus)
- **UserPreferences context**: User type (n8n_user vs developer)

### Color Palette (Premium Dark Theme)
- Primary: Blue (#3b82f6 / blue-500, #60a5fa / blue-400)
- Accent: Violet (#8b5cf6 / violet-500)
- Danger: Red (#ef4444)
- Warning: Amber (#f59e0b)
- Success: Green (#22c55e)
- Background: Zinc-950 (#09090b), Zinc-900 (#18181b)
- Borders: Zinc-800 (#27272a)
- Text: Zinc-100 (primary), Zinc-400 (secondary), Zinc-500 (muted)

### UI Component Library
- shadcn/ui pattern: CVA + Radix primitives + Tailwind
- Config: `components.json`, aliases `@/components/ui`, `@/lib/utils`
- Core: Button, Badge, Card, Tabs, Tooltip, Input, Select, Switch, Label, Textarea, Skeleton
- Animation: framer-motion via `FadeIn`, `StaggerContainer`, `StaggerItem`, `ScaleIn`

### Frontend Testing
- Framework: Playwright 1.41
- Test files: `frontend/tests/e2e/`
- Run: `cd frontend && npm run test:public`
- Auth tests require setup: `npm run test:setup-auth` first
