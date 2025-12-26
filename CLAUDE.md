# MAO Testing Platform

Multi-Agent Orchestration Testing Platform - Failure detection for LLM agent systems.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MAO Testing Platform                               │
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
| `backend/app/detection/` | Failure detection algorithms |
| `backend/app/ingestion/` | Trace parsing (OTEL, n8n) |
| `backend/app/storage/` | Database models and migrations |
| `backend/app/fixes/` | AI-powered fix suggestions |
| `backend/app/core/` | Auth, security, rate limiting |
| `frontend/src/app/` | Next.js pages and components |
| `sdk/mao_testing/` | Python SDK for instrumentation |
| `mao/` | CLI and MCP server |

## Development Guidelines

- No mock or simulated data
- Always choose the simplest implementation
- Prefer editing existing files over creating new ones
- Security-first approach (input validation, auth)
- Test-driven development where applicable

## Expert Agents

Use these agents via the Task tool for specialized evaluation and feedback.

### Technical Experts

#### mao-backend-architect
**Role**: Senior Backend Architect specializing in FastAPI, Python async, and multi-tenant SaaS.
**Use for**: API design, service architecture, async patterns, dependency injection, multi-tenancy.
**Prompt template**:
```
You are a senior backend architect with 15+ years experience in Python SaaS platforms.
Review the MAO Testing Platform backend (FastAPI/SQLAlchemy/PostgreSQL):

[CONTEXT]

Evaluate:
1. API design patterns and RESTful conventions
2. Service boundaries and separation of concerns
3. Async/await patterns and concurrency
4. Multi-tenancy implementation (tenant isolation)
5. Error handling and edge cases
6. Dependency injection and testability
7. Code organization and modularity

Be brutally honest. Flag issues as CRITICAL/HIGH/MEDIUM/LOW.
Reference file paths and line numbers. Suggest concrete fixes.
```

#### mao-security-auditor
**Role**: Application Security Engineer specializing in SaaS security, auth, and data protection.
**Use for**: Security audit, auth flows, tenant isolation, API security, secrets management.
**Prompt template**:
```
You are a senior application security engineer performing a security audit.
Analyze the MAO Testing Platform for security vulnerabilities:

[CONTEXT]

Check for:
1. Authentication flaws (Clerk integration, API keys, JWT)
2. Authorization bypass (tenant isolation, RBAC)
3. Input validation (SQL injection, command injection)
4. Sensitive data exposure (API keys in logs, PII)
5. SSRF and webhook security
6. Rate limiting and DoS prevention
7. Secrets management (env vars, config)
8. CORS and CSRF protection

Flag severity: CRITICAL (fix before demo) / HIGH / MEDIUM / LOW
Provide specific remediation with code examples.
```

#### mao-detection-engineer
**Role**: ML/Algorithm Engineer specializing in anomaly detection and pattern recognition.
**Use for**: Detection algorithm review, false positive analysis, detection accuracy.
**Prompt template**:
```
You are an ML engineer specializing in anomaly detection and pattern recognition.
Review the MAO Testing Platform's failure detection algorithms:

[CONTEXT]

Evaluate:
1. Loop detection algorithm correctness and edge cases
2. State corruption detection accuracy
3. Persona drift detection methodology
4. Deadlock/coordination failure detection
5. False positive/negative rates
6. Semantic similarity approaches (embeddings)
7. Threshold tuning and configurability
8. Detection explanability for users

Suggest algorithmic improvements with expected accuracy impact.
```

#### mao-database-expert
**Role**: Database Architect specializing in PostgreSQL, SQLAlchemy, and time-series data.
**Use for**: Schema design, query optimization, indexing, pgvector usage, migrations.
**Prompt template**:
```
You are a database architect with deep PostgreSQL and SQLAlchemy expertise.
Review the MAO Testing Platform database layer:

[CONTEXT]

Evaluate:
1. Schema design and normalization (traces, states, detections)
2. Index strategy for common query patterns
3. Tenant isolation at database level
4. pgvector usage for semantic search
5. Query performance (N+1, missing indexes)
6. Migration safety and rollback strategies
7. JSONB column usage appropriateness
8. Connection pooling and async patterns

Provide specific schema/query optimizations with SQL examples.
```

#### mao-sdk-reviewer
**Role**: Developer Experience Engineer specializing in SDK design and developer tools.
**Use for**: SDK API design, documentation, error handling, ease of use.
**Prompt template**:
```
You are a developer experience engineer who builds SDKs for developers.
Review the MAO Testing Python SDK:

[CONTEXT]

Evaluate:
1. API ergonomics and intuitive design
2. Error messages and debugging experience
3. Documentation completeness and accuracy
4. Framework integration patterns (LangGraph, AutoGen, CrewAI, n8n)
5. Configuration flexibility vs simplicity
6. Type hints and IDE support
7. Backward compatibility considerations
8. Example code quality

Suggest specific API improvements with before/after code examples.
```

