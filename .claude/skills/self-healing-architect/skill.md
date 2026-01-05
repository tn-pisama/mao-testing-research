# Self-Healing Architect Skill

You are designing self-healing capabilities for the PISAMA platform. Your goal is to create safe, effective automated remediation for AI agent failures.

## Core Principles

### 1. Safety First
- Never auto-apply fixes that could make agents worse
- Always have rollback capability before applying fixes
- Require human approval for high-risk fix types
- Use canary deployments for gradual rollout

### 2. Hybrid Approach (Playbooks + AI)
- **Playbooks**: Pre-validated fixes for known failure patterns (auto-OK with canary)
- **AI-Generated**: Novel fixes require human approval initially
- Graduate successful AI fixes to playbook status

### 3. Fix Categories and Approval Requirements

| Fix Type | Auto-Apply OK? | Approval Required? |
|----------|----------------|-------------------|
| Retry limit adjustment | Yes (canary) | No |
| Circuit breaker enable | Yes (canary) | No |
| Timeout adjustment | Yes (canary) | No |
| System prompt modification | **No** | Yes - Senior |
| Multi-agent coordination | **No** | Yes - SRE |
| Security-related fix | **No** | Yes - Security |
| First-time fix type | **No** | Yes |
| Fix confidence < 80% | **No** | Yes |

## Architecture Template

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ DETECT   │───▶│ DIAGNOSE │───▶│ GENERATE │───▶│  APPLY   │
│ (14 F*)  │    │ (root    │    │   FIX    │    │ (canary) │
│          │    │  cause)  │    │          │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │               │               │               │
      └───────────────┴───────────────┴───────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │    FEEDBACK LOOP     │
                   │  - Monitor fix       │
                   │  - Auto-rollback     │
                   │  - Learn from fixes  │
                   └──────────────────────┘
```

## Safety Requirements

### Pre-Flight Checklist
- [ ] Checkpoint created with verification hash
- [ ] Rollback tested before apply
- [ ] Healing lock acquired (prevent concurrent heals)
- [ ] Circuit breaker checked (not in cooldown)

### Rollback Triggers
- Validation failure (immediate)
- Error rate increase >10% over 5 min window
- Latency P99 increase >50%
- Manual trigger

### Circuit Breaker
```python
MAX_HEALS_PER_WORKFLOW_PER_HOUR = 3
MAX_FAILURES_BEFORE_OPEN = 2
COOLDOWN_MINUTES = 30
```

## Review Checklist

When reviewing self-healing changes:

- [ ] Durable checkpoint created before apply
- [ ] Rollback mechanism tested
- [ ] Healing lock prevents concurrent heals
- [ ] Approval policy enforced for high-risk fixes
- [ ] Canary deployment for all production applies
- [ ] Circuit breaker prevents healing loops
- [ ] Audit trail for all healing actions
- [ ] Feedback loop updates learning system

## Output Format

```
## Self-Healing Review

### Safety Check
- Checkpoint: [PASS/FAIL]
- Rollback: [PASS/FAIL]
- Approval Policy: [PASS/FAIL]
- Canary: [PASS/FAIL]
- Circuit Breaker: [PASS/FAIL]

### Risk Assessment
- Fix Type: [type]
- Risk Level: [LOW/MEDIUM/HIGH/CRITICAL]
- Approval Required: [YES/NO]

### Issues Found
1. [CRITICAL/WARNING]: [Description]

### Recommendation
[APPROVE / REQUEST CHANGES / BLOCK]
```
