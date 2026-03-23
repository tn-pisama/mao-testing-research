"""Run full detector calibration on Modal with enough memory.

Usage:
    modal run scripts/modal_calibrate.py
"""

import modal

app = modal.App("pisama-calibrate")

# Image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "numpy>=1.24",
        "scikit-learn>=1.3",
        "sentence-transformers>=2.2",
        "pydantic>=2.0",
        "pydantic-settings>=2.0",
        "anthropic>=0.25",
    )
    .add_local_dir("/Users/tuomonikulainen/mao-testing-research/backend/app", remote_path="/app/app")
    .add_local_dir("/Users/tuomonikulainen/mao-testing-research/backend/data", remote_path="/app/data")
)


@app.function(
    image=image,
    memory=16384,  # 16GB RAM
    timeout=1800,  # 30 minutes
    secrets=[modal.Secret.from_dotenv("/Users/tuomonikulainen/mao-testing-research/backend/.env")],
)
def run_calibration():
    import json
    import gc
    import os
    import sys

    sys.path.insert(0, "/app")
    os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")

    from app.detection_enterprise.calibrate import calibrate_single, _get_golden_dataset
    from app.detection_enterprise.detector_adapters import DETECTOR_RUNNERS
    from app.detection.validation import DetectionType

    ds = _get_golden_dataset()
    print(f"Dataset: {len(ds.entries)} entries")

    results = {}
    skipped = []

    for dt in DetectionType:
        entries = ds.get_entries_by_type(dt)
        runner = DETECTOR_RUNNERS.get(dt)
        if not runner or len(entries) < 3:
            skipped.append(dt.value)
            continue

        try:
            cal = calibrate_single(dt, entries)
            gc.collect()

            if cal is None:
                skipped.append(dt.value)
                continue

            tp = cal.true_positives
            tn = cal.true_negatives
            fp = cal.false_positives
            fn = cal.false_negatives
            fp_r = fp / (fp + tn) if (fp + tn) > 0 else 0
            fn_r = fn / (fn + tp) if (fn + tp) > 0 else 0

            results[dt.value] = {
                "detection_type": cal.detection_type,
                "f1": cal.f1,
                "precision": cal.precision,
                "recall": cal.recall,
                "sample_count": cal.sample_count,
                "optimal_threshold": cal.optimal_threshold,
                "true_positives": tp,
                "true_negatives": tn,
                "false_positives": fp,
                "false_negatives": fn,
                "ece": cal.ece,
                "f1_ci_lower": cal.f1_ci_lower,
                "f1_ci_upper": cal.f1_ci_upper,
                "difficulty_breakdown": getattr(cal, "difficulty_breakdown", {}),
            }

            print(f"  {dt.value:<35} F1={cal.f1:.3f} N={cal.sample_count:>4} FP={fp_r:.0%} FN={fn_r:.0%}")
        except Exception as e:
            print(f"  {dt.value:<35} ERROR: {str(e)[:80]}")
            skipped.append(dt.value)

    from datetime import datetime, timezone

    report = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "detector_count": len(results),
        "skipped": skipped,
        "splits_used": None,
        "results": results,
    }

    f1s = [r["f1"] for r in results.values()]
    print(f"\nDone: {len(results)} detectors, mean F1={sum(f1s)/len(f1s):.3f}")
    print(f"F1>=0.90: {sum(1 for f in f1s if f >= 0.90)}")
    print(f"F1>=0.70: {sum(1 for f in f1s if f >= 0.70)}")
    print(f"F1<0.70: {sum(1 for f in f1s if f < 0.70)}")
    print(f"Skipped: {len(skipped)}")

    return report


@app.local_entrypoint()
def main():
    import json

    print("Running calibration on Modal (16GB RAM)...")
    report = run_calibration.remote()

    # Save locally
    out_path = "data/calibration_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to {out_path}")

    # Print comparison with old results
    old_f1 = {
        "injection": 0.667, "communication": 0.667, "n8n_complexity": 0.681,
        "derailment": 0.688, "retrieval_quality": 0.698, "overflow": 0.706,
        "completion": 0.703, "n8n_schema": 0.762, "n8n_error": 0.765,
        "n8n_cycle": 0.783, "withholding": 0.800, "persona_drift": 0.812,
        "hallucination": 0.815, "specification": 0.815, "grounding": 0.850,
        "context": 0.865, "loop": 0.901, "coordination": 0.914,
        "corruption": 0.909, "workflow": 0.933, "convergence": 0.969,
        "decomposition": 1.000,
    }

    print(f"\n{'Detector':<35} {'New F1':>7} {'Old F1':>7} {'Change':>8}")
    print("-" * 60)
    for name, r in sorted(report["results"].items(), key=lambda x: x[1]["f1"], reverse=True):
        old = old_f1.get(name)
        if old:
            chg = r["f1"] - old
            flag = " +++" if chg > 0.05 else (" ---" if chg < -0.05 else "")
            print(f"{name:<35} {r['f1']:>7.3f} {old:>7.3f} {chg:>+8.3f}{flag}")
        else:
            print(f"{name:<35} {r['f1']:>7.3f}")
