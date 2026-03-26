"""Tests for Multi-Chain Interaction Analyzer."""
import pytest
from app.detection.multi_chain import (
    MultiChainAnalyzer,
    TraceGraph,
    TraceNode,
    TraceEdge,
    build_trace_graph,
    detect,
)


def _make_trace(
    trace_id: str,
    detection_types: list = None,
    status: str = "completed",
    first_state_delta: dict = None,
    last_state_delta: dict = None,
    agent_ids: list = None,
):
    return TraceNode(
        trace_id=trace_id,
        session_id="session-1",
        framework="n8n",
        status=status,
        detection_types=detection_types or [],
        state_count=3,
        agent_ids=agent_ids or ["agent-1"],
        first_state_delta=first_state_delta or {},
        last_state_delta=last_state_delta or {},
    )


def _make_graph(traces, edges):
    g = TraceGraph()
    for t in traces:
        g.nodes[t.trace_id] = t
    g.edges = edges
    child_ids = {e.child_trace_id for e in edges}
    g.roots = [tid for tid in g.nodes if tid not in child_ids]
    return g


class TestCascadeFailure:
    def test_corruption_causes_hallucination(self):
        """Parent corruption → child hallucination = cascade."""
        graph = _make_graph(
            traces=[
                _make_trace("t1", detection_types=["corruption"]),
                _make_trace("t2", detection_types=["hallucination"]),
            ],
            edges=[TraceEdge("t1", "t2", "execute_workflow")],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        assert result.detected
        cascades = [i for i in result.issues if i.issue_type == "cascade_failure"]
        assert len(cascades) >= 1
        assert cascades[0].severity == "severe"

    def test_unrelated_failures_no_cascade(self):
        """Parent loop + child injection — not a known cascade pair."""
        graph = _make_graph(
            traces=[
                _make_trace("t1", detection_types=["loop"]),
                _make_trace("t2", detection_types=["injection"]),
            ],
            edges=[TraceEdge("t1", "t2", "execute_workflow")],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        cascades = [i for i in result.issues if i.issue_type == "cascade_failure"]
        assert len(cascades) == 0

    def test_no_failures_no_cascade(self):
        """Both traces clean → no cascade."""
        graph = _make_graph(
            traces=[
                _make_trace("t1", detection_types=[]),
                _make_trace("t2", detection_types=[]),
            ],
            edges=[TraceEdge("t1", "t2", "execute_workflow")],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        assert not result.detected

    def test_multi_hop_cascade(self):
        """A → B → C cascade chain."""
        graph = _make_graph(
            traces=[
                _make_trace("t1", detection_types=["corruption"]),
                _make_trace("t2", detection_types=["hallucination"]),
                _make_trace("t3", detection_types=["specification"]),
            ],
            edges=[
                TraceEdge("t1", "t2", "execute_workflow"),
                TraceEdge("t2", "t3", "execute_workflow"),
            ],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        cascades = [i for i in result.issues if i.issue_type == "cascade_failure"]
        # t1→t2 (corruption→hallucination) and t2→t3 (hallucination→specification)
        assert len(cascades) >= 2


class TestDataCorruptionPropagation:
    def test_shared_key_value_change(self):
        """Parent output key differs from child input key → corruption propagation."""
        graph = _make_graph(
            traces=[
                _make_trace("t1", last_state_delta={"result": "42", "name": "Alice"}),
                _make_trace("t2", first_state_delta={"result": "99", "name": "Alice"}),
            ],
            edges=[TraceEdge("t1", "t2", "execute_workflow")],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        corruptions = [i for i in result.issues if i.issue_type == "data_corruption_propagation"]
        assert len(corruptions) == 1
        assert "result" in corruptions[0].evidence["corrupted_keys"]

    def test_no_shared_keys_no_corruption(self):
        """Different keys → no corruption detected."""
        graph = _make_graph(
            traces=[
                _make_trace("t1", last_state_delta={"output_a": "value"}),
                _make_trace("t2", first_state_delta={"input_b": "value"}),
            ],
            edges=[TraceEdge("t1", "t2", "execute_workflow")],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        corruptions = [i for i in result.issues if i.issue_type == "data_corruption_propagation"]
        assert len(corruptions) == 0

    def test_matching_values_no_corruption(self):
        """Shared keys with same values → no corruption."""
        graph = _make_graph(
            traces=[
                _make_trace("t1", last_state_delta={"result": "42"}),
                _make_trace("t2", first_state_delta={"result": "42"}),
            ],
            edges=[TraceEdge("t1", "t2", "execute_workflow")],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        corruptions = [i for i in result.issues if i.issue_type == "data_corruption_propagation"]
        assert len(corruptions) == 0


class TestCrossChainLoops:
    def test_ab_ba_loop(self):
        """A → B → A cycle detected."""
        graph = _make_graph(
            traces=[
                _make_trace("t1"),
                _make_trace("t2"),
            ],
            edges=[
                TraceEdge("t1", "t2", "execute_workflow"),
                TraceEdge("t2", "t1", "execute_workflow"),
            ],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        loops = [i for i in result.issues if i.issue_type == "cross_chain_loop"]
        assert len(loops) >= 1
        assert loops[0].severity == "severe"

    def test_abc_ca_loop(self):
        """A → B → C → A cycle."""
        graph = _make_graph(
            traces=[_make_trace("t1"), _make_trace("t2"), _make_trace("t3")],
            edges=[
                TraceEdge("t1", "t2", "subgraph"),
                TraceEdge("t2", "t3", "subgraph"),
                TraceEdge("t3", "t1", "subgraph"),
            ],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        loops = [i for i in result.issues if i.issue_type == "cross_chain_loop"]
        assert len(loops) >= 1

    def test_no_loop_in_dag(self):
        """Clean DAG → no loops."""
        graph = _make_graph(
            traces=[_make_trace("t1"), _make_trace("t2"), _make_trace("t3")],
            edges=[
                TraceEdge("t1", "t2", "execute_workflow"),
                TraceEdge("t1", "t3", "execute_workflow"),
            ],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        loops = [i for i in result.issues if i.issue_type == "cross_chain_loop"]
        assert len(loops) == 0


class TestRedundantWork:
    def test_siblings_with_overlapping_input(self):
        """Two children of same parent with 80%+ overlapping input."""
        graph = _make_graph(
            traces=[
                _make_trace("parent"),
                _make_trace("child1", first_state_delta={
                    "task": "analyze the customer revenue data from Q1 2025",
                    "context": "enterprise sales pipeline metrics"
                }),
                _make_trace("child2", first_state_delta={
                    "task": "analyze the customer revenue data from Q1 2025",
                    "context": "enterprise sales pipeline metrics and trends"
                }),
            ],
            edges=[
                TraceEdge("parent", "child1", "execute_workflow"),
                TraceEdge("parent", "child2", "execute_workflow"),
            ],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        redundant = [i for i in result.issues if i.issue_type == "redundant_work"]
        assert len(redundant) >= 1

    def test_siblings_with_different_input(self):
        """Two children with different tasks → not redundant."""
        graph = _make_graph(
            traces=[
                _make_trace("parent"),
                _make_trace("child1", first_state_delta={
                    "task": "search for customer data",
                }),
                _make_trace("child2", first_state_delta={
                    "task": "generate the quarterly report",
                }),
            ],
            edges=[
                TraceEdge("parent", "child1", "execute_workflow"),
                TraceEdge("parent", "child2", "execute_workflow"),
            ],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        redundant = [i for i in result.issues if i.issue_type == "redundant_work"]
        assert len(redundant) == 0


class TestBuildTraceGraph:
    def test_build_from_dicts(self):
        """build_trace_graph correctly builds graph from raw dicts."""
        graph = build_trace_graph(
            traces=[
                {"trace_id": "t1", "status": "completed", "detection_types": ["loop"]},
                {"trace_id": "t2", "status": "failed", "detection_types": ["timeout"]},
            ],
            links=[
                {"parent_trace_id": "t1", "child_trace_id": "t2", "link_type": "execute_workflow"},
            ],
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.roots == ["t1"]
        assert graph.nodes["t1"].detection_types == ["loop"]

    def test_multiple_roots(self):
        """Graph with no links → all traces are roots."""
        graph = build_trace_graph(
            traces=[
                {"trace_id": "t1"},
                {"trace_id": "t2"},
            ],
            links=[],
        )
        assert set(graph.roots) == {"t1", "t2"}


class TestDetectFunction:
    def test_detect_returns_tuple(self):
        """detect() returns (bool, float, result) tuple."""
        detected, confidence, result = detect(
            traces=[
                {"trace_id": "t1", "detection_types": ["corruption"],
                 "last_state_delta": {"data": "original"}},
                {"trace_id": "t2", "detection_types": ["hallucination"],
                 "first_state_delta": {"data": "corrupted"}},
            ],
            links=[
                {"parent_trace_id": "t1", "child_trace_id": "t2", "link_type": "execute_workflow"},
            ],
        )
        assert isinstance(detected, bool)
        assert isinstance(confidence, float)
        assert detected  # cascade + corruption propagation

    def test_single_trace_not_detected(self):
        """Single trace → no multi-chain analysis possible."""
        detected, confidence, result = detect(
            traces=[{"trace_id": "t1"}],
            links=[],
        )
        assert not detected
        assert confidence == 0.0


class TestEdgeCases:
    def test_empty_graph(self):
        graph = TraceGraph()
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        assert not result.detected

    def test_nodes_without_edges(self):
        """Multiple traces but no links → no issues."""
        graph = _make_graph(
            traces=[_make_trace("t1"), _make_trace("t2")],
            edges=[],
        )
        analyzer = MultiChainAnalyzer()
        result = analyzer.analyze(graph)
        assert not result.detected
