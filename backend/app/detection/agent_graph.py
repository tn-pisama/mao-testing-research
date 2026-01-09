"""
Graph-Based Agent Coordination Detection
==========================================

Builds a graph representation of agent interactions to detect:
- F3: Coordination Failure (communication cycles, missed handoffs)
- F9: Role Usurpation (agents acting outside their designated roles)

Based on SentinelAgent research: graph-based analysis with node/edge/path analysis.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .turn_aware import (
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    TurnSnapshot,
    MODULE_VERSION,
)

logger = logging.getLogger(__name__)


class EdgeType(str, Enum):
    """Types of edges in agent interaction graph."""
    MESSAGE = "message"           # Direct message between agents
    HANDOFF = "handoff"           # Task handoff
    DELEGATION = "delegation"     # Task delegation
    RESPONSE = "response"         # Response to a request
    TOOL_CALL = "tool_call"       # Agent calling a tool
    TOOL_RESULT = "tool_result"   # Tool returning result


@dataclass
class AgentNode:
    """Node representing an agent in the interaction graph."""
    id: str
    role: Optional[str] = None
    turn_indices: List[int] = field(default_factory=list)
    message_count: int = 0
    tool_calls: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InteractionEdge:
    """Edge representing an interaction between agents."""
    from_agent: str
    to_agent: str
    edge_type: EdgeType
    turn_index: int
    content_snippet: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CycleInfo:
    """Information about a detected cycle in the graph."""
    agents: List[str]
    turn_indices: List[int]
    cycle_length: int
    is_semantic_repeat: bool = False
    content_samples: List[str] = field(default_factory=list)


@dataclass
class HandoffFailure:
    """Information about a detected handoff failure."""
    from_agent: str
    to_agent: str
    turn_index: int
    failure_type: str  # "no_response", "ignored", "timeout"
    evidence: str = ""


class AgentInteractionGraph:
    """
    Graph representation of agent-to-agent interactions.

    Supports analysis for:
    - Communication cycles (potential infinite loops)
    - Handoff failures (agent A sends to B, B doesn't respond)
    - Role boundary violations
    - Coordination overhead (excessive back-and-forth)
    """

    def __init__(self):
        self.nodes: Dict[str, AgentNode] = {}
        self.edges: List[InteractionEdge] = []
        self._adjacency: Dict[str, List[Tuple[str, InteractionEdge]]] = defaultdict(list)

    def add_agent(self, agent_id: str, role: Optional[str] = None) -> AgentNode:
        """Add or get an agent node."""
        if agent_id not in self.nodes:
            self.nodes[agent_id] = AgentNode(id=agent_id, role=role)
        elif role and not self.nodes[agent_id].role:
            self.nodes[agent_id].role = role
        return self.nodes[agent_id]

    def add_interaction(
        self,
        from_agent: str,
        to_agent: str,
        edge_type: EdgeType,
        turn_index: int,
        content_snippet: str = "",
    ):
        """Add an interaction edge between agents."""
        # Ensure nodes exist
        self.add_agent(from_agent)
        self.add_agent(to_agent)

        # Update node statistics
        self.nodes[from_agent].message_count += 1
        self.nodes[from_agent].turn_indices.append(turn_index)
        if edge_type == EdgeType.TOOL_CALL:
            self.nodes[from_agent].tool_calls += 1

        # Create edge
        edge = InteractionEdge(
            from_agent=from_agent,
            to_agent=to_agent,
            edge_type=edge_type,
            turn_index=turn_index,
            content_snippet=content_snippet[:200],
        )
        self.edges.append(edge)
        self._adjacency[from_agent].append((to_agent, edge))

    def find_cycles(self, min_length: int = 2, max_length: int = 10) -> List[CycleInfo]:
        """
        Find communication cycles in the graph.

        A cycle is a sequence of interactions that returns to the starting agent.
        Cycles indicate potential infinite loops or coordination problems.
        """
        cycles = []
        visited_paths: Set[str] = set()

        def dfs(start: str, current: str, path: List[str], turn_path: List[int], depth: int):
            if depth > max_length:
                return

            for neighbor, edge in self._adjacency.get(current, []):
                new_path = path + [neighbor]
                new_turn_path = turn_path + [edge.turn_index]

                # Found a cycle back to start
                if neighbor == start and len(new_path) >= min_length:
                    # Create canonical path for dedup
                    canonical = "->".join(sorted(new_path))
                    if canonical not in visited_paths:
                        visited_paths.add(canonical)
                        cycles.append(CycleInfo(
                            agents=new_path,
                            turn_indices=new_turn_path,
                            cycle_length=len(new_path),
                            content_samples=[edge.content_snippet for edge in self.edges
                                           if edge.turn_index in new_turn_path][:5],
                        ))

                # Continue DFS
                if neighbor not in path:  # Avoid revisiting in current path
                    dfs(start, neighbor, new_path, new_turn_path, depth + 1)

        # Start DFS from each agent
        for agent_id in self.nodes:
            dfs(agent_id, agent_id, [agent_id], [], 0)

        return cycles

    def find_handoff_failures(self, max_turns_for_response: int = 5) -> List[HandoffFailure]:
        """
        Find failed handoffs where an agent sends a message but gets no response.

        Looks for patterns where:
        - Agent A sends to Agent B
        - Agent B never responds to Agent A within N turns
        """
        failures = []

        # Track pending handoffs
        pending: Dict[Tuple[str, str], InteractionEdge] = {}  # (from, to) -> edge

        for edge in sorted(self.edges, key=lambda e: e.turn_index):
            key = (edge.from_agent, edge.to_agent)
            reverse_key = (edge.to_agent, edge.from_agent)

            # Check if this is a response to a pending handoff
            if reverse_key in pending:
                del pending[reverse_key]

            # Track this as a pending handoff
            if edge.edge_type in (EdgeType.HANDOFF, EdgeType.DELEGATION, EdgeType.MESSAGE):
                pending[key] = edge

        # Any remaining pending are failed handoffs
        for (from_agent, to_agent), edge in pending.items():
            # Check if there's any later response
            has_response = any(
                e.from_agent == to_agent and e.to_agent == from_agent
                for e in self.edges
                if e.turn_index > edge.turn_index
            )

            if not has_response:
                failures.append(HandoffFailure(
                    from_agent=from_agent,
                    to_agent=to_agent,
                    turn_index=edge.turn_index,
                    failure_type="no_response",
                    evidence=f"Agent {from_agent} sent to {to_agent} at turn {edge.turn_index}, no response received",
                ))

        return failures

    def calculate_coordination_overhead(self) -> Dict[str, Any]:
        """
        Calculate metrics about coordination overhead.

        High overhead may indicate inefficient multi-agent coordination.
        """
        if not self.edges:
            return {"overhead_score": 0.0, "details": {}}

        # Count back-and-forth exchanges
        exchanges = defaultdict(int)
        for i, edge in enumerate(self.edges):
            if i > 0:
                prev = self.edges[i - 1]
                if edge.from_agent == prev.to_agent and edge.to_agent == prev.from_agent:
                    pair = tuple(sorted([edge.from_agent, edge.to_agent]))
                    exchanges[pair] += 1

        # Calculate metrics
        total_messages = len(self.edges)
        unique_agents = len(self.nodes)
        back_and_forth = sum(exchanges.values())

        # Overhead score: ratio of back-and-forth to total messages
        overhead_score = back_and_forth / total_messages if total_messages > 0 else 0

        return {
            "overhead_score": overhead_score,
            "total_messages": total_messages,
            "unique_agents": unique_agents,
            "back_and_forth_count": back_and_forth,
            "busiest_pairs": dict(sorted(exchanges.items(), key=lambda x: -x[1])[:5]),
        }


class GraphBasedCoordinationDetector:
    """
    Detector for coordination failures using graph analysis.

    Detects:
    - F3: Agent Coordination Failure (excessive cycles, genuine handoff failures)
    - High coordination overhead

    IMPORTANT: Normal multi-agent workflows have expected interaction patterns:
    - A→B→A dialogue is NORMAL (conversations go back and forth)
    - Programmer→Reviewer→Programmer is NORMAL (code review)
    - Only flag when patterns are EXCESSIVE or CONTRADICTORY
    """

    name = "GraphBasedCoordinationDetector"

    def __init__(
        self,
        min_cycle_length: int = 3,  # Require at least 3-agent cycle
        max_cycle_length: int = 8,
        overhead_threshold: float = 0.7,  # Raised from 0.5 to be more conservative
        min_handoff_failures: int = 5,  # Raised to 5+ to reduce FPR on broadcast-style communication
        min_cycles_to_flag: int = 2,  # Same cycle must repeat 2+ times
    ):
        self.min_cycle_length = min_cycle_length
        self.max_cycle_length = max_cycle_length
        self.overhead_threshold = overhead_threshold
        self.min_handoff_failures = min_handoff_failures
        self.min_cycles_to_flag = min_cycles_to_flag

    def _build_graph(self, snapshots: List[TurnSnapshot]) -> AgentInteractionGraph:
        """Build interaction graph from turn snapshots."""
        graph = AgentInteractionGraph()

        prev_agent: Optional[str] = None

        for i, snapshot in enumerate(snapshots):
            agent_id = snapshot.participant_id or f"agent_{i}"

            # Determine edge type
            if snapshot.participant_type == "tool":
                edge_type = EdgeType.TOOL_RESULT
            elif prev_agent and "handoff" in snapshot.content.lower():
                edge_type = EdgeType.HANDOFF
            elif prev_agent and "delegate" in snapshot.content.lower():
                edge_type = EdgeType.DELEGATION
            else:
                edge_type = EdgeType.MESSAGE

            # Add interaction
            if prev_agent and prev_agent != agent_id:
                graph.add_interaction(
                    from_agent=prev_agent,
                    to_agent=agent_id,
                    edge_type=edge_type,
                    turn_index=i,
                    content_snippet=snapshot.content[:200],
                )

            prev_agent = agent_id

        return graph

    def detect(self, snapshots: List[TurnSnapshot]) -> TurnAwareDetectionResult:
        """
        Detect coordination failures using graph analysis.

        Args:
            snapshots: List of turn snapshots

        Returns:
            Detection result for F3 (Coordination Failure)
        """
        if len(snapshots) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for coordination analysis",
                detector_name=self.name,
            )

        # Build graph
        graph = self._build_graph(snapshots)

        if len(graph.nodes) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Single agent, no coordination to analyze",
                detector_name=self.name,
            )

        # Find issues
        cycles = graph.find_cycles(self.min_cycle_length, self.max_cycle_length)
        handoff_failures = graph.find_handoff_failures()
        overhead = graph.calculate_coordination_overhead()

        # Aggregate evidence
        issues = []
        affected_turns = []
        max_severity = TurnAwareSeverity.NONE
        confidence = 0.0

        # Cycles - only flag if same cycle repeats excessively
        # Filter to find cycles that repeat multiple times
        cycle_counts = {}
        for c in cycles:
            # Normalize cycle (sort agents to find same cycle regardless of start)
            normalized = tuple(sorted(c.agents))
            cycle_counts[normalized] = cycle_counts.get(normalized, 0) + 1

        # Only flag cycles that repeat multiple times (min_cycles_to_flag)
        excessive_cycles = [(cycle, count) for cycle, count in cycle_counts.items()
                           if count >= self.min_cycles_to_flag]

        if excessive_cycles:
            worst_cycle, count = max(excessive_cycles, key=lambda x: x[1])
            issues.append(f"Excessive repetition: cycle {' <-> '.join(worst_cycle[:3])} repeated {count}x")

            # Find affected turns from the repeated cycles
            for c in cycles:
                if tuple(sorted(c.agents)) == worst_cycle:
                    affected_turns.extend(c.turn_indices)

            max_severity = TurnAwareSeverity.MODERATE
            confidence = max(confidence, 0.60 + 0.05 * count)  # Scale with repetitions

            if count >= 4:
                max_severity = TurnAwareSeverity.SEVERE
                confidence = max(confidence, 0.85)

        # Handoff failures - only flag if MANY failures (not just a few)
        if len(handoff_failures) >= self.min_handoff_failures:
            issues.append(f"Multiple handoff failures: {len(handoff_failures)} handoffs without response")
            for failure in handoff_failures[:3]:  # Top 3 for explanation
                affected_turns.append(failure.turn_index)
            max_severity = max(max_severity, TurnAwareSeverity.MODERATE)
            confidence = max(confidence, 0.55 + 0.05 * len(handoff_failures))

        # Coordination overhead - high threshold to avoid false positives
        if overhead["overhead_score"] > self.overhead_threshold:
            issues.append(
                f"High coordination overhead: {overhead['overhead_score']:.0%} of messages are back-and-forth"
            )
            max_severity = max(max_severity, TurnAwareSeverity.MINOR)
            confidence = max(confidence, 0.50)

        detected = len(issues) > 0

        return TurnAwareDetectionResult(
            detected=detected,
            severity=max_severity,
            confidence=confidence,
            failure_mode="F3" if detected else None,
            explanation="; ".join(issues) if issues else "No coordination failures detected",
            affected_turns=sorted(set(affected_turns)),
            evidence={
                "cycles": [{"agents": c.agents, "length": c.cycle_length} for c in cycles],
                "handoff_failures": [
                    {"from": f.from_agent, "to": f.to_agent, "turn": f.turn_index}
                    for f in handoff_failures
                ],
                "overhead": overhead,
                "graph_stats": {
                    "nodes": len(graph.nodes),
                    "edges": len(graph.edges),
                },
            },
            suggested_fix="Add explicit acknowledgments for handoffs; implement coordination protocol with timeouts",
            detector_name=self.name,
            detector_version=MODULE_VERSION,
        )


class GraphBasedUsurpationDetector:
    """
    Detector for role usurpation using graph analysis.

    Detects F9: Role Usurpation - when an agent acts outside its designated role.
    """

    name = "GraphBasedUsurpationDetector"

    # Common role patterns - made more specific to reduce false positives
    # Single common words like "run", "check", "find" trigger too many FPs
    ROLE_PATTERNS = {
        "coordinator": ["i will assign", "let me delegate", "i'll coordinate", "as coordinator", "orchestrating"],
        "executor": ["executing now", "i will implement", "implementing the", "as executor"],
        "reviewer": ["reviewing your", "let me review", "my review shows", "as reviewer", "upon review"],
        "researcher": ["researching this", "my research shows", "investigating the", "as researcher"],
    }

    def __init__(self, strict_roles: bool = False):
        self.strict_roles = strict_roles

    def _infer_role(self, agent_id: str, content: str) -> Optional[str]:
        """Infer agent role from ID and content."""
        agent_lower = agent_id.lower()

        # Check agent ID first
        for role, patterns in self.ROLE_PATTERNS.items():
            if role in agent_lower:
                return role

        # Check content for role signals
        content_lower = content.lower()
        for role, patterns in self.ROLE_PATTERNS.items():
            if any(p in content_lower for p in patterns):
                return role

        return None

    def _detect_boundary_violation(
        self,
        agent_id: str,
        expected_role: Optional[str],
        content: str,
    ) -> Optional[str]:
        """Detect if an agent is acting outside its role."""
        if not expected_role:
            return None

        content_lower = content.lower()

        # Check if agent is doing something outside its role
        for role, patterns in self.ROLE_PATTERNS.items():
            if role == expected_role:
                continue
            if any(p in content_lower for p in patterns):
                return f"{agent_id} (expected {expected_role}) is doing {role} work"

        return None

    def detect(self, snapshots: List[TurnSnapshot]) -> TurnAwareDetectionResult:
        """
        Detect role usurpation.

        Args:
            snapshots: List of turn snapshots

        Returns:
            Detection result for F9 (Role Usurpation)
        """
        if len(snapshots) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for usurpation analysis",
                detector_name=self.name,
            )

        violations = []
        affected_turns = []
        agent_roles: Dict[str, str] = {}

        for i, snapshot in enumerate(snapshots):
            agent_id = snapshot.participant_id or f"agent_{i}"

            # Infer or retrieve role
            if agent_id not in agent_roles:
                role = self._infer_role(agent_id, snapshot.content)
                if role:
                    agent_roles[agent_id] = role

            # Check for violations
            if agent_id in agent_roles:
                violation = self._detect_boundary_violation(
                    agent_id,
                    agent_roles[agent_id],
                    snapshot.content,
                )
                if violation:
                    violations.append(violation)
                    affected_turns.append(i)

        # F9: Balance precision vs recall
        # v1: 10+ AND >30% = 0% recall
        # v2: 5+ OR >20% = 50% recall but 75% FPR
        # v3: Tighter thresholds with AND logic
        # v4: With more specific patterns, we can lower thresholds slightly
        min_violations_to_flag = 4  # Lowered since patterns are more specific
        min_violation_ratio = 0.15
        violation_ratio = len(violations) / len(snapshots) if snapshots else 0
        detected = len(violations) >= min_violations_to_flag and violation_ratio > min_violation_ratio
        confidence = min(0.9, 0.2 + violation_ratio * 0.5) if detected else 0.0

        severity = TurnAwareSeverity.NONE
        if detected:
            if len(violations) >= 8:
                severity = TurnAwareSeverity.SEVERE
            elif len(violations) >= 6:
                severity = TurnAwareSeverity.MODERATE
            else:
                severity = TurnAwareSeverity.MINOR

        return TurnAwareDetectionResult(
            detected=detected,
            severity=severity,
            confidence=confidence,
            failure_mode="F9" if detected else None,
            explanation="; ".join(violations[:3]) if violations else "No role usurpation detected",
            affected_turns=affected_turns,
            evidence={
                "violations": violations,
                "agent_roles": agent_roles,
            },
            suggested_fix="Enforce role boundaries; add role validation before action execution",
            detector_name=self.name,
            detector_version=MODULE_VERSION,
        )
