---
name: benchmark-evaluator
description: |
  Guide running MAST benchmarks, interpreting F1 scores, and tuning detection thresholds.
  Use when evaluating detection accuracy, running benchmarks, or tuning detector parameters.
  Provides commands, interpretation guidance, and threshold tuning strategies.
allowed-tools: Read, Grep, Glob, Bash
---

# Benchmark Evaluator Skill

You are evaluating detection accuracy using the MAST benchmark. Your goal is to guide benchmark execution, interpret results, and tune detectors to achieve target accuracy.

## MAST Benchmark Overview

**MAST** (Multi-Agent System Traces) is a curated dataset of 869 traces with ground-truth failure labels across all MAST taxonomy categories (LOOP, STATE, PERSONA, COORDINATION, RESOURCE).

**Target Metrics:**
- Overall F1: ≥ 70%
- Per-category F1: ≥ 65%
- Precision: ≥ 75% (minimize false positives)
- Recall: ≥ 65% (catch most failures)

---

## Running Benchmarks

### Quick Evaluation

```bash
cd backend
pytest tests/benchmark/test_mast_evaluation.py -v
```

### Full Evaluation with Detailed Report

```bash
cd backend
python -m app.benchmark.evaluate_mast --output results.json --verbose
```

### Evaluate Specific Detector

```bash
python -m app.benchmark.evaluate_mast --detector loop --output loop_results.json
```

### Evaluate by Failure Type

```bash
python -m app.benchmark.evaluate_mast --failure-type LOOP --output loop_eval.json
python -m app.benchmark.evaluate_mast --failure-type STATE --output state_eval.json
```

---

## Interpreting Results

### Sample Output

```json
{
  "overall": {
    "precision": 0.78,
    "recall": 0.72,
    "f1": 0.75,
    "true_positives": 625,
    "false_positives": 178,
    "false_negatives": 244
  },
  "by_failure_type": {
    "LOOP": {"precision": 0.92, "recall": 0.85, "f1": 0.88},
    "STATE": {"precision": 0.75, "recall": 0.68, "f1": 0.71},
    "PERSONA": {"precision": 0.65, "recall": 0.58, "f1": 0.61},
    "COORDINATION": {"precision": 0.70, "recall": 0.75, "f1": 0.72},
    "RESOURCE": {"precision": 0.88, "recall": 0.82, "f1": 0.85}
  }
}
```

### What to Look For

1. **F1 Score < Target (0.70)**
   - If precision high but recall low → detector too conservative, missing failures
   - If recall high but precision low → detector too aggressive, false positives
   - If both low → detector fundamentally needs improvement

2. **Per-Type Performance**
   - LOOP should be easiest (target F1 > 0.85) - pattern-based
   - PERSONA often hardest (target F1 > 0.60) - semantic
   - STATE and COORDINATION (target F1 > 0.70)
   - RESOURCE should be straightforward (target F1 > 0.80) - quantitative

3. **False Positive Analysis**
   - Review `false_positives` list in output
   - Identify patterns in FPs (are they all one subcategory?)
   - Check if FPs are actually correct (ground truth may be wrong)

4. **False Negative Analysis**
   - Review `false_negatives` list
   - Check detector threshold (may be too high)
   - Check if detector even has logic for this failure subtype

---

## Threshold Tuning

### General Strategy

Each detector has a `confidence_threshold` parameter (default 0.9):
- Higher threshold (0.95-0.99) → More conservative, fewer FPs
- Lower threshold (0.70-0.85) → More sensitive, higher recall

### Per-Detector Tuning

**Loop Detector (backend/app/detection/loop.py):**
```python
class LoopDetectorConfig:
    exact_match_threshold: float = 0.95  # For LOOP-001
    structural_similarity_threshold: float = 0.90  # For LOOP-002
    semantic_similarity_threshold: float = 0.85  # For LOOP-003
    min_occurrences: int = 3  # Minimum repetitions to trigger
```

**Tuning guidance:**
- If missing subtle loops → lower `semantic_similarity_threshold` to 0.80
- If too many FPs on similar-but-different messages → raise to 0.90
- If catching 2-iteration loops unnecessarily → increase `min_occurrences` to 4

**State Corruption Detector (backend/app/detection/corruption.py):**
```python
class CorruptionDetectorConfig:
    consistency_threshold: float = 0.95  # Internal consistency check
    validation_strictness: float = 0.90  # Schema validation
```

