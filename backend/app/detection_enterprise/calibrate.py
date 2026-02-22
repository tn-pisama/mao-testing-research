"""Threshold calibration for detection algorithms using the golden dataset.

Runs each detector against its golden test samples, finds optimal confidence
thresholds via grid search, and reports precision/recall/F1 metrics.
"""

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import create_default_golden_dataset, GoldenDatasetEntry

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


# ---------------------------------------------------------------------------
# Detector adapter functions
#
# Each adapter takes a GoldenDatasetEntry and returns (detected, confidence).
# If a detector cannot be imported, the adapter will be None and will be
# skipped at calibration time.
# ---------------------------------------------------------------------------

def _build_detector_runners() -> Dict[DetectionType, Any]:
    """Build the mapping of detection types to adapter callables.

    Each adapter has the signature:
        (entry: GoldenDatasetEntry) -> Tuple[bool, float]

    Returns a dict keyed by DetectionType.  Entries whose detectors fail to
    import are silently omitted (with a logged warning).
    """
    runners: Dict[DetectionType, Any] = {}

    # --- LOOP ---
    try:
        from app.detection.loop import loop_detector, StateSnapshot as LoopStateSnapshot

        def _run_loop(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            raw_states = entry.input_data["states"]
            states = [
                LoopStateSnapshot(
                    agent_id=s["agent_id"],
                    content=s["content"],
                    state_delta=s.get("state_delta", {}),
                    sequence_num=idx,
                )
                for idx, s in enumerate(raw_states)
            ]
            result = loop_detector.detect_loop(states)
            return result.detected, result.confidence

        runners[DetectionType.LOOP] = _run_loop
    except Exception as exc:
        logger.warning("Could not import loop detector: %s", exc)

    # --- PERSONA_DRIFT ---
    try:
        from app.detection.persona import persona_scorer, Agent

        def _run_persona(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            agent_data = entry.input_data["agent"]
            agent = Agent(
                id=agent_data["id"],
                persona_description=agent_data["persona_description"],
                allowed_actions=[],
            )
            output = entry.input_data["output"]
            result = persona_scorer.score_consistency(agent, output)
            # Persona scorer returns "consistent" flag; drift is the opposite.
            drift_detected = not result.consistent
            # Use 1 - score as confidence of drift (lower consistency -> higher
            # confidence of drift).
            confidence = 1.0 - result.score if drift_detected else result.score
            return drift_detected, confidence

        runners[DetectionType.PERSONA_DRIFT] = _run_persona
    except Exception as exc:
        logger.warning("Could not import persona detector: %s", exc)

    # --- HALLUCINATION ---
    try:
        from app.detection.hallucination import hallucination_detector, SourceDocument

        def _run_hallucination(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            raw_sources = entry.input_data.get("sources", [])
            sources = [
                SourceDocument(content=s["content"], metadata=s.get("metadata", {}))
                for s in raw_sources
            ]
            output = entry.input_data["output"]
            result = hallucination_detector.detect_hallucination(output, sources)
            return result.detected, result.confidence

        runners[DetectionType.HALLUCINATION] = _run_hallucination
    except Exception as exc:
        logger.warning("Could not import hallucination detector: %s", exc)

    # --- INJECTION ---
    try:
        from app.detection.injection import injection_detector

        def _run_injection(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            text = entry.input_data["text"]
            result = injection_detector.detect_injection(text)
            return result.detected, result.confidence

        runners[DetectionType.INJECTION] = _run_injection
    except Exception as exc:
        logger.warning("Could not import injection detector: %s", exc)

    # --- OVERFLOW ---
    try:
        from app.detection.overflow import overflow_detector

        def _run_overflow(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            current_tokens = entry.input_data["current_tokens"]
            model = entry.input_data["model"]
            result = overflow_detector.detect_overflow(current_tokens, model)
            return result.detected, result.confidence

        runners[DetectionType.OVERFLOW] = _run_overflow
    except Exception as exc:
        logger.warning("Could not import overflow detector: %s", exc)

    # --- CORRUPTION ---
    try:
        from app.detection.corruption import corruption_detector
        from app.detection.corruption import StateSnapshot as CorruptionStateSnapshot

        def _run_corruption(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            prev_fields = entry.input_data.get("prev_state", {})
            curr_fields = entry.input_data.get("current_state", {})
            prev_snap = CorruptionStateSnapshot(
                state_delta=prev_fields,
                agent_id="calibration",
            )
            curr_snap = CorruptionStateSnapshot(
                state_delta=curr_fields,
                agent_id="calibration",
            )
            result = corruption_detector.detect_corruption_with_confidence(prev_snap, curr_snap)
            return result.detected, result.confidence

        runners[DetectionType.CORRUPTION] = _run_corruption
    except Exception as exc:
        logger.warning("Could not import corruption detector: %s", exc)

    # --- COORDINATION ---
    try:
        from app.detection.coordination import coordination_analyzer, Message

        def _run_coordination(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            raw_messages = entry.input_data["messages"]
            messages = [
                Message(
                    from_agent=m["from_agent"],
                    to_agent=m["to_agent"],
                    content=m["content"],
                    timestamp=m["timestamp"],
                    acknowledged=m.get("acknowledged", False),
                )
                for m in raw_messages
            ]
            agent_ids = entry.input_data["agent_ids"]
            result = coordination_analyzer.analyze_coordination_with_confidence(messages, agent_ids)
            return result.detected, result.confidence

        runners[DetectionType.COORDINATION] = _run_coordination
    except Exception as exc:
        logger.warning("Could not import coordination detector: %s", exc)

    # --- CONTEXT ---
    try:
        from app.detection.context import ContextNeglectDetector

        _context_detector = ContextNeglectDetector()

        def _run_context(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            context = entry.input_data["context"]
            output = entry.input_data["output"]
            result = _context_detector.detect(context, output)
            return result.detected, result.confidence

        runners[DetectionType.CONTEXT] = _run_context
    except Exception as exc:
        logger.warning("Could not import context detector: %s", exc)

    # --- COMMUNICATION ---
    try:
        from app.detection.communication import CommunicationBreakdownDetector

        _comm_detector = CommunicationBreakdownDetector()

        def _run_communication(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            sender_message = entry.input_data["sender_message"]
            receiver_response = entry.input_data["receiver_response"]
            result = _comm_detector.detect(sender_message, receiver_response)
            return result.detected, result.confidence

        runners[DetectionType.COMMUNICATION] = _run_communication
    except Exception as exc:
        logger.warning("Could not import communication detector: %s", exc)

    # --- COMPLETION ---
    try:
        from app.detection.completion import completion_detector

        def _run_completion(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            task = entry.input_data.get("task", "")
            agent_output = entry.input_data.get("agent_output", "")
            result = completion_detector.detect(task, agent_output)
            return result.detected, result.confidence

        runners[DetectionType.COMPLETION] = _run_completion
    except Exception as exc:
        logger.warning("Could not import completion detector: %s", exc)

    # --- GROUNDING (may not have standalone detector) ---
    try:
        from app.detection_enterprise.grounding import grounding_detector  # type: ignore

        def _run_grounding(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            agent_output = entry.input_data.get("agent_output", "")
            source_documents = entry.input_data.get("source_documents", [])
            result = grounding_detector.detect(agent_output, source_documents)
            return result.detected, result.confidence

        runners[DetectionType.GROUNDING] = _run_grounding
    except Exception as exc:
        logger.warning("Skipping GROUNDING detector (not available): %s", exc)

    # --- RETRIEVAL_QUALITY (may not have standalone detector) ---
    try:
        from app.detection_enterprise.retrieval_quality import retrieval_quality_detector  # type: ignore

        def _run_retrieval(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            query = entry.input_data.get("query", "")
            retrieved_documents = entry.input_data.get("retrieved_documents", [])
            agent_output = entry.input_data.get("agent_output", "")
            result = retrieval_quality_detector.detect(query, retrieved_documents, agent_output)
            return result.detected, result.confidence

        runners[DetectionType.RETRIEVAL_QUALITY] = _run_retrieval
    except Exception as exc:
        logger.warning("Skipping RETRIEVAL_QUALITY detector (not available): %s", exc)

    # --- DERAILMENT (tiered detector adapter) ---
    try:
        from app.detection_enterprise.tiered import create_tiered_derailment_detector

        _tiered_derailment = create_tiered_derailment_detector()

        def _run_derailment(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            output = entry.input_data.get("output", "")
            task = entry.input_data.get("task", "")
            result = _tiered_derailment.detect(text=output, context=task)
            return result.detected, result.confidence

        runners[DetectionType.DERAILMENT] = _run_derailment
    except Exception as exc:
        logger.warning("Could not import derailment detector: %s", exc)

    # --- SPECIFICATION (tiered detector adapter) ---
    try:
        from app.detection_enterprise.tiered import create_tiered_specification_detector

        _tiered_specification = create_tiered_specification_detector()

        def _run_specification(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            task_specification = entry.input_data.get("task_specification", "")
            user_intent = entry.input_data.get("user_intent", "")
            result = _tiered_specification.detect(text=task_specification, context=user_intent)
            return result.detected, result.confidence

        runners[DetectionType.SPECIFICATION] = _run_specification
    except Exception as exc:
        logger.warning("Could not import specification detector: %s", exc)

    # --- DECOMPOSITION (tiered detector adapter) ---
    try:
        from app.detection_enterprise.tiered import create_tiered_decomposition_detector

        _tiered_decomposition = create_tiered_decomposition_detector()

        def _run_decomposition(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            decomposition = entry.input_data.get("decomposition", "")
            task_description = entry.input_data.get("task_description", "")
            result = _tiered_decomposition.detect(text=decomposition, context=task_description)
            return result.detected, result.confidence

        runners[DetectionType.DECOMPOSITION] = _run_decomposition
    except Exception as exc:
        logger.warning("Could not import decomposition detector: %s", exc)

    # --- WITHHOLDING (tiered detector adapter) ---
    try:
        from app.detection_enterprise.tiered import create_tiered_withholding_detector

        _tiered_withholding = create_tiered_withholding_detector()

        def _run_withholding(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            agent_output = entry.input_data.get("agent_output", "")
            internal_state = entry.input_data.get("internal_state", "")
            result = _tiered_withholding.detect(text=agent_output, context=internal_state)
            return result.detected, result.confidence

        runners[DetectionType.WITHHOLDING] = _run_withholding
    except Exception as exc:
        logger.warning("Could not import withholding detector: %s", exc)

    # --- WORKFLOW (tiered detector adapter) ---
    try:
        from app.detection_enterprise.tiered import create_tiered_workflow_detector

        _tiered_workflow = create_tiered_workflow_detector()

        def _run_workflow(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            workflow_def = entry.input_data.get("workflow_definition", {})
            workflow_nodes = workflow_def.get("nodes", [])
            workflow_connections = workflow_def.get("connections", [])
            result = _tiered_workflow.detect(
                text=str(workflow_nodes),
                context=str(workflow_connections),
            )
            return result.detected, result.confidence

        runners[DetectionType.WORKFLOW] = _run_workflow
    except Exception as exc:
        logger.warning("Could not import workflow detector: %s", exc)

    return runners


# Build once at module level so callers can reference it.
DETECTOR_RUNNERS: Dict[DetectionType, Any] = _build_detector_runners()


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


def calibrate_single(
    detection_type: DetectionType,
    entries: List[GoldenDatasetEntry],
) -> Optional[CalibrationResult]:
    """Run calibration for a single detector type.

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

    for entry in entries:
        try:
            detected, confidence = runner(entry)
            predictions.append((detected, confidence))
            ground_truths.append(entry.expected_detected)
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

    # Grid search: find the threshold that maximises F1.  Ties broken by
    # higher precision (fewer false positives).
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

    return CalibrationResult(
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
    )


def calibrate_all() -> Dict[str, Any]:
    """Run calibration across all detector types using the golden dataset.

    Returns:
        A dict with the structure::

            {
                "calibrated_at": "<ISO timestamp>",
                "detector_count": <int>,
                "skipped": ["<type>", ...],
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
    dataset = create_default_golden_dataset()
    results: Dict[str, Any] = {}
    skipped: List[str] = []

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
    ]

    for dt in target_types:
        entries = dataset.get_entries_by_type(dt)
        cal = calibrate_single(dt, entries)
        if cal is None:
            skipped.append(dt.value)
            continue
        results[cal.detection_type] = asdict(cal)

    report = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "detector_count": len(results),
        "skipped": skipped,
        "results": results,
    }
    return report


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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    report = calibrate_all()

    # Pretty-print summary to stdout.
    print("\n" + "=" * 72)
    print("  DETECTION THRESHOLD CALIBRATION REPORT")
    print("=" * 72)
    print(f"  Timestamp : {report['calibrated_at']}")
    print(f"  Detectors : {report['detector_count']} calibrated")
    if report["skipped"]:
        print(f"  Skipped   : {', '.join(report['skipped'])}")
    print("-" * 72)

    for dtype, metrics in report["results"].items():
        print(f"\n  [{dtype.upper()}]")
        print(f"    Optimal threshold : {metrics['optimal_threshold']:.2f}")
        print(f"    Precision         : {metrics['precision']:.4f}")
        print(f"    Recall            : {metrics['recall']:.4f}")
        print(f"    F1                : {metrics['f1']:.4f}")
        print(f"    Samples           : {metrics['sample_count']}")
        print(
            f"    Confusion         : TP={metrics['true_positives']}  "
            f"TN={metrics['true_negatives']}  "
            f"FP={metrics['false_positives']}  "
            f"FN={metrics['false_negatives']}"
        )

    print("\n" + "=" * 72)

    # Optionally write the report to a JSON file.
    default_report_path = Path(__file__).parent.parent.parent / "data" / "calibration_report.json"
    save_calibration_report(report, default_report_path)
    print(f"\n  Report written to: {default_report_path}\n")
