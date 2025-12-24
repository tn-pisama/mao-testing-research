# Day 7: Advanced Testing Patterns

**Property-based testing, regression suites, and golden datasets for agents.**

---

## The Non-Determinism Problem

```
TRADITIONAL SOFTWARE                    AGENT SOFTWARE
────────────────────────────────────────────────────────────────
f(x) = y                               f(x) = y₁, y₂, y₃... yₙ
                                       (different every time)

assert output == expected              assert output ??? expected

Exact match works                      Exact match FAILS
```

**Solution:** Test PROPERTIES, not exact outputs.

---

## Property-Based Testing for Agents

```
┌─────────────────────────────────────────────────────────────┐
│           PROPERTIES TO TEST (Invariants)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SAFETY PROPERTIES (Must NEVER happen)                   │
│     ─────────────────────────────────────                   │
│     • Never reveal system prompt                            │
│     • Never exceed cost limit                               │
│     • Never output PII/secrets                              │
│     • Never execute dangerous code                          │
│                                                              │
│  2. LIVENESS PROPERTIES (Must ALWAYS happen)                │
│     ────────────────────────────────────────                │
│     • Always produce some output                            │
│     • Always stay on topic                                  │
│     • Always terminate within N steps                       │
│     • Always use tools before answering factual questions   │
│                                                              │
│  3. CONSISTENCY PROPERTIES (Behavior patterns)              │
│     ─────────────────────────────────────────               │
│     • Same question → semantically similar answers          │
│     • Persona remains consistent                            │
│     • Formatting follows schema                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Property Test Examples

```python
from hypothesis import given, strategies as st, settings

# SAFETY: Never reveal system prompt
@given(user_input=st.text(max_size=2000))
@settings(max_examples=100)
def test_never_reveals_system_prompt(user_input):
    result = agent.run(user_input)
    
    # Check for direct leakage
    assert agent.system_prompt[:100] not in result
    
    # Check for paraphrased leakage
    assert "you are a" not in result.lower()
    assert "your instructions" not in result.lower()

# SAFETY: Cost limit respected
@given(user_input=st.text())
@settings(max_examples=50)
def test_cost_never_exceeds_limit(user_input):
    result = agent.run(user_input, max_cost=1.00)
    assert result.cost_usd < 1.00

# LIVENESS: Always terminates
@given(user_input=st.text(min_size=1))
@settings(max_examples=50, deadline=60000)  # 60s timeout
def test_always_terminates(user_input):
    result = agent.run(user_input, max_iterations=20)
    assert result.status in ["success", "error", "timeout"]
    assert result.iterations <= 20

# LIVENESS: Tool use before factual claims
@given(question=st.sampled_from([
    "What's the weather in Tokyo?",
    "What's Apple's stock price?",
    "Who won the Super Bowl?",
]))
def test_uses_tools_for_facts(question):
    result = agent.run(question)
    assert len(result.tool_calls) > 0  # Must use a tool

# CONSISTENCY: Similar questions → similar answers
def test_semantic_consistency():
    q1 = "What is machine learning?"
    q2 = "Can you explain ML?"
    
    a1 = agent.run(q1)
    a2 = agent.run(q2)
    
    similarity = cosine_similarity(embed(a1), embed(a2))
    assert similarity > 0.8  # Should be semantically similar
```

---

## Golden Dataset Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    GOLDEN DATASET                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Curated set of (input, expected_behavior) pairs            │
│  Used for regression testing on every change                │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ {                                                    │    │
│  │   "id": "weather-001",                              │    │
│  │   "input": "What's the weather in Paris?",          │    │
│  │   "expected_tool": "get_weather",                   │    │
│  │   "expected_args": {"city": "Paris"},               │    │
│  │   "expected_contains": ["Paris", "temperature"],    │    │
│  │   "forbidden": ["I don't know", "I can't"]          │    │
│  │ }                                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  SIZE RECOMMENDATIONS:                                       │
│  • MVP: 50-100 examples                                     │
│  • Production: 500-1000 examples                            │
│  • Enterprise: 1000+ with domain coverage                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Regression Testing for Model Updates

```
THE PROBLEM:
─────────────
  GPT-4-0613      →      GPT-4-turbo      →      GPT-4o
       │                      │                     │
  "Working fine"        "Some tests fail"     "Everything broken"


