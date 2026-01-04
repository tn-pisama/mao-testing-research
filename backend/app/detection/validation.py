"""Detection validation framework for accuracy measurement and calibration."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import numpy as np
from datetime import datetime, timezone


class DetectionType(Enum):
    LOOP = "loop"
    CORRUPTION = "corruption"
    PERSONA_DRIFT = "persona_drift"
    HALLUCINATION = "hallucination"
    DERAILMENT = "derailment"
    OVERFLOW = "overflow"
    COORDINATION = "coordination"
    INJECTION = "injection"
    COMMUNICATION = "communication"
    CONTEXT = "context"
    DECOMPOSITION = "decomposition"
    WORKFLOW = "workflow"
    GROUNDING = "grounding"  # F15: OfficeQA-inspired
    RETRIEVAL_QUALITY = "retrieval_quality"  # F16: OfficeQA-inspired


@dataclass
class LabeledSample:
    """A sample with ground truth label for validation."""
    sample_id: str
    detection_type: DetectionType
    input_data: Dict[str, Any]
    ground_truth: bool
    ground_truth_confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionPrediction:
    """A detection result to be validated."""
    sample_id: str
    detected: bool
    confidence: float
    detection_type: DetectionType
    raw_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationMetrics:
    """Metrics for detection validation."""
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    total_samples: int = 0
    
    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)
    
    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)
    
    @property
    def f1_score(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)
    
    @property
    def accuracy(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / self.total_samples
    
    @property
    def specificity(self) -> float:
        if self.true_negatives + self.false_positives == 0:
            return 0.0
        return self.true_negatives / (self.true_negatives + self.false_positives)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "total_samples": self.total_samples,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "accuracy": round(self.accuracy, 4),
            "specificity": round(self.specificity, 4),
        }


@dataclass
class CalibrationResult:
    """Result of confidence calibration analysis."""
    expected_confidence: float
    actual_accuracy: float
    sample_count: int
    calibration_error: float
    
    @property
    def is_overconfident(self) -> bool:
        return self.expected_confidence > self.actual_accuracy
    
    @property
    def is_underconfident(self) -> bool:
        return self.expected_confidence < self.actual_accuracy


class DetectionValidator:
    """Validates detection results against ground truth."""
    
    def __init__(self):
        self.samples: Dict[str, LabeledSample] = {}
        self.predictions: Dict[str, DetectionPrediction] = {}
        self._metrics_cache: Dict[DetectionType, ValidationMetrics] = {}
    
    def add_labeled_sample(self, sample: LabeledSample) -> None:
        self.samples[sample.sample_id] = sample
        self._metrics_cache.clear()
    
    def add_prediction(self, prediction: DetectionPrediction) -> None:
        self.predictions[prediction.sample_id] = prediction
        self._metrics_cache.clear()
    
    def validate(
        self,
        detection_type: Optional[DetectionType] = None,
    ) -> ValidationMetrics:
        """Compute validation metrics for predictions."""
        metrics = ValidationMetrics()
        
        for sample_id, sample in self.samples.items():
            if detection_type and sample.detection_type != detection_type:
                continue
            
            if sample_id not in self.predictions:
                continue
            
            prediction = self.predictions[sample_id]
            ground_truth = sample.ground_truth
            predicted = prediction.detected
            
            metrics.total_samples += 1
            
            if ground_truth and predicted:
                metrics.true_positives += 1
            elif not ground_truth and not predicted:
                metrics.true_negatives += 1
            elif not ground_truth and predicted:
                metrics.false_positives += 1
            else:
                metrics.false_negatives += 1
        
        return metrics
    
    def validate_by_type(self) -> Dict[DetectionType, ValidationMetrics]:
        """Compute metrics for each detection type."""
        results = {}
        for detection_type in DetectionType:
            metrics = self.validate(detection_type)
            if metrics.total_samples > 0:
                results[detection_type] = metrics
        return results
    
    def compute_calibration(
        self,
        num_bins: int = 10,
        detection_type: Optional[DetectionType] = None,
    ) -> List[CalibrationResult]:
        """Compute confidence calibration across bins."""
        predictions_with_truth = []
        
        for sample_id, sample in self.samples.items():
            if detection_type and sample.detection_type != detection_type:
                continue
            if sample_id not in self.predictions:
                continue
            
            pred = self.predictions[sample_id]
            predictions_with_truth.append({
                "confidence": pred.confidence,
                "correct": pred.detected == sample.ground_truth,
            })
        
        if not predictions_with_truth:
            return []
        
        bin_edges = np.linspace(0, 1, num_bins + 1)
        results = []
        
        for i in range(num_bins):
            low, high = bin_edges[i], bin_edges[i + 1]
            bin_preds = [
                p for p in predictions_with_truth
                if low <= p["confidence"] < high or (i == num_bins - 1 and p["confidence"] == high)
            ]
            
            if not bin_preds:
                continue
            
            expected = (low + high) / 2
            actual = sum(p["correct"] for p in bin_preds) / len(bin_preds)
            error = abs(expected - actual)
            
            results.append(CalibrationResult(
                expected_confidence=expected,
                actual_accuracy=actual,
                sample_count=len(bin_preds),
                calibration_error=error,
            ))
        
        return results
    
    def compute_ece(
        self,
        num_bins: int = 10,
        detection_type: Optional[DetectionType] = None,
    ) -> float:
        """Compute Expected Calibration Error."""
        calibration = self.compute_calibration(num_bins, detection_type)
        if not calibration:
            return 0.0
        
        total_samples = sum(c.sample_count for c in calibration)
        if total_samples == 0:
            return 0.0
        
        ece = sum(
            c.sample_count * c.calibration_error
            for c in calibration
        ) / total_samples
        
        return ece
    
    def find_optimal_threshold(
        self,
        detection_type: Optional[DetectionType] = None,
        metric: str = "f1",
        thresholds: Optional[List[float]] = None,
    ) -> Tuple[float, float]:
        """Find optimal confidence threshold for a given metric."""
        if thresholds is None:
            thresholds = [i / 20 for i in range(1, 20)]
        
        best_threshold = 0.5
        best_score = 0.0
        
        for threshold in thresholds:
            temp_predictions = {}
            for sample_id, pred in self.predictions.items():
                if detection_type:
                    sample = self.samples.get(sample_id)
                    if sample and sample.detection_type != detection_type:
                        continue
                
                temp_predictions[sample_id] = DetectionPrediction(
                    sample_id=pred.sample_id,
                    detected=pred.confidence >= threshold,
                    confidence=pred.confidence,
                    detection_type=pred.detection_type,
                    raw_score=pred.raw_score,
                )
            
            original_predictions = self.predictions
            self.predictions = temp_predictions
            metrics = self.validate(detection_type)
            self.predictions = original_predictions
            
            score = getattr(metrics, metric if metric != "f1" else "f1_score", 0.0)
            if score > best_score:
                best_score = score
                best_threshold = threshold
        
        return best_threshold, best_score
    
    def get_misclassified(
        self,
        detection_type: Optional[DetectionType] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Get all misclassified samples for analysis."""
        misclassified = {}
        
        for sample_id, sample in self.samples.items():
            if detection_type and sample.detection_type != detection_type:
                continue
            if sample_id not in self.predictions:
                continue
            
            pred = self.predictions[sample_id]
            if pred.detected != sample.ground_truth:
                misclassified[sample_id] = {
                    "ground_truth": sample.ground_truth,
                    "predicted": pred.detected,
                    "confidence": pred.confidence,
                    "type": "false_positive" if pred.detected else "false_negative",
                    "input_data": sample.input_data,
                    "metadata": {**sample.metadata, **pred.metadata},
                }
        
        return misclassified
    
    def summary(self) -> Dict[str, Any]:
        """Generate a summary of validation results."""
        metrics_by_type = self.validate_by_type()
        overall_metrics = self.validate()
        
        return {
            "overall": overall_metrics.to_dict(),
            "by_type": {
                dt.value: m.to_dict()
                for dt, m in metrics_by_type.items()
            },
            "expected_calibration_error": round(self.compute_ece(), 4),
            "total_samples": len(self.samples),
            "total_predictions": len(self.predictions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def create_validation_report(
    validator: DetectionValidator,
    include_misclassified: bool = True,
) -> Dict[str, Any]:
    """Create a comprehensive validation report."""
    report = validator.summary()
    
    optimal_thresholds = {}
    for detection_type in DetectionType:
        threshold, score = validator.find_optimal_threshold(detection_type)
        if score > 0:
            optimal_thresholds[detection_type.value] = {
                "threshold": threshold,
                "f1_score": round(score, 4),
            }
    
    report["optimal_thresholds"] = optimal_thresholds
    
    if include_misclassified:
        misclassified = validator.get_misclassified()
        report["misclassified_count"] = len(misclassified)
        report["misclassified_samples"] = list(misclassified.keys())[:10]
    
    return report
