"""Multi-Chain Interaction Analyzer — Cross-Trace Failure Detection.

Detects failure patterns that span multiple agent chains/pipelines:

1. Cascade failures: upstream error propagates to downstream chain
2. Data corruption propagation: bad output corrupts next chain's input
3. Cross-chain loops: Chain A → Chain B → Chain A
4. Redundant work: parallel chains duplicating effort

Improvements based on:
- A2P Framework (Sept 2025): Causal inference for failure attribution
- RCAEval (WWW 2025): Temporal knowledge graphs, multi-source RCA
- Microservices cascade detection: Temporal causality, probabilistic scoring
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Fix 7: Weighted CASCADE_PAIRS — stronger pairs get higher weight
CASCADE_PAIRS_WEIGHTED: Dict[str, Dict[str, float]] = {
    "corruption": {"hallucination": 0.9, "context": 0.8, "corruption": 0.95, "specification": 0.6},
    "hallucination": {"hallucination": 0.8, "grounding": 0.85, "specification": 0.4},
    "timeout": {"context": 0.8, "completion": 0.7, "overflow": 0.9},
    "overflow": {"context": 0.7, "completion": 0.6, "derailment": 0.5},
    "loop": {"timeout": 0.85, "overflow": 0.8, "completion": 0.7},
    "injection": {"derailment": 0.9, "persona_drift": 0.7, "hallucination": 0.6},
    "derailment": {"specification": 0.6, "completion": 0.5, "derailment": 0.7},
    "n8n_timeout": {"n8n_timeout": 0.9, "completion": 0.6, "context": 0.7},
    "n8n_error": {"n8n_error": 0.9, "corruption": 0.7, "completion": 0.6},
}

# Fallback: any error-type parent can weakly cascade to these
FALLBACK_CASCADE_TARGETS = {"context", "completion", "overflow"}
FALLBACK_CASCADE_WEIGHT = 0.3


@dataclass
class TraceNode:
    """A trace in the multi-chain graph."""
    trace_id: str
    session_id: str = ""
    framework: str = ""
    status: str = "completed"
    detection_types: List[str] = field(default_factory=list)
    state_count: int = 0
    agent_ids: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    first_state_delta: Dict[str, Any] = field(default_factory=dict)
    last_state_delta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceEdge:
    """Link between parent and child traces."""
    parent_trace_id: str
    child_trace_id: str
    link_type: str = "unknown"


@dataclass
class TraceGraph:
    """DAG of linked traces."""
    nodes: Dict[str, TraceNode] = field(default_factory=dict)
    edges: List[TraceEdge] = field(default_factory=list)
    roots: List[str] = field(default_factory=list)


@dataclass
class MultiChainIssue:
    """A detected cross-chain issue."""
    issue_type: str
    description: str
    severity: str = "moderate"
    affected_traces: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiChainAnalysisResult:
    """Result of multi-chain analysis."""
    detected: bool
    confidence: float
    issues: List[MultiChainIssue] = field(default_factory=list)
    trace_graph: Optional[TraceGraph] = None
    explanation: str = ""


class MultiChainAnalyzer:
    """Analyzes interactions and failure propagation across linked traces."""

    def analyze(self, trace_graph: TraceGraph) -> MultiChainAnalysisResult:
        """Run all cross-chain detections on a trace graph."""
        if not trace_graph.nodes or len(trace_graph.nodes) < 2:
            return MultiChainAnalysisResult(
                detected=False, confidence=0.0, trace_graph=trace_graph,
                explanation="Fewer than 2 traces — no cross-chain analysis possible",
            )

        issues = []
        issues.extend(self._detect_cascade_failures(trace_graph))
        issues.extend(self._detect_data_corruption_propagation(trace_graph))
        issues.extend(self._detect_cross_chain_loops(trace_graph))
        issues.extend(self._detect_redundant_work(trace_graph))

        detected = len(issues) > 0
        if not issues:
            confidence = 0.0
        else:
            # Fix 10: Use max issue confidence, not just severity lookup
            issue_confidences = []
            for i in issues:
                base = {"minor": 0.4, "moderate": 0.7, "severe": 0.9}.get(i.severity, 0.5)
                # If evidence has cascade_weight, use it
                cascade_w = i.evidence.get("cascade_weight", 1.0)
                issue_confidences.append(base * cascade_w)
            confidence = max(issue_confidences)

        explanation_parts = [f"{i.issue_type}: {i.description}" for i in issues[:5]]
        explanation = "; ".join(explanation_parts) if explanation_parts else "No cross-chain issues found"

        return MultiChainAnalysisResult(
            detected=detected, confidence=round(confidence, 4),
            issues=issues, trace_graph=trace_graph, explanation=explanation,
        )

    # ── Fix 6 + 7 + 10: Temporal Causality + Weighted Cascades ───────

    def _detect_cascade_failures(self, graph: TraceGraph) -> List[MultiChainIssue]:
        """Detect cascade failures with temporal causality and probabilistic weighting."""
        issues = []

        children_of: Dict[str, List[str]] = defaultdict(list)
        for edge in graph.edges:
            children_of[edge.parent_trace_id].append(edge.child_trace_id)

        for parent_id, child_ids in children_of.items():
            parent = graph.nodes.get(parent_id)
            if not parent or not parent.detection_types:
                continue

            for child_id in child_ids:
                child = graph.nodes.get(child_id)
                if not child or not child.detection_types:
                    continue

                # Fix 6: Temporal causality gate
                if not self._temporal_causality_valid(parent, child):
                    continue

                for p_det in parent.detection_types:
                    # Fix 7: Weighted cascade pairs + fallback
                    known_effects = CASCADE_PAIRS_WEIGHTED.get(p_det, {})

                    for c_det in child.detection_types:
                        weight = known_effects.get(c_det, 0.0)

                        # Fallback: unknown parent type can weakly cascade
                        if weight == 0.0 and c_det in FALLBACK_CASCADE_TARGETS:
                            weight = FALLBACK_CASCADE_WEIGHT

                        if weight > 0.0:
                            issues.append(MultiChainIssue(
                                issue_type="cascade_failure",
                                description=(
                                    f"{p_det} in trace {parent_id[:8]} cascaded to "
                                    f"{c_det} in child trace {child_id[:8]} "
                                    f"(weight={weight:.1f})"
                                ),
                                severity="severe" if weight > 0.7 else "moderate" if weight > 0.4 else "minor",
                                affected_traces=[parent_id, child_id],
                                evidence={
                                    "parent_detection": p_det,
                                    "child_detection": c_det,
                                    "cascade_weight": weight,
                                    "link_type": next(
                                        (e.link_type for e in graph.edges
                                         if e.parent_trace_id == parent_id and e.child_trace_id == child_id),
                                        "unknown",
                                    ),
                                },
                            ))

        return issues

    @staticmethod
    def _temporal_causality_valid(parent: TraceNode, child: TraceNode) -> bool:
        """Check that parent completed before child started (temporal causality).

        Returns True if causality is valid or timestamps are unavailable.
        """
        if not parent.completed_at or not child.created_at:
            return True  # No timestamps → can't disprove causality
        try:
            p_time = datetime.fromisoformat(str(parent.completed_at).replace("Z", "+00:00"))
            c_time = datetime.fromisoformat(str(child.created_at).replace("Z", "+00:00"))
            # Parent must finish before child starts for cascade
            return p_time <= c_time
        except (ValueError, TypeError):
            return True  # Parse error → can't disprove

    # ── Fix 8 + 9: Semantic Data Corruption Detection ────────────────

    def _detect_data_corruption_propagation(self, graph: TraceGraph) -> List[MultiChainIssue]:
        """Detect data corruption with semantic comparison and volume scoring."""
        issues = []

        for edge in graph.edges:
            parent = graph.nodes.get(edge.parent_trace_id)
            child = graph.nodes.get(edge.child_trace_id)
            if not parent or not child:
                continue

            parent_out = parent.last_state_delta
            child_in = child.first_state_delta
            if not parent_out or not child_in:
                continue

            shared_keys = set(parent_out.keys()) & set(child_in.keys())
            corrupted_keys = []

            for key in shared_keys:
                p_val = str(parent_out[key])
                c_val = str(child_in[key])

                if not p_val or not c_val:
                    continue

                # Exact match → not corrupted
                if p_val == c_val:
                    continue

                # Case-insensitive match → not corrupted
                if p_val.strip().lower() == c_val.strip().lower():
                    continue

                # Fix 8a: Numeric equivalence check
                if _numeric_equal(p_val, c_val):
                    continue

                # Fix 8b: Fuzzy string match — high similarity = formatting, not corruption
                similarity = SequenceMatcher(None, p_val.lower(), c_val.lower()).ratio()
                if similarity > 0.9:
                    continue  # Just formatting differences

                corrupted_keys.append(key)

            if corrupted_keys:
                # Fix 9: Data flow volume scoring
                total_keys = max(len(parent_out), len(child_in), 1)
                corrupted_ratio = len(corrupted_keys) / max(len(shared_keys), 1)
                data_flow_ratio = len(shared_keys) / total_keys

                if data_flow_ratio < 0.1:
                    severity = "minor"  # Very little data shared
                elif corrupted_ratio > 0.5:
                    severity = "severe"
                elif corrupted_ratio > 0.2:
                    severity = "moderate"
                else:
                    severity = "minor"

                issues.append(MultiChainIssue(
                    issue_type="data_corruption_propagation",
                    description=(
                        f"Data corrupted between trace {edge.parent_trace_id[:8]} "
                        f"and {edge.child_trace_id[:8]}: keys {corrupted_keys} "
                        f"({corrupted_ratio:.0%} of shared data)"
                    ),
                    severity=severity,
                    affected_traces=[edge.parent_trace_id, edge.child_trace_id],
                    evidence={
                        "corrupted_keys": corrupted_keys,
                        "corrupted_ratio": round(corrupted_ratio, 3),
                        "data_flow_ratio": round(data_flow_ratio, 3),
                        "parent_values": {k: str(parent_out[k])[:100] for k in corrupted_keys},
                        "child_values": {k: str(child_in[k])[:100] for k in corrupted_keys},
                    },
                ))

        return issues

    # ── Cross-Chain Loop Detection (unchanged, works well) ───────────

    def _detect_cross_chain_loops(self, graph: TraceGraph) -> List[MultiChainIssue]:
        """Detect cycles in the trace graph using DFS."""
        issues = []
        adj: Dict[str, List[str]] = defaultdict(list)
        for edge in graph.edges:
            adj[edge.parent_trace_id].append(edge.child_trace_id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {tid: WHITE for tid in graph.nodes}

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            color[node] = GRAY
            for neighbor in adj.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    cycle_start = path.index(neighbor) if neighbor in path else -1
                    if cycle_start >= 0:
                        return path[cycle_start:] + [neighbor]
                    return [neighbor, node, neighbor]
                elif color[neighbor] == WHITE:
                    result = dfs(neighbor, path + [neighbor])
                    if result:
                        return result
            color[node] = BLACK
            return None

        for tid in graph.nodes:
            if color.get(tid) == WHITE:
                cycle = dfs(tid, [tid])
                if cycle:
                    issues.append(MultiChainIssue(
                        issue_type="cross_chain_loop",
                        description=f"Trace loop detected: {' → '.join(t[:8] for t in cycle)}",
                        severity="severe",
                        affected_traces=list(set(cycle)),
                        evidence={"cycle": cycle},
                    ))
                    break

        return issues

    # ── Redundant Work Detection (unchanged, works well) ─────────────

    def _detect_redundant_work(self, graph: TraceGraph) -> List[MultiChainIssue]:
        """Detect sibling traces doing overlapping work."""
        issues = []
        siblings: Dict[str, List[str]] = defaultdict(list)
        for edge in graph.edges:
            siblings[edge.parent_trace_id].append(edge.child_trace_id)

        for parent_id, child_ids in siblings.items():
            if len(child_ids) < 2:
                continue
            for i in range(len(child_ids)):
                for j in range(i + 1, len(child_ids)):
                    t1 = graph.nodes.get(child_ids[i])
                    t2 = graph.nodes.get(child_ids[j])
                    if not t1 or not t2:
                        continue
                    t1_text = _dict_to_words(t1.first_state_delta)
                    t2_text = _dict_to_words(t2.first_state_delta)
                    if not t1_text or not t2_text:
                        continue
                    overlap = len(t1_text & t2_text) / max(min(len(t1_text), len(t2_text)), 1)
                    if overlap > 0.9:
                        issues.append(MultiChainIssue(
                            issue_type="redundant_work",
                            description=(
                                f"Sibling traces {child_ids[i][:8]} and {child_ids[j][:8]} "
                                f"have {overlap:.0%} input overlap (parent: {parent_id[:8]})"
                            ),
                            severity="moderate",
                            affected_traces=[parent_id, child_ids[i], child_ids[j]],
                            evidence={"overlap_ratio": round(overlap, 3), "shared_words": list(t1_text & t2_text)[:20]},
                        ))
        return issues


def _dict_to_words(d: Dict[str, Any]) -> Set[str]:
    """Extract word set from a dict's string values.

    Includes 2-char words to capture region codes (US, EU) and short identifiers
    that distinguish otherwise-identical tasks.
    """
    words = set()
    for v in d.values():
        text = str(v) if not isinstance(v, str) else v
        words.update(w.lower() for w in text.split() if len(w) >= 2)
    return words


def _numeric_equal(a: str, b: str) -> bool:
    """Check if two string values are numerically equivalent."""
    try:
        return float(a) == float(b)
    except (ValueError, TypeError):
        return False


def build_trace_graph(traces: List[Dict[str, Any]], links: List[Dict[str, Any]]) -> TraceGraph:
    """Build a TraceGraph from raw trace and link data."""
    graph = TraceGraph()
    for t in traces:
        tid = t.get("trace_id", "")
        graph.nodes[tid] = TraceNode(
            trace_id=tid, session_id=t.get("session_id", ""),
            framework=t.get("framework", ""), status=t.get("status", "completed"),
            detection_types=t.get("detection_types", []),
            state_count=t.get("state_count", 0), agent_ids=t.get("agent_ids", []),
            created_at=t.get("created_at"), completed_at=t.get("completed_at"),
            first_state_delta=t.get("first_state_delta", {}),
            last_state_delta=t.get("last_state_delta", {}),
        )
    child_ids = set()
    for link in links:
        edge = TraceEdge(
            parent_trace_id=link.get("parent_trace_id", ""),
            child_trace_id=link.get("child_trace_id", ""),
            link_type=link.get("link_type", "unknown"),
        )
        graph.edges.append(edge)
        child_ids.add(edge.child_trace_id)
    graph.roots = [tid for tid in graph.nodes if tid not in child_ids]
    return graph


def detect(traces: List[Dict[str, Any]], links: List[Dict[str, Any]]) -> Tuple[bool, float, MultiChainAnalysisResult]:
    """Convenience function for detection pipeline integration."""
    graph = build_trace_graph(traces, links)
    analyzer = MultiChainAnalyzer()
    result = analyzer.analyze(graph)
    return result.detected, result.confidence, result
