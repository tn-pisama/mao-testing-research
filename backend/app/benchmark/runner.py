"""Benchmark runner for executing detectors on MAST data.

Runs ML-based, rule-based, and LLM-based detectors on MAST traces and collects results.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from app.benchmark.mast_loader import (
    ALL_FAILURE_MODES,
    FAILURE_MODE_NAMES,
    MASTDataLoader,
    MASTRecord,
)

logger = logging.getLogger(__name__)

# Semantic failure modes that benefit from LLM-based detection
# These are modes where keyword matching fundamentally fails because
# failures are structural/behavioral rather than linguistic
LLM_SEMANTIC_MODES = {"F6", "F8", "F9", "F13"}


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
        api_key: Optional[str] = None,
    ):
        """Initialize benchmark runner.

        Args:
            loader: MASTDataLoader with loaded data
            failure_modes: List of modes to benchmark (default: all)
            batch_size: Batch size for ML detector
            api_key: Anthropic API key for LLM detection
        """
        import os
        self.loader = loader
        self.failure_modes = failure_modes or ALL_FAILURE_MODES
        self.batch_size = batch_size
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        # Load additional API keys for round-robin (if available)
        self._api_keys: List[str] = []
        if self._api_key:
            self._api_keys.append(self._api_key)
        for i in range(2, 10):  # Support up to 9 additional keys
            key = os.getenv(f"ANTHROPIC_API_KEY_{i}")
            if key:
                self._api_keys.append(key)
        if len(self._api_keys) > 1:
            logger.info(f"Loaded {len(self._api_keys)} API keys for round-robin")

        # Detector instances (lazy loaded)
        self._ml_detector = None
        self._enterprise_detectors: Dict[str, Any] = {}

    def run(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        use_ml_detector: bool = True,
        use_llm_detector: bool = False,
        use_hybrid_detector: bool = False,
        llm_model: str = "haiku",
        llm_modes: Optional[List[str]] = None,
        max_llm_records: Optional[int] = None,
    ) -> BenchmarkResult:
        """Run full benchmark.

        Args:
            progress_callback: Optional callback(processed, total) for progress
            use_ml_detector: Whether to use ML detector (requires training)
            use_llm_detector: Whether to use LLM detector for semantic modes
            use_hybrid_detector: Whether to use hybrid turn-aware + LLM detection
            llm_model: LLM model to use ('haiku', 'sonnet', 'opus')
            llm_modes: Failure modes for LLM detection (default: F6,F8,F9,F13)
            max_llm_records: Maximum records for LLM detection (cost control)

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

        # Determine which modes to handle with LLM vs rule-based
        llm_detection_modes = set()
        if use_llm_detector:
            llm_detection_modes = set(llm_modes) if llm_modes else LLM_SEMANTIC_MODES
            llm_detection_modes = llm_detection_modes & set(self.failure_modes)
            logger.info(f"Using LLM detection for modes: {llm_detection_modes}")

        # Process in batches (for rule-based/ML detection)
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]

            try:
                batch_attempts = self._process_batch(
                    batch,
                    use_ml_detector=use_ml_detector,
                    skip_modes=llm_detection_modes,  # Skip LLM modes in batch
                )
                result.attempts.extend(batch_attempts)
                result.processed_records += len(batch)
            except Exception as e:
                logger.error(f"Batch {i // self.batch_size} failed: {e}")
                result.errors.append(str(e))

            # Progress callback
            if progress_callback:
                progress_callback(result.processed_records, result.total_records)

        # Run LLM detection if enabled (but not if hybrid is enabled - hybrid handles semantic modes)
        if use_llm_detector and llm_detection_modes and not use_hybrid_detector:
            logger.info(f"Running LLM detection ({llm_model}) for {len(llm_detection_modes)} modes...")
            try:
                llm_attempts = self._run_llm_detection(
                    records,
                    llm_modes=list(llm_detection_modes),
                    model=llm_model,
                    max_records=max_llm_records,
                )
                result.attempts.extend(llm_attempts)
                logger.info(f"LLM detection complete: {len(llm_attempts)} attempts")
            except Exception as e:
                logger.error(f"LLM detection failed: {e}")
                result.errors.append(f"LLM detection: {str(e)}")

        # Run hybrid detection if enabled (turn-aware + LLM escalation)
        if use_hybrid_detector:
            hybrid_modes = llm_modes if llm_modes else ["F6", "F8", "F9", "F13"]
            hybrid_modes = [m for m in hybrid_modes if m in self.failure_modes]
            logger.info(f"Running hybrid detection for modes: {hybrid_modes}")
            try:
                hybrid_attempts = self._run_hybrid_detection(
                    records,
                    modes=hybrid_modes,
                    llm_escalation=bool(self._api_key),
                )
                result.attempts.extend(hybrid_attempts)
                logger.info(f"Hybrid detection complete: {len(hybrid_attempts)} attempts")
            except Exception as e:
                logger.error(f"Hybrid detection failed: {e}")
                result.errors.append(f"Hybrid detection: {str(e)}")

        # Count detections
        result.total_detections = sum(1 for a in result.attempts if a.detected)
        result.completed_at = datetime.utcnow()

        return result

    def _process_batch(
        self,
        records: List[MASTRecord],
        use_ml_detector: bool = True,
        skip_modes: Optional[set] = None,
    ) -> List[DetectionAttempt]:
        """Process a batch of records.

        Args:
            records: List of MASTRecord to process
            use_ml_detector: Whether to use ML detector
            skip_modes: Modes to skip (handled by LLM detection)

        Returns:
            List of DetectionAttempt for all modes and records
        """
        skip_modes = skip_modes or set()
        attempts = []

        # Run ML detector in batch mode for F1-F14
        if use_ml_detector:
            ml_attempts = self._run_ml_detector_batch(records, skip_modes)
            attempts.extend(ml_attempts)
        else:
            # Run rule-based detection for F1-F14
            rule_attempts = self._run_rule_based_batch(records, skip_modes)
            attempts.extend(rule_attempts)

        # Run enterprise detectors for F15, F16
        for record in records:
            for mode in self.failure_modes:
                # Skip modes already handled or being handled by LLM
                if mode in [f"F{i}" for i in range(1, 15)] or mode in skip_modes:
                    continue

                # Run appropriate enterprise detector (F15, F16)
                attempt = self._run_enterprise_detector(record, mode)
                if attempt:
                    attempts.append(attempt)

        return attempts

    def _run_ml_detector_batch(
        self,
        records: List[MASTRecord],
        skip_modes: Optional[set] = None,
    ) -> List[DetectionAttempt]:
        """Run ML detector on batch of records.

        Args:
            records: List of records to process
            skip_modes: Modes to skip (handled by LLM detection)

        Returns:
            List of DetectionAttempt for F1-F14
        """
        skip_modes = skip_modes or set()
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
            return self._run_rule_based_batch(records, skip_modes)

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
                    if mode not in self.failure_modes or mode in skip_modes:
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
            return self._run_rule_based_batch(records, skip_modes)

        return attempts

    def _run_rule_based_batch(
        self,
        records: List[MASTRecord],
        skip_modes: Optional[set] = None,
    ) -> List[DetectionAttempt]:
        """Run rule-based detection as fallback.

        Uses improved keyword matching and turn-aware detectors for F6/F9.
        """
        skip_modes = skip_modes or set()
        attempts = []

        # Improved keyword patterns for each mode (based on MAST vocabulary)
        mode_keywords = {
            "F1": [
                "requirement", "specification", "misunderstand", "wrong task",
                "not what", "different from", "instead of", "should have",
                "misinterpret", "incorrect understanding",
            ],
            "F2": [
                "decomposition", "breakdown", "step", "subtask",
                "break down", "divide", "split", "sub-task",
            ],
            "F3": [
                "resource", "memory", "timeout", "limit", "exceed",
                "out of memory", "rate limit", "quota", "capacity",
                "too many", "maximum", "exceeded",
            ],
            "F4": [
                "tool not found", "no such", "undefined function",
                "cannot access", "not available", "missing tool",
                "tool error", "function not", "command not found",
                "module not", "import error",
            ],
            "F5": [
                "repeated", "same step", "cycle", "again", "already",
                "loop", "stuck", "infinite", "keep doing", "over and over",
                "same output", "no progress", "circular",
            ],
            "F6": [
                "instead of", "wrong task", "different", "unrelated",
                "off-topic", "not relevant", "another topic", "tangent",
                "deviate", "stray", "drift",
            ],
            "F7": [
                "ignore", "forgot", "missing context", "previous",
                "didn't consider", "overlooked", "failed to remember",
                "lost context", "not mentioned",
            ],
            "F8": [
                "didn't mention", "failed to include", "missing information",
                "incomplete", "left out", "omitted", "not disclosed",
                "hidden", "concealed", "not shared",
            ],
            "F9": [
                "not my role", "outside scope", "took over", "override",
                "beyond authority", "not authorized", "exceeded role",
                "usurp", "overstep",
            ],
            "F10": [
                "miscommunication", "misunderstand", "confusion",
                "unclear", "ambiguous", "conflicting message",
            ],
            "F11": [
                "coordinate", "conflict", "disagree", "inconsistent",
                "contradiction", "different opinion", "clash",
                "out of sync", "misaligned",
            ],
            "F12": [
                "validate", "check", "verify", "incorrect output",
                "wrong result", "error in output", "failed validation",
                "invalid", "broken",
            ],
            "F13": [
                "without testing", "skip", "bypass", "no review",
                "no validation", "quality", "untested", "unreviewed",
                "skip check", "pushed directly", "no quality",
            ],
            "F14": [
                "premature", "incomplete", "not finished", "partial",
                "early termination", "abandoned", "stopped early",
                "done incorrectly", "falsely complete",
            ],
        }

        # Run turn-aware detection for semantic modes (unless skipped for LLM)
        turn_aware_modes = {"F6", "F8"}  # Modes handled by turn-aware detectors
        modes_to_run = [m for m in turn_aware_modes if m not in skip_modes]
        if modes_to_run:
            turn_aware_attempts = self._run_turn_aware_detectors(records, modes_to_run)
            attempts.extend(turn_aware_attempts)

        for record in records:
            trajectory_lower = record.trajectory.lower()

            for mode in self.failure_modes:
                # Skip modes handled by turn-aware detectors or LLM
                if mode in turn_aware_modes or mode in skip_modes:
                    continue

                if mode not in mode_keywords:
                    continue

                # Check for keywords
                keywords = mode_keywords[mode]
                matches = sum(1 for kw in keywords if kw in trajectory_lower)

                # Lower threshold for modes with longer keyword lists
                threshold = 1 if len(keywords) > 6 else 2
                detected = matches >= threshold
                confidence = min(0.3 + matches * 0.1, 0.85)

                attempts.append(DetectionAttempt(
                    record_id=record.trace_id,
                    failure_mode=mode,
                    detector_name="rule_based",
                    detected=detected,
                    confidence=confidence if detected else 1 - confidence,
                    latency_ms=0.1,  # Very fast
                ))

        return attempts

    def _run_turn_aware_detectors(
        self,
        records: List[MASTRecord],
        modes: Optional[List[str]] = None,
    ) -> List[DetectionAttempt]:
        """Run turn-aware detectors for semantic modes (F6, F8).

        Uses turn-aware detectors with parsed conversation turns.

        Args:
            records: List of records to process
            modes: List of modes to run (default: ['F6', 'F8'])
        """
        if modes is None:
            modes = ["F6", "F8"]

        # Filter to modes in target list
        modes = [m for m in modes if m in self.failure_modes]
        if not modes:
            return []

        attempts = []

        try:
            from app.benchmark.trajectory_parser import parse_trajectory_to_turns
            from app.detection.turn_aware.derailment import TurnAwareDerailmentDetector
            from app.detection.turn_aware.withholding import TurnAwareInformationWithholdingDetector
        except ImportError as e:
            logger.warning(f"Turn-aware detector import failed: {e}")
            return attempts

        # Initialize detectors
        detectors = {}
        if "F6" in modes:
            detectors["F6"] = ("turn_aware_derailment", None)  # Created per-record with framework
        if "F8" in modes:
            detectors["F8"] = ("turn_aware_withholding", TurnAwareInformationWithholdingDetector())

        for record in records:
            start_time = time.time()
            try:
                # Parse trajectory into turns
                turns = parse_trajectory_to_turns(record.trajectory, record.framework)

                if len(turns) < 2:
                    # Not enough turns for meaningful analysis
                    for mode in modes:
                        detector_name = detectors[mode][0] if mode in detectors else f"turn_aware_{mode.lower()}"
                        attempts.append(DetectionAttempt(
                            record_id=record.trace_id,
                            failure_mode=mode,
                            detector_name=detector_name,
                            detected=False,
                            confidence=0.3,
                            latency_ms=(time.time() - start_time) * 1000,
                        ))
                    continue

                # Run each detector
                for mode in modes:
                    mode_start = time.time()

                    if mode == "F6":
                        # Derailment detector (created per-record with framework)
                        detector = TurnAwareDerailmentDetector(
                            framework=record.framework,
                            drift_threshold=0.50,
                            require_strong_evidence=False,
                        )
                        result = detector.detect(turns)
                        detector_name = "turn_aware_derailment"

                    elif mode == "F8":
                        # Withholding detector
                        detector = detectors["F8"][1]
                        metadata = {
                            "task_description": record.task,
                            "framework": record.framework,
                        }
                        result = detector.detect(turns=turns, conversation_metadata=metadata)
                        detector_name = "turn_aware_withholding"
                    else:
                        continue

                    latency_ms = (time.time() - mode_start) * 1000

                    attempts.append(DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name=detector_name,
                        detected=result.detected,
                        confidence=result.confidence,
                        latency_ms=latency_ms,
                        raw_result=result,
                    ))

            except Exception as e:
                logger.warning(f"Turn-aware detection failed for {record.trace_id}: {e}")
                for mode in modes:
                    detector_name = detectors.get(mode, (f"turn_aware_{mode.lower()}",))[0]
                    attempts.append(DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name=detector_name,
                        detected=False,
                        confidence=0.0,
                        latency_ms=(time.time() - start_time) * 1000,
                        error=str(e),
                    ))

        return attempts

    def _run_llm_detection(
        self,
        records: List[MASTRecord],
        llm_modes: Optional[List[str]] = None,
        model: str = "haiku",
        max_records: Optional[int] = None,
        use_few_shot: bool = True,
    ) -> List[DetectionAttempt]:
        """Run LLM-based detection for semantic failure modes.

        Uses Claude to analyze trajectories for failure modes that keyword
        matching cannot detect (structural/behavioral failures).

        Args:
            records: List of records to process
            llm_modes: Failure modes to use LLM for (default: F6, F8, F9, F13)
            model: Model to use ('haiku', 'sonnet', 'opus')
            max_records: Maximum records to process (for cost control)
            use_few_shot: Include few-shot examples in prompt

        Returns:
            List of DetectionAttempt for LLM-detected modes
        """
        if llm_modes is None:
            llm_modes = list(LLM_SEMANTIC_MODES)

        # Filter to only modes in our target list
        llm_modes = [m for m in llm_modes if m in self.failure_modes]
        if not llm_modes:
            return []

        # Apply record limit if specified
        if max_records:
            records = records[:max_records]

        # Run async detection
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self._run_llm_detection_async(records, llm_modes, model, use_few_shot)
        )

    async def _run_llm_detection_async(
        self,
        records: List[MASTRecord],
        llm_modes: List[str],
        model: str,
        use_few_shot: bool,
    ) -> List[DetectionAttempt]:
        """Async implementation of LLM detection."""
        from anthropic import AsyncAnthropic

        if not self._api_key:
            logger.error("ANTHROPIC_API_KEY not set, skipping LLM detection")
            return []

        client = AsyncAnthropic(api_key=self._api_key)

        # Model selection
        model_map = {
            "haiku": "claude-3-5-haiku-20241022",
            "sonnet": "claude-sonnet-4-20250514",
            "opus": "claude-opus-4-20250514",
        }
        model_id = model_map.get(model, model_map["haiku"])

        # Get few-shot examples if enabled
        few_shot_examples = {}
        if use_few_shot:
            try:
                from app.benchmark.few_shot_bank import MAST_FEW_SHOT_EXAMPLES
                few_shot_examples = MAST_FEW_SHOT_EXAMPLES
            except ImportError:
                logger.warning("Few-shot bank not available, proceeding without examples")

        attempts = []
        total = len(records) * len(llm_modes)
        processed = 0

        for record in records:
            for mode in llm_modes:
                # Skip if mode not in ground truth
                if mode not in record.ground_truth:
                    continue

                start_time = time.time()

                try:
                    # Build prompt
                    prompt = self._build_llm_prompt(
                        record, mode, few_shot_examples.get(mode, {})
                    )

                    # Call Claude
                    response = await client.messages.create(
                        model=model_id,
                        max_tokens=1000,
                        messages=[{"role": "user", "content": prompt}],
                    )

                    # Parse response
                    content = response.content[0].text
                    detected, confidence, reasoning = self._parse_llm_response(content)

                    latency_ms = (time.time() - start_time) * 1000

                    attempts.append(DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name=f"llm_{model}",
                        detected=detected,
                        confidence=confidence,
                        latency_ms=latency_ms,
                        raw_result={"reasoning": reasoning[:500]},
                    ))

                    processed += 1
                    if processed % 10 == 0:
                        logger.info(f"LLM detection progress: {processed}/{total}")

                except Exception as e:
                    latency_ms = (time.time() - start_time) * 1000
                    logger.warning(f"LLM detection failed for {record.trace_id}/{mode}: {e}")
                    attempts.append(DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name=f"llm_{model}",
                        detected=False,
                        confidence=0.0,
                        latency_ms=latency_ms,
                        error=str(e),
                    ))

        return attempts

    def _build_llm_prompt(
        self,
        record: MASTRecord,
        mode: str,
        few_shot: Dict[str, Any],
    ) -> str:
        """Build LLM prompt for failure mode detection."""
        mode_name = FAILURE_MODE_NAMES.get(mode, mode)

        # Mode-specific definitions
        mode_definitions = {
            "F6": """Task Derailment occurs when an agent deviates from the intended objective
or focus of the task, pursuing unrelated work or losing track of the original goal.
Signs include: implementing different features than requested, working on tangential
problems, or shifting focus mid-task to unrelated concerns.""",
            "F8": """Information Withholding occurs when an agent fails to share or communicate
important data or insights that could impact decision-making. Signs include: having
relevant information but not mentioning it, hiding errors, or failing to communicate
important findings to other agents.""",
            "F9": """Role Usurpation occurs when an agent acts outside their designated role
or takes over responsibilities assigned to another agent. Signs include: a CEO writing
code, a tester making design decisions, or any agent performing tasks outside their
defined role boundaries.""",
            "F13": """Quality Gate Bypass occurs when testing, review, or validation steps
are skipped, inadequate, or shallow. Signs include: tests that don't verify actual
requirements, reviews that rubber-stamp without examination, or pushing code without
proper quality checks.""",
        }

        definition = mode_definitions.get(mode, f"Failure mode {mode}: {mode_name}")

        # Build few-shot section
        few_shot_section = ""
        if few_shot:
            examples = []
            for pos in few_shot.get("positive", [])[:2]:
                examples.append(f"""
**Example of {mode} (YES):**
Task: {pos.get('task', 'N/A')}
Trajectory snippet: {pos.get('trajectory_snippet', 'N/A')[:500]}
Why: {pos.get('explanation', 'This is a clear example of this failure mode.')}
""")
            for neg in few_shot.get("negative", [])[:1]:
                examples.append(f"""
**Example of NOT {mode} (NO):**
Task: {neg.get('task', 'N/A')}
Trajectory snippet: {neg.get('trajectory_snippet', 'N/A')[:500]}
Why: {neg.get('explanation', 'This does not exhibit this failure mode.')}
""")
            if examples:
                few_shot_section = "\n## Reference Examples\n" + "\n".join(examples)

        # Truncate trajectory to fit context
        trajectory = record.trajectory[:80000]  # ~100K chars max

        prompt = f"""You are an expert evaluator of multi-agent AI systems. Your task is to
determine if a trace exhibits failure mode {mode} ({mode_name}).

## Failure Mode Definition

{definition}
{few_shot_section}

## Trace to Evaluate

**Task/Goal:** {record.task[:1000]}

**Framework:** {record.framework}

**Agent Trajectory:**
```
{trajectory}
```

## Your Evaluation

Does this trace exhibit failure mode {mode} ({mode_name})?

Respond in JSON format:
```json
{{
  "verdict": "YES" or "NO",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation citing specific evidence>"
}}
```
"""
        return prompt

    def _parse_llm_response(self, content: str) -> Tuple[bool, float, str]:
        """Parse LLM response into (detected, confidence, reasoning)."""
        import json
        import re

        # Try to extract JSON
        json_match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                verdict = parsed.get("verdict", "").upper()
                confidence = float(parsed.get("confidence", 0.5))
                reasoning = parsed.get("reasoning", "")
                return verdict == "YES", confidence, reasoning
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: keyword detection
        content_upper = content.upper()
        if '"YES"' in content_upper or "VERDICT: YES" in content_upper:
            return True, 0.7, content[:500]
        elif '"NO"' in content_upper or "VERDICT: NO" in content_upper:
            return False, 0.7, content[:500]

        return False, 0.5, content[:500]

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

    def _run_hybrid_detection(
        self,
        records: List[MASTRecord],
        modes: Optional[List[str]] = None,
        llm_escalation: bool = True,
    ) -> List[DetectionAttempt]:
        """Run hybrid detection: Turn-aware first, LLM escalation for ambiguous.

        This method uses a two-phase approach:
        1. Run turn-aware detectors (fast, free) on all records
        2. If confidence is ambiguous (0.40-0.85), escalate to LLM

        Args:
            records: List of MASTRecord to process
            modes: Failure modes to process (default: F6, F8, F9, F13)
            llm_escalation: Whether to escalate ambiguous cases to LLM

        Returns:
            List of DetectionAttempt for all processed modes
        """
        if modes is None:
            modes = list(LLM_SEMANTIC_MODES)

        # Filter to only requested modes that are in our target list
        modes = [m for m in modes if m in self.failure_modes]
        if not modes:
            return []

        # Import turn-aware detectors
        try:
            from app.detection.turn_aware.derailment import TurnAwareDerailmentDetector
            from app.detection.turn_aware.withholding import TurnAwareInformationWithholdingDetector
            from app.detection.turn_aware.role_usurpation import TurnAwareRoleUsurpationDetector
            from app.detection.turn_aware.quality_gate import TurnAwareQualityGateBypassDetector
        except ImportError as e:
            logger.error(f"Turn-aware detectors not available: {e}")
            return []

        # Initialize detectors
        TURN_AWARE_DETECTORS = {
            "F6": TurnAwareDerailmentDetector(),
            "F8": TurnAwareInformationWithholdingDetector(),
            "F9": TurnAwareRoleUsurpationDetector(),
            "F13": TurnAwareQualityGateBypassDetector(),
        }

        HIGH_THRESHOLD = 0.85  # Accept directly
        LOW_THRESHOLD = 0.40   # Reject directly

        attempts = []
        llm_queue = []  # Queue for LLM escalation

        for record in records:
            # Parse trajectory into turn snapshots
            turns = self._parse_to_turn_snapshots(record)
            if not turns:
                logger.warning(f"No turns parsed for {record.trace_id}")
                continue

            metadata = {
                "task_description": record.task,
                "framework": record.framework,
                "trace_id": record.trace_id,
            }

            for mode in modes:
                if mode not in record.ground_truth:
                    continue

                detector = TURN_AWARE_DETECTORS.get(mode)
                if not detector:
                    continue

                # Phase 1: Turn-aware detection (fast, free)
                start = time.time()
                try:
                    result = detector.detect(turns=turns, conversation_metadata=metadata)
                    latency = (time.time() - start) * 1000

                    # Confidence routing
                    if result.confidence >= HIGH_THRESHOLD:
                        # High confidence - accept directly
                        attempts.append(DetectionAttempt(
                            record_id=record.trace_id,
                            failure_mode=mode,
                            detector_name="hybrid_turn_aware_accept",
                            detected=result.detected,
                            confidence=result.confidence,
                            latency_ms=latency,
                        ))
                    elif result.confidence < LOW_THRESHOLD:
                        # Low confidence - reject directly
                        attempts.append(DetectionAttempt(
                            record_id=record.trace_id,
                            failure_mode=mode,
                            detector_name="hybrid_turn_aware_reject",
                            detected=False,
                            confidence=1.0 - result.confidence,
                            latency_ms=latency,
                        ))
                    else:
                        # Ambiguous (0.40-0.85) - queue for LLM
                        if llm_escalation and self._api_key:
                            llm_queue.append((record, mode, result, latency))
                        else:
                            # No LLM available, use turn-aware result
                            attempts.append(DetectionAttempt(
                                record_id=record.trace_id,
                                failure_mode=mode,
                                detector_name="hybrid_turn_aware_ambiguous",
                                detected=result.detected,
                                confidence=result.confidence,
                                latency_ms=latency,
                            ))

                except Exception as e:
                    latency = (time.time() - start) * 1000
                    logger.warning(f"Turn-aware detection failed for {record.trace_id}/{mode}: {e}")
                    attempts.append(DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name="hybrid_error",
                        detected=False,
                        confidence=0.0,
                        latency_ms=latency,
                        error=str(e),
                    ))

        # Phase 2: LLM escalation for ambiguous cases
        if llm_queue and self._api_key:
            logger.info(f"Escalating {len(llm_queue)} ambiguous cases to LLM...")
            try:
                llm_results = self._run_llm_escalation(llm_queue)
                attempts.extend(llm_results)
            except Exception as e:
                logger.error(f"LLM escalation failed: {e}")
                # Fall back to turn-aware results for ambiguous cases
                for record, mode, result, latency in llm_queue:
                    attempts.append(DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name="hybrid_escalation_failed",
                        detected=result.detected,
                        confidence=result.confidence,
                        latency_ms=latency,
                        error=str(e),
                    ))

        return attempts

    def _run_llm_escalation(
        self,
        queue: List[Tuple[MASTRecord, str, Any, float]],
    ) -> List[DetectionAttempt]:
        """Run LLM detection for ambiguous cases from hybrid pipeline.

        Args:
            queue: List of (record, mode, turn_aware_result, pattern_latency)

        Returns:
            List of DetectionAttempt with LLM verification
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._run_llm_escalation_async(queue))

    async def _run_llm_escalation_async(
        self,
        queue: List[Tuple[MASTRecord, str, Any, float]],
        max_concurrent: int = 5,  # Concurrent requests per key
    ) -> List[DetectionAttempt]:
        """Async LLM escalation for ambiguous cases with parallel processing.

        Uses round-robin across multiple API keys for 4x throughput.

        Args:
            queue: List of (record, mode, turn_aware_result, pattern_latency)
            max_concurrent: Maximum concurrent API requests per key

        Returns:
            List of DetectionAttempt with LLM verification
        """
        from anthropic import AsyncAnthropic

        if not self._api_keys:
            return []

        # Create multiple clients for round-robin (one per API key)
        clients = [AsyncAnthropic(api_key=key) for key in self._api_keys]
        num_clients = len(clients)
        model_id = "claude-3-5-haiku-20241022"  # Use Haiku for cost efficiency

        # Total concurrent = max_concurrent * num_keys
        total_concurrent = max_concurrent * num_clients
        semaphore = asyncio.Semaphore(total_concurrent)
        logger.info(f"Using {num_clients} API keys with {total_concurrent} total concurrent requests")

        # Get few-shot examples
        few_shot_examples = {}
        try:
            from app.benchmark.few_shot_bank import MAST_FEW_SHOT_EXAMPLES
            few_shot_examples = MAST_FEW_SHOT_EXAMPLES
        except ImportError:
            pass

        async def process_one(item: Tuple[MASTRecord, str, Any, float], idx: int) -> DetectionAttempt:
            """Process a single LLM escalation request with round-robin client."""
            record, mode, turn_aware_result, pattern_latency = item
            # Round-robin client selection based on index
            client = clients[idx % num_clients]
            async with semaphore:
                start_time = time.time()
                try:
                    prompt = self._build_llm_prompt(
                        record, mode, few_shot_examples.get(mode, {})
                    )
                    response = await client.messages.create(
                        model=model_id,
                        max_tokens=1000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    content = response.content[0].text
                    detected, confidence, reasoning = self._parse_llm_response(content)
                    latency = (time.time() - start_time) * 1000

                    # Combine turn-aware pattern latency with LLM latency
                    total_latency = pattern_latency + latency

                    # Confidence boost if LLM confirms, penalty if rejects
                    if detected == turn_aware_result.detected:
                        final_confidence = min(0.95, confidence + 0.1)
                    else:
                        final_confidence = confidence  # Trust LLM verdict

                    return DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name="hybrid_llm_verified",
                        detected=detected,
                        confidence=final_confidence,
                        latency_ms=total_latency,
                        raw_result={"llm_reasoning": reasoning[:300]},
                    )

                except Exception as e:
                    latency = (time.time() - start_time) * 1000
                    logger.warning(f"LLM escalation failed for {record.trace_id}/{mode}: {e}")
                    # Fall back to turn-aware result
                    return DetectionAttempt(
                        record_id=record.trace_id,
                        failure_mode=mode,
                        detector_name="hybrid_llm_fallback",
                        detected=turn_aware_result.detected,
                        confidence=turn_aware_result.confidence,
                        latency_ms=pattern_latency + latency,
                        error=str(e),
                    )

        logger.info(f"Escalating {len(queue)} cases to LLM (max {total_concurrent} concurrent)...")
        results = await asyncio.gather(*[process_one(item, idx) for idx, item in enumerate(queue)])
        return list(results)

    def _parse_to_turn_snapshots(self, record: MASTRecord) -> List:
        """Convert MAST trajectory to TurnSnapshot list.

        Args:
            record: MASTRecord with trajectory

        Returns:
            List of TurnSnapshot for turn-aware detection
        """
        try:
            from app.benchmark.trajectory_parser import parse_trajectory_to_turns
            from app.detection.turn_aware._base import TurnSnapshot
        except ImportError as e:
            logger.error(f"Failed to import turn-aware modules: {e}")
            return []

        # Use existing parser to extract turns
        parsed_turns = parse_trajectory_to_turns(record.trajectory, record.framework)
        if not parsed_turns:
            return []

        snapshots = []
        accumulated = ""
        for i, turn in enumerate(parsed_turns):
            accumulated += f"\n{turn.participant_id}: {turn.content}"
            snapshots.append(TurnSnapshot(
                turn_number=i,
                participant_type=turn.participant_type or "agent",
                participant_id=turn.participant_id,
                content=turn.content,
                accumulated_context=accumulated[:50000],  # Limit context size
                accumulated_tokens=len(accumulated.split()),
            ))

        return snapshots

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
