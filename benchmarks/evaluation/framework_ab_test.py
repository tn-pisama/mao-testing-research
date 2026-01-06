"""A/B Test: Framework-Aware vs Generic Detection.

Compares detection accuracy between:
- Generic detection (global thresholds)
- Framework-aware detection (per-framework thresholds)

Usage:
    python -m benchmarks.evaluation.framework_ab_test
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.config import get_framework_thresholds, FRAMEWORK_THRESHOLDS
from app.detection.loop import MultiLevelLoopDetector, StateSnapshot


@dataclass
class DetectionResult:
    """Result from a single detection run."""
    trace_id: str
    framework: str
    detected: bool
    confidence: float
    method: Optional[str]
    actual_failure: bool  # Ground truth


@dataclass
class ABTestResults:
    """Results from A/B test comparison."""
    framework: str
    generic_tp: int = 0
    generic_fp: int = 0
    generic_tn: int = 0
    generic_fn: int = 0
    aware_tp: int = 0
    aware_fp: int = 0
    aware_tn: int = 0
    aware_fn: int = 0

    @property
    def generic_precision(self) -> float:
        if self.generic_tp + self.generic_fp == 0:
            return 0.0
        return self.generic_tp / (self.generic_tp + self.generic_fp)

    @property
    def generic_recall(self) -> float:
        if self.generic_tp + self.generic_fn == 0:
            return 0.0
        return self.generic_tp / (self.generic_tp + self.generic_fn)

    @property
    def generic_f1(self) -> float:
        p, r = self.generic_precision, self.generic_recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def aware_precision(self) -> float:
        if self.aware_tp + self.aware_fp == 0:
            return 0.0
        return self.aware_tp / (self.aware_tp + self.aware_fp)

    @property
    def aware_recall(self) -> float:
        if self.aware_tp + self.aware_fn == 0:
            return 0.0
        return self.aware_tp / (self.aware_tp + self.aware_fn)

    @property
    def aware_f1(self) -> float:
        p, r = self.aware_precision, self.aware_recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def improvement(self) -> float:
        """F1 improvement from aware vs generic."""
        return self.aware_f1 - self.generic_f1


def load_traces_with_labels(traces_dir: Path) -> List[Dict]:
    """Load trace files with ground truth labels.

    Expected format: JSONL files where each line has:
    - states: List of state snapshots
    - framework: Detected/labeled framework
    - is_failure: Boolean ground truth label
    - failure_mode: e.g., "F5" for workflow failures
    """
    traces = []

    for file_path in traces_dir.glob("*.jsonl"):
        with open(file_path) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    trace = json.loads(line)
                    # Only include traces with loop-related failures or healthy
                    if trace.get("failure_mode") in ["F5", "healthy", None]:
                        traces.append(trace)
                except json.JSONDecodeError:
                    continue

    return traces


def create_state_snapshots(trace: Dict) -> List[StateSnapshot]:
    """Convert trace dict to StateSnapshot list."""
    snapshots = []

    states = trace.get("states", [])
    if not states:
        # Try to extract from other formats
        messages = trace.get("messages", [])
        for i, msg in enumerate(messages):
            content = msg.get("content", "") or str(msg)
            snapshots.append(StateSnapshot(
                agent_id=msg.get("agent_id", "default"),
                state_delta={"content": content},
                content=content,
                sequence_num=i,
            ))
        return snapshots

    for i, state in enumerate(states):
        if isinstance(state, dict):
            content = state.get("content", "") or str(state.get("state_delta", {}))
            snapshots.append(StateSnapshot(
                agent_id=state.get("agent_id", "default"),
                state_delta=state.get("state_delta", state),
                content=content,
                sequence_num=state.get("sequence_num", i),
            ))

    return snapshots


def run_detection(snapshots: List[StateSnapshot], framework: Optional[str], use_framework_aware: bool) -> tuple:
    """Run detection and return (detected, confidence, method)."""
    if use_framework_aware and framework:
        detector = MultiLevelLoopDetector.for_framework(framework)
    else:
        detector = MultiLevelLoopDetector()  # Generic defaults

    result = detector.detect_loop(snapshots)
    return result.detected, result.confidence, result.method


def run_ab_test(traces: List[Dict]) -> Dict[str, ABTestResults]:
    """Run A/B test comparing generic vs framework-aware detection."""
    results_by_framework: Dict[str, ABTestResults] = defaultdict(lambda: ABTestResults(framework=""))

    for trace in traces:
        framework = trace.get("framework", "unknown")
        is_failure = trace.get("is_failure", False) or trace.get("failure_mode") not in [None, "healthy"]

        if framework not in results_by_framework:
            results_by_framework[framework] = ABTestResults(framework=framework)

        results = results_by_framework[framework]

        snapshots = create_state_snapshots(trace)
        if len(snapshots) < 3:
            continue

        # Generic detection
        generic_detected, _, _ = run_detection(snapshots, framework, use_framework_aware=False)

        # Framework-aware detection
        aware_detected, _, _ = run_detection(snapshots, framework, use_framework_aware=True)

        # Update generic stats
        if generic_detected and is_failure:
            results.generic_tp += 1
        elif generic_detected and not is_failure:
            results.generic_fp += 1
        elif not generic_detected and is_failure:
            results.generic_fn += 1
        else:
            results.generic_tn += 1

        # Update aware stats
        if aware_detected and is_failure:
            results.aware_tp += 1
        elif aware_detected and not is_failure:
            results.aware_fp += 1
        elif not aware_detected and is_failure:
            results.aware_fn += 1
        else:
            results.aware_tn += 1

    return dict(results_by_framework)


def print_results(results: Dict[str, ABTestResults]):
    """Print A/B test results in table format."""
    print("\n" + "=" * 80)
    print("FRAMEWORK-AWARE VS GENERIC DETECTION A/B TEST RESULTS")
    print("=" * 80)

    print("\n{:<12} | {:^20} | {:^20} | {:^10}".format(
        "Framework", "Generic F1", "Aware F1", "Δ F1"
    ))
    print("-" * 70)

    total_generic_f1 = 0
    total_aware_f1 = 0
    framework_count = 0

    for framework, r in sorted(results.items()):
        if r.generic_tp + r.generic_fn + r.aware_tp + r.aware_fn == 0:
            continue

        delta = r.improvement
        delta_str = f"+{delta:.1%}" if delta > 0 else f"{delta:.1%}"
        color = "\033[92m" if delta > 0 else "\033[91m" if delta < 0 else ""
        reset = "\033[0m" if delta != 0 else ""

        print("{:<12} | {:^20.1%} | {:^20.1%} | {}{:^10}{}".format(
            framework,
            r.generic_f1,
            r.aware_f1,
            color,
            delta_str,
            reset,
        ))

        total_generic_f1 += r.generic_f1
        total_aware_f1 += r.aware_f1
        framework_count += 1

    if framework_count > 0:
        print("-" * 70)
        avg_improvement = (total_aware_f1 - total_generic_f1) / framework_count
        print("{:<12} | {:^20.1%} | {:^20.1%} | {:^10}".format(
            "AVERAGE",
            total_generic_f1 / framework_count,
            total_aware_f1 / framework_count,
            f"+{avg_improvement:.1%}" if avg_improvement > 0 else f"{avg_improvement:.1%}",
        ))

    print("\n" + "=" * 80)
    print("DETAILED BREAKDOWN BY FRAMEWORK")
    print("=" * 80)

    for framework, r in sorted(results.items()):
        thresholds = get_framework_thresholds(framework)
        print(f"\n{framework.upper()}")
        print(f"  Thresholds: structural={thresholds.structural_threshold}, semantic={thresholds.semantic_threshold}")
        print(f"  Window: {thresholds.loop_detection_window}, Min matches: {thresholds.min_matches_for_loop}")
        print(f"  Generic:  TP={r.generic_tp}, FP={r.generic_fp}, TN={r.generic_tn}, FN={r.generic_fn}")
        print(f"            Precision={r.generic_precision:.1%}, Recall={r.generic_recall:.1%}, F1={r.generic_f1:.1%}")
        print(f"  Aware:    TP={r.aware_tp}, FP={r.aware_fp}, TN={r.aware_tn}, FN={r.aware_fn}")
        print(f"            Precision={r.aware_precision:.1%}, Recall={r.aware_recall:.1%}, F1={r.aware_f1:.1%}")


def main():
    """Run A/B test on available trace data."""
    traces_dir = Path(__file__).parent.parent.parent / "traces"

    if not traces_dir.exists():
        print(f"Traces directory not found: {traces_dir}")
        print("Please ensure trace files exist in the traces/ directory.")
        return

    print(f"Loading traces from: {traces_dir}")
    traces = load_traces_with_labels(traces_dir)

    if not traces:
        print("No traces found with loop-related failures or healthy labels.")
        print("Creating synthetic test data for demonstration...")
        traces = create_synthetic_test_data()

    print(f"Loaded {len(traces)} traces for A/B testing")

    # Count by framework
    framework_counts = defaultdict(int)
    for t in traces:
        framework_counts[t.get("framework", "unknown")] += 1
    print("Traces by framework:", dict(framework_counts))

    results = run_ab_test(traces)
    print_results(results)


def create_synthetic_test_data() -> List[Dict]:
    """Create synthetic test data for demonstration when no traces exist."""
    traces = []

    # LangGraph traces - structural loops are common
    for i in range(20):
        is_loop = i < 10  # 50% loops
        states = []
        for j in range(10):
            if is_loop and j >= 5:
                # Repeat state pattern
                states.append({
                    "agent_id": "agent_1",
                    "state_delta": {"step": 5, "action": "search"},
                    "content": "Searching for information..."
                })
            else:
                states.append({
                    "agent_id": "agent_1",
                    "state_delta": {"step": j, "action": f"step_{j}"},
                    "content": f"Executing step {j}"
                })
        traces.append({
            "trace_id": f"langgraph_{i}",
            "framework": "langgraph",
            "states": states,
            "is_failure": is_loop,
            "failure_mode": "F5" if is_loop else "healthy",
        })

    # AutoGen traces - semantic loops in conversation
    for i in range(20):
        is_loop = i < 8  # 40% loops
        messages = []
        for j in range(12):
            if is_loop and j >= 6:
                # Semantic repetition
                messages.append({
                    "agent_id": ["assistant", "user"][j % 2],
                    "content": "Let me search for that information again.",
                })
            else:
                messages.append({
                    "agent_id": ["assistant", "user"][j % 2],
                    "content": f"Message {j}: discussing topic {j}",
                })
        traces.append({
            "trace_id": f"autogen_{i}",
            "framework": "autogen",
            "messages": messages,
            "is_failure": is_loop,
            "failure_mode": "F5" if is_loop else "healthy",
        })

    # CrewAI traces - task handoff patterns
    for i in range(15):
        is_loop = i < 6  # 40% loops
        states = []
        for j in range(8):
            if is_loop and j >= 4:
                states.append({
                    "agent_id": f"agent_{j % 2}",
                    "state_delta": {"task": "research", "status": "pending"},
                    "content": "Handing off research task...",
                })
            else:
                states.append({
                    "agent_id": f"agent_{j % 3}",
                    "state_delta": {"task": f"task_{j}", "status": "complete"},
                    "content": f"Completed task {j}",
                })
        traces.append({
            "trace_id": f"crewai_{i}",
            "framework": "crewai",
            "states": states,
            "is_failure": is_loop,
            "failure_mode": "F5" if is_loop else "healthy",
        })

    return traces


if __name__ == "__main__":
    main()
