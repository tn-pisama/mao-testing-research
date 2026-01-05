# PISAMA Competitive Analysis: Skill Review Findings

**Date:** 2026-01-05
**Document:** Consolidated review of `/docs/competitive-analysis-2025.md`
**Skills Invoked:** 6 (3 existing + 3 new)

---

## Executive Summary

Six expert skills reviewed the PISAMA competitive analysis and roadmap. Key findings:

| Area | Assessment | Priority Action |
|------|------------|-----------------|
| **Positioning** | RISKY | Remove "only" claim; focus on outcomes |
| **Self-Healing** | 70% FEASIBLE | Hybrid playbook+AI approach required |
| **OTEL Integration** | CLEAR PATH | 3-week implementation to parity |
| **Detection Taxonomy** | COMPETITIVE | Unique F3/F4 modes; add quality metrics |
| **Architecture** | SOUND | GenAI conventions alignment needed |

**Critical Risk Identified:** The positioning statement "only platform that detects AND fixes" is false - AWS Bedrock has playbook-based remediation. This claim is verifiable and will damage credibility.

---

## 1. Competitive Strategy Review

### Skill: competitive-strategy-reviewer

#### Claim Verification

| Claim | Status | Evidence |
|-------|--------|----------|
| "Only platform that detects AND fixes" | **FALSE** | AWS has playbook remediation, DevOps Agent |
| "No competitor has closed-loop remediation" | **PARTIALLY TRUE** | AWS is playbook (manual), PISAMA targets AI-generated |
| "Multi-agent failure detection unique" | **TRUE** | F3/F4 (persona drift, coordination) not in competitor evaluators |
| "Local-first privacy model" | **TRUE** | All competitors are cloud-first |

#### Positioning Risk Assessment

- **Defensibility:** WEAK (current "only" claim)
- **Risk of Competitive Attack:** HIGH
- **Time Window:** 6-12 months before self-healing commoditized

#### Recommended Positioning

**FROM:** "The only platform that detects agent failures AND automatically fixes them"

**TO:** "Ship reliable AI agents without dedicated SRE - detect, diagnose, and resolve failures before users notice"

**Rationale:** Outcome-focused, avoids disprovable "only" claim, emphasizes operational benefit.

#### Messaging Guidelines

| DO | DON'T |
|----|-------|
| Lead with outcomes | Use "only" claims |
| Be specific about shipped vs planned | Compare feature counts |
| Acknowledge competitor strengths | Position on roadmap |
| Focus on multi-agent, local-first | Ignore enterprise gaps |

---

## 2. Self-Healing Architecture Review

### Skill: self-healing-architect

#### Feasibility Assessment

| Fix Type | Feasibility | Auto-Apply Safe? |
|----------|-------------|------------------|
| Retry limit adjustment | **95%** | Yes (canary) |
| Circuit breaker enable | **90%** | Yes (canary) |
| Timeout adjustment | **90%** | Yes (canary) |
| System prompt modification | **50%** | **No** - requires approval |
| Multi-agent coordination | **30%** | **No** - requires SRE review |

**Overall Feasibility:** 70% for config-level fixes, 40% for prompt/coordination fixes

#### Safety Gaps Identified

1. **CRITICAL:** Missing rollback execution mechanism
   - Plan has rollback *triggers* but no *execution* code
   - Required: Checkpoint/restore system

2. **HIGH:** Missing concurrent healing protection
   - Multiple fixes could apply simultaneously
   - Required: Healing lock per workflow

3. **HIGH:** Missing circuit breaker
   - Healing loops possible (fix fails → retry fix → loop)
   - Required: MAX_HEALS_PER_WORKFLOW_PER_HOUR = 3

4. **MEDIUM:** Approval workflow not designed
   - High-risk fixes need human approval
   - Required: Slack/email approval with timeout

#### Recommended Approach: Hybrid

```
┌────────────────────────────────────────────────────────────┐
│                   HYBRID SELF-HEALING                       │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  PLAYBOOKS (Deterministic)    AI-GENERATED (Novel)         │
│  ─────────────────────────    ────────────────────────     │
│  • Retry adjustment           • Prompt modifications       │
│  • Circuit breaker            • Coordination changes       │
│  • Timeout tuning             • Novel failure types        │
│  • Rate limiting              • Cross-agent fixes          │
│                                                             │
│  AUTO-APPLY: Yes (canary)     AUTO-APPLY: No               │
│  APPROVAL: None               APPROVAL: Required           │
│  ROLLBACK: Auto               ROLLBACK: Auto               │
│                                                             │
│  Graduate successful AI fixes to playbook status           │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

#### Implementation Timeline

- **Phase 1 (Weeks 1-4):** Playbook infrastructure, checkpoint system
- **Phase 2 (Weeks 5-8):** 5 initial playbooks, rollback execution
- **Phase 3 (Weeks 9-12):** AI fix generation, approval workflow
- **Phase 4 (Weeks 13-16):** Learning loop, playbook graduation

**Total:** 16 weeks (4 months) for production-ready self-healing

---

## 3. OTEL Integration Review

### Skill: otel-integration-architect

#### Current Gap

| Feature | Competitors | PISAMA |
|---------|-------------|--------|
| OTLP/HTTP receiver | Yes | **No** |
| OTLP/gRPC receiver | Yes | **No** |
| GenAI semantic conventions | Yes | Partial (export only) |

#### Implementation Plan

**Phase 1a: OTLP/HTTP Receiver (Week 1-2)**

```python
# /api/v1/traces (OTLP JSON)
# Content-Type: application/json

