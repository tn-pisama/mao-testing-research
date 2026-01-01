# MAST Failure Taxonomy - Complete Reference

## Overview

The Multi-Agent System Trace (MAST) failure taxonomy provides a standardized classification system for failures observed in multi-agent workflows. This enables consistent labeling, analysis, and improvement of detection algorithms.

---

## LOOP Failures

Failures where agents exhibit repetitive behavior without meaningful progress.

### LOOP-001: Exact Message Loop

**Definition**: Agent outputs the exact same message 3 or more times.

**Detection Tier**: 1 (Hash-based)

**Indicators**:
- Identical message content
- Same structural format
- No state change between occurrences

**Example**:
```
Agent: "I'll help you with that."
Agent: "I'll help you with that."
Agent: "I'll help you with that."
```

**Common Causes**:
- Missing response acknowledgment
- State not updated after action
- Faulty termination condition

**Severity**: Medium

---

### LOOP-002: Structural Loop

**Definition**: Agent outputs messages with identical structure but different variable content.

**Detection Tier**: 1 (Structural fingerprint)

**Indicators**:
- Same message template
- Only numbers/names/IDs change
- Pattern repeats 3+ times

**Example**:
```
Agent: "Processing item 1 of 100"
Agent: "Processing item 1 of 100"  # Stuck, not progressing
Agent: "Processing item 1 of 100"
```

**Common Causes**:
- Iterator not advancing
- Off-by-one errors
- Retry logic without backoff

**Severity**: Medium

---

### LOOP-003: Semantic Loop

**Definition**: Agent outputs messages with same meaning but different wording.

**Detection Tier**: 3 (Embeddings)

**Indicators**:
- Embedding similarity > 0.95
- Paraphrased content
- No semantic progress

**Example**:
```
Agent: "I'll search for that information."
Agent: "Let me look that up for you."
Agent: "I'll find that data now."
```

**Common Causes**:
- LLM regenerating similar responses
- Missing memory of previous actions
- Prompt not including action history

**Severity**: High

---

### LOOP-004: Tool Cycle

**Definition**: Same sequence of tool calls repeats without achieving goal.

**Detection Tier**: 1-2 (Sequence matching)

**Indicators**:
- Tool call sequence repeats
- Each cycle produces same/similar results
- Goal not achieved

**Example**:
```
search("weather NYC") → no results
read("weather.txt") → file not found
search("weather NYC") → no results  # Repeating
read("weather.txt") → file not found
```

**Common Causes**:
- No alternative strategy when primary fails
- Missing failure handling
- Incorrect success condition

**Severity**: Medium

---

### LOOP-005: Conversation Circle

**Definition**: Multi-turn conversation returns to previously discussed point.

**Detection Tier**: 3 (Semantic similarity)

**Indicators**:
- Topic revisited after apparent resolution
- Questions re-asked
- Agreement reached then undone

**Example**:
```
Turn 5: "So we'll use Python for this project."
Turn 6: "Sounds good, Python it is."
...
Turn 12: "Should we use Python or JavaScript?"
Turn 13: "I think Python would be best."
```

**Common Causes**:
- Insufficient context window
- Decision not persisted in state
- Conflicting agent goals

**Severity**: High

---

### LOOP-006: Escalation Loop

**Definition**: Agent repeatedly attempts escalation without success.

**Detection Tier**: 2 (State + action sequence)

**Indicators**:
- Multiple escalation attempts
- Escalation not acknowledged
- Agent continues trying

**Example**:
```
Agent A: "I need to escalate this to a supervisor."
System: [Escalation attempted]
Agent A: "Let me try escalating again."
System: [Escalation attempted]
Agent A: "I'll escalate this issue."
```

**Common Causes**:
- Escalation endpoint unavailable
- Missing acknowledgment mechanism
- No fallback strategy

**Severity**: Critical

---

## STATE Failures

Failures involving incorrect or problematic state management.

### STATE-001: No Progress

**Definition**: State remains unchanged despite agent actions.

**Detection Tier**: 2 (State delta)

**Indicators**:
- state.before == state.after for 3+ spans
- Actions being taken but not reflected
- Progress metrics static

**Example**:
```
Span 1: state = {"completed": 0, "total": 10}
[Agent processes item]
Span 2: state = {"completed": 0, "total": 10}  # No change
[Agent processes item]
Span 3: state = {"completed": 0, "total": 10}  # Still no change
```

