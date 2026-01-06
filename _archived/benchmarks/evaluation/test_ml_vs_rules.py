"""Compare ML-based vs Rule-based detection on MAST benchmark.

This module provides a fair comparison between:
1. ML detector trained on MAST annotations
2. Rule-based turn-aware detectors

Uses 5-fold cross-validation for robust metrics.

Usage:
    python -m benchmarks.evaluation.test_ml_vs_rules --data-dir data/mast
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Setup paths
_BACKEND_PATH = str(Path(__file__).parent.parent.parent / "backend")
sys.path.insert(0, _BACKEND_PATH)

# Import ML detector directly to avoid init issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    'ml_detector',
    Path(__file__).parent.parent.parent / "backend/app/detection/ml_detector.py"
)
ml_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ml_module)

MLFailureDetector = ml_module.MLFailureDetector
FeatureExtractor = ml_module.FeatureExtractor
FAILURE_MODES = ml_module.FAILURE_MODES
ANNOTATION_MAP = ml_module.ANNOTATION_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ModeMetrics:
    """Metrics for a single failure mode."""
    mode: str
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        d = self.true_positives + self.false_positives
        return self.true_positives / d if d > 0 else 0.0

    @property
    def recall(self) -> float:
        d = self.true_positives + self.false_negatives
        return self.true_positives / d if d > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def load_mast_data(data_dir: Path) -> List[Dict]:
    """Load MAST dataset."""
    data_file = data_dir / "MAD_full_dataset.json"
    with open(data_file) as f:
        return json.load(f)


def get_ground_truth(record: Dict) -> Dict[str, bool]:
    """Extract ground truth labels from MAST record."""
    annotations = record.get("mast_annotation", {})
    labels = {}
    for code, mode in ANNOTATION_MAP.items():
        value = annotations.get(code, 0)
        labels[mode] = bool(value) if isinstance(value, int) else value
    return labels


def evaluate_ml_crossval(
    records: List[Dict],
    n_folds: int = 5,
    model_type: str = "random_forest",
    use_embeddings: bool = True,
) -> Dict[str, ModeMetrics]:
    """Evaluate ML detector with cross-validation.

    Args:
        records: MAST records
        n_folds: Number of CV folds
        model_type: Classifier type
        use_embeddings: Use text embeddings

    Returns:
        Metrics by failure mode
    """
    from sklearn.model_selection import KFold

    # Initialize metrics
    all_metrics = {mode: ModeMetrics(mode=mode) for mode in FAILURE_MODES}

    # Cross-validation
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
    indices = np.arange(len(records))

    for fold, (train_idx, test_idx) in enumerate(kf.split(indices)):
        logger.info(f"ML Fold {fold + 1}/{n_folds}")

        # Split data
        train_records = [records[i] for i in train_idx]
        test_records = [records[i] for i in test_idx]

        # Train detector
        detector = MLFailureDetector(
            use_embeddings=use_embeddings,
            model_type=model_type,
        )
        detector.train(train_records, test_split=0.0)  # No further split

        # Predict on test set
        predictions = detector.predict_batch(test_records)

        # Update metrics
        for i, record in enumerate(test_records):
            gt = get_ground_truth(record)
            pred = predictions[i]

            for mode in FAILURE_MODES:
                gt_val = gt.get(mode, False)
                pred_val = pred.get(mode, False)

                if gt_val and pred_val:
                    all_metrics[mode].true_positives += 1
                elif gt_val and not pred_val:
                    all_metrics[mode].false_negatives += 1
                elif not gt_val and pred_val:
                    all_metrics[mode].false_positives += 1
                else:
                    all_metrics[mode].true_negatives += 1

    return all_metrics


def evaluate_rules_baseline(records: List[Dict]) -> Dict[str, ModeMetrics]:
    """Evaluate rule-based detectors (for comparison).

    Note: This is a simplified version - the rule-based detectors
    require full conversation parsing which adds complexity.
    """
    # Import rule-based detectors
    try:
        spec2 = importlib.util.spec_from_file_location(
            'turn_aware',
            Path(__file__).parent.parent.parent / "backend/app/detection/turn_aware.py"
        )
        turn_aware = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(turn_aware)

        TurnSnapshot = turn_aware.TurnSnapshot
        DETECTORS = {
            'F1': turn_aware.TurnAwareSpecificationMismatchDetector(),
            'F3': turn_aware.TurnAwareResourceMisallocationDetector(),
            'F5': turn_aware.TurnAwareLoopDetector(),
            'F6': turn_aware.TurnAwareDerailmentDetector(),
            'F7': turn_aware.TurnAwareContextNeglectDetector(),
            'F8': turn_aware.TurnAwareInformationWithholdingDetector(),
            'F11': turn_aware.TurnAwareCoordinationFailureDetector(),
            'F12': turn_aware.TurnAwareOutputValidationDetector(),
            'F13': turn_aware.TurnAwareQualityGateBypassDetector(),
            'F14': turn_aware.TurnAwareCompletionMisjudgmentDetector(),
        }
    except Exception as e:
        logger.warning(f"Could not load rule-based detectors: {e}")
        return {}

    # Feature extractor for parsing
    extractor = FeatureExtractor(use_embeddings=False)

    all_metrics = {mode: ModeMetrics(mode=mode) for mode in DETECTORS.keys()}

    logger.info("Evaluating rule-based detectors...")

    for i, record in enumerate(records):
        if i % 100 == 0:
            logger.info(f"Rule-based: {i}/{len(records)}")

        gt = get_ground_truth(record)

        # Parse trajectory into turns
        features = extractor.extract_features(record)
        trajectory = record.get("trace", {}).get("trajectory", "")
        framework = record.get("mas_name", "")
        turns_data = extractor._parse_turns(trajectory, framework)

        # Convert to TurnSnapshots
        snapshots = []
        for j, turn in enumerate(turns_data):
            role = turn.get("role", "agent")
            participant_type = "user" if role == "user" else "agent"

            snapshot = TurnSnapshot(
                turn_number=j + 1,
                participant_type=participant_type,
                participant_id=turn.get("participant", role),
                content=turn.get("content", "")[:5000],
            )
            snapshots.append(snapshot)

        if len(snapshots) < 2:
            continue

        # Run each detector
        for mode, detector in DETECTORS.items():
            try:
                result = detector.detect(snapshots)
                pred = result.detected
            except Exception:
                pred = False

            gt_val = gt.get(mode, False)

            if gt_val and pred:
                all_metrics[mode].true_positives += 1
            elif gt_val and not pred:
                all_metrics[mode].false_negatives += 1
            elif not gt_val and pred:
                all_metrics[mode].false_positives += 1
            else:
                all_metrics[mode].true_negatives += 1

    return all_metrics


def print_comparison(ml_metrics: Dict, rules_metrics: Dict) -> None:
    """Print comparison table."""
    print("\n" + "=" * 90)
    print("ML vs RULE-BASED DETECTOR COMPARISON")
    print("=" * 90)
    print(f"{'Mode':<6} {'Name':<22} {'ML F1':>10} {'ML P':>8} {'ML R':>8} | {'Rule F1':>10} {'Rule P':>8} {'Rule R':>8}")
    print("-" * 90)

    mode_names = {
        'F1': 'Spec Mismatch', 'F2': 'Task Decomp', 'F3': 'Resource Misalloc',
        'F4': 'Tool Provision', 'F5': 'Workflow Design', 'F6': 'Derailment',
        'F7': 'Context Neglect', 'F8': 'Info Withholding', 'F9': 'Role Usurp',
        'F10': 'Comm Breakdown', 'F11': 'Coordination Fail', 'F12': 'Output Valid',
        'F13': 'Quality Gate', 'F14': 'Completion Misjudge',
    }

    ml_f1s = []
    rule_f1s = []

    for mode in FAILURE_MODES:
        name = mode_names.get(mode, mode)[:22]

        ml_m = ml_metrics.get(mode, ModeMetrics(mode=mode))
        ml_f1s.append(ml_m.f1)

        rule_m = rules_metrics.get(mode, ModeMetrics(mode=mode))
        rule_f1 = rule_m.f1 if rule_m.true_positives + rule_m.false_positives + rule_m.false_negatives > 0 else 0.0
        rule_f1s.append(rule_f1)

        rule_p = rule_m.precision
        rule_r = rule_m.recall

        print(
            f"{mode:<6} {name:<22} "
            f"{ml_m.f1 * 100:>9.1f}% {ml_m.precision * 100:>7.1f}% {ml_m.recall * 100:>7.1f}% | "
            f"{rule_f1 * 100:>9.1f}% {rule_p * 100:>7.1f}% {rule_r * 100:>7.1f}%"
        )

    print("-" * 90)
    ml_macro = np.mean(ml_f1s)
    rule_macro = np.mean([f for f in rule_f1s if f > 0]) if any(rule_f1s) else 0.0

    print(f"{'MACRO F1':<29} {ml_macro * 100:>9.1f}%{' ' * 26}| {rule_macro * 100:>9.1f}%")
    print("=" * 90)

    improvement = (ml_macro - rule_macro) / rule_macro * 100 if rule_macro > 0 else 0
    print(f"\nML improvement over rules: +{improvement:.1f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/mast"))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--model", choices=["random_forest", "gradient_boosting", "logistic"], default="random_forest")
    parser.add_argument("--no-embeddings", action="store_true")
    parser.add_argument("--skip-rules", action="store_true", help="Skip rule-based evaluation")

    args = parser.parse_args()

    # Load data
    logger.info(f"Loading data from {args.data_dir}")
    records = load_mast_data(args.data_dir)
    logger.info(f"Loaded {len(records)} records")

    # Evaluate ML with cross-validation
    logger.info(f"Running {args.folds}-fold cross-validation for ML detector...")
    ml_metrics = evaluate_ml_crossval(
        records,
        n_folds=args.folds,
        model_type=args.model,
        use_embeddings=not args.no_embeddings,
    )

    # Evaluate rule-based
    if not args.skip_rules:
        logger.info("Evaluating rule-based detectors...")
        rules_metrics = evaluate_rules_baseline(records)
    else:
        rules_metrics = {}

    # Print comparison
    print_comparison(ml_metrics, rules_metrics)

    # Save results
    output_dir = Path("benchmarks/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"ml_vs_rules_{timestamp}.json"

    results = {
        "timestamp": datetime.now().isoformat(),
        "n_records": len(records),
        "n_folds": args.folds,
        "model_type": args.model,
        "ml_metrics": {
            mode: {"f1": m.f1, "precision": m.precision, "recall": m.recall}
            for mode, m in ml_metrics.items()
        },
        "rules_metrics": {
            mode: {"f1": m.f1, "precision": m.precision, "recall": m.recall}
            for mode, m in rules_metrics.items()
        },
        "ml_macro_f1": np.mean([m.f1 for m in ml_metrics.values()]),
    }

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to {output_file}")


if __name__ == "__main__":
    main()
