# End-to-End Testing Strategy for MAO

## Overview

Testing MAO requires validating the entire pipeline with **real data**, **real framework integrations**, and **real fix suggestions**. No mocks for critical paths.

## Testing Pyramid for MAO

```
                    ┌─────────────────────┐
                    │   Production        │  Real traffic, real failures
                    │   Monitoring        │  Continuous validation
                    ├─────────────────────┤
                    │   E2E Integration   │  Real frameworks, real APIs
                    │   Tests             │  LangChain, CrewAI, AutoGen
                    ├─────────────────────┤
                    │   Detection         │  Golden dataset validation
                    │   Accuracy Tests    │  Known failure patterns
                    ├─────────────────────┤
                    │   Fix Suggestion    │  Suggestions actually work
                    │   Validation        │  Before/after comparison
                    ├─────────────────────┤
                    │   Unit Tests        │  Fast, isolated, mocked
                    └─────────────────────┘
```

## 1. Real Data Testing

### 1.1 Golden Dataset (Already Implemented)

We have 420 golden traces in `/backend/fixtures/golden/golden_traces.jsonl`:
- 84 infinite_loop traces
- 85 state_corruption traces  
- 85 persona_drift traces
- 85 deadlock traces
- 81 healthy traces

**Validation Script:**
```python
# backend/scripts/validate_detections.py
import json
from app.detection import DetectionEngine

def validate_golden_dataset():
    """Validate detection accuracy against golden dataset."""
    results = {
        'infinite_loop': {'tp': 0, 'fp': 0, 'fn': 0},
        'state_corruption': {'tp': 0, 'fp': 0, 'fn': 0},
        'persona_drift': {'tp': 0, 'fp': 0, 'fn': 0},
        'deadlock': {'tp': 0, 'fp': 0, 'fn': 0},
    }
    
    with open('fixtures/golden/golden_traces.jsonl') as f:
        for line in f:
            trace = json.loads(line)
            expected = trace['metadata']['failure_type']
            detected = detection_engine.analyze(trace)
            
            if expected == 'healthy':
                for det_type in detected:
                    results[det_type]['fp'] += 1
            elif expected in detected:
                results[expected]['tp'] += 1
            else:
                results[expected]['fn'] += 1
    
    for detection_type, counts in results.items():
        precision = counts['tp'] / (counts['tp'] + counts['fp'])
        recall = counts['tp'] / (counts['tp'] + counts['fn'])
        f1 = 2 * precision * recall / (precision + recall)
        print(f"{detection_type}: P={precision:.2%} R={recall:.2%} F1={f1:.2%}")
```

**Target Metrics:**
| Detection Type | Precision | Recall | F1 Score |
|----------------|-----------|--------|----------|
| Infinite Loop | ≥95% | ≥95% | ≥95% |
| State Corruption | ≥90% | ≥85% | ≥87% |
| Persona Drift | ≥85% | ≥80% | ≥82% |
| Deadlock | ≥90% | ≥90% | ≥90% |

### 1.2 Production Data Replay

Import real traces from production systems:

```python
# backend/scripts/replay_production_traces.py
async def replay_production_traces(source: str):
    """
    Replay real production traces through detection pipeline.
    Sources: langsmith, langfuse, otlp, custom
    """
    parser = get_parser(source)
    
    for trace in parser.parse(file_content):
        # Run through detection
        detections = await detection_engine.analyze(trace)
        
        # Log for human review
        if detections:
            await create_review_task(trace, detections)
```

### 1.3 Continuous Data Collection

```yaml
# docker-compose.test.yml
services:
  trace-collector:
    image: mao/trace-collector
    environment:
      - SOURCES=langsmith,langfuse,arize
      - COLLECTION_INTERVAL=1h
      - ANONYMIZE=true
    volumes:
      - ./collected_traces:/data
```

## 2. Real Framework Integrations

### 2.1 Integration Test Matrix

| Framework | Version | Test Type | Real LLM | Recording |
|-----------|---------|-----------|----------|-----------|
| LangChain | 0.3.x | E2E | ✅ | VCR cassettes |
| LangGraph | 0.2.x | E2E | ✅ | VCR cassettes |
| CrewAI | 0.8.x | E2E | ✅ | VCR cassettes |
| AutoGen | 0.4.x | E2E | ✅ | VCR cassettes |
| OpenAI Agents | 1.x | E2E | ✅ | VCR cassettes |
| Semantic Kernel | 1.x | E2E | ✅ | VCR cassettes |

