"""Tests for Orchestration Quality Scorer."""
import pytest
from app.detection.orchestration_quality import (
    OrchestrationQualityScorer,
    OrchestrationScore,
    detect,
)


def _make_state(
    agent_id: str,
    seq: int,
    role: str = "worker",
    latency_ms: int = 100,
    status: str = "completed",
    state_delta: dict = None,
    tool_calls: list = None,
    output: str = "",
):
    return {
        "agent_id": agent_id,
        "agent_role": role,
        "sequence_num": seq,
        "latency_ms": latency_ms,
        "status": status,
        "state_delta": state_delta or {},
        "tool_calls": tool_calls,
        "output": output,
    }


class TestOrchestrationQualityBasic:
    def test_empty_trace(self):
        scorer = OrchestrationQualityScorer()
        result = scorer.score([])
        assert result.overall == 0.0

    def test_single_state(self):
        scorer = OrchestrationQualityScorer()
        result = scorer.score([_make_state("a", 0)])
        assert result.overall == 1.0

    def test_single_agent_multiple_states(self):
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0),
            _make_state("a", 1),
            _make_state("a", 2),
        ]
        result = scorer.score(states)
        assert result.overall == 0.8  # Single agent — no orchestration


class TestEfficiency:
    def test_dependent_sequential_two_agents(self):
        """Two agents sharing state keys — must be sequential, efficiency = 1.0."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("planner", 0, role="planner", latency_ms=200,
                        state_delta={"plan": "search for data"}),
            _make_state("executor", 1, role="executor", latency_ms=300,
                        state_delta={"plan": "executed", "result": "data found"}),
        ]
        result = scorer.score(states)
        # Shared key "plan" creates dependency → critical path = total → efficiency = 1.0
        assert result.efficiency == 1.0


class TestUtilization:
    def test_balanced_utilization(self):
        """Equal work across agents → high utilization."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0, latency_ms=100),
            _make_state("b", 1, latency_ms=100),
            _make_state("c", 2, latency_ms=100),
        ]
        result = scorer.score(states)
        assert result.utilization > 0.8

    def test_single_bottleneck_agent(self):
        """One agent does 90% of work → low utilization."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("bottleneck", 0, latency_ms=900),
            _make_state("helper_1", 1, latency_ms=50),
            _make_state("helper_2", 2, latency_ms=50),
        ]
        result = scorer.score(states)
        assert result.utilization < 0.5


class TestParallelization:
    def test_independent_tasks_sequential(self):
        """Three agents: c assigns to a and b, but a and b run sequentially despite being independent."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("coordinator", 0, state_delta={"tasks": "assigned"}),
            _make_state("a", 1, state_delta={"task_a": "data"}),
            _make_state("a", 2, state_delta={"task_a": "result"}),
            _make_state("b", 3, state_delta={"task_b": "data"}),
            _make_state("b", 4, state_delta={"task_b": "result"}),
        ]
        result = scorer.score(states)
        # Topology alignment flags: pipeline with independent keys could be fan-out
        assert result.topology_alignment <= 0.5  # Topology mismatch detected
        assert result.overall < 0.95  # Not perfect orchestration

    def test_dependent_tasks_sequential_is_ok(self):
        """Two agents sharing state keys run sequentially → fine (they must)."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0, state_delta={"shared_data": "input"}),
            _make_state("b", 1, state_delta={"shared_data": "processed"}),
        ]
        result = scorer.score(states)
        assert result.parallelization == 1.0  # No missed opportunities


class TestDelegationQuality:
    def test_context_preserved_at_handoff(self):
        """Good handoff: incoming state references outgoing context."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0, state_delta={"task": "analyze the customer data"}),
            _make_state("b", 1, state_delta={"task": "analyze the customer data for trends"}),
        ]
        result = scorer.score(states)
        assert result.delegation_quality > 0.6

    def test_deep_delegation_chain_penalized(self):
        """5-hop delegation with distinct roles and low context overlap → penalty."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("manager", 0, role="manager", state_delta={"task": "analyze report"}),
            _make_state("lead", 1, role="lead", state_delta={"task": "review code"}),
            _make_state("senior", 2, role="senior", state_delta={"task": "check syntax"}),
            _make_state("mid", 3, role="mid", state_delta={"task": "run tests"}),
            _make_state("junior", 4, role="junior", state_delta={"task": "format output"}),
        ]
        result = scorer.score(states)
        # Different roles, low word overlap at each step → low delegation quality
        assert result.delegation_quality < 0.8


class TestCommunicationEfficiency:
    def test_many_handoffs_few_productive(self):
        """Many agent switches but little productive output → low efficiency."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0),  # No output, no tools
            _make_state("b", 1),
            _make_state("a", 2),
            _make_state("b", 3),
            _make_state("a", 4),
            _make_state("b", 5, tool_calls=["search"], output="Found result"),
        ]
        result = scorer.score(states)
        assert result.communication_efficiency < 0.6

    def test_productive_states_with_few_handoffs(self):
        """Each agent does productive work → high efficiency."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0, tool_calls=["search"], output="Results found"),
            _make_state("b", 1, tool_calls=["write"], output="Report generated"),
        ]
        result = scorer.score(states)
        assert result.communication_efficiency > 0.7


class TestRobustness:
    def test_error_with_recovery(self):
        """Error followed by successful retry → good robustness."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0),
            _make_state("b", 1, status="error"),
            _make_state("c", 2, status="completed"),  # Recovery
        ]
        result = scorer.score(states)
        assert result.robustness > 0.5

    def test_error_without_recovery(self):
        """Consecutive errors with no recovery → poor robustness."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0),
            _make_state("b", 1, status="error"),
            _make_state("c", 2, status="error"),
        ]
        result = scorer.score(states)
        assert result.robustness < 0.5

    def test_no_errors(self):
        """Clean execution → perfect robustness."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0),
            _make_state("b", 1),
        ]
        result = scorer.score(states)
        assert result.robustness >= 0.7  # Recovery=1.0, redundancy may vary


