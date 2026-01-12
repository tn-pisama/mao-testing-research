#!/usr/bin/env python3
"""
Split MAST dataset into dev and test sets for accuracy improvement.

Usage:
    python benchmarks/scripts/split_mast_dataset.py \
        --input data/mast/MAD_full_dataset.json \
        --dev-output data/mast_dev_869.json \
        --test-output data/mast_test_373.json \
        --split-ratio 0.7
"""

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple


def load_mast_dataset(input_path: Path) -> List[Dict]:
    """Load MAST dataset from JSON file."""
    print(f"Loading dataset from {input_path}...")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle different JSON structures
    if isinstance(data, list):
        traces = data
    elif isinstance(data, dict) and "traces" in data:
        traces = data["traces"]
    elif isinstance(data, dict) and "data" in data:
        traces = data["data"]
    else:
        raise ValueError(f"Unexpected JSON structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")

    print(f"Loaded {len(traces)} traces")
    return traces


def analyze_dataset(traces: List[Dict]) -> None:
    """Analyze dataset composition before splitting."""
    print("\n=== Dataset Analysis ===")
    print(f"Total traces: {len(traces)}")

    # Framework distribution
    frameworks = {}
    for trace in traces:
        framework = trace.get("framework", trace.get("source", "unknown"))
        frameworks[framework] = frameworks.get(framework, 0) + 1

    print("\nFramework distribution:")
    for framework, count in sorted(frameworks.items(), key=lambda x: -x[1]):
        print(f"  {framework}: {count} ({count/len(traces)*100:.1f}%)")

    # Failure mode distribution (if available)
    failure_modes = {}
    for trace in traces:
        failures = trace.get("ground_truth_failures", {})
        for mode, detected in failures.items():
            if detected:
                failure_modes[mode] = failure_modes.get(mode, 0) + 1

    if failure_modes:
        print("\nFailure mode prevalence:")
        for mode, count in sorted(failure_modes.items(), key=lambda x: x[0]):
            print(f"  {mode}: {count} ({count/len(traces)*100:.1f}%)")


def stratified_split(
    traces: List[Dict],
    split_ratio: float,
    seed: int = 42
) -> Tuple[List[Dict], List[Dict]]:
    """
    Split traces into dev and test sets with stratification by framework.

    This ensures both sets have representative samples from each framework.
    """
    random.seed(seed)

    # Group traces by framework
    framework_traces = {}
    for trace in traces:
        framework = trace.get("framework", trace.get("source", "unknown"))
        if framework not in framework_traces:
            framework_traces[framework] = []
        framework_traces[framework].append(trace)

    dev_traces = []
    test_traces = []

    # Split each framework separately
    for framework, fw_traces in framework_traces.items():
        # Shuffle within framework
        random.shuffle(fw_traces)

        # Split
        split_idx = int(len(fw_traces) * split_ratio)
        dev_traces.extend(fw_traces[:split_idx])
        test_traces.extend(fw_traces[split_idx:])

    # Final shuffle to mix frameworks
    random.shuffle(dev_traces)
    random.shuffle(test_traces)

    return dev_traces, test_traces


def verify_split(
    original: List[Dict],
    dev: List[Dict],
    test: List[Dict]
) -> None:
    """Verify the split is correct."""
    print("\n=== Verification ===")

    # Check counts
    assert len(dev) + len(test) == len(original), "Split counts don't match original"
    print(f"✓ Total traces match: {len(dev)} + {len(test)} = {len(original)}")

    # Check no overlap using object identity
    # Create sets of trace indices by hashing multiple fields to ensure uniqueness
    def get_trace_signature(trace):
        """Create unique signature from trace content."""
        return (
            trace.get("trace_id"),
            trace.get("mas_name"),
            trace.get("benchmark_name"),
            str(trace.get("trace", ""))[:100]  # First 100 chars of trace
        )

    dev_sigs = set(get_trace_signature(t) for t in dev)
    test_sigs = set(get_trace_signature(t) for t in test)
    overlap = dev_sigs & test_sigs

    if len(overlap) > 0:
        print(f"⚠️  Warning: Found {len(overlap)} potential overlaps")
        # This might be OK if traces genuinely have same trace_id but different content
    else:
        print("✓ No overlap between dev and test")

    # Check framework distribution
    def get_framework_dist(traces):
        frameworks = {}
        for trace in traces:
            framework = trace.get("framework", trace.get("source", "unknown"))
            frameworks[framework] = frameworks.get(framework, 0) + 1
        return frameworks

    orig_dist = get_framework_dist(original)
    dev_dist = get_framework_dist(dev)
    test_dist = get_framework_dist(test)

    print("\nFramework distribution comparison:")
    for framework in sorted(orig_dist.keys()):
        orig_pct = orig_dist[framework] / len(original) * 100
        dev_pct = dev_dist.get(framework, 0) / len(dev) * 100
        test_pct = test_dist.get(framework, 0) / len(test) * 100
        print(f"  {framework}:")
        print(f"    Original: {orig_pct:.1f}%")
        print(f"    Dev:      {dev_pct:.1f}%")
        print(f"    Test:     {test_pct:.1f}%")


def save_split(
    dev_traces: List[Dict],
    test_traces: List[Dict],
    dev_output: Path,
    test_output: Path
) -> None:
    """Save split datasets."""
    print(f"\nSaving dev set ({len(dev_traces)} traces) to {dev_output}...")
    with open(dev_output, "w", encoding="utf-8") as f:
        json.dump(dev_traces, f, indent=2)

    print(f"Saving test set ({len(test_traces)} traces) to {test_output}...")
    with open(test_output, "w", encoding="utf-8") as f:
        json.dump(test_traces, f, indent=2)

    print("\n✓ Split complete!")
    print(f"  Dev set:  {dev_output}")
    print(f"  Test set: {test_output}")


def main():
    parser = argparse.ArgumentParser(
        description="Split MAST dataset into dev and test sets"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/mast/MAD_full_dataset.json"),
        help="Input MAST dataset JSON file"
    )
    parser.add_argument(
        "--dev-output",
        type=Path,
        default=Path("data/mast_dev_869.json"),
        help="Output path for dev set"
    )
    parser.add_argument(
        "--test-output",
        type=Path,
        default=Path("data/mast_test_373.json"),
        help="Output path for test set"
    )
    parser.add_argument(
        "--split-ratio",
        type=float,
        default=0.7,
        help="Ratio for dev set (default: 0.7)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    args = parser.parse_args()

    # Load dataset
    traces = load_mast_dataset(args.input)

    # Analyze before split
    analyze_dataset(traces)

    # Perform stratified split
    print(f"\nSplitting with ratio {args.split_ratio:.1%} dev / {1-args.split_ratio:.1%} test...")
    dev_traces, test_traces = stratified_split(
        traces,
        args.split_ratio,
        seed=args.seed
    )

    print(f"\nSplit sizes:")
    print(f"  Dev:  {len(dev_traces)} traces ({len(dev_traces)/len(traces)*100:.1f}%)")
    print(f"  Test: {len(test_traces)} traces ({len(test_traces)/len(traces)*100:.1f}%)")

    # Verify split
    verify_split(traces, dev_traces, test_traces)

    # Save split
    save_split(dev_traces, test_traces, args.dev_output, args.test_output)

    print("\n" + "="*50)
    print("IMPORTANT: Use dev set for all development and tuning.")
    print("           Test set should ONLY be used for final validation!")
    print("="*50)


if __name__ == "__main__":
    main()
