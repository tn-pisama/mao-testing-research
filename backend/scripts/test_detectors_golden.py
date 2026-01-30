#!/usr/bin/env python3
"""
CLI for testing PISAMA detectors against the golden dataset.

Usage:
    python scripts/test_detectors_golden.py --all
    python scripts/test_detectors_golden.py --detector loop --limit 100
    python scripts/test_detectors_golden.py --all --output results/detector_report.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.detection.golden_test_harness import GoldenDatasetTestHarness, HarnessConfig


def main():
    parser = argparse.ArgumentParser(
        description="Test PISAMA detectors against the golden dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all detectors
  python scripts/test_detectors_golden.py --all

  # Test specific detector with sample limit
  python scripts/test_detectors_golden.py --detector loop --limit 100

  # Save detailed report
  python scripts/test_detectors_golden.py --all --output results/report.json

  # Quick test with limit
  python scripts/test_detectors_golden.py --all --limit 50
        """
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("backend/data/golden_dataset_n8n_full.json"),
        help="Path to golden dataset JSON file (default: backend/data/golden_dataset_n8n_full.json)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all available detectors"
    )

    parser.add_argument(
        "--detector",
        type=str,
        choices=["loop", "coordination", "corruption", "persona_drift", "overflow", "completion"],
        help="Test a specific detector"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit samples per detector (for quick testing)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for test results (JSON format)"
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Confidence threshold for detection (default: 0.5)"
    )

    parser.add_argument(
        "--save-misclassified",
        action="store_true",
        default=True,
        help="Save misclassified samples for debugging"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Determine which detectors to test
    if args.all:
        detectors = ["loop", "coordination", "corruption", "persona_drift", "overflow", "completion"]
    elif args.detector:
        detectors = [args.detector]
    else:
        parser.error("Must specify --all or --detector")

    # Check dataset exists
    if not args.dataset.exists():
        print(f"ERROR: Dataset not found at {args.dataset}")
        print(f"Please generate the dataset first using:")
        print(f"  python3 generate_golden_simple.py")
        sys.exit(1)

    # Configure harness
    output_dir = args.output.parent if args.output else Path("backend/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    config = HarnessConfig(
        dataset_path=args.dataset,
        output_dir=output_dir,
        detectors=detectors,
        sample_limit=args.limit,
        save_misclassified=args.save_misclassified,
        confidence_threshold=args.threshold,
    )

    # Run tests
    harness = GoldenDatasetTestHarness(config)
    results = harness.run_all()

    # Generate report
    report = harness.generate_report(results)

    # Save report if output specified
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed results saved to: {args.output}")
    else:
        # Save to default location
        default_output = output_dir / f"detector_test_results_{report['run_timestamp'].replace(':', '-').split('.')[0]}.json"
        with open(default_output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed results saved to: {default_output}")

    # Print final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")

    for detector_type, summary in report["summary"].items():
        print(f"\n{detector_type.upper()}:")
        print(f"  F1 Score:    {summary['f1_score']:.4f}")
        print(f"  Precision:   {summary['precision']:.4f}")
        print(f"  Recall:      {summary['recall']:.4f}")
        print(f"  Accuracy:    {summary['accuracy']:.4f}")
        print(f"  Optimal Threshold: {summary['optimal_threshold']:.2f}")
        print(f"  Samples Tested: {summary['samples_tested']}")

    # Exit with non-zero if any detector has F1 < 0.3 (reasonable baseline)
    min_f1 = min(s["f1_score"] for s in report["summary"].values())
    if min_f1 < 0.3:
        print(f"\nWARNING: Minimum F1 score ({min_f1:.4f}) below 0.3 threshold")
        sys.exit(1)

    print(f"\n{'='*70}")
    print("All tests completed successfully!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
