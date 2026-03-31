"""TRAIL Benchmark Evaluation Metrics.

Implements TRAIL's evaluation protocol: joint accuracy (span_id + category
must both match) and per-category F1. Also includes per-impact breakdown.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CategoryMetrics:
    """Precision, recall, F1 for a single category."""

    category: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        if self.tp + self.fp == 0:
            return 0.0
        return self.tp / (self.tp + self.fp)

    @property
    def recall(self) -> float:
        if self.tp + self.fn == 0:
            return 0.0
        return self.tp / (self.tp + self.fn)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def support(self) -> int:
        return self.tp + self.fn

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "support": self.support,
        }


def compute_joint_accuracy(
    predictions: List[Tuple[str, str]],
    ground_truth: List[Tuple[str, str]],
) -> float:
    """Compute joint accuracy: both span_id AND category must match.

    This is the primary TRAIL metric. A prediction is correct only if
    both the localization (span_id) and classification (category) are right.

    Args:
        predictions: List of (span_id, category) tuples.
        ground_truth: List of (span_id, category) tuples.

    Returns:
        Fraction of ground-truth annotations correctly predicted.
    """
    if not ground_truth:
        return 1.0 if not predictions else 0.0

    gt_set: Set[Tuple[str, str]] = set(ground_truth)
    correct = sum(1 for pred in predictions if pred in gt_set)

    return correct / len(gt_set)


def compute_per_category_f1(
    predictions: List[Tuple[str, str]],
    ground_truth: List[Tuple[str, str]],
    categories: Optional[List[str]] = None,
) -> Dict[str, CategoryMetrics]:
    """Compute per-category precision, recall, and F1.

    Localization is ignored here — only the category label matters.
    Matching is done by span_id: if a prediction has the same span_id
    and same category as a ground-truth entry, it's a TP.

    Args:
        predictions: List of (span_id, category).
        ground_truth: List of (span_id, category).
        categories: List of categories to evaluate. If None, uses the
                     union of categories in predictions and ground_truth.

    Returns:
        Dict mapping category name to CategoryMetrics.
    """
    if categories is None:
        all_cats = set(cat for _, cat in predictions) | set(cat for _, cat in ground_truth)
        categories = sorted(all_cats)

    gt_set = set(ground_truth)
    pred_set = set(predictions)

    # Group by category
    gt_by_cat: Dict[str, Set[str]] = defaultdict(set)
    pred_by_cat: Dict[str, Set[str]] = defaultdict(set)
    for span_id, cat in ground_truth:
        gt_by_cat[cat].add(span_id)
    for span_id, cat in predictions:
        pred_by_cat[cat].add(span_id)

    result: Dict[str, CategoryMetrics] = {}
    for cat in categories:
        gt_spans = gt_by_cat.get(cat, set())
        pred_spans = pred_by_cat.get(cat, set())

        tp = len(gt_spans & pred_spans)
        fp = len(pred_spans - gt_spans)
        fn = len(gt_spans - pred_spans)

        result[cat] = CategoryMetrics(category=cat, tp=tp, fp=fp, fn=fn)

    return result


def compute_per_impact_breakdown(
    predictions: List[Tuple[str, str]],
    ground_truth: List[Tuple[str, str]],
    annotations: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Break down detection performance by impact level (HIGH/MEDIUM/LOW).

    Args:
        predictions: List of (span_id, category).
        ground_truth: List of (span_id, category).
        annotations: Raw annotation dicts with 'location', 'category', 'impact'.

    Returns:
        Dict mapping impact level to {accuracy, total, detected, missed}.
    """
    # Build lookup: (span_id, category) -> impact
    gt_impact: Dict[Tuple[str, str], str] = {}
    for ann in annotations:
        key = (str(ann.get("location", "")), str(ann.get("category", "")))
        gt_impact[key] = str(ann.get("impact", "MEDIUM")).upper()

    pred_set = set(predictions)

    by_impact: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "detected": 0, "missed": 0}
    )

    for gt_key in ground_truth:
        impact = gt_impact.get(gt_key, "MEDIUM")
        by_impact[impact]["total"] += 1
        if gt_key in pred_set:
            by_impact[impact]["detected"] += 1
        else:
            by_impact[impact]["missed"] += 1

    result: Dict[str, Dict[str, Any]] = {}
    for impact in ["HIGH", "MEDIUM", "LOW"]:
        data = by_impact.get(impact, {"total": 0, "detected": 0, "missed": 0})
        total = data["total"]
        detected = data["detected"]
        result[impact] = {
            "total": total,
            "detected": detected,
            "missed": data["missed"],
            "accuracy": round(detected / total, 4) if total > 0 else 0.0,
        }

    return result


def compute_macro_f1(category_metrics: Dict[str, CategoryMetrics]) -> float:
    """Compute macro-averaged F1 across categories."""
    f1_values = [m.f1 for m in category_metrics.values() if m.support > 0]
    if not f1_values:
        return 0.0
    return sum(f1_values) / len(f1_values)


def compute_micro_f1(category_metrics: Dict[str, CategoryMetrics]) -> float:
    """Compute micro-averaged F1 across categories."""
    total_tp = sum(m.tp for m in category_metrics.values())
    total_fp = sum(m.fp for m in category_metrics.values())
    total_fn = sum(m.fn for m in category_metrics.values())

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
