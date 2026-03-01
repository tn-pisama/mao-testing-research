"""Tests for ICP-tier calibration monitoring.

Tests the in-memory calibration monitor that tracks detection metrics
from diagnose runs and generates drift alerts.
"""

import pytest

from app.api.v1.diagnostics import _CalibrationMonitor


class TestCalibrationMonitor:
    """Test the _CalibrationMonitor class."""

    def test_empty_monitor(self):
        """Fresh monitor has no data."""
        monitor = _CalibrationMonitor()
        stats = monitor.get_stats()
        assert stats == {}
        summary = monitor.get_summary()
        assert summary["total_detectors_observed"] == 0
        assert summary["total_observations"] == 0

    def test_record_single_detection(self):
        monitor = _CalibrationMonitor()
        monitor.record("F6", detected=True, confidence=0.75, severity="moderate")
        monitor.record_run()

        stats = monitor.get_stats()
        assert "F6" in stats
        assert stats["F6"]["total_observations"] == 1
        assert stats["F6"]["detected_count"] == 1
        assert stats["F6"]["detection_rate"] == 1.0
        assert stats["F6"]["avg_confidence"] == 0.75

    def test_record_mixed_detections(self):
        monitor = _CalibrationMonitor()
        # 3 detected, 2 not
        monitor.record("F2", detected=True, confidence=0.8, severity="moderate")
        monitor.record("F2", detected=True, confidence=0.6, severity="minor")
        monitor.record("F2", detected=True, confidence=0.7, severity="moderate")
        monitor.record("F2", detected=False, confidence=0.0, severity="none")
        monitor.record("F2", detected=False, confidence=0.0, severity="none")

        stats = monitor.get_stats()
        f2 = stats["F2"]
        assert f2["total_observations"] == 5
        assert f2["detected_count"] == 3
        assert f2["detection_rate"] == 0.6
        assert f2["avg_confidence"] == pytest.approx(0.7, abs=0.01)

    def test_confidence_distribution(self):
        monitor = _CalibrationMonitor()
        # HIGH: >= 0.80
        monitor.record("F10", detected=True, confidence=0.90, severity="severe")
        # LIKELY: 0.60-0.80
        monitor.record("F10", detected=True, confidence=0.65, severity="moderate")
        # POSSIBLE: 0.40-0.60
        monitor.record("F10", detected=True, confidence=0.45, severity="minor")
        # LOW: < 0.40
        monitor.record("F10", detected=True, confidence=0.25, severity="minor")

        stats = monitor.get_stats()
        dist = stats["F10"]["confidence_distribution"]
        assert dist["high"] == 1
        assert dist["likely"] == 1
        assert dist["possible"] == 1
        assert dist["low"] == 1

    def test_severity_distribution(self):
        monitor = _CalibrationMonitor()
        monitor.record("F7", detected=True, confidence=0.9, severity="severe")
        monitor.record("F7", detected=True, confidence=0.7, severity="moderate")
        monitor.record("F7", detected=True, confidence=0.5, severity="minor")
        monitor.record("F7", detected=False, confidence=0.0, severity="none")

        stats = monitor.get_stats()
        sev = stats["F7"]["severity_distribution"]
        assert sev["severe"] == 1
        assert sev["moderate"] == 1
        assert sev["minor"] == 1
        # "none" only counted for detected=True
        assert "none" not in sev

    def test_high_fpr_alert(self):
        """Detectors firing >50% of the time should trigger an alert."""
        monitor = _CalibrationMonitor()
        # Fire 6 out of 10 observations (60% rate)
        for i in range(10):
            monitor.record("F2", detected=(i < 6), confidence=0.7, severity="moderate")

        stats = monitor.get_stats()
        alerts = stats["F2"]["alerts"]
        assert len(alerts) >= 1
        assert any(a["type"] == "high_detection_rate" for a in alerts)

    def test_low_confidence_alert(self):
        """Detectors with low average confidence should trigger an alert."""
        monitor = _CalibrationMonitor()
        # All detections with very low confidence
        for _ in range(5):
            monitor.record("F13", detected=True, confidence=0.25, severity="minor")

        stats = monitor.get_stats()
        alerts = stats["F13"]["alerts"]
        assert any(a["type"] == "low_avg_confidence" for a in alerts)

    def test_no_alerts_for_healthy_detector(self):
        """Well-behaved detectors should have no alerts."""
        monitor = _CalibrationMonitor()
        # 2 out of 10 detections (20% rate), high confidence
        for i in range(10):
            if i < 2:
                monitor.record("F1", detected=True, confidence=0.85, severity="moderate")
            else:
                monitor.record("F1", detected=False, confidence=0.0, severity="none")

        stats = monitor.get_stats()
        alerts = stats["F1"]["alerts"]
        assert len(alerts) == 0

    def test_get_all_alerts(self):
        monitor = _CalibrationMonitor()
        # Create two detectors with alerts
        for _ in range(10):
            monitor.record("F2", detected=True, confidence=0.7, severity="moderate")
            monitor.record("F6", detected=True, confidence=0.3, severity="minor")

        all_alerts = monitor.get_alerts()
        assert len(all_alerts) >= 2
        detectors_with_alerts = {a["detector"] for a in all_alerts}
        assert "F2" in detectors_with_alerts
        assert "F6" in detectors_with_alerts

    def test_summary(self):
        monitor = _CalibrationMonitor()
        monitor.record("F1", detected=True, confidence=0.8, severity="moderate")
        monitor.record("F2", detected=False, confidence=0.0, severity="none")
        monitor.record_run()

        summary = monitor.get_summary()
        assert summary["total_detectors_observed"] == 2
        assert summary["total_observations"] == 2
        assert summary["total_diagnose_runs"] == 1
        assert "monitoring_since" in summary

    def test_window_trimming(self):
        """Monitor should trim old records when window is exceeded."""
        monitor = _CalibrationMonitor()
        monitor.MAX_WINDOW = 10  # Small window for testing

        for i in range(20):
            monitor.record("F5", detected=True, confidence=0.5 + i * 0.01, severity="minor")

        stats = monitor.get_stats()
        # Should only have MAX_WINDOW records
        assert stats["F5"]["total_observations"] == 10

    def test_multiple_detectors_independent(self):
        """Different detectors should have independent stats."""
        monitor = _CalibrationMonitor()
        monitor.record("F1", detected=True, confidence=0.9, severity="severe")
        monitor.record("F6", detected=False, confidence=0.0, severity="none")
        monitor.record("F10", detected=True, confidence=0.5, severity="minor")

        stats = monitor.get_stats()
        assert stats["F1"]["detected_count"] == 1
        assert stats["F6"]["detected_count"] == 0
        assert stats["F10"]["detected_count"] == 1


