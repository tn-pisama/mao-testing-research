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
- **Frontend**: Next.js 14, React, TailwindCSS, Clerk Auth
- **SDK**: Python package with LangGraph/AutoGen/CrewAI/n8n integrations
- **CLI**: Click-based CLI with MCP server support
- **Infrastructure**: Docker, Terraform, AWS ECS

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

- Test files: `test_*.py` in `backend/tests/`
- Golden datasets: `backend/tests/fixtures/golden/`
- Run tests: `pytest backend/tests/`
- Test organization: unit, integration, e2e, detection_enterprise
- E2E strategy: See `docs/E2E_TESTING_STRATEGY.md`

## Architecture Principles

1. **Tiered Detection**: Always start at Tier 1 (hash), escalate only if needed (Tier 2: state delta, Tier 3: embeddings, Tier 4: LLM, Tier 5: human)
2. **OTEL-First**: All traces use OpenTelemetry with `gen_ai.*` semantic conventions
3. **Framework-Agnostic Core**: No LangGraph/CrewAI/AutoGen imports in core - use adapters in packages/
4. **Cost-Aware**: Track tokens, compute time, $ cost per detection (target: $0.05/trace)
5. **Safety-First Healing**: Require checkpoints, rollback capability, approval policies for high-risk fixes

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
- Demo mode fallback for graceful API failures
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
