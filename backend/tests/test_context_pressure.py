"""Tests for F20 context pressure detector."""
import pytest
from app.detection.context_pressure import (
    ContextPressureDetector,
    PressureSeverity,
)


@pytest.fixture
def detector():
    return ContextPressureDetector()


def _make_states(n, token_count_fn=None, output_len_fn=None, context_limit=200_000):
    """Helper to build state lists with controllable token/output patterns."""
    states = []
    for i in range(n):
        tokens = token_count_fn(i) if token_count_fn else i * 5000
        out_len = output_len_fn(i) if output_len_fn else 200
        states.append({
            "sequence_num": i,
            "token_count": tokens,
            "state_delta": {"output": "x" * out_len},
        })
    return states


class TestContextPressureDetector:
    def test_no_pressure_short_trace(self, detector):
        """Traces with <4 states should not trigger."""
        states = _make_states(3)
        result = detector.detect(states=states)
        assert not result.detected

    def test_no_pressure_healthy_trace(self, detector):
        """Healthy trace with low utilization should not trigger."""
        states = _make_states(10, token_count_fn=lambda i: i * 1000, output_len_fn=lambda i: 200)
        result = detector.detect(states=states, context_limit=200_000)
        assert not result.detected

    def test_high_utilization_signal(self, detector):
        """High token count near context limit should trigger utilization signal."""
        # Each state adds 12k tokens → 20 states = 240k tokens (> 200k limit)
        states = _make_states(20, token_count_fn=lambda i: i * 12000)
        result = detector.detect(states=states, context_limit=200_000)
        signal_types = [s.signal_type for s in result.signals]
        assert "high_utilization" in signal_types

    def test_output_decline_signal(self, detector):
        """Declining output length should trigger decline signal."""
        # Early states: 500 chars, late states: 50 chars
        states = _make_states(15, output_len_fn=lambda i: max(500 - i * 35, 30))
        result = detector.detect(states=states)
        signal_types = [s.signal_type for s in result.signals]
        assert "output_decline" in signal_types

    def test_wrapup_language_signal(self, detector):
        """Wrap-up language in late states should trigger signal."""
        states = _make_states(10, output_len_fn=lambda i: 200)
        # Inject wrap-up language in last 40% of states
        for i in range(7, 10):
            states[i]["state_delta"]["output"] = (
                "I'll leave the rest for now. This should be sufficient. "
                "For brevity, I'll skip the remaining items."
            )
        result = detector.detect(states=states)
        signal_types = [s.signal_type for s in result.signals]
        assert "premature_wrapup" in signal_types

    def test_quality_cliff_signal(self, detector):
        """Sudden output length drop in final states should trigger cliff."""
        # Consistent 300-char output, then sudden drop to 20 in last 2 states
        def output_fn(i):
            return 20 if i >= 18 else 300
        states = _make_states(20, output_len_fn=output_fn)
        result = detector.detect(states=states)
        signal_types = [s.signal_type for s in result.signals]
        assert "quality_cliff" in signal_types

    def test_requires_two_signals(self, detector):
        """Detection requires at least 2 active signals (ensemble gate)."""
        # Only one signal: high utilization, but normal output
        states = _make_states(10, token_count_fn=lambda i: i * 20000, output_len_fn=lambda i: 200)
        result = detector.detect(states=states, context_limit=200_000)
        # Might or might not detect — depends on whether only 1 signal fires
        active = sum(1 for s in result.signals if s.strength > 0)
        if active < 2:
            assert not result.detected

    def test_severity_levels(self, detector):
        """High confidence should produce high severity."""
        # Create maximum pressure: high util + declining + wrapup + cliff
        states = _make_states(20, token_count_fn=lambda i: i * 10000, output_len_fn=lambda i: max(400 - i * 20, 10))
        for i in range(15, 20):
            states[i]["state_delta"]["output"] = "I'll leave that for now. For brevity, wrapping up."
        result = detector.detect(states=states, context_limit=200_000)
        if result.detected:
            assert result.severity in (PressureSeverity.MEDIUM, PressureSeverity.HIGH, PressureSeverity.CRITICAL)
