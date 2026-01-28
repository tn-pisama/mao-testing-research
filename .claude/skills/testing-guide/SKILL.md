---
name: testing-guide
description: |
  pytest patterns, golden datasets, and fixture conventions for PISAMA.
  Use when writing tests, organizing test files, or using golden datasets.
  Ensures consistent testing patterns and proper fixture usage.
allowed-tools: Read, Grep, Glob, Write, Bash
---

# Testing Guide Skill

You are writing tests for the PISAMA platform. Your goal is to follow established testing patterns, use fixtures correctly, and leverage golden datasets.

## Test Organization

```
backend/tests/
├── unit/                    # Unit tests (fast, no I/O)
│   ├── test_detection/
│   ├── test_ingestion/
│   └── test_fixes/
├── integration/             # Integration tests (DB, API)
│   ├── test_api_endpoints.py
│   └── test_database.py
├── e2e/                     # End-to-end tests
│   └── test_trace_to_detection.py
├── detection_enterprise/    # Enterprise tier tests
│   └── test_ml_detector.py
├── fixtures/                # Test fixtures and data
│   ├── golden/             # Golden dataset traces
│   └── mocks/              # Mock objects
├── benchmark/               # MAST benchmark tests
│   └── test_mast_evaluation.py
└── conftest.py              # Shared fixtures

```

---

## Test File Naming

**Pattern:** `test_{module_name}.py`

- ✅ `test_loop_detector.py`
- ✅ `test_api_traces.py`  
- ❌ `loop_test.py` (wrong prefix)
- ❌ `test_loops.py` (should match module name)

**Class naming:** `Test{Feature}`

```python
class TestLoopDetector:
    def test_exact_match(self):
        pass
    
    def test_structural_similarity(self):
        pass
```

---

## Common Fixtures

### conftest.py Fixtures

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.storage.models import Base

@pytest.fixture
async def db_session():
    """Provide test database session."""
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def sample_trace():
    """Provide sample trace for testing."""
    return {
        "trace_id": "test-123",
        "spans": [
            {"span_id": "span-1", "name": "agent.run", ...},
            {"span_id": "span-2", "name": "tool.call", ...},
        ]
    }

@pytest.fixture
def mock_detector(mocker):
    """Provide mocked detector."""
    detector = mocker.Mock()
    detector.detect.return_value = []
    return detector
```

---

## Golden Dataset Usage

Golden datasets are real traces with known ground-truth labels stored in `tests/fixtures/golden/`.

### Loading Golden Traces

```python
import pytest
import json
from pathlib import Path

@pytest.fixture
def golden_traces():
    """Load all golden traces."""
    golden_dir = Path(__file__).parent / "fixtures" / "golden"
    traces = []
    
    for trace_file in golden_dir.glob("*.json"):
        with open(trace_file) as f:
            traces.append(json.load(f))
    
    return traces

def test_detector_on_golden_dataset(golden_traces, loop_detector):
    """Test detector accuracy on golden dataset."""
    for trace in golden_traces:
        if trace["expected_failure"] == "LOOP-001":
            detections = loop_detector.detect(trace)
            assert len(detections) > 0, f"Failed to detect loop in {trace['trace_id']}"
```

### Adding Golden Traces

```python
# Save a new golden trace
golden_trace = {
    "trace_id": "golden-loop-001",
    "description": "Exact message loop example",
    "expected_failure": "LOOP-001",
    "spans": [...],
    "ground_truth": {
        "has_failure": True,
        "failure_type": "LOOP",
        "failure_code": "LOOP-001",
        "affected_span_ids": ["span-2", "span-3", "span-4"]
    }
}

with open("tests/fixtures/golden/loop_001.json", "w") as f:
    json.dump(golden_trace, f, indent=2)
```

---

## Detection Test Patterns

### Pattern 1: Positive Case Test

```python
def test_loop_detector_finds_exact_match():
    """Test detector finds exact message loops."""
    trace = create_trace_with_loop(
        messages=["I'll help you with that"] * 3
    )
    
    detector = LoopDetector()
    detections = detector.detect(trace)
    
    assert len(detections) == 1
    assert detections[0].type == "loop"
    assert detections[0].confidence >= 0.9
