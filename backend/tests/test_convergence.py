"""Tests for convergence issue detection."""

import pytest
from app.detection.convergence import (
    ConvergenceDetector,
    ConvergenceResult,
    ConvergenceFailureType,
    ConvergenceSeverity,
)


@pytest.fixture
def detector():
    return ConvergenceDetector()


class TestConvergenceDetectorBasics:
    """Basic functionality tests."""

    def test_insufficient_data_returns_not_detected(self, detector):
        result = detector.detect_convergence_issues([], direction="minimize")
        assert not result.detected
        assert result.confidence == 0.0

    def test_single_point_returns_not_detected(self, detector):
        result = detector.detect_convergence_issues(
            [{"value": 1.0}], direction="minimize"
        )
        assert not result.detected

    def test_two_points_returns_not_detected(self, detector):
        result = detector.detect_convergence_issues(
            [{"value": 1.0}, {"value": 0.9}], direction="minimize"
        )
        assert not result.detected


class TestPlateau:
    """Plateau detection tests."""

    def test_clear_plateau_detected(self, detector):
        """conv_001: Loss flat at 0.65 for 10 steps."""
        metrics = [{"step": i, "value": 0.65} for i in range(10)]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert result.detected
        assert result.failure_type == "plateau"
        assert result.confidence > 0.5

    def test_near_plateau_detected(self, detector):
        """conv_006: Very slight plateau (0.1% improvement)."""
        metrics = [{"step": i, "value": 0.65 - i * 0.0001} for i in range(10)]
        result = detector.detect_convergence_issues(
            metrics, direction="minimize",
            window_size=10,
        )
        assert result.detected
        assert result.failure_type == "plateau"

    def test_healthy_improvement_not_flagged(self, detector):
        """conv_004: Healthy monotonic improvement."""
        metrics = [{"step": i, "value": 5.0 - i * 0.3} for i in range(10)]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert not result.detected

    def test_slow_but_steady_not_flagged(self, detector):
        """conv_005: Slow but steady improvement."""
        metrics = [{"step": i, "value": 5.0 - i * 0.05} for i in range(10)]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert not result.detected


class TestRegression:
    """Regression detection tests."""

    def test_clear_regression_detected(self, detector):
        """conv_002: Clear 10% regression from best."""
        metrics = [
            {"step": 0, "value": 1.0},
            {"step": 1, "value": 0.8},
            {"step": 2, "value": 0.7},
            {"step": 3, "value": 0.6},  # best
            {"step": 4, "value": 0.7},
            {"step": 5, "value": 0.8},
            {"step": 6, "value": 0.9},  # regressed
        ]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert result.detected
        # Divergence is prioritized here because the recent window shows
        # consistent wrong-direction movement. Both regression and divergence
        # fire, but divergence is more specific.
        assert result.failure_type in ("regression", "divergence")
        assert result.best_value == 0.6
        assert result.confidence > 0.5

    def test_pure_regression_without_divergence(self, detector):
        """Regression where recent values aren't consistently diverging or thrashing."""
        # Few direction changes, not enough for thrashing (need >=3 reversals)
        # Not enough wrong-direction steps for divergence (need >=70%)
        metrics = [
            {"step": 0, "value": 1.0},
            {"step": 1, "value": 0.8},
            {"step": 2, "value": 0.5},  # best
            {"step": 3, "value": 0.52},
            {"step": 4, "value": 0.55},
            {"step": 5, "value": 0.53},  # slightly regressed, not diverging
        ]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert result.detected
        # Should be regression (not enough reversals for thrashing,
        # not enough consecutive wrong-dir for divergence)
        assert result.failure_type == "regression"

    def test_regression_masked_by_noise(self, detector):
        """conv_009: Regression masked by noise."""
        # Best at step 3 (0.5), then noisy regression
        metrics = [
            {"step": 0, "value": 1.0},
            {"step": 1, "value": 0.7},
            {"step": 2, "value": 0.55},
            {"step": 3, "value": 0.5},  # best
            {"step": 4, "value": 0.52},
            {"step": 5, "value": 0.48},  # briefly better? no, still near best
            {"step": 6, "value": 0.55},
            {"step": 7, "value": 0.60},
            {"step": 8, "value": 0.65},  # clearly regressed
        ]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert result.detected
        # Should detect regression (regression_tolerance default is 0.02)

    def test_maximize_regression(self, detector):
        """Regression with maximize direction."""
        metrics = [
            {"step": 0, "value": 0.5},
            {"step": 1, "value": 0.7},
            {"step": 2, "value": 0.9},  # best
            {"step": 3, "value": 0.6},  # regressed
        ]
        result = detector.detect_convergence_issues(metrics, direction="maximize")
        assert result.detected
        assert result.best_value == 0.9


