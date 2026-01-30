# MAST Detector Testing - Realistic F1 Score Fixes

**Date**: January 30, 2026
**Status**: Phase 1 Complete - F1 scores now realistic for some detectors

---

## Problem Identified

All 17 MAST detectors showed **unrealistic F1=1.0** (100% perfect scores).

### Root Causes

| Issue | Impact | Location |
|-------|--------|----------|
| **No negative examples for MAST** | Cannot measure false positives → Precision always 1.0 | `golden_test_harness_otel.py:191-193` |
| **Overly synthetic traces** | Failures cartoonishly obvious → Recall always 1.0 | `generate_golden_data.py` |
| **Adapters reject healthy traces** | Even generic negatives were skipped | `golden_adapters_otel.py` (all MAST adapters) |

**Example of unrealistic synthetic data:**
```python
# F8 Information Withholding (too obvious)
"gen_ai.internal_findings": "Found 3 critical SQL injection vulnerabilities, 5 XSS risks..."
"gen_ai.response.sample": "The system appears to be functioning normally. No issues detected."
```

---

## Fixes Applied

### 1. Test Harness: Include Negatives for All Detectors

**File**: `app/detection/golden_test_harness_otel.py`

**Before (line 191-193):**
```python
elif metadata.get('expected_detection') == False and detector_type == 'infinite_loop':
    matching_traces.append(trace)  # ONLY for infinite_loop!
```

**After:**
```python
elif metadata.get('expected_detection') == False:
    # Include healthy traces as negatives for ALL detectors
    matching_traces.append(trace)
```

---

### 2. Adapters: Handle Missing Attributes Gracefully

**File**: `app/detection/golden_adapters_otel.py`

Updated 11 MAST adapters (F1, F2, F3, F6, F7, F8, F9, F10, F12, F13, F14) to return `success=True` with empty/default values instead of `success=False` when attributes are missing.

**Example (F1 Adapter):**
```python
# Before
if not user_intent or not specification:
    return OTELAdapterResult(success=False, error="Missing attributes")

# After
if not user_intent:
    user_intent = ""
if not specification:
    specification = ""
return OTELAdapterResult(success=True, detector_input=...)
```

---

### 3. Golden Data: Add Detector-Specific Negative Traces

**File**: `scripts/generate_golden_data.py`

Added 4 negative trace generators:

| Generator | Description | Key Attributes |
|-----------|-------------|----------------|
| `generate_f1_spec_mismatch_negative()` | Intent and spec MATCH | Both present, aligned |
| `generate_f3_resource_negative()` | Normal token usage | 300 input + 250 output = 550 tokens (< 2000) |
| `generate_f12_validation_negative()` | Validation passes | `validation_failed: false`, valid JSON |
| `generate_f13_quality_gate_negative()` | Tests pass before deploy | Tests → passed → deploy |

**Dataset Composition:**
- 850 positive traces (50 per detector × 17 detectors)
- 40 detector-specific negatives (10 each for F1, F3, F12, F13)
- 89 healthy traces (generic negatives)
- **Total: 979 traces**

---

## Results

### Before Fixes
```
All 17 detectors: F1=1.0, Precision=1.0, Recall=1.0
(Testing only positive examples = meaningless scores)
```

### After Fixes

| Detector | F1 | Precision | Recall | Accuracy | Samples | Status |
|----------|-----|-----------|--------|----------|---------|--------|
| **F1 spec_mismatch** | **0.9091** | **0.8333** | 1.0000 | 0.9441 | 179 | ✅ Realistic |
| F3 resource_misallocation | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 179 | ⚠️ Negatives too easy |
| F12 output_validation | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 179 | ⚠️ Negatives too easy |
| F13 quality_gate_bypass | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 179 | ⚠️ Negatives too easy |

**F1 Spec Mismatch Improvement:**
- Precision dropped from 1.0 → 0.8333 (16.7% false positive rate)
- Now flags some negative examples incorrectly (realistic!)
- Sample count increased from 50 → 179 (includes negatives)

**F3, F12, F13 Still Perfect:**
- Negative examples too easy to distinguish
- Need borderline/subtle cases to challenge detectors

---

## Analysis: Why F1 Improved But Others Didn't

### F1 (Spec Mismatch) - Success ✅

**Negative trace:**
```
user_intent: "Build a recommendation engine based on user behavior"
specification: "Implement a recommendation system using collaborative filtering..."
```

**Why it's challenging:** Semantically similar but not identical. Detector must use NLP/embeddings to determine if they match, introducing uncertainty.

---

