"""Tests for Sprint 3 confidence tier feature."""

import pytest
from app.detection_enterprise.orchestrator import (
    ConfidenceTier,
    DetectionCategory,
    DetectionResult,
    Severity,
)


def _make_result(confidence: float) -> DetectionResult:
    return DetectionResult(
        category=DetectionCategory.LOOP,
        detected=True,
        confidence=confidence,
        severity=Severity.HIGH,
        title="test",
        description="test detection",
    )


class TestConfidenceTierMapping:
    def test_high_tier(self):
        result = _make_result(0.85)
        assert result.confidence_tier == ConfidenceTier.HIGH

    def test_likely_tier(self):
        result = _make_result(0.70)
        assert result.confidence_tier == ConfidenceTier.LIKELY

    def test_possible_tier(self):
        result = _make_result(0.50)
        assert result.confidence_tier == ConfidenceTier.POSSIBLE

    def test_low_tier(self):
        result = _make_result(0.30)
        assert result.confidence_tier == ConfidenceTier.LOW


class TestConfidenceTierBoundaries:
    """Verify exact boundary values map correctly."""

    def test_boundary_080(self):
        assert _make_result(0.80).confidence_tier == ConfidenceTier.HIGH

    def test_boundary_below_080(self):
        assert _make_result(0.79).confidence_tier == ConfidenceTier.LIKELY

    def test_boundary_060(self):
        assert _make_result(0.60).confidence_tier == ConfidenceTier.LIKELY

    def test_boundary_below_060(self):
        assert _make_result(0.59).confidence_tier == ConfidenceTier.POSSIBLE

    def test_boundary_040(self):
        assert _make_result(0.40).confidence_tier == ConfidenceTier.POSSIBLE

    def test_boundary_below_040(self):
        assert _make_result(0.39).confidence_tier == ConfidenceTier.LOW

    def test_boundary_zero(self):
        assert _make_result(0.0).confidence_tier == ConfidenceTier.LOW

    def test_boundary_one(self):
        assert _make_result(1.0).confidence_tier == ConfidenceTier.HIGH


class TestConfidenceTierInToDict:
    def test_to_dict_includes_confidence_tier(self):
        result = _make_result(0.85)
        d = result.to_dict()
        assert "confidence_tier" in d
        assert d["confidence_tier"] == "high"

    def test_to_dict_tier_matches_confidence(self):
        for conf, expected_tier in [
            (0.90, "high"),
            (0.70, "likely"),
            (0.50, "possible"),
            (0.20, "low"),
        ]:
            d = _make_result(conf).to_dict()
            assert d["confidence_tier"] == expected_tier, (
                f"confidence={conf} should map to {expected_tier}, got {d['confidence_tier']}"
            )


class TestConfidenceTierEnum:
    def test_tier_values(self):
        assert ConfidenceTier.HIGH.value == "high"
        assert ConfidenceTier.LIKELY.value == "likely"
        assert ConfidenceTier.POSSIBLE.value == "possible"
        assert ConfidenceTier.LOW.value == "low"

    def test_tier_is_str(self):
        """ConfidenceTier inherits from str for JSON serialization."""
        assert isinstance(ConfidenceTier.HIGH, str)
