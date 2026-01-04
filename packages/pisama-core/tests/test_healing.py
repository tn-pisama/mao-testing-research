"""Tests for pisama_core.healing module."""

import pytest

from pisama_core.healing.models import FixContext, FixResult, HealingPlan
from pisama_core.healing.base import BaseFix
from pisama_core.healing.engine import HealingEngine
from pisama_core.detection.result import DetectionResult, FixRecommendation, FixType


class TestFixContext:
    """Tests for FixContext model."""

    def test_create_context(self):
        """Test basic context creation."""
        result = DetectionResult.issue_found("test", severity=50, summary="test")
        context = FixContext(
            detection_result=result,
            session_id="session-1",
        )
        assert context.session_id == "session-1"
        assert context.detection_result == result

    def test_context_with_metadata(self):
        """Test context with extra metadata."""
        result = DetectionResult.issue_found("test", severity=50, summary="test")
        context = FixContext(
            detection_result=result,
            session_id="session-1",
            metadata={"attempt": 1, "user_approved": True},
        )
        assert context.metadata["attempt"] == 1


class TestFixResult:
    """Tests for FixResult model."""

    def test_create_success_result(self):
        """Test creating successful fix result."""
        result = FixResult(
            success=True,
            fix_type=FixType.BREAK_LOOP,
            message="Loop broken successfully",
        )
        assert result.success is True
        assert result.fix_type == FixType.BREAK_LOOP

    def test_create_failure_result(self):
        """Test creating failed fix result."""
        result = FixResult(
            success=False,
            fix_type=FixType.BREAK_LOOP,
            message="Failed to break loop",
            error="Permission denied",
        )
        assert result.success is False
        assert result.error == "Permission denied"


class TestHealingPlan:
    """Tests for HealingPlan model."""

    def test_create_plan(self):
        """Test creating healing plan."""
        plan = HealingPlan(
            fixes=[FixType.BREAK_LOOP, FixType.SWITCH_STRATEGY],
            priority_order=[0, 1],
        )
        assert len(plan.fixes) == 2
        assert plan.fixes[0] == FixType.BREAK_LOOP

    def test_plan_is_empty(self):
        """Test empty plan detection."""
        empty_plan = HealingPlan()
        assert empty_plan.is_empty is True

        non_empty = HealingPlan(fixes=[FixType.BREAK_LOOP])
        assert non_empty.is_empty is False


class SimpleTestFix(BaseFix):
    """Simple fix for testing."""

    fix_type = FixType.BREAK_LOOP

    async def apply(self, context: FixContext) -> FixResult:
        """Apply the fix."""
        return FixResult(
            success=True,
            fix_type=self.fix_type,
            message="Test fix applied",
        )

    def can_apply(self, context: FixContext) -> bool:
        """Check if fix can be applied."""
        return True


class TestBaseFix:
    """Tests for BaseFix."""

    def test_fix_attributes(self):
        """Test fix has required attributes."""
        fix = SimpleTestFix()
        assert fix.fix_type == FixType.BREAK_LOOP

    @pytest.mark.asyncio
    async def test_apply_fix(self):
        """Test applying fix."""
        fix = SimpleTestFix()
        result = DetectionResult.issue_found("test", severity=50, summary="test")
        context = FixContext(detection_result=result, session_id="sess-1")

        fix_result = await fix.apply(context)
        assert fix_result.success is True


class TestHealingEngine:
    """Tests for HealingEngine."""

    def test_create_engine(self):
        """Test creating healing engine."""
        engine = HealingEngine()
        assert engine is not None

    def test_analyze_detection_result(self):
        """Test analyzing detection result for healing plan."""
        engine = HealingEngine()
        result = DetectionResult.issue_found(
            detector_name="loop",
            severity=60,
            summary="Loop detected",
            fix_type=FixType.BREAK_LOOP,
            fix_instruction="Break the loop",
        )

        plan = engine.analyze(result)
        assert plan is not None
        # Should have at least the recommended fix
        assert len(plan.fixes) >= 1

    def test_analyze_no_issue_returns_empty_plan(self):
        """Test that no-issue result returns empty plan."""
        engine = HealingEngine()
        result = DetectionResult.no_issue("test")

        plan = engine.analyze(result)
        assert plan.is_empty is True

    def test_register_fix(self):
        """Test registering a fix handler."""
        engine = HealingEngine()
        fix = SimpleTestFix()
        engine.register_fix(fix)

        assert engine.get_fix(FixType.BREAK_LOOP) is fix

    @pytest.mark.asyncio
    async def test_execute_fix(self):
        """Test executing a fix."""
        engine = HealingEngine()
        fix = SimpleTestFix()
        engine.register_fix(fix)

        result = DetectionResult.issue_found("test", severity=50, summary="test")
        context = FixContext(detection_result=result, session_id="sess-1")

        fix_result = await engine.execute_fix(FixType.BREAK_LOOP, context)
        assert fix_result.success is True
