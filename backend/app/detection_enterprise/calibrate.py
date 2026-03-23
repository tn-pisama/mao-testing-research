"""Threshold calibration for detection algorithms using the golden dataset.

Runs each detector against its golden test samples, finds optimal confidence
thresholds via grid search, and reports precision/recall/F1 metrics.
"""

import hashlib
import json
import logging
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import (
    create_default_golden_dataset,
    GoldenDatasetEntry,
)

# Lazy import for DB-backed dataset (avoids circular imports at module level)
_db_golden_dataset_factory = None

def _get_golden_dataset(db_session=None, tenant_id=None):
    """Get the golden dataset, preferring DB when a session is available.

    Loads hardcoded entries first, then merges any additional entries from
    the expanded JSON file (which contains LLM-generated samples).
    """
    if db_session is not None:
        import asyncio
        from app.detection_enterprise.golden_dataset import create_default_golden_dataset_from_db
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                dataset = loop.run_in_executor(
                    pool,
                    lambda: asyncio.run(create_default_golden_dataset_from_db(db_session, tenant_id)),
                )
                return asyncio.get_event_loop().run_until_complete(dataset)
        except RuntimeError:
            return asyncio.run(create_default_golden_dataset_from_db(db_session, tenant_id))

    dataset = create_default_golden_dataset()

    # Merge additional entries from the expanded JSON file (LLM-generated samples)
    expanded_path = Path(__file__).parent.parent.parent / "data" / "golden_dataset_expanded.json"
    if expanded_path.exists():
        try:
            before = len(dataset.entries)
            dataset.load_json(expanded_path)
            added = len(dataset.entries) - before
            if added > 0:
                logger.info(f"Loaded {added} additional entries from {expanded_path.name} (total: {len(dataset.entries)})")
        except Exception as e:
            logger.warning(f"Failed to load expanded golden dataset: {e}")

    return dataset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Grid search threshold range: 0.10, 0.15, 0.20, ... , 0.85, 0.90
# ---------------------------------------------------------------------------
THRESHOLD_GRID: List[float] = [round(0.1 + i * 0.05, 2) for i in range(17)]


# ---------------------------------------------------------------------------
# Dataclass for per-detector calibration results
# ---------------------------------------------------------------------------
@dataclass
class CalibrationResult:
    """Calibration metrics for a single detector type."""
    detection_type: str
    optimal_threshold: float
    precision: float
    recall: float
    f1: float
    sample_count: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    ece: float = 0.0
    calibrated_ece: float = 0.0
    f1_ci_lower: float = 0.0
    f1_ci_upper: float = 0.0


@dataclass
class SamplePrediction:
    """Per-sample prediction from a calibration run for error analysis."""
    entry_id: str
    detection_type: str
    expected: bool
    predicted: bool          # after threshold application
    raw_detected: bool       # raw detector output (before threshold)
    confidence: float
    threshold_used: float
    classification: str      # "TP" | "TN" | "FP" | "FN"
    description: str
    tags: List[str]
    difficulty: str
    input_data_summary: str  # truncated to 500 chars


def _build_sample_predictions(
    entries: List[GoldenDatasetEntry],
    predictions: List[Tuple[bool, float]],
    ground_truths: List[bool],
    detection_type: DetectionType,
    threshold: float,
) -> List[SamplePrediction]:
    """Classify every sample as TP/TN/FP/FN at the given threshold."""
    result = []
    for idx, entry in enumerate(entries):
        detected, confidence = predictions[idx]
        predicted_pos = detected and confidence >= threshold
        expected = ground_truths[idx]
        cls = (
            "TP" if expected and predicted_pos else
            "FN" if expected and not predicted_pos else
            "FP" if not expected and predicted_pos else
            "TN"
        )
        result.append(SamplePrediction(
            entry_id=entry.id,
            detection_type=detection_type.value,
            expected=expected,
            predicted=predicted_pos,
            raw_detected=detected,
            confidence=confidence,
            threshold_used=threshold,
            classification=cls,
            description=entry.description,
            tags=entry.tags,
            difficulty=entry.difficulty,
            input_data_summary=str(entry.input_data)[:500],
        ))
    return result


def _compute_latency_stats(latencies_ms: List[float]) -> Dict[str, float]:
    """Compute latency statistics from per-sample timing data.

    Excludes zero-latency entries (detector failures) from mean/p95 but
    includes them in total.
    """
    if not latencies_ms:
        return {"mean_ms": 0.0, "p95_ms": 0.0, "total_ms": 0.0}
    # Filter out failed runs (0.0ms) for percentile calculation
    valid = [lat for lat in latencies_ms if lat > 0.01]
    if not valid:
        return {"mean_ms": 0.0, "p95_ms": 0.0, "total_ms": round(sum(latencies_ms), 2)}
    sorted_lat = sorted(valid)
    p95_idx = min(int(0.95 * len(sorted_lat)), len(sorted_lat) - 1)
    return {
        "mean_ms": round(sum(sorted_lat) / len(sorted_lat), 2),
        "p95_ms": round(sorted_lat[p95_idx], 2),
        "total_ms": round(sum(latencies_ms), 2),
    }


def _compute_difficulty_breakdown(
    sample_preds: List[SamplePrediction],
) -> Dict[str, Dict[str, Any]]:
    """Break down P/R/F1 by difficulty level (easy/medium/hard)."""
    by_diff: Dict[str, List[SamplePrediction]] = {}
    for sp in sample_preds:
        by_diff.setdefault(sp.difficulty, []).append(sp)

    result = {}
    for diff, preds in sorted(by_diff.items()):
        tp = sum(1 for p in preds if p.classification == "TP")
        fp = sum(1 for p in preds if p.classification == "FP")
        fn = sum(1 for p in preds if p.classification == "FN")
        tn = sum(1 for p in preds if p.classification == "TN")
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        result[diff] = {
            "f1": round(f1, 4), "precision": round(p, 4), "recall": round(r, 4),
            "n": len(preds), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        }
    return result


# Detector adapters and LLM prompt builder (extracted to detector_adapters.py)
from app.detection_enterprise.detector_adapters import (
    DETECTOR_RUNNERS,
    _entry_to_llm_prompt,
)

# ---------------------------------------------------------------------------
# Calibration context — holds mutable state for a single calibration run.
# Replaces former module-level globals for thread safety.
# ---------------------------------------------------------------------------

@dataclass
class CalibrationContext:
    """Mutable state for a single calibration run (thread-safe replacement for module globals)."""
    escalation_counts: Dict[str, int] = field(default_factory=dict)
    llm_cost: Dict[str, float] = field(default_factory=dict)
    llm_tokens: Dict[str, int] = field(default_factory=dict)
    trial_seed: int = 0

    def reset_cost_trackers(self) -> None:
        self.escalation_counts.clear()
        self.llm_cost.clear()
        self.llm_tokens.clear()


# Default context (used when no explicit context is provided)
_default_ctx = CalibrationContext()