**Common Causes**:
- State update logic not triggered
- Immutable state modified incorrectly
- Race condition in updates

**Severity**: Medium

---

### STATE-002: State Regression

**Definition**: State reverts to a previous value after progressing.

**Detection Tier**: 2 (State history comparison)

**Indicators**:
- state[n] == state[n-k] where k > 1
- Progress undone
- Non-monotonic state fields

**Example**:
```
Span 1: state = {"step": 1}
Span 2: state = {"step": 2}
Span 3: state = {"step": 3}
Span 4: state = {"step": 1}  # Regressed!
```

**Common Causes**:
- State overwritten instead of merged
- Parallel updates with stale data
- Incorrect state restoration

**Severity**: High

---

### STATE-003: Invalid Transition

**Definition**: State transition violates defined state machine rules.

**Detection Tier**: 2 (Transition validation)

**Indicators**:
- Transition not in allowed set
- Skipped intermediate states
- Invalid state combination

**Example**:
```
Valid: draft → submitted → approved → published
Actual: draft → published  # Skipped intermediate states!
```

**Common Causes**:
- Business logic bypass
- Missing validation
- Corrupted transition logic

**Severity**: High

---

### STATE-004: State Corruption

**Definition**: State becomes internally inconsistent or malformed.

**Detection Tier**: 2-3 (Validation + semantic)

**Indicators**:
- Schema violation
- Referential integrity broken
- Impossible value combinations

**Example**:
```
state = {
  "items": ["a", "b", "c"],
  "count": 2,  # Should be 3!
  "status": "empty"  # Should be "has_items"!
}
```

**Common Causes**:
- Partial updates
- Missing atomicity
- Incorrect merge logic

**Severity**: Critical

---

### STATE-005: State Loss

**Definition**: State data disappears or becomes undefined unexpectedly.

**Detection Tier**: 2 (Null/undefined detection)

**Indicators**:
- Required fields become null
- Nested objects disappear
- Array becomes empty unexpectedly

**Example**:
```
Before: {"user": {"name": "Alice", "id": 123}}
After:  {"user": null}
```

**Common Causes**:
- Serialization error
- Timeout during save
- Incorrect delete operation

**Severity**: Critical

---

### STATE-006: Race Condition

**Definition**: Concurrent state modifications cause inconsistency.

**Detection Tier**: 2-4 (Timing + causal analysis)

**Indicators**:
- Overlapping span timestamps
- State changes don't compose correctly
- Final state missing some updates

**Example**:
```
Time 0: state = {"count": 0}
Time 1 (Agent A): read count (0), increment, write count (1)
Time 1 (Agent B): read count (0), increment, write count (1)
Time 2: state = {"count": 1}  # Should be 2!
```

**Common Causes**:
- Missing locks/transactions
- Optimistic concurrency without retry
- Shared mutable state

**Severity**: High

---

## PERSONA Failures

Failures where agents deviate from their defined character/role.

### PERSONA-001: Persona Drift

**Definition**: Agent's behavior gradually deviates from system prompt.

**Detection Tier**: 3 (Embedding drift)

**Indicators**:
- Response style changes over time
- Vocabulary shifts
- Tone becomes inconsistent

**Example**:
```
System: "You are a formal customer service agent."
Early: "Good afternoon. How may I assist you today?"
Later: "Hey! What's up? Need help with something?"
```

**Common Causes**:
- Context window pressure
- User influence on tone
- Conflicting instructions

**Severity**: Medium

---

### PERSONA-002: Role Confusion

**Definition**: Agent performs actions outside its defined role.

**Detection Tier**: 3-4 (Role + action analysis)

**Indicators**:
- Actions inconsistent with role
- Attempts unauthorized operations
- Crosses role boundaries

**Example**:
```
Role: "Research Assistant - gather information only"
Action: "I'll go ahead and make that purchase for you."
```

**Common Causes**:
- Unclear role boundaries
- User pressure
- Missing action restrictions

**Severity**: High

---

### PERSONA-003: Capability Claim

**Definition**: Agent claims abilities it doesn't have.

**Detection Tier**: 4 (Semantic analysis)

**Indicators**:
- Claims unavailable tools
- Promises impossible actions
- Overstates abilities

**Example**:
```
Agent: "I'll send an email to confirm that booking."
Reality: Agent has no email tool.
```

**Common Causes**:
- Hallucination
- Training data influence
- Missing capability grounding

**Severity**: High

---

### PERSONA-004: Persona Collapse

