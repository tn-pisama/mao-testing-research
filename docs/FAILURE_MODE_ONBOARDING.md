# Failure Mode Detection — Engineering & DS Onboarding

Get productive with PISAMA's detection system within a day. This guide covers running detectors, adding new ones, calibrating thresholds, and debugging failures.

For the customer-facing failure mode reference, see [`docs/failure-modes-reference.md`](./failure-modes-reference.md).

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Environment variables: `DATABASE_URL`, `ANTHROPIC_API_KEY`
- Install dependencies: `pip install -e ".[dev]"` from `backend/`

### Running the Detection Pipeline

The detection pipeline runs via the `DetectionOrchestrator` which analyzes a full trace:

```python
from app.detection_enterprise.orchestrator import DetectionOrchestrator

orchestrator = DetectionOrchestrator(
    enable_llm_explanation=True,
    max_parallel_detectors=5,
    timeout_seconds=30.0,
)
result = orchestrator.analyze_trace(trace)

print(f"Failures found: {result.failure_count}")
print(f"Primary failure: {result.primary_failure}")
for detection in result.all_detections:
    print(f"  {detection.category}: {detection.confidence:.2f} ({detection.severity})")
```

### Running a Single Detector

Each detector can be invoked independently:

```python
from app.detection.loop import MultiLevelLoopDetector, StateSnapshot

detector = MultiLevelLoopDetector()
states = [
    StateSnapshot(agent_id="agent_1", state_delta={"step": 1}, content="...", sequence_num=0),
    StateSnapshot(agent_id="agent_1", state_delta={"step": 1}, content="...", sequence_num=1),
]
result = detector.detect_loop(states)
print(f"Loop detected: {result.detected}, confidence: {result.confidence}")
```

### Running Calibration

```bash
cd backend
python -m app.detection_enterprise.calibrate
```

This runs all detectors against the golden dataset and outputs F1/P/R per detector.

---

## Architecture at a Glance

```
┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐    ┌─────────┐
│  Trace       │───▶│  Ingestion   │───▶│  Detection Pipeline  │───▶│ Storage │
│  (OTEL/n8n)  │    │  Parser      │    │  (Orchestrator)      │    │ (PG)    │
└─────────────┘    └──────────────┘    └──────────┬───────────┘    └────┬────┘
                                                   │                     │
                                                   ▼                     ▼
                                          ┌────────────────┐    ┌──────────────┐
                                          │  Self-Healing   │    │  Frontend    │
                                          │  Pipeline       │    │  Dashboard   │
                                          └────────────────┘    └──────────────┘
```

### Key Files

| Component | Entry Point | Purpose |
|-----------|-------------|---------|
| Orchestrator | `backend/app/detection_enterprise/orchestrator.py` | Runs all detectors on a trace |
| Tiered Detection | `backend/app/detection_enterprise/tiered.py` | Cost-aware escalation (rules → AI → human) |
| Calibration | `backend/app/detection_enterprise/calibrate.py` | Golden dataset benchmarking |
| LLM Judge | `backend/app/detection/llm_judge/judge.py` | Claude-based failure verification |
| Turn-Aware Base | `backend/app/detection/turn_aware/_base.py` | Base class for conversation detectors |
| Validation | `backend/app/detection/validation.py` | DetectionType enum, metrics, ECE |
| Golden Dataset | `backend/app/detection_enterprise/golden_dataset.py` | Test data management |
| Embeddings | `backend/app/core/embeddings.py` | E5-large-instruct, nomic, ensemble |
| Healing Engine | `backend/app/healing/engine.py` | 5-stage self-healing |
| Storage Models | `backend/app/storage/models.py` | SQLAlchemy models |

### Tiered Detection Overview

Detection uses a cost-aware escalation model:

| Tier | Method | Cost | When Used |
|------|--------|------|-----------|
| 1 | Rule-based (hash, pattern, structural) | $0.00 | Always — first pass |
| 2 | State delta (cross-field, velocity) | $0.00 | When Tier 1 is inconclusive |
| 3 | Embedding similarity (E5/nomic) | ~$0.001 | Gray zone confidence (0.35–0.65) |
| 4 | LLM Judge (Claude) | ~$0.005–0.05 | Tier 3 still uncertain |
| 5 | Human review | $50+ | Critical decisions only |

