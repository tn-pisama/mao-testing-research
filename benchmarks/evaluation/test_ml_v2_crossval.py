"""Cross-validation evaluation for ML detector v2.

Runs 5-fold CV to get reliable performance estimates.
"""

import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np

# Import v2 detector
import importlib.util
spec = importlib.util.spec_from_file_location(
    'ml_v2',
    Path(__file__).parent.parent.parent / "backend/app/detection/ml_detector_v2.py"
)
ml_v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ml_v2)

AdvancedMLDetector = ml_v2.AdvancedMLDetector
FAILURE_MODES = ml_v2.FAILURE_MODES
ANNOTATION_MAP = ml_v2.ANNOTATION_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ModeMetrics:
    mode: str
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d > 0 else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def get_labels(record: Dict) -> Dict[str, bool]:
    annotations = record.get("mast_annotation", {})
    labels = {}
    for code, mode in ANNOTATION_MAP.items():
        value = annotations.get(code, 0)
        labels[mode] = bool(value) if isinstance(value, int) else value
    return labels


def run_crossval(
    records: List[Dict],
    n_folds: int = 5,
    model_type: str = "xgboost",
) -> Dict[str, ModeMetrics]:
    """Run cross-validation."""
    from sklearn.model_selection import KFold

    metrics = {mode: ModeMetrics(mode=mode) for mode in FAILURE_MODES}
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
    indices = np.arange(len(records))

    for fold, (train_idx, test_idx) in enumerate(kf.split(indices)):
        logger.info(f"Fold {fold + 1}/{n_folds}")

        train_records = [records[i] for i in train_idx]
        test_records = [records[i] for i in test_idx]

        # Train
        detector = AdvancedMLDetector(
            model_type=model_type,
            use_embeddings=True,
            use_tfidf=True,
            use_smote=True,
        )
        detector.train(train_records, test_split=0.0)

        # Predict
        predictions = detector.predict_batch(test_records)

        # Update metrics
        for i, record in enumerate(test_records):
            gt = get_labels(record)
            pred = predictions[i]

            for mode in FAILURE_MODES:
                gt_val = gt.get(mode, False)
                pred_val = pred.get(mode, False)

                if gt_val and pred_val:
                    metrics[mode].tp += 1
                elif gt_val and not pred_val:
                    metrics[mode].fn += 1
                elif not gt_val and pred_val:
                    metrics[mode].fp += 1
                else:
                    metrics[mode].tn += 1

    return metrics


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/mast"))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--model", default="xgboost")

    args = parser.parse_args()

    # Load data
    data_file = args.data_dir / "MAD_full_dataset.json"
    with open(data_file) as f:
        records = json.load(f)
    logger.info(f"Loaded {len(records)} records")

    # Run CV
    metrics = run_crossval(records, n_folds=args.folds, model_type=args.model)

    # Print results
    print("\n" + "=" * 70)
    print(f"ML DETECTOR v2 - {args.folds}-FOLD CROSS-VALIDATION")
    print("=" * 70)
    print(f"{'Mode':<6} {'Name':<25} {'F1':>8} {'Prec':>8} {'Recall':>8}")
    print("-" * 70)

    mode_names = {
        'F1': 'Specification Mismatch', 'F2': 'Task Decomposition',
        'F3': 'Resource Misallocation', 'F4': 'Tool Provision',
        'F5': 'Flawed Workflow Design', 'F6': 'Task Derailment',
        'F7': 'Context Neglect', 'F8': 'Information Withholding',
        'F9': 'Role Usurpation', 'F10': 'Communication Breakdown',
        'F11': 'Coordination Failure', 'F12': 'Output Validation',
        'F13': 'Quality Gate Bypass', 'F14': 'Completion Misjudgment',
    }

    f1_scores = []
    for mode in FAILURE_MODES:
        m = metrics[mode]
        name = mode_names.get(mode, mode)[:25]
        if m.tp + m.fn > 0:  # Has positive samples
            f1_scores.append(m.f1)
            print(f"{mode:<6} {name:<25} {m.f1*100:>7.1f}% {m.precision*100:>7.1f}% {m.recall*100:>7.1f}%")
        else:
            print(f"{mode:<6} {name:<25} {'N/A':>8} {'N/A':>8} {'N/A':>8}")

    print("-" * 70)
    macro_f1 = np.mean(f1_scores)
    print(f"{'MACRO F1':<32} {macro_f1*100:>7.1f}%")
    print("=" * 70)

    # Save results
    output_dir = Path("benchmarks/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"ml_v2_cv_{timestamp}.json"

    results = {
        "timestamp": datetime.now().isoformat(),
        "model_type": args.model,
        "n_folds": args.folds,
        "n_records": len(records),
        "macro_f1": macro_f1,
        "modes": {
            mode: {"f1": m.f1, "precision": m.precision, "recall": m.recall}
            for mode, m in metrics.items()
        },
    }

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to {output_file}")

    return macro_f1


if __name__ == "__main__":
    main()
