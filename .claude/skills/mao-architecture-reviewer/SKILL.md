---
name: mao-architecture-reviewer
description: |
  Reviews MAO codebase changes for architectural consistency.
  Use when modifying detection algorithms, SDK interfaces, backend services, or database schemas.
  Ensures OTEL compatibility, tiered detection patterns, cost-awareness, and framework-agnostic design.
  Automatically invoked when reviewing PRs, refactoring core components, or adding new features.
allowed-tools: Read, Grep, Glob
---

# MAO Architecture Review Skill

You are reviewing changes to the MAO Testing Platform codebase. Your job is to ensure architectural consistency and catch violations before they reach production.

## Core Architectural Principles

### 1. OTEL-First Design
All trace data MUST be OpenTelemetry compatible:
- Use standard OTEL span attributes (`service.name`, `span.kind`, etc.)
- Custom attributes MUST be prefixed with `mao.`
- Trace context propagation MUST follow W3C Trace Context spec
- Never invent proprietary trace formats

### 2. Tiered Detection Architecture
Detection algorithms MUST follow the cost tier hierarchy:

| Tier | Method | Cost | Latency | Use When |
|------|--------|------|---------|----------|
| 1 | Structural hash | $0 | <1ms | Exact pattern match possible |
| 2 | State delta analysis | $0 | <5ms | Sequential state changes |
| 3 | Local embeddings | $0 | <50ms | Semantic similarity needed |
| 4 | LLM Judge | $0.50 | <2s | Ambiguous cases only |
| 5 | Human review | $50 | <24h | Critical/novel failures |

**Rule**: Always start at Tier 1. Only escalate if lower tiers cannot solve the problem.

### 3. Cost-Aware Design
Every detection path MUST track:
- Tokens consumed (if LLM involved)
- Compute time
- Estimated $ cost
- Escalation rate to higher tiers

### 4. Framework-Agnostic Core
The core detection engine MUST NOT contain:
- LangGraph-specific code
- CrewAI-specific code
- AutoGen-specific code
- Any framework imports

Framework-specific code belongs ONLY in `sdk/adapters/`.

## Review Checklist

When reviewing changes, verify:

### A. OTEL Compatibility
- [ ] New spans use standard OTEL attributes
- [ ] Custom attributes prefixed with `mao.`
- [ ] No proprietary trace formats introduced
- [ ] Trace context properly propagated

### B. Detection Tier Compliance
- [ ] Algorithm placed in correct tier
- [ ] Lower tier alternatives considered
- [ ] Escalation criteria documented
- [ ] False positive budget defined (<5%)

### C. Cost Tracking
- [ ] Cost metrics captured
- [ ] Token usage tracked (if applicable)
- [ ] Latency budgets respected
- [ ] No unbounded loops or recursion

### D. Framework Independence
- [ ] Core logic has no framework imports
- [ ] Adapter pattern used for framework-specific code
- [ ] Interface contracts maintained
- [ ] Tests don't depend on specific framework

### E. Database Schema
- [ ] Migrations are backward-compatible
- [ ] Indexes added for query patterns
- [ ] pgvector columns use appropriate dimensions
- [ ] No breaking changes to existing tables

### F. SDK Interface Stability
- [ ] Public API unchanged (or versioned)
- [ ] New methods have clear contracts
- [ ] Error handling is consistent
- [ ] Type hints complete

## Common Violations to Flag

### Critical (Block PR)
- Framework-specific code in `core/`
- Missing OTEL compatibility
- Unbounded LLM calls (no max tokens/retries)
- Breaking changes to SDK public API

### Warning (Request Justification)
- Tier 3+ detection without trying Tier 1-2 first
- Missing cost tracking
- New database columns without indexes
- Incomplete type hints

### Suggestion (Non-blocking)
- Opportunities to move to lower tier
- Missing docstrings
- Test coverage gaps
- Performance optimizations

## Output Format

Structure your review as:

```
## Architecture Review: [Component Name]

### Summary
[1-2 sentence overview]

### Compliance Check
- OTEL Compatibility: [PASS/FAIL/WARN]
- Detection Tier: [PASS/FAIL/WARN]
- Cost Tracking: [PASS/FAIL/WARN]
- Framework Independence: [PASS/FAIL/WARN]
- Database Schema: [PASS/FAIL/WARN] (if applicable)
- SDK Interface: [PASS/FAIL/WARN] (if applicable)

### Issues Found
1. [CRITICAL/WARNING/SUGGESTION]: [Description]
   - Location: [file:line]
   - Fix: [Recommended action]

### Recommendation
[APPROVE / REQUEST CHANGES / BLOCK]
```

## Resources

For detailed specifications, I can load:
- `resources/architecture.md` - Full system architecture
- `resources/otel-standards.md` - OTEL attribute specifications
- `resources/tiered-detection.md` - Detection tier implementation guide
- `resources/database-schema.md` - Current schema and migration rules
