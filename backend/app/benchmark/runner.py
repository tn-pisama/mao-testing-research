"""Benchmark runner for executing detectors on MAST data.

Runs ML-based and rule-based detectors on MAST traces and collects results.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from app.benchmark.mast_loader import ALL_FAILURE_MODES, MASTDataLoader, MASTRecord

logger = logging.getLogger(__name__)


@dataclass
class DetectionAttempt:
    """Result of running a detector on a single record for a single mode."""

    record_id: str
    failure_mode: str
    detector_name: str
    detected: bool
    confidence: float
    latency_ms: float
    error: Optional[str] = None
    raw_result: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "record_id": self.record_id,
            "failure_mode": self.failure_mode,
            "detector_name": self.detector_name,
            "detected": self.detected,
            "confidence": round(self.confidence, 4),
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
        }


@dataclass
class BenchmarkResult:
    """Complete benchmark run result."""

    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_records: int = 0
    processed_records: int = 0
    total_detections: int = 0
    attempts: List[DetectionAttempt] = field(default_factory=list)
    ground_truths: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Total duration in seconds."""
        if not self.completed_at:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    def get_predictions(self) -> Dict[str, Dict[str, Tuple[bool, float]]]:
        """Get predictions in format for MetricsComputer.

        Returns:
            Dict[record_id -> Dict[mode -> (detected, confidence)]]
        """
        predictions: Dict[str, Dict[str, Tuple[bool, float]]] = {}
        for attempt in self.attempts:
            if attempt.record_id not in predictions:
                predictions[attempt.record_id] = {}
            predictions[attempt.record_id][attempt.failure_mode] = (
                attempt.detected,
                attempt.confidence,
            )
        return predictions

    def get_latencies(self) -> Dict[str, Dict[str, float]]:
        """Get latencies in format for MetricsComputer.

        Returns:
            Dict[record_id -> Dict[mode -> latency_ms]]
        """
        latencies: Dict[str, Dict[str, float]] = {}
        for attempt in self.attempts:
            if attempt.record_id not in latencies:
                latencies[attempt.record_id] = {}
            latencies[attempt.record_id][attempt.failure_mode] = attempt.latency_ms
        return latencies

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "total_records": self.total_records,
            "processed_records": self.processed_records,
            "total_detections": self.total_detections,
            "error_count": len(self.errors),
        }