POST /v1/traces
Authorization: Bearer <api-key>

# Accept OTLP ExportTraceServiceRequest
# Map to UniversalTrace format
```

**Phase 1b: GenAI Conventions (Week 2-3)**

| OTEL Attribute | PISAMA Mapping |
|----------------|----------------|
| `gen_ai.agent.id` | `agent_id` |
| `gen_ai.agent.name` | `agent_name` |
| `gen_ai.operation.name` | `operation_type` |
| `gen_ai.request.model` | `model` |
| `gen_ai.usage.input_tokens` | `input_tokens` |
| `gen_ai.usage.output_tokens` | `output_tokens` |
| `gen_ai.tool.name` | `tool_name` |
| `gen_ai.tool.call.id` | `tool_call_id` |

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    PISAMA TRACE INGESTION                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  OTLP/HTTP ───────┐                                         │
│  /v1/traces       │                                         │
│                   ├──▶ GenAI Mapper ──▶ UniversalTrace      │
│  Legacy API ──────┤                                         │
│  /api/v1/traces   │                                         │
│                   │                                         │
│  OTLP/gRPC ───────┘  (Phase 2)                             │
│  :4317                                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Compliance Checklist

- [ ] OTLP/HTTP endpoint at `/v1/traces`
- [ ] Protobuf and JSON encoding support
- [ ] GenAI Tier 1 attributes mapped
- [ ] Backward compatible with existing SDK
- [ ] Content-Type negotiation
- [ ] Auth supports both OTEL headers and PISAMA API keys

---

## 4. MAST Failure Taxonomy Review

### Skill: mast-failure-classifier

#### PISAMA vs Competitor Coverage

| PISAMA Mode | Category | AWS Evaluator | Google Metric | MLflow Scorer |
|-------------|----------|---------------|---------------|---------------|
| F1: Exact Loop | LOOP | - | - | - |
| F2: Structural Loop | LOOP | - | - | - |
| F3: Semantic Loop | LOOP | - | - | - |
| **F4: Persona Drift** | PERSONA | - | - | - |
| F5: State Corruption | STATE | - | - | - |
| F6: No Progress | STATE | - | trajectory_exact_match | - |
| **F7: Coordination Failure** | COORDINATION | - | - | - |
| F8: Deadlock | COORDINATION | - | - | - |
| F9: Token Explosion | RESOURCE | - | - | - |
| F10: Timeout | RESOURCE | - | - | - |
| F11: Context Overflow | RESOURCE | - | - | - |
| F12: Hallucination | PERSONA | Faithfulness, Groundedness | hallucination | groundedness |
| F13: Tool Misuse | STATE | Tool Selection | tool_use_quality | - |
| F14: Instruction Violation | PERSONA | Instruction Following | INSTRUCTION_FOLLOWING | - |

**Key Finding:** F4 (Persona Drift) and F7 (Coordination Failure) are unique to PISAMA - no competitor detects these.

#### Gaps vs Competitors

| Competitor Metric | PISAMA Equivalent | Gap? |
|-------------------|-------------------|------|
| AWS: Correctness | - | **YES** |
| AWS: Helpfulness | - | **YES** |
| AWS: Conciseness | - | **YES** |
| AWS: Coherence | - | **YES** |
| Google: trajectory_precision | - | **YES** |
| Google: trajectory_recall | - | **YES** |
| MLflow: answer_relevance | - | **YES** |
| MLflow: retrieval_precision | - | **YES** |

#### Recommended Additions

**Priority 1 (Table Stakes):**
1. **Correctness Evaluator** - Factual accuracy scoring
2. **Helpfulness Evaluator** - User value assessment
3. **Response Relevance** - Query-response alignment

**Priority 2 (Competitive Parity):**
4. **Trajectory Metrics** - Tool call sequence evaluation
5. **Coherence Evaluator** - Logical structure assessment

**Priority 3 (Differentiation):**
6. **Multi-Agent Effectiveness** - Team performance scoring
7. **Cost Efficiency Score** - Value per token metric

---

## 5. Detection Algorithm Review

### Skill: detection-algorithm-designer

#### Current Architecture Alignment

| Tier | PISAMA Current | Recommendation |
|------|----------------|----------------|
| Tier 1 (Hash) | F1, F2 | Keep - cost effective |
| Tier 2 (State Delta) | F5, F6 | Keep - good accuracy |
| Tier 3 (Embeddings) | F3, F4 | Keep - semantic needed |
| Tier 4 (LLM Judge) | F12-F14 | **Add more** - quality evals |
| Tier 5 (Human) | None | Add for ambiguous cases |

#### Algorithm Gaps

1. **Missing: Trajectory Evaluation**
   - No tool call sequence analysis
   - Competitors: Google has 5 trajectory metrics
   - Required for parity

2. **Missing: Quality Scoring**
   - Current: Failure/not-failure binary
   - Needed: 0-1 quality scores for monitoring
   - All competitors have continuous metrics

3. **Missing: Continuous Evaluation**
   - Current: Batch analysis
   - Needed: Real-time streaming evaluation
   - Competitors: AWS, Google have real-time

#### Recommended Algorithm Additions

```python
# Priority 1: Quality Evaluators (Tier 4)
class CorrectnessEvaluator:
    """Uses LLM to assess factual accuracy."""
    tier = 4
    cost = "$0.50 per eval"

