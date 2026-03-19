"""Tests for convergence fix generators."""

import pytest
from app.fixes.convergence_fixes import ConvergenceFixGenerator
from app.fixes.models import FixType, FixConfidence


@pytest.fixture
def generator():
    return ConvergenceFixGenerator()


class TestCanHandle:
    def test_handles_convergence(self, generator):
        assert generator.can_handle("convergence_failure")

    def test_handles_convergence_prefix(self, generator):
        assert generator.can_handle("convergence")

    def test_does_not_handle_loop(self, generator):
        assert not generator.can_handle("infinite_loop")


class TestPlateauFixes:
    def test_generates_plateau_fixes(self, generator):
        detection = {
            "id": "det_001",
            "details": {"failure_type": "plateau", "stalled_steps": 10},
        }
        fixes = generator.generate_fixes(detection, {})
        assert len(fixes) >= 2
        fix_types = {f.fix_type for f in fixes}
        assert FixType.CHECKPOINT_RECOVERY in fix_types
        assert FixType.STRATEGY_SWITCH in fix_types

    def test_plateau_fixes_have_code_changes(self, generator):
        fixes = generator.generate_fixes(
            {"id": "d1", "details": {"failure_type": "plateau"}}, {}
        )
        for fix in fixes:
            assert len(fix.code_changes) > 0
            assert fix.code_changes[0].suggested_code


class TestRegressionFixes:
    def test_generates_regression_fixes(self, generator):
        detection = {
            "id": "det_002",
            "details": {"failure_type": "regression", "regression_frac": 0.05},
        }
        fixes = generator.generate_fixes(detection, {})
        assert len(fixes) >= 2
        fix_types = {f.fix_type for f in fixes}
        assert FixType.CHECKPOINT_RECOVERY in fix_types
        assert FixType.REGRESSION_GUARD in fix_types

    def test_regression_guard_uses_tolerance(self, generator):
        detection = {
            "id": "d1",
            "details": {"failure_type": "regression", "regression_frac": 0.1},
        }
        fixes = generator.generate_fixes(detection, {})
        guard_fix = next(f for f in fixes if f.fix_type == FixType.REGRESSION_GUARD)
        assert "0.1" in guard_fix.code_changes[0].suggested_code


class TestThrashingFixes:
    def test_generates_thrashing_fixes(self, generator):
        detection = {
            "id": "det_003",
            "details": {"failure_type": "thrashing"},
        }
        fixes = generator.generate_fixes(detection, {})
        assert len(fixes) >= 2
        fix_types = {f.fix_type for f in fixes}
        assert FixType.DIRECTION_LOCK in fix_types
        assert FixType.EXPLORATION_TEMPERATURE in fix_types


class TestDivergenceFixes:
    def test_generates_divergence_fixes(self, generator):
        detection = {
            "id": "det_004",
            "details": {"failure_type": "divergence"},
        }
        fixes = generator.generate_fixes(detection, {})
        assert len(fixes) >= 2
        fix_types = {f.fix_type for f in fixes}
        assert FixType.EMERGENCY_STOP in fix_types
        assert FixType.CHECKPOINT_RECOVERY in fix_types


class TestFixSuggestionQuality:
    def test_all_fixes_have_required_fields(self, generator):
        for failure_type in ("plateau", "regression", "thrashing", "divergence"):
            detection = {"id": "d", "details": {"failure_type": failure_type}}
            fixes = generator.generate_fixes(detection, {})
            for fix in fixes:
                assert fix.id
                assert fix.detection_type == "convergence_failure"
                assert fix.title
                assert fix.description
                assert fix.rationale
                assert fix.tags
                assert isinstance(fix.confidence, FixConfidence)

    def test_default_fallback(self, generator):
        """Unknown failure_type gets default fixes."""
        detection = {"id": "d", "details": {"failure_type": "unknown"}}
        fixes = generator.generate_fixes(detection, {})
        assert len(fixes) >= 2
