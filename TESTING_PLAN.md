# MAO Testing Platform - Comprehensive Testing Plan

## Executive Summary

This plan validates the MAO Testing Platform detection algorithms using:
1. **Internal synthetic data** - Phase 1/2 benchmarks, existing trace files
2. **PISAMA Claude Code traces** - Real Claude Code session captures
3. **External benchmarks** - UC Berkeley MAST-Data, ToolBench, API-Bank, AgentHarm

**Target Metrics:**
- Phase 1 Synthetic: >85% accuracy
- Phase 2 Adversarial: >70% accuracy (currently 81.8%)
- MAST-Data cross-validation: >70% F1-score
- Real trace detection: <10% false positive rate

---

## Phase 1: Internal Synthetic Data Testing

### 1.1 Existing Trace Inventory
| Category | Files | Frameworks |
|----------|-------|------------|
| By Framework | 14 files | LangChain, AutoGen, CrewAI, LangGraph, OpenAI, Anthropic, React |
| By Type | 12 files | Task execution, Benchmark, Code execution, OTEL traces |
| By Source | Multiple | Anthropic, LangSmith, AgentBench |

### 1.2 Test Execution
```bash
# Run Phase 1 synthetic evaluation (all failure modes)
python benchmarks/evaluation/phase1_synthetic_eval.py

# Run Phase 2 adversarial evaluation
python benchmarks/evaluation/phase2_adversarial_eval.py

# Run detector unit tests
pytest backend/tests/test_mast_detectors.py -v
```

### 1.3 Success Criteria
- [ ] Phase 1: All 14 failure modes (F1-F16) tested
- [ ] Phase 1: Overall accuracy >85%
- [ ] Phase 2: Adversarial accuracy >70%
- [ ] Unit tests: 100% pass rate

---

## Phase 2: MAST-Data Integration (UC Berkeley)