class HelpfulnessEvaluator:
    """Uses LLM to assess user value."""
    tier = 4
    cost = "$0.50 per eval"

# Priority 2: Trajectory Evaluation (Tier 2)
class TrajectoryPrecisionDetector:
    """Compares tool calls to expected sequence."""
    tier = 2
    cost = "$0"

class TrajectoryRecallDetector:
    """Checks if required tools were called."""
    tier = 2
    cost = "$0"
```

---

## 6. Architecture Review

### Skill: mao-architecture-reviewer

#### Compliance Assessment

| Principle | Status | Notes |
|-----------|--------|-------|
| OTEL-First Design | **PARTIAL** | Export only, need ingestion |
| Tiered Detection | **PASS** | Well-structured tier system |
| Cost-Aware Design | **PASS** | Cost tracking in place |
| Framework-Agnostic | **PASS** | Adapters properly isolated |

#### Technical Feasibility of Roadmap

| Phase | Feasibility | Risk |
|-------|-------------|------|
| Phase 1: Platform Parity | **HIGH** | Standard implementation |
| Phase 2: Self-Healing | **MEDIUM** | Safety mechanisms complex |
| Phase 3: Multi-Agent | **HIGH** | Extends existing detection |
| Phase 4: Enterprise | **MEDIUM** | SOC 2 timeline aggressive |

#### Critical Architecture Gaps

1. **OTEL Native Ingestion**
   - Required for enterprise adoption
   - Blocks integration with existing observability stacks
   - Implementation: 3 weeks

2. **Real-Time Dashboard**
   - Required for production monitoring
   - Competitors all have this
   - Implementation: WebSocket + React components

3. **Approval Workflow System**
   - Required for safe self-healing
   - Not in current architecture
   - Implementation: State machine + notification service

---

## Consolidated Recommendations

### Immediate Actions (Week 1)

1. **Update Positioning Statement** - Remove "only" claim
2. **Begin OTEL Ingestion** - Phase 1a implementation
3. **Design Approval Workflow** - For self-healing safety

### Short-Term (Weeks 2-6)

4. **Complete OTEL Parity** - GenAI conventions, both encodings
5. **Add Quality Evaluators** - Correctness, Helpfulness, Relevance
6. **Implement Playbook Infrastructure** - 5 initial playbooks

### Medium-Term (Weeks 7-12)

7. **Self-Healing MVP** - Config-level fixes with canary
8. **Real-Time Dashboard** - Live trace streaming
9. **Trajectory Evaluation** - Precision/recall metrics

### Long-Term (Weeks 13-24)

10. **AI-Generated Fixes** - With approval workflow
11. **Multi-Agent Evaluation** - Team effectiveness metrics
12. **Enterprise Readiness** - SSO, RBAC, SOC 2 prep

---

## Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| "Only" claim challenged | HIGH | HIGH | Change messaging immediately |
| Self-healing causes harm | MEDIUM | CRITICAL | Canary + rollback + approval |
| AWS adds closed-loop | MEDIUM | HIGH | Ship faster, deepen multi-agent |
| Enterprise rejects local-only | LOW | MEDIUM | Add optional cloud sync |
| OTEL ingestion delayed | LOW | MEDIUM | Clear 3-week scope |

---

## Skills Created

Three new skills were created for ongoing use:

1. **otel-integration-architect** - Reviews OTEL compatibility
2. **self-healing-architect** - Reviews self-healing safety
3. **competitive-strategy-reviewer** - Reviews positioning claims

---

## Appendix: Skill Outputs

Full outputs from each skill invocation are available in the conversation history.

| Skill | Focus | Key Finding |
|-------|-------|-------------|
| mao-architecture-reviewer | Technical architecture | OTEL ingestion is priority |
| detection-algorithm-designer | Algorithm design | Add quality evaluators |
| mast-failure-classifier | Taxonomy mapping | F3/F4 are unique advantages |
| competitive-strategy-reviewer | Positioning | "Only" claim is risky |
| self-healing-architect | Safety | Hybrid approach required |
| otel-integration-architect | Standards | 3-week implementation |
