"""Threshold calibration from labeled synthetic data.

Runs the loop detector against labeled traces with various threshold
configurations to find optimal settings for each framework.

Usage:
    python -m benchmarks.evaluation.threshold_calibration --traces traces/
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import itertools

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.detection.loop import MultiLevelLoopDetector, StateSnapshot
from app.config import FRAMEWORK_THRESHOLDS, FrameworkThresholds


@dataclass
class CalibrationResult:
    """Result from a single calibration run."""
    structural_threshold: float
    semantic_threshold: float
    window_size: int
    min_matches: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    fpr: float  # False positive rate


@dataclass
class TraceLabel:
    """Labeled trace for calibration."""
    trace_id: str
    framework: str
    has_loop: bool
    loop_type: Optional[str]
    states: List[Dict]


def load_labeled_traces(traces_dir: str) -> Dict[str, List[TraceLabel]]:
    """Load labeled traces from JSONL files.

    Expected format:
    {
        "trace_id": "...",
        "framework": "langgraph",
        "failure_mode": "F1",  # F1 = exact loop, F3 = semantic loop, healthy = no loop
        "states": [{"agent_id": "...", "state": {...}, "content": "..."}, ...]
    }

    Returns:
        Dict mapping framework to list of labeled traces
    """
    traces_path = Path(traces_dir)
    traces_by_framework = defaultdict(list)

    # Load from various trace files
    for trace_file in traces_path.glob("*.jsonl"):
        with open(trace_file) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    framework = data.get("framework", "unknown")
                    failure_mode = data.get("failure_mode", "healthy")

                    # Determine if this is a loop trace
                    has_loop = failure_mode in [
                        "F1", "F3", "F6",  # Loop-related failure modes
                        "infinite_loop", "semantic_loop", "exact_loop",
                    ]
                    loop_type = failure_mode if has_loop else None

                    # Extract states
                    states = data.get("states", data.get("trace", []))
                    if not states:
                        continue

                    traces_by_framework[framework].append(TraceLabel(
                        trace_id=data.get("trace_id", data.get("id", str(len(traces_by_framework[framework])))),
                        framework=framework,
                        has_loop=has_loop,
                        loop_type=loop_type,
                        states=states,
                    ))
                except (json.JSONDecodeError, KeyError):
                    continue

    return traces_by_framework


def convert_to_snapshots(states: List[Dict]) -> List[StateSnapshot]:
    """Convert trace states to StateSnapshot objects."""
    snapshots = []
    for i, state in enumerate(states):
        snapshots.append(StateSnapshot(
            agent_id=state.get("agent_id", state.get("agent", "unknown")),
            state_delta=state.get("state", state.get("state_delta", {})),
            content=state.get("content", json.dumps(state.get("state", state.get("state_delta", {})))),
            sequence_num=i,
        ))
    return snapshots


def evaluate_thresholds(
    traces: List[TraceLabel],
    structural_threshold: float,
    semantic_threshold: float,
    window_size: int,
    min_matches: int,
    framework: Optional[str] = None,
) -> CalibrationResult:
    """Evaluate a threshold configuration against labeled traces."""

    detector = MultiLevelLoopDetector(
        structural_threshold=structural_threshold,
        semantic_threshold=semantic_threshold,
        window_size=window_size,
        min_matches_for_loop=min_matches,
        framework=framework,
    )

    tp = fp = fn = tn = 0

    for trace in traces:
        snapshots = convert_to_snapshots(trace.states)
        if len(snapshots) < 3:
            continue

        result = detector.detect_loop(snapshots)

        if trace.has_loop:
            if result.detected:
                tp += 1
            else:
                fn += 1
        else:
            if result.detected:
                fp += 1
            else:
                tn += 1

    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return CalibrationResult(
        structural_threshold=structural_threshold,
        semantic_threshold=semantic_threshold,
        window_size=window_size,
        min_matches=min_matches,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        fpr=fpr,
    )


def grid_search_thresholds(
    traces: List[TraceLabel],
    framework: str,
    current_thresholds: FrameworkThresholds,
) -> Tuple[CalibrationResult, List[CalibrationResult]]:
    """Search for optimal thresholds using grid search.

    Searches around current thresholds to find improvements.

    Returns:
        Tuple of (best_result, all_results)
    """
    # Define search space around current values
    structural_range = [
        max(0.5, current_thresholds.structural_threshold - 0.06),
        current_thresholds.structural_threshold - 0.03,
        current_thresholds.structural_threshold,
        min(0.99, current_thresholds.structural_threshold + 0.03),
    ]

    semantic_range = [
        max(0.5, current_thresholds.semantic_threshold - 0.06),
        current_thresholds.semantic_threshold - 0.03,
        current_thresholds.semantic_threshold,
        min(0.99, current_thresholds.semantic_threshold + 0.03),
    ]

    window_range = [
        max(3, current_thresholds.loop_detection_window - 2),
        current_thresholds.loop_detection_window,
        min(15, current_thresholds.loop_detection_window + 2),
    ]

    min_matches_range = [2, 3]

    all_results = []

    for struct, sem, window, min_m in itertools.product(
        structural_range, semantic_range, window_range, min_matches_range
    ):
        result = evaluate_thresholds(
            traces=traces,
            structural_threshold=round(struct, 2),
            semantic_threshold=round(sem, 2),
            window_size=window,
            min_matches=min_m,
            framework=framework,
        )
        all_results.append(result)

    # Sort by F1 score (descending), then by FPR (ascending)
    all_results.sort(key=lambda r: (-r.f1_score, r.fpr))

    return all_results[0], all_results


def print_calibration_results(
    framework: str,
    current: FrameworkThresholds,
    best: CalibrationResult,
    num_traces: int,
) -> Dict:
    """Print and return calibration results."""

    print(f"\n{'='*60}")
    print(f"FRAMEWORK: {framework.upper()}")
    print(f"{'='*60}")
    print(f"Evaluated on {num_traces} traces")
    print()

    print("Current Thresholds:")
    print(f"  structural_threshold: {current.structural_threshold}")
    print(f"  semantic_threshold: {current.semantic_threshold}")
    print(f"  loop_detection_window: {current.loop_detection_window}")
    print(f"  min_matches_for_loop: {current.min_matches_for_loop}")
    print()

    # Evaluate current thresholds for comparison
    # (we'd need traces here, so just show best results)

    print("Best Found Thresholds:")
    print(f"  structural_threshold: {best.structural_threshold}")
    print(f"  semantic_threshold: {best.semantic_threshold}")
    print(f"  loop_detection_window: {best.window_size}")
    print(f"  min_matches_for_loop: {best.min_matches}")
    print()

    print("Performance Metrics:")
    print(f"  Precision: {best.precision*100:.1f}%")
    print(f"  Recall:    {best.recall*100:.1f}%")
    print(f"  F1 Score:  {best.f1_score*100:.1f}%")
    print(f"  FPR:       {best.fpr*100:.1f}%")
    print()

    print("Confusion Matrix:")
    print(f"  TP={best.true_positives:3d}  FP={best.false_positives:3d}")
    print(f"  FN={best.false_negatives:3d}  TN={best.true_negatives:3d}")

    # Check if change is recommended
    struct_changed = abs(best.structural_threshold - current.structural_threshold) > 0.01
    sem_changed = abs(best.semantic_threshold - current.semantic_threshold) > 0.01
    window_changed = best.window_size != current.loop_detection_window
    min_changed = best.min_matches != current.min_matches_for_loop

    if struct_changed or sem_changed or window_changed or min_changed:
        print("\n⚠️  THRESHOLD CHANGE RECOMMENDED")
        if struct_changed:
            print(f"   structural: {current.structural_threshold} → {best.structural_threshold}")
        if sem_changed:
            print(f"   semantic: {current.semantic_threshold} → {best.semantic_threshold}")
        if window_changed:
            print(f"   window: {current.loop_detection_window} → {best.window_size}")
        if min_changed:
            print(f"   min_matches: {current.min_matches_for_loop} → {best.min_matches}")
    else:
        print("\n✅ Current thresholds are optimal")

    return {
        "framework": framework,
        "current": {
            "structural_threshold": current.structural_threshold,
            "semantic_threshold": current.semantic_threshold,
            "loop_detection_window": current.loop_detection_window,
            "min_matches_for_loop": current.min_matches_for_loop,
        },
        "recommended": {
            "structural_threshold": best.structural_threshold,
            "semantic_threshold": best.semantic_threshold,
            "loop_detection_window": best.window_size,
            "min_matches_for_loop": best.min_matches,
        },
        "metrics": {
            "precision": round(best.precision, 4),
            "recall": round(best.recall, 4),
            "f1_score": round(best.f1_score, 4),
            "fpr": round(best.fpr, 4),
        },
        "confusion_matrix": {
            "tp": best.true_positives,
            "fp": best.false_positives,
            "fn": best.false_negatives,
            "tn": best.true_negatives,
        },
        "change_recommended": struct_changed or sem_changed or window_changed or min_changed,
    }


def run_calibration(traces_dir: str, output_file: Optional[str] = None) -> Dict:
    """Run full calibration pipeline.

    Args:
        traces_dir: Directory containing labeled trace JSONL files
        output_file: Optional path to save calibration results

    Returns:
        Dict with calibration results per framework
    """
    print("=" * 60)
    print("THRESHOLD CALIBRATION PIPELINE")
    print("=" * 60)

    traces_by_framework = load_labeled_traces(traces_dir)

    if not traces_by_framework:
        print(f"\n⚠️  No traces found in {traces_dir}")
        print("Expected JSONL files with labeled traces.")
        return {}

    print(f"\nLoaded traces from {traces_dir}:")
    for fw, traces in traces_by_framework.items():
        loop_count = sum(1 for t in traces if t.has_loop)
        print(f"  {fw}: {len(traces)} traces ({loop_count} with loops)")

    results = {}

    for framework, traces in traces_by_framework.items():
        if len(traces) < 10:
            print(f"\n⚠️  Skipping {framework}: insufficient traces ({len(traces)} < 10)")
            continue

        current = FRAMEWORK_THRESHOLDS.get(framework, FRAMEWORK_THRESHOLDS["unknown"])

        best_result, all_results = grid_search_thresholds(
            traces=traces,
            framework=framework,
            current_thresholds=current,
        )

        result = print_calibration_results(
            framework=framework,
            current=current,
            best=best_result,
            num_traces=len(traces),
        )

        results[framework] = result

    # Save results if output file specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to {output_file}")

    # Generate config.py update snippet
    if results:
        print("\n" + "=" * 60)
        print("CONFIG UPDATE SNIPPET")
        print("=" * 60)
        print("# Copy these changes to backend/app/config.py:")
        print()
        for fw, result in results.items():
            if result.get("change_recommended"):
                rec = result["recommended"]
                print(f'    "{fw}": FrameworkThresholds(')
                print(f'        structural_threshold={rec["structural_threshold"]},')
                print(f'        semantic_threshold={rec["semantic_threshold"]},')
                print(f'        loop_detection_window={rec["loop_detection_window"]},')
                print(f'        min_matches_for_loop={rec["min_matches_for_loop"]},')
                print(f'        confidence_scaling=1.0,')
                print(f'    ),')
                print()

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calibrate detection thresholds from labeled traces")
    parser.add_argument("--traces", default="traces", help="Directory containing labeled traces")
    parser.add_argument("--output", default="calibration_results.json", help="Output file for results")

    args = parser.parse_args()

    run_calibration(args.traces, args.output)
