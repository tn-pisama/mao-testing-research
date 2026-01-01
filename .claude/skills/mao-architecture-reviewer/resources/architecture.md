# MAO Testing Platform Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MAO TESTING PLATFORM                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Frontend   │  │   Backend    │  │     SDK      │  │     CLI     │ │
│  │   (Next.js)  │  │  (FastAPI)   │  │   (Python)   │  │   (Python)  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
│         │                 │                 │                  │        │
│         └────────────┬────┴────────────┬────┴──────────────────┘        │
│                      │                 │                                 │
│                      ▼                 ▼                                 │
│         ┌────────────────────────────────────────┐                      │
│         │           API Gateway Layer            │                      │
│         │    (Authentication, Rate Limiting)     │                      │
│         └────────────────┬───────────────────────┘                      │
│                          │                                               │
│         ┌────────────────┴───────────────────────┐                      │
│         │         Core Detection Engine          │                      │
│         │                                        │                      │
│         │  ┌──────────┐ ┌──────────┐ ┌────────┐ │                      │
│         │  │   Loop   │ │  State   │ │Persona │ │                      │
│         │  │ Detector │ │ Detector │ │Detector│ │                      │
│         │  └──────────┘ └──────────┘ └────────┘ │                      │
│         │  ┌──────────┐ ┌──────────┐ ┌────────┐ │                      │
│         │  │  Coord   │ │   Cost   │ │  Fix   │ │                      │
│         │  │ Detector │ │ Tracker  │ │  Gen   │ │                      │
│         │  └──────────┘ └──────────┘ └────────┘ │                      │
│         │                                        │                      │
│         └────────────────┬───────────────────────┘                      │
│                          │                                               │
│         ┌────────────────┴───────────────────────┐                      │
│         │              Data Layer                │                      │
│         │                                        │                      │
│         │  ┌──────────────────────────────────┐ │                      │
│         │  │     PostgreSQL + pgvector        │ │                      │
│         │  │  - Traces, Spans, Detections     │ │                      │
│         │  │  - Embeddings (1536 dimensions)  │ │                      │
│         │  │  - User/Org/Project data         │ │                      │
│         │  └──────────────────────────────────┘ │                      │
│         │                                        │                      │
│         └────────────────────────────────────────┘                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Frontend (Next.js)
- Dashboard visualization
- Trace explorer
- Detection alerts
- User management
- **No business logic** - presentation only

### Backend (FastAPI)
- REST API endpoints
- WebSocket for real-time updates
- Authentication/authorization
- Orchestrates detection engine
- Database access layer

### SDK (Python)
- Framework adapters (LangGraph, CrewAI, AutoGen)
- OTEL instrumentation
- Trace export
- **Must be lightweight** - minimal dependencies

### CLI (Python)
- Local trace analysis
- Configuration management
- Developer tooling
- Can work offline

### Core Detection Engine
- Framework-agnostic algorithms
- Tiered detection (1-5)
- Cost tracking
- Fix generation
- **No framework imports allowed**

## Data Flow

```
1. Agent Workflow Executes
         │
         ▼
2. SDK Instruments (OTEL spans)
         │
         ▼
3. Traces Sent to Backend
         │
         ▼
4. Detection Engine Analyzes
   ├── Tier 1: Hash-based (instant)
   ├── Tier 2: State delta (fast)
   ├── Tier 3: Embeddings (medium)
   ├── Tier 4: LLM Judge (slow)
   └── Tier 5: Human (async)
         │
         ▼
5. Detections Stored + Alerts Sent
         │
         ▼
6. Fix Suggestions Generated
         │
         ▼
7. Dashboard Updated (WebSocket)
```

## Directory Structure

```
mao-testing/
├── frontend/              # Next.js app
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── lib/
│   └── package.json
│
├── backend/               # FastAPI app
│   ├── src/
│   │   ├── api/          # Route handlers
│   │   ├── core/         # Detection engine (NO FRAMEWORK IMPORTS)
│   │   ├── db/           # Database models
│   │   ├── services/     # Business logic
│   │   └── utils/
│   └── pyproject.toml
│
├── sdk/                   # Python SDK
│   ├── mao_testing/
│   │   ├── tracer.py     # OTEL instrumentation
│   │   ├── adapters/     # Framework-specific (LangGraph, CrewAI, etc.)
│   │   └── exporters/    # Trace export
│   └── pyproject.toml
│
├── cli/                   # CLI tool
│   ├── mao_cli/
│   └── pyproject.toml
│
└── shared/               # Shared types/contracts
    └── types/
```

## Key Interfaces

### TraceIngester (Backend)
```python
class TraceIngester(Protocol):
    async def ingest(self, trace: OTELTrace) -> str:
        """Ingest trace, return trace_id."""

    async def get_trace(self, trace_id: str) -> OTELTrace:
        """Retrieve trace by ID."""
```

### Detector (Core)
```python
class Detector(Protocol):
    @property
    def tier(self) -> int:
        """Detection tier (1-5)."""

    async def detect(self, trace: OTELTrace) -> list[Detection]:
        """Run detection, return findings."""

    def should_escalate(self, detection: Detection) -> bool:
        """Whether to escalate to next tier."""
```

### FrameworkAdapter (SDK)
```python
class FrameworkAdapter(Protocol):
    def instrument(self, app: Any) -> None:
        """Attach OTEL instrumentation."""

    def extract_state(self, context: Any) -> dict:
        """Extract agent state."""

    def extract_persona(self, agent: Any) -> str:
        """Extract persona/system prompt."""

    def get_dag(self) -> DAG:
        """Extract workflow DAG."""
```

## Database Schema (Core Tables)

```sql
-- Traces
CREATE TABLE traces (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    project_id UUID NOT NULL,
    trace_id TEXT NOT NULL,  -- OTEL trace ID
    root_span_id TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spans
CREATE TABLE spans (
    id UUID PRIMARY KEY,
    trace_id UUID REFERENCES traces(id),
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    name TEXT NOT NULL,
    kind TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    attributes JSONB,
    events JSONB,
    embedding VECTOR(1536),  -- For semantic search
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Detections
CREATE TABLE detections (
    id UUID PRIMARY KEY,
    trace_id UUID REFERENCES traces(id),
    detector TEXT NOT NULL,  -- 'loop', 'state_corruption', 'persona_drift'
    tier INT NOT NULL,       -- 1-5
    severity TEXT NOT NULL,  -- 'low', 'medium', 'high', 'critical'
    confidence FLOAT,
    details JSONB,
    cost_usd FLOAT,          -- Detection cost
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fixes
CREATE TABLE fixes (
    id UUID PRIMARY KEY,
    detection_id UUID REFERENCES detections(id),
    fix_type TEXT NOT NULL,
    code_diff TEXT,
    explanation TEXT,
    applied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Security Model

- API keys scoped to org/project
- Row-level security in PostgreSQL
- No cross-org data access
- Audit logging for all mutations
- Secrets in environment variables only