**Definition**: Agent completely abandons its defined persona.

**Detection Tier**: 3-4 (Major drift detection)

**Indicators**:
- Ignores system prompt entirely
- Responds as "base" model
- No persona markers in output

**Example**:
```
System: "You are Chef Pierre, a French cooking expert."
Agent: "As an AI language model, I can help with that."
```

**Common Causes**:
- Conflicting instructions
- Safety guardrail triggered
- Extreme context pressure

**Severity**: Critical

---

### PERSONA-005: Cross-Contamination

**Definition**: Agent adopts characteristics of another agent in the system.

**Detection Tier**: 3-4 (Cross-agent analysis)

**Indicators**:
- Uses another agent's vocabulary
- Performs another agent's role
- References another agent's context

**Example**:
```
Agent A (Research): "I'll analyze that data."
Agent B (Writer): "I'll analyze that data and write a research paper."
```

**Common Causes**:
- Shared context contamination
- Handoff residue
- Prompt leakage

**Severity**: High

---

## COORDINATION Failures

Failures in multi-agent interaction and orchestration.

### COORD-001: Handoff Failure

**Definition**: Transfer of control between agents fails.

**Detection Tier**: 2 (Event sequence)

**Indicators**:
- Handoff initiated but not received
- Acknowledgment missing
- Work duplicated or dropped

**Severity**: High

---

### COORD-002: Message Loss

**Definition**: Communication between agents is lost.

**Detection Tier**: 2 (Message correlation)

**Indicators**:
- Send without corresponding receive
- Agent proceeds without expected input
- Gap in conversation flow

**Severity**: Critical

---

### COORD-003: Deadlock

**Definition**: Multiple agents waiting on each other indefinitely.

**Detection Tier**: 2-4 (Dependency analysis)

**Indicators**:
- Circular wait pattern
- No progress for extended time
- Mutual blocking detected

**Severity**: Critical

---

### COORD-004: Priority Inversion

**Definition**: Lower-priority work blocks higher-priority work.

**Detection Tier**: 4 (Priority analysis)

**Indicators**:
- High-priority task waiting
- Low-priority task holding resource
- Unexpected ordering

**Severity**: Medium

---

### COORD-005: Cascade Failure

**Definition**: One agent's failure causes others to fail.

**Detection Tier**: 2-4 (Dependency + timing)

**Indicators**:
- Sequential failures
- Common dependency
- Failure propagation pattern

**Severity**: Critical

---

### COORD-006: Coordination Overhead

**Definition**: Excessive communication between agents.

**Detection Tier**: 2 (Message counting)

**Indicators**:
- High message-to-action ratio
- Redundant coordination
- Chattiness without progress

**Severity**: Medium

---

## RESOURCE Failures

Failures related to computational resources and limits.

### RESOURCE-001: Token Explosion

**Definition**: Excessive token usage beyond reasonable bounds.

**Detection Tier**: 1-2 (Metric tracking)

**Indicators**:
- Token count >> expected
- Repeated large outputs
- Context filled rapidly

**Severity**: High

---

### RESOURCE-002: Timeout

**Definition**: Operation exceeds time limit.

**Detection Tier**: 1 (Timer)

**Indicators**:
- Span duration > limit
- Incomplete operation
- Timeout error in logs

**Severity**: Medium

---

### RESOURCE-003: Rate Limit

**Definition**: API rate limit exceeded.

**Detection Tier**: 1 (Error detection)

**Indicators**:
- 429 errors
- Retry patterns
- Backoff visible

**Severity**: Medium

---

### RESOURCE-004: Cost Overrun

**Definition**: Execution cost exceeds budget.

**Detection Tier**: 1-2 (Cost tracking)

**Indicators**:
- Cumulative cost > budget
- Expensive operations repeated
- No cost optimization

**Severity**: High

---

### RESOURCE-005: Memory Exhaustion

**Definition**: Context window fully consumed.

**Detection Tier**: 1-2 (Token tracking)

**Indicators**:
- Context near/at limit
- Truncation visible
- Lost information

**Severity**: Critical

---

## Severity Matrix

| Severity | Response Time | Impact | Examples |
|----------|---------------|--------|----------|
| Low | Best effort | Cosmetic | Formatting issues |
| Medium | 24 hours | Quality | Minor loops, delays |
| High | 4 hours | Reliability | Role confusion, regression |
| Critical | Immediate | Availability | Deadlock, data loss |
