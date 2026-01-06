# MAST Benchmarks

Multi-Agent System Testing (MAST) benchmarks for evaluating failure mode detection across agent frameworks.

## Structure

```
benchmarks/
├── generators/          # Trace generators for testing
│   ├── trace_generator.py           # Basic trace generation
│   ├── complex_trace_generator.py   # Multi-span complex traces
│   ├── semantic_trace_generator.py  # Semantic failure traces
│   ├── workflow_trace_generator.py  # Workflow-based traces
│   ├── adversarial_generator.py     # Adversarial test cases
│   └── fast_scaled_traces.py        # High-volume generation
├── evaluation/          # Detection evaluation
│   ├── run_all_detectors.py         # Run all F1-F16 detectors
│   ├── semantic_detector.py         # LLM-based semantic detection
│   ├── ensemble_detector.py         # Ensemble detection
│   └── evaluate_detectors.py        # Evaluation with versioning
├── frameworks/          # Framework-specific adapters
│   ├── autogen/                     # AutoGen traces
│   ├── crewai/                      # CrewAI traces
│   ├── n8n/                         # n8n workflow traces
│   ├── graph/                       # LangGraph traces
│   └── agents/                      # Generic agent traces
├── data/               # Data utilities
│   ├── detector_versioning.py       # Version tracking
│   ├── data_split.py               # Train/test splits
│   └── feature_extraction.py       # Feature engineering
├── results/            # Evaluation results
│   ├── configs/                    # Detector configurations
│   └── evaluation_history.jsonl    # Historical results
└── traces/             # Generated traces (gitignored)
```

## MAST Failure Modes (F1-F16)

| Code | Name | Category |
|------|------|----------|
| F1 | Specification Mismatch | Content |
| F2 | Poor Task Decomposition | Structural |
| F3 | Resource Misallocation | Structural |
| F4 | Inadequate Tool Provision | Structural |
| F5 | Flawed Workflow Design | Structural |
| F6 | Task Derailment | Content |
| F7 | Context Neglect | Content |
| F8 | Information Withholding | Content |
| F9 | Role Usurpation | Structural |
| F10 | Communication Breakdown | Content |
| F11 | Coordination Failure | Structural |
| F12 | Output Validation Failure | Structural |
| F13 | Quality Gate Bypass | Content |
| F14 | Completion Misjudgment | Content |
| F15 | Grounding Failure | RAG |
| F16 | Retrieval Quality Failure | RAG |

## Usage

### Generate traces
```bash
cd benchmarks
python -m generators.trace_generator
```

### Run detection
```bash
python -m evaluation.run_all_detectors
```

### Evaluate with versioning
```bash
python -m evaluation.evaluate_detectors --version 1.0
```

## Detection Results

See [DETECTION_REPORT.md](./DETECTION_REPORT.md) for current detection rates.

**Overall: 82.4%** detection rate across F1-F14 (F15-F16 TBD).