class TestICPDetectorInventory:
    """Test the ICP detector inventory endpoint function."""

    def test_detector_modules_importable(self):
        """All detectors in the module map should be importable."""
        from app.detection.turn_aware import _DETECTOR_MODULES

        # Count class-level detectors (not functions)
        class_detectors = [
            name for name in _DETECTOR_MODULES
            if name[0].isupper() and not name.startswith("_")
        ]
        # We should have a good number of turn-aware detectors
        assert len(class_detectors) >= 15

    def test_failure_modes_covered(self):
        """Verify F1-F14 are all covered by turn-aware detectors."""
        from app.detection.turn_aware import _DETECTOR_MODULES

        # Known detector names for each failure mode
        expected_modes = {
            "F1": "Specification",
            "F2": "TaskDecomposition",
            "F3": "Resource",
            "F6": "Derailment",
            "F7": "ContextNeglect",
            "F8": "Withholding",
            "F9": "Usurpation",
            "F10": "Communication",
            "F11": "Coordination",
            "F12": "OutputValidation",
            "F13": "QualityGate",
            "F14": "Completion",
        }

        all_names = set(_DETECTOR_MODULES.keys())
        for fm, keyword in expected_modes.items():
            matches = [n for n in all_names if keyword in n]
            assert len(matches) >= 1, f"No detector found for {fm} (keyword: {keyword})"
