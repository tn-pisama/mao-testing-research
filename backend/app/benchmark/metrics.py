"""Metrics computation for MAST benchmarks.

Computes precision, recall, F1, confusion matrices, and calibration metrics.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.benchmark.mast_loader import ALL_FAILURE_MODES, FAILURE_MODE_NAMES

logger = logging.getLogger(__name__)


@dataclass
class ConfusionMatrix:
    """Confusion matrix for binary classification."""

    tp: int = 0  # True Positives
    tn: int = 0  # True Negatives
    fp: int = 0  # False Positives
    fn: int = 0  # False Negatives

    @property
    def total(self) -> int:
        """Total samples."""
        return self.tp + self.tn + self.fp + self.fn

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)."""
        if self.tp + self.fp == 0:
            return 0.0
        return self.tp / (self.tp + self.fp)

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)."""
        if self.tp + self.fn == 0:
            return 0.0
        return self.tp / (self.tp + self.fn)

    @property
    def f1(self) -> float:
        """F1 = 2 * precision * recall / (precision + recall)."""
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def accuracy(self) -> float:
        """Accuracy = (TP + TN) / total."""
        if self.total == 0:
            return 0.0
        return (self.tp + self.tn) / self.total

    @property
    def specificity(self) -> float:
        """Specificity = TN / (TN + FP)."""
        if self.tn + self.fp == 0:
            return 0.0
        return self.tn / (self.tn + self.fp)

    @property
    def support(self) -> int:
        """Number of positive samples (TP + FN)."""
        return self.tp + self.fn

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tp": self.tp,
            "tn": self.tn,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "specificity": round(self.specificity, 4),
            "support": self.support,
        }


@dataclass
class CalibrationBin:
    """Calibration bin for reliability diagram."""

    confidence_low: float
    confidence_high: float
    predictions: List[Tuple[float, bool]] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Number of predictions in this bin."""
        return len(self.predictions)

    @property
    def mean_confidence(self) -> float:
        """Mean predicted confidence in this bin."""
        if not self.predictions:
            return (self.confidence_low + self.confidence_high) / 2
        return sum(p[0] for p in self.predictions) / len(self.predictions)

    @property
    def accuracy(self) -> float:
        """Actual accuracy in this bin."""
        if not self.predictions:
            return 0.0
        return sum(1 for _, correct in self.predictions if correct) / len(self.predictions)

    @property
    def calibration_error(self) -> float:
        """Absolute difference between confidence and accuracy."""
        return abs(self.mean_confidence - self.accuracy)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "confidence_low": self.confidence_low,
            "confidence_high": self.confidence_high,
            "mean_confidence": round(self.mean_confidence, 4),
            "accuracy": round(self.accuracy, 4),
            "count": self.count,
            "calibration_error": round(self.calibration_error, 4),
        }


@dataclass
class FailureModeMetrics:
    """Metrics for a single failure mode."""

    failure_mode: str
    confusion_matrix: ConfusionMatrix
    calibration_bins: List[CalibrationBin] = field(default_factory=list)
    mean_latency_ms: float = 0.0

    @property
    def name(self) -> str:
        """Human-readable name for this failure mode."""
        return FAILURE_MODE_NAMES.get(self.failure_mode, self.failure_mode)

    @property
    def precision(self) -> float:
        """Precision for this mode."""
        return self.confusion_matrix.precision

    @property
    def recall(self) -> float:
        """Recall for this mode."""
        return self.confusion_matrix.recall

    @property
    def f1(self) -> float:
        """F1 for this mode."""
        return self.confusion_matrix.f1

    @property
    def accuracy(self) -> float:
        """Accuracy for this mode."""
        return self.confusion_matrix.accuracy

    @property
    def sample_count(self) -> int:
        """Total samples evaluated for this mode."""
        return self.confusion_matrix.total

    @property
    def support(self) -> int:
        """Number of positive samples for this mode."""
        return self.confusion_matrix.support

    @property
    def ece(self) -> float:
        """Expected Calibration Error."""
        if not self.calibration_bins:
            return 0.0
        total_count = sum(b.count for b in self.calibration_bins)
        if total_count == 0:
            return 0.0
        return sum(
            b.count * b.calibration_error for b in self.calibration_bins
        ) / total_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "failure_mode": self.failure_mode,
            "name": self.name,
            "confusion_matrix": self.confusion_matrix.to_dict(),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "ece": round(self.ece, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "sample_count": self.sample_count,
            "support": self.support,
        }