The goal is **$0.05/trace average** — most traces resolve at Tier 1–2.

---

## How a Detector Works

### Walk-Through: Loop Detection (`backend/app/detection/loop.py`)

The `MultiLevelLoopDetector` is a good example of the multi-tier approach within a single detector:

1. **Structural matching** — Compares `agent_id` and `state_delta` keys between consecutive states. If identical, it's likely a loop. Base confidence: 0.96.

2. **Hash collision** — Computes SHA256 hash of normalized state_delta. If two states hash identically, they contain the same data. Base confidence: 0.80.

3. **Semantic similarity** — Uses embeddings to compare content. If similarity exceeds threshold, detects semantically similar but not identical loops. Base confidence: 0.70.

4. **Semantic clustering** — KMeans clustering on embeddings for longer traces (≥6 states). Detects if a dominant cluster represents >60% of states or cyclic patterns in recent windows. Base confidence: 0.75.

The detector tries methods cheapest-first and returns the first positive match:

```python
# From MultiLevelLoopDetector.detect_loop()
def detect_loop(self, states: List[StateSnapshot]) -> LoopDetectionResult:
    # 1. Structural matching (free)
    for i in range(1, len(states)):
        if self._structural_match(states[i-1], states[i]):
            if not self._has_meaningful_progress(states[i-1], states[i]):
                return LoopDetectionResult(detected=True, method="structural", ...)

    # 2. Hash collision (free)
    hashes = {}
    for state in states:
        h = self._compute_state_hash(state)
        if h in hashes:
            return LoopDetectionResult(detected=True, method="hash", ...)
        hashes[h] = state

    # 3. Semantic similarity (costs embedding compute)
    # ... embedding-based comparison

    # 4. Semantic clustering (costs more embedding compute)
    # ... KMeans clustering for pattern detection
```

Key anti-false-positive measures:
- **Summary/recap whitelisting** (v1.2): Phrases like "to summarize" or "step 3 of 5" are not loops
- **Meaningful progress check**: New keys or >2 value changes mean actual progress

### TurnAwareDetector Base Class

For conversation-level analysis, detectors extend `TurnAwareDetector` (`backend/app/detection/turn_aware/_base.py`):

```python
@dataclass
class TurnSnapshot:
    turn_number: int
    participant_type: str    # 'user', 'agent', 'system', 'tool'
    participant_id: str
    content: str
    content_hash: str        # SHA256[:16], auto-generated
    accumulated_context: str  # Running context
    accumulated_tokens: int
    turn_metadata: Dict[str, Any]

class TurnAwareDetector(ABC):
    name: str = "TurnAwareDetector"
    version: str = "1.1"
    supported_failure_modes: List[str] = []

    @abstractmethod
    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        pass
```

Constants: `MAX_TURNS_BEFORE_SUMMARIZATION = 50`, `MAX_TOKENS_BEFORE_SUMMARIZATION = 8000`, `EMBEDDING_SIMILARITY_THRESHOLD = 0.7`.

### DetectionResult Structure

The orchestrator returns `DetectionResult` objects:

```python
@dataclass
class DetectionResult:
    category: DetectionCategory   # "loop", "corruption", etc.
    detected: bool
    confidence: float             # 0.0–1.0
    severity: Severity            # CRITICAL, HIGH, MEDIUM, LOW, INFO
    title: str
    description: str
    evidence: List[Dict[str, Any]]
    affected_spans: List[str]
    suggested_fix: Optional[str]
    raw_result: Optional[Any]     # Detector-specific result dataclass
```

### Registration in DetectionType Enum

All detectors must be registered in `backend/app/detection/validation.py`:

