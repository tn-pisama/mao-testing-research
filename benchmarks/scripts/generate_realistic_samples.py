#!/usr/bin/env python3
"""CLI for generating realistic test samples (real LLM + adversarial)."""

import argparse
import json
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.generators.moltbot.real_llm_generator import RealLLMGenerator
from benchmarks.generators.moltbot.generator import GoldenDatasetEntry


DETECTION_TYPES = [
    "loop",
    "completion",
    "injection",
    "overflow",
    "hallucination",
    "persona_drift",
    "corruption",
    "coordination",
]

# Sample counts per type (for realistic testing)
SAMPLE_TARGETS = {
    "loop": {"real": 0, "adversarial": 15},  # Already have 25
    "completion": {"real": 0, "adversarial": 15},  # Already have 25
    "injection": {"real": 50, "adversarial": 25},
    "overflow": {"real": 40, "adversarial": 15},
    "hallucination": {"real": 50, "adversarial": 25},
    "persona_drift": {"real": 40, "adversarial": 15},
    "corruption": {"real": 40, "adversarial": 15},
    "coordination": {"real": 40, "adversarial": 15},
}


def generate_real_llm_samples(
    detector_type: str,
    count: int,
    generator: RealLLMGenerator,
    output_dir: Path,
):
    """Generate real LLM samples for a detection type."""
    print(f"\nGenerating {count} real LLM samples for {detector_type}...")

    entries = []
    channels = ["slack", "whatsapp", "telegram", "discord", "signal"]

    for i in range(count):
        channel = channels[i % len(channels)]
        print(f"  Sample {i+1}/{count} ({channel})...", end=" ")

        try:
            # Call appropriate generator method
            if detector_type == "loop":
                input_data, raw_data, metadata = generator.generate_loop_scenario(channel)
            elif detector_type == "completion":
                input_data, raw_data, metadata = generator.generate_completion_scenario(channel)
            elif detector_type == "injection":
                scenarios = ["roleplay", "meta_discussion", "indirect"]
                scenario = scenarios[i % len(scenarios)]
                input_data, raw_data, metadata = generator.generate_injection_scenario(
                    channel, scenario
                )
            elif detector_type == "overflow":
                input_data, raw_data, metadata = generator.generate_overflow_scenario(channel)
            elif detector_type == "hallucination":
                scenarios = ["tool_contradiction", "confident_fabrication"]
                scenario = scenarios[i % len(scenarios)]
                input_data, raw_data, metadata = generator.generate_hallucination_scenario(
                    channel, scenario
                )
            elif detector_type == "persona_drift":
                input_data, raw_data, metadata = generator.generate_persona_drift_scenario()
            elif detector_type == "corruption":
                input_data, raw_data, metadata = generator.generate_corruption_scenario(channel)
            elif detector_type == "coordination":
                input_data, raw_data, metadata = generator.generate_coordination_scenario(channel)
            else:
                print(f"ERROR: Unknown detector type {detector_type}")
                continue

            # Create entry
            entry_id = f"real_llm_{detector_type}_{i:03d}"
            entry = GoldenDatasetEntry(
                id=entry_id,
                detection_type=metadata.detection_type,
                input_data=input_data,
                expected_detected=metadata.expected_detected,
                expected_confidence_min=metadata.expected_confidence_min,
                expected_confidence_max=metadata.expected_confidence_max,
                description=metadata.description,
                source="real_llm",
                tags=metadata.tags,
                variant=metadata.variant,
                human_verified=False,
            )

            # Save with raw logs
            generator.save_with_raw_logs(entry, raw_data, str(output_dir))
            entries.append(entry)

            print("✓")

        except Exception as e:
            print(f"ERROR: {e}")
            continue

    return entries


def generate_adversarial_samples(
    detector_type: str,
    count: int,
    output_dir: Path,
):
    """Generate adversarial samples for a detection type."""
    print(f"\nGenerating {count} adversarial samples for {detector_type}...")
    print("  (Note: Adversarial generation not yet implemented)")

    # TODO: Implement adversarial generator
    # For now, just create placeholder
    entries = []

    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Generate realistic test samples for PISAMA detectors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate real LLM samples for injection detection
  python scripts/generate_realistic_samples.py --type real_llm --detector injection --count 50

  # Generate adversarial samples for hallucination
  python scripts/generate_realistic_samples.py --type adversarial --detector hallucination --count 25

  # Generate all real LLM samples (based on targets)
  python scripts/generate_realistic_samples.py --type real_llm --all

  # Quick test with 5 samples
  python scripts/generate_realistic_samples.py --type real_llm --detector injection --count 5
        """,
    )

    parser.add_argument(
        "--type",
        required=True,
        choices=["real_llm", "adversarial"],
        help="Type of samples to generate",
    )

    parser.add_argument(
        "--detector",
        choices=DETECTION_TYPES,
        help="Specific detector to generate samples for",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate samples for all detectors (using SAMPLE_TARGETS)",
    )

    parser.add_argument(
        "--count",
        type=int,
        help="Number of samples to generate (overrides SAMPLE_TARGETS)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/data/moltbot/real_llm"),
        help="Output directory for generated samples",
    )

    parser.add_argument(
        "--model",
        default="claude-sonnet-4-5",
        help="Model to use for real LLM generation",
    )

    args = parser.parse_args()

    if not args.all and not args.detector:
        parser.error("Must specify --all or --detector")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Determine which detectors to generate
    if args.all:
        detectors_to_generate = DETECTION_TYPES
    else:
        detectors_to_generate = [args.detector]

    # Initialize generator if needed
    generator = None
    if args.type == "real_llm":
        try:
            generator = RealLLMGenerator(model=args.model)
        except ValueError as e:
            print(f"ERROR: {e}")
            print("Set ANTHROPIC_API_KEY environment variable")
            sys.exit(1)

    # Generate samples
    all_entries = []
    total_cost = 0.0

    for detector_type in detectors_to_generate:
        # Determine count
        if args.count:
            count = args.count
        else:
            count = SAMPLE_TARGETS[detector_type][args.type]

        if count == 0:
            print(f"\nSkipping {detector_type} (already have samples or count=0)")
            continue

        # Generate
        if args.type == "real_llm":
            entries = generate_real_llm_samples(
                detector_type, count, generator, args.output
            )
        else:
            entries = generate_adversarial_samples(
                detector_type, count, args.output
            )

        all_entries.extend(entries)

        # Estimate cost ($0.05 per sample average)
        cost = count * 0.05
        total_cost += cost
        print(f"  Generated: {len(entries)}/{count} samples")
        print(f"  Estimated cost: ${cost:.2f}")

    # Summary
    print(f"\n{'='*70}")
    print("GENERATION SUMMARY")
    print(f"{'='*70}")
    print(f"Total samples generated: {len(all_entries)}")
    print(f"Total estimated cost: ${total_cost:.2f}")
    print(f"Output directory: {args.output}")

    # Save combined JSONL
    if all_entries:
        combined_path = args.output / f"golden_{args.type}_batch.jsonl"
        with open(combined_path, "w") as f:
            for entry in all_entries:
                f.write(json.dumps(entry.to_dict()) + "\n")
        print(f"Combined JSONL: {combined_path}")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()
