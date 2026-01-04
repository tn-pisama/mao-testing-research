"""Detector versioning and evaluation tracking system.

Tracks detector configurations, patterns, and evaluation results over time
to enable reproducible experiments and performance comparisons.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
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

    # Metadata
    failure_traces: int
    healthy_traces: int
    frameworks: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationResult":
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
) -> EvaluationResult:
    """Create an evaluation result with computed metrics."""
    metrics = compute_metrics(tp, fp, tn, fn)

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
        failure_traces=failure_traces,
        healthy_traces=healthy_traces,
        frameworks=frameworks,
    )


def print_results_table(results: dict[str, EvaluationResult]) -> None:
    """Print a formatted table of results."""
    mode_names = {
        'F1': 'Specification Mismatch', 'F2': 'Task Decomposition',
        'F3': 'Resource Misalloc', 'F4': 'Tool Provision',
        'F5': 'Workflow Design', 'F6': 'Task Derailment',
        'F7': 'Context Neglect', 'F8': 'Info Withholding',
        'F9': 'Role Usurpation', 'F10': 'Communication',
        'F11': 'Coordination', 'F12': 'Output Validation',
        'F13': 'Quality Gate', 'F14': 'Completion',
    }

    print(f"{'Mode':<5} {'Name':<20} {'Ver':<6} {'Prec':>7} {'Recall':>7} {'F1':>7} {'FPR':>7}")
    print("-" * 75)

    for mode in ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'F13', 'F14']:
        if mode in results:
            r = results[mode]
            name = mode_names.get(mode, mode)[:20]
            print(f"{mode:<5} {name:<20} {r.version:<6} {r.precision*100:>6.1f}% {r.recall*100:>6.1f}% {r.f1*100:>6.1f}% {r.fpr*100:>6.1f}%")
        else:
            print(f"{mode:<5} {mode_names.get(mode, mode)[:20]:<20} {'N/A':<6} {'--':>7} {'--':>7} {'--':>7} {'--':>7}")
