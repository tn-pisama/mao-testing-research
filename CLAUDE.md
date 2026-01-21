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

---

## Expert Agents

Use these agents via the Task tool for specialized evaluation and feedback.

### Agent Index

| Agent | Role | Use For |
|-------|------|---------|
| **Technical** | | |
| mao-backend-architect | Senior Backend Architect | API design, async patterns, multi-tenancy |
| mao-security-auditor | Security Engineer | Auth flows, tenant isolation, API security |
| mao-detection-engineer | ML/Algorithm Engineer | Detection accuracy, false positive analysis |
| mao-database-expert | Database Architect | Schema design, queries, pgvector, indexing |
| mao-sdk-reviewer | Developer Experience | SDK usability, documentation, integrations |
| mao-performance-engineer | Performance Engineer | Latency, query optimization, bottlenecks |
| mao-frontend-reviewer | Frontend Engineer | React, Next.js, component design |
| mao-devops-reviewer | DevOps Engineer | Docker, Terraform, CI/CD |
| mao-demo-readiness | Product/QA Lead | Demo preparation, edge cases, polish |
| mao-testing-reviewer | QA Engineer | Test coverage, quality, reliability |
| **Detection Algorithms** | | |
| hallucination-detection-architect | ML Engineer | Factual grounding, RAG, hallucination detection |
| prompt-injection-detector | Security Engineer | Prompt injection, jailbreak prevention |
| context-overflow-detector | Systems Engineer | Context window, token limits, memory |
| tool-misuse-detector | AI Safety Engineer | Tool abuse, capability boundaries |
| cost-anomaly-detector | FinOps Engineer | Cost spikes, runaway agents, optimization |
| latency-degradation-detector | Performance Engineer | Latency analysis, SLO management |
| semantic-drift-detector | NLP Engineer | Embedding drift, behavioral consistency |
| **Integrations** | | |
| langchain-integration-architect | LangChain Expert | Chains, agents, LCEL patterns |
| openai-assistants-integration | OpenAI Platform Expert | Assistants API, function calling |
| bedrock-agents-integration | AWS AI/ML Specialist | Bedrock Agents, knowledge bases |
| dify-integration-architect | Low-code AI Specialist | Dify workflows and agents |
| flowise-integration-architect | Visual AI Builder | Flowise chatflows, agentflows |
| semantic-kernel-completion | Microsoft AI Specialist | Semantic Kernel plugins, planners |
| **Observability** | | |
| datadog-integration-architect | Observability Engineer | APM, custom metrics, dashboards |
| grafana-integration-architect | Grafana/Prometheus | Dashboards, metrics export |
| pagerduty-integration-architect | Incident Management | Alerting, escalation |
| slack-teams-notification-architect | Collaboration | Slack/Teams notifications |
| **Self-Healing** | | |
| auto-rollback-architect | SRE | Rollback on failed fixes |
| canary-deployment-architect | Release Engineer | Progressive delivery, A/B testing |
| human-approval-workflow-architect | Workflow Specialist | Human-in-the-loop approval |
| **Testing** | | |
| trace-replay-architect | Testing Platform Engineer | Record/replay, what-if simulation |
| chaos-injection-architect | Chaos Engineer | Failure injection, resilience |
| adversarial-prompt-tester | AI Red Team | Prompt attacks, defense testing |
| load-testing-architect | Performance Engineer | Load testing, capacity planning |
| **Enterprise** | | |
| soc2-compliance-architect | Compliance Engineer | SOC 2, security controls |
| sso-saml-architect | IAM Specialist | SAML/OIDC, enterprise SSO |
| rbac-permissions-architect | Authorization Specialist | Role-based access control |
| data-residency-architect | Data Privacy Engineer | Regional data isolation |
| audit-logging-architect | Security Engineer | Audit logging, forensics |
| **Infrastructure** | | |
| kubernetes-deployment-architect | K8s Platform Engineer | Helm charts, self-hosted |
| multi-region-architect | Distributed Systems | Global availability |
| caching-architecture-architect | Performance Engineer | Redis, caching strategies |
| queue-architecture-architect | Backend Engineer | Async processing, message queues |

### Standard Prompt Template

When invoking an agent via the Task tool, use this template:

```
You are {AGENT_ROLE} reviewing the MAO Testing Platform {COMPONENT}.

[CONTEXT: Specific files or areas to review]

Evaluate against these criteria:
{CRITERIA_LIST - see role-specific criteria below}

Flag issues as: CRITICAL (blocks demo) / HIGH / MEDIUM / LOW
Reference file paths and line numbers.
Suggest concrete fixes with code examples.
```

### Evaluation Criteria by Role

**Backend/Architecture**: API design, async patterns, multi-tenancy, error handling, dependency injection, code organization

**Security**: Auth flaws, authorization bypass, input validation, sensitive data exposure, SSRF, rate limiting, secrets management, CORS/CSRF

**Detection/ML**: Algorithm correctness, edge cases, false positive/negative rates, threshold tuning, explainability

**Database**: Schema design, index strategy, tenant isolation, pgvector usage, query performance, migration safety

**SDK/DX**: API ergonomics, error messages, documentation, framework integrations, type hints, examples

**Performance**: Query efficiency, async parallelization, memory usage, caching, hot paths, vector search

**Frontend**: Component architecture, data fetching, state management, loading/error states, accessibility, performance

**DevOps**: Dockerfile best practices, Terraform modules, secrets handling, health checks, logging, scaling

**Demo Readiness**: Happy path flows, error handling, empty states, data visualization, polish, value proposition clarity

### Usage Examples

```bash
# Backend architecture review
Task: mao-backend-architect
"Review backend/app/api/v1/*.py. Evaluate API design and multi-tenancy."

# Security audit before demo
Task: mao-security-auditor
"Audit backend/app/core/. Check Clerk integration and tenant isolation."

# Detection algorithm review
Task: mao-detection-engineer
"Review backend/app/detection/. Evaluate accuracy and edge cases."

# Demo readiness check
Task: mao-demo-readiness
"Evaluate full platform for investor demo. Test happy path end-to-end."
```

---

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
