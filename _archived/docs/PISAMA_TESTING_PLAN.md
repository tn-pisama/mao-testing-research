# Pisama Detection Testing Plan

Comprehensive plan to evaluate Pisama detection capabilities against all available datasets.

## Executive Summary

| Dataset Category | Source | Traces | Ground Truth | Priority |
|-----------------|--------|--------|--------------|----------|
| **Internal Synthetic** | Generators | ~4,650 | Labeled (F1-F16) | P0 - Baseline |
| **External Collected** | Scraped | 4,142 | Unlabeled | P1 - Real-world |
| **Raw External** | HuggingFace/Toolathlon | ~200MB | Partial labels | P2 - Scale test |

---

## Phase 1: Internal Synthetic Traces (Baseline Evaluation)

### 1.1 Data Sources

| Generator | Traces | Failure Modes | Complexity | Location |
|-----------|--------|---------------|------------|----------|
| `trace_generator.py` | 800 | F1-F16 (50 each) | Simple | `benchmarks/generators/` |
| `complex_trace_generator.py` | 2,100+ | F1-F16 | Simple/Medium/Complex | `benchmarks/generators/` |
| `semantic_trace_generator.py` | ~250 | F1-F14 | Semantic (no markers) | `benchmarks/generators/` |
| `adversarial_generator.py` | ~500 | F1,F2,F6,F7,F8,F14 | Adversarial edge cases | `benchmarks/generators/` |
| `workflow_trace_generator.py` | ~1,000 | F5,F11,F13 | Pipeline/Recovery workflows | `benchmarks/generators/` |

### 1.2 Test Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SYNTHETIC TRACE TEST MATRIX                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Detector     │ Simple │ Medium │ Complex │ Semantic │ Adversarial │ Target│
│  ─────────────┼────────┼────────┼─────────┼──────────┼─────────────┼───────│
│  F1  Spec     │   ✓    │   ✓    │    ✓    │    ✓     │      ✓      │ >85%  │
│  F2  Decomp   │   ✓    │   ✓    │    ✓    │    ✓     │      ✓      │ >80%  │
│  F3  Resource │   ✓    │   ✓    │    ✓    │    ✓     │             │ >75%  │
│  F4  Tool     │   ✓    │   ✓    │    ✓    │    ✓     │             │ >80%  │
│  F5  Workflow │   ✓    │   ✓    │    ✓    │    ✓     │             │ >85%  │
│  F6  Derail   │   ✓    │   ✓    │    ✓    │    ✓     │      ✓      │ >80%  │
│  F7  Context  │   ✓    │   ✓    │    ✓    │    ✓     │      ✓      │ >75%  │
│  F8  Withhold │   ✓    │   ✓    │    ✓    │    ✓     │      ✓      │ >75%  │
│  F9  Role     │   ✓    │   ✓    │    ✓    │    ✓     │             │ >80%  │
│  F10 Comms    │   ✓    │   ✓    │    ✓    │    ✓     │             │ >80%  │
│  F11 Coord    │   ✓    │   ✓    │    ✓    │    ✓     │             │ >80%  │
│  F12 Output   │   ✓    │   ✓    │    ✓    │    ✓     │             │ >85%  │
│  F13 Quality  │   ✓    │   ✓    │    ✓    │    ✓     │             │ >80%  │
│  F14 Complete │   ✓    │   ✓    │    ✓    │    ✓     │      ✓      │ >75%  │
│  F15 Ground   │   -    │   -    │    -    │    -     │             │ TBD   │
│  F16 Retriev  │   -    │   -    │    -    │    -     │             │ TBD   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Execution Commands

```bash
# Generate fresh traces (if needed)
cd /Users/tuomonikulainen/mao-testing-research/benchmarks

# Basic traces (F1-F16)
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python -m generators.trace_generator

# Complex multi-tier traces
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python -m generators.complex_trace_generator

# Semantic traces (implicit failures)
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python -m generators.semantic_trace_generator

# Adversarial edge cases
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python -m generators.adversarial_generator

# Run all detectors
python -m evaluation.run_all_detectors --input traces/ --output results/synthetic_eval.json

# Evaluate with versioning
python -m evaluation.evaluate_detectors --version 2.0 --traces traces/
```

### 1.4 Metrics & Targets

| Metric | Definition | Target (F1-F14) | Target (F15-F16) |
|--------|------------|-----------------|------------------|
| **Precision** | TP / (TP + FP) | > 85% | > 70% |
| **Recall** | TP / (TP + FN) | > 80% | > 65% |
| **F1 Score** | 2 * P * R / (P + R) | > 82% | > 67% |
| **FPR** | FP / (FP + TN) | < 15% | < 25% |