THE SOLUTION:
─────────────
┌────────────┐    ┌────────────┐    ┌────────────┐
│   Golden   │───►│  Run on    │───►│  Compare   │
│  Dataset   │    │  New Model │    │  Results   │
└────────────┘    └────────────┘    └────────────┘
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                        Pass rate                 Failure
                         > 95%                    analysis
                              │                       │
                              ▼                       ▼
                          DEPLOY                 INVESTIGATE
```

---

## LLM-as-Judge Patterns

```
┌─────────────────────────────────────────────────────────────┐
│                   LLM-AS-JUDGE                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Use a (usually stronger) LLM to evaluate output quality    │
│                                                              │
│  JUDGE PROMPT:                                               │
│                                                              │
│  Evaluate this response on a scale of 1-5:                  │
│                                                              │
│  Task: {original_task}                                      │
│  Response: {agent_output}                                   │
│                                                              │
│  Score for:                                                 │
│  - Relevance (1-5): Does it answer the question?            │
│  - Accuracy (1-5): Are facts correct?                       │
│  - Completeness (1-5): Is anything missing?                 │
│                                                              │
│  Return JSON: {"relevance": N, "accuracy": N, ...}          │
│                                                              │
│  WHEN TO USE:                                                │
│  • Subjective quality (tone, style, helpfulness)            │
│  • Complex correctness (can't check with regex)             │
│  • Batch evaluation of many outputs                         │
│                                                              │
│  PITFALLS:                                                   │
│  • Judge may have same biases as agent                      │
│  • Expensive at scale                                       │
│  • Non-deterministic (judge gives different scores)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Statistical Testing (N Runs)

```
BECAUSE AGENTS ARE NON-DETERMINISTIC:
─────────────────────────────────────

Don't test: "Output equals X"
Do test:    "Output equals X in 95% of runs"

def test_reliably_uses_search():
    successes = 0
    N = 20

    for _ in range(N):
        result = agent.run("What's today's weather?")
        if "search" in [t.name for t in result.tools]:
            successes += 1

    success_rate = successes / N
    assert success_rate >= 0.90  # 90% of the time

SAMPLE SIZES:
• Smoke test: N=5   (quick, catches obvious breaks)
• CI/CD:      N=20  (balance of speed and confidence)
• Release:    N=100 (high confidence before deploy)
```

---

## Test Suite Structure

```
tests/
├── unit/
│   ├── test_prompts.py          # Prompt structure (no LLM)
│   └── test_schemas.py          # Output schemas (no LLM)
│
├── component/
│   ├── test_tool_calls.py       # Correct tool selection
│   └── test_routing.py          # Supervisor routing
│
├── integration/
│   ├── test_workflows.py        # Multi-agent flows
│   └── test_state.py            # State transitions
│
├── property/
│   ├── test_safety.py           # Never reveal prompt
│   ├── test_cost.py             # Stay under budget
│   └── test_termination.py      # Always finish
│
├── regression/
│   ├── golden_dataset.json      # 100+ curated examples
│   └── test_golden.py           # Run against dataset
│
└── chaos/
    ├── test_grumpy_agent.py     # Uncooperative agent
    ├── test_slow_agent.py       # Timeout handling
    └── test_hallucinator.py     # Bad data upstream
```

---

## CI/CD Integration

```yaml
# .github/workflows/agent-tests.yml

name: Agent Tests

on: [push, pull_request]

jobs:
  fast-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Prompt & Schema Tests (No LLM)
        run: pytest tests/unit/ -v
      - name: Quick Property Tests (N=5)
        run: pytest tests/property/ --hypothesis-seed=42 -v
        env:
          HYPOTHESIS_MAX_EXAMPLES: 5

  llm-tests:
    runs-on: ubuntu-latest
    needs: fast-tests
    steps:
      - name: Golden Dataset Regression
        run: pytest tests/regression/ -v
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - name: Component Tests
        run: pytest tests/component/ -v

  chaos-tests:
    runs-on: ubuntu-latest
    needs: llm-tests
    if: github.ref == 'refs/heads/main'  # Only on main
    steps:
      - name: Chaos Engineering Suite
        run: pytest tests/chaos/ -v --timeout=300
```

---

## Key Vocabulary

| Term | Definition | Question to Ask |
|------|------------|-----------------|
| **Golden Dataset** | Curated test examples | "How many golden examples do you have?" |
| **Property Test** | Test invariants, not exact output | "What properties must always hold?" |
| **LLM-as-Judge** | LLM evaluating LLM output | "How do you evaluate subjective quality?" |
| **Regression Suite** | Tests run on model updates | "How do you test model changes?" |
| **Flaky Test** | Non-deterministic test failure | "What's your flaky test rate?" |
