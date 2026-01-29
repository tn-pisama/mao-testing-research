"""
OTEL Golden Trace Test Harness
================================

Test harness for running PISAMA detectors against OTEL execution traces
with full runtime data (actual LLM outputs, state transitions, etc.)

Unlike the n8n harness (static workflow definitions), this tests with
REAL execution data.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime

from app.detection.validation import (
    DetectionType, LabeledSample, DetectionPrediction,
    DetectionValidator, ValidationMetrics
)
from app.detection.loop import MultiLevelLoopDetector
from app.detection.coordination import CoordinationAnalyzer
from app.detection.corruption import SemanticCorruptionDetector
from app.detection.persona import PersonaConsistencyScorer
from app.detection.golden_adapters_otel import get_otel_adapter


@dataclass
class OTELHarnessConfig:
    """Configuration for the OTEL test harness."""
    traces_path: Path
    output_dir: Path
    detectors: List[str] = field(default_factory=lambda: [
        "infinite_loop", "coordination_deadlock", "state_corruption", "persona_drift"
    ])
    sample_limit: Optional[int] = None
    save_misclassified: bool = True
    confidence_threshold: float = 0.5


@dataclass
class OTELDetectorTestResult:
    """Result for a single detector's test run."""
    detector_type: str
    samples_tested: int
    samples_skipped: int
    metrics: Dict[str, Any]
    optimal_threshold: float
    optimal_f1: float
    misclassified: List[Dict[str, Any]]
    calibration_error: float
    execution_time_seconds: float