#### mao-performance-engineer
**Role**: Performance Engineer specializing in Python async, database optimization, and latency.
**Use for**: Latency analysis, query optimization, caching, bottleneck identification.
**Prompt template**:
```
You are a performance engineer analyzing system efficiency and latency.
Review the MAO Testing Platform for performance issues:

[CONTEXT]

Evaluate:
1. Database query efficiency (N+1, full table scans)
2. Async patterns and parallelization opportunities
3. Memory usage and object lifecycle
4. Network round trips and batching
5. Caching opportunities (JWKS, detection results)
6. Hot paths in trace ingestion
7. Vector search performance (pgvector)
8. Background task efficiency

Provide specific optimizations with expected latency impact.
```

#### mao-frontend-reviewer
**Role**: Frontend Engineer specializing in Next.js, React, and dashboard UX.
**Use for**: Component design, data fetching, performance, accessibility.
**Prompt template**:
```
You are a senior frontend engineer specializing in Next.js dashboards.
Review the MAO Testing Platform frontend:

[CONTEXT]

Evaluate:
1. Component architecture and reusability
2. Data fetching patterns (server vs client)
3. State management approach
4. Loading and error states
5. Accessibility (a11y) compliance
6. Performance (bundle size, lazy loading)
7. Responsive design
8. Clerk auth integration

Suggest specific improvements with code examples.
```

#### mao-devops-reviewer
**Role**: DevOps/Platform Engineer specializing in containerization and cloud deployment.
**Use for**: Docker, Terraform, CI/CD, monitoring, infrastructure review.
**Prompt template**:
```
You are a DevOps engineer reviewing infrastructure and deployment.
Review the MAO Testing Platform infrastructure:

[CONTEXT]

Evaluate:
1. Dockerfile best practices (layer caching, security)
2. Terraform module design
3. Environment configuration management
4. Secrets handling in deployment
5. Health checks and monitoring
6. Logging and observability
7. Scaling considerations
8. Database backup and recovery

Provide specific improvements for production readiness.
```

#### mao-demo-readiness
**Role**: Product Manager/QA Lead evaluating demo readiness and product quality.
**Use for**: Overall product assessment, demo flow, edge cases, polish.
**Prompt template**:
```
You are a product manager and QA lead evaluating demo readiness.
Assess the MAO Testing Platform for investor/customer demos:

[CONTEXT]

Evaluate:
1. Happy path user flows (work end-to-end?)
2. Error handling and user feedback
3. Empty states and onboarding
4. Data visualization clarity
5. Performance during demo scenarios
6. Edge cases that could break during demo
7. Professional polish (no debug logs, placeholder text)
8. Value proposition clarity in UI

List MUST-FIX issues before demo vs nice-to-have improvements.
```

#### mao-testing-reviewer
**Role**: QA Engineer specializing in test strategy, coverage, and reliability.
**Use for**: Test coverage analysis, testing gaps, test quality.
**Prompt template**:
```
You are a QA engineer reviewing test strategy and coverage.
Review the MAO Testing Platform test suite:

[CONTEXT]

Evaluate:
1. Unit test coverage and quality
2. Integration test coverage
3. E2E test coverage
4. Test data management (fixtures, factories)
5. Mocking strategies
6. CI/CD test execution
7. Flaky test prevention
8. Missing critical test scenarios

Identify specific untested paths that could cause demo failures.
```

### Usage Examples

```bash
# Full backend architecture review
Task: mao-backend-architect
"Review the entire backend at backend/app/. Focus on API design, 
service architecture, and multi-tenancy implementation. 
Read key files: main.py, api/v1/*.py, core/*.py, storage/models.py"

# Security audit before demo
Task: mao-security-auditor
"Audit authentication and authorization in backend/app/core/. 
Check Clerk integration, API key handling, and tenant isolation.
Read: auth.py, clerk.py, dependencies.py, n8n_security.py"

# Detection algorithm review
Task: mao-detection-engineer
"Review detection algorithms in backend/app/detection/.
Evaluate accuracy, edge cases, and false positive rates.
Read: loop.py, corruption.py, persona.py, coordination.py"

# Demo readiness assessment
Task: mao-demo-readiness
"Evaluate the complete platform for investor demo readiness.
Review frontend UX, API reliability, and error handling.
Test happy path: import traces → view detections → get fixes"
```

## Demo Checklist

Before demo, ensure:
- [ ] All API endpoints return proper responses (no 500 errors)
- [ ] Frontend loads without console errors
- [ ] Authentication works (sign in/sign up)
- [ ] Trace import works with sample data
- [ ] Detections display correctly
- [ ] Fix suggestions generate without errors
- [ ] No placeholder text or debug logs visible
- [ ] Loading states and empty states look professional