class BenchmarkRunner:
    """Run benchmarks on MAST dataset.

    This runner coordinates detection across multiple detectors and
    collects results with timing information.
    """

    def __init__(
        self,
        loader: MASTDataLoader,
        failure_modes: Optional[List[str]] = None,
        batch_size: int = 32,
    ):
        """Initialize benchmark runner.

        Args:
            loader: MASTDataLoader with loaded data
            failure_modes: List of modes to benchmark (default: all)
            batch_size: Batch size for ML detector
        """
        self.loader = loader
        self.failure_modes = failure_modes or ALL_FAILURE_MODES
        self.batch_size = batch_size

        # Detector instances (lazy loaded)
        self._ml_detector = None
        self._enterprise_detectors: Dict[str, Any] = {}

    def run(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        use_ml_detector: bool = True,
    ) -> BenchmarkResult:
        """Run full benchmark.

        Args:
            progress_callback: Optional callback(processed, total) for progress
            use_ml_detector: Whether to use ML detector (requires training)

        Returns:
            BenchmarkResult with all attempts and ground truths
        """
        result = BenchmarkResult(
            run_id=str(uuid4())[:8],
            started_at=datetime.utcnow(),
            total_records=len(self.loader),
        )

        records = list(self.loader)

        # Collect ground truths
        for record in records:
            result.ground_truths[record.trace_id] = record.ground_truth

        # Process in batches
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]

            try:
                batch_attempts = self._process_batch(
                    batch,
                    use_ml_detector=use_ml_detector,
                )
                result.attempts.extend(batch_attempts)
                result.processed_records += len(batch)
            except Exception as e:
                logger.error(f"Batch {i // self.batch_size} failed: {e}")
                result.errors.append(str(e))

            # Progress callback
            if progress_callback:
                progress_callback(result.processed_records, result.total_records)

        # Count detections
        result.total_detections = sum(1 for a in result.attempts if a.detected)
        result.completed_at = datetime.utcnow()

        return result

    def _process_batch(
        self,
        records: List[MASTRecord],
        use_ml_detector: bool = True,
    ) -> List[DetectionAttempt]:
        """Process a batch of records.

        Args:
            records: List of MASTRecord to process
            use_ml_detector: Whether to use ML detector

        Returns:
            List of DetectionAttempt for all modes and records
        """
        attempts = []

        # Run ML detector in batch mode for F1-F14
        if use_ml_detector:
            ml_attempts = self._run_ml_detector_batch(records)
            attempts.extend(ml_attempts)
        else:
            # Run rule-based detection for F1-F14
            rule_attempts = self._run_rule_based_batch(records)
            attempts.extend(rule_attempts)

        # Run enterprise detectors for F15, F16
        for record in records:
            for mode in self.failure_modes:
                # Skip modes already handled
                if mode in [f"F{i}" for i in range(1, 15)]:
                    continue

                # Run appropriate enterprise detector (F15, F16)
                attempt = self._run_enterprise_detector(record, mode)
                if attempt:
                    attempts.append(attempt)

        return attempts

    def _run_ml_detector_batch(
        self,
        records: List[MASTRecord],
    ) -> List[DetectionAttempt]:
        """Run ML detector on batch of records.

        Args:
            records: List of records to process

        Returns:
            List of DetectionAttempt for F1-F14
        """
        attempts = []

        # Check if ML detector is available
        if self._ml_detector is None:
            try:
                from app.detection_enterprise.ml_detector_v3 import MultiTaskDetector
                self._ml_detector = MultiTaskDetector()
            except ImportError:
                logger.warning("ML detector not available")
                return attempts

        # Check if trained
        if not self._ml_detector.is_trained:
            logger.warning("ML detector not trained, using rule-based detection")
            return self._run_rule_based_batch(records)

        # Prepare batch input
        batch_input = [
            {"trace": {"trajectory": r.trajectory}}
            for r in records
        ]

        # Run batch prediction
        start_time = time.time()
        try:
            predictions = self._ml_detector.predict_batch(batch_input)
            latency_ms = (time.time() - start_time) * 1000 / len(records)

            for record, preds in zip(records, predictions):
                for mode, detected in preds.items():
                    if mode not in self.failure_modes:
                        continue

                    attempts.append(DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name="ml_v3",
                        detected=bool(detected),
                        confidence=0.7 if detected else 0.3,  # Default confidence
                        latency_ms=latency_ms,
                    ))

        except Exception as e:
            logger.error(f"ML detector batch failed: {e}")
            return self._run_rule_based_batch(records)

        return attempts

    def _run_rule_based_batch(
        self,
        records: List[MASTRecord],
    ) -> List[DetectionAttempt]:
        """Run simple rule-based detection as fallback.

        Uses keyword matching for basic detection when ML is unavailable.
        """
        attempts = []

        # Simple keyword patterns for each mode
        mode_keywords = {
            "F1": ["requirement", "specification", "misunderstand", "wrong task"],
            "F2": ["decomposition", "breakdown", "step", "subtask"],
            "F3": ["resource", "memory", "timeout", "limit", "exceed"],
            "F4": ["tool", "missing tool", "no tool", "unavailable"],
            "F5": ["workflow", "loop", "stuck", "infinite", "repeat"],
            "F6": ["derail", "off-topic", "unrelated", "different task"],
            "F7": ["ignore", "forgot", "missing context", "previous"],
            "F8": ["withhold", "omit", "hide", "not tell"],
            "F9": ["usurp", "override", "take over", "not authorized"],
            "F10": ["miscommunication", "misunderstand", "confusion"],
            "F11": ["coordinate", "conflict", "disagree", "inconsistent"],
            "F12": ["validate", "check", "verify", "incorrect output"],
            "F13": ["quality", "skip", "bypass", "no review"],
            "F14": ["complete", "done", "finish", "premature", "incomplete"],
        }

        for record in records:
            trajectory_lower = record.trajectory.lower()

            for mode in self.failure_modes:
                if mode not in mode_keywords:
                    continue

                # Check for keywords
                keywords = mode_keywords[mode]
                matches = sum(1 for kw in keywords if kw in trajectory_lower)

                detected = matches >= 2  # Require at least 2 keyword matches
                confidence = min(0.3 + matches * 0.15, 0.85)

                attempts.append(DetectionAttempt(
                    record_id=record.trace_id,
                    failure_mode=mode,
                    detector_name="rule_based",
                    detected=detected,
                    confidence=confidence if detected else 1 - confidence,
                    latency_ms=0.1,  # Very fast
                ))

        return attempts

    def _run_enterprise_detector(
        self,
        record: MASTRecord,
        mode: str,
    ) -> Optional[DetectionAttempt]:
        """Run enterprise detector for a specific mode.

        Args:
            record: MASTRecord to process
            mode: Failure mode to detect

        Returns:
            DetectionAttempt or None if detector unavailable
        """
        start_time = time.time()

        try:
            if mode == "F15":
                return self._run_grounding_detector(record, start_time)
            elif mode == "F16":
                return self._run_retrieval_quality_detector(record, start_time)
            # Add other enterprise detectors as needed
            else:
                return None

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return DetectionAttempt(
                record_id=record.trace_id,
                failure_mode=mode,
                detector_name="enterprise",
                detected=False,
                confidence=0.0,
                latency_ms=latency_ms,
                error=str(e),
            )

    def _run_grounding_detector(
        self,
        record: MASTRecord,
        start_time: float,
    ) -> DetectionAttempt:
        """Run grounding detector (F15)."""
        if "grounding" not in self._enterprise_detectors:
            from app.detection_enterprise.grounding import GroundingDetector
            self._enterprise_detectors["grounding"] = GroundingDetector()

        detector = self._enterprise_detectors["grounding"]

        # F15 needs output and sources - extract from trajectory
        # For benchmark, we use trajectory as output and empty sources
        # Real usage would have proper source documents
        result = detector.detect(
            agent_output=record.trajectory[:5000],  # Truncate
            source_documents=[],  # No sources in MAST data
            task=record.task,
        )

        latency_ms = (time.time() - start_time) * 1000

        return DetectionAttempt(
            record_id=record.trace_id,
            failure_mode="F15",
            detector_name="grounding",
            detected=result.detected,
            confidence=result.confidence,
            latency_ms=latency_ms,
            raw_result=result,
        )

    def _run_retrieval_quality_detector(
        self,
        record: MASTRecord,
        start_time: float,
    ) -> DetectionAttempt:
        """Run retrieval quality detector (F16)."""
        if "retrieval_quality" not in self._enterprise_detectors:
            from app.detection_enterprise.retrieval_quality import RetrievalQualityDetector
            self._enterprise_detectors["retrieval_quality"] = RetrievalQualityDetector()

        detector = self._enterprise_detectors["retrieval_quality"]

        # F16 needs query and documents - not available in MAST
        # Return not detected with low confidence
        latency_ms = (time.time() - start_time) * 1000

        return DetectionAttempt(
            record_id=record.trace_id,
            failure_mode="F16",
            detector_name="retrieval_quality",
            detected=False,
            confidence=0.5,  # Uncertain
            latency_ms=latency_ms,
            error="No retrieval context in MAST data",
        )

    def train_ml_detector(
        self,
        records: Optional[List[MASTRecord]] = None,
        epochs: int = 50,
        test_split: float = 0.2,
    ) -> Dict[str, Any]:
        """Train ML detector on MAST data.

        Args:
            records: Training records (default: use loader)
            epochs: Training epochs
            test_split: Fraction for test set

        Returns:
            Training results with metrics
        """
        from app.detection_enterprise.ml_detector_v3 import MultiTaskDetector

        if records is None:
            records = list(self.loader)

        # Prepare training data
        train_data = []
        for record in records:
            train_data.append({
                "trace": {"trajectory": record.trajectory},
                "mast_annotation": record.raw_annotations,
            })

        # Initialize and train
        self._ml_detector = MultiTaskDetector(epochs=epochs)
        result = self._ml_detector.train(train_data)

        return result
