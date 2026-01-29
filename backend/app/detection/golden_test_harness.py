"""
Golden Dataset Test Harness
============================

Test harness for running PISAMA detectors against the golden dataset and
computing validation metrics (F1, precision, recall, accuracy).
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime

from app.detection.validation import (
    DetectionType, LabeledSample, DetectionPrediction,
    DetectionValidator, ValidationMetrics
)
from app.detection_enterprise.golden_dataset import GoldenDataset, GoldenDatasetEntry
from app.detection.loop import MultiLevelLoopDetector
from app.detection.coordination import CoordinationAnalyzer
from app.detection.corruption import SemanticCorruptionDetector
from app.detection.persona import PersonaConsistencyScorer
from app.detection.overflow import ContextOverflowDetector
from app.detection.golden_adapters import get_adapter


@dataclass
class HarnessConfig:
    """Configuration for the test harness."""
    dataset_path: Path
    output_dir: Path
    detectors: List[str] = field(default_factory=lambda: [
        "loop", "coordination", "corruption", "persona_drift", "overflow"
    ])
    sample_limit: Optional[int] = None
    save_misclassified: bool = True
    parallel_execution: bool = False
    confidence_threshold: float = 0.5


@dataclass
class DetectorTestResult:
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


class GoldenDatasetTestHarness:
    """Test harness for running detectors against golden dataset."""

    def __init__(self, config: HarnessConfig):
        self.config = config
        self.dataset = GoldenDataset(config.dataset_path)
        self.detectors = self._init_detectors()

    def _init_detectors(self) -> Dict[str, Callable]:
        """Initialize detector instances and their run methods."""
        return {
            "loop": self._run_loop_detection,
            "coordination": self._run_coordination_detection,
            "corruption": self._run_corruption_detection,
            "persona_drift": self._run_persona_detection,
            "overflow": self._run_overflow_detection,
        }

    def run_all(self) -> Dict[str, DetectorTestResult]:
        """Run all configured detectors against their samples."""
        results = {}

        print(f"\n{'='*70}")
        print(f"Golden Dataset Test Harness")
        print(f"{'='*70}")
        print(f"Dataset: {self.config.dataset_path}")
        print(f"Total samples: {len(self.dataset.entries)}")
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

    def run_detector(self, detector_type: str) -> DetectorTestResult:
        """Run a specific detector against its samples."""
        start_time = time.time()

        # Get samples for this detection type
        detection_type = DetectionType(detector_type)
        entries = self.dataset.get_entries_by_type(detection_type)

        print(f"Found {len(entries)} samples for {detector_type}")

        if self.config.sample_limit:
            entries = entries[:self.config.sample_limit]
            print(f"Limited to {len(entries)} samples")

        # Get adapter and detector
        adapter = get_adapter(detector_type)
        detector_fn = self.detectors.get(detector_type)

        if not adapter:
            raise ValueError(f"No adapter found for detector type: {detector_type}")
        if not detector_fn:
            raise ValueError(f"No detector function found for type: {detector_type}")

        # Create validator for this detector
        validator = DetectionValidator()
        samples_skipped = 0

        # Process each sample
        for i, entry in enumerate(entries):
            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(entries)} samples...")

            # Convert to detector input
            adapted = adapter.adapt(entry.input_data)

            if not adapted.success:
                samples_skipped += 1
                # print(f"  Skipped sample {entry.id}: {adapted.error}")
                continue

            # Add ground truth sample
            labeled = entry.to_labeled_sample()
            validator.add_labeled_sample(labeled)

            # Run detection
            try:
                result = detector_fn(adapted.detector_input)

                # Create prediction
                prediction = DetectionPrediction(
                    sample_id=entry.id,
                    detected=result.detected,
                    confidence=result.confidence,
                    detection_type=detection_type,
                    raw_score=getattr(result, 'raw_score', None),
                )
                validator.add_prediction(prediction)

            except Exception as e:
                print(f"  Error running detector on sample {entry.id}: {e}")
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
                # Limit to first 100 for memory
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

        return DetectorTestResult(
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

    def _run_overflow_detection(self, detector_input: Dict) -> Any:
        """Run overflow detector."""
        detector = ContextOverflowDetector()
        return detector.detect_overflow(
            current_tokens=detector_input["current_tokens"],
            model=detector_input["model"],
        )

    def generate_report(self, results: Dict[str, DetectorTestResult]) -> Dict:
        """Generate comprehensive test report."""
        report = {
            "run_timestamp": datetime.utcnow().isoformat(),
            "dataset_path": str(self.config.dataset_path),
            "total_samples": len(self.dataset.entries),
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
                "misclassified_samples": result.misclassified[:10],  # Top 10 for report
            }

        return report