**Tuning guidance:**
- If missing edge cases → lower `consistency_threshold` to 0.90
- If flagging valid but unusual states → raise `validation_strictness` to 0.95

**Persona Detector (backend/app/detection/persona.py):**
```python
class PersonaDetectorConfig:
    drift_threshold: float = 0.75  # How different from persona
    embedding_similarity: float = 0.85  # Semantic comparison
```

**Tuning guidance:**
- Persona is hardest to tune - start with lower thresholds (0.70-0.75)
- Collect false positives, adjust based on patterns
- May need different thresholds per persona type

### Iterative Tuning Process

1. **Run baseline** (`pytest tests/benchmark/` - record F1)
2. **Identify weakest detector** (lowest per-type F1)
3. **Analyze FPs and FNs** for that detector
4. **Adjust ONE threshold** (make small change, ±0.05)
5. **Re-run benchmark** - measure impact
6. **Repeat** until target F1 achieved

**Golden Rule:** Tune one detector at a time. Changing multiple simultaneously makes it impossible to attribute improvements.

---

## Common Issues and Fixes

### Issue: Overall F1 < 0.70

**Diagnosis:**
```bash
python -m app.benchmark.evaluate_mast --verbose --output detailed.json
# Review detailed.json for per-detector breakdown
```

**Fix Strategy:**
1. Identify 2-3 weakest detectors (lowest F1)
2. Focus tuning efforts there first
3. Low-hanging fruit: adjust thresholds by ±0.05
4. If threshold tuning insufficient, may need detector logic changes

---

### Issue: High Precision (>0.80) but Low Recall (<0.60)

**Diagnosis:** Detector is too conservative, missing failures.

**Fix:**
- Lower `confidence_threshold` by 0.05-0.10
- Check if detector has logic for all failure subtypes
- Review false negatives - are they edge cases?

**Example:**
```python
# Before
PersonaDetectorConfig(drift_threshold=0.85)

# After
PersonaDetectorConfig(drift_threshold=0.75)  # More sensitive
```

---

### Issue: High Recall (>0.80) but Low Precision (<0.65)

**Diagnosis:** Detector too aggressive, many false positives.

**Fix:**
- Raise `confidence_threshold` by 0.05-0.10
- Add additional validation checks
- Review false positives for patterns

**Example:**
```python
# Before
LoopDetectorConfig(min_occurrences=2)

# After
LoopDetectorConfig(min_occurrences=3)  # Require more repetitions
```

---

### Issue: One Failure Type F1 << Others

**Diagnosis:** Specific detector needs attention.

**Fix:**
- Isolate that detector: `pytest tests/detection/test_{detector}.py`
- Review detector logic for that failure type
- Check if ground truth labels are correct
- May need detector algorithm changes, not just threshold tuning

---

## Benchmark Workflow Checklist

- [ ] Run baseline evaluation (`pytest tests/benchmark/`)
- [ ] Record baseline F1 scores (overall + per-type)
- [ ] Identify weakest 2-3 detectors
- [ ] Analyze FPs and FNs for those detectors
- [ ] Tune ONE threshold at a time
- [ ] Re-run benchmark after each change
- [ ] Document threshold changes in detector config
- [ ] When F1 ≥ 0.70, commit changes
- [ ] Update benchmark results in `docs/BENCHMARK_RESULTS.md`

---

## Resources

For detailed benchmark commands and scripts:
- `resources/benchmark-commands.md` - Full command reference
- `backend/tests/benchmark/` - Benchmark test suite
- `backend/app/benchmark/evaluate_mast.py` - Evaluation script

### External References

**Bloom** - https://github.com/safety-research/bloom
- Automated behavioral evaluation pipeline with reproducible test generation
- 4-stage process: Understanding → Ideation → Rollout → Judgment
- Multi-model comparison for testing detectors across different configurations
- Variation dimensions for testing edge cases (noise, pressure, etc.)

**Anthropic Evals** - https://github.com/anthropics/evals
- Model-written evaluation datasets for behavioral testing
- Sycophancy, persona, and dangerous goal pursuit patterns
- Methodology for expanding MAST taxonomy with new failure modes
- Reference datasets for validating detection algorithms
- `docs/BENCHMARK_RESULTS.md` - Historical results
