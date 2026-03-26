"""Orchestration Quality Scorer — Multi-Agent Workflow Quality Assessment.

Extends TrajectoryEvaluator from single-agent to multi-agent. Scores 7
dimensions of orchestration quality on a 0.0-1.0 scale:

1. efficiency: Makespan ratio (optimal parallel vs actual elapsed)
2. utilization: Agent load distribution (Gini coefficient)
3. parallelization: Topology-aware missed parallelization detection
4. delegation_quality: Context preservation across true delegation handoffs
5. communication_efficiency: Message-to-work ratio
6. robustness: Fault tolerance and error recovery
7. topology_alignment: Is the orchestration topology suited to the task?

Research basis:
- Who&When (ICML 2025): Causal attribution over binary detection
- SentinelAgent (2025): Node/edge/path graph-level analysis
- Scaling Agent Systems (Dec 2025): 4-agent saturation, topology matters
- Google Vertex AI (2026): Trajectory-level evaluation

Fires as a detector when overall quality drops below 0.7.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Topology types
PIPELINE = "pipeline"       # A→B→C, each agent once, linear
FAN_OUT = "fan_out"         # A→[B,C,D], one dispatcher + parallel workers
FAN_IN = "fan_in"           # [A,B,C]→D, parallel workers + one aggregator
PARALLEL = "parallel"       # [A,B] same sequence_num, concurrent
HIERARCHICAL = "hierarchical"  # A→B→A, supervisor pattern
MIXED = "mixed"             # Combination


@dataclass
class OrchestrationScore:
    """Multi-dimensional orchestration quality score."""
    overall: float  # 0.0-1.0, weighted combination
    efficiency: float = 0.0
    utilization: float = 0.0
    parallelization: float = 0.0
    delegation_quality: float = 0.0
    communication_efficiency: float = 0.0
    robustness: float = 0.0
    topology_alignment: float = 0.0
    topology: str = MIXED
    dimensions: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    agent_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    critical_path: List[str] = field(default_factory=list)


class OrchestrationQualityScorer:
    """Scores the quality of multi-agent orchestration from trace data."""

    def __init__(
        self,
        efficiency_weight: float = 0.25,
        utilization_weight: float = 0.15,
        parallelization_weight: float = 0.15,
        delegation_weight: float = 0.10,
        communication_weight: float = 0.15,
        robustness_weight: float = 0.10,
        topology_weight: float = 0.10,
    ):
        self.weights = {
            "efficiency": efficiency_weight,
            "utilization": utilization_weight,
            "parallelization": parallelization_weight,
            "delegation_quality": delegation_weight,
            "communication_efficiency": communication_weight,
            "robustness": robustness_weight,
            "topology_alignment": topology_weight,
        }

    def score(self, states: List[Dict[str, Any]]) -> OrchestrationScore:
        """Score orchestration quality from a list of agent states."""
        if not states or len(states) < 2:
            return OrchestrationScore(
                overall=1.0 if states else 0.0,
                issues=["Single state — no orchestration to evaluate"] if states else ["Empty trace"],
            )

        agents = {s.get("agent_id", "") for s in states if s.get("agent_id")}
        if len(agents) < 2:
            return OrchestrationScore(
                overall=0.8,
                issues=["Single agent — orchestration scoring requires 2+ agents"],
            )

        issues = []
        agent_states = defaultdict(list)
        for s in states:
            agent_states[s.get("agent_id", "unknown")].append(s)

        handoffs = self._extract_handoffs(states)
        topology = self._classify_topology(states, agent_states)

        # Score each dimension
        eff = self._score_efficiency(states, agent_states)
        util = self._score_utilization(agent_states)
        par = self._score_parallelization(states, agent_states, topology)
        deleg = self._score_delegation_quality(states, handoffs)
        comm = self._score_communication_efficiency(states, handoffs)
        robust = self._score_robustness(states, agent_states)
        topo = self._score_topology_alignment(states, agent_states, topology)

        if eff < 0.5:
            issues.append(f"Low efficiency ({eff:.2f}): agents could run more in parallel")
        if util < 0.5:
            issues.append(f"Poor utilization ({util:.2f}): unbalanced agent workload")
        if par < 0.5:
            issues.append(f"Missed parallelization ({par:.2f}): independent tasks run sequentially")
        if deleg < 0.5:
            issues.append(f"Weak delegation ({deleg:.2f}): context lost across handoffs")
        if comm < 0.5:
            issues.append(f"Low communication efficiency ({comm:.2f}): high message-to-work ratio")
        if robust < 0.5:
            issues.append(f"Low robustness ({robust:.2f}): poor error recovery")
        if topo < 0.5:
            issues.append(f"Topology mismatch ({topo:.2f}): orchestration pattern doesn't suit the task")

        overall = sum(
            score * self.weights[dim]
            for dim, score in [
                ("efficiency", eff), ("utilization", util), ("parallelization", par),
                ("delegation_quality", deleg), ("communication_efficiency", comm),
                ("robustness", robust), ("topology_alignment", topo),
            ]
        )

        agent_stats = {}
        for aid, ast in agent_states.items():
            agent_stats[aid] = {
                "state_count": len(ast),
                "total_latency_ms": sum(s.get("latency_ms", 100) for s in ast),
                "errors": sum(1 for s in ast if s.get("status") == "error"),
                "role": ast[0].get("agent_role", "unknown") if ast else "unknown",
            }

        critical_path = self._compute_critical_path(agent_states)

        dims = {
            "efficiency": round(eff, 4), "utilization": round(util, 4),
            "parallelization": round(par, 4), "delegation_quality": round(deleg, 4),
            "communication_efficiency": round(comm, 4), "robustness": round(robust, 4),
            "topology_alignment": round(topo, 4),
        }

        return OrchestrationScore(
            overall=round(overall, 4), efficiency=round(eff, 4),
            utilization=round(util, 4), parallelization=round(par, 4),
            delegation_quality=round(deleg, 4), communication_efficiency=round(comm, 4),
            robustness=round(robust, 4), topology_alignment=round(topo, 4),
            topology=topology, dimensions=dims, issues=issues,
            agent_stats=agent_stats, critical_path=critical_path,
        )

    # ── Topology Classification ──────────────────────────────────────

    def _classify_topology(
        self, states: List[Dict], agent_states: Dict[str, List[Dict]]
    ) -> str:
        """Classify the orchestration pattern from the trace."""
        agents = list(agent_states.keys())
        n_agents = len(agents)

        # Check for parallel execution (agents with same sequence_num)
        seq_groups = defaultdict(set)
        for s in states:
            seq_groups[s.get("sequence_num", 0)].add(s.get("agent_id", ""))
        has_parallel = any(len(aids) > 1 for aids in seq_groups.values())

        # Check for hierarchical (supervisor returns)
        agent_sequence = [s.get("agent_id", "") for s in states]
        agent_first = {}
        agent_last = {}
        for i, aid in enumerate(agent_sequence):
            if aid not in agent_first:
                agent_first[aid] = i
            agent_last[aid] = i
        has_return = any(
            agent_first[a] < agent_first.get(b, 999) < agent_last[a]
            for a in agents for b in agents if a != b and a in agent_first and a in agent_last
        )

        # Check for fan-out (one agent then multiple different agents)
        handoff_targets = defaultdict(set)
        prev = None
        for s in states:
            aid = s.get("agent_id", "")
            if aid and aid != prev and prev:
                handoff_targets[prev].add(aid)
            prev = aid
        has_fan_out = any(len(targets) >= 2 for targets in handoff_targets.values())

        if has_return:
            return HIERARCHICAL
        if has_parallel:
            return PARALLEL
        if has_fan_out:
            return FAN_OUT
        # Pipeline: each agent appears in one contiguous block
        seen_agents = []
        prev = None
        for s in states:
            aid = s.get("agent_id", "")
            if aid != prev:
                seen_agents.append(aid)
                prev = aid
        if len(set(seen_agents)) == len(seen_agents):
            return PIPELINE

        return MIXED

    # ── Handoff Extraction ───────────────────────────────────────────

    def _extract_handoffs(self, states: List[Dict]) -> List[Tuple[str, str, int]]:
        """Extract agent-to-agent handoffs. Returns (from_agent, to_agent, state_index)."""
        handoffs = []
        prev_agent = None
        for i, s in enumerate(states):
            aid = s.get("agent_id", "")
            if aid and aid != prev_agent and prev_agent is not None:
                handoffs.append((prev_agent, aid, i))
            prev_agent = aid
        return handoffs

    # ── Fix 3: Makespan-Based Efficiency ─────────────────────────────

    def _score_efficiency(
        self, states: List[Dict], agent_states: Dict[str, List[Dict]]
    ) -> float:
        """Makespan ratio: optimal parallel execution vs actual sequential execution.

        For a fan-out of 3 agents each taking 100ms:
        - optimal (parallel): max(100, 100, 100) = 100ms
        - actual (sequential): 100+100+100 = 300ms
        - efficiency = 100/300 = 0.33

        For a pipeline A(100ms)→B(200ms):
        - optimal = actual = 300ms (must be sequential)
        - efficiency = 1.0
        """
        total_elapsed = sum(s.get("latency_ms", 100) for s in states)
        if total_elapsed == 0:
            return 1.0

        # Build data-dependency graph using shared state_delta keys
        agent_keys: Dict[str, Set[str]] = {}
        agent_durations: Dict[str, int] = {}
        for aid, ast in agent_states.items():
            keys = set()
            for s in ast:
                delta = s.get("state_delta", {})
                if isinstance(delta, dict):
                    keys.update(delta.keys())
            agent_keys[aid] = keys
            agent_durations[aid] = sum(s.get("latency_ms", 100) for s in ast)

        # Data dependencies: B depends on A if they share state_delta keys
        # OR there's meaningful text overlap (implicit context passing)
        agents = list(agent_states.keys())
        dependencies: Dict[str, Set[str]] = defaultdict(set)
        prev_agent = None
        prev_state = None
        for s in states:
            aid = s.get("agent_id", "")
            if aid and aid != prev_agent and prev_agent:
                shared = agent_keys.get(prev_agent, set()) & agent_keys.get(aid, set())
                if shared:
                    dependencies[aid].add(prev_agent)
                elif prev_state:
                    # Check text overlap for implicit context passing
                    prev_text = self._state_to_text(prev_state)
                    cur_text = self._state_to_text(s)
                    stop = {"the", "a", "an", "is", "of", "to", "in", "and", "or", "it", "for", "with"}
                    if prev_text and cur_text:
                        pw = set(prev_text.lower().split()) - stop
                        cw = set(cur_text.lower().split()) - stop
                        if pw and len(pw & cw) / max(len(pw), 1) > 0.15:
                            dependencies[aid].add(prev_agent)
            prev_agent = aid
            prev_state = s

        # Compute optimal makespan via critical path through DATA dependencies only
        earliest_finish: Dict[str, int] = {}

        def compute_ef(agent: str, visited: Set[str]) -> int:
            if agent in earliest_finish:
                return earliest_finish[agent]
            if agent in visited:
                return agent_durations.get(agent, 0)
            visited.add(agent)
            dep_finish = 0
            for dep in dependencies.get(agent, set()):
                dep_finish = max(dep_finish, compute_ef(dep, visited))
            ef = dep_finish + agent_durations.get(agent, 0)
            earliest_finish[agent] = ef
            return ef

        optimal_makespan = 0
        for aid in agent_durations:
            optimal_makespan = max(optimal_makespan, compute_ef(aid, set()))

        if optimal_makespan == 0:
            return 1.0

        # efficiency = optimal / actual
        return min(1.0, optimal_makespan / total_elapsed)

    # ── Utilization (unchanged, works well) ──────────────────────────

    def _score_utilization(self, agent_states: Dict[str, List[Dict]]) -> float:
        """Gini coefficient of agent workload distribution."""
        if len(agent_states) < 2:
            return 1.0
        workloads = [sum(s.get("latency_ms", 100) for s in ast) for ast in agent_states.values()]
        if not workloads or max(workloads) == 0:
            return 1.0
        n = len(workloads)
        workloads_sorted = sorted(workloads)
        total = sum(workloads_sorted)
        if total == 0:
            return 1.0
        gini_sum = sum((2 * (i + 1) - n - 1) * w for i, w in enumerate(workloads_sorted))
        gini = gini_sum / (n * total)
        return max(0.0, min(1.0, 1.0 - gini))

    # ── Fix 1: Topology-Aware Parallelization ────────────────────────

    def _score_parallelization(
        self, states: List[Dict], agent_states: Dict[str, List[Dict]], topology: str
    ) -> float:
        """Topology-aware parallelization scoring.

        - Pipeline: parallelization = 1.0 (sequential is correct)
        - Fan-out/Parallel: check if workers actually ran concurrently
        - Mixed: check for independent agents that ran sequentially
        """
        if len(agent_states) < 2:
            return 1.0

        # Pipelines: sequential IS the correct pattern
        if topology == PIPELINE:
            return 1.0

        # For parallel/fan-out topologies: check if concurrent agents ran concurrently
        seq_groups = defaultdict(set)
        for s in states:
            seq_groups[s.get("sequence_num", 0)].add(s.get("agent_id", ""))

        # Count agents that share a sequence_num (true parallel execution)
        parallel_agents = set()
        for seq, aids in seq_groups.items():
            if len(aids) > 1:
                parallel_agents.update(aids)

        # Count agents that could be parallel (same role, no shared keys)
        agent_keys: Dict[str, Set[str]] = {}
        for aid, ast in agent_states.items():
            keys = set()
            for s in ast:
                delta = s.get("state_delta", {})
                if isinstance(delta, dict):
                    keys.update(delta.keys())
            agent_keys[aid] = keys

        agent_roles: Dict[str, str] = {}
        for aid, ast in agent_states.items():
            agent_roles[aid] = ast[0].get("agent_role", "") if ast else ""

        # Find potentially parallelizable agents:
        # 1. Same sequence_num anywhere (already running concurrently)
        # 2. Same role (peer workers)
        # 3. No shared state keys (independent work)
        agents = list(agent_states.keys())
        parallelizable_pairs = []
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                a, b = agents[i], agents[j]
                a_seqs = {s.get("sequence_num", -1) for s in agent_states[a]}
                b_seqs = {s.get("sequence_num", -1) for s in agent_states[b]}
                already_parallel = bool(a_seqs & b_seqs)  # Share sequence_num = concurrent
                same_role = agent_roles.get(a) and agent_roles[a] == agent_roles[b]
                no_shared = not (agent_keys.get(a, set()) & agent_keys.get(b, set()))
                if already_parallel or same_role or no_shared:
                    parallelizable_pairs.append((a, b))

        if not parallelizable_pairs:
            return 1.0

        # How many of these actually ran in parallel?
        parallel_count = 0
        for a, b in parallelizable_pairs:
            a_seqs = {s.get("sequence_num", 0) for s in agent_states[a]}
            b_seqs = {s.get("sequence_num", 0) for s in agent_states[b]}
            if a_seqs & b_seqs:  # Overlapping sequence_nums = concurrent
                parallel_count += 1

        return parallel_count / len(parallelizable_pairs)

    # ── Fix 2: Delegation Quality — Skip Peer Handoffs ───────────────

    def _score_delegation_quality(
        self, states: List[Dict], handoffs: List[Tuple[str, str, int]]
    ) -> float:
        """Score context preservation across TRUE delegation handoffs.

        Skips handoffs between parallel peers (same sequence_num or same role).
        """
        if not handoffs:
            return 1.0

        preservation_scores = []
        for from_agent, to_agent, idx in handoffs:
            if idx <= 0 or idx >= len(states):
                continue
            outgoing = states[idx - 1]
            incoming = states[idx]

            # Skip parallel peer handoffs — not a real delegation
            if outgoing.get("sequence_num") == incoming.get("sequence_num"):
                continue
            out_role = outgoing.get("agent_role", "")
            in_role = incoming.get("agent_role", "")
            if out_role and out_role == in_role:
                continue

            out_text = self._state_to_text(outgoing)
            in_text = self._state_to_text(incoming)

            if not out_text or not in_text:
                preservation_scores.append(0.5)
                continue

            # Word overlap with domain-term boosting
            out_words = set(out_text.lower().split())
            in_words = set(in_text.lower().split())
            if not out_words:
                preservation_scores.append(0.5)
                continue

            shared = out_words & in_words
            # Filter stop words for a cleaner signal
            stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                    "for", "of", "to", "in", "on", "at", "by", "with", "and", "or",
                    "it", "its", "this", "that", "from"}
            meaningful_shared = shared - stop
            meaningful_out = out_words - stop

            if not meaningful_out:
                preservation_scores.append(0.5)
                continue

            overlap = len(meaningful_shared) / max(len(meaningful_out), 1)
            # Scale: 30% meaningful overlap = good delegation
            preservation_scores.append(min(1.0, overlap * 3))

        if not preservation_scores:
            return 1.0  # No true delegations to evaluate

        return sum(preservation_scores) / len(preservation_scores)

    # ── Communication Efficiency (unchanged, works well) ─────────────

    def _score_communication_efficiency(
        self, states: List[Dict], handoffs: List[Tuple[str, str, int]]
    ) -> float:
        """Message-to-work ratio."""
        if not states:
            return 1.0
        productive = sum(
            1 for s in states
            if s.get("tool_calls") or len(str(s.get("output", ""))) > 50 or s.get("state_delta")
        )
        comm_count = len(handoffs)
        if productive == 0:
            return 0.0 if comm_count > 0 else 0.5
        ratio = productive / (productive + comm_count)
        return min(1.0, ratio * 1.5)

    # ── Robustness (unchanged, works well) ───────────────────────────

    def _score_robustness(
        self, states: List[Dict], agent_states: Dict[str, List[Dict]]
    ) -> float:
        """Error recovery + role redundancy."""
        if not states:
            return 1.0
        error_count = 0
        recovery_count = 0
        for i, s in enumerate(states):
            if s.get("status") == "error":
                error_count += 1
                if i + 1 < len(states) and states[i + 1].get("status") != "error":
                    recovery_count += 1
        recovery_score = recovery_count / error_count if error_count else 1.0

        roles = defaultdict(list)
        for aid, ast in agent_states.items():
            role = ast[0].get("agent_role", "") if ast else ""
            if role:
                roles[role].append(aid)
        redundant = sum(1 for agents in roles.values() if len(agents) > 1)
        redundancy_score = redundant / max(len(roles), 1) if roles else 0.5

        return recovery_score * 0.7 + redundancy_score * 0.3

    # ── Fix 4: Topology Alignment ────────────────────────────────────

    def _score_topology_alignment(
        self, states: List[Dict], agent_states: Dict[str, List[Dict]], topology: str
    ) -> float:
        """Score whether the topology matches the task characteristics.

        Pipeline + independent keys → bad (should fan-out): 0.3
        Fan-out + shared keys → bad (should pipeline): 0.3
        Hierarchical + single step per worker → bad (unnecessary overhead): 0.5
        Otherwise → good: 1.0
        """
        # Check if agents have independent or shared state keys
        agent_keys: Dict[str, Set[str]] = {}
        for aid, ast in agent_states.items():
            keys = set()
            for s in ast:
                delta = s.get("state_delta", {})
                if isinstance(delta, dict):
                    keys.update(delta.keys())
            agent_keys[aid] = keys

        agents = list(agent_states.keys())
        all_keys = [agent_keys.get(a, set()) for a in agents]

        # Compute pairwise independence ratio
        n_pairs = 0
        independent_pairs = 0
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                n_pairs += 1
                if not (all_keys[i] & all_keys[j]):
                    independent_pairs += 1

        independence_ratio = independent_pairs / max(n_pairs, 1)

        if topology == PIPELINE and independence_ratio > 0.7:
            # Pipeline but agents are independent → could be fan-out
            # But not a hard penalty — pipeline is a valid safe choice
            return 0.5
        if topology in (FAN_OUT, PARALLEL) and independence_ratio < 0.3:
            # Fan-out/parallel but agents share lots of state → should pipeline
            return 0.4
        if topology == HIERARCHICAL:
            # Check if workers do meaningful work (>1 state each)
            worker_states = [
                len(ast) for aid, ast in agent_states.items()
                if len(ast) > 0 and ast[0].get("agent_role") != agent_states[list(agent_states.keys())[0]][0].get("agent_role")
            ]
            if worker_states and max(worker_states) <= 1:
                return 0.5  # Unnecessary hierarchy for trivial work

        return 1.0

    # ══════════════════════════════════════════════════════════════════
    # CONVERSATION MODE — for message-based coordination data (MAST, ChatDev)
    # Research: MultiAgentBench (ACL 2025), AgentPRM (2025), MAST (NeurIPS 2025)
    # ══════════════════════════════════════════════════════════════════

    # Conversation mode weights
    CONV_WEIGHTS = {
        "information_flow": 0.25,
        "contribution_quality": 0.20,
        "decision_convergence": 0.25,
        "role_coherence": 0.15,
        "task_drift": 0.15,
    }

    # Role → domain keywords for coherence scoring
    ROLE_KEYWORDS = {
        "chief executive officer": {"decide", "approve", "coordinate", "propose", "agree", "task", "goal"},
        "chief product officer": {"requirement", "feature", "user", "product", "spec", "design"},
        "chief technology officer": {"architecture", "design", "technology", "framework", "language", "stack", "system"},
        "programmer": {"implement", "code", "write", "function", "class", "def", "import", "return", "variable"},
        "code reviewer": {"review", "check", "test", "bug", "error", "suggest", "issue", "fix", "approve"},
        "counselor": {"discuss", "suggest", "advise", "recommend", "consider", "option"},
        "art designer": {"design", "layout", "color", "interface", "image", "visual", "style"},
    }

    def score_conversation(
        self, messages: List[Dict[str, Any]], agent_ids: List[str] = None,
    ) -> OrchestrationScore:
        """Score orchestration quality from conversation messages.

        Each message dict should have: from_agent, to_agent, content, timestamp.
        """
        # Filter out system messages
        msgs = [m for m in messages if m.get("from_agent", "") != "system"]
        if len(msgs) < 2:
            return OrchestrationScore(
                overall=1.0 if msgs else 0.0,
                issues=["Too few messages to evaluate"],
            )

        agents = agent_ids or list({m.get("from_agent", "") for m in msgs} - {""})
        if len(agents) < 2:
            return OrchestrationScore(overall=0.8, issues=["Single agent in conversation"])

        issues = []

        info_flow = self._conv_information_flow(msgs)
        contrib = self._conv_contribution_quality(msgs, agents)
        convergence = self._conv_decision_convergence(msgs)
        role_coh = self._conv_role_coherence(msgs)
        drift = self._conv_task_drift(msgs)

        if info_flow < 0.4:
            issues.append(f"Poor information flow ({info_flow:.2f}): agents don't build on each other's context")
        if contrib < 0.4:
            issues.append(f"Low contribution quality ({contrib:.2f}): agents produce generic/shallow messages")
        if convergence < 0.4:
            issues.append(f"Poor convergence ({convergence:.2f}): agents loop or diverge instead of deciding")
        if role_coh < 0.4:
            issues.append(f"Role drift ({role_coh:.2f}): agents not acting in their designated roles")
        if drift < 0.4:
            issues.append(f"Task drift ({drift:.2f}): conversation deviates from original task")

        overall = sum(
            score * self.CONV_WEIGHTS[dim]
            for dim, score in [
                ("information_flow", info_flow), ("contribution_quality", contrib),
                ("decision_convergence", convergence), ("role_coherence", role_coh),
                ("task_drift", drift),
            ]
        )

        agent_stats = {}
        for aid in agents:
            agent_msgs = [m for m in msgs if m.get("from_agent") == aid]
            agent_stats[aid] = {
                "message_count": len(agent_msgs),
                "avg_length": sum(len(str(m.get("content", ""))) for m in agent_msgs) / max(len(agent_msgs), 1),
                "role": aid.split(":")[-1].lower().replace("_", " ") if ":" in aid else aid,
            }

        dims = {
            "information_flow": round(info_flow, 4),
            "contribution_quality": round(contrib, 4),
            "decision_convergence": round(convergence, 4),
            "role_coherence": round(role_coh, 4),
            "task_drift": round(drift, 4),
        }

        return OrchestrationScore(
            overall=round(overall, 4),
            delegation_quality=round(info_flow, 4),  # Map to closest execution dim
            communication_efficiency=round(convergence, 4),
            utilization=round(contrib, 4),
            robustness=round(role_coh, 4),
            topology_alignment=round(drift, 4),
            topology="conversation",
            dimensions=dims,
            issues=issues,
            agent_stats=agent_stats,
        )

    def _conv_information_flow(self, msgs: List[Dict]) -> float:
        """Does each agent build on the previous agent's context?

        Extracts key concepts (>4-char words) from message A,
        checks if message B references them.
        """
        stop = {
            "the", "that", "this", "with", "from", "have", "will", "been", "were",
            "would", "could", "should", "about", "their", "there", "which", "these",
            "those", "being", "other", "your", "what", "when", "where", "some",
            "into", "them", "than", "then", "also", "just", "more", "very",
        }
        scores = []
        prev_content = None
        prev_agent = None
        for m in msgs:
            content = str(m.get("content", ""))
            agent = m.get("from_agent", "")
            if prev_content and agent != prev_agent:
                prev_concepts = {
                    w for w in prev_content.lower().split()
                    if len(w) > 4 and w not in stop and w.isalpha()
                }
                if prev_concepts:
                    cur_words = set(content.lower().split())
                    referenced = len(prev_concepts & cur_words) / len(prev_concepts)
                    scores.append(min(1.0, referenced * 2))  # 50% reference = perfect
            prev_content = content
            prev_agent = agent

        return sum(scores) / max(len(scores), 1)

    def _conv_contribution_quality(self, msgs: List[Dict], agents: List[str]) -> float:
        """Do all agents contribute substantively?

        Scores: message length, specificity (code/numbers), actionability.
        Penalizes generic-only agents.
        """
        action_verbs = {
            "implement", "review", "check", "approve", "write", "design",
            "create", "build", "fix", "test", "modify", "update", "analyze",
        }
        generic = {"ok", "sure", "yes", "no", "thanks", "agree", "agreed"}

        agent_quality = {}
        for aid in agents:
            agent_msgs = [m for m in msgs if m.get("from_agent") == aid]
            if not agent_msgs:
                agent_quality[aid] = 0.0
                continue

            scores = []
            for m in agent_msgs:
                content = str(m.get("content", ""))
                length_s = min(1.0, len(content) / 200)
                specific_s = 1.0 if any(c in content for c in ["(", ")", "{", "}", "def ", "class ", "import "]) else 0.3
                action_s = 1.0 if any(v in content.lower() for v in action_verbs) else 0.3
                not_generic = 0.0 if content.lower().strip() in generic else 1.0
                scores.append((length_s + specific_s + action_s + not_generic) / 4)

            agent_quality[aid] = sum(scores) / len(scores)

        if not agent_quality:
            return 0.5

        # Penalize if any agent contributes nothing meaningful
        min_quality = min(agent_quality.values())
        avg_quality = sum(agent_quality.values()) / len(agent_quality)
        return avg_quality * 0.7 + min_quality * 0.3

    def _conv_decision_convergence(self, msgs: List[Dict]) -> float:
        """Do agents converge on decisions or loop endlessly?

        Tracks convergence vs divergence phrases across agent pairs.
        """
        convergence_words = {
            "agree", "agreed", "confirm", "confirmed", "approved", "approve",
            "decided", "finalized", "completed", "done", "accepted", "lgtm",
        }
        divergence_words = {
            "disagree", "actually", "instead", "reconsider", "however",
            "but", "wrong", "incorrect", "redo", "revise", "reject",
        }

        pair_msgs = defaultdict(list)
        for m in msgs:
            pair = (m.get("from_agent", ""), m.get("to_agent", ""))
            pair_msgs[pair].append(str(m.get("content", "")).lower())

        scores = []
        for pair, contents in pair_msgs.items():
            conv = sum(1 for c in contents if any(w in c for w in convergence_words))
            div = sum(1 for c in contents if any(w in c for w in divergence_words))
            total = conv + div
            if total > 0:
                scores.append(conv / total)

        if not scores:
            return 0.7  # No convergence/divergence signals → neutral

        return sum(scores) / len(scores)

    def _conv_role_coherence(self, msgs: List[Dict]) -> float:
        """Do agents act according to their designated roles?

        Maps role names to domain keywords and checks message content.
        """
        scores = []
        for m in msgs:
            agent = m.get("from_agent", "")
            role = agent.split(":")[-1].lower().replace("_", " ") if ":" in agent else agent.lower()
            content_words = set(str(m.get("content", "")).lower().split())

            # Find best matching role domain
            best_match = 0.0
            for role_key, domain in self.ROLE_KEYWORDS.items():
                if role_key in role or role in role_key:
                    if domain:
                        match = len(content_words & domain) / len(domain)
                        best_match = max(best_match, match)

            if best_match > 0:
                scores.append(min(1.0, best_match * 3))  # Scale: 33% keyword match = good
            # If no role mapping found, skip (don't penalize unknown roles)

        return sum(scores) / max(len(scores), 1) if scores else 0.7

    def _conv_task_drift(self, msgs: List[Dict]) -> float:
        """Does the conversation stay focused on the original task?

        Compares each message to the task description (first message).
        """
        if len(msgs) < 2:
            return 1.0

        # First message is typically the task description
        task_content = str(msgs[0].get("content", ""))
        stop = {
            "the", "a", "an", "is", "are", "was", "for", "of", "to", "in",
            "and", "or", "it", "this", "that", "with", "on", "at", "by",
        }
        task_words = {w.lower() for w in task_content.split() if len(w) > 3 and w.lower() not in stop}

        if not task_words:
            return 0.7

        scores = []
        for m in msgs[1:]:
            content = str(m.get("content", ""))
            msg_words = set(content.lower().split())
            overlap = len(task_words & msg_words) / len(task_words)
            scores.append(min(1.0, overlap * 3))  # 33% task-word reference = on-topic

        return sum(scores) / max(len(scores), 1)

    # ── Helpers ──────────────────────────────────────────────────────

    def _compute_critical_path(self, agent_states: Dict[str, List[Dict]]) -> List[str]:
        """Return agents in order of first appearance."""
        if not agent_states:
            return []
        agent_first_seq = {}
        for aid, ast in agent_states.items():
            seqs = [s.get("sequence_num", 0) for s in ast]
            agent_first_seq[aid] = min(seqs) if seqs else 0
        return sorted(agent_first_seq.keys(), key=lambda a: agent_first_seq[a])

    @staticmethod
    def _state_to_text(state: Dict) -> str:
        """Extract text content from a state dict."""
        parts = []
        delta = state.get("state_delta", {})
        if isinstance(delta, dict):
            for v in delta.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, (list, dict)):
                    parts.append(str(v)[:200])
        output = state.get("output", "")
        if output:
            parts.append(str(output)[:200])
        return " ".join(parts)


def detect(
    states: List[Dict[str, Any]] = None,
    messages: List[Dict[str, Any]] = None,
    agent_ids: List[str] = None,
) -> Tuple[bool, float, OrchestrationScore]:
    """Dual-mode detection: auto-detects execution traces vs conversations.

    Args:
        states: Execution trace states (LangGraph, n8n) — structured mode
        messages: Conversation messages (MAST, ChatDev) — conversation mode
        agent_ids: Optional list of agent IDs (for conversation mode)
    """
    scorer = OrchestrationQualityScorer()

    if messages is not None:
        result = scorer.score_conversation(messages, agent_ids)
        # Conversation mode: calibrated on MAST data, optimal threshold 0.70
        threshold = 0.70
        dim_floor = 0.35
    elif states is not None:
        result = scorer.score(states)
        # Execution mode: calibrated on LangGraph data, optimal threshold 0.80
        threshold = 0.80
        dim_floor = 0.40
    else:
        return False, 0.0, OrchestrationScore(overall=1.0, issues=["No input"])

    dim_values = list(result.dimensions.values())
    low_dims = sum(1 for d in dim_values if d < dim_floor)

    detected = result.overall < threshold or low_dims >= 2

    if detected:
        min_dim = min(dim_values) if dim_values else 0.5
        conf_overall = max(0.0, (threshold - result.overall) / threshold)
        conf_dims = max(0.0, (dim_floor - min_dim) / dim_floor) if min_dim < dim_floor else 0.0
        confidence = max(conf_overall, conf_dims)
    else:
        confidence = 0.0

    return detected, round(confidence, 4), result