@dataclass
class BenchmarkMetrics:
    """Complete metrics from a benchmark run."""

    # Per-mode metrics
    by_mode: Dict[str, FailureModeMetrics] = field(default_factory=dict)

    # Aggregate metrics
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0
    micro_precision: float = 0.0
    micro_recall: float = 0.0
    micro_f1: float = 0.0
    weighted_f1: float = 0.0

    # Overall
    overall_accuracy: float = 0.0
    overall_ece: float = 0.0
    total_latency_ms: float = 0.0
    mean_latency_per_record_ms: float = 0.0
    total_records: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary": {
                "macro_precision": round(self.macro_precision, 4),
                "macro_recall": round(self.macro_recall, 4),
                "macro_f1": round(self.macro_f1, 4),
                "micro_precision": round(self.micro_precision, 4),
                "micro_recall": round(self.micro_recall, 4),
                "micro_f1": round(self.micro_f1, 4),
                "weighted_f1": round(self.weighted_f1, 4),
                "overall_accuracy": round(self.overall_accuracy, 4),
                "overall_ece": round(self.overall_ece, 4),
                "total_latency_ms": round(self.total_latency_ms, 2),
                "mean_latency_per_record_ms": round(self.mean_latency_per_record_ms, 2),
                "total_records": self.total_records,
            },
            "by_mode": {
                mode: metrics.to_dict()
                for mode, metrics in sorted(self.by_mode.items())
            },
        }


