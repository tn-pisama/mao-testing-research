#!/usr/bin/env python3
"""Evaluate LLM judge vs rule-based detectors on real golden dataset entries.

Runs the 12 non-production detectors on real data using both the rule-based
detector and the LLM judge, then compares F1 scores to identify where the
LLM judge adds value.

Cost estimate: ~600 entries * ~500 tokens avg = 300K tokens ~ $2 total (Haiku).

Usage:
    cd ~/mao-testing-research/backend
    python scripts/run_llm_judge_eval.py
"""

import os
import sys
import json
import time
import gc
import logging

# ---------------------------------------------------------------------------
# Environment setup (must happen before any app imports)
# ---------------------------------------------------------------------------
os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
sys.path.insert(0, "/Users/tuomonikulainen/mao-testing-research/backend")

# Load .env for ANTHROPIC_API_KEY
from pathlib import Path

env_path = Path("/Users/tuomonikulainen/mao-testing-research/backend/.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App imports
# ---------------------------------------------------------------------------
from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
from app.detection_enterprise.calibrate import _get_golden_dataset
from app.detection_enterprise.detector_adapters import (
    DETECTOR_RUNNERS,
    _entry_to_llm_prompt,
)

# ---------------------------------------------------------------------------
# Target detectors: non-production or improvable
# ---------------------------------------------------------------------------
TARGETS = {
    "convergence": 0.696,
    "withholding": 0.690,
    "communication": 0.667,
    "hallucination": 0.654,
    "specification": 0.644,
    "derailment": 0.639,
    "completion": 0.716,
    "retrieval_quality": 0.479,
    "grounding": 0.422,
    "n8n_timeout": 0.381,
    "n8n_schema": 0.333,
    "context": 0.702,
}

MAX_ENTRIES_PER_DETECTOR = 50


def _compute_f1(predictions: list, ground_truths: list, threshold: float = 0.0) -> dict:
    """Compute precision, recall, F1 from (detected, confidence) predictions."""
    tp = fp = fn = tn = 0
    for (detected, confidence), expected in zip(predictions, ground_truths):
        predicted_pos = detected and confidence >= threshold
        if expected and predicted_pos:
            tp += 1
        elif expected and not predicted_pos:
            fn += 1
        elif not expected and predicted_pos:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "f1": round(f1, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def _find_optimal_threshold(predictions: list, ground_truths: list) -> tuple:
    """Grid search for optimal confidence threshold."""
    best_f1 = 0.0
    best_thresh = 0.0
    for t in [round(0.05 + i * 0.05, 2) for i in range(18)]:
        metrics = _compute_f1(predictions, ground_truths, threshold=t)
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_thresh = t
    return best_thresh, best_f1


def main():
    print("=" * 78)
    print("LLM Judge Evaluation: Rule-Based vs LLM Judge on Real Data")
    print("=" * 78)

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\nERROR: No ANTHROPIC_API_KEY found. Skipping LLM judge evaluation.")
        print("Set it in .env or environment to run the full evaluation.")
        sys.exit(1)

    # Initialize LLM judge (same one used by tiered detection)
    try:
        from app.enterprise.evals.llm_judge import LLMJudge, JudgeModel
        from app.enterprise.evals.scorer import EvalType
    except ImportError as e:
        print(f"\nERROR: Could not import LLM judge: {e}")
        sys.exit(1)

    judge = LLMJudge(model=JudgeModel.CLAUDE_HAIKU)
    if not judge.is_available:
        print("\nERROR: LLM judge reports not available (API key issue).")
        sys.exit(1)

    print(f"\nLLM Judge model: {judge.model.value}")
    print(f"API key: ...{api_key[-8:]}")

    # Load golden dataset (real + structural entries only)
    print("\nLoading golden dataset...")
    dataset = _get_golden_dataset()
    total_entries = len(dataset.entries)
    print(f"Total entries in golden dataset: {total_entries}")

    # Filter to real/structural sources only
    real_sources = {"real", "structural", "mast_benchmark", "swe_bench", "real_trace",
                    "n8n_production", "production", "external"}

    results = []
    total_cost = 0.0
    total_llm_calls = 0

    for det_name, baseline_f1 in TARGETS.items():
        try:
            det_type = DetectionType(det_name)
        except ValueError:
            print(f"\n  SKIP {det_name}: not in DetectionType enum")
            continue

        if det_type not in DETECTOR_RUNNERS:
            print(f"\n  SKIP {det_name}: no detector runner available")
            continue

        runner = DETECTOR_RUNNERS[det_type]

        # Get entries for this detector
        all_entries = dataset.get_entries_by_type(det_type)
        if not all_entries:
            print(f"\n  SKIP {det_name}: no golden dataset entries")
            continue

        # Prefer real-sourced entries, fall back to all entries
        real_entries = [
            e for e in all_entries
            if any(rs in (e.source or "").lower() for rs in real_sources)
        ]

        # If few real entries, include all entries
        if len(real_entries) < 10:
            entries = all_entries[:MAX_ENTRIES_PER_DETECTOR]
            source_note = f"all ({len(real_entries)} real)"
        else:
            entries = real_entries[:MAX_ENTRIES_PER_DETECTOR]
            source_note = "real"

        n_pos = sum(1 for e in entries if e.expected_detected)
        n_neg = len(entries) - n_pos
        print(f"\n{'─' * 78}")
        print(f"  {det_name} ({len(entries)} entries: {n_pos}+/{n_neg}-, source={source_note})")
        print(f"{'─' * 78}")

        # Run rule-based detector on all entries
        rule_preds = []
        ground_truths = []
        for entry in entries:
            try:
                detected, confidence = runner(entry)
                rule_preds.append((detected, confidence))
            except Exception as exc:
                # Detector error -> treat as no detection
                rule_preds.append((False, 0.0))
                logger.debug(f"  Rule detector error on {entry.id}: {exc}")
            ground_truths.append(entry.expected_detected)

        # Find best rule-based threshold
        rule_thresh, _ = _find_optimal_threshold(rule_preds, ground_truths)
        rule_metrics = _compute_f1(rule_preds, ground_truths, threshold=rule_thresh)

        print(f"  Rule-based: F1={rule_metrics['f1']:.3f} P={rule_metrics['precision']:.3f} "
              f"R={rule_metrics['recall']:.3f} (thresh={rule_thresh}) "
              f"[TP={rule_metrics['tp']} FP={rule_metrics['fp']} FN={rule_metrics['fn']} TN={rule_metrics['tn']}]")

        # Run LLM judge on all entries
        llm_preds = []
        det_cost = 0.0
        det_llm_calls = 0
        errors = 0

        for i, entry in enumerate(entries):
            rule_det, rule_conf = rule_preds[i]
            prompt = _entry_to_llm_prompt(entry, det_name, rule_det, rule_conf)

            try:
                result = judge.judge(
                    eval_type=EvalType.SAFETY,
                    output="",
                    custom_prompt=prompt,
                )
                score = result.score
                det_cost += result.cost_usd
                det_llm_calls += 1

                # LLM score > 0.5 means detected
                llm_preds.append((score > 0.5, score))

                if (i + 1) % 10 == 0:
                    print(f"    ... processed {i + 1}/{len(entries)} entries (${det_cost:.3f})")

            except Exception as exc:
                errors += 1
                # On error, fall back to rule-based prediction
                llm_preds.append(rule_preds[i])
                logger.debug(f"  LLM judge error on {entry.id}: {exc}")

            # Brief pause to avoid rate limiting
            if det_llm_calls % 20 == 0:
                time.sleep(0.5)

        # Find best LLM threshold
        llm_thresh, _ = _find_optimal_threshold(llm_preds, ground_truths)
        llm_metrics = _compute_f1(llm_preds, ground_truths, threshold=llm_thresh)

        print(f"  LLM judge:  F1={llm_metrics['f1']:.3f} P={llm_metrics['precision']:.3f} "
              f"R={llm_metrics['recall']:.3f} (thresh={llm_thresh}) "
              f"[TP={llm_metrics['tp']} FP={llm_metrics['fp']} FN={llm_metrics['fn']} TN={llm_metrics['tn']}]")
        if errors:
            print(f"  LLM errors: {errors}")

        # Combined strategy: use rule-based, then escalate gray zone to LLM
        combined_preds = []
        gray_lo, gray_hi = 0.20, 0.80  # default gray zone
        escalated = 0
        for i, entry in enumerate(entries):
            rule_det, rule_conf = rule_preds[i]
            llm_det, llm_score = llm_preds[i]

            # In gray zone -> use LLM judgment
            if gray_lo <= rule_conf <= gray_hi:
                combined_preds.append((llm_det, llm_score))
                escalated += 1
            else:
                combined_preds.append((rule_det, rule_conf))

        combo_thresh, _ = _find_optimal_threshold(combined_preds, ground_truths)
        combo_metrics = _compute_f1(combined_preds, ground_truths, threshold=combo_thresh)

        print(f"  Combined:   F1={combo_metrics['f1']:.3f} P={combo_metrics['precision']:.3f} "
              f"R={combo_metrics['recall']:.3f} (thresh={combo_thresh}, escalated={escalated})")

        improvement = llm_metrics["f1"] - rule_metrics["f1"]
        combo_improvement = combo_metrics["f1"] - rule_metrics["f1"]
        print(f"  LLM improvement: {improvement:+.3f} | Combined improvement: {combo_improvement:+.3f} | Cost: ${det_cost:.3f}")

        total_cost += det_cost
        total_llm_calls += det_llm_calls

        results.append({
            "detector": det_name,
            "n_entries": len(entries),
            "baseline_f1": baseline_f1,
            "rule_f1": rule_metrics["f1"],
            "rule_precision": rule_metrics["precision"],
            "rule_recall": rule_metrics["recall"],
            "rule_threshold": rule_thresh,
            "llm_f1": llm_metrics["f1"],
            "llm_precision": llm_metrics["precision"],
            "llm_recall": llm_metrics["recall"],
            "llm_threshold": llm_thresh,
            "combo_f1": combo_metrics["f1"],
            "combo_precision": combo_metrics["precision"],
            "combo_recall": combo_metrics["recall"],
            "improvement": improvement,
            "combo_improvement": combo_improvement,
            "cost_usd": det_cost,
            "llm_calls": det_llm_calls,
            "errors": errors,
        })

        # Free memory between detectors
        gc.collect()

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SUMMARY: Rule-Based vs LLM Judge vs Combined")
    print("=" * 78)
    print(f"{'Detector':<22} {'Rule F1':>8} {'Judge F1':>9} {'Combo F1':>9} {'Improv':>8} {'Cost':>7}")
    print("─" * 78)

    improved_detectors = []
    for r in sorted(results, key=lambda x: x["combo_improvement"], reverse=True):
        marker = ""
        if r["combo_improvement"] > 0.05:
            marker = " *"
            improved_detectors.append(r["detector"])
        elif r["combo_improvement"] > 0:
            marker = " +"
        print(f"  {r['detector']:<20} {r['rule_f1']:>7.3f} {r['llm_f1']:>9.3f} {r['combo_f1']:>9.3f} "
              f"{r['combo_improvement']:>+7.3f} ${r['cost_usd']:>6.3f}{marker}")

    print("─" * 78)
    print(f"  Total LLM calls: {total_llm_calls}")
    print(f"  Total cost: ${total_cost:.3f}")
    print(f"  (* = >5% F1 improvement from combined approach)")
    print(f"  (+ = 0-5% improvement)")

    # ---------------------------------------------------------------------------
    # Update gray zone config if improvements found
    # ---------------------------------------------------------------------------
    if improved_detectors:
        print(f"\n{'=' * 78}")
        print(f"RECOMMENDATION: Widen gray zones for: {', '.join(improved_detectors)}")
        print(f"{'=' * 78}")

        # Build recommended gray zone updates
        recommendations = {}
        for r in results:
            if r["detector"] in improved_detectors:
                # Suggest wider gray zone to capture more escalations
                recommendations[r["detector"]] = {
                    "current_rule_f1": r["rule_f1"],
                    "combo_f1": r["combo_f1"],
                    "improvement": r["combo_improvement"],
                    "suggested_gray_zone": "(0.10, 0.90)",
                }
                print(f"  {r['detector']}: F1 {r['rule_f1']:.3f} -> {r['combo_f1']:.3f} "
                      f"(+{r['combo_improvement']:.3f})")

    # Save detailed results to JSON
    output_path = Path("/Users/tuomonikulainen/mao-testing-research/backend/data/llm_judge_eval_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": judge.model.value,
            "total_cost_usd": total_cost,
            "total_llm_calls": total_llm_calls,
            "results": results,
        }, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
