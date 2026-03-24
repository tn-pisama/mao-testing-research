"""Tests for shadow evaluation drift detection."""
import pytest
from datetime import datetime, timezone
from app.detection_enterprise.shadow_eval import (
    ShadowEvalResult,
    DriftReport,
    pick_shadow_sample,
    run_shadow_eval,
    compute_drift_report,
)


class TestPickShadowSample:
    def test_returns_entry_from_golden_data(self):
        golden = [
            {"id": "test_1", "detection_type": "loop", "expected_detected": True,
             "expected_confidence_min": 0.3, "expected_confidence_max": 1.0,
             "human_verified": True},
            {"id": "test_2", "detection_type": "hallucination", "expected_detected": False,
             "expected_confidence_min": 0.0, "expected_confidence_max": 0.3,
             "human_verified": False},
        ]
        sample = pick_shadow_sample(golden)
        assert sample is not None
        assert sample["id"] in ("test_1", "test_2")

    def test_prefers_human_verified(self):
        golden = [
            {"id": "verified", "detection_type": "loop", "expected_detected": True,
             "human_verified": True},
            {"id": "unverified", "detection_type": "loop", "expected_detected": False,
             "human_verified": False},
        ]
        # Run multiple times — verified should be picked more often
        picks = [pick_shadow_sample(golden)["id"] for _ in range(20)]
        assert picks.count("verified") > picks.count("unverified")

    def test_empty_golden_returns_none(self):
        assert pick_shadow_sample([]) is None


class TestRunShadowEval:
    def test_correct_detection_matches(self):
        entry = {
            "id": "test_1",
            "detection_type": "loop",
            "input_data": {"states": [{"content": "hello"}, {"content": "hello"}]},
            "expected_detected": True,
            "expected_confidence_min": 0.0,
            "expected_confidence_max": 1.0,
        }
        # Mock runner that always detects
        def mock_runner(input_data):
            return True, 0.8

        result = run_shadow_eval(entry, mock_runner)
        assert isinstance(result, ShadowEvalResult)
        assert result.match is True
        assert result.actual_detected is True

    def test_incorrect_detection_mismatches(self):
        entry = {
            "id": "test_2",
            "detection_type": "hallucination",
            "input_data": {"output": "test"},
            "expected_detected": False,
            "expected_confidence_min": 0.0,
            "expected_confidence_max": 0.3,
        }
        # Mock runner that falsely detects
        def mock_runner(input_data):
            return True, 0.9

        result = run_shadow_eval(entry, mock_runner)
        assert result.match is False

    def test_runner_error_records_error(self):
        entry = {
            "id": "test_3",
            "detection_type": "loop",
            "input_data": {},
            "expected_detected": True,
        }
        def failing_runner(input_data):
            raise ValueError("test error")

        result = run_shadow_eval(entry, failing_runner)
        assert result.match is False
        assert result.error is not None


class TestComputeDriftReport:
    def test_all_passing_no_drift(self):
        results = [
            ShadowEvalResult(
                detector_type="loop",
                golden_entry_id=f"entry_{i}",
                expected_detected=True,
                actual_detected=True,
                expected_confidence_min=0.3,
                expected_confidence_max=1.0,
                actual_confidence=0.8,
                match=True,
            )
            for i in range(10)
        ]
        report = compute_drift_report(results)
        assert isinstance(report, DriftReport)
        assert not report.drifted
        assert report.accuracy == 1.0

    def test_drift_detected_below_threshold(self):
        # 4 correct + 6 wrong = 40% accuracy (below production threshold 70%)
        results = [
            ShadowEvalResult(
                detector_type="loop",
                golden_entry_id=f"entry_{i}",
                expected_detected=True,
                actual_detected=i < 4,
                expected_confidence_min=0.3,
                expected_confidence_max=1.0,
                actual_confidence=0.5,
                match=i < 4,
            )
            for i in range(10)
        ]
        report = compute_drift_report(results, detector_tier="production")
        assert report.drifted
        assert report.accuracy < 0.70

    def test_empty_results_no_drift(self):
        report = compute_drift_report([])
        assert not report.drifted
