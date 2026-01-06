"""Train/validation/test split with stratification for multi-agent traces.

Ensures balanced representation across:
- Frameworks (langchain, autogen, crewai, n8n)
- Failure modes (F1-F14)
- Complexity levels (simple, medium, complex)
- Healthy vs failure traces
"""

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_traces(traces_dir: str = "traces") -> list[dict]:
    """Load all traces from JSONL files."""
    traces_dir = Path(traces_dir)
    all_traces = []

    frameworks = ["langchain", "autogen", "crewai", "n8n"]

    for framework in frameworks:
        # Load failure traces
        failure_file = traces_dir / f"{framework}_scaled_traces.jsonl"
        if failure_file.exists():
            with open(failure_file) as f:
                for line in f:
                    if line.strip():
                        trace = json.loads(line)
                        all_traces.append(trace)

        # Load healthy traces
        healthy_file = traces_dir / f"{framework}_healthy_traces.jsonl"
        if healthy_file.exists():
            with open(healthy_file) as f:
                for line in f:
                    if line.strip():
                        trace = json.loads(line)
                        all_traces.append(trace)

    return all_traces


def get_stratification_key(trace: dict) -> str:
    """Generate a stratification key combining framework, mode, complexity, and health."""
    framework = trace.get("framework", "unknown")
    failure_mode = trace.get("failure_mode", "unknown")
    complexity = trace.get("complexity", "unknown")
    is_healthy = trace.get("is_healthy", False)
    health_label = "healthy" if is_healthy else "failure"

    return f"{framework}_{failure_mode}_{complexity}_{health_label}"


def stratified_split(
    traces: list[dict],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split traces into train/val/test sets with stratification.

    Args:
        traces: List of trace dictionaries
        train_ratio: Fraction for training set
        val_ratio: Fraction for validation set
        test_ratio: Fraction for test set
        random_seed: Random seed for reproducibility

    Returns:
        Tuple of (train_traces, val_traces, test_traces)
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 0.001, \
        "Ratios must sum to 1.0"

    random.seed(random_seed)

    # Group traces by stratification key
    stratified_groups = defaultdict(list)
    for trace in traces:
        key = get_stratification_key(trace)
        stratified_groups[key].append(trace)

    train_traces = []
    val_traces = []
    test_traces = []

    # Split each group maintaining ratios
    for key, group_traces in stratified_groups.items():
        random.shuffle(group_traces)

        n = len(group_traces)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)

        train_traces.extend(group_traces[:train_end])
        val_traces.extend(group_traces[train_end:val_end])
        test_traces.extend(group_traces[val_end:])

    # Shuffle each set
    random.shuffle(train_traces)
    random.shuffle(val_traces)
    random.shuffle(test_traces)

    return train_traces, val_traces, test_traces


def save_split(
    train_traces: list[dict],
    val_traces: list[dict],
    test_traces: list[dict],
    output_dir: str = "traces/splits",
) -> None:
    """Save split traces to JSONL files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    splits = [
        ("train", train_traces),
        ("val", val_traces),
        ("test", test_traces),
    ]

    for split_name, traces in splits:
        output_file = output_dir / f"{split_name}_traces.jsonl"
        with open(output_file, "w") as f:
            for trace in traces:
                f.write(json.dumps(trace) + "\n")
        print(f"  Saved {len(traces)} traces to {output_file}")


def analyze_split(
    train_traces: list[dict],
    val_traces: list[dict],
    test_traces: list[dict],
) -> dict:
    """Analyze the distribution of splits."""

    def get_distribution(traces: list[dict]) -> dict:
        framework_dist = defaultdict(int)
        mode_dist = defaultdict(int)
        complexity_dist = defaultdict(int)
        health_dist = defaultdict(int)

        for trace in traces:
            framework_dist[trace.get("framework", "unknown")] += 1
            mode_dist[trace.get("failure_mode", "unknown")] += 1
            complexity_dist[trace.get("complexity", "unknown")] += 1
            health_dist["healthy" if trace.get("is_healthy", False) else "failure"] += 1

        return {
            "total": len(traces),
            "by_framework": dict(framework_dist),
            "by_mode": dict(mode_dist),
            "by_complexity": dict(complexity_dist),
            "by_health": dict(health_dist),
        }

    return {
        "train": get_distribution(train_traces),
        "val": get_distribution(val_traces),
        "test": get_distribution(test_traces),
    }


def print_split_summary(analysis: dict) -> None:
    """Print a summary of the split distribution."""
    print("\n" + "="*70)
    print("SPLIT DISTRIBUTION SUMMARY")
    print("="*70)

    for split_name, dist in analysis.items():
        print(f"\n{split_name.upper()} SET: {dist['total']} traces")

        print(f"  By Framework:")
        for fw, count in sorted(dist["by_framework"].items()):
            pct = 100 * count / dist["total"]
            print(f"    {fw}: {count} ({pct:.1f}%)")

        print(f"  By Health:")
        for health, count in sorted(dist["by_health"].items()):
            pct = 100 * count / dist["total"]
            print(f"    {health}: {count} ({pct:.1f}%)")

        print(f"  By Complexity:")
        for comp, count in sorted(dist["by_complexity"].items()):
            pct = 100 * count / dist["total"]
            print(f"    {comp}: {count} ({pct:.1f}%)")

    # Check balance
    print("\n" + "-"*70)
    print("BALANCE CHECK")
    print("-"*70)

    train_health = analysis["train"]["by_health"]
    val_health = analysis["val"]["by_health"]
    test_health = analysis["test"]["by_health"]

    for health_type in ["healthy", "failure"]:
        train_pct = 100 * train_health.get(health_type, 0) / analysis["train"]["total"]
        val_pct = 100 * val_health.get(health_type, 0) / analysis["val"]["total"]
        test_pct = 100 * test_health.get(health_type, 0) / analysis["test"]["total"]

        variance = max(train_pct, val_pct, test_pct) - min(train_pct, val_pct, test_pct)
        status = "OK" if variance < 5 else "WARN"
        print(f"  {health_type}: train={train_pct:.1f}%, val={val_pct:.1f}%, test={test_pct:.1f}% [{status}]")


def create_splits(
    traces_dir: str = "traces",
    output_dir: str = "traces/splits",
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Complete pipeline to create and save stratified splits."""
    print("Loading traces...")
    traces = load_traces(traces_dir)
    print(f"  Loaded {len(traces)} total traces")

    print("\nCreating stratified split...")
    train, val, test = stratified_split(
        traces,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed,
    )

    print("\nSaving splits...")
    save_split(train, val, test, output_dir)

    analysis = analyze_split(train, val, test)
    print_split_summary(analysis)

    # Save analysis
    analysis_file = Path(output_dir) / "split_analysis.json"
    with open(analysis_file, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"\nSaved analysis to {analysis_file}")

    return train, val, test


if __name__ == "__main__":
    create_splits()
