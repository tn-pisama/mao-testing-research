"""Unit tests for detection validation framework."""

import pytest
from app.detection.validation import (
    DetectionValidator,
    LabeledSample,
    DetectionPrediction,
    DetectionType,
    ValidationMetrics,
    CalibrationResult,
    create_validation_report,
)


class TestValidationMetrics:
    def test_precision_all_correct(self):
        metrics = ValidationMetrics(
            true_positives=10,
            true_negatives=10,
            false_positives=0,
            false_negatives=0,
            total_samples=20,
        )
        assert metrics.precision == 1.0
    
    def test_precision_some_false_positives(self):
        metrics = ValidationMetrics(
            true_positives=8,
            true_negatives=10,
            false_positives=2,
            false_negatives=0,
            total_samples=20,
        )
        assert metrics.precision == 0.8
    
    def test_recall_all_detected(self):
        metrics = ValidationMetrics(
            true_positives=10,
            true_negatives=10,
            false_positives=0,
            false_negatives=0,
            total_samples=20,
        )
        assert metrics.recall == 1.0
    
    def test_recall_some_missed(self):
        metrics = ValidationMetrics(
            true_positives=7,
            true_negatives=10,
            false_positives=0,
            false_negatives=3,
            total_samples=20,
        )
        assert metrics.recall == 0.7
    
    def test_f1_score(self):
        metrics = ValidationMetrics(
            true_positives=8,
            true_negatives=8,
            false_positives=2,
            false_negatives=2,
            total_samples=20,
        )
        expected_precision = 8 / 10
        expected_recall = 8 / 10
        expected_f1 = 2 * (expected_precision * expected_recall) / (expected_precision + expected_recall)
        assert abs(metrics.f1_score - expected_f1) < 1e-6
    
    def test_accuracy(self):
        metrics = ValidationMetrics(
            true_positives=8,
            true_negatives=8,
            false_positives=2,
            false_negatives=2,
            total_samples=20,
        )
        assert metrics.accuracy == 0.8
    
    def test_specificity(self):
        metrics = ValidationMetrics(
            true_positives=8,
            true_negatives=9,
            false_positives=1,
            false_negatives=2,
            total_samples=20,
        )
        assert metrics.specificity == 0.9
    
    def test_to_dict(self):
        metrics = ValidationMetrics(
            true_positives=5,
            true_negatives=5,
            false_positives=0,
            false_negatives=0,
            total_samples=10,
        )
        d = metrics.to_dict()
        assert d["precision"] == 1.0
        assert d["recall"] == 1.0
        assert d["f1_score"] == 1.0
        assert d["accuracy"] == 1.0


