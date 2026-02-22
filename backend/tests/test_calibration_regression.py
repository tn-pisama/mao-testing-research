"""Calibration regression tests — ensures no detector silently degrades.

Phase S1 of the eval pipeline plan.
Run with: pytest tests/test_calibration_regression.py -m slow -v
"""

import pytest

from app.detection_enterprise.calibrate import calibrate_all


# -----------------------------------------------------------------------
# Thresholds
# -----------------------------------------------------------------------
MINIMUM_F1 = 0.40  # Absolute floor — anything below is broken
TARGET_F1 = 0.65   # Warning threshold — below this needs attention
AVERAGE_F1_FLOOR = 0.70  # System-wide minimum average


@pytest.mark.slow
def test_no_detector_below_minimum_f1():
    """No detector should have F1 below the absolute floor."""
    report = calibrate_all()
    results = report["results"]

    broken = []
    for name, metrics in results.items():
        if metrics["f1"] < MINIMUM_F1:
            broken.append(f"{name}: F1={metrics['f1']:.4f}")

    assert not broken, (
        f"Detectors below minimum F1 ({MINIMUM_F1}): {broken}"
    )


@pytest.mark.slow
def test_average_f1_above_floor():
    """System-wide average F1 must stay above floor."""
    report = calibrate_all()
    results = report["results"]

    assert len(results) > 0, "No detector results returned"

    avg_f1 = sum(m["f1"] for m in results.values()) / len(results)
    assert avg_f1 >= AVERAGE_F1_FLOOR, (
        f"Average F1 ({avg_f1:.4f}) below floor ({AVERAGE_F1_FLOOR})"
    )


@pytest.mark.slow
def test_no_detector_completely_broken():
    """Every detector must have F1 > 0 (not completely non-functional)."""
    report = calibrate_all()
    results = report["results"]

    zero_f1 = [name for name, m in results.items() if m["f1"] == 0.0]
    assert not zero_f1, (
        f"Detectors with F1=0.0 (completely broken): {zero_f1}"
    )


@pytest.mark.slow
def test_calibration_report_structure():
    """Calibration report has expected structure."""
    report = calibrate_all()

    assert "calibrated_at" in report
    assert "detector_count" in report
    assert "skipped" in report
    assert "results" in report
    assert isinstance(report["results"], dict)
    assert report["detector_count"] > 0

    for name, metrics in report["results"].items():
        assert "optimal_threshold" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert "sample_count" in metrics
        assert 0.0 <= metrics["precision"] <= 1.0
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["f1"] <= 1.0
        assert metrics["sample_count"] > 0


@pytest.mark.slow
def test_all_target_types_calibrated():
    """All 17 target detection types should be calibrated (not skipped)."""
    report = calibrate_all()

    # We expect at least 15 detectors calibrated (allow 2 skips for optional enterprise detectors)
    assert report["detector_count"] >= 15, (
        f"Only {report['detector_count']} detectors calibrated, "
        f"skipped: {report['skipped']}"
    )


@pytest.mark.slow
def test_detectors_below_target_count():
    """Track how many detectors are below the target F1 (informational)."""
    report = calibrate_all()
    results = report["results"]

    below_target = {
        name: metrics["f1"]
        for name, metrics in results.items()
        if metrics["f1"] < TARGET_F1
    }

    # This test passes but prints a warning — useful for CI visibility
    if below_target:
        sorted_below = sorted(below_target.items(), key=lambda x: x[1])
        warning_msg = "Detectors below target F1 ({}):\n".format(TARGET_F1)
        for name, f1 in sorted_below:
            warning_msg += f"  {name}: {f1:.4f}\n"
        import warnings
        warnings.warn(warning_msg, stacklevel=1)


@pytest.mark.slow
def test_no_significant_f1_regression():
    """No detector should drop more than 0.10 F1 vs previous calibration."""
    from app.detection_enterprise.calibration_history import CalibrationHistory

    history = CalibrationHistory()
    experiments = history.load_all()
    if len(experiments) < 2:
        pytest.skip("Need at least 2 experiments for regression comparison")

    current = experiments[-1]
    previous = experiments[-2]

    regressions = []
    for dtype in current.results:
        if dtype in previous.results:
            current_f1 = current.results[dtype].get("f1", 0.0)
            previous_f1 = previous.results[dtype].get("f1", 0.0)
            delta = current_f1 - previous_f1
            if delta < -0.10:
                regressions.append(
                    f"{dtype}: {previous_f1:.4f} → {current_f1:.4f} ({delta:+.4f})"
                )

    assert not regressions, (
        f"Significant F1 regressions (>0.10 drop) vs previous experiment:\n"
        + "\n".join(f"  {r}" for r in regressions)
    )
