"""Threshold calibration for detection algorithms using the golden dataset.

Runs each detector against its golden test samples, finds optimal confidence
thresholds via grid search, and reports precision/recall/F1 metrics.
"""

import hashlib
import json
import logging
import sys
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
    ece: float = 0.0
    f1_ci_lower: float = 0.0
    f1_ci_upper: float = 0.0


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

            # Convert subtask names to dict format expected by the detector.
            # Golden data stores subtasks as plain strings (names); the detector
            # expects List[Dict] with 'name' and 'status' keys.  Without
            # explicit status info we mark them as "pending" so the detector can
            # compare the subtask list against evidence in the agent output.
            raw_subtasks = entry.input_data.get("subtasks", None)
            subtasks = None
            if raw_subtasks:
                subtasks = [
                    {"name": s, "status": "pending"} if isinstance(s, str) else s
                    for s in raw_subtasks
                ]

            success_criteria = entry.input_data.get("success_criteria", None)

            result = completion_detector.detect(
                task,
                agent_output,
                subtasks=subtasks,
                success_criteria=success_criteria,
            )
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

    # --- SPECIFICATION (direct detector adapter) ---
    try:
        from app.detection.specification import SpecificationMismatchDetector

        _spec_detector = SpecificationMismatchDetector()

        def _run_specification(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            user_intent = entry.input_data.get("user_intent", "")
            task_specification = entry.input_data.get("task_specification", "")
            result = _spec_detector.detect(
                user_intent=user_intent,
                task_specification=task_specification,
            )
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

    # --- WORKFLOW (direct detector adapter) ---
    try:
        from app.detection.workflow import FlawedWorkflowDetector, WorkflowNode

        _workflow_detector = FlawedWorkflowDetector(require_error_handling=False)

        def _run_workflow(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
            workflow_def = entry.input_data.get("workflow_definition", {})
            raw_nodes = workflow_def.get("nodes", [])
            raw_connections = workflow_def.get("connections", [])

            # Build incoming/outgoing maps from connections
            outgoing_map: Dict[str, List[str]] = {}
            incoming_map: Dict[str, List[str]] = {}
            for conn in raw_connections:
                src = conn["from"]
                dst = conn["to"]
                outgoing_map.setdefault(src, []).append(dst)
                incoming_map.setdefault(dst, []).append(src)

            # Construct WorkflowNode objects from node names + connection maps
            nodes = []
            for name in raw_nodes:
                node_type = "start" if name not in incoming_map else (
                    "end" if name not in outgoing_map else "agent"
                )
                nodes.append(WorkflowNode(
                    id=name,
                    name=name,
                    node_type=node_type,
                    incoming=incoming_map.get(name, []),
                    outgoing=outgoing_map.get(name, []),
                    has_error_handler="error" in name.lower(),
                    is_terminal=name not in outgoing_map,
                ))

            result = _workflow_detector.detect(nodes)
            return result.detected, result.confidence

        runners[DetectionType.WORKFLOW] = _run_workflow
    except Exception as exc:
        logger.warning("Could not import workflow detector: %s", exc)

    # --- N8N DETECTORS ---
    # All n8n detectors follow the same pattern: instantiate detector,
    # call detect_workflow(workflow_json), return (detected, confidence).
    _n8n_detector_map = {
        DetectionType.N8N_SCHEMA: ("app.detection.n8n.schema_detector", "N8NSchemaDetector"),
        DetectionType.N8N_CYCLE: ("app.detection.n8n.cycle_detector", "N8NCycleDetector"),
        DetectionType.N8N_COMPLEXITY: ("app.detection.n8n.complexity_detector", "N8NComplexityDetector"),
        DetectionType.N8N_ERROR: ("app.detection.n8n.error_detector", "N8NErrorDetector"),
        DetectionType.N8N_RESOURCE: ("app.detection.n8n.resource_detector", "N8NResourceDetector"),
        DetectionType.N8N_TIMEOUT: ("app.detection.n8n.timeout_detector", "N8NTimeoutDetector"),
    }
    for det_type, (module_path, class_name) in _n8n_detector_map.items():
        try:
            import importlib
            mod = importlib.import_module(module_path)
            detector_cls = getattr(mod, class_name)
            detector_instance = detector_cls()

            def _make_n8n_runner(det):
                def _run(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
                    wf = entry.input_data.get("workflow_json", entry.input_data)
                    result = det.detect_workflow(wf)
                    return result.detected, result.confidence
                return _run

            runners[det_type] = _make_n8n_runner(detector_instance)
        except Exception as exc:
            logger.warning("Could not import n8n detector %s: %s", det_type.value, exc)

    return runners


# Build once at module level so callers can reference it.
DETECTOR_RUNNERS: Dict[DetectionType, Any] = _build_detector_runners()


def _apply_tiered_runners() -> None:
    """Replace weak heuristic runners with tiered detectors that escalate to LLM.

    This upgrades detectors that have low F1 scores (<0.70) to use the tiered
    detection system, which escalates ambiguous cases to LLM verification.
    The tiered detectors use lower confidence thresholds to escalate more
    aggressively for these weak detectors.
    """
    from app.detection_enterprise.tiered import (
        TierConfig,
        create_tiered_specification_detector,
        create_tiered_communication_detector,
        create_tiered_coordination_detector,
        create_tiered_completion_detector,
        create_tiered_withholding_detector,
        create_tiered_loop_detector,
    )

    # Lower thresholds → escalate more aggressively for weak detectors
    weak_config = TierConfig(
        rule_confidence_threshold=0.6,
        gray_zone_lower=0.30,
        gray_zone_upper=0.70,
    )

    tiered_map = {
        DetectionType.SPECIFICATION: ("specification", create_tiered_specification_detector),
        DetectionType.COMMUNICATION: ("communication", create_tiered_communication_detector),
        DetectionType.COORDINATION: ("coordination", create_tiered_coordination_detector),
        DetectionType.COMPLETION: ("completion", create_tiered_completion_detector),
        DetectionType.LOOP: ("loop", create_tiered_loop_detector),
    }

    for dt, (name, factory) in tiered_map.items():
        try:
            tiered = factory(config=weak_config)

            def _make_runner(tiered_det, det_type):
                """Create a calibration runner from a tiered detector."""
                def _run(entry: GoldenDatasetEntry) -> Tuple[bool, float]:
                    # Build text/context from entry input_data based on detection type
                    input_data = entry.input_data
                    text = ""
                    context = ""

                    if det_type == "specification":
                        text = input_data.get("task_specification", "")
                        context = input_data.get("user_intent", "")
                    elif det_type == "communication":
                        text = input_data.get("receiver_response", "")
                        context = input_data.get("sender_message", "")
                    elif det_type == "coordination":
                        # Use the existing direct runner for coordination (complex input)
                        return DETECTOR_RUNNERS[DetectionType.COORDINATION](entry)
                    elif det_type == "completion":
                        text = input_data.get("agent_output", "")
                        context = input_data.get("task", "")
                    elif det_type == "loop":
                        # Use the existing direct runner for loop (needs StateSnapshot)
                        return DETECTOR_RUNNERS[DetectionType.LOOP](entry)
                    else:
                        text = str(input_data)

                    result = tiered_det.detect(text=text, context=context)
                    return result.detected, result.confidence
                return _run

            DETECTOR_RUNNERS[dt] = _make_runner(tiered, name)
            logger.info("Upgraded %s to tiered detector", name)
        except Exception as exc:
            logger.warning("Could not create tiered %s: %s", name, exc)


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

        for train_idx, test_idx in splits:
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

        # Average threshold across folds
        avg_threshold = round(sum(fold_best_thresholds) / len(fold_best_thresholds), 2)
        # Snap to nearest grid point
        avg_threshold = min(THRESHOLD_GRID, key=lambda t: abs(t - avg_threshold))

        precision, recall, f1 = _precision_recall_f1(fold_tp, fold_tn, fold_fp, fold_fn)

        # Compute ECE on full predictions using the averaged threshold
        ece = _compute_ece(predictions, ground_truths, avg_threshold)

        logger.info(
            "CV calibration for %s: threshold=%.2f  P=%.3f  R=%.3f  F1=%.3f  ECE=%.4f  (fold thresholds=%s)",
            detection_type.value,
            avg_threshold,
            precision,
            recall,
            f1,
            ece,
            fold_best_thresholds,
        )

        ci_lower, ci_upper = _bootstrap_confidence_interval(
            predictions, ground_truths, avg_threshold,
        )

        return CalibrationResult(
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
            f1_ci_lower=ci_lower,
            f1_ci_upper=ci_upper,
        )

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
        ece=ece,
        f1_ci_lower=ci_lower,
        f1_ci_upper=ci_upper,
    )


def calibrate_all(
    phoenix_tracer: Optional[Any] = None,
    splits: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run calibration across all detector types using the golden dataset.

    Args:
        phoenix_tracer: Optional OTEL tracer for Phoenix observability.
            When provided, each detector calibration is exported as a span.
        splits: If provided, only use entries from these splits (e.g.
            ``["train", "val"]``).  When ``None``, uses all entries
            (backward-compatible).

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

        if cal is None:
            skipped.append(dt.value)
        else:
            results[cal.detection_type] = asdict(cal)
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

    report = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "detector_count": len(results),
        "skipped": skipped,
        "splits_used": splits,
        "results": results,
    }
    return report


# ---------------------------------------------------------------------------
# Holdout evaluation (uses test split only)
# ---------------------------------------------------------------------------


def evaluate_holdout(
    calibration_report: Dict[str, Any],
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
    dataset = create_default_golden_dataset()
    cal_results = calibration_report.get("results", {})
    eval_results: Dict[str, Any] = {}

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

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "split": "test",
        "detector_count": len(eval_results),
        "results": eval_results,
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
            entry = {
                "name": meta["name"],
                "tier": meta["tier"],
                "status": status,
                "readiness": readiness,
                "module": meta["module"],
                "f1_score": f1,
                "precision": precision,
                "recall": metrics.get("recall", 0.0),
                "optimal_threshold": metrics.get("optimal_threshold", 0.5),
                "sample_count": sample_count,
                "f1_ci_lower": metrics.get("f1_ci_lower", 0.0),
                "f1_ci_upper": metrics.get("f1_ci_upper", 0.0),
                "last_calibrated": calibrated_at,
            }

        capabilities[dtype_value] = entry

    registry = {
        "version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": capabilities,
        "summary": {
            "total": len(capabilities),
            "production": readiness_counts["production"],
            "beta": readiness_counts["beta"],
            "experimental": readiness_counts["experimental"],
            "failing": readiness_counts["failing"],
            "untested": readiness_counts["untested"],
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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detection threshold calibration")
    parser.add_argument("--compare", type=int, metavar="N", help="Compare last N experiments")
    parser.add_argument("--no-history", action="store_true", help="Skip saving to history")
    parser.add_argument(
        "--generate-data", action="store_true",
        help="Generate LLM golden data for types below 30 samples, then re-calibrate",
    )
    parser.add_argument(
        "--generate-target", type=int, default=50, metavar="N",
        help="Target entries per type for --generate-data (default: 50)",
    )
    parser.add_argument(
        "--difficulty", type=str, choices=["easy", "medium", "hard", "mixed"],
        default="mixed",
        help="Difficulty level for --generate-data (default: mixed = easy/medium/hard passes)",
    )
    parser.add_argument(
        "--phoenix", action="store_true",
        help="Export calibration spans to Phoenix via OTEL",
    )
    parser.add_argument(
        "--phoenix-endpoint", type=str, default="http://localhost:6006/v1/traces",
        help="Phoenix OTLP endpoint (default: http://localhost:6006/v1/traces)",
    )
    parser.add_argument(
        "--apply-thresholds", action="store_true",
        help="Auto-apply calibrated thresholds to threshold config",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print report only — skip threshold application and history save",
    )
    parser.add_argument(
        "--registry", action="store_true",
        help="Generate/update capability_registry.json from calibration results",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print progress log summary and exit",
    )
    parser.add_argument(
        "--tiered", action="store_true",
        help="Use tiered detectors (with LLM escalation) instead of raw heuristic detectors",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.status:
        from app.detection_enterprise.progress_log import ProgressLog
        print(ProgressLog().format_status())
        sys.exit(0)

    if args.compare:
        from app.detection_enterprise.calibration_history import CalibrationHistory
        history = CalibrationHistory()
        print(history.format_comparison(args.compare))
        sys.exit(0)

    if args.registry and not args.generate_data:
        # Standalone registry generation from existing report (no re-calibration)
        report_path = Path(__file__).parent.parent.parent / "data" / "calibration_report.json"
        if not report_path.exists():
            print("  ERROR: No calibration report found. Run calibration first.")
            sys.exit(1)
        with open(report_path) as f:
            existing_report = json.load(f)
        registry = generate_capability_registry(existing_report)
        s = registry["summary"]
        print(f"  Registry: {s['production']} production, {s['beta']} beta, "
              f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")
        try:
            from app.detection_enterprise.progress_log import ProgressLog
            ProgressLog().log("registry_updated", "calibrate.py",
                f"Registry: {s['production']} production, {s['beta']} beta, "
                f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")
        except Exception:
            pass
        sys.exit(0)

    # --- LLM golden data expansion ---
    if args.generate_data:
        from app.detection_enterprise.golden_data_generator import GoldenDataGenerator
        from app.detection_enterprise.golden_dataset import create_default_golden_dataset

        generator = GoldenDataGenerator()
        if not generator.is_available:
            print("  ERROR: No ANTHROPIC_API_KEY set — cannot generate data")
            sys.exit(1)

        dataset = create_default_golden_dataset()
        print(f"\n  Current dataset: {len(dataset.entries)} entries")
        use_difficulty_passes = (args.difficulty == "mixed")
        new_entries = generator.generate_all(
            dataset,
            target_per_type=args.generate_target,
            use_difficulty_passes=use_difficulty_passes,
        )
        if new_entries:
            for entry in new_entries:
                dataset.add_entry(entry)
            save_path = Path(__file__).parent.parent.parent / "data" / "golden_dataset_expanded.json"
            dataset.save(save_path)
            print(f"  Generated {len(new_entries)} new entries")
            print(f"  Expanded dataset saved to: {save_path}")
        else:
            print("  All types already at target — no generation needed")
        print()

    # --- Phoenix OTEL setup ---
    phoenix_tracer = None
    if args.phoenix:
        try:
            from app.detection_enterprise.phoenix_exporter import setup_phoenix_exporter
            phoenix_tracer = setup_phoenix_exporter(endpoint=args.phoenix_endpoint)
            print(f"  Phoenix tracing enabled → {args.phoenix_endpoint}")
        except Exception as exc:
            print(f"  WARNING: Could not enable Phoenix tracing: {exc}")

    # If --tiered, rebuild detector runners to use tiered detectors
    if args.tiered:
        _apply_tiered_runners()

    report = calibrate_all(phoenix_tracer=phoenix_tracer)

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
        f1 = metrics['f1']
        ci_lo = metrics.get('f1_ci_lower', 0.0)
        ci_hi = metrics.get('f1_ci_upper', 0.0)
        readiness = _compute_readiness(
            f1, metrics.get('precision', 0.0), metrics.get('sample_count', 0),
        )
        print(f"\n  [{dtype.upper()}]")
        print(f"    Optimal threshold : {metrics['optimal_threshold']:.2f}")
        print(f"    Precision         : {metrics['precision']:.4f}")
        print(f"    Recall            : {metrics['recall']:.4f}")
        print(f"    F1                : {f1:.4f} (95% CI: {ci_lo:.2f}\u2013{ci_hi:.2f})")
        print(f"    Readiness         : {readiness}")
        print(f"    Samples           : {metrics['sample_count']}")
        print(
            f"    Confusion         : TP={metrics['true_positives']}  "
            f"TN={metrics['true_negatives']}  "
            f"FP={metrics['false_positives']}  "
            f"FN={metrics['false_negatives']}"
        )
        if "ece" in metrics:
            print(f"    ECE               : {metrics['ece']:.4f}")

    print("\n" + "=" * 72)

    # Apply thresholds (unless --dry-run)
    if args.apply_thresholds and not args.dry_run:
        from app.detection_enterprise.threshold_config import ThresholdConfig
        config = ThresholdConfig()
        changes = config.update_from_calibration(report)
        config.save()
        if changes:
            print(f"\n  Thresholds updated ({len(changes)} changed):")
            for dtype, delta in sorted(changes.items()):
                print(f"    {dtype}: {delta['old']:.2f} \u2192 {delta['new']:.2f} (F1={delta['f1']:.4f})")
        else:
            print(f"\n  Thresholds unchanged (no significant changes)")

    if args.dry_run:
        print("\n  Dry run \u2014 no thresholds or history saved")

    # Save to history (unless --no-history or --dry-run)
    if not args.no_history and not args.dry_run:
        from app.detection_enterprise.calibration_history import (
            CalibrationHistory, create_experiment_from_report,
        )
        history = CalibrationHistory()
        experiment = create_experiment_from_report(report)
        history.append(experiment)
        print(f"  Experiment {experiment.id} saved to history")

    # Write the report to a JSON file.
    default_report_path = Path(__file__).parent.parent.parent / "data" / "calibration_report.json"
    save_calibration_report(report, default_report_path)
    print(f"\n  Report written to: {default_report_path}")

    # Generate capability registry (if --registry or always after calibration)
    if args.registry:
        registry = generate_capability_registry(report)
        s = registry["summary"]
        print(f"  Registry: {s['production']} production, {s['beta']} beta, "
              f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")

    # Log to progress log (unless dry-run)
    if not args.dry_run:
        try:
            from app.detection_enterprise.progress_log import ProgressLog
            progress = ProgressLog()
            avg_f1 = sum(m["f1"] for m in report["results"].values()) / len(report["results"])
            progress.log("calibration_run", "calibrate.py",
                f"Calibrated {report['detector_count']} detectors, avg F1={avg_f1:.4f}",
                detector_count=report["detector_count"],
                average_f1=round(avg_f1, 4),
                skipped=report["skipped"])
            if args.apply_thresholds:
                progress.log("threshold_update", "calibrate.py",
                    f"Updated thresholds from calibration")
            if args.registry:
                s = registry["summary"]
                progress.log("registry_updated", "calibrate.py",
                    f"Registry: {s['production']} production, {s['beta']} beta, "
                    f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")
        except Exception:
            pass  # Progress logging is non-critical

    print()