---

## Phase 2: External Collected Traces (Real-World Validation)

### 2.1 Data Inventory

**Aggregated Collection** (`traces/all_traces.jsonl` - 207 MB, 4,142 traces)

| Source | Count | Description |
|--------|-------|-------------|
| HuggingFace | 3,894 | Function calling, agent conversations |
| GitHub | 242 | Scraped from public repos |
| Research | 5 | Academic datasets |
| Anthropic | 1 | Anthropic examples |

**By Framework:**

| Framework | Count | Expected Detections |
|-----------|-------|---------------------|
| Agent Trajectory | 1,300 | F5, F6, F11, F14 |
| Function Calling | 878 | F4, F12 |
| Conversation | 800 | F7, F8, F10 |
| Code Agent | 668 | F1, F2, F6 |
| React | 249 | F6, F14 |
| LangChain | 34 | F4, F5, F6 |
| AutoGen | 28 | F9, F10, F11 |
| CrewAI | 28 | F9, F10, F11 |
| LangSmith | 20 | All |
| LangGraph | 17 | F5, F11 |

### 2.2 Labeling Strategy

Since external traces lack ground truth, we use a **tiered labeling approach**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LABELING WORKFLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  External Trace ──► Pisama Detection ──► Detection Results                 │
│                                              │                               │
│                                              ▼                               │
│                     ┌────────────────────────────────────────┐              │
│                     │         TRIAGE BY CONFIDENCE           │              │
│                     ├────────────────────────────────────────┤              │
│                     │  High (>0.8)  │ Auto-label positive    │              │
│                     │  Medium (0.5) │ LLM-as-Judge review    │              │
│                     │  Low (<0.5)   │ Sample for human review│              │
│                     └────────────────────────────────────────┘              │
│                                              │                               │
│                                              ▼                               │
│                           Golden Dataset (ground truth)                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Execution Plan

```bash
cd /Users/tuomonikulainen/mao-testing-research

# Run detection on all external traces
python -c "
import json
from pathlib import Path
from backend.app.detection.orchestrator import DetectionOrchestrator

orchestrator = DetectionOrchestrator()
results = []

with open('traces/all_traces.jsonl') as f:
    for i, line in enumerate(f):
        trace = json.loads(line)
        diagnosis = orchestrator.diagnose(trace)
        results.append({
            'trace_id': trace.get('id', f'trace_{i}'),
            'source': trace.get('source'),
            'framework': trace.get('framework'),
            'has_failures': diagnosis.has_failures,
            'failure_count': diagnosis.failure_count,
            'detections': [d.dict() for d in diagnosis.all_detections],
            'confidence': diagnosis.primary_failure.confidence if diagnosis.primary_failure else None
        })

with open('results/external_traces_detection.jsonl', 'w') as f:
    for r in results:
        f.write(json.dumps(r) + '\\n')
"

# Analyze detection distribution
python -c "
import json
from collections import Counter

detections = Counter()
sources = Counter()

with open('results/external_traces_detection.jsonl') as f:
    for line in f:
        r = json.loads(line)
        if r['has_failures']:
            for d in r['detections']:
                detections[d['detection_type']] += 1
            sources[r['source']] += 1

print('Detection Distribution:')
for d, count in detections.most_common():
    print(f'  {d}: {count}')

print('\\nFailures by Source:')
for s, count in sources.most_common():
    print(f'  {s}: {count}')
"
```

### 2.4 LLM-as-Judge Validation

For medium-confidence detections, use Claude to validate:

```python
# benchmarks/evaluation/llm_judge_validation.py

JUDGE_PROMPT = """
You are an expert in multi-agent system failures.

Given this trace and the detection result, determine if the detection is correct.

TRACE:
{trace_content}

DETECTION:
- Type: {detection_type}
- Description: {description}
- Confidence: {confidence}
- Evidence: {evidence}

Is this detection correct? Respond with:
1. CORRECT - The failure mode is accurately detected
2. INCORRECT - This is a false positive
3. PARTIAL - The failure exists but is misclassified

Explain your reasoning in 2-3 sentences.
"""
```

---

## Phase 3: Raw External Datasets (Scale Testing)

### 3.1 Data Sources

