"""Calibration experiment tracking — stores calibration runs for comparison.

Each calibration run is stored as a single line in a JSONL file with full
metrics, dataset hash, and metadata for reproducibility.
"""

import hashlib
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Default history file location
DEFAULT_HISTORY_PATH = Path(__file__).parent.parent.parent / "data" / "calibration_history.jsonl"


@dataclass
class CalibrationExperiment:
    """A single calibration experiment record."""
    id: str
    timestamp: str
    golden_dataset_size: int
    golden_dataset_hash: str
    detector_count: int
    results: Dict[str, Any]
    average_f1: float
    below_target_count: int  # Detectors below F1=0.70
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compare(self, other: "CalibrationExperiment") -> Dict[str, Any]:
        """Compare this experiment with another, returning per-detector deltas."""
        deltas = {}
        for dtype in set(self.results) | set(other.results):
            this_f1 = self.results.get(dtype, {}).get("f1", 0.0)
            other_f1 = other.results.get(dtype, {}).get("f1", 0.0)
            delta = this_f1 - other_f1
            if abs(delta) > 0.001:
                deltas[dtype] = {
                    "current_f1": this_f1,
                    "previous_f1": other_f1,
                    "delta": round(delta, 4),
                }
        return {
            "avg_f1_delta": round(self.average_f1 - other.average_f1, 4),
            "below_target_delta": self.below_target_count - other.below_target_count,
            "detector_deltas": deltas,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationExperiment":
        return cls(**data)


def _get_git_commit() -> Optional[str]:
    """Get current git commit hash, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _compute_dataset_hash(report: Dict[str, Any]) -> str:
    """Compute a reproducibility hash from calibration results."""
    # Hash the sorted results keys + sample counts for reproducibility
    items = []
    for dtype, metrics in sorted(report.get("results", {}).items()):
        items.append(f"{dtype}:{metrics.get('sample_count', 0)}")
    content = "|".join(items)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def create_experiment_from_report(report: Dict[str, Any]) -> CalibrationExperiment:
    """Create a CalibrationExperiment from a calibrate_all() report."""
    results = report.get("results", {})
    f1_values = [m["f1"] for m in results.values()]
    avg_f1 = sum(f1_values) / len(f1_values) if f1_values else 0.0
    below_target = sum(1 for f1 in f1_values if f1 < 0.70)

    total_samples = sum(m.get("sample_count", 0) for m in results.values())

    return CalibrationExperiment(
        id=f"cal_{hashlib.sha256(report['calibrated_at'].encode()).hexdigest()[:12]}",
        timestamp=report["calibrated_at"],
        golden_dataset_size=total_samples,
        golden_dataset_hash=_compute_dataset_hash(report),
        detector_count=report.get("detector_count", len(results)),
        results=results,
        average_f1=round(avg_f1, 4),
        below_target_count=below_target,
        metadata={
            "git_commit": _get_git_commit(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "skipped": report.get("skipped", []),
            "llm_cost_summary": report.get("llm_cost_summary", {}),
        },
    )


class CalibrationHistory:
    """Manages calibration experiment history stored as JSONL."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_HISTORY_PATH

    def append(self, experiment: CalibrationExperiment) -> None:
        """Append an experiment to the history file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(experiment.to_dict(), default=str) + "\n")
        logger.info("Appended experiment %s to %s", experiment.id, self.path)

    def load_all(self) -> List[CalibrationExperiment]:
        """Load all experiments from history."""
        if not self.path.exists():
            return []

        experiments = []
        with open(self.path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    experiments.append(CalibrationExperiment.from_dict(data))
                except (json.JSONDecodeError, TypeError, KeyError) as exc:
                    logger.warning("Skipping malformed line %d: %s", line_num, exc)

        return experiments

    def load_recent(self, n: int = 5) -> List[CalibrationExperiment]:
        """Load the N most recent experiments."""
        all_experiments = self.load_all()
        return all_experiments[-n:]

    def compare_latest(self, n: int = 1) -> Optional[Dict[str, Any]]:
        """Compare the latest experiment against the nth-previous one.

        Args:
            n: How many experiments back to compare against (1 = previous run).

        Returns:
            Comparison dict, or None if not enough history.
        """
        experiments = self.load_all()
        if len(experiments) < n + 1:
            return None

        current = experiments[-1]
        previous = experiments[-(n + 1)]
        return {
            "current": {"id": current.id, "timestamp": current.timestamp, "avg_f1": current.average_f1},
            "previous": {"id": previous.id, "timestamp": previous.timestamp, "avg_f1": previous.average_f1},
            "comparison": current.compare(previous),
        }

    def format_comparison(self, n: int = 3) -> str:
        """Format a human-readable comparison of recent experiments."""
        experiments = self.load_recent(n + 1)
        if not experiments:
            return "No calibration history available."

        lines = []
        lines.append("=" * 72)
        lines.append("  CALIBRATION EXPERIMENT HISTORY")
        lines.append("=" * 72)

        for exp in reversed(experiments):
            lines.append(f"\n  [{exp.id}] {exp.timestamp}")
            lines.append(f"    avg_f1={exp.average_f1:.4f}, below_target={exp.below_target_count}/{exp.detector_count}")
            lines.append(f"    dataset_size={exp.golden_dataset_size}, hash={exp.golden_dataset_hash}")
            if exp.metadata.get("git_commit"):
                lines.append(f"    git_commit={exp.metadata['git_commit']}")
            llm_cost = exp.metadata.get("llm_cost_summary", {})
            if llm_cost.get("total_escalations", 0) > 0:
                lines.append(f"    llm_cost=${llm_cost['total_cost_usd']:.4f} ({llm_cost['total_escalations']} escalations)")

        if len(experiments) >= 2:
            current = experiments[-1]
            previous = experiments[-2]
            comparison = current.compare(previous)

            lines.append(f"\n  DELTA (latest vs previous):")
            lines.append(f"    avg_f1: {comparison['avg_f1_delta']:+.4f}")
            lines.append(f"    below_target: {comparison['below_target_delta']:+d}")

            if comparison["detector_deltas"]:
                lines.append(f"\n    Per-detector changes:")
                for dtype, delta in sorted(
                    comparison["detector_deltas"].items(),
                    key=lambda x: abs(x[1]["delta"]),
                    reverse=True,
                ):
                    lines.append(
                        f"      {dtype}: {delta['previous_f1']:.4f} → {delta['current_f1']:.4f} ({delta['delta']:+.4f})"
                    )

        lines.append("\n" + "=" * 72)
        return "\n".join(lines)
