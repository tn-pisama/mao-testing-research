"""CLI for Moltbot golden data generation."""

import argparse
import json
import sys
from pathlib import Path

from benchmarks.generators.moltbot.generator import MoltbotTraceGenerator
from benchmarks.generators.moltbot.scenarios import (
    LoopScenarioGenerator,
    CompletionScenarioGenerator,
    InjectionScenarioGenerator,
    PersonaScenarioGenerator,
    CoordinationScenarioGenerator,
    CorruptionScenarioGenerator,
    OverflowScenarioGenerator,
    HallucinationScenarioGenerator,
)


def generate_command(args):
    """Generate golden dataset."""
    print(f"Generating Moltbot golden dataset...")
    print(f"  Samples: {args.count}")
    print(f"  Output: {args.output}")

    # Create generator
    generator = MoltbotTraceGenerator()

    # Register all scenario generators
    generator.register_scenario("loop", LoopScenarioGenerator())
    generator.register_scenario("completion", CompletionScenarioGenerator())
    generator.register_scenario("injection", InjectionScenarioGenerator())
    generator.register_scenario("persona", PersonaScenarioGenerator())
    generator.register_scenario("coordination", CoordinationScenarioGenerator())
    generator.register_scenario("corruption", CorruptionScenarioGenerator())
    generator.register_scenario("overflow", OverflowScenarioGenerator())
    generator.register_scenario("hallucination", HallucinationScenarioGenerator())

    # Generate dataset
    if args.detector:
        # Generate for specific detector only
        print(f"  Detector: {args.detector}")
        # Filter to just this detector
        original_variants = generator.DETECTION_VARIANTS.copy()
        generator.DETECTION_VARIANTS = {args.detector: original_variants[args.detector]}

    entries = generator.generate_golden_dataset(n_samples=args.count, balanced=not args.unbalanced)

    # Save dataset
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generator.save_golden_dataset(entries, args.output)

    print(f"✅ Generated {len(entries)} samples")
    print(f"   Saved to: {args.output}")

    # Show statistics
    stats = {}
    for entry in entries:
        det_type = entry.detection_type
        stats[det_type] = stats.get(det_type, {"positive": 0, "negative": 0})
        if entry.expected_detected:
            stats[det_type]["positive"] += 1
        else:
            stats[det_type]["negative"] += 1

    print("\nDataset Statistics:")
    for det_type, counts in sorted(stats.items()):
        total = counts["positive"] + counts["negative"]
        print(f"  {det_type:12s}: {total:3d} samples ({counts['positive']:3d} pos, {counts['negative']:3d} neg)")


def validate_command(args):
    """Validate golden dataset format."""
    print(f"Validating {args.dataset}...")

    try:
        with open(args.dataset) as f:
            entries = [json.loads(line) for line in f]

        print(f"✅ Valid JSONL format ({len(entries)} entries)")

        # Check required fields
        required_fields = [
            "id",
            "detection_type",
            "input_data",
            "expected_detected",
            "expected_confidence_min",
            "expected_confidence_max",
            "description",
            "source",
            "tags",
        ]

        for i, entry in enumerate(entries):
            for field in required_fields:
                if field not in entry:
                    print(f"❌ Entry {i} missing field: {field}")
                    sys.exit(1)

        print(f"✅ All entries have required fields")

        # Check detection type distribution
        det_types = {}
        for entry in entries:
            dt = entry["detection_type"]
            det_types[dt] = det_types.get(dt, 0) + 1

        print("\nDetection Type Distribution:")
        for dt, count in sorted(det_types.items()):
            print(f"  {dt:12s}: {count:3d} samples")

        print("\n✅ Validation passed!")

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ File not found: {args.dataset}")
        sys.exit(1)


def test_command(args):
    """Run detectors against golden dataset."""
    print(f"Testing detectors against {args.dataset}...")
    print("\nNote: Actual detector testing requires PISAMA backend.")
    print("Run: python backend/scripts/test_detectors_golden.py --dataset", args.dataset)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Moltbot Golden Data Generator")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate golden dataset")
    gen_parser.add_argument("--output", default="benchmarks/data/moltbot/golden_moltbot.jsonl", help="Output file")
    gen_parser.add_argument("--count", type=int, default=200, help="Number of samples")
    gen_parser.add_argument("--detector", help="Generate for specific detector only")
    gen_parser.add_argument("--unbalanced", action="store_true", help="Don't balance positive/negative samples")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate golden dataset")
    val_parser.add_argument("dataset", help="Path to golden dataset JSONL")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test detectors against golden dataset")
    test_parser.add_argument("dataset", help="Path to golden dataset JSONL")

    args = parser.parse_args()

    if args.command == "generate":
        generate_command(args)
    elif args.command == "validate":
        validate_command(args)
    elif args.command == "test":
        test_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
