#!/usr/bin/env python3
"""
Test PISAMA detectors against OTEL golden traces.

Usage:
    python scripts/test_detectors_otel.py --all
    python scripts/test_detectors_otel.py --detector infinite_loop --limit 50
    python scripts/test_detectors_otel.py --all --output results/otel_report.json
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.detection.golden_test_harness_otel import (
    OTELGoldenTraceTestHarness,
    OTELHarnessConfig,
)


def main():
    parser = argparse.ArgumentParser(
        description="Test PISAMA detectors against OTEL golden traces"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all detectors (legacy + MAST F1-F14)",
    )
    parser.add_argument(
        "--legacy-only",
        action="store_true",
        help="Test only legacy detectors (loop, coordination, corruption, persona)",
    )
    parser.add_argument(
        "--mast-only",
        action="store_true",
        help="Test only MAST F1-F14 detectors",
    )
    parser.add_argument(
        "--detector",
        type=str,
        choices=[
            "infinite_loop", "coordination_deadlock", "state_corruption", "persona_drift",
            "F1_spec_mismatch", "F2_poor_decomposition", "F3_resource_misallocation",
            "F4_inadequate_tool", "F5_flawed_workflow", "F6_task_derailment",
            "F7_context_neglect", "F8_information_withholding", "F9_role_usurpation",
            "F10_communication_breakdown", "F12_output_validation_failure",
            "F13_quality_gate_bypass", "F14_completion_misjudgment"
        ],
        help="Test specific detector",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of traces per detector",
    )
    parser.add_argument(
        "--traces",
        type=str,
        default="fixtures/golden/mast_traces.jsonl/golden_traces.jsonl",
        help="Path to OTEL traces file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON report path",
    )

    args = parser.parse_args()

    # Determine which detectors to test
    legacy_detectors = ["infinite_loop", "coordination_deadlock", "state_corruption", "persona_drift"]
    mast_detectors = [
        "F1_spec_mismatch", "F2_poor_decomposition", "F3_resource_misallocation",
        "F4_inadequate_tool", "F5_flawed_workflow", "F6_task_derailment",
        "F7_context_neglect", "F8_information_withholding", "F9_role_usurpation",
        "F10_communication_breakdown", "F12_output_validation_failure",
        "F13_quality_gate_bypass", "F14_completion_misjudgment"
    ]

    if args.all:
        detectors = legacy_detectors + mast_detectors
    elif args.legacy_only:
        detectors = legacy_detectors
    elif args.mast_only:
        detectors = mast_detectors
    elif args.detector:
        detectors = [args.detector]
    else:
        print("Error: Must specify --all, --legacy-only, --mast-only, or --detector")
        parser.print_help()
        return 1

    # Setup paths
    backend_dir = Path(__file__).parent.parent
    traces_path = backend_dir / args.traces
    output_dir = backend_dir / "data"

    if not traces_path.exists():
        print(f"Error: Traces file not found: {traces_path}")
        return 1

    # Create config
    config = OTELHarnessConfig(
        traces_path=traces_path,
        output_dir=output_dir,
        detectors=detectors,
        sample_limit=args.limit,
    )

    # Run tests
    harness = OTELGoldenTraceTestHarness(config)
    results = harness.run_all()

    # Generate report
    report = harness.generate_report(results)

    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")

    print("| Detector | F1 | Precision | Recall | Accuracy | Samples |")
    print("|----------|-----|-----------|--------|----------|---------|")

    for detector_type, summary in report["summary"].items():
        print(
            f"| {detector_type:20} | "
            f"{summary['f1_score']:.3f} | "
            f"{summary['precision']:.3f} | "
            f"{summary['recall']:.3f} | "
            f"{summary['accuracy']:.3f} | "
            f"{summary['samples_tested']:4d} |"
        )

    # Save report if requested
    if args.output:
        output_path = backend_dir / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