class MetricsComputer:
    """Compute metrics from benchmark results."""

    def __init__(self, num_calibration_bins: int = 10):
        """Initialize metrics computer.

        Args:
            num_calibration_bins: Number of bins for calibration computation
        """
        self.num_calibration_bins = num_calibration_bins

    def compute(
        self,
        predictions: Dict[str, Dict[str, Tuple[bool, float]]],
        ground_truths: Dict[str, Dict[str, bool]],
        latencies: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> BenchmarkMetrics:
        """Compute all metrics from predictions and ground truths.

        Args:
            predictions: Dict[record_id -> Dict[mode -> (detected, confidence)]]
            ground_truths: Dict[record_id -> Dict[mode -> ground_truth]]
            latencies: Optional Dict[record_id -> Dict[mode -> latency_ms]]

        Returns:
            BenchmarkMetrics with all computed metrics
        """
        metrics = BenchmarkMetrics()
        metrics.total_records = len(ground_truths)

        # Compute per-mode metrics
        for mode in ALL_FAILURE_MODES:
            mode_metrics = self._compute_mode_metrics(
                mode=mode,
                predictions=predictions,
                ground_truths=ground_truths,
                latencies=latencies,
            )
            if mode_metrics.sample_count > 0:
                metrics.by_mode[mode] = mode_metrics

        # Compute aggregate metrics
        self._compute_aggregates(metrics)

        return metrics

    def _compute_mode_metrics(
        self,
        mode: str,
        predictions: Dict[str, Dict[str, Tuple[bool, float]]],
        ground_truths: Dict[str, Dict[str, bool]],
        latencies: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> FailureModeMetrics:
        """Compute metrics for a single failure mode."""
        cm = ConfusionMatrix()
        calibration_data: List[Tuple[float, bool]] = []
        total_latency = 0.0
        latency_count = 0

        for record_id, gt_dict in ground_truths.items():
            gt = gt_dict.get(mode, False)
            pred_dict = predictions.get(record_id, {})

            if mode not in pred_dict:
                continue

            detected, confidence = pred_dict[mode]

            # Update confusion matrix
            if detected and gt:
                cm.tp += 1
            elif detected and not gt:
                cm.fp += 1
            elif not detected and gt:
                cm.fn += 1
            else:
                cm.tn += 1

            # Collect calibration data
            # Correct prediction if (detected and gt) or (not detected and not gt)
            is_correct = detected == gt
            calibration_data.append((confidence, is_correct))

            # Collect latency
            if latencies and record_id in latencies and mode in latencies[record_id]:
                total_latency += latencies[record_id][mode]
                latency_count += 1

        # Compute calibration bins
        calibration_bins = self._compute_calibration_bins(calibration_data)

        # Compute mean latency
        mean_latency = total_latency / latency_count if latency_count > 0 else 0.0

        return FailureModeMetrics(
            failure_mode=mode,
            confusion_matrix=cm,
            calibration_bins=calibration_bins,
            mean_latency_ms=mean_latency,
        )

    def _compute_calibration_bins(
        self,
        data: List[Tuple[float, bool]],
    ) -> List[CalibrationBin]:
        """Compute calibration bins from prediction data."""
        bins = []
        bin_width = 1.0 / self.num_calibration_bins

        for i in range(self.num_calibration_bins):
            low = i * bin_width
            high = (i + 1) * bin_width
            bin_data = CalibrationBin(confidence_low=low, confidence_high=high)

            # Add predictions that fall in this bin
            for confidence, correct in data:
                if low <= confidence < high or (i == self.num_calibration_bins - 1 and confidence == 1.0):
                    bin_data.predictions.append((confidence, correct))

            bins.append(bin_data)

        return bins

    def _compute_aggregates(self, metrics: BenchmarkMetrics) -> None:
        """Compute aggregate metrics from per-mode metrics."""
        if not metrics.by_mode:
            return

        # Collect per-mode values
        precisions = []
        recalls = []
        f1s = []
        supports = []

        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_tn = 0
        total_latency = 0.0
        total_ece = 0.0
        mode_count = 0

        for mode_metrics in metrics.by_mode.values():
            cm = mode_metrics.confusion_matrix

            # Skip modes with no samples
            if cm.total == 0:
                continue

            precisions.append(mode_metrics.precision)
            recalls.append(mode_metrics.recall)
            f1s.append(mode_metrics.f1)
            supports.append(mode_metrics.support)

            total_tp += cm.tp
            total_fp += cm.fp
            total_fn += cm.fn
            total_tn += cm.tn
            total_latency += mode_metrics.mean_latency_ms
            total_ece += mode_metrics.ece
            mode_count += 1

        # Macro averages (unweighted average across modes)
        if precisions:
            metrics.macro_precision = sum(precisions) / len(precisions)
            metrics.macro_recall = sum(recalls) / len(recalls)
            metrics.macro_f1 = sum(f1s) / len(f1s)

        # Micro averages (computed from total TP/FP/FN)
        if total_tp + total_fp > 0:
            metrics.micro_precision = total_tp / (total_tp + total_fp)
        if total_tp + total_fn > 0:
            metrics.micro_recall = total_tp / (total_tp + total_fn)
        if metrics.micro_precision + metrics.micro_recall > 0:
            metrics.micro_f1 = (
                2 * metrics.micro_precision * metrics.micro_recall /
                (metrics.micro_precision + metrics.micro_recall)
            )

        # Weighted F1 (weighted by support)
        total_support = sum(supports)
        if total_support > 0 and f1s:
            metrics.weighted_f1 = sum(
                f1 * sup for f1, sup in zip(f1s, supports)
            ) / total_support

        # Overall accuracy
        total_samples = total_tp + total_tn + total_fp + total_fn
        if total_samples > 0:
            metrics.overall_accuracy = (total_tp + total_tn) / total_samples

        # Overall ECE (average across modes)
        if mode_count > 0:
            metrics.overall_ece = total_ece / mode_count

        # Total and mean latency
        metrics.total_latency_ms = total_latency
        if metrics.total_records > 0:
            metrics.mean_latency_per_record_ms = total_latency / metrics.total_records
