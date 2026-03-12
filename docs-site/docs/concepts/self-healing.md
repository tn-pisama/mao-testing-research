# Self-Healing

PISAMA's self-healing pipeline automatically generates, validates, and applies fixes when failure modes are detected in agent workflows. The system is designed with safety-first principles: every fix requires a checkpoint, every applied fix can be rolled back.

## Pipeline Overview

```
Detection Result
       │
       ▼
┌──────────────────┐
│  1. Analyze      │  Identify failure root cause
│                  │  Determine fix category
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  2. Generate Fix │  AI-powered fix suggestion
│                  │  Code-level or config-level
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  3. Approval     │  Manual or automatic
│     Policy       │  Based on risk level
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  4. Apply &      │  Execute with checkpoint
│     Validate     │  Run validation checks
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  5. Rollback     │  If validation fails,
│     (if needed)  │  restore from checkpoint
└──────────────────┘
```

## Fix Categories

### Basic Fix Suggestions (All Plans)

Text-based suggestions that describe what to change:

- **Loop breaking**: "Consider adding a maximum iteration count or convergence check"
- **Injection defense**: "Add input sanitization before passing to LLM"
- **Overflow prevention**: "Implement conversation summarization when context exceeds 70%"

### Code-Level Fixes (Startup+)

Specific code changes with copy-paste solutions:

```python
# Example: Loop detection fix suggestion
# Add to your agent's step function:
if iteration_count > MAX_ITERATIONS:
    return {"status": "terminated", "reason": "max_iterations_exceeded"}
```

### AI-Generated Runbooks (Growth+)

Operational documentation generated from detection patterns:

- Step-by-step remediation procedures
- Monitoring queries to verify the fix
- Prevention guidelines for the team

### Self-Healing Playbooks (Growth+)

Pre-configured automated fix sequences:

| Playbook | Trigger | Action |
|---|---|---|
| Loop breaker | Loop detected with confidence > 0.85 | Inject termination condition |
| Context compressor | Overflow at WARNING level | Summarize older context |
| Persona reset | Persona drift > threshold | Re-inject system prompt |
| Cost circuit breaker | Budget exceeded | Pause workflow, notify |

### AI-Generated Fixes (Enterprise)

Full automated fix generation using Claude:

- Analyzes the trace, detection, and codebase context
- Generates specific code patches
- Includes test cases for the fix
- Provides rollback instructions

## Approval Policies

Fixes are categorized by risk level, and each level has a different approval requirement:

| Risk Level | Examples | Policy |
|---|---|---|
| **Low** | Config changes, threshold adjustments | Auto-apply |
| **Medium** | Prompt modifications, retry logic | Require team lead approval |
| **High** | Code changes, workflow modifications | Require admin approval |
| **Critical** | Data pipeline changes, auth modifications | Require manual review + staging test |

## API Endpoints

### List healing operations

```bash
curl "http://localhost:8000/api/v1/tenants/$TENANT_ID/healing/operations" \
  -H "Authorization: Bearer $TOKEN"
```

### Get operation details

```bash
curl "http://localhost:8000/api/v1/tenants/$TENANT_ID/healing/operations/$OPERATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### Approve an operation

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/healing/operations/$OPERATION_ID/approve" \
  -H "Authorization: Bearer $TOKEN"
```

### Execute a healing operation

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/healing/operations/$OPERATION_ID/execute" \
  -H "Authorization: Bearer $TOKEN"
```

### Rollback a fix

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/healing/operations/$OPERATION_ID/rollback" \
  -H "Authorization: Bearer $TOKEN"
```

### View healing history

```bash
curl "http://localhost:8000/api/v1/tenants/$TENANT_ID/healing/history" \
  -H "Authorization: Bearer $TOKEN"
```

## Safety Guarantees

1. **Checkpoint before apply**: Every fix creates a state checkpoint before modifying anything
2. **Rollback capability**: Any applied fix can be rolled back to its checkpoint
3. **Validation after apply**: Fixes are validated immediately after application -- if validation fails, automatic rollback is triggered
4. **Audit trail**: Every healing operation is logged with timestamps, approvers, and outcomes
5. **Canary deployment**: Enterprise tier supports canary-style fix application -- apply to a subset, verify, then roll out

## Availability by Plan

| Capability | Free | Startup | Growth | Enterprise |
|---|---|---|---|---|
| Basic fix suggestions | Yes | Yes | Yes | Yes |
| Code-level fixes | -- | Yes | Yes | Yes |
| Fix confidence scores | -- | Yes | Yes | Yes |
| AI-generated runbooks | -- | -- | Yes | Yes |
| Playbook fixes | -- | -- | Yes | Yes |
| AI-generated fixes | -- | -- | -- | Yes |
| Auto-apply (canary) | -- | -- | -- | Yes |