### 2.1 Dataset Overview
- **Source**: [HuggingFace mcemri/MAST-Data](https://huggingface.co/datasets/mcemri/MAST-Data)
- **Size**: 1,600+ annotated traces
- **Labels**: 14 failure modes (aligns with our taxonomy!)
- **Frameworks**: MetaGPT, ChatDev, HyperAgent, OpenManus, AppWorld, Magentic, AG2
- **Agreement**: Inter-annotator kappa = 0.88

### 2.2 Taxonomy Mapping
| MAST-Data Label | MAO Detector |
|-----------------|--------------|
| System Design Issues | F1-F5 (Specification, Decomposition, Resource, Tool, Workflow) |
| Inter-Agent Misalignment | F6-F11 (Derailment, Context, Withholding, Usurpation, Communication, Coordination) |
| Task Verification | F12-F14 (Validation, Quality, Completion) |

### 2.3 Test Execution
```python
from huggingface_hub import hf_hub_download
import json

# Download MAST dataset
file_path = hf_hub_download(
    repo_id="mcemri/MAD",
    filename="MAD_full_dataset.json",
    repo_type="dataset"
)

# Load and run detection
with open(file_path, "r") as f:
    mast_data = json.load(f)

# Run MAO detectors against MAST traces
# Compare predictions vs ground truth labels
```

### 2.4 Success Criteria
- [ ] Successfully download and parse MAST-Data
- [ ] Map MAST failure labels to MAO failure modes
- [ ] Achieve >70% F1-score on labeled failures
- [ ] Document false positive/negative patterns

---

## Phase 3: PISAMA Claude Code Real Traces

### 3.1 Trace Capture Setup
```bash
# Install pisama-claude-code
pip install pisama-claude-code

# Install hooks for trace capture
pisama-cc install

# Check status
pisama-cc status

# View captured traces
pisama-cc traces --last 10
```

### 3.2 Test Scenarios
1. **Happy Path**: Complete a simple coding task successfully
2. **Loop Detection**: Create a task that causes repetitive behavior
3. **Context Neglect**: Multi-step task where context is lost
4. **Task Derailment**: Ask for X, agent does Y
5. **Completion Misjudgment**: Partial completion declared as done

### 3.3 Trace Conversion
```bash
# Export traces for analysis
pisama-cc export --format jsonl --output traces/claude_sessions.jsonl

# Convert to MAO format
python -m pisama_claude_code.trace_converter traces/claude_sessions.jsonl
```

### 3.4 Success Criteria
- [ ] Successfully capture 10+ Claude Code sessions
- [ ] Convert traces to MAO-compatible format
- [ ] Run detection algorithms on real traces
- [ ] <10% false positive rate on known-good sessions

---

## Phase 4: External Benchmarks

### 4.1 ToolBench (Tool Calling)
- **Source**: [OpenBMB/ToolBench](https://github.com/OpenBMB/ToolBench)
- **Size**: 16,464 APIs, 126,486 instruction pairs
- **Focus**: Tool provision (F4), Tool misuse detection

```bash
# Clone ToolBench
git clone https://github.com/OpenBMB/ToolBench.git external/toolbench

# Extract test cases with known failures
python scripts/extract_toolbench_failures.py
```

### 4.2 API-Bank (API Call Validation)
- **Source**: [arxiv:2304.08244](https://arxiv.org/abs/2304.08244)
- **Size**: 753 annotated API calls
- **Focus**: Tool calling accuracy, F4 detection

### 4.3 AgentHarm (Safety/Adversarial)
- **Source**: [HuggingFace ai-safety-institute/AgentHarm](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)
- **Size**: 440 tasks, 11 harm categories
- **Focus**: Adversarial robustness, safety detection

### 4.4 Success Criteria
- [ ] Process ToolBench failure cases
- [ ] Test F4 (Tool Provision) detector accuracy
- [ ] Process AgentHarm dataset
- [ ] Document coverage gaps

---

## Phase 5: Cross-Validation Report

### 5.1 Metrics to Collect
| Metric | Formula | Target |
|--------|---------|--------|
| Precision | TP / (TP + FP) | >80% |
| Recall | TP / (TP + FN) | >75% |
| F1-Score | 2 * (P * R) / (P + R) | >77% |
| False Positive Rate | FP / (FP + TN) | <10% |
| Accuracy | (TP + TN) / Total | >80% |

### 5.2 Per-Detector Analysis
For each F1-F14 detector:
- Precision/Recall on synthetic data
- Precision/Recall on MAST-Data
- Precision/Recall on real traces
- Common failure patterns

### 5.3 Report Template
```
## Detection Accuracy Report

### Overall Results
- Internal Synthetic: X% accuracy
- MAST-Data Cross-validation: X% F1
- Real Traces: X% accuracy, Y% FPR

### Per-Detector Results
| Detector | Synthetic | MAST | Real | Notes |
|----------|-----------|------|------|-------|
| F1 | X% | X% | X% | ... |
| ... | ... | ... | ... | ... |

### Recommendations
1. ...
2. ...
```

---

## Execution Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Internal | 1 hour | None |
| Phase 2: MAST-Data | 2 hours | HuggingFace access |
| Phase 3: Real Traces | 2 hours | pisama-cc installed |
| Phase 4: External | 2 hours | Dataset downloads |
| Phase 5: Report | 1 hour | Phases 1-4 complete |

**Total Estimated Time**: 8 hours

---

## Quick Start

```bash
# Run all tests
./scripts/run_comprehensive_tests.sh

# Or step by step:
# 1. Internal tests
python benchmarks/evaluation/phase1_synthetic_eval.py
python benchmarks/evaluation/phase2_adversarial_eval.py

# 2. MAST-Data
python scripts/test_mast_data.py

# 3. Real traces
pisama-cc traces --analyze

# 4. External benchmarks
python scripts/test_external_benchmarks.py

# 5. Generate report
python scripts/generate_test_report.py
```