### 2.2 LangChain Integration Tests

```python
# backend/tests/integration/test_langchain_integration.py
import pytest
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import Tool
from mao_sdk import MAOTracer

@pytest.fixture
def mao_tracer():
    return MAOTracer(
        endpoint="http://localhost:8000",
        project="integration-tests"
    )

@pytest.fixture
def langchain_agent(mao_tracer):
    """Create a real LangChain agent with MAO instrumentation."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    tools = [
        Tool(name="search", func=real_search, description="Search the web"),
        Tool(name="calculator", func=real_calculator, description="Do math"),
    ]
    
    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    return mao_tracer.wrap(executor)

class TestLangChainInfiniteLoop:
    """Test infinite loop detection with real LangChain agent."""
    
    @pytest.mark.vcr()  # Record/replay HTTP calls
    async def test_detects_tool_loop(self, langchain_agent, mao_tracer):
        """Agent calling same tool repeatedly should trigger detection."""
        # This prompt is designed to cause a loop
        result = await langchain_agent.ainvoke({
            "input": "Keep searching until you find the exact answer to life"
        })
        
        # Wait for async detection
        await asyncio.sleep(2)
        
        # Verify detection
        detections = await mao_tracer.get_detections(trace_id=result.trace_id)
        assert any(d.type == "infinite_loop" for d in detections)
        
    @pytest.mark.vcr()
    async def test_healthy_agent_no_false_positive(self, langchain_agent, mao_tracer):
        """Normal agent execution should not trigger false positives."""
        result = await langchain_agent.ainvoke({
            "input": "What is 2 + 2?"
        })
        
        await asyncio.sleep(2)
        
        detections = await mao_tracer.get_detections(trace_id=result.trace_id)
        assert len(detections) == 0
```

### 2.3 CrewAI Integration Tests

```python
# backend/tests/integration/test_crewai_integration.py
from crewai import Agent, Task, Crew
from mao_sdk import MAOTracer

@pytest.fixture
def research_crew(mao_tracer):
    """Create a real CrewAI crew with MAO instrumentation."""
    researcher = Agent(
        role="Researcher",
        goal="Find accurate information",
        backstory="You are a thorough researcher",
        llm="gpt-4o-mini",
        verbose=True
    )
    
    writer = Agent(
        role="Writer", 
        goal="Write clear summaries",
        backstory="You are a concise writer",
        llm="gpt-4o-mini",
        verbose=True
    )
    
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        verbose=True
    )
    
    return mao_tracer.wrap(crew)

class TestCrewAIDeadlock:
    """Test deadlock detection with real CrewAI crew."""
    
    @pytest.mark.vcr()
    async def test_detects_circular_delegation(self, deadlock_crew, mao_tracer):
        """Agents delegating back and forth should trigger deadlock detection."""
        result = await deadlock_crew.kickoff()
        
        detections = await mao_tracer.get_detections(trace_id=result.trace_id)
        assert any(d.type == "deadlock" for d in detections)

class TestCrewAIPersonaDrift:
    """Test persona drift detection with real CrewAI agents."""
    
    @pytest.mark.vcr()
    async def test_detects_role_deviation(self, research_crew, mao_tracer):
        """Agent deviating from assigned role should trigger detection."""
        # Task that might cause researcher to start writing
        result = await research_crew.kickoff({
            "topic": "Write a poem about AI"  # Wrong task for researcher
        })
        
        detections = await mao_tracer.get_detections(trace_id=result.trace_id)
        assert any(d.type == "persona_drift" for d in detections)
```

### 2.4 VCR Recording Strategy

```python
# backend/tests/conftest.py
import pytest
from vcr import VCR

@pytest.fixture(scope="module")
def vcr_config():
    return {
        "cassette_library_dir": "tests/cassettes",
        "record_mode": "new_episodes",  # Record new, replay existing
        "match_on": ["method", "scheme", "host", "port", "path"],
        "filter_headers": ["authorization", "x-api-key"],
        "filter_post_data_parameters": ["api_key"],
        "before_record_response": scrub_response,
    }

def scrub_response(response):
    """Remove sensitive data from recorded responses."""
    # Scrub API keys, tokens, PII
    return response
```