| Dataset | Size | Location | Format | Notes |
|---------|------|----------|--------|-------|
| HuggingFace Glaive | 7.5 MB | `traces/raw/hf_expanded_*.jsonl` | Function calling | Clean format |
| Toolathlon | 145 MB | `traces/raw/toolathlon_*.jsonl` | Agent trajectories | Tool use focus |
| Toucan 1.5M | 30 MB | `traces/raw/toucan_*.jsonl` | MCP trajectories | Partial download |

### 3.2 Format Normalization

Raw datasets need conversion to UniversalTrace format:

```python
# benchmarks/data/normalize_raw.py

def normalize_glaive(raw_trace: dict) -> UniversalTrace:
    """Convert Glaive function-calling format to UniversalTrace."""
    return UniversalTrace(
        trace_id=raw_trace.get('id', str(uuid4())),
        spans=[
            Span(
                name=msg['role'],
                content=msg['content'],
                tool_calls=extract_tool_calls(msg) if 'function_call' in msg else None
            )
            for msg in raw_trace['messages']
        ],
        metadata={
            'source': 'glaive',
            'original_format': 'function_calling'
        }
    )

def normalize_toolathlon(raw_trace: dict) -> UniversalTrace:
    """Convert Toolathlon trajectory format to UniversalTrace."""
    # ... implementation

def normalize_toucan(raw_trace: dict) -> UniversalTrace:
    """Convert Toucan MCP trajectory format to UniversalTrace."""
    # ... implementation
```

### 3.3 Scale Test Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Throughput** | 100 traces/sec | Time to process all traces |
| **Memory** | < 4 GB peak | Monitor during batch processing |
| **Latency p50** | < 50ms per trace | Single-trace detection time |
| **Latency p99** | < 200ms per trace | Tail latency |

### 3.4 Execution Commands

```bash
# Normalize and process raw datasets
cd /Users/tuomonikulainen/mao-testing-research

# Process Glaive (function calling)
python -c "
import json
import time
from pathlib import Path

start = time.time()
count = 0

for raw_file in Path('traces/raw').glob('hf_*.jsonl'):
    with open(raw_file) as f:
        for line in f:
            trace = json.loads(line)
            # Process trace
            count += 1

elapsed = time.time() - start
print(f'Processed {count} traces in {elapsed:.2f}s')
print(f'Throughput: {count/elapsed:.1f} traces/sec')
"

# Process Toolathlon (large dataset)
python -c "
import json
import time
from pathlib import Path

start = time.time()
count = 0
failures = 0

for raw_file in Path('traces/raw').glob('toolathlon_*.jsonl'):
    with open(raw_file) as f:
        for line in f:
            trace = json.loads(line)
            # Run detection (simplified)
            count += 1

elapsed = time.time() - start
print(f'Processed {count} traces in {elapsed:.2f}s')
print(f'Throughput: {count/elapsed:.1f} traces/sec')
"
```

---

## Phase 4: Cross-Framework Evaluation

### 4.1 Framework-Specific Detection

| Framework | Primary Failure Modes | Detection Focus |
|-----------|----------------------|-----------------|
| **LangChain** | F4 (Tool), F6 (Derailment) | Chain execution, tool calls |
| **LangGraph** | F5 (Workflow), F11 (Coordination) | State machine, node transitions |
| **AutoGen** | F9 (Role), F10 (Communication) | Multi-agent chat, role boundaries |
| **CrewAI** | F9 (Role), F10 (Communication), F11 (Coordination) | Task delegation, crew dynamics |
| **n8n** | F5 (Workflow), F12 (Output), F13 (Quality) | Workflow nodes, validation |
| **Function Calling** | F4 (Tool), F12 (Output) | Function schema, return values |

### 4.2 Framework Test Files

```bash
traces/by_framework/
├── langchain.jsonl       # 34 traces
├── langgraph.jsonl       # 17 traces
├── autogen.jsonl         # 28 traces
├── crewai.jsonl          # 28 traces
├── function_calling.jsonl # 878 traces
├── agent_trajectory.jsonl # 1,300 traces (indexed separately)
├── react.jsonl           # 249 traces
└── code_agent.jsonl      # 668 traces
```

### 4.3 Framework-Specific Evaluation