class OTELGoldenTraceTestHarness:
    """Test harness for running detectors against OTEL golden traces."""

    def __init__(self, config: OTELHarnessConfig):
        self.config = config
        self.traces = self._load_traces()
        self.detectors = self._init_detectors()

    def _load_traces(self) -> List[Dict[str, Any]]:
        """Load OTEL traces from JSONL file."""
        traces = []
        with open(self.config.traces_path, 'r') as f:
            for line in f:
                traces.append(json.loads(line))
        return traces

    def _init_detectors(self) -> Dict[str, Callable]:
        """Initialize detector instances and their run methods."""
        return {
            "infinite_loop": self._run_loop_detection,
            "coordination_deadlock": self._run_coordination_detection,
            "state_corruption": self._run_corruption_detection,
            "persona_drift": self._run_persona_detection,
        }

    def run_all(self) -> Dict[str, OTELDetectorTestResult]:
        """Run all configured detectors against OTEL traces."""
        results = {}

        print(f"\n{'='*70}")
        print(f"OTEL Golden Trace Test Harness")
        print(f"{'='*70}")
        print(f"Traces file: {self.config.traces_path}")
        print(f"Total traces: {len(self.traces)}")
        print(f"Detectors to test: {', '.join(self.config.detectors)}")
        print(f"{'='*70}\n")

        for detector_type in self.config.detectors:
            print(f"\n{'='*70}")
            print(f"Testing {detector_type.upper()} detector...")
            print(f"{'='*70}")

            try:
                result = self.run_detector(detector_type)
                results[detector_type] = result

                # Print summary
                print(f"\nResults for {detector_type}:")
                print(f"  Samples tested: {result.samples_tested}")
                print(f"  Samples skipped: {result.samples_skipped}")
                print(f"  F1 Score:      {result.metrics.get('f1_score', 0):.4f}")
                print(f"  Precision:     {result.metrics.get('precision', 0):.4f}")
                print(f"  Recall:        {result.metrics.get('recall', 0):.4f}")
                print(f"  Accuracy:      {result.metrics.get('accuracy', 0):.4f}")
                print(f"  Optimal Threshold: {result.optimal_threshold:.2f} (F1={result.optimal_f1:.4f})")
                print(f"  Execution time: {result.execution_time_seconds:.2f}s")

            except Exception as e:
                print(f"ERROR testing {detector_type}: {e}")
                import traceback
                traceback.print_exc()

        return results

    def run_detector(self, detector_type: str) -> OTELDetectorTestResult:
        """Run a specific detector against OTEL traces."""
        start_time = time.time()

        # Filter traces by detection type
        matching_traces = []
        for trace in self.traces:
            metadata = trace.get('_golden_metadata', {})
            trace_dtype = metadata.get('detection_type')

            # Map trace detection types to detector types
            type_map = {
                'infinite_loop': 'infinite_loop',
                'state_corruption': 'state_corruption',
                'persona_drift': 'persona_drift',
                'coordination_deadlock': 'coordination_deadlock',
            }

            if trace_dtype == detector_type or (trace_dtype in type_map and type_map[trace_dtype] == detector_type):
                matching_traces.append(trace)
            elif metadata.get('expected_detection') == False and detector_type == 'infinite_loop':
                # Include healthy traces as negatives
                matching_traces.append(trace)

        print(f"Found {len(matching_traces)} traces for {detector_type}")

        if self.config.sample_limit:
            matching_traces = matching_traces[:self.config.sample_limit]
            print(f"Limited to {len(matching_traces)} traces")

        # Get adapter and detector
        adapter = get_otel_adapter(detector_type)
        detector_fn = self.detectors.get(detector_type)

        if not adapter:
            raise ValueError(f"No OTEL adapter found for detector type: {detector_type}")
        if not detector_fn:
            raise ValueError(f"No detector function found for type: {detector_type}")

        # Create validator for this detector
        # Map OTEL detection types to DetectionType enum
        detection_type_map = {
            'infinite_loop': DetectionType.LOOP,
            'coordination_deadlock': DetectionType.COORDINATION,
            'state_corruption': DetectionType.CORRUPTION,
            'persona_drift': DetectionType.PERSONA_DRIFT,
        }
        detection_type = detection_type_map.get(detector_type, DetectionType.LOOP)

        validator = DetectionValidator()
        samples_skipped = 0

        # Process each trace
        for i, trace in enumerate(matching_traces):
            if (i + 1) % 20 == 0:
                print(f"  Processed {i + 1}/{len(matching_traces)} traces...")

            # Get ground truth
            metadata = trace.get('_golden_metadata', {})
            expected_detected = metadata.get('expected_detection', True)

            # Generate sample ID
            trace_id = None
            for rs in trace.get('resourceSpans', []):
                for ss in rs.get('scopeSpans', []):
                    for span in ss.get('spans', []):
                        trace_id = span.get('traceId')
                        break
                    if trace_id:
                        break
                if trace_id:
                    break

            sample_id = trace_id or f"trace_{i}"

            # Add ground truth sample
            labeled = LabeledSample(
                sample_id=sample_id,
                detection_type=detection_type,
                input_data={},  # OTEL trace data (not needed for validation)
                ground_truth=expected_detected,
                ground_truth_confidence=1.0,
            )
            validator.add_labeled_sample(labeled)

            # Convert to detector input
            adapted = adapter.adapt(trace)

            if not adapted.success:
                samples_skipped += 1
                continue

            # Run detection
            try:
                result = detector_fn(adapted.detector_input)

                # Create prediction
                prediction = DetectionPrediction(
                    sample_id=sample_id,
                    detected=result.detected,
                    confidence=result.confidence,
                    detection_type=detection_type,
                    raw_score=getattr(result, 'raw_score', None),
                )
                validator.add_prediction(prediction)

            except Exception as e:
                print(f"  Error running detector on trace {sample_id}: {e}")
                samples_skipped += 1

        # Calculate metrics
        metrics = validator.validate(detection_type)

        # Find optimal threshold
        try:
            optimal_threshold, optimal_f1 = validator.find_optimal_threshold(detection_type)
        except Exception:
            optimal_threshold = 0.5
            optimal_f1 = metrics.f1_score

        # Compute calibration error
        try:
            ece = validator.compute_ece(detection_type=detection_type)
        except Exception:
            ece = 0.0

        # Get misclassified samples
        misclassified = []
        if self.config.save_misclassified:
            try:
                misclassified_dict = validator.get_misclassified(detection_type)
                misclassified = list(misclassified_dict.values())[:100]
            except Exception as e:
                print(f"  Warning: Could not get misclassified samples: {e}")

        # Convert metrics to dict
        metrics_dict = {
            "true_positives": metrics.true_positives,
            "true_negatives": metrics.true_negatives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
            "total_samples": metrics.total_samples,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "accuracy": metrics.accuracy,
            "specificity": metrics.specificity,
        }

        return OTELDetectorTestResult(
            detector_type=detector_type,
            samples_tested=metrics.total_samples,
            samples_skipped=samples_skipped,
            metrics=metrics_dict,
            optimal_threshold=optimal_threshold,
            optimal_f1=optimal_f1,
            misclassified=misclassified,
            calibration_error=ece,
            execution_time_seconds=time.time() - start_time,
        )

    def _run_loop_detection(self, detector_input: List) -> Any:
        """Run loop detector."""
        detector = MultiLevelLoopDetector()
        return detector.detect_loop_enhanced(detector_input)

    def _run_coordination_detection(self, detector_input: Dict) -> Any:
        """Run coordination detector."""
        analyzer = CoordinationAnalyzer()
        return analyzer.analyze_coordination_with_confidence(
            messages=detector_input["messages"],
            agent_ids=detector_input["agent_ids"],
        )

    def _run_corruption_detection(self, detector_input: Dict) -> Any:
        """Run corruption detector using text-based semantic detection."""
        detector = SemanticCorruptionDetector()
        return detector.detect_from_text(
            task=detector_input["task"],
            output=detector_input["output"],
            context=detector_input.get("context"),
        )

    def _run_persona_detection(self, detector_input: Dict) -> Any:
        """Run persona drift detector."""
        scorer = PersonaConsistencyScorer()
        result = scorer.score_consistency(
            agent=detector_input["agent"],
            output=detector_input["output"],
        )

        # Persona detector returns "consistent", but we want "drift detected"
        # Invert the detection logic
        return type('Result', (), {
            'detected': not result.consistent,  # Invert
            'confidence': result.confidence if not result.consistent else (1.0 - result.confidence),
            'raw_score': result.raw_score,
        })()

    def generate_report(self, results: Dict[str, OTELDetectorTestResult]) -> Dict:
        """Generate comprehensive test report."""
        report = {
            "run_timestamp": datetime.utcnow().isoformat(),
            "traces_path": str(self.config.traces_path),
            "total_traces": len(self.traces),
            "detectors_tested": list(results.keys()),
            "summary": {},
            "details": {},
        }

        for detector_type, result in results.items():
            report["summary"][detector_type] = {
                "f1_score": result.metrics.get("f1_score", 0),
                "precision": result.metrics.get("precision", 0),
                "recall": result.metrics.get("recall", 0),
                "accuracy": result.metrics.get("accuracy", 0),
                "samples_tested": result.samples_tested,
                "optimal_threshold": result.optimal_threshold,
            }

            report["details"][detector_type] = {
                "metrics": result.metrics,
                "calibration_error": result.calibration_error,
                "execution_time": result.execution_time_seconds,
                "samples_skipped": result.samples_skipped,
                "misclassified_count": len(result.misclassified),
                "misclassified_samples": result.misclassified[:10],
            }

        return report