class TestDetectionValidator:
    def setup_method(self):
        self.validator = DetectionValidator()
    
    def test_add_sample_and_prediction(self):
        sample = LabeledSample(
            sample_id="test1",
            detection_type=DetectionType.LOOP,
            input_data={"states": []},
            ground_truth=True,
        )
        prediction = DetectionPrediction(
            sample_id="test1",
            detected=True,
            confidence=0.9,
            detection_type=DetectionType.LOOP,
        )
        
        self.validator.add_labeled_sample(sample)
        self.validator.add_prediction(prediction)
        
        assert len(self.validator.samples) == 1
        assert len(self.validator.predictions) == 1
    
    def test_validate_perfect_predictions(self):
        for i in range(10):
            gt = i < 5
            sample = LabeledSample(
                sample_id=f"test{i}",
                detection_type=DetectionType.LOOP,
                input_data={},
                ground_truth=gt,
            )
            prediction = DetectionPrediction(
                sample_id=f"test{i}",
                detected=gt,
                confidence=0.9 if gt else 0.1,
                detection_type=DetectionType.LOOP,
            )
            self.validator.add_labeled_sample(sample)
            self.validator.add_prediction(prediction)
        
        metrics = self.validator.validate()
        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
    
    def test_validate_with_errors(self):
        samples_data = [
            (True, True),
            (True, True),
            (True, False),
            (False, False),
            (False, True),
        ]
        
        for i, (gt, pred) in enumerate(samples_data):
            sample = LabeledSample(
                sample_id=f"test{i}",
                detection_type=DetectionType.PERSONA_DRIFT,
                input_data={},
                ground_truth=gt,
            )
            prediction = DetectionPrediction(
                sample_id=f"test{i}",
                detected=pred,
                confidence=0.8 if pred else 0.2,
                detection_type=DetectionType.PERSONA_DRIFT,
            )
            self.validator.add_labeled_sample(sample)
            self.validator.add_prediction(prediction)
        
        metrics = self.validator.validate()
        assert metrics.true_positives == 2
        assert metrics.true_negatives == 1
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 1
        assert metrics.accuracy == 0.6
    
    def test_validate_by_type(self):
        for i in range(5):
            sample = LabeledSample(
                sample_id=f"loop{i}",
                detection_type=DetectionType.LOOP,
                input_data={},
                ground_truth=True,
            )
            prediction = DetectionPrediction(
                sample_id=f"loop{i}",
                detected=True,
                confidence=0.9,
                detection_type=DetectionType.LOOP,
            )
            self.validator.add_labeled_sample(sample)
            self.validator.add_prediction(prediction)
        
        for i in range(3):
            sample = LabeledSample(
                sample_id=f"persona{i}",
                detection_type=DetectionType.PERSONA_DRIFT,
                input_data={},
                ground_truth=True,
            )
            prediction = DetectionPrediction(
                sample_id=f"persona{i}",
                detected=False,
                confidence=0.3,
                detection_type=DetectionType.PERSONA_DRIFT,
            )
            self.validator.add_labeled_sample(sample)
            self.validator.add_prediction(prediction)
        
        by_type = self.validator.validate_by_type()
        
        assert DetectionType.LOOP in by_type
        assert by_type[DetectionType.LOOP].accuracy == 1.0
        
        assert DetectionType.PERSONA_DRIFT in by_type
        assert by_type[DetectionType.PERSONA_DRIFT].recall == 0.0
    
    def test_get_misclassified(self):
        sample_fp = LabeledSample(
            sample_id="fp1",
            detection_type=DetectionType.LOOP,
            input_data={"data": "test"},
            ground_truth=False,
        )
        pred_fp = DetectionPrediction(
            sample_id="fp1",
            detected=True,
            confidence=0.7,
            detection_type=DetectionType.LOOP,
        )
        
        sample_fn = LabeledSample(
            sample_id="fn1",
            detection_type=DetectionType.LOOP,
            input_data={"data": "test2"},
            ground_truth=True,
        )
        pred_fn = DetectionPrediction(
            sample_id="fn1",
            detected=False,
            confidence=0.3,
            detection_type=DetectionType.LOOP,
        )
        
        self.validator.add_labeled_sample(sample_fp)
        self.validator.add_prediction(pred_fp)
        self.validator.add_labeled_sample(sample_fn)
        self.validator.add_prediction(pred_fn)
        
        misclassified = self.validator.get_misclassified()
        
        assert len(misclassified) == 2
        assert "fp1" in misclassified
        assert misclassified["fp1"]["type"] == "false_positive"
        assert "fn1" in misclassified
        assert misclassified["fn1"]["type"] == "false_negative"
    
    def test_find_optimal_threshold(self):
        for i in range(20):
            gt = i < 10
            confidence = (i + 1) / 20
            
            sample = LabeledSample(
                sample_id=f"test{i}",
                detection_type=DetectionType.HALLUCINATION,
                input_data={},
                ground_truth=gt,
            )
            prediction = DetectionPrediction(
                sample_id=f"test{i}",
                detected=confidence >= 0.5,
                confidence=confidence,
                detection_type=DetectionType.HALLUCINATION,
            )
            self.validator.add_labeled_sample(sample)
            self.validator.add_prediction(prediction)
        
        threshold, score = self.validator.find_optimal_threshold(DetectionType.HALLUCINATION)
        assert 0 < threshold < 1
        assert score > 0


class TestCalibrationResult:
    def test_overconfident(self):
        result = CalibrationResult(
            expected_confidence=0.9,
            actual_accuracy=0.7,
            sample_count=100,
            calibration_error=0.2,
        )
        assert result.is_overconfident
        assert not result.is_underconfident
    
    def test_underconfident(self):
        result = CalibrationResult(
            expected_confidence=0.5,
            actual_accuracy=0.8,
            sample_count=100,
            calibration_error=0.3,
        )
        assert result.is_underconfident
        assert not result.is_overconfident


class TestValidationReport:
    def test_create_validation_report(self):
        validator = DetectionValidator()
        
        for i in range(10):
            gt = i < 5
            sample = LabeledSample(
                sample_id=f"test{i}",
                detection_type=DetectionType.LOOP,
                input_data={},
                ground_truth=gt,
            )
            prediction = DetectionPrediction(
                sample_id=f"test{i}",
                detected=gt,
                confidence=0.9 if gt else 0.1,
                detection_type=DetectionType.LOOP,
            )
            validator.add_labeled_sample(sample)
            validator.add_prediction(prediction)
        
        report = create_validation_report(validator)
        
        assert "overall" in report
        assert "by_type" in report
        assert "optimal_thresholds" in report
        assert report["total_samples"] == 10
        assert report["overall"]["accuracy"] == 1.0
