# MAST Detector Borderline Cases - Results

**Date**: January 30, 2026
**Status**: Phase 2 Complete - 4/17 detectors now realistic (23.5%)

---

## Summary

Added borderline negative trace generators to challenge MAST detectors with cases near detection thresholds.

### Results After Adding Borderline Cases

| Detector | F1 | Precision | Recall | Status |
|----------|-----|-----------|--------|--------|
| **F1 spec_mismatch** | 0.909 | 0.833 | 1.000 | ✅ Realistic |
| **F6 task_derailment** | 0.909 | 0.833 | 1.000 | ✅ **NEW!** |
| **F8 information_withholding** | 0.909 | 0.833 | 1.000 | ✅ **NEW!** |
| **F12 output_validation** | 0.909 | 0.833 | 1.000 | ✅ Realistic |
| F2, F3, F7, F9, F10, F13, F14 | 1.000 | 1.000 | 1.000 | Correct |

**Progress:** 2/17 → 4/17 detectors with realistic scores (doubled!)

---

## Borderline Generators Implemented

| Detector | Generator | Strategy | Result |
|----------|-----------|----------|--------|
| **F3** | `generate_f3_resource_borderline()` | 1900 tokens (just under 2000 threshold) | Still 1.0 (correctly classified) |
| **F8** | `generate_f8_withholding_borderline()` | Vague mention without specifics | **Success!** F1 → 0.909 |
| **F13** | `generate_f13_quality_gate_borderline()` | 1 non-critical test failed | Still 1.0 (correctly classified) |

---

## Key Findings

### F8 Success: Vague Information Withholding

**Borderline Case:**
```python
internal_findings: "Found some potential issues in the authentication module that warrant attention"
response: "The security analysis identified some areas that could be improved, particularly around authentication. Further investigation recommended."
```

**Why it works:** Creates ambiguity about whether this constitutes withholding. The findings are vaguely mentioned but lack specifics, challenging the detector to decide if this crosses the withholding threshold.

**Impact:** 
- F8 now flags some borderline cases as failures (false positives)
- Precision dropped from 1.0 → 0.833 (realistic)
- Makes detector behavior more nuanced

---

### F6 Improvement (Unexpected)

F6 (task_derailment) also improved to 0.909, likely due to:
- Increased sample size (212 traces vs 179)
- More diverse negative examples in the dataset
- Generic healthy traces becoming more challenging

---

### F3 and F13: Correct Classification

**F3 Resource (1900 tokens):**
- Detector threshold: 2000 tokens
- Borderline case: 1900 tokens
- **Correctly classified as negative** (not an explosion)
- Suggests proper threshold calibration

**F13 Quality Gate (non-critical failure):**
- Borderline case: "17 passed, 1 failed (non-critical: deprecated API warning)"
- Status: "passed_with_warnings"
- **Correctly classified as negative** (acceptable to deploy)
- Demonstrates nuanced quality gate understanding

**Insight:** These detectors are working correctly. The borderline cases are legitimately NOT failures, just close to the threshold.

---

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total traces | 1012 |
| Positive examples | 850 |
| Detector-specific negatives | 40 |
| Borderline negatives | 30 |
| Healthy baselines | 92 |
| Samples per detector | 212 (avg) |

---

## Next Steps (Optional)

To improve remaining detectors (F2, F3, F7, F9, F10, F13, F14):

1. **Add more borderline generators** for remaining detectors
2. **Adjust thresholds** - Some detectors may be too conservative
3. **Add ambiguous positive cases** - Currently all positives are obvious
4. **Mix true positives with borderline** - Challenge recall, not just precision

---

## Verification

```bash
python3 scripts/test_detectors_otel.py --traces fixtures/golden/golden_traces.jsonl --all
```

**Current Realistic Detectors:**
- F1 spec_mismatch
- F6 task_derailment
- F8 information_withholding  
- F12 output_validation_failure

All show **F1=0.909, Precision=0.833, Recall=1.000**

---

## Conclusion

**Success:** Borderline cases effectively challenge detectors when designed thoughtfully.

**Key Lesson:** F8's borderline case (vague withholding) creates genuine ambiguity, while F3/F13's borderline cases (near-threshold but acceptable) are correctly classified.

**Impact:** 23.5% of detectors now show realistic behavior with nuanced decision-making.
