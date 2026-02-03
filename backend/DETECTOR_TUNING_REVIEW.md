# Detector Tuning Review

**Date**: 2026-02-02
**Tasks**: PIS-W1-2-B-003 (Tune 6 conservative detectors), PIS-W1-2-B-004 (Fix F8, F10 adapters)

## Summary

Reviewed 6 conservative detectors and fixed F10 adapter multi-message handling. All detectors currently achieve F1=1.0 on existing test data.

---

## Fixed Issues

### PIS-W1-2-B-004: F10 Adapter Fix ✅

**Problem**: F10 Communication Breakdown detector only checked first 2 messages, missing breakdowns in longer traces.

**Fix**: Modified `_run_f10_communication()` in `golden_test_harness_otel.py` to check all sequential message pairs.

**Implementation**:
```python
# Before: Only checked messages[0] and messages[1]
# After: Loops through all pairs
for i in range(len(messages) - 1):
    sender_msg = messages[i]
    receiver_msg = messages[i + 1]
    result = detector.detect(...)
    if result.detected:
        all_detections.append(result)
```

**Verification**: All 38 communication tests pass.

---

## PIS-W1-2-B-003: Conservative Detector Review

### Current Threshold Settings

| Detector | File | Key Parameters | Status |
|----------|------|----------------|--------|
| **F2** Poor Decomposition | `turn_aware/task_decomposition.py` | `min_steps_for_complex=3`<br>`max_vague_ratio=0.3` | ✅ Tuned |
| **F3** Resource Misallocation | `turn_aware/resource.py` | `min_turns=2`<br>`min_issues_to_flag=1` (was 2)<br>`token_explosion_threshold=2000` | ✅ Tuned |
| **F9** Role Usurpation | `turn_aware/role_usurpation.py` | `min_turns=2` (was 3)<br>`min_violations=1`<br>Returns `confidence=0.50` for LLM escalation | ✅ Tuned |
| **F12** Output Validation | `turn_aware/output_validation.py` | `min_turns=2`<br>`min_issues_to_flag=3` (raised to reduce 17.8% FPR) | ✅ Tuned |
| **F13** Quality Gate Bypass | `turn_aware/quality_gate.py` | `min_turns=2`<br>`min_issues_to_flag=1` (lowered from 2) | ✅ Tuned |
| **State Corruption** | `corruption.py` | Domain validators for type drift<br>`_detect_type_drift()` method added | ✅ Tuned |

### Tuning History

Based on `backend/MAST_TUNING_STATUS.md`:

**Previously Too Conservative (Now Fixed)**:
1. **F2**: Threshold tuned for better precision
2. **F3**: `min_issues_to_flag` lowered from 2 to 1 for token explosion detection
3. **F9**: `min_turns` lowered from 3 to 2, added multi-task boundary detection
4. **F12**: `min_issues_to_flag` raised to 3 (was causing 17.8% FP rate at lower values)
5. **F13**: `min_issues_to_flag` lowered from 2 to 1 for better recall
6. **state_corruption**: Added `_detect_type_drift()` method to catch structural changes

### Current F1 Scores

All detectors achieve **F1=1.0** (perfect) on existing test data after tuning.

---

## Remaining Work

### 1. Add Negative Test Traces (Medium Priority)

Current F1=1.0 may be unrealistic due to lack of challenging negative examples.

**Needed negative traces**:

| Detector | Negative Case Description |
|----------|---------------------------|
| F2 | Well-decomposed complex task (clear steps, no vagueness) |
| F3 | Appropriate resource allocation (agents have needed tools, balanced workload) |
| F9 | Agents respecting role boundaries (no role usurpation) |
| F12 | Proper output validation (validation gates working correctly) |
| F13 | Quality gates enforced (no bypasses, proper checks) |
| state_corruption | Clean state transitions (no type drift, valid values) |
| F8 | Agent shares all relevant information (no withholding) |
| F10 | Clear communication with acknowledgments (no breakdowns) |

**Location**: Create in `backend/tests/fixtures/` or equivalent.

### 2. Validate Thresholds with Realistic Data

Once negative traces are added:
1. Run full MAST benchmark
2. Check if F1 scores remain ≥0.90
3. Adjust thresholds if needed (may need to increase `min_issues_to_flag` or tighten similarity thresholds)

### 3. F8 Withholding Detector (Lower Priority)

F8 currently functions correctly but could benefit from:
- Turn-aware version integration (currently uses standalone detector)
- Additional negative traces for realistic testing

---

## Recommendations

### Short Term (This Week)
1. ✅ Commit F10 multi-message fix
2. ✅ Document current threshold settings
3. Update Google Sheet tasks to "Done"

### Medium Term (Next Sprint)
1. Create negative test traces for F2, F3, F9, F12, F13
2. Add F8, F10 negative traces
3. Re-run benchmarks with realistic data
4. Adjust thresholds if F1 drops below 0.90

### Long Term
1. Implement automated threshold tuning based on production data
2. Add A/B testing framework for detector configurations
3. Build feedback loop from false positives/negatives in production

---

## Verification Commands

```bash
# Test F10 communication breakdown
pytest backend/tests/test_communication.py -xvs

# Test all turn-aware detectors
pytest backend/tests/test_turn_aware_detectors_f1_f14.py -xvs

# Run full detection suite
pytest backend/tests/ -k "detection" --tb=short
```

---

## References

- `backend/MAST_TUNING_STATUS.md` - Detailed tuning history
- `backend/MAST_TEST_SUMMARY.md` - Test results summary
- `backend/REALISTIC_TESTING_FIXES.md` - Phase 3 plan for negative traces
- `backend/app/detection/turn_aware/` - Turn-aware detector implementations
