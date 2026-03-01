"""Calibration regression tests — ensures no detector silently degrades.

Phase S1 of the eval pipeline plan, updated for capability vs regression
eval separation per "Demystifying Evals for AI Agents" recommendations.

Run with: pytest tests/test_calibration_regression.py -m slow -v
"""

import pytest

from app.detection_enterprise.calibrate import (
    calibrate_all,
    generate_capability_registry,
)


# -----------------------------------------------------------------------
# Thresholds (uniform baselines)
# -----------------------------------------------------------------------
MINIMUM_F1 = 0.40  # Absolute floor — anything below is broken
TARGET_F1 = 0.65   # Warning threshold — below this needs attention
AVERAGE_F1_FLOOR = 0.70  # System-wide minimum average


# -----------------------------------------------------------------------
# Per-readiness-tier CI gates (Anthropic evals article recommendation)
# -----------------------------------------------------------------------
# Production detectors have tighter gates than beta/experimental.
TIER_GATES = {
    "production":   {"min_f1": 0.70, "max_regression": 0.05},
    "beta":         {"min_f1": 0.40, "max_regression": 0.10},
    "experimental": {"min_f1": 0.30, "max_regression": 0.15},
    "failing":      {"min_f1": 0.00, "max_regression": 1.00},
}


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
def test_report_includes_difficulty_and_latency():
    """Calibration report includes per-difficulty breakdown and latency stats."""
    report = calibrate_all()

    for name, metrics in report["results"].items():
        # difficulty_breakdown should exist (may be empty for edge cases)
        assert "difficulty_breakdown" in metrics, f"{name}: missing difficulty_breakdown"
        assert "latency_stats" in metrics, f"{name}: missing latency_stats"
        assert "llm_cost" in metrics, f"{name}: missing llm_cost"

        # Validate difficulty breakdown structure when present
        for diff, dm in metrics["difficulty_breakdown"].items():
            assert "f1" in dm, f"{name}/{diff}: missing f1"
            assert "n" in dm, f"{name}/{diff}: missing n"
            assert 0.0 <= dm["f1"] <= 1.0, f"{name}/{diff}: f1 out of range"
            assert dm["n"] > 0, f"{name}/{diff}: n must be positive"


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
    """No detector should drop more than its tier-appropriate max regression.

    Production detectors: max 0.05 drop
    Beta detectors: max 0.10 drop
    Experimental detectors: max 0.15 drop
    """
    from app.detection_enterprise.calibration_history import CalibrationHistory
    from app.detection_enterprise.calibrate import _compute_readiness

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

            # Determine readiness tier for this detector
            precision = current.results[dtype].get("precision", 0.0)
            sample_count = current.results[dtype].get("sample_count", 0)
            readiness = _compute_readiness(current_f1, precision, sample_count)
            gate = TIER_GATES.get(readiness, TIER_GATES["failing"])
            max_regression = gate["max_regression"]

            if delta < -max_regression:
                regressions.append(
                    f"{dtype} ({readiness}): {previous_f1:.4f} → {current_f1:.4f} "
                    f"({delta:+.4f}, max allowed: -{max_regression:.2f})"
                )

    assert not regressions, (
        f"Significant F1 regressions vs previous experiment:\n"
        + "\n".join(f"  {r}" for r in regressions)
    )


@pytest.mark.slow
def test_per_tier_minimum_f1():
    """Each detector must meet its readiness tier's minimum F1 gate."""
    from app.detection_enterprise.calibrate import _compute_readiness

    report = calibrate_all()
    results = report["results"]

    failures = []
    for name, metrics in results.items():
        f1 = metrics["f1"]
        precision = metrics.get("precision", 0.0)
        sample_count = metrics.get("sample_count", 0)
        readiness = _compute_readiness(f1, precision, sample_count)
        gate = TIER_GATES.get(readiness, TIER_GATES["failing"])

        if f1 < gate["min_f1"]:
            failures.append(
                f"{name} ({readiness}): F1={f1:.4f} < tier min {gate['min_f1']:.2f}"
            )

    assert not failures, (
        f"Detectors below their tier's minimum F1:\n"
        + "\n".join(f"  {f}" for f in failures)
    )


# -----------------------------------------------------------------------
# Per-detector targets (Sprint 7)
# -----------------------------------------------------------------------
# These four detectors were fixed in Sprint 7 and must not regress below 0.55.
CRITICAL_DETECTOR_TARGETS = {
    "workflow": 0.55,
    "corruption": 0.55,
    "completion": 0.55,
    "specification": 0.55,
}


@pytest.mark.slow
def test_critical_detectors_above_target():
    """Sprint 7 critical detectors must stay above their per-detector F1 targets."""
    report = calibrate_all()
    results = report["results"]

    failures = []
    for detector_name, min_f1 in CRITICAL_DETECTOR_TARGETS.items():
        if detector_name not in results:
            failures.append(f"{detector_name}: NOT FOUND in calibration results")
            continue
        actual_f1 = results[detector_name]["f1"]
        if actual_f1 < min_f1:
            failures.append(
                f"{detector_name}: F1={actual_f1:.4f} < target {min_f1:.4f}"
            )

    assert not failures, (
        f"Critical detectors below per-detector targets:\n"
        + "\n".join(f"  {f}" for f in failures)
    )


# -----------------------------------------------------------------------
# Saturation detection (Anthropic evals article)
# -----------------------------------------------------------------------

@pytest.mark.slow
def test_saturated_detectors_flagged():
    """Warn when any detector hits F1>=0.95 with few hard samples (saturation signal)."""
    report = calibrate_all()
    registry = generate_capability_registry(report)

    saturated = [
        name for name, entry in registry["capabilities"].items()
        if entry.get("eval_category") == "saturated"
    ]

    # Informational: saturation means the eval no longer provides signal
    if saturated:
        import warnings
        warnings.warn(
            f"Saturated detectors (need harder samples): {', '.join(saturated)}",
            stacklevel=1,
        )


@pytest.mark.slow
def test_capability_registry_has_eval_categories():
    """Capability registry assigns eval_category to every detector."""
    report = calibrate_all()
    registry = generate_capability_registry(report)

    valid_categories = {"regression", "capability", "saturated"}
    for name, entry in registry["capabilities"].items():
        assert "eval_category" in entry, f"{name}: missing eval_category"
        assert entry["eval_category"] in valid_categories, (
            f"{name}: invalid eval_category '{entry['eval_category']}'"
        )