**Cassette Management:**
```bash
# Record fresh cassettes (costs money, use sparingly)
MAO_RECORD_MODE=all pytest tests/integration/ -k langchain

# Replay existing cassettes (fast, free)
MAO_RECORD_MODE=none pytest tests/integration/

# Record only new tests
MAO_RECORD_MODE=new_episodes pytest tests/integration/
```

## 3. Real Fix Suggestion Validation

### 3.1 Fix Validation Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                   Fix Validation Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DETECT           2. SUGGEST         3. APPLY         4. VERIFY
│  ┌─────────┐        ┌─────────┐        ┌─────────┐      ┌─────────┐
│  │ Failing │───────▶│ Fix     │───────▶│ Modified│─────▶│ Passing │
│  │ Agent   │        │ Suggest │        │ Agent   │      │ Agent   │
│  └─────────┘        └─────────┘        └─────────┘      └─────────┘
│       │                  │                  │                │
│       ▼                  ▼                  ▼                ▼
│  Detection          Suggestion          Apply fix       Re-run test
│  triggered          generated           automatically   verify fixed
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Fix Suggestion Test Cases

```python
# backend/tests/integration/test_fix_suggestions.py

class TestInfiniteLoopFixes:
    """Validate infinite loop fix suggestions actually work."""
    
    @pytest.fixture
    def looping_agent_code(self):
        return '''
from langchain.agents import AgentExecutor

agent = AgentExecutor(
    agent=react_agent,
    tools=tools,
    verbose=True
)
'''
    
    @pytest.fixture
    def fixed_agent_code(self):
        return '''
from langchain.agents import AgentExecutor

agent = AgentExecutor(
    agent=react_agent,
    tools=tools,
    verbose=True,
    max_iterations=10,
    early_stopping_method="force"
)
'''
    
    async def test_max_iterations_fix_works(self, looping_agent_code, mao_client):
        """Verify that adding max_iterations prevents infinite loops."""
        
        # 1. Run agent without fix - should detect loop
        trace1 = await run_agent(looping_agent_code, loop_inducing_prompt)
        detections = await mao_client.get_detections(trace1.id)
        assert any(d.type == "infinite_loop" for d in detections)
        
        # 2. Get fix suggestion
        fix = detections[0].fix_suggestion
        assert "max_iterations" in fix.code_change
        
        # 3. Apply fix
        fixed_code = apply_fix(looping_agent_code, fix)
        
        # 4. Run agent with fix - should NOT detect loop
        trace2 = await run_agent(fixed_code, loop_inducing_prompt)
        detections2 = await mao_client.get_detections(trace2.id)
        assert not any(d.type == "infinite_loop" for d in detections2)


class TestStateCorruptionFixes:
    """Validate state corruption fix suggestions."""
    
    async def test_state_validation_fix_works(self):
        """Verify that adding state validation prevents corruption."""
        
        # Agent with corrupting state transitions
        corrupting_agent = create_state_corrupting_agent()
        trace1 = await run_agent(corrupting_agent)
        
        detections = await mao_client.get_detections(trace1.id)
        assert any(d.type == "state_corruption" for d in detections)
        
        # Apply suggested fix
        fix = detections[0].fix_suggestion
        fixed_agent = apply_fix(corrupting_agent, fix)
        
        # Verify fix works
        trace2 = await run_agent(fixed_agent)
        detections2 = await mao_client.get_detections(trace2.id)
        assert not any(d.type == "state_corruption" for d in detections2)


class TestDeadlockFixes:
    """Validate deadlock fix suggestions."""
    
    async def test_timeout_fix_prevents_deadlock(self):
        """Verify that adding timeouts prevents deadlocks."""
        
        # CrewAI agents that deadlock
        deadlocking_crew = create_deadlocking_crew()
        trace1 = await run_crew(deadlocking_crew)
        
        detections = await mao_client.get_detections(trace1.id)
        assert any(d.type == "deadlock" for d in detections)
        
        # Apply timeout fix
        fix = detections[0].fix_suggestion
        assert "timeout" in fix.code_change or "max_delegation_depth" in fix.code_change
        
        fixed_crew = apply_fix(deadlocking_crew, fix)
        trace2 = await run_crew(fixed_crew)
        
        # Should complete without deadlock
        assert trace2.status == "completed"
        detections2 = await mao_client.get_detections(trace2.id)
        assert not any(d.type == "deadlock" for d in detections2)
```

