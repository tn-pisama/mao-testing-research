#!/usr/bin/env python3
"""Expand ICP detector golden data to 100 samples each.

Uses GoldenDataGenerator (Claude Sonnet) to generate additional samples
for under-covered ICP detectors. Generates balanced positive/negative
samples across easy/medium/hard difficulty levels.

Usage:
    cd ~/mao-testing-research
    PYTHONPATH=backend python3 backend/scripts/expand_icp_golden_data.py

Requires: ANTHROPIC_API_KEY environment variable.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_data_generator import GoldenDataGenerator
from app.detection_enterprise.golden_dataset import create_default_golden_dataset

ICP_DETECTORS = [
    DetectionType.COORDINATION,
    DetectionType.CORRUPTION,
    DetectionType.HALLUCINATION,
    DetectionType.SPECIFICATION,
    DetectionType.DECOMPOSITION,
    DetectionType.CONTEXT,
    DetectionType.PERSONA_DRIFT,
    DetectionType.COMMUNICATION,
    DetectionType.WITHHOLDING,
    DetectionType.COMPLETION,
    DetectionType.OVERFLOW,
    DetectionType.INJECTION,
    DetectionType.DERAILMENT,
    DetectionType.WORKFLOW,
]

TARGET = 100


def main():
    print("Loading existing golden dataset...")
    dataset = create_default_golden_dataset()

    generator = GoldenDataGenerator()
    if not generator.is_available:
        print("ERROR: GoldenDataGenerator not available.")
        print("Make sure ANTHROPIC_API_KEY is set and anthropic SDK is installed.")
        sys.exit(1)

    total_generated = 0

    for dt in ICP_DETECTORS:
        existing = dataset.get_entries_by_type(dt)
        current = len(existing)

        if current >= TARGET:
            print(f"  {dt.value}: {current} samples (already >= {TARGET}, skipping)")
            continue

        needed = TARGET - current
        print(f"\n  {dt.value}: {current} -> targeting {TARGET} ({needed} to generate)")

        generated_for_type = 0
        for difficulty in ["easy", "medium", "hard"]:
            # Distribute evenly across difficulties
            n = needed // 3
            if difficulty == "medium":
                n += needed % 3  # give remainder to medium

            if n <= 0:
                continue

            print(f"    Generating {n} {difficulty} samples...", end=" ", flush=True)
            try:
                entries = generator.generate(
                    dt,
                    count=n,
                    positive_ratio=0.5,
                    existing_entries=existing,
                    difficulty=difficulty,
                )
                for e in entries:
                    dataset.add_entry(e)
                generated_for_type += len(entries)
                print(f"got {len(entries)}")
            except Exception as exc:
                print(f"FAILED: {exc}")

        new_total = len(dataset.get_entries_by_type(dt))
        total_generated += generated_for_type
        print(f"    {dt.value}: {current} -> {new_total}")

    # Save expanded dataset
    save_path = Path(__file__).parent.parent / "data" / "golden_dataset_expanded.json"
    dataset.save(save_path)
    print(f"\nTotal generated: {total_generated}")
    print(f"Expanded dataset saved to: {save_path}")


if __name__ == "__main__":
    main()
