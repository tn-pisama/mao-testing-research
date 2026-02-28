"""ML Detection Training Pipeline.

Bridges the golden dataset and MAST benchmark data with the ML Detector v4
training system. Provides entry points for training, evaluation, and model
management.

Usage:
    python -m app.detection_enterprise.train_pipeline --data data/mast/MAD_full_dataset.json
    python -m app.detection_enterprise.train_pipeline --golden  # Use golden dataset (augmented)
"""

import argparse
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping from DetectionType.value -> closest MAST annotation code
# ---------------------------------------------------------------------------
DETECTION_TYPE_TO_MAST: Dict[str, str] = {
    "loop": "2.1",              # F6: Task derailment (closest)
    "corruption": "1.5",        # F5: Flawed workflow
    "persona_drift": "2.4",     # F9: Role usurpation
    "hallucination": "3.1",     # F12: Output validation failure
    "injection": "1.4",         # F4: Inadequate tool (closest)
    "overflow": "1.3",          # F3: Resource misallocation
    "coordination": "2.6",      # F11: Coordination failure
    "communication": "2.5",     # F10: Communication breakdown
    "context": "2.2",           # F7: Context neglect
    "derailment": "2.1",        # F6: Task derailment
    "decomposition": "1.2",     # F2: Poor decomposition
    "workflow": "1.5",          # F5: Flawed workflow
    "withholding": "2.3",       # F8: Information withholding
    "completion": "3.3",        # F14: Completion misjudgment
    "specification": "1.1",     # F1: Spec mismatch
    "grounding": "3.1",         # F12: Output validation failure
    "retrieval_quality": "3.2", # F13: Quality gate bypass
}

# All MAST annotation codes (for building zero-vectors)
ALL_MAST_CODES = [
    "1.1", "1.2", "1.3", "1.4", "1.5",
    "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
    "3.1", "3.2", "3.3",
]

# ---------------------------------------------------------------------------
# Noise vocabulary used by augmentation
# ---------------------------------------------------------------------------
_NOISE_WORDS = [
    "additionally", "furthermore", "meanwhile", "however", "subsequently",
    "indeed", "notably", "essentially", "apparently", "presumably",
    "typically", "generally", "accordingly", "consequently", "therefore",
]


# ============================================================================
# Golden dataset -> ML detector format conversion
# ============================================================================

def _input_data_to_text(input_data: Dict[str, Any]) -> str:
    """Recursively extract all string values from input_data into a trajectory.

    Walks the nested dict/list structure and concatenates every string value
    it finds, separated by newlines.  This produces a pseudo-trajectory that
    the ML detector can embed.
    """
    parts: List[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, str):
            stripped = obj.strip()
            if stripped:
                parts.append(stripped)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item)
        # Numeric / bool scalars are converted to string only when they carry
        # domain meaning (e.g. token counts).  We stringify them to keep them
        # in the trajectory text.
        elif isinstance(obj, (int, float)):
            parts.append(str(obj))

    _walk(input_data)
    return "\n".join(parts)


def convert_golden_to_mast_format(
    entries: List[Any],
) -> List[Dict[str, Any]]:
    """Convert GoldenDatasetEntry objects to ML Detector v4 record format.

    Each golden entry becomes a record with::

        {
            "trace": {"trajectory": "<text>"},
            "mast_annotation": {"1.1": 0, "1.2": 0, ..., "<code>": 1}
        }

    The annotation code is set to 1 only when ``expected_detected`` is True
    for the entry.  Negative golden samples produce an all-zero annotation
    vector (no failure mode active).

    Args:
        entries: Iterable of ``GoldenDatasetEntry`` instances.

    Returns:
        List of records in the format expected by
        ``MultiTaskDetectorV4.train()``.
    """
    records: List[Dict[str, Any]] = []

    for entry in entries:
        # Build trajectory text from input_data
        trajectory = _input_data_to_text(entry.input_data)
        if not trajectory:
            logger.warning("Skipping entry %s: empty trajectory text", entry.id)
            continue

        # Prepend description if available for richer context
        if entry.description:
            trajectory = f"{entry.description}\n{trajectory}"

        # Build annotation vector -- all zeros by default
        annotation: Dict[str, int] = {code: 0 for code in ALL_MAST_CODES}

        if entry.expected_detected:
            # Map the DetectionType to the closest MAST code
            dt_value = entry.detection_type.value
            mast_code = DETECTION_TYPE_TO_MAST.get(dt_value)
            if mast_code:
                annotation[mast_code] = 1
            else:
                logger.warning(
                    "No MAST mapping for detection_type=%s (entry %s), "
                    "keeping all-zero annotation",
                    dt_value,
                    entry.id,
                )

        records.append({
            "trace": {"trajectory": trajectory},
            "mast_annotation": annotation,
            "_source_id": entry.id,
            "_source_type": "golden",
        })

    logger.info(
        "Converted %d golden entries to ML detector format (%d positive, %d negative)",
        len(records),
        sum(1 for r in records if any(v == 1 for v in r["mast_annotation"].values())),
        sum(1 for r in records if all(v == 0 for v in r["mast_annotation"].values())),
    )
    return records


