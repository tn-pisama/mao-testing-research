"""Detector versioning and evaluation tracking system.

Tracks detector configurations, patterns, and evaluation results over time
to enable reproducible experiments and performance comparisons.
"""

import json
import hashlib
import random
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class DetectorConfig:
    """Configuration for a single failure mode detector."""
    mode: str
    name: str
    version: str
    patterns: list[tuple[str, str]]  # (regex_pattern, issue_type)
    thresholds: dict[str, float]
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DetectorConfig":
        return cls(**data)

    def get_hash(self) -> str:
        """Generate hash of config for change detection."""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]


@dataclass
class EvaluationResult:
    """Results from evaluating a detector."""
    mode: str
    version: str
    config_hash: str
    timestamp: str

    # Confusion matrix
    tp: int  # True positives
    fp: int  # False positives
    tn: int  # True negatives
    fn: int  # False negatives

    # Computed metrics
    precision: float
    recall: float
    f1: float
    fpr: float  # False positive rate

    # Consistency metrics (from Anthropic "Demystifying evals" article)
    pass_at_k: float = 0.0  # P(at least 1 success in k trials)
    pass_caret_k: float = 0.0  # P(all k trials succeed) - consistency metric
    consistency_gap: float = 0.0  # pass_at_k - pass_caret_k (lower is better)

    # Metadata
    failure_traces: int = 0
    healthy_traces: int = 0
    frameworks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationResult":
        # Handle older results without consistency metrics
        defaults = {"pass_at_k": 0.0, "pass_caret_k": 0.0, "consistency_gap": 0.0}
        for key, default in defaults.items():
            if key not in data:
                data[key] = default
        return cls(**data)


