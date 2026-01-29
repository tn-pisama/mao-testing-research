"""CLI for generating golden data with real LLM calls."""

import argparse
import json
import os
import sys

from benchmarks.generators.moltbot.generator import GoldenDatasetEntry
from benchmarks.generators.moltbot.real_llm_generator import RealLLMGenerator


def generate_real_command(args):
    """Generate golden data with real LLM calls."""
    print("🤖 Generating with REAL LLM calls...")
    print(f"   Model: {args.model}")
    print(f"   Scenarios: {args.count}")
    print(f"   Cost estimate: ~${args.count * 0.05:.2f} (approximate)")
    print()

    if not args.yes:
        confirm = input("This will make API calls and incur costs. Continue? [y/N]: ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return

    try:
        generator = RealLLMGenerator(model=args.model)
    except ValueError as e:
        print(f"❌ {e}")
        print("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)
    except ImportError as e:
        print(f"❌ {e}")
        sys.exit(1)

    entries = []
    output_dir = args.output_dir

    # Generate scenarios
    scenarios_to_generate = []

    if args.detector == "all" or args.detector == "loop":
        scenarios_to_generate.extend([("loop", i) for i in range(args.count // 2)])

    if args.detector == "all" or args.detector == "completion":
        scenarios_to_generate.extend([("completion", i) for i in range(args.count // 2)])

    print(f"Generating {len(scenarios_to_generate)} scenarios...")
    print()

    for i, (scenario_type, idx) in enumerate(scenarios_to_generate):
        print(f"[{i+1}/{len(scenarios_to_generate)}] Generating {scenario_type}...")

        try:
            if scenario_type == "loop":
                input_data, raw_llm, metadata = generator.generate_loop_scenario(
                    channel=args.channel
                )
            elif scenario_type == "completion":
                input_data, raw_llm, metadata = generator.generate_completion_scenario(
                    channel=args.channel
                )
            else:
                continue

            # Create golden entry
            entry = GoldenDatasetEntry(
                id=f"real_llm_{scenario_type}_{int(idx):03d}",
                detection_type=metadata.detection_type.upper(),
                input_data=input_data,
                expected_detected=metadata.expected_detected,
                expected_confidence_min=metadata.expected_confidence_min,
                expected_confidence_max=metadata.expected_confidence_max,
                description=metadata.description,
                source="real_llm",
                tags=metadata.tags,
                source_trace_id=input_data.get("trace_id"),
                human_verified=False,
            )

            # Save with raw logs
            generator.save_with_raw_logs(entry, raw_llm, output_dir)
            entries.append(entry)

            print(f"   ✅ Generated (detected: {metadata.expected_detected})")
            print()

        except Exception as e:
            print(f"   ❌ Error: {e}")
            if args.stop_on_error:
                raise
            continue

    # Save combined golden dataset
    golden_jsonl = f"{output_dir}/golden_real_llm.jsonl"
    with open(golden_jsonl, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry.to_dict()) + "\n")

    print(f"\n✅ Generated {len(entries)} samples with real LLM calls")
    print(f"   Golden dataset: {golden_jsonl}")
    print(f"   Raw logs: {output_dir}/raw_*.json")

    # Show statistics
    stats = {"detected": 0, "not_detected": 0}
    for entry in entries:
        if entry.expected_detected:
            stats["detected"] += 1
        else:
            stats["not_detected"] += 1

    print(f"\nStatistics:")
    print(f"   Should detect: {stats['detected']}")
    print(f"   Should NOT detect: {stats['not_detected']}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Moltbot golden data with real LLM calls"
    )

    parser.add_argument(
        "--model",
        default="claude-opus-4-5",
        choices=["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4"],
        help="Claude model to use",
    )
    parser.add_argument(
        "--count", type=int, default=10, help="Number of scenarios to generate"
    )
    parser.add_argument(
        "--detector",
        default="all",
        choices=["all", "loop", "completion"],
        help="Which detector scenarios to generate",
    )
    parser.add_argument(
        "--channel",
        default="whatsapp",
        choices=["whatsapp", "slack", "telegram", "discord"],
        help="Moltbot channel to simulate",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/data/moltbot/real_llm",
        help="Output directory",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    parser.add_argument(
        "--stop-on-error", action="store_true", help="Stop if any generation fails"
    )

    args = parser.parse_args()
    generate_real_command(args)


if __name__ == "__main__":
    main()
