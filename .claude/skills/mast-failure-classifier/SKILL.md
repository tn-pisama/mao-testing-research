---
name: mast-failure-classifier
description: |
  Classifies multi-agent system failures using the MAST taxonomy.
  Use when analyzing traces to identify failure types, severities, and root causes.
  Provides consistent failure categorization, severity scoring, and remediation guidance.
  Essential for building the failure detection training data and improving detection algorithms.
allowed-tools: Read, Grep, Glob
---

# MAST Failure Classifier Skill

You are classifying failures in Multi-Agent System Traces (MAST). Your goal is to accurately categorize failures using a consistent taxonomy, enabling systematic analysis and improvement of detection algorithms.

## MAST Failure Taxonomy

### Level 1: Primary Categories

```
MAST Failures
├── LOOP          # Repetitive behavior without progress
├── STATE         # State-related issues
├── PERSONA       # Agent behavior violations
├── COORDINATION  # Multi-agent interaction failures
└── RESOURCE      # Cost/performance issues
```

### Level 2: Subcategories

#### LOOP Failures

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| LOOP-001 | Exact Message Loop | Same message repeated 3+ times | Medium |
| LOOP-002 | Structural Loop | Same structure, different values | Medium |
| LOOP-003 | Semantic Loop | Same meaning, different wording | High |
| LOOP-004 | Tool Cycle | Same tool sequence repeats | Medium |
| LOOP-005 | Conversation Circle | Discussion returns to same point | High |
| LOOP-006 | Escalation Loop | Repeated escalation attempts | Critical |

#### STATE Failures

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| STATE-001 | No Progress | State unchanged despite actions | Medium |
| STATE-002 | State Regression | State reverts to previous value | High |
| STATE-003 | Invalid Transition | Transition violates state machine | High |
| STATE-004 | State Corruption | State becomes invalid/malformed | Critical |
| STATE-005 | State Loss | State data missing after operation | Critical |
| STATE-006 | Race Condition | Concurrent state modifications | High |

#### PERSONA Failures

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| PERSONA-001 | Persona Drift | Behavior deviates from system prompt | Medium |
| PERSONA-002 | Role Confusion | Agent acts outside defined role | High |
| PERSONA-003 | Capability Claim | Claims abilities it doesn't have | High |
| PERSONA-004 | Persona Collapse | Completely abandons persona | Critical |
| PERSONA-005 | Cross-Contamination | Adopts another agent's persona | High |

#### COORDINATION Failures

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| COORD-001 | Handoff Failure | Agent handoff not completed | High |
| COORD-002 | Message Loss | Communication between agents lost | Critical |
| COORD-003 | Deadlock | Agents waiting on each other | Critical |
| COORD-004 | Priority Inversion | Wrong agent takes precedence | Medium |
| COORD-005 | Cascade Failure | One failure triggers others | Critical |
| COORD-006 | Coordination Overhead | Excessive inter-agent communication | Medium |

#### RESOURCE Failures

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| RESOURCE-001 | Token Explosion | Excessive token usage | High |
| RESOURCE-002 | Timeout | Operation exceeded time limit | Medium |
| RESOURCE-003 | Rate Limit | API rate limit exceeded | Medium |
| RESOURCE-004 | Cost Overrun | Exceeded cost budget | High |
| RESOURCE-005 | Memory Exhaustion | Context window exhausted | Critical |

## Classification Process

### Step 1: Initial Triage

First, identify the primary failure category:

```markdown
## Quick Category Check

1. Is there repetitive behavior?
   → YES: Likely LOOP
   → Check: LOOP-001 through LOOP-006

2. Is the state wrong or not changing?
   → YES: Likely STATE
   → Check: STATE-001 through STATE-006

3. Is an agent behaving out of character?
   → YES: Likely PERSONA
   → Check: PERSONA-001 through PERSONA-005

4. Are multiple agents involved in the failure?
   → YES: Likely COORDINATION
   → Check: COORD-001 through COORD-006

5. Is it about cost, time, or resources?
   → YES: Likely RESOURCE
   → Check: RESOURCE-001 through RESOURCE-005
```

### Step 2: Detailed Classification

For each suspected failure, evaluate:

```markdown
## Failure Analysis Template

**Trace ID**: [trace_id]
**Failure Code**: [e.g., LOOP-003]
**Confidence**: [0.0-1.0]

**Evidence**:
- Span IDs involved: [list]
- Key attributes: [relevant mao.* attributes]
- Pattern observed: [description]

**Severity Assessment**:
- Base severity: [from taxonomy]
- Adjusted severity: [if context changes it]
- Justification: [why adjustment if any]

**Root Cause Hypothesis**:
[What likely caused this failure]

**Recommended Fix Category**:
- Prompt engineering
- State management
- Coordination logic
- Resource limits
- Architecture change
```