```python
class DetectionType(Enum):
    LOOP = "loop"
    CORRUPTION = "corruption"
    PERSONA_DRIFT = "persona_drift"
    HALLUCINATION = "hallucination"
    DERAILMENT = "derailment"
    OVERFLOW = "overflow"
    COORDINATION = "coordination"
    INJECTION = "injection"
    COMMUNICATION = "communication"
    CONTEXT = "context"
    DECOMPOSITION = "decomposition"
    WORKFLOW = "workflow"
    GROUNDING = "grounding"
    RETRIEVAL_QUALITY = "retrieval_quality"
    # n8n-specific
    N8N_SCHEMA = "n8n_schema"
    N8N_CYCLE = "n8n_cycle"
    N8N_COMPLEXITY = "n8n_complexity"
    N8N_ERROR = "n8n_error"
    N8N_RESOURCE = "n8n_resource"
    N8N_TIMEOUT = "n8n_timeout"
```

---

## Adding a New Detector

### Step-by-Step Checklist

1. **Create detector file** in `backend/app/detection/` (ICP tier) or `backend/app/detection_enterprise/` (Enterprise tier)

2. **Define result dataclass** with at minimum: `detected: bool`, `confidence: float`, `raw_score: Optional[float]`, `calibration_info: Optional[Dict]`

3. **Implement the detector class** with:
   - `__init__()` accepting `confidence_scaling: float = 1.0` for calibration
   - Main `detect()` or `detect_with_confidence()` method
   - `_calibrate_confidence()` for threshold-aware confidence scoring

4. **Register in DetectionType enum** — add entry to `backend/app/detection/validation.py`

5. **Create golden dataset entries** — add labeled samples in `backend/app/detection_enterprise/golden_dataset.py` using `GoldenDatasetEntry`:
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
   )
   ```

6. **Create golden dataset adapter** in `backend/app/detection/golden_adapters.py` — maps golden entries to detector-specific inputs

7. **Write tests** in `backend/tests/` — at minimum test the positive and negative cases

8. **Wire into orchestrator** — add detection method to `DetectionOrchestrator` in `backend/app/detection_enterprise/orchestrator.py` following the lazy-loading pattern:
   ```python
   @property
   def my_detector(self) -> MyDetector:
       if self._my_detector is None:
           self._my_detector = MyDetector()
       return self._my_detector
   ```

### Template

```python
"""My Detector (MAST Taxonomy F-XX)"""

DETECTOR_VERSION = "1.0"
DETECTOR_NAME = "MyDetector"

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class MyDetectorResult:
    detected: bool
    confidence: float
    issue_type: Optional[str] = None
    severity: str = "medium"
    raw_score: Optional[float] = None
    calibration_info: Optional[Dict[str, Any]] = None

class MyDetector:
    def __init__(self, confidence_scaling: float = 1.0):
        self.confidence_scaling = confidence_scaling

    def detect(self, task: str, output: str, context: str = "") -> MyDetectorResult:
        # 1. Cheap checks first (pattern matching, keyword analysis)
        # 2. More expensive checks if needed (embeddings, LLM)
        # 3. Calibrate confidence
        raw_score = self._compute_score(task, output, context)
        confidence = self._calibrate_confidence(raw_score)
        detected = confidence >= 0.5  # Will be threshold-tuned by calibration

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

---

## Calibration & Benchmarking

### Golden Dataset

The golden dataset lives in `backend/fixtures/golden/`:
- `manifest.json` — metadata (counts by detection type)
- `golden_traces.jsonl` — 1067 OTEL traces, one per line

Each trace has `_golden_metadata` with ground truth:
```json
{
  "resourceSpans": [...],
  "_golden_metadata": {
    "detection_type": "F3_resource_misallocation",
    "expected_detection": true,
    "mast_annotation": {"1.3": 1},
    "variant": "default"
  }
}
```

Additionally, in-memory golden entries are defined in `backend/app/detection_enterprise/golden_dataset.py` using the `GoldenDatasetEntry` dataclass:
```python
@dataclass
class GoldenDatasetEntry:
    id: str
    detection_type: DetectionType
    input_data: Dict[str, Any]
    expected_detected: bool
    expected_confidence_min: float = 0.0
    expected_confidence_max: float = 1.0
    description: str = ""
    source: str = "manual"
    tags: List[str] = field(default_factory=list)
    difficulty: str = "medium"  # "easy", "medium", "hard"
```

### Running Calibration

```bash
cd backend
python -m app.detection_enterprise.calibrate
```

This performs a grid search over thresholds `[0.10, 0.15, 0.20, ..., 0.90]` for each detector and reports:

```
=== Calibration Results ===
injection:      F1=0.927  P=0.983  R=0.877  threshold=0.35  samples=120
corruption:     F1=0.906  P=0.955  R=0.863  threshold=0.30  samples=95
loop:           F1=0.846  P=0.829  R=0.863  threshold=0.40  samples=110
...
```

Output dataclass:
```python
@dataclass
class CalibrationResult:
    detection_type: str
    optimal_threshold: float
    precision: float
    recall: float
    f1: float
    sample_count: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    ece: float  # Expected Calibration Error
```

### Interpreting Scores

| Metric | Target | What It Means |
|--------|--------|---------------|
| F1 ≥ 0.80 | Production | Detector is reliable enough for production use |
| F1 ≥ 0.70 | Beta | Usable but needs improvement |
| F1 < 0.70 | Development | Not yet reliable for users |
| Precision > Recall | Conservative | Few false positives, may miss real failures |
| Recall > Precision | Aggressive | Catches most failures, but noisy |
| ECE < 0.05 | Well-calibrated | Reported confidence matches actual accuracy |

### Threshold Tuning Workflow

1. Run calibration → identify low-F1 detectors
2. Analyze false positives/negatives using `SamplePrediction` error analysis
3. Adjust detector logic (thresholds, patterns, exclusions)
4. Add more golden dataset entries covering edge cases
5. Re-run calibration → verify improvement
6. Repeat until F1 ≥ 0.80

### Sprint 9c Accuracy (Current)

| Detector | F1 | P | R | Status |
|---|---|---|---|---|
| injection | 0.927 | 0.983 | 0.877 | Production |
| persona_drift | 0.932 | 0.921 | 0.944 | Production |
| corruption | 0.906 | 0.955 | 0.863 | Production |
| withholding | 0.874 | 0.857 | 0.891 | Production |
| context | 0.868 | 0.842 | 0.896 | Production |
| loop | 0.846 | 0.829 | 0.863 | Production |
| retrieval_quality | 0.832 | 0.721 | 0.984 | Production |
| overflow | 0.823 | 1.000 | 0.699 | Production |
| derailment | 0.820 | 0.702 | 0.985 | Production |
| communication | 0.818 | 0.795 | 0.842 | Production |
| workflow | 0.808 | 0.843 | 0.776 | Production |
| hallucination | 0.791 | 0.762 | 0.822 | Beta |
| coordination | 0.786 | 0.768 | 0.805 | Beta |
| decomposition | 0.772 | 0.753 | 0.791 | Beta |
| specification | 0.717 | 0.701 | 0.734 | Beta |
| completion | 0.733 | 0.718 | 0.749 | Beta |
| grounding | 0.704 | 0.689 | 0.720 | Beta |

---

## Tiered Detection Deep Dive

### TierConfig

The tiered system is configured per detector type in `backend/app/detection_enterprise/tiered.py`:

```python
@dataclass
class TierConfig:
    rule_confidence_threshold: float = 0.7       # Escalate below this
    cheap_ai_confidence_threshold: float = 0.8
    expensive_ai_confidence_threshold: float = 0.85
    gray_zone_lower: float = 0.35               # Uncertain range
    gray_zone_upper: float = 0.65
    enable_cheap_ai: bool = True
    enable_expensive_ai: bool = True
    enable_human_escalation: bool = True
    track_costs: bool = True
```

### Gray Zone Handling

When confidence falls in [0.35, 0.65], the result is "uncertain" and escalates to the next tier. This prevents the system from committing to low-confidence decisions.

### LLM Judge Integration

The LLM Judge (`backend/app/detection/llm_judge/judge.py`) fires at Tier 3–4:

- **Model routing**: Failure modes are routed to specific model tiers:
  - **Tier 1 (low-stakes)**: F3, F7, F11, F12 → `gemini-flash-lite` ($0.10/$0.40 per 1M tokens)
  - **Tier 2 (default)**: F1, F2, F4, F5, F10, F13 → `claude-sonnet-4` ($3/$15 per 1M tokens)
  - **Tier 3 (high-stakes)**: F6, F8, F9, F14 → `claude-sonnet-4-thinking` (extended thinking)

