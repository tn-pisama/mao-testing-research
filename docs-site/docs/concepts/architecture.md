# Architecture

PISAMA is a full-stack platform for detecting and healing failure modes in multi-agent LLM systems. This page describes the system architecture, key components, and data flow.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PISAMA Platform                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Frontend   │  │   Backend    │  │     SDK      │  │     CLI      │   │
│  │   (Next.js)  │  │  (FastAPI)   │  │   (Python)   │  │   (Python)   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │            │
│         └─────────────────┼─────────────────┴─────────────────┘            │
│                           │                                                │
│                           ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Core Services                               │   │
│  ├───────────────┬──────────────┬──────────────┬───────────────────── │   │
│  │  Detection    │   Ingestion  │   Storage    │   Self-Healing       │   │
│  │  Engine       │   Pipeline   │   Layer      │   Pipeline           │   │
│  │  - 21 MAST   │   - OTEL     │   - Postgres │   - Analyze          │   │
│  │  - 6 n8n     │   - n8n      │   - pgvector │   - Generate fixes   │   │
│  │  - Tiered    │   - Universal│   - SQLAlch  │   - Apply + validate │   │
│  │  - LLM Judge │              │              │   - Rollback          │   │
│  └───────────────┴──────────────┴──────────────┴──────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI, SQLAlchemy, PostgreSQL 16+, pgvector, Alembic |
| **Frontend** | Next.js 16, React 18, TailwindCSS 3.4, Zustand, TanStack Query 5 |
| **ML / Embeddings** | E5-large-instruct (1024d), nomic-embed-text-v1.5 (768d), sentence-transformers |
| **LLM** | Claude (Anthropic) for judge and fixes; Gemini for budget tier |
| **SDK** | Python with LangGraph, AutoGen, CrewAI, n8n adapters |
| **CLI** | Click-based with MCP server support |
| **Infrastructure** | Docker, Terraform, AWS ECS |

## Data Flow

### Trace Ingestion Pipeline

Traces enter PISAMA through the ingestion pipeline, which normalizes data from any supported framework into a common internal format.

```
Trace Source (OTEL / webhook / SDK)
        │
        ▼
┌──────────────┐
│  Ingestion   │  Parses framework-specific formats
│  Parser      │  (OTEL, n8n, conversation, raw JSON)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  ParsedState │  Normalized representation:
│  Objects     │  - trace_id, agent_id, sequence_num
│              │  - state_delta, state_hash (SHA256[:16])
│              │  - token_count, latency_ms, timestamp
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Storage     │  PostgreSQL + pgvector
│  Layer       │  SQLAlchemy models, Alembic migrations
└──────────────┘
```

**Agent identification** uses framework-specific OTEL attributes:

| Framework | Agent attribute | State attribute |
|---|---|---|
| Standard OTEL | `gen_ai.agent.name` | `gen_ai.state` |
| LangGraph | `langgraph.node.name` | `langgraph.state` |
| CrewAI | `crewai.agent.role` | `crewai.state` |
| AutoGen | `autogen.agent.name` | -- |
| OpenClaw | `openclaw.agent.name` | `openclaw.session.state` |

### Detection Pipeline

The `DetectionOrchestrator` is the main entry point for trace analysis. It runs all applicable detectors and returns a `DiagnosisResult`.

```
Trace / ParsedStates
        │
        ▼
┌──────────────────┐
│ Detection        │  Runs detectors sequentially:
│ Orchestrator     │  loop → overflow → tool issues →
│                  │  error patterns → grounding → retrieval
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Filter & Sort    │  Keep detected=True only
│                  │  Sort by severity, then confidence
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ DiagnosisResult  │  primary_failure, all_detections,
│                  │  root_cause_explanation,
│                  │  self_healing_available
└──────────────────┘
```

Each detector follows a **cheapest-first** strategy, escalating through tiers only when lower tiers are inconclusive. See [Detection Tiers](detection-tiers.md) for details.

### Self-Healing Pipeline

When failures are detected, the self-healing pipeline can generate and apply fixes:

```
Detection Result
       │
       ▼
┌──────────────┐
│ Fix          │  AI-powered fix generation
│ Generator    │  Code suggestions, best practices
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Approval     │  Manual or automatic based on policy
│ Policy       │  High-risk fixes require human approval
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Apply &      │  Execute fix with checkpoint
│ Validate     │  Rollback if validation fails
└──────────────┘
```

See [Self-Healing](self-healing.md) for the full pipeline description.

## Key Directories

| Directory | Purpose |
|---|---|
| `backend/app/api/v1/` | REST API endpoints |
| `backend/app/detection/` | ICP-tier detection algorithms (16 detectors) |
| `backend/app/detection_enterprise/` | Enterprise ML/tiered detection, calibration |
| `backend/app/detection/llm_judge/` | LLM-as-Judge verification |
| `backend/app/ingestion/` | Trace parsing (OTEL, n8n, universal) |
| `backend/app/storage/` | Database models and migrations |
| `backend/app/fixes/` | AI-powered fix suggestions |
| `backend/app/healing/` | Self-healing orchestration |
| `backend/app/core/` | Auth, security, rate limiting, feature gates |
| `backend/tests/` | pytest tests |
| `frontend/src/app/` | Next.js pages and components |
| `packages/` | Python packages (pisama-core, pisama-claude-code) |
| `cli/` | CLI with MCP server support |

## Architecture Principles

1. **Tiered Detection** -- Always start at Tier 1 (hash), escalate only if needed through Tier 2 (state delta), Tier 3 (embeddings), Tier 4 (LLM), Tier 5 (human).

2. **OTEL-First** -- All traces use OpenTelemetry with `gen_ai.*` semantic conventions.

3. **Framework-Agnostic Core** -- No LangGraph, CrewAI, or AutoGen imports in core detection code. Framework-specific logic lives in adapters in `packages/`.

4. **Cost-Aware** -- Track tokens, compute time, and dollar cost per detection. Target: $0.05/trace average.

5. **Safety-First Healing** -- Require checkpoints, rollback capability, and approval policies for high-risk fixes.

6. **Feature-Flagged Enterprise** -- ICP code never imports from enterprise modules. Enterprise code can import from ICP. Feature gates return HTTP 402 when features are not enabled.
