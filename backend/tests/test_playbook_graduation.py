"""Tests for the Learning Loop / Playbook Graduation system (Gap 5).

Tests fix effectiveness tracking, graduation, revocation, and
auto-apply recommendations.
"""

import pytest
from datetime import datetime, timezone

from app.healing.playbook import (
    PlaybookRegistry,
    PlaybookEntry,
    FixOutcome,
    DEFAULT_GRADUATION_THRESHOLD,
)


# ---------------------------------------------------------------------------
# FixOutcome tests
# ---------------------------------------------------------------------------

class TestFixOutcome:
    def test_outcome_defaults(self):
        outcome = FixOutcome(
            detection_type="infinite_loop",
            fix_type="retry_limit",
            success=True,
        )
        assert outcome.detection_type == "infinite_loop"
        assert outcome.fix_type == "retry_limit"
        assert outcome.success is True
        assert outcome.timestamp is not None


# ---------------------------------------------------------------------------
# PlaybookEntry tests
# ---------------------------------------------------------------------------

class TestPlaybookEntry:
    def test_empty_entry(self):
        entry = PlaybookEntry(detection_type="loop", fix_type="retry")
        assert entry.success_rate == 0.0
        assert entry.total_count == 0
        assert entry.graduated is False

    def test_record_success(self):
        entry = PlaybookEntry(detection_type="loop", fix_type="retry")
        entry.record(FixOutcome(
            detection_type="loop", fix_type="retry",
            success=True, confidence=0.9,
        ))
        assert entry.success_count == 1
        assert entry.total_count == 1
        assert entry.consecutive_successes == 1
        assert entry.avg_confidence == 0.9

    def test_record_failure_resets_consecutive(self):
        entry = PlaybookEntry(detection_type="loop", fix_type="retry")
        entry.record(FixOutcome(detection_type="loop", fix_type="retry", success=True))
        entry.record(FixOutcome(detection_type="loop", fix_type="retry", success=True))
        assert entry.consecutive_successes == 2

        entry.record(FixOutcome(detection_type="loop", fix_type="retry", success=False))
        assert entry.consecutive_successes == 0
        assert entry.failure_count == 1

    def test_success_rate(self):
        entry = PlaybookEntry(detection_type="loop", fix_type="retry")
        for _ in range(3):
            entry.record(FixOutcome(detection_type="loop", fix_type="retry", success=True))
        entry.record(FixOutcome(detection_type="loop", fix_type="retry", success=False))

        assert entry.success_rate == 0.75

    def test_to_dict(self):
        entry = PlaybookEntry(
            detection_type="infinite_loop",
            fix_type="retry_limit",
            success_count=5,
            total_count=6,
            failure_count=1,
            graduated=True,
        )
        d = entry.to_dict()
        assert d["detection_type"] == "infinite_loop"
        assert d["graduated"] is True
        assert d["success_rate"] == round(5 / 6, 3)

    def test_revoke_on_failure(self):
        entry = PlaybookEntry(
            detection_type="loop", fix_type="retry",
            graduated=True,
            graduated_at=datetime.now(timezone.utc),
        )
        entry.record(FixOutcome(detection_type="loop", fix_type="retry", success=False))
        assert entry.graduated is False
        assert entry.graduated_at is None


# ---------------------------------------------------------------------------
# PlaybookRegistry tests
# ---------------------------------------------------------------------------