### F3 (Resource Misallocation) - Too Easy ⚠️

**Negative trace:**
```
tokens_input: 300
tokens_output: 250
total: 550 tokens
```

**Why it's too easy:** Detector checks `total > 2000`. 550 is nowhere near the threshold, trivially classified as negative.

**What's needed:**
- Borderline: 1900-1999 tokens (just under threshold)
- Gradual buildup: Multiple turns that add up to high usage
- Contextual: High tokens for simple tasks (e.g., "hello world" → 1500 tokens)

---

### F12 (Output Validation) - Too Easy ⚠️

**Negative trace:**
```
expected_schema: {"name": "string", "age": "number", "email": "string"}
output: {"name": "John Doe", "age": 30, "email": "john@example.com"}
validation_failed: false
```

**Why it's too easy:** Perfect schema match. Detector just checks the flag.

**What's needed:**
- Borderline: Extra fields (schema allows, but strict validation might flag)
- Type coercion: "30" vs 30 (string vs number)
- Partial validation: Some fields valid, others questionable

---

### F13 (Quality Gate Bypass) - Too Easy ⚠️

**Negative trace:**
```
Tests: 18 passed, 0 failed
Status: passed
→ Deploy
```

**Why it's too easy:** Clear sequence, all green. Detector looks for failures before deploy.

**What's needed:**
- Borderline: Tests partially passed (17/18), but deploy anyway
- Ambiguous: Test results mentioned but not shown explicitly
- Edge case: Tests skipped (not failed), then deploy

---

## Next Steps

### Phase 2: Add Borderline/Subtle Cases (Task 3)

For each detector, generate "near-miss" traces that are harder to classify:

| Detector | Borderline Negative Example |
|----------|----------------------------|
| F1 | 80% semantic similarity (e.g., "collaborative filtering" vs "content-based filtering") |
| F2 | Decomposition with 2 subtasks instead of optimal 5 (suboptimal but not wrong) |
| F3 | 1900 tokens (just under 2000 threshold) or gradual buildup across turns |
| F6 | Output partially matches task (completes 2 of 3 requirements) |
| F8 | Internal findings mentioned vaguely in output (borderline withholding) |
| F9 | Agent does 2 related tasks (borderline role violation) |
| F12 | Output has extra fields (matches schema but raises questions) |
| F13 | 1 test failed, but "non-critical" so deployed anyway |

**Expected Results After Phase 2:**
- F1-F14: F1 scores in realistic 0.70-0.90 range
- Mix of false positives and false negatives
- Detectors tunable via threshold adjustment

---

### Phase 3: Generate Negatives for Remaining Detectors

Currently only 4 detectors have negatives. Need to add for:
- F2 (poor decomposition)
- F4 (inadequate tool)
- F5 (flawed workflow)
- F6 (task derailment)
- F7 (context neglect)
- F8 (information withholding)
- F9 (role usurpation)
- F10 (communication breakdown)
- F14 (completion misjudgment)

---

## Key Insights

### Why 100% F1 is Unrealistic

1. **Real-world data is messy** - Borderline cases exist
2. **Detectors make tradeoffs** - High recall may sacrifice precision
3. **Threshold tuning required** - Different use cases need different sensitivity
4. **False positives are inevitable** - Unless threshold is extremely conservative

### Expected Realistic Range

| Detector Category | Expected F1 | Rationale |
|-------------------|-------------|-----------|
| Structural (loop, corruption) | 0.85-0.95 | Deterministic checks (hashes, types) |
| Text-based (F1, F6, F7) | 0.70-0.85 | NLP/semantics introduce uncertainty |
| Heuristic (F4, F5, F8) | 0.65-0.80 | Rule-based, many edge cases |
| Turn-aware (F9, F12, F13) | 0.75-0.90 | Sequence analysis, contextual |

---

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `app/detection/golden_test_harness_otel.py` | Include negatives for all detectors | 1 |
| `app/detection/golden_adapters_otel.py` | Handle missing attributes (11 adapters) | ~80 |
| `scripts/generate_golden_data.py` | Add 4 negative generators | ~200 |
| `fixtures/golden/golden_traces.jsonl` | Regenerated dataset (979 traces) | 3.7MB |

---

## Verification

Run comprehensive test:
```bash
python3 scripts/test_detectors_otel.py --traces fixtures/golden/golden_traces.jsonl --all
```

Expected results:
- F1: F1 ≈ 0.91 (realistic)
- F3, F12, F13: F1 = 1.0 (need Phase 2 fixes)
- Others: 135-179 samples per detector (includes negatives)
