"""
Graph-Based Agent Coordination Detection (v1.2)
==========================================

Builds a graph representation of agent interactions to detect:
- F3: Coordination Failure (communication cycles, missed handoffs)
- F9: Role Usurpation (agents acting outside their designated roles)

Enhanced in v1.2:
- Semantic repetition checking in cycles (uses EmbeddingMixin)
- Orphan agent detection (agents that join but never contribute)
- Handoff protocol validation (request-response pairs)
- Node-level role consistency scoring

Based on SentinelAgent research: graph-based analysis with node/edge/path analysis.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .turn_aware import (
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    TurnSnapshot,
    MODULE_VERSION,
    EmbeddingMixin,
    EMBEDDING_SIMILARITY_THRESHOLD,
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
    semantic_similarity: float = 0.0  # v1.2: Track similarity score
    content_samples: List[str] = field(default_factory=list)


@dataclass
class OrphanAgent:
    """Information about an orphan agent (joined but didn't contribute)."""
    agent_id: str
    role: Optional[str] = None
    join_turn: int = 0
    inbound_messages: int = 0  # Messages received
    outbound_messages: int = 0  # Messages sent
    reason: str = ""  # Why considered orphan


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

    def find_orphan_agents(self, min_contribution_ratio: float = 0.1) -> List[OrphanAgent]:
        """
        Find orphan agents - agents that were added to the graph but never
        contributed meaningfully to the conversation.

        v1.2: Detects agents that:
        - Only received messages but never sent any
        - Sent very few messages relative to others
        - Were mentioned/addressed but never responded
        """
        orphans = []

        if len(self.nodes) < 2:
            return orphans

        # Calculate message statistics per agent
        outbound_counts = defaultdict(int)
        inbound_counts = defaultdict(int)

        for edge in self.edges:
            outbound_counts[edge.from_agent] += 1
            inbound_counts[edge.to_agent] += 1

        avg_outbound = sum(outbound_counts.values()) / len(self.nodes) if self.nodes else 1

        for agent_id, node in self.nodes.items():
            outbound = outbound_counts.get(agent_id, 0)
            inbound = inbound_counts.get(agent_id, 0)

            # Check if agent is an orphan
            reason = None

            # Never sent any messages but received some
            if outbound == 0 and inbound > 0:
                reason = f"Received {inbound} messages but never responded"

            # Sent very few messages compared to average
            elif avg_outbound > 2 and outbound < avg_outbound * min_contribution_ratio:
                reason = f"Sent only {outbound} messages vs avg {avg_outbound:.1f}"

            if reason:
                orphans.append(OrphanAgent(
                    agent_id=agent_id,
                    role=node.role,
                    join_turn=node.turn_indices[0] if node.turn_indices else 0,
                    inbound_messages=inbound,
                    outbound_messages=outbound,
                    reason=reason,
                ))

        return orphans

    def validate_handoff_protocol(self) -> List[Dict[str, Any]]:
        """
        Validate request-response handoff protocol.

        v1.2: Checks that:
        - Requests have corresponding responses
        - Response comes from the expected agent
        - Response is within reasonable turn distance
        """
        violations = []

        # Track pending requests: (requester, requestee) -> edge
        pending = {}

        for edge in sorted(self.edges, key=lambda e: e.turn_index):
            # Check if this is a request (handoff/delegation)
            is_request = edge.edge_type in (EdgeType.HANDOFF, EdgeType.DELEGATION)

            # Check if this is a response
            reverse_key = (edge.to_agent, edge.from_agent)
            if reverse_key in pending:
                pending_edge = pending[reverse_key]
                turn_distance = edge.turn_index - pending_edge.turn_index

                # Valid response - remove from pending
                del pending[reverse_key]

                # But check if response took too long
                if turn_distance > 10:
                    violations.append({
                        "type": "slow_response",
                        "from": pending_edge.from_agent,
                        "to": pending_edge.to_agent,
                        "request_turn": pending_edge.turn_index,
                        "response_turn": edge.turn_index,
                        "turn_distance": turn_distance,
                    })

            # Track new request
            if is_request:
                key = (edge.from_agent, edge.to_agent)
                pending[key] = edge

        # Any remaining pending are failed handoffs
        for (from_agent, to_agent), edge in pending.items():
            violations.append({
                "type": "no_response",
                "from": from_agent,
                "to": to_agent,
                "request_turn": edge.turn_index,
                "content_snippet": edge.content_snippet[:100],
            })

        return violations


class GraphBasedCoordinationDetector(EmbeddingMixin):
    """
    Detector for coordination failures using graph analysis.

    v1.2 Enhancements:
    - Semantic repetition checking in cycles
    - Orphan agent detection
    - Handoff protocol validation
    - Uses EmbeddingMixin for semantic similarity

    Detects:
    - F3: Agent Coordination Failure (excessive cycles, genuine handoff failures)
    - High coordination overhead
    - Orphan agents (agents that don't contribute)

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
        semantic_repeat_threshold: float = 0.85,  # v1.2: Similarity threshold for semantic repeats
    ):
        EmbeddingMixin.__init__(self)
        self.min_cycle_length = min_cycle_length
        self.max_cycle_length = max_cycle_length
        self.overhead_threshold = overhead_threshold
        self.min_handoff_failures = min_handoff_failures
        self.min_cycles_to_flag = min_cycles_to_flag
        self.semantic_repeat_threshold = semantic_repeat_threshold

    def _check_semantic_repetition(
        self,
        cycles: List[CycleInfo],
        snapshots: List[TurnSnapshot],
    ) -> List[CycleInfo]:
        """
        Check if cycles contain semantically similar content.

        v1.2: Uses embeddings to detect when messages in a cycle are
        semantically repeating the same content (not just syntactically similar).
        """
        enhanced_cycles = []

        for cycle in cycles:
            if len(cycle.content_samples) < 2:
                enhanced_cycles.append(cycle)
                continue

            # Compare consecutive messages in the cycle for semantic similarity
            similarities = []
            for i in range(len(cycle.content_samples) - 1):
                if cycle.content_samples[i] and cycle.content_samples[i + 1]:
                    try:
                        sim = self.semantic_similarity(
                            cycle.content_samples[i],
                            cycle.content_samples[i + 1],
                        )
                        similarities.append(sim)
                    except Exception as e:
                        logger.debug(f"Semantic similarity failed: {e}")
                        continue

            if similarities:
                avg_sim = sum(similarities) / len(similarities)
                is_repeat = avg_sim >= self.semantic_repeat_threshold

                # Create enhanced cycle info
                enhanced_cycles.append(CycleInfo(
                    agents=cycle.agents,
                    turn_indices=cycle.turn_indices,
                    cycle_length=cycle.cycle_length,
                    is_semantic_repeat=is_repeat,
                    semantic_similarity=avg_sim,
                    content_samples=cycle.content_samples,
                ))
            else:
                enhanced_cycles.append(cycle)

        return enhanced_cycles

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

        v1.2 Enhancements:
        - Semantic repetition checking in cycles
        - Orphan agent detection
        - Enhanced handoff protocol validation

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

        # v1.2: Enhanced analysis
        orphan_agents = graph.find_orphan_agents()
        handoff_violations = graph.validate_handoff_protocol()

        # v1.2: Check for semantic repetition in cycles
        enhanced_cycles = self._check_semantic_repetition(cycles, snapshots)

        # Aggregate evidence
        issues = []
        affected_turns = []
        max_severity = TurnAwareSeverity.NONE
        confidence = 0.0

        # Cycles - only flag if same cycle repeats excessively
        # v1.2: Also boost confidence if cycles are semantically repetitive
        cycle_counts = {}
        semantic_repeat_count = 0
        for c in enhanced_cycles:
            # Normalize cycle (sort agents to find same cycle regardless of start)
            normalized = tuple(sorted(c.agents))
            cycle_counts[normalized] = cycle_counts.get(normalized, 0) + 1
            if c.is_semantic_repeat:
                semantic_repeat_count += 1

        # Only flag cycles that repeat multiple times (min_cycles_to_flag)
        excessive_cycles = [(cycle, count) for cycle, count in cycle_counts.items()
                           if count >= self.min_cycles_to_flag]

        if excessive_cycles:
            worst_cycle, count = max(excessive_cycles, key=lambda x: x[1])
            issues.append(f"Excessive repetition: cycle {' <-> '.join(worst_cycle[:3])} repeated {count}x")

            # Find affected turns from the repeated cycles
            for c in enhanced_cycles:
                if tuple(sorted(c.agents)) == worst_cycle:
                    affected_turns.extend(c.turn_indices)

            max_severity = TurnAwareSeverity.MODERATE
            confidence = max(confidence, 0.60 + 0.05 * count)  # Scale with repetitions

            # v1.2: Boost confidence if semantic repeats detected
            if semantic_repeat_count > 0:
                confidence = max(confidence, 0.70 + 0.05 * semantic_repeat_count)
                issues.append(f"Semantic repetition detected in {semantic_repeat_count} cycles")

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

        # v1.2: Check for orphan agents
        if len(orphan_agents) >= 2:
            orphan_names = [o.agent_id for o in orphan_agents[:3]]
            issues.append(f"Orphan agents detected: {', '.join(orphan_names)} - joined but didn't contribute")
            max_severity = max(max_severity, TurnAwareSeverity.MINOR)
            confidence = max(confidence, 0.45 + 0.1 * len(orphan_agents))

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
                # v1.2: Enhanced cycle info with semantic similarity
                "cycles": [
                    {
                        "agents": c.agents,
                        "length": c.cycle_length,
                        "is_semantic_repeat": c.is_semantic_repeat,
                        "semantic_similarity": round(c.semantic_similarity, 3),
                    }
                    for c in enhanced_cycles
                ],
                "handoff_failures": [
                    {"from": f.from_agent, "to": f.to_agent, "turn": f.turn_index}
                    for f in handoff_failures
                ],
                # v1.2: Handoff protocol violations
                "handoff_violations": handoff_violations[:5],
                # v1.2: Orphan agent info
                "orphan_agents": [
                    {"id": o.agent_id, "role": o.role, "reason": o.reason}
                    for o in orphan_agents
                ],
                "overhead": overhead,
                "graph_stats": {
                    "nodes": len(graph.nodes),
                    "edges": len(graph.edges),
                },
            },
            suggested_fix="Add explicit acknowledgments for handoffs; implement coordination protocol with timeouts; ensure all agents contribute meaningfully",
            detector_name=self.name,
            detector_version="1.2",
        )


class GraphBasedUsurpationDetector(EmbeddingMixin):
    """
    Detector for role usurpation using graph analysis.

    v1.2 Enhancements:
    - Node-level role consistency scoring using embeddings
    - Semantic drift detection within agent's messages
    - Uses EmbeddingMixin for role-content alignment

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
        # v1.2: Extended role patterns
        "programmer": ["writing code", "implementing", "coding the", "def ", "function ", "class "],
        "designer": ["designing", "mockup", "wireframe", "ui design", "ux design"],
        "tester": ["testing", "test case", "test plan", "qa ", "quality assurance"],
    }

    # v1.2: Role descriptions for semantic matching
    ROLE_DESCRIPTIONS = {
        "coordinator": "Managing tasks, delegating work, coordinating team members, overseeing progress",
        "executor": "Implementing solutions, executing tasks, carrying out assigned work",
        "reviewer": "Reviewing work, providing feedback, checking quality, approving changes",
        "researcher": "Researching topics, gathering information, investigating problems",
        "programmer": "Writing code, implementing features, fixing bugs, software development",
        "designer": "Creating designs, mockups, wireframes, visual layouts",
        "tester": "Testing software, writing test cases, quality assurance, finding bugs",
    }

    def __init__(self, strict_roles: bool = False, role_consistency_threshold: float = 0.3):
        EmbeddingMixin.__init__(self)
        self.strict_roles = strict_roles
        self.role_consistency_threshold = role_consistency_threshold

    def _compute_role_consistency(
        self,
        agent_id: str,
        role: str,
        messages: List[str],
    ) -> Dict[str, Any]:
        """
        Compute role consistency score for an agent using semantic similarity.

        v1.2: Compares agent's messages against role description to detect drift.
        """
        if not messages or role not in self.ROLE_DESCRIPTIONS:
            return {"score": 1.0, "aligned": True, "details": "No role description available"}

        role_desc = self.ROLE_DESCRIPTIONS[role]

        # Sample messages for efficiency (max 5)
        sample_messages = messages[:5] if len(messages) > 5 else messages

        similarities = []
        for msg in sample_messages:
            if len(msg) > 50:  # Only check substantial messages
                try:
                    sim = self.semantic_similarity(msg[:500], role_desc)
                    similarities.append(sim)
                except Exception as e:
                    logger.debug(f"Role consistency check failed: {e}")
                    continue

        if not similarities:
            return {"score": 1.0, "aligned": True, "details": "No messages to check"}

        avg_sim = sum(similarities) / len(similarities)
        is_aligned = avg_sim >= self.role_consistency_threshold

        return {
            "score": round(avg_sim, 3),
            "aligned": is_aligned,
            "messages_checked": len(similarities),
            "role_description": role_desc[:50] + "...",
        }

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

        v1.2 Enhancements:
        - Node-level role consistency scoring
        - Semantic drift detection within agent's messages

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
        agent_messages: Dict[str, List[str]] = defaultdict(list)

        for i, snapshot in enumerate(snapshots):
            agent_id = snapshot.participant_id or f"agent_{i}"

            # Collect messages per agent for consistency scoring
            agent_messages[agent_id].append(snapshot.content)

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

        # v1.2: Compute role consistency scores for agents with roles
        role_consistency_scores = {}
        low_consistency_agents = []
        for agent_id, role in agent_roles.items():
            consistency = self._compute_role_consistency(
                agent_id,
                role,
                agent_messages.get(agent_id, []),
            )
            role_consistency_scores[agent_id] = consistency
            if not consistency.get("aligned", True):
                low_consistency_agents.append(agent_id)

        # F9: Balance precision vs recall
        # v1: 10+ AND >30% = 0% recall
        # v2: 5+ OR >20% = 50% recall but 75% FPR
        # v3: Tighter thresholds with AND logic
        # v4: With more specific patterns, we can lower thresholds slightly
        # v1.2: Factor in role consistency scores
        min_violations_to_flag = 4  # Lowered since patterns are more specific
        min_violation_ratio = 0.15
        violation_ratio = len(violations) / len(snapshots) if snapshots else 0
        detected = len(violations) >= min_violations_to_flag and violation_ratio > min_violation_ratio

        # v1.2: Also detect if many agents have low role consistency
        if len(low_consistency_agents) >= 2:
            detected = True

        confidence = min(0.9, 0.2 + violation_ratio * 0.5) if detected else 0.0

        # v1.2: Boost confidence if role consistency is low
        if low_consistency_agents and detected:
            confidence = max(confidence, 0.55 + 0.1 * len(low_consistency_agents))

        severity = TurnAwareSeverity.NONE
        if detected:
            if len(violations) >= 8 or len(low_consistency_agents) >= 3:
                severity = TurnAwareSeverity.SEVERE
            elif len(violations) >= 6 or len(low_consistency_agents) >= 2:
                severity = TurnAwareSeverity.MODERATE
            else:
                severity = TurnAwareSeverity.MINOR

        explanation_parts = violations[:3] if violations else []
        if low_consistency_agents:
            explanation_parts.append(
                f"Role consistency drift: {', '.join(low_consistency_agents[:2])} acting outside role"
            )

        return TurnAwareDetectionResult(
            detected=detected,
            severity=severity,
            confidence=confidence,
            failure_mode="F9" if detected else None,
            explanation="; ".join(explanation_parts) if explanation_parts else "No role usurpation detected",
            affected_turns=affected_turns,
            evidence={
                "violations": violations,
                "agent_roles": agent_roles,
                # v1.2: Include role consistency scores
                "role_consistency": role_consistency_scores,
                "low_consistency_agents": low_consistency_agents,
            },
            suggested_fix="Enforce role boundaries; add role validation before action execution; monitor role consistency",
            detector_name=self.name,
            detector_version="1.2",
        )
