# Realistic PISAMA Testing - Implementation Status

## Problem Addressed

Previous test results were artificially inflated due to:
1. Only 2/8 detection types had real LLM samples
2. Synthetic samples matched detector patterns too perfectly
3. Small dataset size (24 samples/type)
4. Detectors rely on brittle regex patterns easily bypassed

## Solution Implemented

### 1. Extended Real LLM Generator ✅

Added 6 new scenario methods to `benchmarks/generators/moltbot/real_llm_generator.py`:

| Method | Detection Type | Scenario | Status |
|--------|----------------|----------|--------|
| `generate_injection_scenario()` | injection | Roleplay, meta-discussion, indirect injection | ✅ Complete |
| `generate_overflow_scenario()` | overflow | Multi-turn research with token accumulation | ✅ Complete |
| `generate_hallucination_scenario()` | hallucination | Tool contradiction, confident fabrication | ✅ Complete |
| `generate_persona_drift_scenario()` | persona_drift | Multi-channel personality switching | ✅ Complete |
| `generate_corruption_scenario()` | corruption | Conflicting state updates | ✅ Complete |
| `generate_coordination_scenario()` | coordination | Agent handoff with context loss | ✅ Complete |

### 2. Extended CLI Script ✅

Updated `benchmarks/generators/moltbot/cli_real.py` to support all 8 detection types.

**Usage:**
```bash
# Generate 10 injection samples
python benchmarks/generators/moltbot/cli_real.py --detector injection --count 10 --yes

# Generate 5 samples for each detection type (40 total)
python benchmarks/generators/moltbot/cli_real.py --detector all --count 40 --yes

# Test with specific model
python benchmarks/generators/moltbot/cli_real.py --detector hallucination --count 5 --model claude-sonnet-4-5 --yes
```

### 3. Adversarial Generator ⏳

**Status:** Not yet implemented (planned)

**Next steps:**
- Create `benchmarks/generators/moltbot/adversarial_generator.py`
- Implement evasion techniques per detector:
  - Injection: synonym substitution, encoding tricks, benign context abuse
  - Hallucination: spelled numbers, paraphrased claims, implicit citations
  - Loop: metadata injection, agent alternation, whitelist abuse
  - Completion: implicit completion, alternative markers, JSON hiding

### 4. Three-Tier Evaluation ⏳

**Status:** Not yet implemented (planned)

**Next steps:**
- Create `benchmarks/evaluation/realistic_evaluator.py`
- Implement metrics:
  - Synthetic F1 (baseline)
  - Real LLM F1 (target >0.70)
  - Adversarial F1 (target >0.50)
  - Realism gap (target <0.15)
  - Robustness drop (target <0.20)

---

## Current Capabilities

### Ready to Use

You can now generate **real LLM samples** for all 8 detection types:

```bash
# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Generate samples for detection types with NO real data yet
python benchmarks/generators/moltbot/cli_real.py --detector injection --count 50 --yes
python benchmarks/generators/moltbot/cli_real.py --detector overflow --count 40 --yes
python benchmarks/generators/moltbot/cli_real.py --detector hallucination --count 50 --yes
python benchmarks/generators/moltbot/cli_real.py --detector persona_drift --count 40 --yes
python benchmarks/generators/moltbot/cli_real.py --detector corruption --count 40 --yes
python benchmarks/generators/moltbot/cli_real.py --detector coordination --count 40 --yes
```

**Estimated cost:** ~$15 for 300 samples (310 total needed - 50+40+50+40+40+40+50)

### Sample Output Format

Each generation creates:
- `golden_real_llm_{type}_{id}.json` - Golden dataset entry
- `raw_real_llm_{type}_{id}.json` - Full Claude API response
- `golden_real_llm.jsonl` - Combined JSONL for testing

---

## Detector Brittleness Findings

From exploration analysis:

| Detector | Primary Weakness | Bypass Example |
|----------|------------------|----------------|
| **Injection** | Exact string matching | "discard earlier directives" vs "ignore instructions" |
| **Hallucination** | Regex patterns | "two thousand twenty" vs "2020" |
| **Loop** | Hash/structural checks | Add `{"iteration": N}` to break detection |
| **Completion** | Keyword-based | "deliverables produced" vs "task complete" |

---

## Next Steps

### Immediate (Phase 1)
1. ✅ Implement real LLM generators for all 8 detection types
2. ✅ Update CLI to support all types
3. ⏳ Generate 310 real LLM samples (~$15 cost)
4. ⏳ Run tests with real data to get baseline realistic F1 scores

### Short-term (Phase 2)
1. ⏳ Implement adversarial generator with evasion techniques
2. ⏳ Generate 140 adversarial samples
3. ⏳ Create three-tier evaluation framework
4. ⏳ Document F1 drops (synthetic → real → adversarial)

### Long-term (Phase 3)
1. Harden detectors based on realistic F1 scores
2. Replace brittle regex with semantic matching
3. Add adversarial training samples
4. Implement ensemble detection for high-variance types

---

## Files Modified

| File | Changes |
|------|---------|
| `benchmarks/generators/moltbot/real_llm_generator.py` | Added 6 new scenario generation methods |
| `benchmarks/generators/moltbot/cli_real.py` | Extended to support all 8 detection types |

## Files Created

| File | Purpose |
|------|---------|
| `benchmarks/REALISTIC_TESTING_STATUS.md` | This status document |

---

## Expected Results

After generating real LLM samples, we expect F1 scores to drop significantly:

| Detector | Current (Synthetic) | Expected (Real LLM) | Gap |
|----------|---------------------|---------------------|-----|
| Coordination | 1.00 | ~0.75 | -0.25 |
| Hallucination | 0.80 | ~0.65 | -0.15 |
| Loop | 0.75 | ~0.70 | -0.05 |
| Others | 0.50-0.67 | ~0.55 | Variable |

This realistic evaluation will:
- Identify which detectors need hardening
- Guide threshold tuning with real data
- Expose regex brittleness for improvement
- Provide statistically significant metrics