def _apply_tiered_runners(ctx: Optional[CalibrationContext] = None) -> None:
    """Wrap existing runners with LLM judge escalation for gray-zone cases.

    This preserves the original runner's structured data handling and only
    calls the LLM judge when the rule-based confidence is in the gray zone.
    Unlike the previous approach, this doesn't replace the rule-based detector
    with a text-based adapter — it wraps the existing runner.
    """
    if ctx is None:
        ctx = _default_ctx
    import json as _json

    try:
        from app.enterprise.evals.llm_judge import LLMJudge, JudgeModel
        from app.enterprise.evals.scorer import EvalType
    except ImportError:
        logger.warning("LLM Judge not available, tiered runners disabled")
        return

    judge = LLMJudge(model=JudgeModel.CLAUDE_HAIKU)
    if not judge.is_available:
        logger.warning("No ANTHROPIC_API_KEY, tiered runners disabled")
        return

    # Per-type gray zones: wider for low-recall detectors, narrower for low-precision.
    # Detectors already at production (coordination, context, loop) are EXCLUDED
    # to avoid regression from LLM interference.
    gray_zones = {
        DetectionType.INJECTION: (0.15, 0.85),      # Low recall — escalate more
        DetectionType.CORRUPTION: (0.15, 0.85),      # Low recall — escalate more
        DetectionType.COMPLETION: (0.20, 0.80),
        DetectionType.GROUNDING: (0.30, 0.65),       # Narrowed — regressed with wider zone
        DetectionType.DERAILMENT: (0.20, 0.80),      # Widened for precision help
        DetectionType.HALLUCINATION: (0.25, 0.75),
        DetectionType.COORDINATION: (0.35, 0.65),   # Narrow zone, boost-only (no downgrade)
        DetectionType.CONTEXT: (0.30, 0.65),         # Narrow zone, boost-only
        DetectionType.COMMUNICATION: (0.15, 0.85),   # Widened — low precision
        DetectionType.SPECIFICATION: (0.15, 0.85),    # Widened — low precision
        DetectionType.PERSONA_DRIFT: (0.15, 0.85),   # Widened — low precision
        DetectionType.DECOMPOSITION: (0.05, 0.99),   # Escalate ALL — bimodal fix
        DetectionType.WORKFLOW: (0.15, 0.85),         # Widened — near production
        DetectionType.WITHHOLDING: (0.10, 0.80),     # Widened — many TP/FP at 0.13
        DetectionType.RETRIEVAL_QUALITY: (0.10, 0.90),  # Widened — very low precision
        # OpenClaw framework-specific — moderate zones for initial calibration
        DetectionType.OPENCLAW_SESSION_LOOP: (0.20, 0.80),
        DetectionType.OPENCLAW_TOOL_ABUSE: (0.20, 0.80),
        DetectionType.OPENCLAW_ELEVATED_RISK: (0.20, 0.80),
        DetectionType.OPENCLAW_SPAWN_CHAIN: (0.20, 0.80),
        DetectionType.OPENCLAW_CHANNEL_MISMATCH: (0.20, 0.80),
        DetectionType.OPENCLAW_SANDBOX_ESCAPE: (0.20, 0.80),
        # Dify framework-specific
        DetectionType.DIFY_RAG_POISONING: (0.20, 0.80),
        DetectionType.DIFY_ITERATION_ESCAPE: (0.20, 0.80),
        DetectionType.DIFY_MODEL_FALLBACK: (0.20, 0.80),
        DetectionType.DIFY_VARIABLE_LEAK: (0.20, 0.80),
        DetectionType.DIFY_CLASSIFIER_DRIFT: (0.20, 0.80),
        DetectionType.DIFY_TOOL_SCHEMA_MISMATCH: (0.20, 0.80),
        # LangGraph framework-specific
        DetectionType.LANGGRAPH_RECURSION: (0.20, 0.80),
        DetectionType.LANGGRAPH_STATE_CORRUPTION: (0.20, 0.80),
        DetectionType.LANGGRAPH_EDGE_MISROUTE: (0.20, 0.80),
        DetectionType.LANGGRAPH_TOOL_FAILURE: (0.20, 0.80),
        DetectionType.LANGGRAPH_PARALLEL_SYNC: (0.20, 0.80),
        DetectionType.LANGGRAPH_CHECKPOINT_CORRUPTION: (0.20, 0.80),
    }
    # Detectors where soft downgrade is DISABLED (high precision already).
    # For these, LLM can only boost or keep-as-is, never reduce confidence.
    # v1.3: Re-added grounding — soft downgrade hurt R (-0.10) more than helped P (+0.05).
    _no_downgrade = {
        DetectionType.INJECTION.value,
        DetectionType.CORRUPTION.value,
        DetectionType.COORDINATION.value,
        DetectionType.CONTEXT.value,
        DetectionType.GROUNDING.value,
    }

    # v1.5: Per-detector soft downgrade removed — default (0.15, 0.40) for all.
    # Learnings from v1.3-v1.4: aggressive per-detector configs hurt recall badly.
    # Decomposition P jumped 0.655→0.927 but R crashed 0.833→0.576. Completion
    # regressed F1 0.731→0.680. LLM uncertainty (score 0.15-0.30) ≠ false positive.
    _soft_downgrade_config = {}  # All detectors use default (0.15, 0.40)

    # Save original runners before wrapping
    original_runners = dict(DETECTOR_RUNNERS)

    # Cache LLM results by (entry_key, det_type) to avoid duplicate calls across CV folds
    _llm_cache: Dict[str, Tuple[bool, float]] = {}
    # Reset cost trackers on context
    ctx.reset_cost_trackers()

    for det_type, (gz_lo, gz_hi) in gray_zones.items():
        if det_type not in original_runners:
            continue

        original_runner = original_runners[det_type]
        det_name = det_type.value
        ctx.escalation_counts[det_name] = 0

        def _make_wrapper(orig_fn, dt_name, lo, hi, _ctx=ctx):
            def _wrapped(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
                detected, confidence = orig_fn(entry)

                # Strategy: boost detected=True when LLM agrees, soft-downgrade
                # when LLM VERY STRONGLY disagrees (helps precision without killing recall).
                if detected:
                    # Rule says failure — escalate gray-zone cases to LLM.
                    if lo <= confidence <= hi:
                        cache_key = f"{entry.id}:{dt_name}:boost:{_ctx.trial_seed}"
                        if cache_key in _llm_cache:
                            return _llm_cache[cache_key]
                        try:
                            prompt = _entry_to_llm_prompt(entry, dt_name, detected, confidence)
                            result = judge.judge(
                                eval_type=EvalType.SAFETY, output="", custom_prompt=prompt,
                            )
                            _ctx.escalation_counts[dt_name] = _ctx.escalation_counts.get(dt_name, 0) + 1
                            _ctx.llm_cost[dt_name] = _ctx.llm_cost.get(dt_name, 0.0) + getattr(result, "cost_usd", 0.0)
                            _ctx.llm_tokens[dt_name] = _ctx.llm_tokens.get(dt_name, 0) + getattr(result, "tokens_used", 0)
                            if "Error" not in result.reasoning and "Could not parse" not in result.reasoning:
                                if result.score > 0.5:
                                    # LLM agrees → boost confidence
                                    boosted = (True, max(confidence, result.score * 0.9))
                                    _llm_cache[cache_key] = boosted
                                    return boosted
                                elif dt_name not in _no_downgrade:
                                    # v1.4: Per-detector soft downgrade config.
                                    # Only the lowest-P detectors get higher thresholds.
                                    sd_thresh, sd_factor = _soft_downgrade_config.get(dt_name, (0.15, 0.40))
                                    if result.score < sd_thresh:
                                        downgraded = (True, confidence * sd_factor)
                                        _llm_cache[cache_key] = downgraded
                                        return downgraded
                                # LLM disagrees but not strongly → keep as-is
                        except Exception as e:
                            logger.debug("LLM boost failed for %s: %s", dt_name, e)
                    return detected, confidence

                # Rule says no failure. Check if LLM finds something the rule missed.
                # Only escalate if there's SOME signal (confidence not zero).
                if confidence > 0.05:
                    cache_key = f"{entry.id}:{dt_name}:upgrade:{_ctx.trial_seed}"
                    if cache_key in _llm_cache:
                        return _llm_cache[cache_key]
                    try:
                        prompt = _entry_to_llm_prompt(entry, dt_name, False, confidence)
                        result = judge.judge(
                            eval_type=EvalType.SAFETY, output="", custom_prompt=prompt,
                        )
                        _ctx.escalation_counts[dt_name] = _ctx.escalation_counts.get(dt_name, 0) + 1
                        _ctx.llm_cost[dt_name] = _ctx.llm_cost.get(dt_name, 0.0) + getattr(result, "cost_usd", 0.0)
                        _ctx.llm_tokens[dt_name] = _ctx.llm_tokens.get(dt_name, 0) + getattr(result, "tokens_used", 0)
                        if "Error" not in result.reasoning and "Could not parse" not in result.reasoning:
                            if result.score > 0.6:
                                # LLM found a failure the rule missed
                                upgrade = (True, result.score)
                                _llm_cache[cache_key] = upgrade
                                return upgrade
                    except Exception as e:
                        logger.debug("LLM upgrade failed for %s: %s", dt_name, e)

                return detected, confidence
            return _wrapped

        DETECTOR_RUNNERS[det_type] = _make_wrapper(original_runner, det_name, gz_lo, gz_hi)
        logger.info("Wrapped %s with LLM escalation (gray zone: %.2f-%.2f)", det_name, gz_lo, gz_hi)


# ---------------------------------------------------------------------------
# Core calibration logic
# ---------------------------------------------------------------------------

def _compute_metrics_at_threshold(
    predictions: List[Tuple[bool, float]],
    ground_truths: List[bool],
    threshold: float,
) -> Tuple[int, int, int, int]:
    """Compute TP/TN/FP/FN for a given confidence threshold.

    A sample is predicted-positive if the detector said detected=True AND the
    confidence >= threshold.  Otherwise it is predicted-negative.
    """
    tp = tn = fp = fn = 0
    for (detected, confidence), expected in zip(predictions, ground_truths):
        predicted_positive = detected and confidence >= threshold
        if expected and predicted_positive:
            tp += 1
        elif expected and not predicted_positive:
            fn += 1
        elif not expected and predicted_positive:
            fp += 1
        else:
            tn += 1
    return tp, tn, fp, fn


def _precision_recall_f1(tp: int, tn: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _stratified_split(
    entries: List[GoldenDatasetEntry],
    n_folds: int = 3,
) -> List[Tuple[List[int], List[int]]]:
    """Create stratified fold indices for cross-validation.

    Splits entries into *n_folds* folds such that each fold preserves
    (approximately) the class distribution of positive/negative samples.

    Returns a list of (train_indices, test_indices) tuples, one per fold.
    """
    positive_idx = [i for i, e in enumerate(entries) if e.expected_detected]
    negative_idx = [i for i, e in enumerate(entries) if not e.expected_detected]

    # Deterministic shuffle using a simple seed-based approach
    def _seeded_shuffle(lst: List[int], seed: int = 42) -> List[int]:
        """Simple deterministic shuffle without external dependencies."""
        result = list(lst)
        n = len(result)
        h = seed
        for i in range(n - 1, 0, -1):
            h = int(hashlib.md5(f"{seed}_{i}".encode()).hexdigest()[:8], 16)
            j = h % (i + 1)
            result[i], result[j] = result[j], result[i]
        return result

    positive_idx = _seeded_shuffle(positive_idx)
    negative_idx = _seeded_shuffle(negative_idx)

    # Distribute indices across folds
    folds_pos: List[List[int]] = [[] for _ in range(n_folds)]
    folds_neg: List[List[int]] = [[] for _ in range(n_folds)]

    for i, idx in enumerate(positive_idx):
        folds_pos[i % n_folds].append(idx)
    for i, idx in enumerate(negative_idx):
        folds_neg[i % n_folds].append(idx)

    splits = []
    for fold_i in range(n_folds):
        test_idx = folds_pos[fold_i] + folds_neg[fold_i]
        train_idx = []
        for fold_j in range(n_folds):
            if fold_j != fold_i:
                train_idx.extend(folds_pos[fold_j])
                train_idx.extend(folds_neg[fold_j])
        splits.append((train_idx, test_idx))

    return splits


def _isotonic_calibrate(
    confidences: List[float],
    correct: List[bool],
) -> List[Tuple[float, float]]:
    """Pool Adjacent Violators Algorithm (PAVA) for isotonic regression.

    Fits a non-decreasing mapping from raw confidence to calibrated probability.
    Returns a list of (raw_confidence, calibrated_probability) breakpoints
    sorted by raw_confidence.

    Only useful when len(confidences) >= 20.
    """
    if not confidences:
        return []
    # Sort by confidence
    pairs = sorted(zip(confidences, [float(c) for c in correct]))
    n = len(pairs)
    # Initialize blocks: each sample is its own block
    block_sums = [p[1] for p in pairs]  # sum of correct in block
    block_counts = [1] * n
    block_confs = [p[0] for p in pairs]  # representative confidence

    # Pool adjacent violators
    i = 0
    while i < len(block_sums) - 1:
        mean_i = block_sums[i] / block_counts[i]
        mean_j = block_sums[i + 1] / block_counts[i + 1]
        if mean_i > mean_j:
            # Merge block i and i+1
            block_sums[i] += block_sums[i + 1]
            block_counts[i] += block_counts[i + 1]
            block_confs[i] = (block_confs[i] + block_confs[i + 1]) / 2
            del block_sums[i + 1]
            del block_counts[i + 1]
            del block_confs[i + 1]
            # Step back to check previous pair
            if i > 0:
                i -= 1
        else:
            i += 1

    # Build breakpoint list
    return [(block_confs[i], block_sums[i] / block_counts[i])
            for i in range(len(block_sums))]


def _apply_isotonic(raw_conf: float, breakpoints: List[Tuple[float, float]]) -> float:
    """Map a raw confidence through isotonic calibration breakpoints."""
    if not breakpoints:
        return raw_conf
    if raw_conf <= breakpoints[0][0]:
        return breakpoints[0][1]
    if raw_conf >= breakpoints[-1][0]:
        return breakpoints[-1][1]
    # Linear interpolation between breakpoints
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if x0 <= raw_conf <= x1:
            if x1 == x0:
                return y0
            t = (raw_conf - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return breakpoints[-1][1]


def _compute_ece(
    predictions: List[Tuple[bool, float]],
    ground_truths: List[bool],
    threshold: float,
    n_bins: int = 5,
) -> float:
    """Compute Expected Calibration Error.

    Measures how well confidence scores match actual accuracy.
    Lower is better (0.0 = perfectly calibrated).

    Uses the threshold to determine predicted labels, then bins by
    confidence and compares predicted accuracy vs actual accuracy per bin.
    """
    if not predictions:
        return 0.0

    # Collect (confidence, correct) pairs
    pairs = []
    for (detected, confidence), expected in zip(predictions, ground_truths):
        predicted_positive = detected and confidence >= threshold
        correct = (predicted_positive == expected)
        pairs.append((confidence, correct))

    if not pairs:
        return 0.0

    # Bin by confidence
    bin_size = 1.0 / n_bins
    total_ece = 0.0
    total_samples = len(pairs)

    for bin_idx in range(n_bins):
        bin_lower = bin_idx * bin_size
        bin_upper = (bin_idx + 1) * bin_size

        bin_pairs = [(conf, correct) for conf, correct in pairs
                     if bin_lower <= conf < bin_upper]

        if not bin_pairs:
            continue

        avg_confidence = sum(conf for conf, _ in bin_pairs) / len(bin_pairs)
        accuracy = sum(1 for _, correct in bin_pairs if correct) / len(bin_pairs)

        total_ece += (len(bin_pairs) / total_samples) * abs(accuracy - avg_confidence)

    return round(total_ece, 4)


def _bootstrap_confidence_interval(
    predictions: List[Tuple[bool, float]],
    ground_truths: List[bool],
    threshold: float,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
) -> Tuple[float, float]:
    """Compute bootstrap 95% confidence interval for F1 at a given threshold.

    Resamples predictions with replacement, computes F1 for each bootstrap
    sample, and returns the percentile-based CI bounds.
    """
    n = len(predictions)
    if n < 4:
        return 0.0, 1.0

    # Deterministic seed for reproducibility
    seed = 42
    f1_scores = []

    for b in range(n_bootstrap):
        # Generate indices via hash-based PRNG (no numpy dependency)
        indices = []
        for i in range(n):
            h = int(hashlib.md5(f"{seed}_{b}_{i}".encode()).hexdigest()[:8], 16)
            indices.append(h % n)

        boot_preds = [predictions[j] for j in indices]
        boot_truths = [ground_truths[j] for j in indices]
        tp, tn, fp, fn = _compute_metrics_at_threshold(boot_preds, boot_truths, threshold)
        _, _, f1 = _precision_recall_f1(tp, tn, fp, fn)
        f1_scores.append(f1)

    f1_scores.sort()
    alpha = 1.0 - ci
    lower_idx = int(alpha / 2 * n_bootstrap)
    upper_idx = int((1 - alpha / 2) * n_bootstrap) - 1
    lower_idx = max(0, min(lower_idx, n_bootstrap - 1))
    upper_idx = max(0, min(upper_idx, n_bootstrap - 1))

    return round(f1_scores[lower_idx], 4), round(f1_scores[upper_idx], 4)


def calibrate_single(
    detection_type: DetectionType,
    entries: List[GoldenDatasetEntry],
) -> Optional[CalibrationResult]:
    """Run calibration for a single detector type.

    When ``len(entries) >= 8``, uses 3-fold stratified cross-validation to
    find the optimal threshold on training folds and reports the averaged
    held-out metrics.  For fewer samples, falls back to grid search on the
    full dataset (original behaviour).

    Args:
        detection_type: The type of detection to calibrate.
        entries: Golden dataset entries for this detector type.

    Returns:
        CalibrationResult with optimal threshold and metrics, or None if the
        detector runner is unavailable or there are no entries.
    """
    runner = DETECTOR_RUNNERS.get(detection_type)
    if runner is None:
        logger.info(
            "No runner available for %s -- skipping calibration.",
            detection_type.value,
        )
        return None

    if not entries:
        logger.info(
            "No golden entries for %s -- skipping calibration.",
            detection_type.value,
        )
        return None

    # Run the detector on every entry and collect predictions.
    predictions: List[Tuple[bool, float]] = []
    ground_truths: List[bool] = []
    latencies_ms: List[float] = []

    for entry in entries:
        try:
            import time as _time
            _t0 = _time.perf_counter()
            detected, confidence = runner(entry)
            _elapsed = (_time.perf_counter() - _t0) * 1000
            predictions.append((detected, confidence))
            ground_truths.append(entry.expected_detected)
            latencies_ms.append(_elapsed)
        except Exception as exc:
            logger.warning(
                "Detector %s failed on entry %s: %s",
                detection_type.value,
                entry.id,
                exc,
            )
            # Treat detector failure as a negative prediction with zero confidence.
            predictions.append((False, 0.0))
            ground_truths.append(entry.expected_detected)
            latencies_ms.append(0.0)

    # -----------------------------------------------------------------
    # Cross-validation path (>= 8 samples)
    # -----------------------------------------------------------------
    n_positive = sum(1 for g in ground_truths if g)
    n_negative = len(ground_truths) - n_positive
    use_cv = len(entries) >= 8 and n_positive >= 2 and n_negative >= 2

    if use_cv:
        n_folds = 3
        splits = _stratified_split(entries, n_folds=n_folds)

        fold_best_thresholds = []
        fold_tp = fold_tn = fold_fp = fold_fn = 0
        fold_eces: List[float] = []
        fold_metrics: List[Dict[str, Any]] = []

        for fold_i, (train_idx, test_idx) in enumerate(splits):
            # Find best threshold on the training fold
            train_preds = [predictions[i] for i in train_idx]
            train_labels = [ground_truths[i] for i in train_idx]

            best_thr = THRESHOLD_GRID[0]
            best_f1_train = -1.0
            best_prec_train = -1.0

            for thr in THRESHOLD_GRID:
                tp, tn, fp, fn = _compute_metrics_at_threshold(train_preds, train_labels, thr)
                prec, rec, f1 = _precision_recall_f1(tp, tn, fp, fn)
                if f1 > best_f1_train or (f1 == best_f1_train and prec > best_prec_train):
                    best_f1_train = f1
                    best_prec_train = prec
                    best_thr = thr

            fold_best_thresholds.append(best_thr)

            # Evaluate on held-out fold
            test_preds = [predictions[i] for i in test_idx]
            test_labels = [ground_truths[i] for i in test_idx]
            tp, tn, fp, fn = _compute_metrics_at_threshold(test_preds, test_labels, best_thr)
            fold_tp += tp
            fold_tn += tn
            fold_fp += fp
            fold_fn += fn

            # v1.2: Per-fold ECE computation
            fold_ece = _compute_ece(test_preds, test_labels, best_thr)
            fold_eces.append(fold_ece)

            # v1.2: Per-fold metrics logging
            fold_prec, fold_rec, fold_f1 = _precision_recall_f1(tp, tn, fp, fn)
            fold_metrics.append({
                "fold": fold_i,
                "threshold": best_thr,
                "precision": round(fold_prec, 4),
                "recall": round(fold_rec, 4),
                "f1": round(fold_f1, 4),
                "ece": fold_ece,
                "train_size": len(train_idx),
                "test_size": len(test_idx),
            })
            logger.debug(
                "  Fold %d/%d for %s: thr=%.2f P=%.3f R=%.3f F1=%.3f ECE=%.4f",
                fold_i + 1, n_folds, detection_type.value,
                best_thr, fold_prec, fold_rec, fold_f1, fold_ece,
            )

        # Average threshold across folds
        avg_threshold = round(sum(fold_best_thresholds) / len(fold_best_thresholds), 2)
        # Snap to nearest grid point
        avg_threshold = min(THRESHOLD_GRID, key=lambda t: abs(t - avg_threshold))

        precision, recall, f1 = _precision_recall_f1(fold_tp, fold_tn, fold_fp, fold_fn)

        # v1.2: Average ECE across folds (more robust than single full-dataset ECE)
        avg_fold_ece = round(sum(fold_eces) / len(fold_eces), 4) if fold_eces else 0.0
        # Also compute full-dataset ECE for comparison
        full_ece = _compute_ece(predictions, ground_truths, avg_threshold)
        ece = avg_fold_ece  # Use fold-averaged ECE as primary

        # Post-hoc confidence calibration via isotonic regression (PAVA).
        # Only apply when we have enough samples to avoid overfitting.
        calibrated_ece = ece
        if len(entries) >= 20:
            confs = [c for _, c in predictions]
            corrects = [
                (detected and c >= avg_threshold) == gt
                for (detected, c), gt in zip(predictions, ground_truths)
            ]
            breakpoints = _isotonic_calibrate(confs, corrects)
            if breakpoints:
                # Re-compute ECE with calibrated confidences
                cal_preds = [
                    (det, _apply_isotonic(c, breakpoints))
                    for det, c in predictions
                ]
                calibrated_ece = _compute_ece(cal_preds, ground_truths, avg_threshold)

        logger.info(
            "CV calibration for %s: threshold=%.2f  P=%.3f  R=%.3f  F1=%.3f  "
            "ECE=%.4f (fold-avg) / %.4f (full)  (fold thresholds=%s)",
            detection_type.value,
            avg_threshold,
            precision,
            recall,
            f1,
            avg_fold_ece,
            full_ece,
            fold_best_thresholds,
        )

        ci_lower, ci_upper = _bootstrap_confidence_interval(
            predictions, ground_truths, avg_threshold,
        )

        result = CalibrationResult(
            detection_type=detection_type.value,
            optimal_threshold=avg_threshold,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            sample_count=len(entries),
            true_positives=fold_tp,
            true_negatives=fold_tn,
            false_positives=fold_fp,
            false_negatives=fold_fn,
            ece=ece,
            calibrated_ece=calibrated_ece,
            f1_ci_lower=ci_lower,
            f1_ci_upper=ci_upper,
        )
        # v1.2: Attach per-fold detail for transparency
        result.fold_metrics = fold_metrics  # type: ignore[attr-defined]
        result.fold_thresholds = fold_best_thresholds  # type: ignore[attr-defined]
        # v1.3: Per-sample error analysis
        result.sample_predictions = _build_sample_predictions(  # type: ignore[attr-defined]
            entries, predictions, ground_truths, detection_type, avg_threshold,
        )
        # v1.5: Per-difficulty breakdown + latency
        result.difficulty_breakdown = _compute_difficulty_breakdown(  # type: ignore[attr-defined]
            result.sample_predictions,
        )
        result.latency_stats = _compute_latency_stats(latencies_ms)  # type: ignore[attr-defined]
        return result

    # -----------------------------------------------------------------
    # Fallback: full-dataset grid search (< 8 samples)
    # -----------------------------------------------------------------
    best_threshold = THRESHOLD_GRID[0]
    best_f1 = -1.0
    best_precision = -1.0
    best_metrics: Tuple[int, int, int, int] = (0, 0, 0, 0)

    for threshold in THRESHOLD_GRID:
        tp, tn, fp, fn = _compute_metrics_at_threshold(predictions, ground_truths, threshold)
        precision, recall, f1 = _precision_recall_f1(tp, tn, fp, fn)

        # Prefer higher F1, then higher precision as tiebreaker.
        if f1 > best_f1 or (f1 == best_f1 and precision > best_precision):
            best_f1 = f1
            best_precision = precision
            best_threshold = threshold
            best_metrics = (tp, tn, fp, fn)

    tp, tn, fp, fn = best_metrics
    precision, recall, f1 = _precision_recall_f1(tp, tn, fp, fn)

    # Compute ECE on full predictions using best threshold
    ece = _compute_ece(predictions, ground_truths, best_threshold)

    ci_lower, ci_upper = _bootstrap_confidence_interval(
        predictions, ground_truths, best_threshold,
    )

    result = CalibrationResult(
        detection_type=detection_type.value,
        optimal_threshold=best_threshold,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        sample_count=len(entries),
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        ece=ece,
        f1_ci_lower=ci_lower,
        f1_ci_upper=ci_upper,
    )
    # v1.3: Per-sample error analysis
    result.sample_predictions = _build_sample_predictions(  # type: ignore[attr-defined]
        entries, predictions, ground_truths, detection_type, best_threshold,
    )
    # v1.5: Per-difficulty breakdown + latency
    result.difficulty_breakdown = _compute_difficulty_breakdown(  # type: ignore[attr-defined]
        result.sample_predictions,
    )
    result.latency_stats = _compute_latency_stats(latencies_ms)  # type: ignore[attr-defined]
    return result


def calibrate_all(
    phoenix_tracer: Optional[Any] = None,
    splits: Optional[List[str]] = None,
    db_session=None,
    ctx: Optional[CalibrationContext] = None,
) -> Dict[str, Any]:
    """Run calibration across all detector types using the golden dataset.

    Args:
        phoenix_tracer: Optional OTEL tracer for Phoenix observability.
            When provided, each detector calibration is exported as a span.
        splits: If provided, only use entries from these splits (e.g.
            ``["train", "val"]``).  When ``None``, uses all entries
            (backward-compatible).
        ctx: Optional CalibrationContext for thread-safe cost tracking.
            When ``None``, uses the module-level default context.

    Returns:
        A dict with the structure::

            {
                "calibrated_at": "<ISO timestamp>",
                "detector_count": <int>,
                "skipped": ["<type>", ...],
                "splits_used": ["train", "val"] | null,
                "results": {
                    "<detection_type>": {
                        "optimal_threshold": <float>,
                        "precision": <float>,
                        "recall": <float>,
                        "f1": <float>,
                        "sample_count": <int>,
                        "true_positives": <int>,
                        "true_negatives": <int>,
                        "false_positives": <int>,
                        "false_negatives": <int>,
                    },
                    ...
                },
            }
    """
    if ctx is None:
        ctx = _default_ctx
    dataset = _get_golden_dataset(db_session)
    results: Dict[str, Any] = {}
    skipped: List[str] = []
    all_sample_predictions: List[SamplePrediction] = []

    target_types = [
        DetectionType.LOOP,
        DetectionType.PERSONA_DRIFT,
        DetectionType.HALLUCINATION,
        DetectionType.INJECTION,
        DetectionType.OVERFLOW,
        DetectionType.CORRUPTION,
        DetectionType.COORDINATION,
        DetectionType.COMMUNICATION,
        DetectionType.CONTEXT,
        DetectionType.GROUNDING,
        DetectionType.RETRIEVAL_QUALITY,
        DetectionType.COMPLETION,
        DetectionType.DERAILMENT,
        DetectionType.SPECIFICATION,
        DetectionType.DECOMPOSITION,
        DetectionType.WITHHOLDING,
        DetectionType.WORKFLOW,
        DetectionType.CONVERGENCE,
        # OpenClaw framework-specific detectors
        DetectionType.OPENCLAW_SESSION_LOOP,
        DetectionType.OPENCLAW_TOOL_ABUSE,
        DetectionType.OPENCLAW_ELEVATED_RISK,
        DetectionType.OPENCLAW_SPAWN_CHAIN,
        DetectionType.OPENCLAW_CHANNEL_MISMATCH,
        DetectionType.OPENCLAW_SANDBOX_ESCAPE,
        # Dify framework-specific detectors
        DetectionType.DIFY_RAG_POISONING,
        DetectionType.DIFY_ITERATION_ESCAPE,
        DetectionType.DIFY_MODEL_FALLBACK,
        DetectionType.DIFY_VARIABLE_LEAK,
        DetectionType.DIFY_CLASSIFIER_DRIFT,
        DetectionType.DIFY_TOOL_SCHEMA_MISMATCH,
        # LangGraph framework-specific detectors
        DetectionType.LANGGRAPH_RECURSION,
        DetectionType.LANGGRAPH_STATE_CORRUPTION,
        DetectionType.LANGGRAPH_EDGE_MISROUTE,
        DetectionType.LANGGRAPH_TOOL_FAILURE,
        DetectionType.LANGGRAPH_PARALLEL_SYNC,
        DetectionType.LANGGRAPH_CHECKPOINT_CORRUPTION,
        # n8n framework-specific structural detectors
        DetectionType.N8N_SCHEMA,
        DetectionType.N8N_CYCLE,
        DetectionType.N8N_COMPLEXITY,
        DetectionType.N8N_ERROR,
        DetectionType.N8N_RESOURCE,
        DetectionType.N8N_TIMEOUT,
    ]

    # Optional: wrap in a Phoenix parent span
    _parent_ctx = None
    if phoenix_tracer:
        try:
            _parent_ctx = phoenix_tracer.start_as_current_span(
                "calibration_run",
                attributes={
                    "calibration.detector_count": len(target_types),
                    "calibration.dataset_size": len(dataset.entries),
                },
            )
            _parent_ctx.__enter__()
        except Exception:
            _parent_ctx = None

    for dt in target_types:
        if splits:
            entries = dataset.get_entries_by_type_and_split(dt, splits)
        else:
            entries = dataset.get_entries_by_type(dt)

        # Optional: child span per detector
        _child_ctx = None
        if phoenix_tracer:
            try:
                _child_ctx = phoenix_tracer.start_as_current_span(
                    f"calibrate_{dt.value}",
                    attributes={
                        "detector.type": dt.value,
                        "detector.sample_count": len(entries),
                    },
                )
                _child_ctx.__enter__()
            except Exception:
                _child_ctx = None

        cal = calibrate_single(dt, entries)

        # Free memory between detectors to prevent OOM during full calibration
        import gc
        gc.collect()

        if cal is None:
            skipped.append(dt.value)
        else:
            result_dict = asdict(cal)
            # v1.5: Include per-difficulty breakdown, latency, and LLM cost
            result_dict["difficulty_breakdown"] = getattr(cal, "difficulty_breakdown", {})
            result_dict["latency_stats"] = getattr(cal, "latency_stats", {})
            dt_name = cal.detection_type
            result_dict["llm_cost"] = {
                "escalations": ctx.escalation_counts.get(dt_name, 0),
                "cost_usd": round(ctx.llm_cost.get(dt_name, 0.0), 6),
                "tokens": ctx.llm_tokens.get(dt_name, 0),
            }
            results[cal.detection_type] = result_dict
            all_sample_predictions.extend(
                getattr(cal, "sample_predictions", [])
            )
            # Set span attributes with results
            if _child_ctx and phoenix_tracer:
                try:
                    from opentelemetry import trace as _otrace
                    span = _otrace.get_current_span()
                    span.set_attribute("detector.f1", cal.f1)
                    span.set_attribute("detector.precision", cal.precision)
                    span.set_attribute("detector.recall", cal.recall)
                    span.set_attribute("detector.threshold", cal.optimal_threshold)
                except Exception:
                    pass

        if _child_ctx:
            try:
                _child_ctx.__exit__(None, None, None)
            except Exception:
                pass

    if _parent_ctx:
        try:
            _parent_ctx.__exit__(None, None, None)
        except Exception:
            pass

    # Compute LLM cost totals across all detectors
    total_llm_cost = sum(ctx.llm_cost.values())
    total_llm_tokens = sum(ctx.llm_tokens.values())
    total_escalations = sum(ctx.escalation_counts.values())

    # Include dataset content hash for reproducibility
    dataset_content_hash = None
    try:
        dataset_content_hash = dataset.compute_content_hash()
    except Exception:
        pass

    report = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "detector_count": len(results),
        "skipped": skipped,
        "splits_used": splits,
        "results": results,
        "sample_predictions": [asdict(sp) for sp in all_sample_predictions],
        "dataset_content_hash": dataset_content_hash,
        "llm_cost_summary": {
            "total_cost_usd": round(total_llm_cost, 4),
            "total_tokens": total_llm_tokens,
            "total_escalations": total_escalations,
        },
    }
    return report


def compute_correlation_matrix(
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute pairwise Phi coefficient between detector predictions.

    Uses the sample_predictions from a calibration report to find
    detectors that co-fire on the same samples, indicating potential
    redundancy.

    Returns a dict with ``pairs`` (sorted by |phi| descending) and
    ``matrix`` (full detector x detector phi values).
    """
    from collections import defaultdict
    import math

    sample_preds = report.get("sample_predictions", [])
    if not sample_preds:
        return {"pairs": [], "matrix": {}}

    # Group predictions by sample entry_id
    by_sample: Dict[str, Dict[str, bool]] = defaultdict(dict)
    for sp in sample_preds:
        entry_id = sp.get("entry_id", sp.get("sample_id", ""))
        det_type = sp.get("detection_type", "")
        predicted = sp.get("predicted", False)
        by_sample[entry_id][det_type] = predicted

    # Get all detector types that appear in predictions
    all_types = sorted({
        sp.get("detection_type", "")
        for sp in sample_preds
        if sp.get("detection_type")
    })

    if len(all_types) < 2:
        return {"pairs": [], "matrix": {}}

    # Compute Phi coefficient for each pair
    def _phi(type_a: str, type_b: str) -> float:
        n11 = n10 = n01 = n00 = 0
        for preds in by_sample.values():
            a = preds.get(type_a)
            b = preds.get(type_b)
            if a is None or b is None:
                continue
            if a and b:
                n11 += 1
            elif a and not b:
                n10 += 1
            elif not a and b:
                n01 += 1
            else:
                n00 += 1
        denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
        if denom == 0:
            return 0.0
        return (n11 * n00 - n10 * n01) / denom

    matrix: Dict[str, Dict[str, float]] = {}
    pairs: List[Dict[str, Any]] = []

    for i, a in enumerate(all_types):
        matrix[a] = {}
        for j, b in enumerate(all_types):
            if i == j:
                matrix[a][b] = 1.0
            elif j < i:
                matrix[a][b] = matrix[b][a]
            else:
                phi = round(_phi(a, b), 4)
                matrix[a][b] = phi
                if abs(phi) > 0.3:
                    pairs.append({"a": a, "b": b, "phi": phi})

    pairs.sort(key=lambda p: abs(p["phi"]), reverse=True)
    return {"pairs": pairs, "matrix": matrix}


def calibrate_multi_trial(
    n_trials: int = 3,
    **kwargs,
) -> Dict[str, Any]:
    """Run calibration N times to measure F1 variance across LLM judge calls.

    Each trial uses a different cache seed so LLM judge calls are fresh.
    Rule-based detectors are deterministic, so variance only appears when
    --tiered mode is used (LLM escalation introduces stochasticity).

    Args:
        n_trials: Number of independent calibration runs.
        **kwargs: Passed to calibrate_all().

    Returns:
        Dict with per-detector variance stats and raw trial data.
    """
    trial_results = []
    ctx = CalibrationContext()

    for trial in range(n_trials):
        ctx.trial_seed = trial + 1
        ctx.reset_cost_trackers()
        result = calibrate_all(ctx=ctx, **kwargs)
        trial_results.append(result)

    ctx.trial_seed = 0  # Reset

    # Aggregate per-detector variance
    variance_report: Dict[str, Any] = {}
    all_det_types = set()
    for tr in trial_results:
        all_det_types.update(tr["results"].keys())

    for det_type in sorted(all_det_types):
        f1s = [
            tr["results"][det_type]["f1"]
            for tr in trial_results
            if det_type in tr["results"]
        ]
        if not f1s:
            continue
        mean_f1 = sum(f1s) / len(f1s)
        std_f1 = (sum((x - mean_f1) ** 2 for x in f1s) / len(f1s)) ** 0.5
        variance_report[det_type] = {
            "mean_f1": round(mean_f1, 4),
            "std_f1": round(std_f1, 4),
            "min_f1": round(min(f1s), 4),
            "max_f1": round(max(f1s), 4),
            "pass_at_k": round(sum(1 for f in f1s if f >= 0.80) / len(f1s), 4),
            "trials": [round(f, 4) for f in f1s],
        }

    return {
        "trials": n_trials,
        "variance": variance_report,
        "raw_trials": trial_results,
    }


# ---------------------------------------------------------------------------
# Holdout evaluation (uses test split only)
# ---------------------------------------------------------------------------


def evaluate_holdout(
    calibration_report: Dict[str, Any],
    db_session=None,
) -> Dict[str, Any]:
    """Evaluate detectors on the held-out test split using calibrated thresholds.

    This provides unbiased metrics on data never seen during calibration.

    Args:
        calibration_report: The dict returned by ``calibrate_all()``, which
            contains ``results[dtype]["optimal_threshold"]`` per detector.

    Returns:
        A dict with per-detector metrics on the test set only::

            {
                "evaluated_at": "<ISO timestamp>",
                "split": "test",
                "results": { "<dtype>": { "f1": ..., "precision": ..., ... } }
            }
    """
    dataset = _get_golden_dataset(db_session)
    cal_results = calibration_report.get("results", {})
    eval_results: Dict[str, Any] = {}
    all_sample_predictions: List[SamplePrediction] = []

    for dtype_val, cal_metrics in cal_results.items():
        try:
            dt = DetectionType(dtype_val)
        except ValueError:
            continue

        entries = dataset.get_entries_by_type_and_split(dt, ["test"])
        if not entries:
            continue

        runner = DETECTOR_RUNNERS.get(dt)
        if runner is None:
            continue

        threshold = cal_metrics.get("optimal_threshold", 0.5)

        predictions: List[Tuple[bool, float]] = []
        ground_truths: List[bool] = []

        for entry in entries:
            try:
                detected, confidence = runner(entry)
                predictions.append((detected, confidence))
                ground_truths.append(entry.expected_detected)
            except Exception:
                predictions.append((False, 0.0))
                ground_truths.append(entry.expected_detected)

        tp, tn, fp, fn = _compute_metrics_at_threshold(
            predictions, ground_truths, threshold,
        )
        precision, recall, f1 = _precision_recall_f1(tp, tn, fp, fn)

        eval_results[dtype_val] = {
            "optimal_threshold": threshold,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "sample_count": len(entries),
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
        }

        # v1.3: Per-sample error analysis for holdout
        all_sample_predictions.extend(
            _build_sample_predictions(entries, predictions, ground_truths, dt, threshold)
        )

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "split": "test",
        "detector_count": len(eval_results),
        "results": eval_results,
        "sample_predictions": [asdict(sp) for sp in all_sample_predictions],
    }


# ---------------------------------------------------------------------------
# Capability registry generation
# ---------------------------------------------------------------------------

DETECTOR_METADATA: Dict[str, Dict[str, str]] = {
    "loop": {"name": "Loop Detection", "tier": "icp", "module": "app.detection.loop"},
    "persona_drift": {"name": "Persona Drift", "tier": "icp", "module": "app.detection.persona"},
    "hallucination": {"name": "Hallucination Detection", "tier": "icp", "module": "app.detection.hallucination"},
    "injection": {"name": "Injection Detection", "tier": "icp", "module": "app.detection.injection"},
    "overflow": {"name": "Context Overflow", "tier": "icp", "module": "app.detection.overflow"},
    "corruption": {"name": "State Corruption", "tier": "icp", "module": "app.detection.corruption"},
    "coordination": {"name": "Coordination Analysis", "tier": "icp", "module": "app.detection.coordination"},
    "communication": {"name": "Communication Breakdown", "tier": "icp", "module": "app.detection.communication"},
    "context": {"name": "Context Neglect", "tier": "icp", "module": "app.detection.context"},
    "derailment": {"name": "Task Derailment", "tier": "icp", "module": "app.detection.derailment"},
    "specification": {"name": "Specification Mismatch", "tier": "icp", "module": "app.detection.specification"},
    "decomposition": {"name": "Task Decomposition", "tier": "icp", "module": "app.detection.decomposition"},
    "workflow": {"name": "Workflow Analysis", "tier": "icp", "module": "app.detection.workflow"},
    "withholding": {"name": "Information Withholding", "tier": "icp", "module": "app.detection.withholding"},
    "completion": {"name": "Completion Misjudgment", "tier": "icp", "module": "app.detection.completion"},
    "grounding": {"name": "Grounding Detection", "tier": "enterprise", "module": "app.detection_enterprise.grounding"},
    "retrieval_quality": {"name": "Retrieval Quality", "tier": "enterprise", "module": "app.detection_enterprise.retrieval_quality"},
    # n8n framework-specific structural detectors
    "n8n_schema": {"name": "N8N Schema Mismatch", "tier": "enterprise", "module": "app.detection.n8n.schema_detector"},
    "n8n_cycle": {"name": "N8N Graph Cycle", "tier": "enterprise", "module": "app.detection.n8n.cycle_detector"},
    "n8n_complexity": {"name": "N8N Complexity", "tier": "enterprise", "module": "app.detection.n8n.complexity_detector"},
    "n8n_error": {"name": "N8N Error Handling", "tier": "enterprise", "module": "app.detection.n8n.error_detector"},
    "n8n_resource": {"name": "N8N Resource Limits", "tier": "enterprise", "module": "app.detection.n8n.resource_detector"},
    "n8n_timeout": {"name": "N8N Timeout Protection", "tier": "enterprise", "module": "app.detection.n8n.timeout_detector"},
    # Dify framework-specific detectors
    "dify_rag_poisoning": {"name": "Dify RAG Poisoning", "tier": "enterprise", "module": "app.detection.dify.rag_poisoning_detector"},
    "dify_iteration_escape": {"name": "Dify Iteration Escape", "tier": "enterprise", "module": "app.detection.dify.iteration_escape_detector"},
    "dify_model_fallback": {"name": "Dify Model Fallback", "tier": "enterprise", "module": "app.detection.dify.model_fallback_detector"},
    "dify_variable_leak": {"name": "Dify Variable Leak", "tier": "enterprise", "module": "app.detection.dify.variable_leak_detector"},
    "dify_classifier_drift": {"name": "Dify Classifier Drift", "tier": "enterprise", "module": "app.detection.dify.classifier_drift_detector"},
    "dify_tool_schema_mismatch": {"name": "Dify Tool Schema Mismatch", "tier": "enterprise", "module": "app.detection.dify.tool_schema_mismatch_detector"},
    # OpenClaw framework-specific detectors
    "openclaw_session_loop": {"name": "OpenClaw Session Loop", "tier": "enterprise", "module": "app.detection.openclaw.session_loop_detector"},
    "openclaw_tool_abuse": {"name": "OpenClaw Tool Abuse", "tier": "enterprise", "module": "app.detection.openclaw.tool_abuse_detector"},
    "openclaw_elevated_risk": {"name": "OpenClaw Elevated Risk", "tier": "enterprise", "module": "app.detection.openclaw.elevated_risk_detector"},
    "openclaw_spawn_chain": {"name": "OpenClaw Spawn Chain", "tier": "enterprise", "module": "app.detection.openclaw.spawn_chain_detector"},
    "openclaw_channel_mismatch": {"name": "OpenClaw Channel Mismatch", "tier": "enterprise", "module": "app.detection.openclaw.channel_mismatch_detector"},
    "openclaw_sandbox_escape": {"name": "OpenClaw Sandbox Escape", "tier": "enterprise", "module": "app.detection.openclaw.sandbox_escape_detector"},
    # LangGraph framework-specific detectors
    "langgraph_recursion": {"name": "LangGraph Recursion", "tier": "enterprise", "module": "app.detection.langgraph.recursion_detector"},
    "langgraph_state_corruption": {"name": "LangGraph State Corruption", "tier": "enterprise", "module": "app.detection.langgraph.state_corruption_detector"},
    "langgraph_edge_misroute": {"name": "LangGraph Edge Misroute", "tier": "enterprise", "module": "app.detection.langgraph.edge_misroute_detector"},
    "langgraph_tool_failure": {"name": "LangGraph Tool Failure", "tier": "enterprise", "module": "app.detection.langgraph.tool_failure_detector"},
    "langgraph_parallel_sync": {"name": "LangGraph Parallel Sync", "tier": "enterprise", "module": "app.detection.langgraph.parallel_sync_detector"},
    "langgraph_checkpoint_corruption": {"name": "LangGraph Checkpoint Corruption", "tier": "enterprise", "module": "app.detection.langgraph.checkpoint_corruption_detector"},
}

MINIMUM_PASSING_F1 = 0.40

READINESS_CRITERIA = {
    "production":   {"min_f1": 0.80, "min_precision": 0.70, "min_samples": 30},
    "beta":         {"min_f1": 0.65, "min_samples": 15},
    "experimental": {"min_f1": 0.40, "min_samples": 8},
    "failing":      {},
}


def _compute_readiness(f1: float, precision: float, sample_count: int) -> str:
    """Determine readiness tier based on metrics and sample count."""
    for tier, criteria in READINESS_CRITERIA.items():
        if not criteria:
            return tier
        if (f1 >= criteria.get("min_f1", 0.0)
                and precision >= criteria.get("min_precision", 0.0)
                and sample_count >= criteria.get("min_samples", 0)):
            return tier
    return "failing"


def generate_capability_registry(
    report: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate a machine-readable capability registry from calibration results.

    The registry is a structured JSON spec listing every detector with its
    current status (passing/failing/untested), calibration metrics, and metadata.
    Follows the Anthropic pattern of "structured specification as JSON, not markdown."
    """
    output_path = output_path or Path(__file__).parent.parent.parent / "data" / "capability_registry.json"
    results = report.get("results", {})
    skipped = set(report.get("skipped", []))
    calibrated_at = report.get("calibrated_at", "")

    capabilities = {}
    readiness_counts = {"production": 0, "beta": 0, "experimental": 0, "failing": 0, "untested": 0}

    for dtype_value, meta in DETECTOR_METADATA.items():
        if dtype_value in skipped or dtype_value not in results:
            readiness_counts["untested"] += 1
            entry = {
                "name": meta["name"],
                "tier": meta["tier"],
                "status": "untested",
                "readiness": "untested",
                "module": meta["module"],
            }
        else:
            metrics = results[dtype_value]
            f1 = metrics.get("f1", 0.0)
            precision = metrics.get("precision", 0.0)
            sample_count = metrics.get("sample_count", 0)
            readiness = _compute_readiness(f1, precision, sample_count)
            readiness_counts[readiness] += 1
            status = "passing" if f1 >= MINIMUM_PASSING_F1 else "failing"
            # v1.5: Difficulty breakdown and saturation detection
            diff_breakdown = metrics.get("difficulty_breakdown", {})
            easy_metrics = diff_breakdown.get("easy", {})
            hard_metrics = diff_breakdown.get("hard", {})
            is_saturated = (
                easy_metrics.get("f1", 0) >= 0.95
                and hard_metrics.get("n", 0) < 5
                and f1 >= 0.95
                and sample_count >= 20  # avoid false saturation on small datasets
            )
            eval_category = (
                "saturated" if is_saturated else
                "regression" if readiness == "production" else
                "capability"
            )
            entry = {
                "name": meta["name"],
                "tier": meta["tier"],
                "status": status,
                "readiness": readiness,
                "eval_category": eval_category,
                "module": meta["module"],
                "f1_score": f1,
                "precision": precision,
                "recall": metrics.get("recall", 0.0),
                "optimal_threshold": metrics.get("optimal_threshold", 0.5),
                "sample_count": sample_count,
                "f1_ci_lower": metrics.get("f1_ci_lower", 0.0),
                "f1_ci_upper": metrics.get("f1_ci_upper", 0.0),
                "difficulty_breakdown": diff_breakdown,
                "last_calibrated": calibrated_at,
            }
            if is_saturated:
                entry["saturation_warning"] = True

        capabilities[dtype_value] = entry

    # v1.5: Count saturated detectors
    saturated = [k for k, v in capabilities.items() if v.get("saturation_warning")]
    registry = {
        "version": "2.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": capabilities,
        "summary": {
            "total": len(capabilities),
            "production": readiness_counts["production"],
            "beta": readiness_counts["beta"],
            "experimental": readiness_counts["experimental"],
            "failing": readiness_counts["failing"],
            "untested": readiness_counts["untested"],
            "saturated": len(saturated),
            "saturated_detectors": saturated,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)
    logger.info("Capability registry written to %s", output_path)

    return registry


# ---------------------------------------------------------------------------
# Report persistence
# ---------------------------------------------------------------------------

def save_calibration_report(results: Dict[str, Any], path: Path) -> None:
    """Save the calibration report as JSON.

    Args:
        results: The dict returned by ``calibrate_all()``.
        path: Destination file path (parent directories are created if needed).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    logger.info("Calibration report saved to %s", path)


def generate_error_report(
    report: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate per-sample error analysis from calibration predictions.

    Groups predictions by detector type, sorts FPs by confidence descending
    (highest-confidence FPs are most actionable) and FNs by confidence
    ascending (near-miss FNs show threshold sensitivity).

    Args:
        report: The dict returned by ``calibrate_all()`` (must include
            ``sample_predictions``).
        output_path: Where to write the JSON report.  Defaults to
            ``backend/data/error_analysis_<timestamp>.json``.

    Returns:
        The analysis dict keyed by detector type.
    """
    output_path = output_path or (
        Path(__file__).parent.parent.parent / "data"
        / f"error_analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    )

    predictions = report.get("sample_predictions", [])
    if not predictions:
        logger.warning("No sample predictions in report — cannot generate error analysis.")
        return {}

    analysis: Dict[str, Any] = {}

    # Group by detector type
    by_dtype: Dict[str, list] = {}
    for p in predictions:
        by_dtype.setdefault(p["detection_type"], []).append(p)

    for dtype in sorted(by_dtype):
        preds = by_dtype[dtype]
        fps = sorted(
            [p for p in preds if p["classification"] == "FP"],
            key=lambda p: -p["confidence"],
        )
        fns = sorted(
            [p for p in preds if p["classification"] == "FN"],
            key=lambda p: p["confidence"],
        )
        tps = [p for p in preds if p["classification"] == "TP"]
        tns = [p for p in preds if p["classification"] == "TN"]

        analysis[dtype] = {
            "summary": {
                "total": len(preds),
                "TP": len(tps),
                "TN": len(tns),
                "FP": len(fps),
                "FN": len(fns),
                "threshold": preds[0]["threshold_used"] if preds else None,
            },
            "false_positives": fps,
            "false_negatives": fns,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Write analysis without the bulky sample_predictions from the main report
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2, default=str)
    logger.info("Error analysis written to %s", output_path)

    # Print human-readable summary
    print("\n" + "=" * 72)
    print("  ERROR ANALYSIS SUMMARY")
    print("=" * 72)
    for dtype, data in sorted(analysis.items()):
        s = data["summary"]
        if s["FP"] == 0 and s["FN"] == 0:
            continue
        print(f"\n  [{dtype.upper()}]  (threshold={s['threshold']:.2f})")
        print(f"    TP={s['TP']}  TN={s['TN']}  FP={s['FP']}  FN={s['FN']}")
        if data["false_positives"]:
            print(f"    --- False Positives (highest confidence first) ---")
            for fp in data["false_positives"][:5]:
                print(f"      {fp['entry_id']:30s}  conf={fp['confidence']:.3f}  "
                      f"diff={fp['difficulty']:6s}  {fp['description'][:60]}")
            if len(data["false_positives"]) > 5:
                print(f"      ... and {len(data['false_positives']) - 5} more")
        if data["false_negatives"]:
            print(f"    --- False Negatives (near-misses first) ---")
            for fn in data["false_negatives"][:5]:
                print(f"      {fn['entry_id']:30s}  conf={fn['confidence']:.3f}  "
                      f"diff={fn['difficulty']:6s}  {fn['description'][:60]}")
            if len(data["false_negatives"]) > 5:
                print(f"      ... and {len(data['false_negatives']) - 5} more")
    print("\n" + "=" * 72)
    print(f"  Report saved to: {output_path}")

    return analysis


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from app.detection_enterprise.calibrate_cli import main
    main()
