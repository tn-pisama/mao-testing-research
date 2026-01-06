# MAO Skills Strategy: Three-Level Integration

## Executive Summary

Skills operate at **three distinct levels** in the MAO ecosystem:

| Level | Role | Value |
|-------|------|-------|
| **Level 1: Build** | Use Skills to accelerate MAO development | 10x developer productivity |
| **Level 2: Distribute** | Ship Skills as part of MAO product | Distribution channel to Claude ecosystem |
| **Level 3: Test** | MAO tests customer Skills | New product segment ($500M-$1B TAM) |

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THREE-LEVEL SKILLS STRATEGY                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LEVEL 1: BUILD WITH SKILLS                                         │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Developer using Claude Code + Custom Skills               │     │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │     │
│  │  │ mao-arch-    │ │ detection-   │ │ sdk-code-    │       │     │
│  │  │ reviewer     │ │ designer     │ │ generator    │       │     │
│  │  └──────────────┘ └──────────────┘ └──────────────┘       │     │
│  │                         │                                  │     │
│  │                         ▼                                  │     │
│  │              MAO Platform Codebase                         │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                       │
│                              ▼                                       │
│  LEVEL 2: DISTRIBUTE AS SKILLS                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  MAO Product Ships Skills to Claude Users                  │     │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │     │
│  │  │ mao-detect   │ │ mao-fix-     │ │ mao-trace-   │       │     │
│  │  │ -reviewer    │ │ generator    │ │ analyzer     │       │     │
│  │  └──────────────┘ └──────────────┘ └──────────────┘       │     │
│  │                         │                                  │     │
│  │                         ▼                                  │     │
│  │         Claude Users get MAO insights natively             │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                       │
│                              ▼                                       │
│  LEVEL 3: TEST CUSTOMER SKILLS                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  MAO Tests Skills + Multi-Agent Systems                    │     │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │     │
│  │  │ Customer     │ │ Customer     │ │ Multi-Agent  │       │     │
│  │  │ Skill A      │ │ Skill B      │ │ Workflows    │       │     │
│  │  └──────────────┘ └──────────────┘ └──────────────┘       │     │
│  │                         │                                  │     │
│  │                         ▼                                  │     │
│  │    Loop Detection │ Regression │ Output Validation         │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

# LEVEL 1: Using Skills to BUILD MAO

## Philosophy: Eat Your Own Dogfood

Before testing customer Skills, use Skills to build MAO itself. This:
1. Proves the value proposition internally
2. Creates reusable patterns for customers
3. Accelerates development 10x

## Recommended Development Skills

### Skill 1: `mao-architecture-reviewer`

```yaml
---
name: mao-architecture-reviewer
description: Reviews MAO codebase changes for architectural consistency.
Use when modifying detection algorithms, SDK interfaces, or backend services.
Ensures OTEL compatibility, tiered detection patterns, and database schema integrity.
allowed-tools: Read, Grep, Glob
---

# MAO Architecture Review Skill

## Core Principles
- OTEL-first: All traces must be OpenTelemetry compatible
- Tiered detection: Rule-based → Embeddings → LLM → Human
- Cost-aware: Track $/detection at every tier
- Framework-agnostic: No LangGraph/CrewAI specific code in core

## Review Checklist
1. Does this change maintain OTEL span compatibility?
2. Is the detection algorithm in the correct tier?
3. Are database migrations backward-compatible?
4. Is the SDK interface stable (no breaking changes)?

## Architecture Reference
[Load from resources/architecture.md]
```

### Skill 2: `detection-algorithm-designer`

```yaml
---
name: detection-algorithm-designer
description: Designs and validates MAO detection algorithms.
Use when creating new failure mode detectors, optimizing existing algorithms,
or analyzing false positive/negative rates.
allowed-tools: Read, Bash(python:*)
---

# Detection Algorithm Design Skill

## Algorithm Tiers
| Tier | Cost | Latency | Use When |
|------|------|---------|----------|
| 1: Structural Hash | $0 | <1ms | Exact pattern match |
| 2: State Delta | $0 | <5ms | Sequential state changes |
| 3: Local Embeddings | $0 | <50ms | Semantic similarity |
| 4: LLM Judge | $0.50 | <2s | Ambiguous cases |
| 5: Human Review | $50 | <24h | Critical/novel failures |

## Design Process
1. Define failure mode (MAST taxonomy reference)
2. Identify minimum viable detection tier
3. Implement with false positive budget (<5%)
4. Benchmark against labeled trace dataset
5. Document escalation criteria to next tier

## Validation Script
```python
# Run detection validation
python scripts/validate_detector.py --detector=<name> --dataset=mast_labeled
```
```

