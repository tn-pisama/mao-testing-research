# Test Templates

Complete test templates for common PISAMA testing scenarios.

---

## Unit Test Template

```python
"""
Tests for {module_name}.

Coverage:
- Positive cases
- Negative cases  
- Edge cases
- Error handling
"""

import pytest
from app.{module_path} import {ClassName}


class Test{ClassName}:
    """Test suite for {ClassName}."""
    
    @pytest.fixture
    def instance(self):
        """Provide instance for testing."""
        return {ClassName}()
    
    def test_basic_functionality(self, instance):
        """Test basic operation."""
        result = instance.method("input")
        assert result == "expected"
    
    def test_edge_case_empty_input(self, instance):
        """Test handling of empty input."""
        result = instance.method("")
        assert result is None
    
    def test_error_handling(self, instance):
        """Test error is raised for invalid input."""
        with pytest.raises(ValueError):
            instance.method(None)
```

---

## Async Test Template

```python
"""
Async tests for {module_name}.
"""

import pytest
from app.{module_path} import {AsyncClass}


class Test{AsyncClass}:
    """Test suite for {AsyncClass}."""
    
    @pytest.fixture
    async def instance(self):
        """Provide async instance."""
        instance = {AsyncClass}()
        await instance.initialize()
        yield instance
        await instance.cleanup()
    
    @pytest.mark.asyncio
    async def test_async_operation(self, instance):
        """Test async method."""
        result = await instance.async_method("input")
        assert result == "expected"
    
    @pytest.mark.asyncio
    async def test_concurrent_calls(self, instance):
        """Test handling of concurrent operations."""
        results = await asyncio.gather(
            instance.async_method("input1"),
            instance.async_method("input2"),
            instance.async_method("input3"),
        )
        assert len(results) == 3
```

---

## Detector Test Template

```python
"""
Tests for {detector_name} detection algorithm.

Verifies accuracy on:
- Positive cases (detects failures)
- Negative cases (ignores valid patterns)
- Edge cases (thresholds, boundaries)
"""

import pytest
from app.detection.{detector_file} import {DetectorClass}, {DetectorClass}Config


class Test{DetectorClass}:
    """Test suite for {DetectorClass}."""
    
    @pytest.fixture
    def detector(self):
        """Provide detector instance with default config."""
        return {DetectorClass}()
    
    @pytest.fixture
    def detector_low_threshold(self):
        """Provide detector with low threshold (high sensitivity)."""
        config = {DetectorClass}Config(threshold=0.7)
        return {DetectorClass}(config)
    
    def test_detects_basic_failure(self, detector, sample_trace_with_failure):
        """Test detector finds basic failure pattern."""
        detections = detector.detect(sample_trace_with_failure)
        
        assert len(detections) == 1
        assert detections[0].type == "failure_type"
        assert detections[0].confidence >= 0.8
        assert detections[0].severity in ["low", "medium", "high", "critical"]
    
    def test_ignores_valid_pattern(self, detector, sample_trace_valid):
        """Test detector doesn't flag valid patterns as failures."""
        detections = detector.detect(sample_trace_valid)
        
        assert len(detections) == 0, "Should not detect failure in valid trace"
    
    @pytest.mark.parametrize("occurrences", [1, 2, 3, 4, 5])
    def test_threshold_boundary(self, detector, occurrences):
        """Test detection threshold (e.g., requires 3+ occurrences)."""
        trace = create_trace_with_pattern(occurrences=occurrences)
        detections = detector.detect(trace)
        
        if occurrences >= 3:
            assert len(detections) > 0, f"Should detect with {occurrences} occurrences"
        else:
            assert len(detections) == 0, f"Should not detect with {occurrences} occurrences"
    
    def test_handles_empty_trace(self, detector):
        """Test detector handles empty trace gracefully."""
        empty_trace = {"trace_id": "empty", "spans": []}
        detections = detector.detect(empty_trace)
        
        assert len(detections) == 0
    
    def test_handles_large_trace(self, detector):
        """Test detector handles large traces within latency budget."""
        import time
        large_trace = create_trace_with_spans(count=1000)
        
        start = time.monotonic()
        detections = detector.detect(large_trace)
        elapsed = time.monotonic() - start
        
        assert elapsed < 0.1, f"Detection took {elapsed}s, should be <100ms"
    
    def test_cost_tracking(self, detector, sample_trace_with_failure):
        """Test detector tracks cost metrics."""
        detections = detector.detect(sample_trace_with_failure)
        
        if detections:
            assert hasattr(detections[0], "cost_usd")
            assert detections[0].cost_usd >= 0
```

---

## API Integration Test Template