```bash
# Run per-framework evaluation
cd /Users/tuomonikulainen/mao-testing-research

for framework in langchain langgraph autogen crewai function_calling react code_agent; do
    echo "=== Evaluating $framework ==="
    python -c "
import json
from collections import Counter
from backend.app.detection.orchestrator import DetectionOrchestrator

orchestrator = DetectionOrchestrator()
detections = Counter()
total = 0

with open('traces/by_framework/${framework}.jsonl') as f:
    for line in f:
        trace = json.loads(line)
        diagnosis = orchestrator.diagnose(trace)
        total += 1
        if diagnosis.has_failures:
            for d in diagnosis.all_detections:
                detections[d.detection_type.value] += 1

print(f'Total traces: {total}')
print(f'Failure rate: {sum(detections.values())/total*100:.1f}%')
print('Detections:')
for d, c in detections.most_common(5):
    print(f'  {d}: {c} ({c/total*100:.1f}%)')
"
done
```

---

## Phase 5: Adversarial & Edge Case Testing

### 5.1 Adversarial Test Categories

| Category | Description | Generator |
|----------|-------------|-----------|
| **Borderline** | Partial failures, ambiguous cases | `adversarial_generator.py` |
| **Deceptive FP** | Successes that look like failures | `adversarial_generator.py` |
| **Deceptive FN** | Failures that look like successes | `adversarial_generator.py` |
| **Mixed** | Multiple co-occurring failure modes | `complex_trace_generator.py` |
| **Subtle** | Low-signal failures | `semantic_trace_generator.py` |

### 5.2 Adversarial Test Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ADVERSARIAL TEST EXPECTATIONS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Test Type           │ Expected FPR │ Expected FNR │ Acceptable Range      │
│  ────────────────────┼──────────────┼──────────────┼───────────────────────│
│  Borderline cases    │    20-30%    │    20-30%    │ Uncertain is OK       │
│  Deceptive FP        │    15-25%    │      N/A     │ Some FP acceptable    │
│  Deceptive FN        │      N/A     │    15-25%    │ Some FN acceptable    │
│  Mixed scenarios     │    10-15%    │    10-15%    │ Multi-label expected  │
│  Subtle failures     │    10-20%    │    25-35%    │ Low recall acceptable │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Robustness Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Calibration Error** | ECE (Expected Calibration Error) | < 0.10 |
| **Consistency** | Same input → same output | > 99% |
| **Degradation** | Performance drop on adversarial | < 20% |

---

## Phase 6: Golden Dataset Construction

### 6.1 Sample Selection Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GOLDEN DATASET CONSTRUCTION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Source                    │ Samples │ Selection Method                    │
│  ─────────────────────────┼─────────┼─────────────────────────────────────│
│  Synthetic (per F-mode)   │   20    │ Stratified by complexity            │
│  External (per framework) │   10    │ High-confidence detections          │
│  Adversarial              │   50    │ All edge cases                      │
│  Human-verified           │   100   │ Manual review queue                 │
│  ─────────────────────────┼─────────┼─────────────────────────────────────│
│  TOTAL                    │  ~500   │ Diverse, balanced                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Golden Dataset Schema

```python
# backend/app/detection/golden_dataset.py

@dataclass
class GoldenEntry:
    id: str
    trace: Dict[str, Any]  # Full trace content
    expected_detections: List[DetectionType]  # Ground truth labels
    expected_confidence_min: float
    expected_confidence_max: float
    source: str  # synthetic, external, human_verified
    difficulty: str  # easy, medium, hard, adversarial
    labeler: str  # generator, llm_judge, human
    label_confidence: float
    notes: Optional[str]
```

### 6.3 Labeling UI Integration

```bash
# Run labeling interface
cd /Users/tuomonikulainen/mao-testing-research
python -m backend.scripts.label_traces --input results/unlabeled_queue.jsonl
```

---

## Phase 7: Continuous Evaluation Pipeline

### 7.1 CI/CD Integration

```yaml
# .github/workflows/detection-eval.yml
name: Detection Evaluation

on:
  push:
    paths:
      - 'backend/app/detection/**'
      - 'benchmarks/**'
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run synthetic evaluation
        run: |
          python -m benchmarks.evaluation.run_all_detectors \
            --input benchmarks/traces/ \
            --output results/ci_synthetic.json

      - name: Run golden dataset evaluation
        run: |
          python -m benchmarks.evaluation.evaluate_golden \
            --golden data/golden_dataset.json \
            --output results/ci_golden.json

      - name: Check regression
        run: |
          python -m benchmarks.evaluation.check_regression \
            --baseline results/baseline.json \
            --current results/ci_golden.json \
            --threshold 0.05  # 5% regression allowed
```

### 7.2 Regression Monitoring

