"""Evaluate NLI-based entailment checker against rule-based detectors.

Compares DeBERTa-v3-MNLI grounding check with existing hallucination and
grounding detectors on real golden dataset entries.
"""

import gc
import os
import random
import sys

os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
sys.path.insert(0, "/Users/tuomonikulainen/mao-testing-research/backend")

from app.detection.nli_checker import check_grounding
from app.detection_enterprise.calibrate import _get_golden_dataset
from app.detection_enterprise.detector_adapters import DETECTOR_RUNNERS
from app.detection_enterprise.golden_dataset import GoldenDataset
from app.detection.validation import DetectionType

# Load real data only (skip LLM-generated)
print("Loading golden dataset...")
full_ds = _get_golden_dataset()
real_ds = GoldenDataset()
for eid, entry in full_ds.entries.items():
    if entry.source and ("real" in entry.source or "structural" in entry.source):
        real_ds.entries[eid] = entry
del full_ds
gc.collect()
print(f"Loaded {len(real_ds.entries)} real entries")

random.seed(42)

# Test on hallucination and grounding
for det_name in ["hallucination", "grounding"]:
    dt = DetectionType(det_name)
    entries = real_ds.get_entries_by_type(dt)
    runner = DETECTOR_RUNNERS.get(dt)

    # Balance positive/negative
    pos = [e for e in entries if e.expected_detected]
    neg = [e for e in entries if not e.expected_detected]
    sample = random.sample(pos, min(15, len(pos))) + random.sample(neg, min(15, len(neg)))

    print(f"\n{'='*60}")
    print(f"Detector: {det_name} ({len(pos)} pos, {len(neg)} neg total, {len(sample)} sampled)")
    print(f"{'='*60}")

    rule_tp = rule_fp = rule_fn = rule_tn = 0
    nli_tp = nli_fp = nli_fn = nli_tn = 0

    for i, e in enumerate(sample):
        expected = e.expected_detected

        # Rule-based
        try:
            det, conf = runner(e)
            if det and expected:
                rule_tp += 1
            elif det and not expected:
                rule_fp += 1
            elif not det and expected:
                rule_fn += 1
            else:
                rule_tn += 1
        except Exception:
            if expected:
                rule_fn += 1
            else:
                rule_tn += 1

        # NLI-based
        output = e.input_data.get("output", e.input_data.get("agent_output", ""))
        sources = e.input_data.get("sources", e.input_data.get("source_documents", []))
        if isinstance(sources, str):
            sources = [sources]
        sources = [
            s if isinstance(s, str) else s.get("content", str(s))
            for s in sources
        ]

        if output and sources:
            nli_det, nli_conf, details = check_grounding(output, sources)
            if nli_det and expected:
                nli_tp += 1
            elif nli_det and not expected:
                nli_fp += 1
            elif not nli_det and expected:
                nli_fn += 1
            else:
                nli_tn += 1

            # Print per-sample detail
            tag = "TP" if (nli_det and expected) else "FP" if (nli_det and not expected) else "FN" if (not nli_det and expected) else "TN"
            print(f"  [{i+1:2d}] expected={expected} nli_det={nli_det} nli_conf={nli_conf:.2f} -> {tag}")
        else:
            if expected:
                nli_fn += 1
            else:
                nli_tn += 1
            print(f"  [{i+1:2d}] expected={expected} -> SKIP (no output/sources)")

    def f1(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0
        return 2 * p * r / (p + r) if (p + r) > 0 else 0

    def precision(tp, fp):
        return tp / (tp + fp) if (tp + fp) > 0 else 0

    def recall(tp, fn):
        return tp / (tp + fn) if (tp + fn) > 0 else 0

    rf1 = f1(rule_tp, rule_fp, rule_fn)
    nf1 = f1(nli_tp, nli_fp, nli_fn)
    chg = nf1 - rf1

    print(f"\n  Rule-based: P={precision(rule_tp, rule_fp):.3f} R={recall(rule_tp, rule_fn):.3f} F1={rf1:.3f}  [TP={rule_tp} FP={rule_fp} FN={rule_fn} TN={rule_tn}]")
    print(f"  NLI-based:  P={precision(nli_tp, nli_fp):.3f} R={recall(nli_tp, nli_fn):.3f} F1={nf1:.3f}  [TP={nli_tp} FP={nli_fp} FN={nli_fn} TN={nli_tn}]")
    print(f"  Delta F1: {chg:+.3f}")
    if chg > 0:
        print(f"  -> NLI IMPROVES F1 by {chg:.3f}")
    elif chg < 0:
        print(f"  -> Rule-based is better by {abs(chg):.3f}")
    else:
        print(f"  -> Tied")

print("\nDone.")