```python
"""
Integration tests for {endpoint_name} API endpoint.

Tests:
- HTTP methods
- Request validation
- Response format
- Database persistence
- Error handling
"""

import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.integration
class TestTraceIngestionAPI:
    """Test suite for trace ingestion API."""
    
    @pytest.fixture
    async def client(self):
        """Provide async HTTP client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_post_trace_success(self, client, sample_trace):
        """Test successful trace ingestion."""
        response = await client.post("/api/v1/traces/ingest", json=sample_trace)
        
        assert response.status_code == 201
        data = response.json()
        assert "trace_id" in data
        assert data["status"] == "ingested"
    
    @pytest.mark.asyncio
    async def test_post_trace_invalid_format(self, client):
        """Test rejection of invalid trace format."""
        invalid_trace = {"bad": "format"}
        response = await client.post("/api/v1/traces/ingest", json=invalid_trace)
        
        assert response.status_code == 422
        assert "error" in response.json()
    
    @pytest.mark.asyncio
    async def test_get_trace_by_id(self, client, db_session, sample_trace):
        """Test retrieving trace by ID."""
        # First ingest
        post_response = await client.post("/api/v1/traces/ingest", json=sample_trace)
        trace_id = post_response.json()["trace_id"]
        
        # Then retrieve
        get_response = await client.get(f"/api/v1/traces/{trace_id}")
        
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["trace_id"] == trace_id
    
    @pytest.mark.asyncio
    async def test_trace_persisted_to_db(self, client, db_session, sample_trace):
        """Test trace is saved to database."""
        await client.post("/api/v1/traces/ingest", json=sample_trace)
        
        # Query database
        from app.storage.models import Trace
        from sqlalchemy import select
        
        result = await db_session.execute(
            select(Trace).where(Trace.trace_id == sample_trace["trace_id"])
        )
        trace = result.scalar_one()
        
        assert trace is not None
        assert trace.trace_id == sample_trace["trace_id"]
        assert len(trace.spans) == len(sample_trace["spans"])
```

---

## End-to-End Test Template

```python
"""
End-to-end test for {workflow_name}.

Tests complete workflow:
1. Ingest trace
2. Run detection
3. Generate fix
4. Verify results
"""

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
class TestTraceToDetectionWorkflow:
    """E2E test for trace ingestion → detection → fix workflow."""
    
    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, client, trace_with_loop):
        """Test end-to-end: ingest → detect → fix."""
        # Step 1: Ingest trace
        ingest_response = await client.post(
            "/api/v1/traces/ingest", 
            json=trace_with_loop
        )
        assert ingest_response.status_code == 201
        trace_id = ingest_response.json()["trace_id"]
        
        # Step 2: Run detection
        detect_response = await client.post(
            f"/api/v1/traces/{trace_id}/detect"
        )
        assert detect_response.status_code == 200
        detections = detect_response.json()["detections"]
        assert len(detections) > 0
        detection_id = detections[0]["id"]
        
        # Step 3: Generate fix
        fix_response = await client.post(
            f"/api/v1/detections/{detection_id}/fix"
        )
        assert fix_response.status_code == 200
        fix = fix_response.json()
        assert "fix_type" in fix
        assert "description" in fix
        
        # Step 4: Verify fix quality
        assert fix["confidence"] >= 0.7
        assert len(fix["description"]) > 50
```

---

## Benchmark Test Template

```python
"""
Benchmark tests for {detector_name}.

Tests against MAST golden dataset.
"""

import pytest
from app.detection.{detector_file} import {DetectorClass}


@pytest.mark.benchmark
class TestDetectorBenchmark:
    """Benchmark tests using MAST dataset."""
    
    @pytest.fixture
    def detector(self):
        return {DetectorClass}()
    
    @pytest.fixture
    def golden_traces(self):
        """Load golden traces from fixtures."""
        import json
        from pathlib import Path
        
        golden_dir = Path(__file__).parent.parent / "fixtures" / "golden"
        traces = []
        
        for file in golden_dir.glob("*_loop_*.json"):
            with open(file) as f:
                traces.append(json.load(f))
        
        return traces
    
    def test_accuracy_on_golden_dataset(self, detector, golden_traces):
        """Test detector achieves target accuracy on golden dataset."""
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        
        for trace in golden_traces:
            detections = detector.detect(trace)
            has_detection = len(detections) > 0
            should_detect = trace["ground_truth"]["has_failure"]
            
            if has_detection and should_detect:
                true_positives += 1
            elif has_detection and not should_detect:
                false_positives += 1
            elif not has_detection and should_detect:
                false_negatives += 1
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        print(f"\nBenchmark Results:")
        print(f"Precision: {precision:.2f}")
        print(f"Recall: {recall:.2f}")
        print(f"F1: {f1:.2f}")
        
        assert f1 >= 0.70, f"F1 score {f1:.2f} below target 0.70"
```

---

## Parametrized Test Template

```python
"""
Parametrized tests for {functionality}.
"""

import pytest


@pytest.mark.parametrize("input,expected", [
    ("valid", "result"),
    ("edge_case", "edge_result"),
    ("empty", None),
])
def test_with_parameters(input, expected):
    """Test function with multiple inputs."""
    result = function_under_test(input)
    assert result == expected


@pytest.mark.parametrize("threshold", [0.5, 0.7, 0.9, 0.95])
def test_different_thresholds(threshold):
    """Test behavior at different threshold values."""
    config = DetectorConfig(threshold=threshold)
    detector = Detector(config)
    # ... test logic
```
