# Testing Your Agents with MAO

Validate your AI agent's reliability before production using MAO's comprehensive testing framework.

## Quick Start

```bash
# Install MAO SDK
pip install mao-sdk

# Run detection on your agent
mao test --agent my_agent.py --input test_cases.json
```

## Test Types

### 1. Detection Accuracy Tests

Verify MAO correctly identifies issues in your agents:

```python
from mao_sdk import MAOTester

tester = MAOTester(endpoint="https://api.mao-testing.com")

# Test that loop detection works
result = tester.test_detection(
    agent_code="path/to/agent.py",
    expected_detection="infinite_loop",
    test_input={"query": "loop-inducing prompt"}
)

assert result.detection_triggered
assert result.detection_type == "infinite_loop"
```

### 2. Fix Validation Tests

Verify that suggested fixes actually resolve issues:

```python
# Test that a fix resolves the issue
validation = tester.validate_fix(
    original_code=agent_code,
    fix=suggested_fix,
    test_input={"query": "same loop-inducing prompt"}
)

assert validation.issue_resolved
assert validation.no_regressions
```

### 3. Regression Tests

Ensure new agent versions don't introduce failures:

```python
# Compare two versions
comparison = tester.compare_versions(
    baseline="agent_v1.py",
    candidate="agent_v2.py",
    test_cases="golden_dataset.json"
)

assert comparison.no_new_failures
assert comparison.detection_rate >= baseline_detection_rate
```

## Integration with Frameworks

### LangChain

```python
from langchain.agents import AgentExecutor
from mao_sdk import MAOTracer

# Wrap your agent
tracer = MAOTracer()
executor = tracer.wrap(AgentExecutor(agent=my_agent, tools=tools))

# Run tests
result = await executor.ainvoke({"input": "test query"})

# Check for detections
detections = await tracer.get_detections(result.trace_id)
assert len(detections) == 0, f"Unexpected detections: {detections}"
```

### CrewAI

```python
from crewai import Crew
from mao_sdk import MAOTracer

tracer = MAOTracer()
crew = tracer.wrap(Crew(agents=agents, tasks=tasks))

result = crew.kickoff()
detections = await tracer.get_detections(result.trace_id)
```

### AutoGen

```python
from autogen import AssistantAgent
from mao_sdk import MAOTracer

tracer = MAOTracer()
assistant = tracer.wrap(AssistantAgent(name="assistant"))

# Your AutoGen workflow here
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Agent Tests

on: [push, pull_request]

jobs:
  mao-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install dependencies
        run: pip install mao-sdk pytest
      
      - name: Run detection tests
        env:
          MAO_API_KEY: ${{ secrets.MAO_API_KEY }}
        run: pytest tests/test_agent_reliability.py -v
      
      - name: Upload results
        uses: mao-testing/upload-results@v1
        with:
          results-file: test-results.json
```

### GitLab CI

```yaml
mao_tests:
  image: python:3.11
  script:
    - pip install mao-sdk pytest
    - pytest tests/test_agent_reliability.py
  artifacts:
    reports:
      junit: test-results.xml
```

## Test Dashboard

View test results at: **Dashboard → Testing**

The dashboard shows:
- **Detection Accuracy**: How well MAO catches issues
- **Fix Effectiveness**: Success rate of suggested fixes
- **Integration Status**: Per-framework test results
- **Recent Runs**: History of test executions

## Golden Dataset Testing

Test against MAO's curated dataset of known failure patterns:

```python
# Run against golden dataset
results = tester.run_golden_dataset(
    agent_code="my_agent.py",
    categories=["infinite_loop", "state_corruption"]
)

print(f"Detection Rate: {results.detection_rate:.1%}")
print(f"False Positive Rate: {results.false_positive_rate:.1%}")
```

### Dataset Categories

| Category | Description | Count |
|----------|-------------|-------|
| `infinite_loop` | Repetitive tool calls | 84 traces |
| `state_corruption` | Inconsistent state | 85 traces |
| `persona_drift` | Role deviation | 85 traces |
| `deadlock` | Circular waiting | 85 traces |
| `healthy` | Normal execution | 81 traces |

## Custom Test Cases

Create your own test cases:

```json
{
  "test_cases": [
    {
      "name": "should_detect_search_loop",
      "input": {"query": "find the meaning of life, keep searching"},
      "expected_detection": "infinite_loop",
      "timeout": 60
    },
    {
      "name": "should_complete_normally",
      "input": {"query": "what is 2 + 2"},
      "expected_detection": null,
      "timeout": 30
    }
  ]
}
```

## Metrics & Reporting

### Key Metrics

- **Detection Rate**: % of issues correctly identified
- **False Positive Rate**: % of false alarms
- **Fix Success Rate**: % of fixes that resolve issues
- **Regression Rate**: % of fixes that cause new issues

### Target Thresholds

| Metric | Target | Critical |
|--------|--------|----------|
| Detection Rate | ≥90% | <80% |
| False Positive Rate | ≤10% | >20% |
| Fix Success Rate | ≥85% | <70% |
| Regression Rate | ≤5% | >15% |

## Troubleshooting

### Tests Timing Out

```python
# Increase timeout for slow agents
result = tester.test_detection(
    agent_code="my_agent.py",
    test_input={"query": "complex task"},
    timeout=120  # 2 minutes
)
```

### Connection Errors

```python
# Use local testing mode
tester = MAOTester(
    endpoint="http://localhost:8000",  # Local MAO instance
    api_key="dev-key"
)
```

### Debugging Failed Tests

```python
# Get detailed trace for debugging
result = tester.test_detection(
    agent_code="my_agent.py",
    test_input={"query": "test"},
    verbose=True
)

# Print full execution trace
print(result.trace.to_json(indent=2))
```

## Best Practices

1. **Start with golden dataset** - Baseline your agent's reliability
2. **Add custom cases** - Cover your specific use cases
3. **Run in CI/CD** - Catch regressions early
4. **Monitor production** - Use same tests for production monitoring
5. **Review fix suggestions** - Validate before applying

## Next Steps

- [Reviewing Detections](./reviewing-detections.md) - Help improve detection accuracy
- [Understanding Fix Suggestions](./understanding-fix-suggestions.md) - Learn about fix types
- [Importing Historical Data](./importing-historical-data.md) - Test on production traces
