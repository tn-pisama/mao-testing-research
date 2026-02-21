"""Tests for ExecutionQualityScorer.

Covers all five scoring dimensions plus overall blending:
  - success_rate
  - output_consistency
  - error_rate
  - retry_effectiveness
  - latency_health
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "xK9mP2vL7nQ4wR8jT5fY3hA6bD0cE1gU")
os.environ.setdefault("DATABASE_URL", "sqlite://")

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.enterprise.quality.execution_scorer import (
    ExecutionQualityScorer,
    ExecutionScores,
)


@pytest.fixture
def scorer():
    return ExecutionQualityScorer()


# ---------------------------------------------------------------------------
# Helpers to build realistic execution history dicts
# ---------------------------------------------------------------------------

def _make_execution(
    status="success",
    duration_ms=1500,
    node_results=None,
):
    """Build a single execution record."""
    if node_results is None:
        node_results = {
            "agent-1": {
                "status": "success",
                "output": {"result": "ok"},
                "retries": 0,
            }
        }
    return {
        "status": status,
        "duration_ms": duration_ms,
        "node_results": node_results,
    }


def _make_success(duration_ms=1500, node_results=None):
    return _make_execution("success", duration_ms, node_results)


def _make_error(duration_ms=1500, node_results=None):
    if node_results is None:
        node_results = {
            "agent-1": {
                "status": "error",
                "output": None,
                "error": "timeout",
                "retries": 0,
            }
        }
    return _make_execution("error", duration_ms, node_results)


# ---------------------------------------------------------------------------
# 1. Empty / insufficient data
# ---------------------------------------------------------------------------


class TestEmptyData:
    """When there is no usable execution data every score must be zero."""

    def test_empty_history_returns_zero_scores(self, scorer):
        result = scorer.score_from_executions([])

        assert result.overall_score == 0.0
        assert result.total_executions == 0
        assert result.success_rate.score == 0.0
        assert result.output_consistency.score == 0.0
        assert result.error_rate.score == 0.0
        assert result.retry_effectiveness.score == 0.0
        assert result.latency_health.score == 0.0

    def test_only_running_status_returns_zero(self, scorer):
        history = [
            _make_execution(status="running", duration_ms=500),
            _make_execution(status="running", duration_ms=800),
            _make_execution(status="waiting", duration_ms=0),
        ]
        result = scorer.score_from_executions(history)

        assert result.overall_score == 0.0
        assert result.total_executions == 0
        assert result.success_rate.score == 0.0


# ---------------------------------------------------------------------------
# 2. Success rate
# ---------------------------------------------------------------------------


class TestSuccessRate:
    """Success rate = (# success) / (# completed)."""

    def test_all_success(self, scorer):
        history = [_make_success() for _ in range(10)]
        result = scorer.score_from_executions(history)

        assert result.success_rate.score == pytest.approx(1.0)
        assert result.success_rate.sample_count == 10
        assert result.success_rate.issues == []

    def test_half_success(self, scorer):
        history = [_make_success() for _ in range(5)] + [
            _make_error() for _ in range(5)
        ]
        result = scorer.score_from_executions(history)

        assert result.success_rate.score == pytest.approx(0.5)
        assert len(result.success_rate.issues) == 1
        # 50% is not < 0.5 so the scorer emits a "Warning", not "Critical"
        assert "Warning" in result.success_rate.issues[0]

    def test_zero_success(self, scorer):
        history = [_make_error() for _ in range(6)]
        result = scorer.score_from_executions(history)

        assert result.success_rate.score == pytest.approx(0.0)
        assert result.success_rate.sample_count == 6


# ---------------------------------------------------------------------------
# 3. Output consistency
# ---------------------------------------------------------------------------


class TestOutputConsistency:
    """Structural consistency of outputs across successful runs."""

    def test_consistent_outputs_high_score(self, scorer):
        """All successful executions produce identical output key structures."""
        node_results = {
            "agent-1": {
                "status": "success",
                "output": {"result": "ok", "confidence": 0.9},
                "retries": 0,
            },
            "agent-2": {
                "status": "success",
                "output": {"summary": "done", "tokens": 42},
                "retries": 0,
            },
        }
        history = [_make_success(node_results=node_results) for _ in range(5)]
        result = scorer.score_from_executions(history)

        assert result.output_consistency.score == pytest.approx(1.0)
        assert result.output_consistency.issues == []

    def test_inconsistent_outputs_lower_score(self, scorer):
        """Different key structures across executions lower the score."""
        history = [
            _make_success(
                node_results={
                    "agent-1": {
                        "status": "success",
                        "output": {"result": "ok"},
                        "retries": 0,
                    }
                }
            ),
            _make_success(
                node_results={
                    "agent-1": {
                        "status": "success",
                        "output": {"result": "ok"},
                        "retries": 0,
                    }
                }
            ),
            _make_success(
                node_results={
                    "agent-1": {
                        "status": "success",
                        "output": {"error_detail": "something", "code": 500},
                        "retries": 0,
                    }
                }
            ),
        ]
        result = scorer.score_from_executions(history)

        # Two unique key structures -> consistency = 1/2 = 0.5
        assert result.output_consistency.score < 1.0
        assert len(result.output_consistency.issues) >= 1

    def test_single_execution_defaults_to_half(self, scorer):
        """Fewer than 2 successful runs -> default score 0.5."""
        history = [_make_success()]
        result = scorer.score_from_executions(history)

        assert result.output_consistency.score == pytest.approx(0.5)
        assert result.output_consistency.evidence.get("reason") == "insufficient_samples"


# ---------------------------------------------------------------------------
# 4. Error rate
# ---------------------------------------------------------------------------


class TestErrorRate:
    """Per-node error rate scoring: score = 1 - avg_error_rate."""

    def test_no_errors_score_near_one(self, scorer):
        node_results = {
            "agent-1": {"status": "success", "output": {"x": 1}, "retries": 0},
            "agent-2": {"status": "success", "output": {"y": 2}, "retries": 0},
        }
        history = [_make_success(node_results=node_results) for _ in range(8)]
        result = scorer.score_from_executions(history)

        assert result.error_rate.score == pytest.approx(1.0)
        assert result.error_rate.issues == []

    def test_high_error_rate_low_score(self, scorer):
        """All nodes error on every execution -> score near 0."""
        node_results_err = {
            "agent-1": {"status": "error", "output": None, "error": "crash", "retries": 0},
            "agent-2": {"status": "error", "output": None, "error": "crash", "retries": 0},
        }
        history = [_make_error(node_results=node_results_err) for _ in range(5)]
        result = scorer.score_from_executions(history)

        assert result.error_rate.score == pytest.approx(0.0)
        assert len(result.error_rate.issues) >= 1

    def test_issues_list_populated_for_problem_nodes(self, scorer):
        """Nodes with >10% error rate appear in issues."""
        ok_nodes = {
            "agent-1": {"status": "success", "output": {"r": 1}, "retries": 0},
            "agent-bad": {"status": "error", "output": None, "error": "fail", "retries": 0},
        }
        history = [_make_success(node_results=ok_nodes) for _ in range(4)]
        result = scorer.score_from_executions(history)

        issue_text = " ".join(result.error_rate.issues)
        assert "agent-bad" in issue_text


# ---------------------------------------------------------------------------
# 5. Retry effectiveness
# ---------------------------------------------------------------------------


class TestRetryEffectiveness:
    """Retry effectiveness: of retried nodes, what fraction eventually succeeded."""

    def test_no_retries_needed(self, scorer):
        """Zero retries observed -> default score 0.7."""
        node_results = {
            "agent-1": {"status": "success", "output": {"v": 1}, "retries": 0},
        }
        history = [_make_success(node_results=node_results) for _ in range(5)]
        result = scorer.score_from_executions(history)

        assert result.retry_effectiveness.score == pytest.approx(0.7)
        assert result.retry_effectiveness.evidence.get("retried") == 0

    def test_all_retries_succeed(self, scorer):
        """Every retried node eventually succeeds -> score 1.0."""
        node_results = {
            "agent-1": {"status": "success", "output": {"v": 1}, "retries": 2},
            "agent-2": {"status": "success", "output": {"v": 2}, "retries": 1},
        }
        history = [_make_success(node_results=node_results) for _ in range(4)]
        result = scorer.score_from_executions(history)

        assert result.retry_effectiveness.score == pytest.approx(1.0)
        assert result.retry_effectiveness.issues == []

    def test_retries_always_fail(self, scorer):
        """Every retried node still fails -> score 0.0."""
        node_results = {
            "agent-1": {
                "status": "error",
                "output": None,
                "error": "persistent failure",
                "retries": 3,
            },
        }
        history = [_make_error(node_results=node_results) for _ in range(5)]
        result = scorer.score_from_executions(history)

        assert result.retry_effectiveness.score == pytest.approx(0.0)
        assert len(result.retry_effectiveness.issues) >= 1
        assert "rarely help" in result.retry_effectiveness.issues[0].lower() or \
               "Retries rarely help" in result.retry_effectiveness.issues[0]


# ---------------------------------------------------------------------------
# 6. Latency health
# ---------------------------------------------------------------------------


class TestLatencyHealth:
    """Latency health based on p95/median ratio."""

    def test_uniform_latency_high_score(self, scorer):
        """All durations roughly the same -> score 0.9 (ratio < 2)."""
        history = [_make_success(duration_ms=d) for d in [1000, 1050, 980, 1020, 990, 1010, 1000, 1030]]
        result = scorer.score_from_executions(history)

        assert result.latency_health.score == pytest.approx(0.9)
        assert result.latency_health.issues == []

    def test_severe_spikes_low_score(self, scorer):
        """p95 > 5x median -> score 0.3."""
        # 19 executions at ~1000ms, 1 at 20000ms so p95 sits at 20000ms
        durations = [1000] * 19 + [20000]
        history = [_make_success(duration_ms=d) for d in durations]
        result = scorer.score_from_executions(history)

        assert result.latency_health.score == pytest.approx(0.3)
        assert len(result.latency_health.issues) >= 1
        assert "Severe" in result.latency_health.issues[0]

    def test_moderate_spikes_middle_score(self, scorer):
        """p95/median ratio between 3 and 5 -> score 0.5."""
        # 17 at 1000ms, 3 at 4000ms -> p95 = 4000, median ~ 1000, ratio ~ 4
        durations = [1000] * 17 + [4000] * 3
        history = [_make_success(duration_ms=d) for d in durations]
        result = scorer.score_from_executions(history)

        assert result.latency_health.score == pytest.approx(0.5)
        assert len(result.latency_health.issues) >= 1
        assert "spikes" in result.latency_health.issues[0].lower()


# ---------------------------------------------------------------------------
# 7. Overall blending
# ---------------------------------------------------------------------------


class TestOverallBlending:
    """The overall_score must equal the weighted average of all five dimensions."""

    WEIGHTS = [0.3, 0.2, 0.2, 0.15, 0.15]

    def test_weighted_average_computed_correctly(self, scorer):
        """Manually verify the weighted combination."""
        # Build a history that yields predictable dimension scores:
        # - all success (success_rate = 1.0)
        # - consistent outputs (output_consistency = 1.0)
        # - no node errors (error_rate = 1.0)
        # - no retries needed (retry_effectiveness = 0.7)
        # - uniform latency (latency_health = 0.9)
        node_results = {
            "agent-1": {
                "status": "success",
                "output": {"result": "ok", "confidence": 0.95},
                "retries": 0,
            },
        }
        history = [_make_success(duration_ms=1000, node_results=node_results) for _ in range(10)]
        result = scorer.score_from_executions(history)

        expected = (
            1.0 * 0.3    # success_rate
            + 1.0 * 0.2  # output_consistency
            + 1.0 * 0.2  # error_rate
            + 0.7 * 0.15 # retry_effectiveness (no retries -> 0.7)
            + 0.9 * 0.15 # latency_health (uniform -> 0.9)
        )

        assert result.overall_score == pytest.approx(expected, abs=1e-9)

    def test_total_executions_matches(self, scorer):
        """total_executions equals the max sample_count across dimensions."""
        history = [_make_success() for _ in range(7)] + [_make_error() for _ in range(3)]
        result = scorer.score_from_executions(history)

        assert result.total_executions == 10

    def test_all_zeros_give_zero_overall(self, scorer):
        """Empty history produces 0.0 overall via _empty_scores."""
        result = scorer.score_from_executions([])

        assert result.overall_score == pytest.approx(0.0)
        assert result.total_executions == 0