class TestPlaybookRegistry:
    def test_default_threshold(self):
        registry = PlaybookRegistry()
        assert registry.graduation_threshold == DEFAULT_GRADUATION_THRESHOLD

    def test_custom_threshold(self):
        registry = PlaybookRegistry(graduation_threshold=5)
        assert registry.graduation_threshold == 5

    def test_record_and_graduate(self):
        registry = PlaybookRegistry(graduation_threshold=3)

        for i in range(3):
            entry = registry.record_outcome(FixOutcome(
                detection_type="infinite_loop",
                fix_type="retry_limit",
                success=True,
                confidence=0.85,
            ))

        assert entry.graduated is True
        assert entry.graduated_at is not None
        assert registry.is_graduated("infinite_loop", "retry_limit") is True

    def test_no_graduation_below_threshold(self):
        registry = PlaybookRegistry(graduation_threshold=3)

        for i in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="infinite_loop",
                fix_type="retry_limit",
                success=True,
            ))

        assert registry.is_graduated("infinite_loop", "retry_limit") is False

    def test_failure_prevents_graduation(self):
        registry = PlaybookRegistry(graduation_threshold=3)

        # 2 successes, then failure, then 2 more successes
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry",
                success=True,
            ))
        registry.record_outcome(FixOutcome(
            detection_type="loop", fix_type="retry",
            success=False,
        ))
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry",
                success=True,
            ))

        assert registry.is_graduated("loop", "retry") is False

    def test_failure_revokes_graduation(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry",
                success=True,
            ))
        assert registry.is_graduated("loop", "retry") is True

        registry.record_outcome(FixOutcome(
            detection_type="loop", fix_type="retry",
            success=False,
        ))
        assert registry.is_graduated("loop", "retry") is False

    def test_re_graduation_after_revoke(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        # Graduate
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry", success=True,
            ))
        assert registry.is_graduated("loop", "retry") is True

        # Revoke
        registry.record_outcome(FixOutcome(
            detection_type="loop", fix_type="retry", success=False,
        ))
        assert registry.is_graduated("loop", "retry") is False

        # Re-graduate
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry", success=True,
            ))
        assert registry.is_graduated("loop", "retry") is True

    def test_get_graduated_fix(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="infinite_loop",
                fix_type="circuit_breaker",
                success=True,
            ))

        result = registry.get_graduated_fix("infinite_loop")
        assert result == "circuit_breaker"

    def test_get_graduated_fix_prefers_higher_success_rate(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        # Graduate circuit_breaker with 100% (2/2)
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="infinite_loop",
                fix_type="circuit_breaker",
                success=True,
            ))

        # Graduate retry_limit with 66% (2/3)
        registry.record_outcome(FixOutcome(
            detection_type="infinite_loop",
            fix_type="retry_limit",
            success=False,
        ))
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="infinite_loop",
                fix_type="retry_limit",
                success=True,
            ))

        result = registry.get_graduated_fix("infinite_loop")
        assert result == "circuit_breaker"

    def test_get_graduated_fix_none(self):
        registry = PlaybookRegistry()
        assert registry.get_graduated_fix("unknown") is None

    def test_get_recommended_fix_graduated(self):
        registry = PlaybookRegistry(graduation_threshold=2)
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry", success=True,
            ))

        rec = registry.get_recommended_fix("loop")
        assert rec is not None
        assert rec.fix_type == "retry"
        assert rec.graduated is True

    def test_get_recommended_fix_non_graduated(self):
        registry = PlaybookRegistry(graduation_threshold=5)
        registry.record_outcome(FixOutcome(
            detection_type="loop", fix_type="retry", success=True,
        ))

        rec = registry.get_recommended_fix("loop")
        assert rec is not None
        assert rec.fix_type == "retry"
        assert rec.graduated is False

    def test_get_recommended_fix_none(self):
        registry = PlaybookRegistry()
        assert registry.get_recommended_fix("unknown") is None

    def test_get_all_graduated(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry", success=True,
            ))
        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="corruption", fix_type="schema", success=True,
            ))
        # Not graduated
        registry.record_outcome(FixOutcome(
            detection_type="derailment", fix_type="anchor", success=True,
        ))

        graduated = registry.get_all_graduated()
        assert len(graduated) == 2

    def test_get_stats(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry", success=True,
            ))
        registry.record_outcome(FixOutcome(
            detection_type="corruption", fix_type="schema", success=False,
        ))

        stats = registry.get_stats()
        assert stats["total_patterns"] == 2
        assert stats["graduated_count"] == 1
        assert stats["total_outcomes"] == 3
        assert stats["overall_success_rate"] == pytest.approx(2 / 3)

    def test_should_auto_apply_graduated(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry", success=True,
            ))

        should, reason = registry.should_auto_apply("loop", "retry")
        assert should is True
        assert "Graduated" in reason

    def test_should_auto_apply_not_graduated(self):
        registry = PlaybookRegistry(graduation_threshold=5)
        registry.record_outcome(FixOutcome(
            detection_type="loop", fix_type="retry", success=True,
        ))

        should, reason = registry.should_auto_apply("loop", "retry")
        assert should is False
        assert reason is None

    def test_serialization_roundtrip(self):
        registry = PlaybookRegistry(graduation_threshold=2)

        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry",
                success=True, confidence=0.9,
            ))
        registry.record_outcome(FixOutcome(
            detection_type="corruption", fix_type="schema",
            success=False, confidence=0.7,
        ))

        # Serialize
        data = registry.to_dict()

        # Restore
        restored = PlaybookRegistry.from_dict(data)

        assert restored.graduation_threshold == 2
        assert restored.is_graduated("loop", "retry") is True
        assert restored.is_graduated("corruption", "schema") is False

        stats = restored.get_stats()
        assert stats["total_patterns"] == 2
        assert stats["total_outcomes"] == 3

    def test_independent_detection_types(self):
        """Different detection types should track independently."""
        registry = PlaybookRegistry(graduation_threshold=2)

        for _ in range(2):
            registry.record_outcome(FixOutcome(
                detection_type="loop", fix_type="retry", success=True,
            ))

        registry.record_outcome(FixOutcome(
            detection_type="corruption", fix_type="retry", success=True,
        ))

        assert registry.is_graduated("loop", "retry") is True
        assert registry.is_graduated("corruption", "retry") is False