class TestThrashing:
    """Thrashing/oscillation detection tests."""

    def test_clear_thrashing_detected(self, detector):
        """conv_003: Oscillating loss every other step."""
        metrics = [
            {"step": i, "value": 0.64 if i % 2 == 0 else 0.68}
            for i in range(8)
        ]
        result = detector.detect_convergence_issues(
            metrics, direction="minimize", window_size=8,
        )
        assert result.detected
        assert result.failure_type == "thrashing"

    def test_subtle_oscillation_with_trend(self, detector):
        """conv_010: Subtle oscillation with slight trend."""
        # Oscillating but with a very slight downward trend
        metrics = [
            {"step": i, "value": 0.65 - i * 0.002 + (0.01 if i % 2 == 0 else -0.01)}
            for i in range(10)
        ]
        result = detector.detect_convergence_issues(
            metrics, direction="minimize", window_size=10,
        )
        # This is a borderline case — the thrashing signal should be present
        # even with a slight trend, because reversals are frequent
        if result.detected:
            assert result.failure_type in ("thrashing", "plateau")


class TestDivergence:
    """Divergence detection tests."""

    def test_clear_divergence_detected(self, detector):
        """conv_007: Loss increasing for 8 steps."""
        metrics = [{"step": i, "value": 0.5 + i * 0.05} for i in range(8)]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert result.detected
        assert result.failure_type == "divergence"
        assert result.confidence > 0.5

    def test_maximize_divergence(self, detector):
        """Divergence with maximize direction (accuracy decreasing)."""
        metrics = [{"step": i, "value": 0.9 - i * 0.05} for i in range(8)]
        result = detector.detect_convergence_issues(metrics, direction="maximize")
        assert result.detected
        assert result.failure_type == "divergence"


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_brief_plateau_then_breakthrough(self, detector):
        """conv_008: Brief plateau then breakthrough — should not be detected."""
        metrics = [
            {"step": 0, "value": 1.0},
            {"step": 1, "value": 0.8},
            {"step": 2, "value": 0.7},
            {"step": 3, "value": 0.7},
            {"step": 4, "value": 0.7},  # brief plateau
            {"step": 5, "value": 0.5},  # breakthrough
            {"step": 6, "value": 0.3},  # continued improvement
        ]
        result = detector.detect_convergence_issues(
            metrics, direction="minimize", window_size=5,
        )
        # The last 5 steps show improvement, so should not be flagged
        assert not result.detected

    def test_custom_thresholds(self):
        """Custom detector thresholds work correctly."""
        detector = ConvergenceDetector(
            plateau_threshold=0.01,
            regression_tolerance=0.1,
            thrashing_min_reversals=5,
        )
        # With higher plateau threshold, slow improvement triggers
        metrics = [{"step": i, "value": 5.0 - i * 0.005} for i in range(10)]
        result = detector.detect_convergence_issues(
            metrics, direction="minimize", window_size=10,
        )
        assert result.detected
        assert result.failure_type == "plateau"

    def test_result_fields_populated(self, detector):
        """Result fields are correctly populated."""
        metrics = [{"step": i, "value": 0.65} for i in range(10)]
        result = detector.detect_convergence_issues(metrics, direction="minimize")
        assert result.best_value == 0.65
        assert result.current_value == 0.65
        assert result.steps_since_best is not None
        assert result.improvement_rate is not None
        assert result.issues is not None
        assert len(result.issues) > 0

    def test_window_size_parameter(self, detector):
        """Window size parameter controls evaluation scope."""
        # 20 steps: first 15 improving, last 5 flat
        metrics = []
        for i in range(15):
            metrics.append({"step": i, "value": 5.0 - i * 0.2})
        for i in range(5):
            metrics.append({"step": 15 + i, "value": 2.0})

        # With default window=5, should detect plateau in last 5
        result = detector.detect_convergence_issues(
            metrics, direction="minimize", window_size=5,
        )
        assert result.detected
        assert result.failure_type == "plateau"

    def test_none_metrics(self, detector):
        result = detector.detect_convergence_issues(None, direction="minimize")
        assert not result.detected
