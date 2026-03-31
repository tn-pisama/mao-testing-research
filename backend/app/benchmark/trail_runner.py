"""TRAIL Benchmark Runner.

Orchestrates running Pisama detectors against TRAIL traces and
collecting predictions for evaluation.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from app.benchmark.trail_adapter import TRAILSpanAdapter
from app.benchmark.trail_loader import (
    TRAIL_TO_PISAMA,
    TRAILAnnotation,
    TRAILDataLoader,
    TRAILSpan,
    TRAILTrace,
)
from app.benchmark.trail_metrics import (
    CategoryMetrics,
    compute_joint_accuracy,
    compute_macro_f1,
    compute_micro_f1,
    compute_per_category_f1,
    compute_per_impact_breakdown,
)

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    """A single detection prediction on a TRAIL span."""

    trace_id: str
    span_id: str
    trail_category: str  # Original TRAIL category
    pisama_type: str  # Mapped Pisama detector name
    detected: bool
    confidence: float
    latency_ms: float
    error: Optional[str] = None

    def to_tuple(self) -> Tuple[str, str]:
        """Return (span_id, trail_category) for metric computation."""
        return (self.span_id, self.trail_category)


@dataclass
class TRAILBenchmarkResult:
    """Complete TRAIL benchmark run result."""

    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_traces: int = 0
    processed_traces: int = 0
    total_annotations: int = 0
    mapped_annotations: int = 0
    predictions: List[Prediction] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Computed metrics (filled in after run)
    joint_accuracy: float = 0.0
    per_category_f1: Dict[str, CategoryMetrics] = field(default_factory=dict)
    per_impact: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    per_source: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    macro_f1: float = 0.0
    micro_f1: float = 0.0

    @property
    def duration_seconds(self) -> float:
        if not self.completed_at:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def positive_predictions(self) -> List[Prediction]:
        return [p for p in self.predictions if p.detected]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": round(self.duration_seconds, 2),
            "total_traces": self.total_traces,
            "processed_traces": self.processed_traces,
            "total_annotations": self.total_annotations,
            "mapped_annotations": self.mapped_annotations,
            "prediction_count": len(self.predictions),
            "positive_count": len(self.positive_predictions),
            "joint_accuracy": round(self.joint_accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "micro_f1": round(self.micro_f1, 4),
            "error_count": len(self.errors),
        }


class TRAILBenchmarkRunner:
    """Runs Pisama detectors against TRAIL traces.

    For each trace, examines each mapped annotation, extracts the
    annotated span, converts it to detector input format, runs the
    detector, and collects the prediction.
    """

    def __init__(
        self,
        loader: TRAILDataLoader,
        adapter: Optional[TRAILSpanAdapter] = None,
    ):
        self.loader = loader
        self.adapter = adapter or TRAILSpanAdapter()
        self._detector_runners = self._build_detector_runners()

    def _build_detector_runners(self) -> Dict[str, Callable]:
        """Build mapping of Pisama detector types to runner callables.

        Each runner has signature:
            (input_data: dict) -> Tuple[bool, float]

        Returns dict keyed by detector type name. Detectors that fail to
        import are silently skipped.
        """
        runners: Dict[str, Callable] = {}

        # --- HALLUCINATION ---
        try:
            from app.detection.hallucination import (
                hallucination_detector,
                SourceDocument,
            )

            def _run_hallucination(data: Dict[str, Any]) -> Tuple[bool, float]:
                raw_sources = data.get("sources", [])
                sources = [
                    SourceDocument(
                        content=s if isinstance(s, str) else str(s),
                        metadata={},
                    )
                    for s in raw_sources
                ]
                output = data.get("output", "")
                result = hallucination_detector.detect_hallucination(output, sources)
                return result.detected, result.confidence

            runners["hallucination"] = _run_hallucination
        except Exception as exc:
            logger.warning("Could not import hallucination detector: %s", exc)

        # --- CONTEXT ---
        try:
            from app.detection.context import ContextNeglectDetector

            _context_det = ContextNeglectDetector()

            def _run_context(data: Dict[str, Any]) -> Tuple[bool, float]:
                context = data.get("context", "")
                output = data.get("output", "")
                result = _context_det.detect(context=context, output=output)
                return result.detected, result.confidence

            runners["context"] = _run_context
        except Exception as exc:
            logger.warning("Could not import context detector: %s", exc)

        # --- LOOP ---
        try:
            from app.detection.loop import loop_detector, StateSnapshot

            def _run_loop(data: Dict[str, Any]) -> Tuple[bool, float]:
                raw_states = data.get("states", [])
                if len(raw_states) < 3:
                    return False, 0.0
                states = [
                    StateSnapshot(
                        agent_id=s.get("agent_id", f"agent_{i}"),
                        content=s.get("content", ""),
                        state_delta=s.get("state_delta", {}),
                        sequence_num=i,
                    )
                    for i, s in enumerate(raw_states)
                ]
                result = loop_detector.detect_loop(states)
                return result.detected, result.confidence

            runners["loop"] = _run_loop
        except Exception as exc:
            logger.warning("Could not import loop detector: %s", exc)

        # --- DERAILMENT ---
        try:
            from app.detection.derailment import TaskDerailmentDetector

            _derailment_det = TaskDerailmentDetector()

            def _run_derailment(data: Dict[str, Any]) -> Tuple[bool, float]:
                output = data.get("output", "")
                task = data.get("task", "")
                result = _derailment_det.detect(task=task, output=output)
                return result.detected, result.confidence

            runners["derailment"] = _run_derailment
        except Exception as exc:
            logger.warning("Could not import derailment detector: %s", exc)

        # --- COORDINATION ---
        try:
            from app.detection.coordination import coordination_analyzer, Message

            def _run_coordination(data: Dict[str, Any]) -> Tuple[bool, float]:
                raw_msgs = data.get("messages", [])
                agent_ids = data.get("agent_ids", [])
                if len(raw_msgs) < 2:
                    return False, 0.0
                messages = []
                for i, m in enumerate(raw_msgs):
                    sender = m.get("sender", "unknown")
                    # Determine receiver: next different agent
                    receiver = "unknown"
                    for j in range(i + 1, min(i + 3, len(raw_msgs))):
                        other = raw_msgs[j].get("sender", "unknown")
                        if other != sender:
                            receiver = other
                            break
                    messages.append(
                        Message(
                            from_agent=sender,
                            to_agent=receiver,
                            content=m.get("content", ""),
                            timestamp=float(i),
                        )
                    )
                if not agent_ids:
                    agent_ids = list(set(m.from_agent for m in messages))
                result = coordination_analyzer.analyze_coordination(
                    messages, agent_ids
                )
                return result.detected, result.confidence

            runners["coordination"] = _run_coordination
        except Exception as exc:
            logger.warning("Could not import coordination detector: %s", exc)

        # --- COMPLETION ---
        try:
            from app.detection.completion import completion_detector

            def _run_completion(data: Dict[str, Any]) -> Tuple[bool, float]:
                agent_output = data.get("agent_output", "")
                task = data.get("task", "")
                subtasks = data.get("subtasks")
                success_criteria = data.get("success_criteria")
                result = completion_detector.detect(
                    task=task,
                    agent_output=agent_output,
                    subtasks=subtasks,
                    success_criteria=success_criteria,
                )
                return result.detected, result.confidence

            runners["completion"] = _run_completion
        except Exception as exc:
            logger.warning("Could not import completion detector: %s", exc)

        # --- SPECIFICATION ---
        try:
            from app.detection.specification import SpecificationMismatchDetector

            _spec_det = SpecificationMismatchDetector()

            def _run_specification(data: Dict[str, Any]) -> Tuple[bool, float]:
                task_spec = data.get("task_specification", "")
                user_intent = data.get("user_intent", "")
                result = _spec_det.detect(
                    user_intent=user_intent,
                    task_specification=task_spec,
                )
                return result.detected, result.confidence

            runners["specification"] = _run_specification
        except Exception as exc:
            logger.warning("Could not import specification detector: %s", exc)

        # --- WORKFLOW ---
        try:
            from app.detection.workflow import FlawedWorkflowDetector, WorkflowNode

            _workflow_det = FlawedWorkflowDetector()

            def _run_workflow(data: Dict[str, Any]) -> Tuple[bool, float]:
                # Convert workflow steps to WorkflowNode objects
                steps = data.get("workflow_definition", {}).get("steps", [])
                nodes = []
                for i, step in enumerate(steps):
                    node = WorkflowNode(
                        id=str(i),
                        name=step.get("name", f"step_{i}"),
                        node_type=step.get("tool", "action"),
                        incoming=[str(i - 1)] if i > 0 else [],
                        outgoing=[str(i + 1)] if i < len(steps) - 1 else [],
                    )
                    nodes.append(node)
                if not nodes:
                    return False, 0.0
                result = _workflow_det.detect(nodes)
                return result.detected, result.confidence

            runners["workflow"] = _run_workflow
        except Exception as exc:
            logger.warning("Could not import workflow detector: %s", exc)

        # --- GROUNDING ---
        try:
            from app.detection.hallucination import (
                hallucination_detector,
                SourceDocument,
            )

            def _run_grounding(data: Dict[str, Any]) -> Tuple[bool, float]:
                agent_output = data.get("agent_output", "")
                raw_docs = data.get("source_documents", [])
                sources = [
                    SourceDocument(
                        content=d if isinstance(d, str) else str(d),
                        metadata={},
                    )
                    for d in raw_docs
                ]
                result = hallucination_detector.detect_hallucination(
                    agent_output, sources
                )
                return result.detected, result.confidence

            runners["grounding"] = _run_grounding
        except Exception as exc:
            logger.warning("Could not import grounding detector: %s", exc)

        # --- OVERFLOW ---
        try:
            from app.detection.overflow import overflow_detector

            def _run_overflow(data: Dict[str, Any]) -> Tuple[bool, float]:
                context = data.get("context", "")
                token_count = data.get("token_count", 0)
                # Estimate tokens from text if not provided
                if not token_count and context:
                    token_count = len(context) // 4  # rough estimate
                result = overflow_detector.detect_overflow(
                    current_tokens=token_count,
                    model="claude-3-haiku-20240307",
                )
                return result.detected, result.confidence

            runners["overflow"] = _run_overflow
        except Exception as exc:
            logger.warning("Could not import overflow detector: %s", exc)

        # --- RETRIEVAL_QUALITY ---
        try:
            from app.detection.hallucination import (
                hallucination_detector,
                SourceDocument,
            )

            def _run_retrieval_quality(data: Dict[str, Any]) -> Tuple[bool, float]:
                agent_output = data.get("agent_output", "")
                raw_docs = data.get("retrieved_documents", [])
                sources = [
                    SourceDocument(
                        content=d if isinstance(d, str) else str(d),
                        metadata={},
                    )
                    for d in raw_docs
                ]
                if not sources:
                    return True, 0.7  # No retrieval = poor retrieval
                result = hallucination_detector.detect_hallucination(
                    agent_output, sources
                )
                return result.detected, result.confidence

            runners["retrieval_quality"] = _run_retrieval_quality
        except Exception as exc:
            logger.warning("Could not import retrieval_quality detector: %s", exc)

        logger.info(
            "Loaded %d TRAIL detector runners: %s",
            len(runners),
            ", ".join(sorted(runners.keys())),
        )
        return runners

    def run(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> TRAILBenchmarkResult:
        """Run the full TRAIL benchmark.

        Args:
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            TRAILBenchmarkResult with predictions and metrics.
        """
        result = TRAILBenchmarkResult(
            run_id=str(uuid4())[:8],
            started_at=datetime.utcnow(),
        )

        traces = list(self.loader)
        result.total_traces = len(traces)

        for i, trace in enumerate(traces):
            try:
                trace_predictions = self._run_single_trace(trace)
                result.predictions.extend(trace_predictions)
                result.processed_traces += 1

                # Count annotations
                for ann in trace.annotations:
                    result.total_annotations += 1
                    if ann.pisama_type:
                        result.mapped_annotations += 1

            except Exception as exc:
                error_msg = f"Trace {trace.trace_id}: {exc}"
                result.errors.append(error_msg)
                logger.warning(error_msg)

            if progress_callback:
                progress_callback(i + 1, len(traces))

        result.completed_at = datetime.utcnow()

        # Compute metrics
        self._compute_metrics(result, traces)

        return result

    def _run_single_trace(self, trace: TRAILTrace) -> List[Prediction]:
        """Run detectors on a single trace.

        For each mapped annotation, find the annotated span, extract
        detector input, run the detector, and record the prediction.
        """
        predictions: List[Prediction] = []

        for annotation in trace.mapped_annotations:
            pisama_type = annotation.pisama_type
            if not pisama_type:
                continue

            runner = self._detector_runners.get(pisama_type)
            if runner is None:
                predictions.append(
                    Prediction(
                        trace_id=trace.trace_id,
                        span_id=annotation.location,
                        trail_category=annotation.category,
                        pisama_type=pisama_type,
                        detected=False,
                        confidence=0.0,
                        latency_ms=0.0,
                        error=f"No runner for detector: {pisama_type}",
                    )
                )
                continue

            # Find the annotated span
            span = trace.find_span(annotation.location)
            if span is None:
                # Fall back to using the first root span
                span = trace.spans[0] if trace.spans else None
            if span is None:
                predictions.append(
                    Prediction(
                        trace_id=trace.trace_id,
                        span_id=annotation.location,
                        trail_category=annotation.category,
                        pisama_type=pisama_type,
                        detected=False,
                        confidence=0.0,
                        latency_ms=0.0,
                        error="Span not found in trace",
                    )
                )
                continue

            # Extract detector input
            detector_input = self.adapter.extract_for_detector(
                pisama_type, span, trace
            )
            if detector_input is None:
                predictions.append(
                    Prediction(
                        trace_id=trace.trace_id,
                        span_id=annotation.location,
                        trail_category=annotation.category,
                        pisama_type=pisama_type,
                        detected=False,
                        confidence=0.0,
                        latency_ms=0.0,
                        error="Adapter extraction failed",
                    )
                )
                continue

            # Run detector
            start = time.perf_counter()
            try:
                detected, confidence = runner(detector_input)
                latency_ms = (time.perf_counter() - start) * 1000
                predictions.append(
                    Prediction(
                        trace_id=trace.trace_id,
                        span_id=annotation.location,
                        trail_category=annotation.category,
                        pisama_type=pisama_type,
                        detected=detected,
                        confidence=confidence,
                        latency_ms=latency_ms,
                    )
                )
            except Exception as exc:
                latency_ms = (time.perf_counter() - start) * 1000
                predictions.append(
                    Prediction(
                        trace_id=trace.trace_id,
                        span_id=annotation.location,
                        trail_category=annotation.category,
                        pisama_type=pisama_type,
                        detected=False,
                        confidence=0.0,
                        latency_ms=latency_ms,
                        error=str(exc),
                    )
                )

        return predictions

    def _compute_metrics(
        self,
        result: TRAILBenchmarkResult,
        traces: List[TRAILTrace],
    ) -> None:
        """Compute all metrics and attach them to the result."""
        # Build ground truth tuples: (span_id, trail_category)
        ground_truth: List[Tuple[str, str]] = []
        gt_annotations: List[Dict[str, Any]] = []
        for trace in traces:
            for ann in trace.mapped_annotations:
                ground_truth.append((ann.location, ann.category))
                gt_annotations.append({
                    "location": ann.location,
                    "category": ann.category,
                    "impact": ann.impact,
                })

        # Build prediction tuples (only positive detections count)
        pred_tuples = [p.to_tuple() for p in result.positive_predictions]

        # Joint accuracy
        result.joint_accuracy = compute_joint_accuracy(pred_tuples, ground_truth)

        # Per-category F1
        categories = sorted(set(TRAIL_TO_PISAMA.keys()))
        result.per_category_f1 = compute_per_category_f1(
            pred_tuples, ground_truth, categories
        )

        # Macro/micro F1
        result.macro_f1 = compute_macro_f1(result.per_category_f1)
        result.micro_f1 = compute_micro_f1(result.per_category_f1)

        # Per-impact breakdown
        result.per_impact = compute_per_impact_breakdown(
            pred_tuples, ground_truth, gt_annotations
        )

        # Per-source breakdown
        for source_name in ["gaia", "swe-bench"]:
            source_traces = [t for t in traces if t.source == source_name]
            if not source_traces:
                continue

            source_gt: List[Tuple[str, str]] = []
            for trace in source_traces:
                for ann in trace.mapped_annotations:
                    source_gt.append((ann.location, ann.category))

            source_preds = [
                p.to_tuple()
                for p in result.positive_predictions
                if any(
                    t.trace_id == p.trace_id
                    for t in source_traces
                )
            ]

            source_acc = compute_joint_accuracy(source_preds, source_gt)
            source_cat_f1 = compute_per_category_f1(source_preds, source_gt)
            result.per_source[source_name] = {
                "traces": len(source_traces),
                "annotations": len(source_gt),
                "joint_accuracy": round(source_acc, 4),
                "macro_f1": round(compute_macro_f1(source_cat_f1), 4),
            }