```

### Pattern 2: Negative Case Test

```python
def test_loop_detector_ignores_valid_pattern():
    """Test detector doesn't flag intentional iteration."""
    trace = create_trace_with_iteration(
        messages=[f"Processing file {i} of 10" for i in range(1, 11)]
    )
    
    detector = LoopDetector()
    detections = detector.detect(trace)
    
    assert len(detections) == 0, "Should not flag valid iteration as loop"
```

### Pattern 3: Edge Case Test

```python
@pytest.mark.parametrize("occurrences", [1, 2, 3, 4, 5])
def test_loop_detector_threshold(occurrences):
    """Test loop detection threshold (requires 3+ occurrences)."""
    trace = create_trace_with_loop(
        messages=["message"] * occurrences
    )
    
    detector = LoopDetector()
    detections = detector.detect(trace)
    
    if occurrences >= 3:
        assert len(detections) > 0, f"Should detect loop with {occurrences} occurrences"
    else:
        assert len(detections) == 0, f"Should not detect loop with {occurrences} occurrences"
```

---

## API Test Patterns

### Pattern 1: Endpoint Test

```python
@pytest.mark.asyncio
async def test_ingest_trace_endpoint(client, sample_trace):
    """Test POST /api/v1/traces/ingest."""
    response = await client.post("/api/v1/traces/ingest", json=sample_trace)
    
    assert response.status_code == 201
    assert "trace_id" in response.json()
```

### Pattern 2: Database Integration Test

```python
@pytest.mark.asyncio
async def test_trace_persisted_to_db(client, db_session, sample_trace):
    """Test trace is saved to database."""
    await client.post("/api/v1/traces/ingest", json=sample_trace)
    
    # Query database
    result = await db_session.execute(
        select(Trace).where(Trace.trace_id == sample_trace["trace_id"])
    )
    trace = result.scalar_one()
    
    assert trace is not None
    assert trace.trace_id == sample_trace["trace_id"]
```

---

## Mocking Patterns

### Mock External API

```python
def test_detection_with_mocked_llm(mocker):
    """Test detection with mocked LLM judge."""
    mock_llm = mocker.patch("app.detection.llm_judge.llm_client")
    mock_llm.complete.return_value = {
        "is_failure": True,
        "failure_type": "LOOP",
        "confidence": 0.92
    }
    
    detector = LLMJudgeDetector()
    detections = detector.detect(sample_trace)
    
    assert len(detections) > 0
    mock_llm.complete.assert_called_once()
```

### Mock Database

```python
def test_service_with_mocked_db(mocker):
    """Test service logic without real database."""
    mock_repo = mocker.Mock()
    mock_repo.get_trace.return_value = sample_trace
    
    service = DetectionService(repository=mock_repo)
    result = await service.detect_failures("trace-123")
    
    mock_repo.get_trace.assert_called_with("trace-123")
```

---

## Running Tests

### Run All Tests
```bash
cd backend
pytest
```

### Run Specific Test File
```bash
pytest tests/unit/test_detection/test_loop_detector.py -v
```

### Run Tests by Pattern
```bash
pytest -k "loop" -v  # All tests with "loop" in name
```

### Run Tests by Marker
```bash
pytest -m "integration" -v  # All integration tests
```

### With Coverage
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Test Markers

```python
import pytest

@pytest.mark.unit
def test_unit():
    pass

@pytest.mark.integration
async def test_integration():
    pass

@pytest.mark.e2e
async def test_e2e():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass

@pytest.mark.skip(reason="Feature not implemented yet")
def test_future_feature():
    pass
```

---

## Testing Checklist

- [ ] Test file named `test_*.py`
- [ ] Positive cases (detector finds failure)
- [ ] Negative cases (detector ignores valid patterns)
- [ ] Edge cases (thresholds, empty inputs, large inputs)
- [ ] Uses fixtures from conftest.py
- [ ] Async tests marked with `@pytest.mark.asyncio`
- [ ] Mocks external dependencies
- [ ] Tests pass locally (`pytest`)
- [ ] Tests pass in CI
- [ ] Coverage ≥ 80% for new code

---

## Resources

For test templates and examples:
- `resources/test-templates.md` - Complete test templates
- `tests/unit/test_detection/` - Detection test examples
- `tests/integration/` - API integration examples
- `tests/fixtures/golden/` - Golden dataset traces