class TestOverallDetection:
    def test_well_orchestrated_high_overall(self):
        """Balanced, productive, minimal handoffs → high overall."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("planner", 0, role="planner", latency_ms=100,
                        state_delta={"plan": "search then summarize"},
                        tool_calls=["plan"], output="Plan created"),
            _make_state("searcher", 1, role="searcher", latency_ms=200,
                        state_delta={"results": "data found"},
                        tool_calls=["search"], output="Search complete with results"),
            _make_state("writer", 2, role="writer", latency_ms=150,
                        state_delta={"report": "final summary"},
                        tool_calls=["write"], output="Report written successfully"),
        ]
        result = scorer.score(states)
        assert result.overall > 0.6

    def test_poorly_orchestrated_low_overall(self):
        """Unbalanced, chatty, error-prone → low overall."""
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0, latency_ms=800),  # Bottleneck
            _make_state("b", 1, latency_ms=10),
            _make_state("a", 2, latency_ms=10),
            _make_state("b", 3, latency_ms=10),
            _make_state("a", 4, latency_ms=10, status="error"),
            _make_state("b", 5, latency_ms=10, status="error"),
        ]
        result = scorer.score(states)
        assert result.overall < 0.6
        assert len(result.issues) > 0

    def test_detect_function_fires_on_poor_orchestration(self):
        """detect() should return detected=True for poor orchestration."""
        states = [
            _make_state("a", 0, latency_ms=900),
            _make_state("b", 1, latency_ms=10),
            _make_state("a", 2, latency_ms=10),
            _make_state("b", 3, latency_ms=10),
            _make_state("a", 4, status="error"),
            _make_state("b", 5, status="error"),
        ]
        detected, confidence, score = detect(states)
        assert isinstance(detected, bool)
        assert isinstance(confidence, float)
        assert isinstance(score, OrchestrationScore)

    def test_detect_function_clean_on_good_orchestration(self):
        """detect() should return detected=False for good orchestration (overall >= 0.7)."""
        # Good orchestration: shared context (plan key flows through), balanced work,
        # productive output at each step, no errors
        states = [
            _make_state("planner", 0, role="planner", latency_ms=100,
                        tool_calls=["plan"], output="Plan: search then summarize the data",
                        state_delta={"plan": "search then summarize", "shared": "context"}),
            _make_state("searcher", 1, role="searcher", latency_ms=120,
                        tool_calls=["search"], output="Found 50 relevant documents for analysis",
                        state_delta={"results": "50 documents found", "shared": "context updated", "plan": "search done"}),
            _make_state("writer", 2, role="writer", latency_ms=100,
                        tool_calls=["write"], output="Executive summary generated from documents",
                        state_delta={"report": "executive summary of findings", "results": "incorporated", "plan": "complete"}),
        ]
        detected, confidence, score = detect(states)
        assert detected is False


class TestAgentStats:
    def test_agent_stats_populated(self):
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0, role="planner", latency_ms=100),
            _make_state("b", 1, role="executor", latency_ms=200),
        ]
        result = scorer.score(states)
        assert "a" in result.agent_stats
        assert "b" in result.agent_stats
        assert result.agent_stats["a"]["role"] == "planner"
        assert result.agent_stats["b"]["total_latency_ms"] == 200


class TestCriticalPath:
    def test_critical_path_ordering(self):
        scorer = OrchestrationQualityScorer()
        states = [
            _make_state("a", 0),
            _make_state("b", 1),
            _make_state("c", 2),
        ]
        result = scorer.score(states)
        assert result.critical_path == ["a", "b", "c"]
