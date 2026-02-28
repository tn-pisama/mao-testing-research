#!/usr/bin/env python3
"""Verify generated n8n golden dataset entries by running them through detectors.

Loads the generated dataset, runs each entry through its corresponding detector,
and reports per-type accuracy metrics (TP, FP, FN, TN, F1, precision, recall).
Flags entries where the detector strongly disagrees with the label.

Usage:
    python -m scripts.verify_n8n_golden_dataset \
        --input data/golden_dataset_n8n_expanded.json \
        --report data/n8n_golden_verification_report.json
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDataset, GoldenDatasetEntry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("verify_n8n")

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "golden_dataset_n8n_expanded.json"
DEFAULT_REPORT = Path(__file__).resolve().parent.parent / "data" / "n8n_golden_verification_report.json"


@dataclass
class TypeVerificationResult:
    """Verification metrics for a single detection type."""
    detection_type: str
    total: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    flagged_entries: List[Dict[str, Any]]


def compute_metrics(tp: int, tn: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """Compute precision, recall, F1 from confusion matrix."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def verify_type(
    detection_type: DetectionType,
    entries: List[GoldenDatasetEntry],
    runner,
    threshold: float = 0.5,
) -> TypeVerificationResult:
    """Run entries through detector and compute metrics."""
    tp = tn = fp = fn = 0
    flagged = []

    for entry in entries:
        try:
            detected, confidence = runner(entry)
            predicted = confidence >= threshold

            if entry.expected_detected and predicted:
                tp += 1
            elif not entry.expected_detected and not predicted:
                tn += 1
            elif not entry.expected_detected and predicted:
                fp += 1
                # Flag: detector thinks positive but label says negative
                if confidence > 0.7:
                    flagged.append({
                        "id": entry.id,
                        "issue": "high_confidence_false_positive",
                        "confidence": round(confidence, 3),
                        "description": entry.description[:100],
                    })
            else:  # expected positive but predicted negative
                fn += 1
                if confidence < 0.3:
                    flagged.append({
                        "id": entry.id,
                        "issue": "low_confidence_false_negative",
                        "confidence": round(confidence, 3),
                        "description": entry.description[:100],
                    })
        except Exception as exc:
            logger.warning("Error running %s on %s: %s", detection_type.value, entry.id, exc)
            # Count errors as disagreement with label
            if entry.expected_detected:
                fn += 1
            else:
                tn += 1  # Not detecting is correct for negatives

    precision, recall, f1 = compute_metrics(tp, tn, fp, fn)

    return TypeVerificationResult(
        detection_type=detection_type.value,
        total=len(entries),
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        flagged_entries=flagged,
    )


def main():
    parser = argparse.ArgumentParser(description="Verify n8n golden dataset entries against detectors")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input dataset JSON")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Output report JSON")
    parser.add_argument("--threshold", type=float, default=0.5, help="Detection threshold (default: 0.5)")
    parser.add_argument("--types", type=str, default=None, help="Comma-separated types to verify")
    parser.add_argument("--n8n-only", action="store_true", help="Only verify entries tagged 'n8n'")
    parser.add_argument("--from-db", action="store_true", help="Load entries from PostgreSQL instead of JSON file")
    args = parser.parse_args()

    # Load dataset
    if args.from_db:
        import asyncio
        from app.detection_enterprise.golden_dataset import GoldenDatasetDB
        from app.storage.database import async_session_maker

        async def _load():
            async with async_session_maker() as session:
                return await GoldenDatasetDB.from_db(session)

        dataset = asyncio.run(_load())
        logger.info("Loaded %d entries from PostgreSQL", len(dataset.entries))
    else:
        if not args.input.exists():
            logger.error("Input file not found: %s", args.input)
            sys.exit(1)
        dataset = GoldenDataset(args.input)
        logger.info("Loaded %d entries from %s", len(dataset.entries), args.input)

    # Build detector runners
    try:
        from app.detection_enterprise.calibrate import _build_detector_runners
        runners = _build_detector_runners()
    except ImportError as e:
        logger.error("Cannot import detector runners: %s", e)
        sys.exit(1)

    # Parse type filter
    type_filter = None
    if args.types:
        type_filter = set(t.strip() for t in args.types.split(","))

    # Run verification
    results: List[TypeVerificationResult] = []
    total_entries = 0
    total_correct = 0

    for dt in DetectionType:
        if type_filter and dt.value not in type_filter:
            continue

        runner = runners.get(dt)
        if runner is None:
            logger.info("No detector runner for %s, skipping", dt.value)
            continue

        entries = dataset.get_entries_by_type(dt)
        if args.n8n_only:
            entries = [e for e in entries if "n8n" in e.tags]

        if not entries:
            logger.info("No entries for %s, skipping", dt.value)
            continue

        logger.info("Verifying %d entries for %s...", len(entries), dt.value)
        result = verify_type(dt, entries, runner, threshold=args.threshold)
        results.append(result)

        total_entries += result.total
        total_correct += result.true_positives + result.true_negatives

    # Build report
    report = {
        "input_file": str(args.input),
        "threshold": args.threshold,
        "n8n_only": args.n8n_only,
        "total_entries_verified": total_entries,
        "overall_accuracy": round(total_correct / total_entries, 4) if total_entries > 0 else 0.0,
        "per_type": [asdict(r) for r in results],
    }

    # Save report
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Report saved to %s", args.report)

    # Print summary
    print(f"\n{'='*80}")
    print(f"N8N Golden Dataset Verification Report")
    print(f"{'='*80}")
    print(f"Input:     {args.input}")
    print(f"Threshold: {args.threshold}")
    print(f"Entries:   {total_entries}")
    print(f"Accuracy:  {report['overall_accuracy']:.1%}")
    print()

    # Table header
    print(f"{'Type':25s} {'Total':>6s} {'TP':>5s} {'TN':>5s} {'FP':>5s} {'FN':>5s} {'Prec':>7s} {'Rec':>7s} {'F1':>7s} {'Flag':>5s}")
    print("-" * 80)

    for r in sorted(results, key=lambda x: x.f1, reverse=True):
        flag_mark = f"{len(r.flagged_entries)}" if r.flagged_entries else "-"
        print(
            f"{r.detection_type:25s} {r.total:6d} {r.true_positives:5d} {r.true_negatives:5d} "
            f"{r.false_positives:5d} {r.false_negatives:5d} {r.precision:7.3f} {r.recall:7.3f} "
            f"{r.f1:7.3f} {flag_mark:>5s}"
        )

    print("-" * 80)

    # Show flagged entries
    all_flagged = []
    for r in results:
        all_flagged.extend(r.flagged_entries)

    if all_flagged:
        print(f"\nFlagged entries ({len(all_flagged)} total — likely bad labels):")
        for f in all_flagged[:20]:
            print(f"  [{f['id']}] {f['issue']} (conf={f['confidence']:.3f}): {f['description']}")
        if len(all_flagged) > 20:
            print(f"  ... and {len(all_flagged) - 20} more (see report JSON)")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