- **RAG retrieval**: Few-shot examples from pgvector (similarity ≥ 0.65)
- **Caching**: SHA256-based cache with LRU eviction (max 1000 entries)
- **Cost tracking**: `JudgeCostTracker` records per-tier and per-provider spend

### The `_no_downgrade` Set

Some detectors should **never** have their confidence lowered by the LLM judge, because they have high precision from rule-based methods:

```python
_no_downgrade = {"coordination", "grounding", ...}
```

For these, the LLM judge can only **boost** confidence, not reduce it. This prevents regression on high-precision detectors.

### Adding a Detector to Tiered Wrapping

In the calibration pipeline, detectors are wrapped with tiered detection based on their calibration results. To enable tiered escalation for a new detector:

1. Ensure the detector has a `confidence_scaling` parameter
2. Add golden dataset entries (positive and negative)
3. The calibration pipeline auto-wraps detectors in tiered detection based on their F1 and ECE

---

## Testing

### Test Organization

```
backend/tests/
├── unit/              # Individual detector tests
├── integration/       # Multi-component tests
├── detection_enterprise/  # Enterprise-tier detector tests
├── e2e/              # End-to-end pipeline tests
└── fixtures/
    └── golden/       # Golden dataset files
```

### Running Tests

```bash
# All tests
cd backend && pytest tests/

# Specific detector
pytest tests/ -k "test_loop"

# With verbose output
pytest tests/ -v --tb=short

# Detection enterprise tests only
pytest tests/detection_enterprise/
```

### Golden Dataset Adapter Pattern

Each detector needs an adapter that maps golden entries to detector-specific inputs. Adapters live in `backend/app/detection/golden_adapters.py`:

```python
class LoopGoldenAdapter:
    def adapt(self, entry: GoldenDatasetEntry) -> Tuple[List[StateSnapshot], bool]:
        """Convert golden entry to detector input + expected result."""
        states = self._parse_states(entry.input_data)
        expected = entry.expected_detected
        return states, expected
```

### Writing Detection Tests