# ============================================================================
# Simple data augmentation
# ============================================================================

def _shuffle_sentences(text: str) -> str:
    """Shuffle the sentence order within a trajectory text."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?\n])\s+', text) if s.strip()]
    if len(sentences) <= 1:
        return text
    random.shuffle(sentences)
    return " ".join(sentences)


def _drop_random_sentences(text: str, drop_ratio: float = 0.2) -> str:
    """Drop a random fraction of sentences."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?\n])\s+', text) if s.strip()]
    if len(sentences) <= 2:
        return text
    n_keep = max(1, int(len(sentences) * (1 - drop_ratio)))
    kept = random.sample(sentences, n_keep)
    return " ".join(kept)


def _add_noise_words(text: str, n_insertions: int = 3) -> str:
    """Insert random filler words at random positions."""
    words = text.split()
    if len(words) < 5:
        return text
    for _ in range(n_insertions):
        pos = random.randint(0, len(words))
        noise = random.choice(_NOISE_WORDS)
        words.insert(pos, noise)
    return " ".join(words)


def _truncate_randomly(text: str, keep_ratio_range: tuple = (0.5, 0.9)) -> str:
    """Randomly truncate the text to a fraction of its original length."""
    ratio = random.uniform(*keep_ratio_range)
    end = max(50, int(len(text) * ratio))
    return text[:end]