### Skill 3: `sdk-interface-generator`

```yaml
---
name: sdk-interface-generator
description: Generates SDK interfaces for MAO framework integrations.
Use when adding support for new frameworks (LangGraph, CrewAI, AutoGen, n8n)
or extending existing SDK capabilities.
allowed-tools: Read, Write, Bash(python:*)
---

# SDK Interface Generation Skill

## Framework Integration Pattern

Every framework integration must implement:

```python
class FrameworkAdapter(Protocol):
    def instrument(self, app: Any) -> None:
        """Attach OTEL instrumentation to framework."""

    def extract_state(self, context: Any) -> Dict[str, Any]:
        """Extract agent state for corruption detection."""

    def extract_persona(self, agent: Any) -> str:
        """Extract persona/system prompt for drift detection."""

    def get_dag(self) -> DAG:
        """Extract workflow DAG for coordination analysis."""
```

## Generation Workflow
1. Analyze framework internals (hook points)
2. Map to standard MAO interfaces
3. Generate adapter class
4. Generate integration tests
5. Generate documentation
```

### Skill 4: `mast-failure-classifier`

```yaml
---
name: mast-failure-classifier
description: Classifies agent failures using the MAST taxonomy.
Use when analyzing traces, labeling training data, or designing detectors.
allowed-tools: Read
---

# MAST Failure Classification Skill

## MAST Taxonomy (UC Berkeley)

### Category 1: System Design Failures
| Code | Failure Mode | Description |
|------|--------------|-------------|
| SD-1 | Poor orchestration | Wrong agent sequence or missing agents |
| SD-2 | Wrong assumptions | Incorrect preconditions about environment |
| SD-3 | Resource misconfiguration | API limits, timeouts, rate limits |

### Category 2: Inter-Agent Failures
| Code | Failure Mode | Description |
|------|--------------|-------------|
| IA-1 | Task derailment | Agent ignores assigned task |
| IA-2 | Input ignorance | Agent doesn't use provided context |
| IA-3 | Information withholding | Agent omits critical details |
| IA-4 | Role usurpation | Agent impersonates another agent |

### Category 3: Task Verification Failures
| Code | Failure Mode | Description |
|------|--------------|-------------|
| TV-1 | Output schema violation | Response doesn't match expected format |
| TV-2 | Incomplete execution | Task partially completed |
| TV-3 | Hallucinated completion | Claims done but didn't execute |

## Classification Process
1. Extract trace spans
2. Identify failure symptoms
3. Map to MAST code
4. Assign confidence score
5. Flag for human review if <80% confidence
```

## Development Workflow with Skills

```bash
# Developer workflow using Claude Code + Skills
$ claude

You: Review the changes I made to the loop detector

Claude: [Invokes mao-architecture-reviewer skill]
        [Loads architecture.md resource]

Analysis:
- ✅ OTEL span compatibility maintained
- ⚠️ Detection moved from Tier 1 to Tier 3 - justify?
- ❌ Missing false positive budget documentation

You: Design a new detector for role usurpation (IA-4)

Claude: [Invokes detection-algorithm-designer skill]
        [Invokes mast-failure-classifier skill]

Recommendation:
- Tier 3 (Local Embeddings) - compare persona embeddings
- Escalate to Tier 4 if similarity score between 0.7-0.9
- Estimated false positive rate: 3.2%
```

---

# LEVEL 2: Skills AS PART OF MAO Product

## Philosophy: Distribution Through Claude Ecosystem

