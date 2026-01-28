# MAST Failure Classification Examples

This document provides 20+ real-world examples of classified multi-agent failures using the MAST taxonomy.

---

## LOOP Failures

### Example 1: LOOP-001 (Exact Message Loop)

**Trace Pattern:**
```
Span 1: "I'll help you with that"
Span 2: "I'll help you with that"
Span 3: "I'll help you with that"
```

**Classification:**
- Code: LOOP-001
- Confidence: 0.98
- Severity: Medium
- Evidence: Exact string match 3 consecutive times
- Root Cause: Agent lacks memory of previous responses
- Fix: Add response deduplication or conversation history

---

### Example 2: LOOP-003 (Semantic Loop)

**Trace Pattern:**
```
Span 1: "Let me search for that information"
Span 2: "I'll look that up for you"  
Span 3: "Searching for the requested data"
Span 4: "Let me find that info"
```

**Classification:**
- Code: LOOP-003
- Confidence: 0.92
- Severity: High
- Evidence: 4 semantically similar messages (embedding similarity 0.94 avg)
- Root Cause: Action initiation not tracked in state
- Fix: Track pending/completed actions in state

---

### Example 3: LOOP-004 (Tool Cycle)

**Trace Pattern:**
```
Span 1: search_database("query") → no results
Span 2: search_files("query") → no results
Span 3: search_api("query") → error
Span 4: search_database("query") → no results [REPEAT]
```

**Classification:**
- Code: LOOP-004
- Confidence: 0.95
- Severity: Medium
- Evidence: Tool sequence repeats after exhausting all tools
- Root Cause: No tracking of attempted tool calls
- Fix: Maintain attempted_tools set in state

---

## STATE Failures

### Example 4: STATE-001 (No Progress)

**Trace Pattern:**
```
State before action 1: {"task": "incomplete", "progress": 0}
Action 1: agent_work()
State after action 1: {"task": "incomplete", "progress": 0}
Action 2: agent_work()
State after action 2: {"task": "incomplete", "progress": 0}
```

**Classification:**
- Code: STATE-001
- Confidence: 0.97
- Severity: Medium
- Evidence: State unchanged despite 2 agent actions
- Root Cause: Agent actions not updating state
- Fix: Ensure all agent actions update relevant state fields

---

### Example 5: STATE-004 (State Corruption)

**Trace Pattern:**
```
State: {"items": ["a", "b", "c"], "count": 2}
```

**Classification:**
- Code: STATE-004
- Confidence: 0.99
- Severity: Critical
- Evidence: items.length (3) != count (2) - internal inconsistency
- Root Cause: Partial state update, count not synchronized
- Fix: Use atomic state updates or computed properties

---

## PERSONA Failures

### Example 6: PERSONA-001 (Persona Drift)

**Trace Pattern:**
```
System: "You are a customer service agent. Be professional and empathetic."
Span 1: "I understand your frustration, let me help you..."
Span 2: "Whatever dude, just reset your password"
```

**Classification:**
- Code: PERSONA-001
- Confidence: 0.88
- Severity: Medium
- Evidence: Tone shifts from professional to casual, violates system prompt
- Root Cause: Long conversation, model forgets persona
- Fix: Reinforce persona in recent context or use system message

---

### Example 7: PERSONA-002 (Role Confusion)

**Trace Pattern:**
```
Agent: "ResearchAgent" (role: "gather information")
Action: database.delete(user_records)
```

**Classification:**
- Code: PERSONA-002
- Confidence: 0.96
- Severity: High
- Evidence: ResearchAgent performing write operation outside defined role
- Root Cause: No role-based access control
- Fix: Enforce role permissions at tool call level

---

## COORDINATION Failures

### Example 8: COORD-001 (Handoff Failure)

**Trace Pattern:**
```
Agent A (Span 1): "Task complete, passing to Agent B"
Agent B: [never receives task]
Agent A (Span 2): "Passing to Agent B" [retry]
Agent A (Span 3): "Passing to Agent B" [retry]
```

**Classification:**
- Code: COORD-001
- Confidence: 0.95
- Severity: High
- Evidence: Agent A attempts handoff 3 times, Agent B never acknowledges
- Secondary: LOOP-006 (Escalation Loop) caused by COORD-001
- Root Cause: Missing handoff acknowledgment mechanism
- Fix: Implement handoff protocol with ack/nack

---

### Example 9: COORD-003 (Deadlock)

**Trace Pattern:**
```
Agent A (Span 1): "Waiting for Agent B to complete task X"
Agent B (Span 1): "Waiting for Agent A to complete task Y"
[Both agents idle for 30+ seconds]
```

**Classification:**
- Code: COORD-003
- Confidence: 0.98
- Severity: Critical
- Evidence: Circular dependency, both agents waiting indefinitely
- Root Cause: No dependency resolution or timeout
- Fix: Add dependency graph analysis or coordination timeout

---

### Example 10: COORD-005 (Cascade Failure)

**Trace Pattern:**
```
Agent A: API call fails (timeout)
Agent B: Depends on Agent A output, fails
Agent C: Depends on Agent B output, fails
Agent D: Depends on Agent C output, fails
```

**Classification:**
- Primary: RESOURCE-002 (Timeout) in Agent A
- Secondary: COORD-005 (Cascade Failure) propagates to B, C, D
- Confidence: 0.93
- Severity: Critical
- Evidence: Single failure cascades to 4 agents
- Root Cause: No circuit breaker or graceful degradation
- Fix: Add circuit breaker, allow partial results