def augment_dataset(
    records: List[Dict[str, Any]],
    multiplier: int = 5,
    target_min: int = 200,
) -> List[Dict[str, Any]]:
    """Augment a small dataset by applying simple text transformations.

    Applies a combination of: sentence shuffling, random sentence dropping,
    noise word insertion, and random truncation.  Each original record spawns
    up to ``multiplier`` augmented variants.

    The function guarantees at least ``target_min`` total records in the
    output (original + augmented).

    Args:
        records: Original records in ML detector format.
        multiplier: Number of augmented copies per original record.
        target_min: Minimum total records to produce.

    Returns:
        Extended list of records (originals + augmented copies).
    """
    augmented: List[Dict[str, Any]] = list(records)  # keep originals

    transforms = [
        _shuffle_sentences,
        _drop_random_sentences,
        lambda t: _add_noise_words(t, n_insertions=random.randint(2, 5)),
        _truncate_randomly,
    ]

    # Decide how many augmentations are needed
    needed = max(0, target_min - len(records))
    effective_multiplier = max(multiplier, -(-needed // max(len(records), 1)))  # ceil div

    for record in records:
        trajectory = record["trace"]["trajectory"]
        for i in range(effective_multiplier):
            # Pick 1-3 random transforms and compose them
            n_transforms = random.randint(1, min(3, len(transforms)))
            chosen = random.sample(transforms, n_transforms)
            new_text = trajectory
            for fn in chosen:
                new_text = fn(new_text)

            aug_record = {
                "trace": {"trajectory": new_text},
                "mast_annotation": dict(record["mast_annotation"]),
                "_source_id": record.get("_source_id", "unknown") + f"_aug{i}",
                "_source_type": "augmented",
            }
            augmented.append(aug_record)

    logger.info(
        "Augmented dataset from %d to %d records (multiplier=%d, target_min=%d)",
        len(records),
        len(augmented),
        multiplier,
        target_min,
    )
    return augmented


# ============================================================================
# Training entry points
# ============================================================================

def train_from_mast(
    data_path: str | Path,
    output_dir: str | Path,
    epochs: int = 50,
    use_contrastive: bool = True,
) -> Dict[str, Any]:
    """Train ML Detector v4 from the MAST benchmark dataset.

    This is the primary training path.  The MAST dataset (MAD_full_dataset.json)
    contains ~300+ annotated agent traces with multi-label failure annotations.

    Args:
        data_path: Path to MAD_full_dataset.json.
        output_dir: Directory to save the trained model.
        epochs: Number of training epochs.
        use_contrastive: Whether to use contrastive fine-tuning (slower but better).

    Returns:
        Training results dict with per-mode and overall metrics.
    """
    from app.detection_enterprise.ml_detector_v4 import MultiTaskDetectorV4

    data_path = Path(data_path)
    output_dir = Path(output_dir)

    if not data_path.exists():
        raise FileNotFoundError(
            f"MAST dataset not found at {data_path}. "
            "Download it or use --golden for golden dataset training."
        )

    logger.info("Loading MAST dataset from %s", data_path)
    with open(data_path) as f:
        records = json.load(f)

    if isinstance(records, dict):
        # Handle wrapper format: {"records": [...]} or {"data": [...]}
        records = records.get("records", records.get("data", [records]))

    logger.info("Loaded %d records from MAST dataset", len(records))

    # Log annotation distribution
    code_counts: Dict[str, int] = {}
    for r in records:
        for code, val in r.get("mast_annotation", {}).items():
            if val:
                code_counts[code] = code_counts.get(code, 0) + 1
    for code in sorted(code_counts):
        logger.info("  Annotation %s: %d positive samples", code, code_counts[code])

    detector = MultiTaskDetectorV4(
        use_contrastive_finetuning=use_contrastive,
        contrastive_iterations=10 if use_contrastive else 0,
        use_chunked_encoding=True,
        chunk_size=6000,
        max_chunks=10,
        use_label_gcn=True,
        hidden_dims=[512, 256, 128],
        dropout=0.3,
        loss_type="focal",
        focal_alpha=0.25,
        focal_gamma=2.0,
        label_smoothing=0.05,
        epochs=epochs,
        batch_size=32,
        learning_rate=0.001,
        cv_folds=5,
        use_adaptive_thresholding=True,
        random_seed=42,
    )

    start_time = time.time()
    results = detector.train(records)
    elapsed = time.time() - start_time

    results["training_time_seconds"] = round(elapsed, 1)
    results["dataset_size"] = len(records)
    results["dataset_source"] = "mast"
    results["data_path"] = str(data_path)

    # Save model
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    detector.save(output_dir)

    # Save training report alongside model
    report_path = output_dir / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Training report saved to %s", report_path)

    _print_results_summary(results)
    return results


def train_from_golden(
    output_dir: str | Path,
    epochs: int = 50,
    use_contrastive: bool = True,
    augment_multiplier: int = 5,
    augment_target_min: int = 200,
    db_session=None,
) -> Dict[str, Any]:
    """Train ML Detector v4 from the golden dataset (augmented).

    The golden dataset has ~60 samples across 11 detection types -- too few
    for direct ML training.  This function augments the data to reach a
    viable training set size and then trains.

    Note: Results will be lower quality than MAST training due to the
    synthetic augmentation.  Use this primarily for rapid prototyping or
    when the MAST dataset is unavailable.

    Args:
        output_dir: Directory to save the trained model.
        epochs: Number of training epochs.
        use_contrastive: Whether to use contrastive fine-tuning.
        augment_multiplier: Augmentation copies per original sample.
        augment_target_min: Minimum total samples after augmentation.

    Returns:
        Training results dict with per-mode and overall metrics.
    """
    from app.detection_enterprise.golden_dataset import create_default_golden_dataset
    from app.detection_enterprise.ml_detector_v4 import MultiTaskDetectorV4

    output_dir = Path(output_dir)

    logger.info("Loading golden dataset")
    if db_session is not None:
        import asyncio
        from app.detection_enterprise.golden_dataset import create_default_golden_dataset_from_db
        dataset = asyncio.run(create_default_golden_dataset_from_db(db_session))
    else:
        dataset = create_default_golden_dataset()
    entries = list(dataset.entries.values())
    logger.info("Golden dataset: %d entries", len(entries))

    # Log per-type distribution
    type_counts: Dict[str, Dict[str, int]] = {}
    for e in entries:
        dt = e.detection_type.value
        if dt not in type_counts:
            type_counts[dt] = {"positive": 0, "negative": 0}
        if e.expected_detected:
            type_counts[dt]["positive"] += 1
        else:
            type_counts[dt]["negative"] += 1
    for dt in sorted(type_counts):
        counts = type_counts[dt]
        logger.info("  %s: %d positive, %d negative", dt, counts["positive"], counts["negative"])

    # Convert to ML detector format
    records = convert_golden_to_mast_format(entries)
    if not records:
        raise ValueError("No valid records after golden dataset conversion")

    # Augment to viable training size
    records = augment_dataset(
        records,
        multiplier=augment_multiplier,
        target_min=augment_target_min,
    )

    logger.info("Training on %d records (augmented from %d golden entries)", len(records), len(entries))

    detector = MultiTaskDetectorV4(
        use_contrastive_finetuning=use_contrastive,
        contrastive_iterations=5 if use_contrastive else 0,
        use_chunked_encoding=True,
        chunk_size=6000,
        max_chunks=10,
        use_label_gcn=True,
        hidden_dims=[512, 256, 128],
        dropout=0.3,
        loss_type="focal",
        focal_alpha=0.25,
        focal_gamma=2.0,
        label_smoothing=0.05,
        epochs=epochs,
        batch_size=32,
        learning_rate=0.001,
        cv_folds=5,
        use_adaptive_thresholding=True,
        random_seed=42,
    )

    start_time = time.time()
    results = detector.train(records)
    elapsed = time.time() - start_time

    results["training_time_seconds"] = round(elapsed, 1)
    results["dataset_size"] = len(records)
    results["original_golden_size"] = len(entries)
    results["dataset_source"] = "golden_augmented"
    results["augment_multiplier"] = augment_multiplier

    # Save model
    output_dir.mkdir(parents=True, exist_ok=True)
    detector.save(output_dir)

    # Save training report
    report_path = output_dir / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Training report saved to %s", report_path)

    _print_results_summary(results)
    return results


# ============================================================================
# Evaluation
# ============================================================================

def evaluate_model(
    model_dir: str | Path,
    data_path: str | Path,
) -> Dict[str, Any]:
    """Evaluate a trained ML Detector v4 model on a test dataset.

    Args:
        model_dir: Path to the saved model directory.
        data_path: Path to a JSON dataset for evaluation.

    Returns:
        Evaluation results with per-mode precision, recall, F1.
    """
    from app.detection_enterprise.ml_detector_v4 import (
        ANNOTATION_MAP,
        FAILURE_MODES,
        MultiTaskDetectorV4,
    )

    model_dir = Path(model_dir)
    data_path = Path(data_path)

    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")
    if not data_path.exists():
        raise FileNotFoundError(f"Evaluation data not found: {data_path}")

    logger.info("Loading model from %s", model_dir)
    detector = MultiTaskDetectorV4.load(model_dir)

    logger.info("Loading evaluation data from %s", data_path)
    with open(data_path) as f:
        records = json.load(f)
    if isinstance(records, dict):
        records = records.get("records", records.get("data", [records]))

    logger.info("Evaluating on %d records", len(records))

    # Extract ground-truth labels
    y_true: List[Dict[str, bool]] = []
    for r in records:
        annotations = r.get("mast_annotation", {})
        labels: Dict[str, bool] = {}
        for code, mode in ANNOTATION_MAP.items():
            labels[mode] = bool(annotations.get(code, 0))
        y_true.append(labels)

    # Predict
    start_time = time.time()
    predictions = detector.predict_batch(records)
    elapsed = time.time() - start_time

    # Compute metrics
    from sklearn.metrics import f1_score, precision_score, recall_score

    results: Dict[str, Any] = {"modes": {}}
    all_f1s = []

    for mode in FAILURE_MODES:
        true_labels = [1 if yt.get(mode, False) else 0 for yt in y_true]
        pred_labels = [1 if p[mode][0] else 0 for p in predictions]

        n_positive = sum(true_labels)
        if n_positive == 0:
            logger.info("  %s: no positive samples, skipping", mode)
            continue

        p = precision_score(true_labels, pred_labels, zero_division=0)
        r = recall_score(true_labels, pred_labels, zero_division=0)
        f1 = f1_score(true_labels, pred_labels, zero_division=0)

        results["modes"][mode] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "n_positive": n_positive,
            "n_total": len(true_labels),
        }
        all_f1s.append(f1)
        logger.info("  %s: P=%.3f R=%.3f F1=%.3f (n=%d)", mode, p, r, f1, n_positive)

    macro_f1 = float(np.mean(all_f1s)) if all_f1s else 0.0
    results["overall"] = {
        "macro_f1": round(macro_f1, 4),
        "n_modes_evaluated": len(all_f1s),
        "n_records": len(records),
        "inference_time_seconds": round(elapsed, 2),
    }

    logger.info("MACRO F1: %.3f (%d modes)", macro_f1, len(all_f1s))
    _print_results_summary(results)
    return results


# ============================================================================
# Reporting helpers
# ============================================================================

def _print_results_summary(results: Dict[str, Any]) -> None:
    """Print a formatted results summary to stdout."""
    print()
    print("=" * 64)
    print("  ML DETECTOR v4 -- TRAINING / EVALUATION REPORT")
    print("=" * 64)

    if "dataset_source" in results:
        print(f"  Source:           {results['dataset_source']}")
    if "dataset_size" in results:
        print(f"  Dataset size:     {results['dataset_size']}")
    if "original_golden_size" in results:
        print(f"  Golden originals: {results['original_golden_size']}")
    if "training_time_seconds" in results:
        print(f"  Training time:    {results['training_time_seconds']}s")

    print("-" * 64)
    print(f"  {'Mode':<10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 64)

    for mode, metrics in sorted(results.get("modes", {}).items()):
        p = metrics.get("precision", 0)
        r = metrics.get("recall", 0)
        f1 = metrics.get("f1", 0)
        print(f"  {mode:<10} {p:>10.1%} {r:>10.1%} {f1:>10.1%}")

    print("-" * 64)
    overall = results.get("overall", {})
    macro_f1 = overall.get("macro_f1", 0)
    print(f"  {'MACRO F1':<10} {'':>10} {'':>10} {macro_f1:>10.1%}")
    print("=" * 64)
    print()


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    """CLI entry point for the training pipeline."""
    parser = argparse.ArgumentParser(
        description="ML Detector v4 Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Train from MAST benchmark dataset (primary)\n"
            "  python -m app.detection_enterprise.train_pipeline "
            "--data data/mast/MAD_full_dataset.json\n\n"
            "  # Train from golden dataset (augmented, for prototyping)\n"
            "  python -m app.detection_enterprise.train_pipeline --golden\n\n"
            "  # Evaluate a saved model\n"
            "  python -m app.detection_enterprise.train_pipeline "
            "--evaluate data/models/ml_detector_v4 "
            "--data data/mast/MAD_full_dataset.json\n"
        ),
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Path to MAST data file (MAD_full_dataset.json)",
    )
    parser.add_argument(
        "--golden",
        action="store_true",
        default=False,
        help="Train from the golden dataset (augmented). "
             "Use when MAST dataset is unavailable.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/models/ml_detector_v4",
        help="Directory to save trained model (default: data/models/ml_detector_v4)",
    )
    parser.add_argument(
        "--evaluate",
        type=str,
        default=None,
        metavar="MODEL_DIR",
        help="Evaluate a trained model instead of training. "
             "Requires --data for the test set.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Training epochs (default: 50)",
    )
    parser.add_argument(
        "--no-contrastive",
        action="store_true",
        default=False,
        help="Disable contrastive fine-tuning (faster training, lower quality)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    use_contrastive = not args.no_contrastive

    # --- Evaluate mode ---
    if args.evaluate:
        if not args.data:
            parser.error("--evaluate requires --data <test_data_path>")
        results = evaluate_model(model_dir=args.evaluate, data_path=args.data)
        return

    # --- Training mode ---
    if not args.data and not args.golden:
        parser.error("Specify --data <path> for MAST training or --golden for golden dataset training")

    if args.golden:
        logger.info("Training from golden dataset (augmented)")
        results = train_from_golden(
            output_dir=args.output_dir,
            epochs=args.epochs,
            use_contrastive=use_contrastive,
        )
    else:
        logger.info("Training from MAST dataset: %s", args.data)
        results = train_from_mast(
            data_path=args.data,
            output_dir=args.output_dir,
            epochs=args.epochs,
            use_contrastive=use_contrastive,
        )


if __name__ == "__main__":
    main()