### 3.3 Fix Effectiveness Metrics

```python
# backend/scripts/measure_fix_effectiveness.py

async def measure_fix_effectiveness():
    """
    For each fix suggestion, measure:
    - Does applying it resolve the issue?
    - Does it introduce new issues?
    - Does the agent still work correctly?
    """
    
    results = []
    
    for detection in get_all_detections_with_fixes():
        original_trace = detection.trace
        fix = detection.fix_suggestion
        
        # Apply fix
        fixed_code = apply_fix(original_trace.agent_code, fix)
        
        # Re-run same scenario
        new_trace = await run_agent(fixed_code, original_trace.input)
        
        # Measure outcomes
        result = {
            'detection_id': detection.id,
            'detection_type': detection.type,
            'fix_type': fix.type,
            'original_issue_resolved': not has_same_detection(new_trace, detection.type),
            'new_issues_introduced': count_new_detections(new_trace, original_trace),
            'agent_still_functional': new_trace.status == 'completed',
            'output_quality_maintained': compare_output_quality(original_trace, new_trace),
        }
        
        results.append(result)
    
    # Calculate effectiveness rates
    for fix_type in ['max_iterations', 'state_validation', 'timeout', 'role_reinforcement']:
        fixes = [r for r in results if r['fix_type'] == fix_type]
        success_rate = sum(1 for r in fixes if r['original_issue_resolved']) / len(fixes)
        regression_rate = sum(1 for r in fixes if r['new_issues_introduced'] > 0) / len(fixes)
        
        print(f"{fix_type}: Success={success_rate:.1%}, Regressions={regression_rate:.1%}")
```

**Target Metrics:**
| Fix Type | Success Rate | Regression Rate | Functionality Preserved |
|----------|--------------|-----------------|------------------------|
| max_iterations | ≥95% | ≤5% | ≥95% |
| state_validation | ≥85% | ≤10% | ≥90% |
| timeout | ≥90% | ≤5% | ≥95% |
| role_reinforcement | ≥80% | ≤15% | ≥85% |

## 4. CI/CD Integration

### 4.1 GitHub Actions Workflow

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Integration Tests

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6am

jobs:
  golden-dataset-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run detection accuracy tests
        run: |
          python scripts/validate_detections.py
          
      - name: Assert minimum accuracy
        run: |
          python -c "
          import json
          with open('detection_results.json') as f:
              results = json.load(f)
          for dtype, metrics in results.items():
              assert metrics['f1'] >= 0.85, f'{dtype} F1 below threshold'
          "

  framework-integration-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        framework: [langchain, crewai, autogen, langgraph]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run integration tests (replay mode)
        env:
          MAO_RECORD_MODE: none
        run: |
          pytest tests/integration/test_${{ matrix.framework }}_integration.py -v
          
  fix-validation-tests:
    runs-on: ubuntu-latest
    needs: [golden-dataset-validation]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run fix effectiveness tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          MAO_RECORD_MODE: new_episodes
        run: |
          pytest tests/integration/test_fix_suggestions.py -v

  weekly-live-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Record fresh cassettes
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          MAO_RECORD_MODE: all
        run: |
          pytest tests/integration/ -v --cassette-dir=tests/cassettes/
          
      - name: Commit updated cassettes
        run: |
          git add tests/cassettes/
          git commit -m "chore: update VCR cassettes" || true
          git push
```

### 4.2 Test Environment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Test Environment                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Test      │     │   MAO       │     │   MAO       │       │
│  │   Agent     │────▶│   SDK       │────▶│   Backend   │       │
│  │  (Real LLM) │     │   Tracer    │     │   (Docker)  │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│        │                                        │               │
│        │                                        │               │
│        ▼                                        ▼               │
│  ┌─────────────┐                         ┌─────────────┐       │
│  │   VCR       │                         │   Test      │       │
│  │   Cassettes │                         │   Database  │       │
│  │   (Replay)  │                         │   (SQLite)  │       │
│  └─────────────┘                         └─────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Docker Compose for Testing

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  mao-backend:
    build: ./backend
    environment:
      - DATABASE_URL=sqlite:///./test.db
      - DETECTION_MODE=sync  # Synchronous for testing
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 3s
      retries: 3

  test-runner:
    build:
      context: .
      dockerfile: Dockerfile.test
    depends_on:
      mao-backend:
        condition: service_healthy
    environment:
      - MAO_ENDPOINT=http://mao-backend:8000
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MAO_RECORD_MODE=${MAO_RECORD_MODE:-none}
    volumes:
      - ./tests/cassettes:/app/tests/cassettes
    command: pytest tests/integration/ -v
```