| Metric | Baseline | Warning | Critical |
|--------|----------|---------|----------|
| Overall F1 | 82.4% | < 80% | < 75% |
| Per-detector F1 | Varies | -5% | -10% |
| FPR | 15% | > 20% | > 25% |
| Latency p99 | 200ms | > 300ms | > 500ms |

### 7.3 Version Tracking

```bash
# Track detector versions
python -m benchmarks.data.detector_versioning \
    --register \
    --version 2.1 \
    --results results/eval_20260104.json \
    --notes "Added F15/F16 detectors"
```

---

## Implementation Schedule

| Phase | Duration | Prerequisites | Output |
|-------|----------|---------------|--------|
| **Phase 1** | 2 days | Generators ready | Baseline metrics |
| **Phase 2** | 3 days | Phase 1 complete | External validation |
| **Phase 3** | 2 days | Phase 2 complete | Scale test results |
| **Phase 4** | 2 days | Phase 1-3 complete | Framework comparison |
| **Phase 5** | 2 days | Adversarial generator | Robustness metrics |
| **Phase 6** | 3 days | Phases 1-5 complete | Golden dataset |
| **Phase 7** | 1 day | Phase 6 complete | CI/CD pipeline |

**Total: ~15 days**

---

## Success Criteria

### Minimum Viable Detection

| Requirement | Metric | Target |
|-------------|--------|--------|
| Core detection (F1-F14) | Avg F1 | > 80% |
| RAG detection (F15-F16) | Avg F1 | > 65% |
| False positive rate | Overall FPR | < 15% |
| Calibration | ECE | < 0.10 |

### Production Readiness

| Requirement | Metric | Target |
|-------------|--------|--------|
| Throughput | Traces/sec | > 100 |
| Latency p99 | Single trace | < 200ms |
| Memory | Peak usage | < 4 GB |
| Consistency | Same input = same output | > 99% |

---

## Appendix A: Data File Locations

```
/Users/tuomonikulainen/mao-testing-research/
├── benchmarks/
│   ├── generators/           # Synthetic trace generators
│   │   ├── trace_generator.py
│   │   ├── complex_trace_generator.py
│   │   ├── semantic_trace_generator.py
│   │   ├── adversarial_generator.py
│   │   └── workflow_trace_generator.py
│   ├── evaluation/           # Detection evaluation
│   │   ├── run_all_detectors.py
│   │   ├── evaluate_detectors.py
│   │   └── semantic_detector.py
│   ├── data/                 # Data utilities
│   │   ├── detector_versioning.py
│   │   └── data_split.py
│   └── results/              # Historical results
├── traces/                   # Collected traces
│   ├── all_traces.jsonl      # 4,142 traces, 207 MB
│   ├── by_framework/         # Indexed by framework
│   ├── by_source/            # Indexed by source
│   ├── by_type/              # Indexed by type
│   ├── raw/                  # Raw external datasets
│   │   ├── hf_expanded_*.jsonl       # 7.5 MB
│   │   ├── toolathlon_*.jsonl        # 145 MB
│   │   └── toucan_1.5m_*.jsonl       # 30 MB
│   └── index.json            # Trace index metadata
└── backend/
    └── app/
        └── detection/        # Detection implementations
            ├── orchestrator.py
            ├── specification.py      # F1
            ├── decomposition.py      # F2
            ├── resource_misallocation.py  # F3
            ├── tool_provision.py     # F4
            ├── workflow.py           # F5
            ├── derailment.py         # F6
            ├── context.py            # F7
            ├── withholding.py        # F8
            ├── role_usurpation.py    # F9
            ├── communication.py      # F10
            ├── coordination.py       # F11
            ├── output_validation.py  # F12
            ├── quality_gate.py       # F13
            ├── completion.py         # F14
            ├── grounding.py          # F15
            └── retrieval_quality.py  # F16
```

## Appendix B: Quick Start Commands

```bash
# Full evaluation pipeline
cd /Users/tuomonikulainen/mao-testing-research

# 1. Generate synthetic traces
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
python -m benchmarks.generators.trace_generator

# 2. Run detection on synthetic
python -m benchmarks.evaluation.run_all_detectors

# 3. Run detection on external
python -m benchmarks.evaluation.run_detection \
    --input traces/all_traces.jsonl \
    --output results/external_eval.json

# 4. Generate metrics report
python -m benchmarks.evaluation.evaluate_detectors \
    --version 2.0 \
    --output results/metrics_report.json

# 5. View results
cat results/metrics_report.json | python -m json.tool
```