```python
import pytest
from app.detection.my_detector import MyDetector

class TestMyDetector:
    def setup_method(self):
        self.detector = MyDetector()

    def test_positive_case(self):
        result = self.detector.detect(
            task="Write a Python function",
            output="Here is a JavaScript function...",  # Wrong language
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

---

## Debugging Detection Issues

### Common False Positives and Fixes

| Detector | False Positive Pattern | Fix |
|----------|----------------------|-----|
| Loop | Summary/recap messages | `_is_summary_or_progress()` whitelist patterns |
| Corruption | Boolean True→False | Exclude bools from `extreme_magnitude_change` |
| Corruption | Velocity on "version" field | `_VELOCITY_IMMUNE_ISSUES` set |
| Corruption | n8n nested `json` wrapper | `_flatten_nested_dicts()` before checks |
| Coordination | Normal ack protocols | Raised `max_back_forth_count` from 3 to 5 |
| Decomposition | Simple direct tasks | `SIMPLE_TASK_INDICATORS` bypass |
| Context | Legitimate adaptations | `ADAPTATION_PHRASES` recognition |

### Tracing a Detection to Raw Data

1. Get the detection record from the API:
   ```bash
   curl /api/v1/detections/{detection_id} -H "Authorization: Bearer $TOKEN"
   ```

2. Look at `details.evidence` — contains the specific data that triggered the detection

3. Find the trace: `trace_id` links to the full trace with all states

4. View states:
   ```bash
   curl /api/v1/traces/{trace_id}/states
   ```

5. Check `state_delta` at the `sequence_num` where the detection fired

### Key Learnings from Sprint 9b/9c

These hard-won lessons are documented here to prevent re-learning:

1. **Corruption: velocity filter on "version" field was suppressing ALL monotonic_regression** — The `version` field was in `high_velocity_fields`, which suppressed `monotonic_regression` detection for *any* field starting with "version". Fix: `_VELOCITY_IMMUNE_ISSUES` set that exempts issue types from velocity suppression.

2. **n8n entries nest state data inside `json` key** — n8n puts actual data in `{"json": {"actual_field": "value"}}`. Without flattening, corruption checks compare wrapper dicts instead of real data. Fix: `_flatten_nested_dicts()`.

3. **Boolean True→False triggers extreme_magnitude_change** — Python treats `True=1`, `False=0`, so `True→False` looks like a 100% drop. Fix: exclude `bool` types from magnitude checks.

4. **`field_disappeared` is too noisy for nested keys** — Only flag when 3+ fields vanish simultaneously, not individual nested key changes.

5. **Tiered soft downgrade HURT coordination/grounding** — These detectors have high precision from rules; LLM judge disagreements are usually wrong. Fix: `_no_downgrade` set.

6. **Sprint 9c: LLM prompt data mapping bug** — The `task` and `output` fields were swapped in the LLM judge prompt for some failure modes, causing persona_drift to score 0.716 instead of 0.932. Always verify prompt field mapping after changes.

---

## Framework-Specific Detection

### n8n Detectors

Six n8n-specific detection types registered in `DetectionType`:

| Type | Purpose |
|------|---------|
| `n8n_schema` | Schema/type mismatches between connected nodes |
| `n8n_cycle` | Graph cycles in workflow connections |
| `n8n_complexity` | Excessive nodes, branching, cyclomatic complexity |
| `n8n_error` | Missing error handling, unprotected AI nodes |
| `n8n_resource` | Missing maxTokens, unbounded loops, no timeout on HTTP |
| `n8n_timeout` | Missing workflow/webhook/AI node timeout |

The n8n workflow validator (`backend/app/detection_enterprise/n8n_workflow_validator.py`) validates workflow JSON structure against known node types and connection topology.

### LangGraph Structural Detectors

LangGraph traces use `langgraph.node.name` and `langgraph.state` OTEL attributes. The OTEL parser extracts these into standard `ParsedState` objects.

### How Framework Detection Differs from MAST Detectors

MAST detectors (F1–F14) analyze **agent behavior** (what the agents said and did). Framework-specific detectors analyze **workflow structure** (how the workflow is configured). Both types produce `DetectionResult` objects and can trigger healing.

---

## Reference

### All 21 Failure Modes

| MAST ID | Name | Detector Key | Category |
|---------|------|-------------|----------|
| F1 | Specification Mismatch | `specification` | Planning |
| F2 | Poor Task Decomposition | `decomposition` | Planning |
| F3 | Resource Misallocation | `resource_misallocation` | Planning |
| F4 | Inadequate Tool Provision | `tool_provision` | Planning |
| F5 | Flawed Workflow Design | `workflow` | Planning |
| F6 | Task Derailment | `derailment` | Execution |
| F7 | Context Neglect | `context` | Execution |
| F8 | Information Withholding | `withholding` | Execution |
| F9 | Role Usurpation | `role_usurpation` | Execution |
| F10 | Communication Breakdown | `communication` | Execution |
| F11 | Coordination Failure | `coordination` | Execution |
| F12 | Output Validation Failure | `output_validation` | Verification |
| F13 | Quality Gate Bypass | `quality_gate` | Verification |
| F14 | Completion Misjudgment | `completion` | Verification |
| — | Loop Detection | `loop` | Extended |
| — | Context Overflow | `overflow` | Extended |
| — | Prompt Injection | `injection` | Extended |
| — | Hallucination | `hallucination` | Extended |
| — | Grounding Failure | `grounding` | Extended |
| — | Retrieval Quality | `retrieval_quality` | Extended |
| — | Persona Drift | `persona_drift` | Extended |
| — | State Corruption | `corruption` | Extended |
| — | Cost Tracking | `cost` | Extended |

### Further Reading

- [`docs/failure-modes-reference.md`](./failure-modes-reference.md) — Customer-facing failure mode reference
- [`docs/TECHNICAL_ARCHITECTURE.md`](./TECHNICAL_ARCHITECTURE.md) — Full system technical architecture
- [`docs/E2E_TESTING_STRATEGY.md`](./E2E_TESTING_STRATEGY.md) — End-to-end testing approach
- [`docs/STATE_OF_THE_ART_DETECTOR_DESIGN.md`](./STATE_OF_THE_ART_DETECTOR_DESIGN.md) — Research foundations