### Step 3: Severity Calibration

Adjust base severity based on context:

| Factor | Severity Adjustment |
|--------|---------------------|
| Affects end user | +1 level |
| Causes data loss | +1 level |
| Auto-recoverable | -1 level |
| First occurrence | -1 level |
| Repeated occurrence | +1 level |
| Cascaded from another failure | -1 level (for secondary) |

Severity Scale:
- **Low**: Minor issue, doesn't affect outcome
- **Medium**: Noticeable issue, may affect quality
- **High**: Significant issue, affects reliability
- **Critical**: Severe issue, requires immediate attention

### Step 4: Multi-Failure Analysis

When multiple failures exist in one trace:

```markdown
## Multi-Failure Report

**Primary Failure**: [The root cause]
- Code: [e.g., STATE-003]
- Confidence: [0.0-1.0]

**Secondary Failures**: [Caused by primary]
1. Code: [e.g., LOOP-002]
   - Caused by: [primary failure code]
   - Relationship: [direct/indirect]

2. Code: [e.g., COORD-001]
   - Caused by: [...]
   - Relationship: [...]

**Cascade Analysis**:
[Diagram or description of failure cascade]
```

## Classification Examples

### Example 1: Semantic Loop

**Trace Pattern**:
```
Span 1: Agent says "I'll search for that information"
Span 2: Agent says "Let me look that up for you"
Span 3: Agent says "I'll find that data"
Span 4: Agent says "Searching for the requested information"
```

**Classification**:
```
Failure Code: LOOP-003 (Semantic Loop)
Confidence: 0.92
Severity: High

Evidence:
- 4 semantically similar messages
- Embedding similarity: 0.94 average
- No state progress between spans

Root Cause: Agent lacks feedback that action was already taken
Recommended Fix: State management - track initiated actions
```

### Example 2: Coordination Failure with Cascade

**Trace Pattern**:
```
Agent A: Completes task, attempts handoff
Agent B: Never receives handoff
Agent A: Retries handoff (x3)
Agent A: Falls into retry loop
```

**Classification**:
```
Primary Failure:
- Code: COORD-001 (Handoff Failure)
- Confidence: 0.95
- Severity: High

Secondary Failure:
- Code: LOOP-006 (Escalation Loop)
- Confidence: 0.88
- Caused by: COORD-001
- Severity: Medium (adjusted from Critical - it's secondary)

Cascade: COORD-001 → LOOP-006
Root Cause: Missing handoff acknowledgment mechanism
```

### Example 3: State Corruption

**Trace Pattern**:
```
State before: {"items": ["a", "b"], "count": 2}
Operation: Add item "c"
State after: {"items": ["a", "b", "c"], "count": 2}  # count not updated
```

**Classification**:
```
Failure Code: STATE-004 (State Corruption)
Confidence: 0.98
Severity: Critical

Evidence:
- State internal inconsistency
- items.length (3) != count (2)

Root Cause: Partial state update, count not synchronized
Recommended Fix: Atomic state updates or computed properties
```

## Output Format

When classifying failures, use this structure:

```json
{
  "trace_id": "abc123",
  "classification_timestamp": "2025-01-01T12:00:00Z",
  "failures": [
    {
      "code": "LOOP-003",
      "name": "Semantic Loop",
      "confidence": 0.92,
      "severity": "high",
      "is_primary": true,
      "span_ids": ["span1", "span2", "span3", "span4"],
      "evidence": {
        "pattern": "4 semantically similar messages",
        "metrics": {
          "similarity_avg": 0.94,
          "state_progress": false
        }
      },
      "root_cause": "Agent lacks action completion feedback",
      "recommended_fix": {
        "category": "state_management",
        "description": "Track initiated actions in state"
      }
    }
  ],
  "cascade_analysis": {
    "has_cascade": false,
    "primary_failure": "LOOP-003",
    "cascade_chain": []
  },
  "overall_severity": "high",
  "requires_immediate_attention": false
}
```

## Resources

For detailed specifications, I can load:
- `resources/failure-taxonomy-full.md` - Complete taxonomy with all codes
- `resources/classification-examples.md` - 50+ classified examples
- `resources/severity-guidelines.md` - Detailed severity calibration rules