Ship Skills that give Claude users MAO capabilities without leaving Claude Code. This:
1. Creates distribution channel (Claude's install base)
2. Lowers barrier to entry (no SDK integration needed)
3. Upsells to full platform

## Product Skills to Ship

### Skill 1: `mao-detection-reviewer`

```yaml
---
name: mao-detection-reviewer
description: Reviews MAO Testing Platform detection results and explains failures.
Use when analyzing agent failures, reviewing trace anomalies, or debugging
multi-agent orchestration issues detected by MAO.
allowed-tools: Read, WebFetch
---

# MAO Detection Review Skill

## Capabilities
- Fetch detection results from MAO API
- Explain root causes in natural language
- Prioritize issues by severity and cost impact
- Suggest investigation paths

## Detection Types Explained

### Loop Detection
A loop occurs when agents repeatedly exchange similar messages without progress.

**Indicators:**
- Structural: Exact message hash repeats
- Semantic: Embedding similarity >0.95 across 3+ turns
- State: No state delta between iterations

**Common Causes:**
1. Missing termination condition
2. Ambiguous task handoff
3. Circular dependency in agent roles

### State Corruption
State corruption occurs when shared state becomes invalid.

**Indicators:**
- Schema violation (JSON parsing fails)
- Cross-field inconsistency (totals don't match)
- Domain constraint violation (negative quantities)

### Persona Drift
Persona drift occurs when an agent's behavior diverges from its defined role.

**Indicators:**
- Embedding distance from baseline >0.3
- Tool usage outside expected patterns
- Response style/tone shift

## Usage
```
You: Review MAO detections for workflow "customer-support-v2"

Claude: [Fetches from MAO API]

Found 3 detections in last 24h:

1. LOOP (High Severity) - $127 token cost
   Agents: Classifier → Router → Classifier
   Root cause: Router returns to Classifier on "unknown" intent

2. STATE_CORRUPTION (Medium) - Trace #4521
   Field: customer.email
   Issue: Null value propagated to downstream agents

3. PERSONA_DRIFT (Low) - Agent "Summarizer"
   Drift score: 0.31 (threshold: 0.30)
   Likely cause: Recent prompt update
```
```

### Skill 2: `mao-fix-generator`

```yaml
---
name: mao-fix-generator
description: Generates code fixes for multi-agent failures detected by MAO.
Use when a loop, state corruption, persona drift, or coordination failure
needs remediation. Produces framework-specific fixes.
allowed-tools: Read, Write
---

# MAO Fix Generation Skill

## Fix Patterns by Failure Type

### Loop Breaking
```python
# LangGraph fix pattern
def add_loop_breaker(graph: StateGraph, max_iterations: int = 5):
    """Inject loop counter into state and add termination edge."""

    # Add iteration counter to state
    graph.state_schema["_mao_loop_count"] = int

    # Add conditional edge that terminates on max
    graph.add_conditional_edges(
        "*",  # All nodes
        lambda state: "END" if state["_mao_loop_count"] > max_iterations else CONTINUE
    )
```

### State Validation
```python
# Pydantic validation middleware
from pydantic import BaseModel, validator

class AgentState(BaseModel):
    customer_email: str
    order_total: float
    items: List[Item]

    @validator('order_total')
    def total_matches_items(cls, v, values):
        expected = sum(item.price for item in values.get('items', []))
        if abs(v - expected) > 0.01:
            raise ValueError(f"Total {v} doesn't match items sum {expected}")
        return v
```

### Persona Reinforcement
```python
# Add persona anchor to system prompt
REINFORCED_PROMPT = '''
{original_system_prompt}

CRITICAL CONSTRAINTS (DO NOT VIOLATE):
- You are ONLY the {role_name} agent
- You must NEVER perform actions assigned to other agents
- If asked to do something outside your role, respond: "That's outside my role as {role_name}"

Your role boundaries:
- CAN: {allowed_actions}
- CANNOT: {prohibited_actions}
'''
```

## Usage
```
You: Generate fix for loop detection in workflow "order-processor"

Claude: [Analyzes detection details]

Fix generated for LangGraph workflow:

1. Add to state schema:
   ```python
   class OrderState(TypedDict):
       # ... existing fields ...
       _loop_count: int  # NEW
   ```

2. Modify router node:
   ```python
   def router(state: OrderState) -> str:
       state["_loop_count"] = state.get("_loop_count", 0) + 1
       if state["_loop_count"] > 5:
           return "escalate_to_human"
       # ... existing logic ...
   ```

3. Add edge:
   ```python
   graph.add_edge("router", "escalate_to_human")
   ```

Shall I apply this fix to your codebase?
```
```

### Skill 3: `mao-trace-analyzer`

```yaml
---
name: mao-trace-analyzer
description: Analyzes OTEL traces from multi-agent workflows.
Use when debugging agent behavior, understanding execution flow,
or investigating anomalies without full MAO platform access.
allowed-tools: Read, Bash(python:*)
---

# MAO Trace Analysis Skill

## Trace Format (OTEL)
```json
{
  "trace_id": "abc123",
  "spans": [
    {
      "span_id": "span1",
      "name": "agent.researcher.execute",
      "parent_span_id": null,
      "start_time": "2025-12-01T10:00:00Z",
      "end_time": "2025-12-01T10:00:05Z",
      "attributes": {
        "agent.name": "researcher",
        "agent.input": "Find pricing for competitor X",
        "agent.output": "Found 3 pricing tiers...",
        "llm.token_count": 1523,
        "llm.model": "claude-3-5-sonnet"
      }
    }
  ]
}
```

## Analysis Capabilities

### 1. Execution Flow Visualization
```
Trace: abc123 (Total: 45.2s, $0.89)
├── researcher (5.2s, $0.12)
│   └── tool:web_search (3.1s)
├── analyzer (12.4s, $0.34)
│   ├── tool:calculator (0.1s)
│   └── llm:summarize (11.2s)
└── writer (27.6s, $0.43)
    └── llm:generate_report (26.8s)
```

### 2. Anomaly Detection
- Span duration >2σ from baseline
- Token count >2σ from baseline
- Missing expected tool calls
- Unexpected agent invocations

### 3. Cost Attribution
- Per-agent token costs
- Per-tool latency breakdown
- Bottleneck identification

## Local Analysis (No MAO Account Required)
```python
# Analyze local trace file
from mao_trace_analyzer import analyze

results = analyze("trace.json")
print(results.flow_diagram)
print(results.anomalies)
print(results.cost_breakdown)
```
```

## Distribution Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                   SKILL DISTRIBUTION FUNNEL                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  FREE TIER (Skills only, no account)                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │ • mao-trace-analyzer (local analysis)              │     │
│  │ • mao-failure-explainer (educational)              │     │
│  │ • 100 trace analyses/month                         │     │
│  └────────────────────────────────────────────────────┘     │
│                         │                                    │
│                         ▼ (Convert 10%)                      │
│  STARTER ($99/mo)                                           │
│  ┌────────────────────────────────────────────────────┐     │
│  │ • mao-detection-reviewer (live detections)         │     │
│  │ • mao-fix-generator (automated fixes)              │     │
│  │ • 1,000 traces/month                               │     │
│  └────────────────────────────────────────────────────┘     │
│                         │                                    │
│                         ▼ (Convert 20%)                      │
│  PLATFORM ($500+/mo)                                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │ • Full MAO Platform access                         │     │
│  │ • Dashboard, alerting, SDK                         │     │
│  │ • Unlimited traces                                 │     │
│  │ • Skills included                                  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

# LEVEL 3: MAO Tests Customer Skills

## Philosophy: New Product Category

No one is testing Skills today. MAO can own this category.

## Technical Architecture

### Skill Testing vs Multi-Agent Testing

| Dimension | Multi-Agent Testing | Skill Testing |
|-----------|---------------------|---------------|
| **Unit of Analysis** | Agent node in DAG | Skill invocation |
| **Orchestration** | Explicit (LangGraph) | Implicit (Claude decides) |
| **State** | Shared state object | Context window |
| **Communication** | Inter-agent messages | Skill outputs |
| **Instrumentation** | Framework hooks | Claude API/logs |

### Skill Testing Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MAO SKILL TESTING ENGINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DATA COLLECTION                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Option A: Claude API Proxy                               │  │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐              │  │
│  │  │ Client  │───▶│ MAO     │───▶│ Claude  │              │  │
│  │  │ App     │    │ Proxy   │    │ API     │              │  │
│  │  └─────────┘    └─────────┘    └─────────┘              │  │
│  │                      │                                    │  │
│  │                      ▼                                    │  │
│  │              Skill invocations captured                   │  │
│  │                                                           │  │
│  │  Option B: Claude Code Log Parser                        │  │
│  │  ┌─────────┐    ┌─────────┐                             │  │
│  │  │ Claude  │───▶│ MAO Log │                             │  │
│  │  │ Code    │    │ Parser  │                             │  │
│  │  └─────────┘    └─────────┘                             │  │
│  │                      │                                    │  │
│  │                      ▼                                    │  │
│  │              Skill metadata extracted                     │  │
│  │                                                           │  │
│  │  Option C: Anthropic Partnership (Future)                │  │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐              │  │
│  │  │ Claude  │───▶│Anthropic│───▶│ MAO     │              │  │
│  │  │ API     │    │Telemetry│    │ Ingest  │              │  │
│  │  └─────────┘    └─────────┘    └─────────┘              │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  SKILL TRACE SCHEMA                                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ {                                                         │  │
│  │   "trace_id": "skill-trace-001",                         │  │
│  │   "session_id": "claude-code-session-xyz",               │  │
│  │   "skill_invocations": [                                 │  │
│  │     {                                                     │  │
│  │       "skill_name": "code-reviewer",                     │  │
│  │       "trigger": "semantic",                             │  │
│  │       "input_context": "Review this PR...",              │  │
│  │       "resources_loaded": ["style-guide.md"],            │  │
│  │       "output": "Found 3 issues...",                     │  │
│  │       "tokens_used": 4521,                               │  │
│  │       "duration_ms": 3200,                               │  │
│  │       "tools_invoked": ["Read", "Grep"]                  │  │
│  │     }                                                     │  │
│  │   ],                                                      │  │
│  │   "skill_chain": ["code-reviewer", "test-generator"],    │  │
│  │   "total_cost": 0.045                                    │  │
│  │ }                                                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  DETECTION ALGORITHMS                                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  1. SKILL LOOP DETECTION                                 │  │
│  │     ┌─────────────────────────────────────────────────┐  │  │
│  │     │ Tier 1: Invocation hash                         │  │  │
│  │     │   - Same skill invoked 3+ times in session      │  │  │
│  │     │   - Input similarity >0.95                       │  │  │
│  │     │                                                  │  │  │
│  │     │ Tier 2: Output cycle detection                  │  │  │
│  │     │   - Skill A output triggers Skill B             │  │  │
│  │     │   - Skill B output triggers Skill A             │  │  │
│  │     │                                                  │  │  │
│  │     │ Tier 3: Semantic loop                           │  │  │
│  │     │   - Different inputs, same semantic intent      │  │  │
│  │     │   - Embedding similarity across invocations     │  │  │
│  │     └─────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  2. SKILL REGRESSION DETECTION                           │  │
│  │     ┌─────────────────────────────────────────────────┐  │  │
│  │     │ Golden Output Comparison                        │  │  │
│  │     │   - Store baseline outputs for test inputs      │  │  │
│  │     │   - Detect semantic drift after SKILL.md edits  │  │  │
│  │     │   - Alert on output schema changes              │  │  │
│  │     │                                                  │  │  │
│  │     │ Behavioral Fingerprinting                       │  │  │
│  │     │   - Track tool usage patterns                   │  │  │
│  │     │   - Detect resource loading changes             │  │  │
│  │     │   - Monitor token consumption shifts            │  │  │
│  │     └─────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  3. SKILL CHAIN ANALYSIS                                 │  │
│  │     ┌─────────────────────────────────────────────────┐  │  │
│  │     │ Implicit DAG Construction                       │  │  │
│  │     │   - Build graph from skill invocation sequences │  │  │
│  │     │   - Identify common chains                       │  │  │
│  │     │   - Detect unexpected chains (anomaly)          │  │  │
│  │     │                                                  │  │  │
│  │     │ Chain Optimization Suggestions                  │  │  │
│  │     │   - "Skill A always precedes B, consider merge" │  │  │
│  │     │   - "Skill C never completes, check trigger"    │  │  │
│  │     └─────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  4. TOOL ESCAPE DETECTION                                │  │
│  │     ┌─────────────────────────────────────────────────┐  │  │
│  │     │ Policy Enforcement Monitoring                   │  │  │
│  │     │   - Skill declares: allowed-tools: Read, Grep   │  │  │
│  │     │   - Detect if Bash, Write attempted             │  │  │
│  │     │   - Alert on policy violations                  │  │  │
│  │     └─────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  5. RESOURCE BLOAT DETECTION                             │  │
│  │     ┌─────────────────────────────────────────────────┐  │  │
│  │     │ Context Window Monitoring                       │  │  │
│  │     │   - Track resources loaded per invocation       │  │  │
│  │     │   - Alert if resources >50% of context          │  │  │
│  │     │   - Suggest resource optimization               │  │  │
│  │     └─────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema for Skill Testing

```sql
-- Skill invocation traces
CREATE TABLE skill_traces (
    id UUID PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    skill_name TEXT NOT NULL,
    trigger_type TEXT, -- 'semantic', 'explicit', 'chained'
    input_hash TEXT,
    input_embedding VECTOR(1536),
    output_hash TEXT,
    output_embedding VECTOR(1536),
    tokens_used INT,
    duration_ms INT,
    resources_loaded JSONB,
    tools_invoked TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skill chain analysis
CREATE TABLE skill_chains (
    id UUID PRIMARY KEY,
    session_id TEXT NOT NULL,
    chain_sequence TEXT[], -- ['skill-a', 'skill-b', 'skill-c']
    chain_hash TEXT,
    occurrence_count INT DEFAULT 1,
    avg_duration_ms FLOAT,
    avg_tokens FLOAT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ
);

-- Skill golden outputs (for regression)
CREATE TABLE skill_golden_outputs (
    id UUID PRIMARY KEY,
    skill_name TEXT NOT NULL,
    test_input TEXT NOT NULL,
    test_input_hash TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    expected_output_embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skill detections
CREATE TABLE skill_detections (
    id UUID PRIMARY KEY,
    trace_id UUID REFERENCES skill_traces(id),
    detection_type TEXT NOT NULL, -- 'loop', 'regression', 'tool_escape', 'resource_bloat'
    severity TEXT NOT NULL, -- 'low', 'medium', 'high', 'critical'
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_skill_traces_session ON skill_traces(session_id);
CREATE INDEX idx_skill_traces_name ON skill_traces(skill_name);
CREATE INDEX idx_skill_traces_input_embedding ON skill_traces USING ivfflat (input_embedding vector_cosine_ops);
CREATE INDEX idx_skill_chains_hash ON skill_chains(chain_hash);
```

### SDK for Skill Testing

```python
# mao_testing/skills/tracer.py

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import hashlib

@dataclass
class SkillInvocation:
    skill_name: str
    trigger_type: str  # 'semantic', 'explicit', 'chained'
    input_context: str
    output: str
    resources_loaded: List[str]
    tools_invoked: List[str]
    tokens_used: int
    duration_ms: int
    timestamp: str

class SkillTracer:
    """Trace skill invocations for MAO analysis."""

    def __init__(self, api_key: str, endpoint: str = "https://api.mao-testing.com"):
        self.api_key = api_key
        self.endpoint = endpoint
        self.session_id = self._generate_session_id()
        self.invocations: List[SkillInvocation] = []

    def trace_invocation(self, invocation: SkillInvocation) -> None:
        """Record a skill invocation."""
        self.invocations.append(invocation)
        self._check_loop_detection(invocation)
        self._send_to_backend(invocation)

    def _check_loop_detection(self, invocation: SkillInvocation) -> None:
        """Real-time loop detection."""
        # Count recent invocations of same skill
        recent = [i for i in self.invocations[-10:] if i.skill_name == invocation.skill_name]
        if len(recent) >= 3:
            # Check input similarity
            input_hashes = [hashlib.md5(i.input_context.encode()).hexdigest()[:8] for i in recent]
            if len(set(input_hashes)) == 1:
                self._alert_loop_detected(invocation.skill_name, "exact_input_match")

    def get_skill_chain(self) -> List[str]:
        """Get the current skill invocation chain."""
        return [i.skill_name for i in self.invocations]

    def run_regression_tests(self, skill_name: str, golden_inputs: List[str]) -> Dict[str, Any]:
        """Run regression tests against golden outputs."""
        results = []
        for input_text in golden_inputs:
            # Would invoke skill and compare to stored golden output
            pass
        return {"skill": skill_name, "tests": len(golden_inputs), "results": results}


# Claude Code integration (hypothetical)
class ClaudeCodeSkillTracer(SkillTracer):
    """Integration with Claude Code skill system."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._hook_into_claude_code()

    def _hook_into_claude_code(self) -> None:
        """Hook into Claude Code's skill invocation lifecycle.

        NOTE: This would require Anthropic to expose hooks, or we parse logs.
        """
        # Option 1: If Anthropic provides hooks
        # claude_code.on_skill_invoked(self._on_skill_invoked)

        # Option 2: Parse Claude Code logs
        # self._start_log_watcher()
        pass

    def _on_skill_invoked(self, event: Dict[str, Any]) -> None:
        """Callback when a skill is invoked."""
        invocation = SkillInvocation(
            skill_name=event["skill_name"],
            trigger_type=event["trigger"],
            input_context=event["input"],
            output=event["output"],
            resources_loaded=event.get("resources", []),
            tools_invoked=event.get("tools", []),
            tokens_used=event.get("tokens", 0),
            duration_ms=event.get("duration_ms", 0),
            timestamp=event["timestamp"]
        )
        self.trace_invocation(invocation)
```

## Product Roadmap: Skill Testing

### Phase 1: Log-Based Analysis (Months 1-3)
- Parse Claude Code logs for skill invocations
- Build skill chain visualization
- Basic loop detection (hash-based)
- **No integration required** - works with existing Claude Code

### Phase 2: Proxy-Based Collection (Months 4-6)
- MAO proxy for Claude API
- Real-time skill invocation capture
- Full token/cost attribution
- Regression testing with golden outputs

### Phase 3: Native Integration (Months 7-12)
- Partner with Anthropic for native hooks
- First-party skill telemetry
- Skill marketplace analytics
- Enterprise skill governance

## Pricing for Skill Testing

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | 100 skill traces/month, basic loop detection |
| **Pro** | $49/mo | 5,000 traces, regression testing, alerts |
| **Team** | $199/mo | 50,000 traces, golden outputs, dashboards |
| **Enterprise** | Custom | Unlimited, SSO, dedicated support |

---

# Strategic Synthesis

## The Flywheel

```
┌─────────────────────────────────────────────────────────────────┐
│                      MAO SKILLS FLYWHEEL                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                    ┌──────────────────┐                         │
│                    │  LEVEL 1: BUILD  │                         │
│                    │  Use Skills to   │                         │
│                    │  build MAO fast  │                         │
│                    └────────┬─────────┘                         │
│                             │                                    │
│              ┌──────────────┴──────────────┐                    │
│              ▼                              ▼                    │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │ LEVEL 2: SHIP    │          │ LEVEL 3: TEST    │            │
│  │ Skills as        │◀────────▶│ Customer Skills  │            │
│  │ distribution     │          │ as product       │            │
│  └────────┬─────────┘          └────────┬─────────┘            │
│           │                              │                       │
│           │      ┌──────────────────┐    │                       │
│           └─────▶│ MORE CUSTOMERS   │◀───┘                       │
│                  │ More data        │                            │
│                  │ Better detection │                            │
│                  └────────┬─────────┘                            │
│                           │                                      │
│                           ▼                                      │
│                  ┌──────────────────┐                           │
│                  │ BETTER SKILLS    │                           │
│                  │ (back to L1)     │                           │
│                  └──────────────────┘                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Competitive Advantage

| Competitor | Multi-Agent Testing | Skill Testing |
|------------|---------------------|---------------|
| LangSmith | ✅ (LangGraph only) | ❌ |
| Arize | ✅ (Generic) | ❌ |
| Braintrust | ⚠️ (Limited) | ❌ |
| **MAO** | ✅ (All frameworks) | ✅ (Only player) |

## Why This Works

1. **Level 1 (Build)**: Skills make MAO development faster
2. **Level 2 (Distribute)**: Skills give MAO distribution through Claude ecosystem
3. **Level 3 (Test)**: Skill testing is a new product category with zero competition
4. **Flywheel**: Each level reinforces the others

## Immediate Next Steps

1. **Week 1-2**: Build Level 1 skills for MAO development
   - `mao-architecture-reviewer`
   - `detection-algorithm-designer`

2. **Week 3-4**: Build Level 2 skills for distribution
   - `mao-trace-analyzer` (free tier)
   - `mao-detection-reviewer` (paid tier)

3. **Month 2-3**: Build Level 3 skill testing MVP
   - Claude Code log parser
   - Basic loop detection
   - Skill chain visualization

4. **Month 4+**: Anthropic partnership discussions
   - Native skill telemetry access
   - Skill marketplace integration

---

*Strategy document - December 2025*