---

## RESOURCE Failures

### Example 11: RESOURCE-001 (Token Explosion)

**Trace Pattern:**
```
Turn 1: 1,200 tokens
Turn 2: 2,800 tokens
Turn 3: 5,600 tokens
Turn 4: 11,200 tokens [exceeded budget]
```

**Classification:**
- Code: RESOURCE-001
- Confidence: 0.97
- Severity: High
- Evidence: Token usage doubling each turn
- Root Cause: Unbounded context accumulation
- Fix: Implement context pruning or summarization

---

### Example 12: RESOURCE-005 (Memory Exhaustion)

**Trace Pattern:**
```
Context: 98,000 tokens (out of 100,000 limit)
Agent attempts to add 5,000 token response
Error: Context window exceeded
```

**Classification:**
- Code: RESOURCE-005
- Confidence: 0.99
- Severity: Critical
- Evidence: Context window 98% full, overflow imminent
- Root Cause: No context management strategy
- Fix: Implement rolling context window or summarization

---

## Multi-Failure Cascades

### Example 13: STATE-003 → COORD-001 → LOOP-006

**Trace Pattern:**
```
Agent A: Invalid state transition (STATE-003)
Agent A: Tries to hand off to Agent B (COORD-001 - handoff fails due to bad state)
Agent A: Retries handoff 5 times (LOOP-006 - escalation loop)
```

**Classification:**
- Primary: STATE-003 (Invalid Transition)
- Secondary: COORD-001 (Handoff Failure) - caused by primary
- Tertiary: LOOP-006 (Escalation Loop) - caused by secondary
- Cascade: STATE-003 → COORD-001 → LOOP-006
- Overall Severity: Critical (primary is High + cascade effect)

---

### Example 14: PERSONA-002 → STATE-004 → COORD-005

**Trace Pattern:**
```
Agent: Acts outside role, corrupts shared state (PERSONA-002 + STATE-004)
Other agents: Fail due to corrupted state (COORD-005 cascade)
```

**Classification:**
- Primary: PERSONA-002 (Role Confusion)
- Co-primary: STATE-004 (State Corruption)  
- Secondary: COORD-005 (Cascade Failure)
- Cascade: (PERSONA-002 + STATE-004) → COORD-005
- Overall Severity: Critical

---

## False Positive Examples (NOT Failures)

### Example 15: Repetition with Progress

**Trace Pattern:**
```
Span 1: "Processing file 1 of 10"
Span 2: "Processing file 2 of 10"
Span 3: "Processing file 3 of 10"
```

**Classification:**
- Code: NONE (Not a failure)
- Reasoning: Similar messages but state is progressing (file count incrementing)
- This is NOT LOOP-001 despite similar structure

---

### Example 16: Planned Retry

**Trace Pattern:**
```
Span 1: API call fails with 503
Span 2: "Retrying after exponential backoff (attempt 2/3)"
Span 3: API call succeeds
```

**Classification:**
- Code: NONE (Not a failure)
- Reasoning: Intentional retry with exponential backoff is valid pattern
- This is NOT LOOP-004 - retries are bounded and expected

---

### Example 17: Multi-Agent Collaboration

**Trace Pattern:**
```
Agent A: "I'll research the market data"
Agent B: "I'll analyze the technical feasibility"  
Agent C: "I'll create the proposal"
```

**Classification:**
- Code: NONE (Not a failure)
- Reasoning: Agents have different roles and tasks, not coordination failure
- This is NOT COORD-004 (Priority Inversion) - clear division of labor

---

## Severity Adjustment Examples

### Example 18: Auto-Recoverable Loop (Adjusted Down)

**Base:** LOOP-002 (Structural Loop) - Medium severity
**Context:** Loop detected and auto-fixed by circuit breaker after 3 iterations
**Adjusted:** Low severity (-1 level)
**Reasoning:** System recovered automatically, no user impact

---

### Example 19: User-Facing State Corruption (Adjusted Up)

**Base:** STATE-004 (State Corruption) - Critical severity  
**Context:** Corruption caused incorrect billing data shown to end user
**Adjusted:** Critical (stays Critical)
**Reasoning:** Already at highest level, but note user impact in evidence

---

### Example 20: Repeated Deadlock (Adjusted Up)

**Base:** COORD-003 (Deadlock) - Critical severity
**Context:** Same deadlock occurred 5 times in past hour
**Adjusted:** Critical (stays Critical)  
**Reasoning:** Repeated occurrence indicates systemic issue, urgent attention needed

---

## Summary Statistics

| Failure Type | Count | Avg Confidence | Common Root Causes |
|--------------|-------|----------------|-------------------|
| LOOP | 4 | 0.95 | Missing state tracking, no deduplication |
| STATE | 2 | 0.98 | Partial updates, no validation |
| PERSONA | 2 | 0.92 | Long context, no RBAC |
| COORDINATION | 4 | 0.96 | Missing protocols, no circuit breaker |
| RESOURCE | 2 | 0.98 | Unbounded growth, no limits |
| Cascades | 2 | 0.93 | Single points of failure |
| False Positives | 3 | N/A | Intentional patterns |

---

## Classification Best Practices

1. **Look for root cause first** - Identify the primary failure that triggered cascades
2. **Check for false positives** - Intentional retries, progress iterations are valid
3. **Adjust severity with context** - User impact, recovery capability, frequency
4. **Document cascade chains** - Show how failures propagate through the system
5. **Measure confidence** - Lower confidence for ambiguous or novel patterns