## 5. Production Monitoring as Testing

### 5.1 Continuous Validation

```python
# backend/app/monitoring/continuous_validation.py

class ContinuousValidator:
    """
    Continuously validate detection accuracy using production data.
    Human-reviewed detections become ground truth.
    """
    
    async def validate_detection_accuracy(self):
        """Compare detection results with human labels."""
        
        # Get detections that have been human-reviewed
        reviewed = await db.detections.find({
            "human_reviewed": True,
            "reviewed_at": {"$gte": datetime.now() - timedelta(days=7)}
        })
        
        confusion_matrix = defaultdict(lambda: defaultdict(int))
        
        for detection in reviewed:
            predicted = detection.type
            actual = detection.human_label  # 'confirmed', 'false_positive', 'missed'
            
            if actual == 'confirmed':
                confusion_matrix[predicted]['tp'] += 1
            elif actual == 'false_positive':
                confusion_matrix[predicted]['fp'] += 1
        
        # Alert on accuracy degradation
        for dtype, counts in confusion_matrix.items():
            precision = counts['tp'] / (counts['tp'] + counts['fp'] + 0.001)
            if precision < THRESHOLDS[dtype]:
                await alert_accuracy_degradation(dtype, precision)
```

### 5.2 Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    Continuous Improvement Loop                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Production     Human        Golden       Detection    Deploy    │
│  Traces    ──▶  Review  ──▶  Dataset ──▶  Training ──▶ Update   │
│                                                                  │
│     │            │            │             │            │       │
│     │            │            │             │            │       │
│     ▼            ▼            ▼             ▼            ▼       │
│  Collect     Label as     Add to       Improve      Monitor     │
│  real        TP/FP/FN     fixtures     algorithms   accuracy    │
│  failures                                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 6. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Set up VCR recording infrastructure
- [ ] Create LangChain integration test suite
- [ ] Implement detection accuracy validation script
- [ ] Set up GitHub Actions CI pipeline

### Phase 2: Framework Coverage (Week 3-4)
- [ ] Add CrewAI integration tests
- [ ] Add AutoGen integration tests
- [ ] Add LangGraph integration tests
- [ ] Record initial cassette library

### Phase 3: Fix Validation (Week 5-6)
- [ ] Implement fix application framework
- [ ] Create fix effectiveness measurement
- [ ] Build before/after comparison tests
- [ ] Measure fix success rates

### Phase 4: Production Loop (Week 7-8)
- [ ] Deploy human review interface
- [ ] Implement continuous validation
- [ ] Build feedback loop automation
- [ ] Create accuracy dashboards

## Appendix: Test Utilities

### A. Agent Factory

```python
# backend/tests/factories/agents.py

class AgentFactory:
    """Factory for creating test agents with known behaviors."""
    
    @staticmethod
    def create_looping_agent(loop_type: str = "tool_repeat"):
        """Create agent that will enter infinite loop."""
        ...
    
    @staticmethod
    def create_corrupting_agent(corruption_type: str = "state_overwrite"):
        """Create agent that corrupts state."""
        ...
    
    @staticmethod
    def create_drifting_agent(drift_severity: str = "moderate"):
        """Create agent that drifts from persona."""
        ...
    
    @staticmethod
    def create_deadlocking_crew(deadlock_type: str = "circular_delegation"):
        """Create CrewAI crew that deadlocks."""
        ...
    
    @staticmethod
    def create_healthy_agent():
        """Create well-behaved agent for negative tests."""
        ...
```

### B. Assertion Helpers

```python
# backend/tests/helpers/assertions.py

async def assert_detection_triggered(
    trace_id: str,
    detection_type: str,
    within_seconds: int = 5
):
    """Assert that a specific detection was triggered."""
    ...

async def assert_no_false_positives(trace_id: str):
    """Assert that no detections were triggered for healthy trace."""
    ...

async def assert_fix_resolves_issue(
    original_code: str,
    fix: FixSuggestion,
    test_input: dict
):
    """Assert that applying fix resolves the original issue."""
    ...
```
