# Week 8: Testing Methodology - Complete Outline

**Duration:** 5 days (20-30 hours total)
**Prerequisites:** Weeks 1-7
**Outcome:** Complete agent testing expertise, production-ready test suites

---

## Day-by-Day Breakdown

### Day 36: Testing Philosophy for Non-Deterministic Systems
- Why traditional testing fails
- Statistical testing foundations
- Property-based testing theory
- Invariants vs exact outputs
- Test pyramid for agents
- Cost-aware test design
- **Reading:** "Testing Non-Deterministic Systems" literature

### Day 37: Property-Based Testing with Hypothesis
- Hypothesis library deep dive
- Strategy composition
- Stateful testing
- Shrinking and counterexamples
- Custom strategies for agents
- Integration with pytest
- **Exercise:** 20 property tests for agent

### Day 38: Golden Dataset Curation
- What makes a good golden example
- Coverage criteria
- Edge case identification
- Labeling methodology
- Dataset versioning
- Maintenance strategies
- **Deliverable:** 100-example golden dataset

### Day 39: LLM-as-Judge Patterns
- Judge prompt engineering
- Calibration techniques
- Multi-judge consensus
- Rubric design
- Bias detection
- Judge selection
- **Exercise:** Calibrated judge with 3 criteria

### Day 40: CI/CD Pipeline Design
- Fast vs slow tests separation
- Parallelization strategies
- Cost budgeting
- Failure alerting
- Regression detection
- Model update testing
- **Deliverable:** Complete CI/CD configuration

---

## Test Types Reference

```python
# LEVEL 1: Prompt Tests (No LLM, <1s, $0)
def test_prompt_has_guardrails():
    assert "NEVER" in agent.system_prompt

# LEVEL 2: Tool Call Tests (1 LLM call, ~2s, ~$0.01)
def test_uses_search_for_factual():
    result = agent("What's the weather?")
    assert result.tool_calls[0].name == "search"

# LEVEL 3: Semantic Tests (LLM-as-Judge, ~5s, ~$0.05)
def test_response_is_helpful():
    result = agent("Explain quantum computing")
    score = judge("Is this helpful? 1-5", result)
    assert score >= 4

# LEVEL 4: Statistical Tests (N runs, ~60s, ~$1)
@settings(max_examples=20)
@given(query=st.text())
def test_always_terminates(query):
    result = agent(query, timeout=30)
    assert result.status != "timeout"

# LEVEL 5: Chaos Tests (Fault injection, ~120s, ~$2)
def test_recovers_from_tool_failure():
    with inject_fault(search_tool, "timeout"):
        result = agent("Find information about X")
    assert result.status == "success"  # Used fallback
```

---

## Golden Dataset Schema

```json
{
  "id": "test-001",
  "category": "factual_query",
  "input": "What year was Python created?",
  "expected": {
    "should_use_tool": true,
    "tool_name": "search",
    "response_contains": ["1991", "Guido"],
    "response_not_contains": ["I don't know"],
    "max_tokens": 500,
    "max_cost": 0.05
  },
  "metadata": {
    "difficulty": "easy",
    "added_date": "2024-01-15",
    "last_verified": "2024-03-01"
  }
}
```

---

## Key Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Golden dataset pass rate | >95% | Weekly regression |
| Property test pass rate | 100% | Every PR |
| Flaky test rate | <5% | Monthly audit |
| Test cost per PR | <$5 | CI budget |
| Time to detect regression | <24h | Alerting SLA |