class DetectorVersionManager:
    """Manages detector versions and evaluation history."""

    def __init__(self, base_dir: str = "detector_versions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.configs_dir = self.base_dir / "configs"
        self.configs_dir.mkdir(exist_ok=True)
        self.results_dir = self.base_dir / "results"
        self.results_dir.mkdir(exist_ok=True)
        self.history_file = self.base_dir / "evaluation_history.jsonl"

    def save_config(self, config: DetectorConfig) -> str:
        """Save a detector configuration and return its hash."""
        config_hash = config.get_hash()
        config_file = self.configs_dir / f"{config.mode}_{config.version}_{config_hash}.json"

        with open(config_file, "w") as f:
            json.dump(config.to_dict(), f, indent=2)

        return config_hash

    def load_config(self, mode: str, version: str = None) -> DetectorConfig | None:
        """Load a detector configuration."""
        pattern = f"{mode}_*.json" if version is None else f"{mode}_{version}_*.json"
        configs = sorted(self.configs_dir.glob(pattern), reverse=True)

        if not configs:
            return None

        with open(configs[0]) as f:
            return DetectorConfig.from_dict(json.load(f))

    def save_result(self, result: EvaluationResult) -> None:
        """Append evaluation result to history."""
        with open(self.history_file, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

        # Also save individual result file
        result_file = self.results_dir / f"{result.mode}_{result.version}_{result.timestamp}.json"
        with open(result_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def get_history(self, mode: str = None) -> list[EvaluationResult]:
        """Get evaluation history, optionally filtered by mode."""
        if not self.history_file.exists():
            return []

        results = []
        with open(self.history_file) as f:
            for line in f:
                if line.strip():
                    result = EvaluationResult.from_dict(json.loads(line))
                    if mode is None or result.mode == mode:
                        results.append(result)

        return results

    def get_latest_results(self) -> dict[str, EvaluationResult]:
        """Get the most recent result for each mode."""
        history = self.get_history()
        latest = {}

        for result in history:
            if result.mode not in latest or result.timestamp > latest[result.mode].timestamp:
                latest[result.mode] = result

        return latest

    def compare_versions(self, mode: str, version1: str, version2: str) -> dict:
        """Compare two versions of a detector."""
        history = self.get_history(mode)

        v1_results = [r for r in history if r.version == version1]
        v2_results = [r for r in history if r.version == version2]

        if not v1_results or not v2_results:
            return {"error": "One or both versions not found"}

        v1 = v1_results[-1]  # Most recent
        v2 = v2_results[-1]

        return {
            "mode": mode,
            "version1": version1,
            "version2": version2,
            "precision_delta": v2.precision - v1.precision,
            "recall_delta": v2.recall - v1.recall,
            "f1_delta": v2.f1 - v1.f1,
            "fpr_delta": v2.fpr - v1.fpr,
        }


def compute_metrics(tp: int, fp: int, tn: int, fn: int) -> dict:
    """Compute precision, recall, F1, and FPR from confusion matrix."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
    }


def compute_pass_at_k(results: list[bool], k: int = 3, n_samples: int = 1000) -> float:
    """Compute pass@k: probability of at least 1 success in k trials.

    This measures how likely it is that the detector will succeed at least once
    when given k chances. High pass@k means the detector can usually find the issue.

    Args:
        results: List of bool indicating success/failure for each test case
        k: Number of trials to sample
        n_samples: Number of Monte Carlo samples for estimation

    Returns:
        Estimated probability of at least 1 success in k trials
    """
    if len(results) < k or k <= 0:
        return 0.0

    successes = 0
    for _ in range(n_samples):
        sample = random.sample(results, k)
        if any(sample):  # At least one success
            successes += 1

    return round(successes / n_samples, 4)


def compute_pass_caret_k(results: list[bool], k: int = 3, n_samples: int = 1000) -> float:
    """Compute pass^k: probability of ALL k trials succeeding.

    This measures consistency/reliability. From Anthropic's "Demystifying evals"
    article: "pass^k requires every one of k trials to succeed...this is essential
    for measuring reliability and consistency."

    Args:
        results: List of bool indicating success/failure for each test case
        k: Number of trials to sample
        n_samples: Number of Monte Carlo samples for estimation

    Returns:
        Estimated probability of all k trials succeeding
    """
    if len(results) < k or k <= 0:
        return 0.0

    successes = 0
    for _ in range(n_samples):
        sample = random.sample(results, k)
        if all(sample):  # All must succeed
            successes += 1

    return round(successes / n_samples, 4)


def compute_consistency_metrics(tp: int, fp: int, tn: int, fn: int, k: int = 3) -> dict:
    """Compute pass@k and pass^k consistency metrics from confusion matrix.

    Constructs a results list from the confusion matrix and computes both metrics.
    """
    # Construct results list: TPs and TNs are successes, FPs and FNs are failures
    results = [True] * (tp + tn) + [False] * (fp + fn)

    if len(results) < k:
        return {"pass_at_k": 0.0, "pass_caret_k": 0.0, "consistency_gap": 0.0}

    pass_at_k = compute_pass_at_k(results, k)
    pass_caret_k = compute_pass_caret_k(results, k)
    consistency_gap = round(pass_at_k - pass_caret_k, 4)

    return {
        "pass_at_k": pass_at_k,
        "pass_caret_k": pass_caret_k,
        "consistency_gap": consistency_gap,
    }


def create_evaluation_result(
    mode: str,
    version: str,
    config_hash: str,
    tp: int,
    fp: int,
    tn: int,
    fn: int,
    failure_traces: int,
    healthy_traces: int,
    frameworks: list[str],
    k: int = 3,  # k for pass@k and pass^k
) -> EvaluationResult:
    """Create an evaluation result with computed metrics including consistency."""
    metrics = compute_metrics(tp, fp, tn, fn)
    consistency = compute_consistency_metrics(tp, fp, tn, fn, k)

    return EvaluationResult(
        mode=mode,
        version=version,
        config_hash=config_hash,
        timestamp=datetime.now().isoformat(),
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        precision=metrics["precision"],
        recall=metrics["recall"],
        f1=metrics["f1"],
        fpr=metrics["fpr"],
        pass_at_k=consistency["pass_at_k"],
        pass_caret_k=consistency["pass_caret_k"],
        consistency_gap=consistency["consistency_gap"],
        failure_traces=failure_traces,
        healthy_traces=healthy_traces,
        frameworks=frameworks,
    )


def print_results_table(results: dict[str, EvaluationResult], show_consistency: bool = True) -> None:
    """Print a formatted table of results.

    Args:
        results: Dict mapping mode to EvaluationResult
        show_consistency: If True, include pass@k, pass^k, and consistency gap columns
    """
    mode_names = {
        'F1': 'Specification Mismatch', 'F2': 'Task Decomposition',
        'F3': 'Resource Misalloc', 'F4': 'Tool Provision',
        'F5': 'Workflow Design', 'F6': 'Task Derailment',
        'F7': 'Context Neglect', 'F8': 'Info Withholding',
        'F9': 'Role Usurpation', 'F10': 'Communication',
        'F11': 'Coordination', 'F12': 'Output Validation',
        'F13': 'Quality Gate', 'F14': 'Completion',
    }

    if show_consistency:
        print(f"{'Mode':<5} {'Name':<18} {'Ver':<5} {'Prec':>6} {'Recall':>6} {'F1':>6} {'pass@k':>7} {'pass^k':>7} {'Gap':>5}")
        print("-" * 90)
    else:
        print(f"{'Mode':<5} {'Name':<20} {'Ver':<6} {'Prec':>7} {'Recall':>7} {'F1':>7} {'FPR':>7}")
        print("-" * 75)

    for mode in ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'F13', 'F14']:
        if mode in results:
            r = results[mode]
            name = mode_names.get(mode, mode)[:18]
            if show_consistency:
                gap_indicator = ""
                if r.consistency_gap > 0.2:
                    gap_indicator = "!"  # High gap indicates inconsistency
                print(f"{mode:<5} {name:<18} {r.version:<5} {r.precision*100:>5.1f}% {r.recall*100:>5.1f}% {r.f1*100:>5.1f}% {r.pass_at_k*100:>6.1f}% {r.pass_caret_k*100:>6.1f}% {r.consistency_gap*100:>4.1f}%{gap_indicator}")
            else:
                print(f"{mode:<5} {name:<20} {r.version:<6} {r.precision*100:>6.1f}% {r.recall*100:>6.1f}% {r.f1*100:>6.1f}% {r.fpr*100:>6.1f}%")
        else:
            if show_consistency:
                print(f"{mode:<5} {mode_names.get(mode, mode)[:18]:<18} {'N/A':<5} {'--':>6} {'--':>6} {'--':>6} {'--':>7} {'--':>7} {'--':>5}")
            else:
                print(f"{mode:<5} {mode_names.get(mode, mode)[:20]:<20} {'N/A':<6} {'--':>7} {'--':>7} {'--':>7} {'--':>7}")

    if show_consistency:
        print("\nNote: pass@k = P(>=1 success in k trials), pass^k = P(all k succeed)")
        print("      Gap = pass@k - pass^k. Lower gap indicates more consistent detector.")
        print("      '!' marks detectors with high inconsistency (gap > 20%)")
