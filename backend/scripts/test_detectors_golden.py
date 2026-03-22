#!/usr/bin/env python3
"""
CLI for testing PISAMA detectors against the golden dataset.

Uses the enterprise calibration pipeline (calibrate_all) which covers all
42+ detectors with cross-validation, difficulty breakdown, and cost tracking.

Usage:
    python scripts/test_detectors_golden.py --all
    python scripts/test_detectors_golden.py --all --output results/detector_report.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.detection_enterprise.calibrate import calibrate_all


def main():
    parser = argparse.ArgumentParser(
        description="Test PISAMA detectors against the golden dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all detectors
  python scripts/test_detectors_golden.py --all

  # Save detailed report
  python scripts/test_detectors_golden.py --all --output results/report.json

  # Test only on test split
  python scripts/test_detectors_golden.py --all --splits test
        """
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all available detectors"
    )

    parser.add_argument(
        "--splits",
        type=str,
        default=None,
        help="Comma-separated splits to use (e.g., 'test' or 'train,val')"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for test results (JSON format)"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if not args.all:
        parser.error("Must specify --all")

    splits = args.splits.split(",") if args.splits else None

    # Run calibration
    print("Running calibration pipeline...")
    report = calibrate_all(splits=splits)

    # Save report
    results = report["results"]
    # Strip sample_predictions for file output (too large)
    output_report = {k: v for k, v in report.items() if k != "sample_predictions"}

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(output_report, f, indent=2)
        print(f"\nDetailed results saved to: {args.output}")

    # Print final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")

    for detector_type, metrics in sorted(results.items()):
        f1 = metrics.get("f1", 0)
        print(f"\n{detector_type.upper()}:")
        print(f"  F1 Score:    {f1:.4f}")
        print(f"  Precision:   {metrics.get('precision', 0):.4f}")
        print(f"  Recall:      {metrics.get('recall', 0):.4f}")
        print(f"  Threshold:   {metrics.get('optimal_threshold', 0.5):.2f}")
        print(f"  Samples:     {metrics.get('sample_count', 0)}")

    # Exit with non-zero if any detector has F1 < 0.3
    f1_values = [m.get("f1", 0) for m in results.values()]
    if f1_values:
        min_f1 = min(f1_values)
        if min_f1 < 0.3:
            print(f"\nWARNING: Minimum F1 score ({min_f1:.4f}) below 0.3 threshold")
            sys.exit(1)

    avg_f1 = sum(f1_values) / len(f1_values) if f1_values else 0
    print(f"\n{'='*70}")
    print(f"Detectors: {len(results)}, Avg F1: {avg_f1:.4f}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
