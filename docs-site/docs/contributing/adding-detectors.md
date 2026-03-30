# Adding New Detectors

This guide walks through adding a new failure mode detector to Pisama, from implementation to calibration.

## Step-by-Step Checklist

### 1. Create the Detector File

Place the detector in the appropriate directory:

- `backend/app/detection/` for ICP-tier detectors (available to all users)
- `backend/app/detection_enterprise/` for Enterprise-tier detectors (feature-flagged)

### 2. Define the Result Dataclass

Every detector must return a result with at minimum these fields:

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class MyDetectorResult:
    detected: bool
    confidence: float
    issue_type: Optional[str] = None
    severity: str = "medium"
    raw_score: Optional[float] = None
    calibration_info: Optional[Dict[str, Any]] = None
```

### 3. Implement the Detector Class

Follow the cheapest-first pattern -- try deterministic checks before expensive embedding or LLM calls:

```python
"""My Detector (MAST Taxonomy F-XX)"""

DETECTOR_VERSION = "1.0"
DETECTOR_NAME = "MyDetector"

class MyDetector:
    def __init__(self, confidence_scaling: float = 1.0):
        self.confidence_scaling = confidence_scaling

    def detect(self, task: str, output: str, context: str = "") -> MyDetectorResult:
        # 1. Cheap checks first (pattern matching, keyword analysis)
        # 2. More expensive checks if needed (embeddings, LLM)
        # 3. Calibrate confidence
        raw_score = self._compute_score(task, output, context)
        confidence = self._calibrate_confidence(raw_score)
        detected = confidence >= 0.5  # Threshold-tuned by calibration

        return MyDetectorResult(
            detected=detected,
            confidence=confidence,
            raw_score=raw_score,
        )

    def _compute_score(self, task, output, context) -> float:
        # Your detection logic here
        return 0.0

    def _calibrate_confidence(self, raw_score: float) -> float:
        return min(raw_score * self.confidence_scaling, 0.99)
```

### 4. Register in DetectionType Enum

Add your detector to `backend/app/detection/validation.py`:

```python
class DetectionType(Enum):
    # ... existing types ...
    MY_DETECTOR = "my_detector"
```

### 5. Create Golden Dataset Entries

Add labeled samples to `backend/app/detection_enterprise/golden_dataset.py`:

```python
GoldenDatasetEntry(
    id="my_detector_001",
    detection_type=DetectionType.MY_DETECTOR,
    input_data={"task": "...", "output": "...", "context": "..."},
    expected_detected=True,
    expected_confidence_min=0.7,
    expected_confidence_max=1.0,
    description="Case where detector should fire",
    source="manual",
    tags=["positive", "clear"],
    difficulty="medium",
)
```

Include both positive and negative cases. Aim for at least 20 entries (10 positive, 10 negative) across easy, medium, and hard difficulties.

### 6. Create a Golden Dataset Adapter

Add an adapter in `backend/app/detection/golden_adapters.py` that maps golden entries to detector-specific inputs:

```python
class MyDetectorGoldenAdapter:
    def adapt(self, entry: GoldenDatasetEntry) -> Tuple[Dict, bool]:
        """Convert golden entry to detector input + expected result."""
        inputs = {
            "task": entry.input_data["task"],
            "output": entry.input_data["output"],
            "context": entry.input_data.get("context", ""),
        }
        return inputs, entry.expected_detected
```

### 7. Write Tests

Create tests in `backend/tests/`:

```python
import pytest
from app.detection.my_detector import MyDetector

class TestMyDetector:
    def setup_method(self):
        self.detector = MyDetector()

    def test_positive_case(self):
        result = self.detector.detect(
            task="Write a Python function",
            output="Here is a JavaScript function...",
        )
        assert result.detected is True
        assert result.confidence >= 0.7

    def test_negative_case(self):
        result = self.detector.detect(
            task="Write a Python function",
            output="def my_function():\n    return 42",
        )
        assert result.detected is False
```

### 8. Wire into the Orchestrator

Add the detection method to `DetectionOrchestrator` in `backend/app/detection_enterprise/orchestrator.py` using the lazy-loading pattern:

```python
@property
def my_detector(self) -> MyDetector:
    if self._my_detector is None:
        self._my_detector = MyDetector()
    return self._my_detector
```

## Running Calibration

After adding golden dataset entries, run calibration to measure accuracy:

```bash
cd backend
python -m app.detection_enterprise.calibrate
```

This performs a grid search over thresholds and reports F1/precision/recall:

```
=== Calibration Results ===
my_detector:    F1=0.850  P=0.900  R=0.806  threshold=0.40  samples=40
```

## Interpreting Scores

| Metric | Target | Meaning |
|---|---|---|
| F1 >= 0.80 | Production | Reliable for production use |
| F1 >= 0.70 | Beta | Usable but needs improvement |
| F1 < 0.70 | Development | Not yet reliable |
| Precision > Recall | Conservative | Few false positives, may miss real failures |
| Recall > Precision | Aggressive | Catches most failures, but noisy |
| ECE < 0.05 | Well-calibrated | Reported confidence matches actual accuracy |

## Threshold Tuning Workflow

1. Run calibration to identify low-F1 detectors
2. Analyze false positives/negatives from the error analysis
3. Adjust detector logic (thresholds, patterns, exclusions)
4. Add more golden dataset entries covering edge cases
5. Re-run calibration to verify improvement
6. Repeat until F1 >= 0.80

## Common Pitfalls

These hard-won lessons prevent you from repeating past mistakes:

1. **LLM prompt data mapping is critical** -- Verify that golden dataset keys match prompt construction. Swapped `task` and `output` fields once caused persona_drift to drop from 0.932 to 0.716.

2. **Per-detector soft downgrade hurts high-precision detectors** -- LLM uncertainty is not the same as a false positive. Some detectors (coordination, grounding) should never have their confidence lowered by the LLM judge. Use the `_no_downgrade` set.

3. **Word-boundary matching prevents substring false positives** -- Critical for ordering detection. Use `\b` word boundaries in regex patterns.

4. **Stemmer edge cases** -- The stemmer must handle double-s words and "ses" plurals specially.

5. **n8n nested data** -- n8n wraps data in `{"json": {...}}`. Flatten nested dicts before running corruption checks.

6. **Boolean type changes are not corruption** -- Python treats `True=1, False=0`, so `True -> False` looks like a 100% magnitude drop. Exclude booleans from magnitude checks.

## Tiered Detection Integration

Your detector is automatically wrapped with tiered detection based on its calibration results. To enable escalation:

1. Ensure the detector has a `confidence_scaling` parameter
2. Add golden dataset entries (positive and negative)
3. The calibration pipeline auto-wraps based on F1 and ECE

## Further Reading

- [Detection Tiers](../concepts/detection-tiers.md) -- How tiered escalation works
- [Failure Modes Reference](../concepts/failure-modes.md) -- All 22 failure modes
- [Technical Architecture](../concepts/architecture.md) -- System overview
