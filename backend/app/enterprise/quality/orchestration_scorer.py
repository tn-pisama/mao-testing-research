"""Orchestration quality scorer with complexity metrics."""

import json
from collections import defaultdict
from typing import Dict, Any, List, Optional, Set, Tuple
from .models import (
    OrchestrationQualityScore,
    DimensionScore,
    ComplexityMetrics,
    OrchestrationDimension,
)
from .agent_scorer import AI_NODE_TYPES, LM_CONFIG_NODE_TYPES
from .error_codes import get_error_code


# Orchestration pattern thresholds
PATTERN_THRESHOLDS = {
    "linear": {"max_nodes": 10, "max_depth": 3, "expected_coupling": 0.2},
    "parallel": {"max_branches": 5, "max_depth": 4, "expected_coupling": 0.3},
    "conditional": {"max_depth": 4, "max_branches": 3, "expected_coupling": 0.4},
    "pipeline": {"max_stages": 7, "max_depth": 5, "expected_coupling": 0.5},
    "loop": {"max_iterations": 10, "max_depth": 4, "expected_coupling": 0.6},
}

# Node types that indicate observability
OBSERVABILITY_NODE_TYPES = {
    "n8n-nodes-base.set",  # Can be used for checkpoints
    "n8n-nodes-base.code",  # Can contain logging
    "n8n-nodes-base.httpRequest",  # Can send to monitoring
    "n8n-nodes-base.errorTrigger",
    "n8n-nodes-base.noOp",
}

# Best practice config flags
BEST_PRACTICE_FLAGS = {
    "retryOnFail": True,
    "continueOnFail": True,
    "timeout": True,
}


class OrchestrationQualityScorer:
    """
    Scores workflow architecture quality across five dimensions:
    1. Data Flow Clarity - Explicit vs implicit state passing
    2. Complexity Management - Node count vs task complexity
    3. Agent Coupling - Independence vs interdependence balance
    4. Observability - Checkpoints, logging, monitoring
    5. Best Practices - Retry, timeout, rate limiting

    Supports two-tier scoring:
    - Tier 1 (fast): Heuristic structural analysis (~1ms)
    - Tier 2 (deep): LLM judge for semantic evaluation (~1-2s)

    When use_llm_judge=True, ALL 5 core dimensions get LLM evaluation.
    When use_llm_judge=False but a dimension score falls in the
    escalation_range, it can optionally be escalated to LLM.
    """

    def __init__(
        self,
        use_llm_judge: Optional[bool] = None,
        judge_model: str = "claude-3-5-haiku-20241022",
        escalation_range: tuple = (0.35, 0.65),
    ):
        import os
        if use_llm_judge is None:
            use_llm_judge = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))
        self.use_llm_judge = use_llm_judge
        self.judge_model = judge_model
        self.escalation_range = escalation_range
        self._judge = None
        if use_llm_judge:
            try:
                from ..evals.llm_judge import LLMJudge, JudgeModel
                model = JudgeModel(judge_model) if judge_model in [m.value for m in JudgeModel] else JudgeModel.CLAUDE_HAIKU
                self._judge = LLMJudge(model=model)
            except Exception:
                pass  # LLM judge unavailable, fall back to heuristic-only

    def _has_ai_language_model_input(self, node: Dict[str, Any], workflow: Dict[str, Any]) -> bool:
        """Check if a node has incoming ai_languageModel connections (sub-node LLM provider)."""
        node_name = node.get("name", "")
        connections = workflow.get("connections", {})
        for src_name, conn_data in connections.items():
            if not isinstance(conn_data, dict):
                continue
            for output_group in conn_data.get("ai_languageModel", []):
                if isinstance(output_group, list):
                    for conn in output_group:
                        if isinstance(conn, dict) and conn.get("node") == node_name:
                            return True
        return False

    def _find_agent_nodes(self, workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find agent nodes by type AND by incoming ai_languageModel connections."""
        nodes = workflow.get("nodes", [])
        agent_nodes = []
        for n in nodes:
            node_type = n.get("type", "")
            # Skip LM config nodes — they are model settings, not agents
            if node_type in LM_CONFIG_NODE_TYPES:
                continue
            if node_type in AI_NODE_TYPES:
                agent_nodes.append(n)
            elif self._has_ai_language_model_input(n, workflow):
                agent_nodes.append(n)
        return agent_nodes

    def score_orchestration(
        self,
        workflow: Dict[str, Any],
        execution_history: Optional[List[Dict[str, Any]]] = None,
        include_reasoning: bool = False,
    ) -> OrchestrationQualityScore:
        """Score workflow orchestration quality across all dimensions."""
        workflow_id = workflow.get("id", "unknown")
        workflow_name = workflow.get("name", "Unnamed Workflow")

        # Calculate complexity metrics
        complexity_metrics = self._calculate_complexity_metrics(workflow)

        # Detect orchestration pattern
        detected_pattern = self._detect_pattern(workflow, complexity_metrics)

        dimensions: List[DimensionScore] = []

        # Score each dimension (heuristic first)
        dim_data_flow = self._score_data_flow_clarity(workflow)
        dim_complexity = self._score_complexity_management(workflow, complexity_metrics, detected_pattern)
        dim_coupling = self._score_agent_coupling(workflow, complexity_metrics)
        dim_observability = self._score_observability(workflow)
        dim_best_practices = self._score_best_practices(workflow)

        core_dims = [dim_data_flow, dim_complexity, dim_coupling, dim_observability, dim_best_practices]

        # LLM blending: if LLM judge is available, enhance scores with semantic evaluation
        if self._judge:
            try:
                llm_scores = self._llm_score_orchestration(workflow, complexity_metrics, detected_pattern)
                if llm_scores:
                    dim_map = {
                        "data_flow_score": dim_data_flow,
                        "complexity_score": dim_complexity,
                        "coupling_score": dim_coupling,
                        "observability_score": dim_observability,
                        "best_practices_score": dim_best_practices,
                    }
                    for key, dim_obj in dim_map.items():
                        if self._should_use_llm(dim_obj.score) and key in llm_scores:
                            llm_result = {
                                "score": llm_scores[key],
                                "reasoning": llm_scores.get("overall_assessment", ""),
                                "tokens": llm_scores.get("tokens", 0),
                            }
                            dim_obj.score = self._blend_scores(dim_obj.score, llm_result, dim_obj)
                            dim_obj.confidence = 0.8
                        else:
                            dim_obj.evidence["scoring_tier"] = "heuristic"
                            dim_obj.confidence = 0.6
            except Exception:
                for dim_obj in core_dims:
                    dim_obj.evidence["scoring_tier"] = "heuristic_fallback"
                    dim_obj.confidence = 0.6

        dimensions.extend(core_dims)

        # n8n-specific dimensions
        doc_score = self._score_documentation_quality(workflow)
        if doc_score:
            dimensions.append(doc_score)

        ai_arch_score = self._score_ai_architecture(workflow)
        if ai_arch_score:
            dimensions.append(ai_arch_score)

        maint_score = self._score_maintenance_quality(workflow)
        if maint_score:
            dimensions.append(maint_score)

        test_cov_score = self._score_test_coverage(workflow)
        if test_cov_score:
            dimensions.append(test_cov_score)

        layout_score = self._score_layout_quality(workflow)
        if layout_score:
            dimensions.append(layout_score)

        # Calculate overall score
        total_weight = sum(d.weight for d in dimensions)
        overall_score = sum(d.score * d.weight for d in dimensions) / total_weight if total_weight > 0 else 0.0

        # Collect issues
        all_issues = []
        critical_issues = []
        for dim in dimensions:
            all_issues.extend(dim.issues)
            if dim.score < 0.4:
                critical_issues.extend(dim.issues[:1])

        # Generate reasoning if requested
        reasoning = None
        if include_reasoning:
            reasoning = self._generate_orchestration_reasoning(
                workflow_name, overall_score, detected_pattern,
                complexity_metrics, dimensions, critical_issues
            )

        return OrchestrationQualityScore(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            overall_score=overall_score,
            dimensions=dimensions,
            complexity_metrics=complexity_metrics,
            issues_count=len(all_issues),
            critical_issues=critical_issues,
            detected_pattern=detected_pattern,
            reasoning=reasoning,
        )

    def _generate_orchestration_reasoning(
        self,
        workflow_name: str,
        overall_score: float,
        detected_pattern: str,
        complexity_metrics: ComplexityMetrics,
        dimensions: List[DimensionScore],
        critical_issues: List[str],
    ) -> str:
        """Generate natural-language reasoning for orchestration quality score."""
        from .models import _score_to_grade

        grade = _score_to_grade(overall_score)
        parts = [
            f"Workflow '{workflow_name}' orchestration scored {overall_score:.0%} ({grade}).",
            f"Pattern: {detected_pattern}, {complexity_metrics.node_count} nodes, "
            f"{complexity_metrics.agent_count} agents, depth {complexity_metrics.max_depth}.",
        ]

        # Summarize top dimensions (lowest scores first)
        sorted_dims = sorted(dimensions, key=lambda d: d.score)
        for dim in sorted_dims[:3]:
            dim_name = dim.dimension.replace("_", " ").title()
            dim_summary = f"{dim_name}: {dim.score:.0%}"
            if dim.issues:
                dim_summary += f" — {dim.issues[0]}"
            parts.append(dim_summary)

        if critical_issues:
            parts.append(f"Critical: {'; '.join(critical_issues[:3])}")

        return " ".join(parts)

    def _calculate_complexity_metrics(self, workflow: Dict[str, Any]) -> ComplexityMetrics:
        """Calculate various complexity metrics for the workflow."""
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})

        # Count nodes by type
        node_count = len(nodes)
        # Count actual agents (by type AND by ai_languageModel connections)
        agent_nodes = self._find_agent_nodes(workflow)
        agent_count = len(agent_nodes)
        ai_node_ratio = agent_count / node_count if node_count > 0 else 0.0

        # Count connections
        connection_count = 0
        for node_conns in connections.values():
            if isinstance(node_conns, dict):
                for output_type, targets in node_conns.items():
                    if isinstance(targets, list):
                        connection_count += len(targets)

        # Calculate depth and branching
        max_depth, parallel_branches, conditional_branches = self._analyze_graph_structure(workflow)

        # Calculate cyclomatic complexity: E - N + 2P
        # E = edges, N = nodes, P = connected components (assume 1)
        cyclomatic_complexity = connection_count - node_count + 2

        # Calculate coupling ratio
        coupling_ratio = self._calculate_coupling_ratio(workflow)

        return ComplexityMetrics(
            node_count=node_count,
            agent_count=agent_count,
            connection_count=connection_count,
            max_depth=max_depth,
            cyclomatic_complexity=max(cyclomatic_complexity, 1),
            coupling_ratio=coupling_ratio,
            ai_node_ratio=ai_node_ratio,
            parallel_branches=parallel_branches,
            conditional_branches=conditional_branches,
        )

    def _analyze_graph_structure(self, workflow: Dict[str, Any]) -> Tuple[int, int, int]:
        """Analyze graph structure for depth and branching."""
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})

        if not nodes:
            return 0, 0, 0

        # Build adjacency list
        node_ids = {n.get("name", n.get("id")): i for i, n in enumerate(nodes)}
        adj: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = defaultdict(int)

        for source_name, node_conns in connections.items():
            if isinstance(node_conns, dict):
                for output_type, targets in node_conns.items():
                    if isinstance(targets, list):
                        for target_list in targets:
                            if isinstance(target_list, list):
                                for target in target_list:
                                    if isinstance(target, dict):
                                        target_name = target.get("node", "")
                                        adj[source_name].append(target_name)
                                        in_degree[target_name] += 1

        # Find start nodes (in_degree = 0)
        all_nodes = set(n.get("name", n.get("id")) for n in nodes)
        start_nodes = [n for n in all_nodes if in_degree.get(n, 0) == 0]

        if not start_nodes:
            start_nodes = list(all_nodes)[:1]

        # BFS for max depth
        max_depth = 0
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = [(n, 0) for n in start_nodes]

        while queue:
            node, depth = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            max_depth = max(max_depth, depth)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

        # Count parallel branches (nodes with multiple outgoing edges)
        parallel_branches = sum(1 for n, targets in adj.items() if len(targets) > 1)

        # Count conditional branches (IF nodes or switch nodes)
        conditional_branches = sum(
            1 for n in nodes
            if any(kw in n.get("type", "").lower() for kw in ["if", "switch", "filter"])
        )

        return max_depth, parallel_branches, conditional_branches

    def _calculate_coupling_ratio(self, workflow: Dict[str, Any]) -> float:
        """Calculate agent coupling ratio based on direct connections."""
        connections = workflow.get("connections", {})

        agent_nodes = self._find_agent_nodes(workflow)
        if len(agent_nodes) < 2:
            return 0.0

        agent_names = {n.get("name", n.get("id")) for n in agent_nodes}

        # Count agent-to-agent connections
        agent_connections = 0
        possible_connections = len(agent_nodes) * (len(agent_nodes) - 1)

        for source_name, node_conns in connections.items():
            if source_name not in agent_names:
                continue

            if isinstance(node_conns, dict):
                for output_type, targets in node_conns.items():
                    if isinstance(targets, list):
                        for target_list in targets:
                            if isinstance(target_list, list):
                                for target in target_list:
                                    if isinstance(target, dict):
                                        target_name = target.get("node", "")
                                        if target_name in agent_names:
                                            agent_connections += 1

        return agent_connections / possible_connections if possible_connections > 0 else 0.0

    def _detect_pattern(self, workflow: Dict[str, Any], metrics: ComplexityMetrics) -> str:
        """Detect the primary orchestration pattern."""
        nodes = workflow.get("nodes", [])

        # Check for loop pattern (loop/iterate nodes)
        has_loops = any(
            "loop" in n.get("type", "").lower() or "iterate" in n.get("type", "").lower()
            for n in nodes
        )
        if has_loops:
            return "loop"

        # Check for parallel pattern (merge nodes or high parallel branches)
        has_merge = any("merge" in n.get("type", "").lower() for n in nodes)
        if has_merge or metrics.parallel_branches >= 2:
            return "parallel"

        # Check for conditional pattern
        if metrics.conditional_branches >= 2:
            return "conditional"

        # Check for pipeline (deep, sequential)
        if metrics.max_depth >= 4 and metrics.parallel_branches <= 1:
            return "pipeline"

        # Default to linear
        return "linear"

    def _score_data_flow_clarity(self, workflow: Dict[str, Any]) -> DimensionScore:
        """
        Score data flow clarity.

        Checks for:
        - Explicit parameter passing vs global state
        - Clear input/output contracts
        - Variable naming clarity
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.7  # Default reasonable score

        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})

        # Check for explicit connections
        total_nodes = len(nodes)
        connected_nodes = len(connections)
        evidence["total_nodes"] = total_nodes
        evidence["nodes_with_connections"] = connected_nodes

        # Initialize connection_coverage to avoid UnboundLocalError with empty workflows
        connection_coverage = 0.0

        df_error_codes = []
        if total_nodes > 0:
            connection_coverage = connected_nodes / total_nodes
            evidence["connection_coverage"] = connection_coverage

            if connection_coverage < 0.5:
                issues.append("Many nodes have no explicit connections")
                suggestions.append("Ensure all nodes have clear input/output connections")
                score -= 0.2
                df_error_codes.append("QE-DF-001")

        # Check for Set/Code nodes that might be passing implicit state
        # Only count "empty" Set nodes (no meaningful field mappings) and
        # Code nodes with no actual code — configured nodes are doing useful work.
        empty_manipulation_nodes = sum(
            1 for n in nodes
            if (n.get("type") == "n8n-nodes-base.set" and not n.get("parameters", {}).get("assignments"))
            or (n.get("type") == "n8n-nodes-base.code" and not (n.get("parameters", {}).get("jsCode") or n.get("parameters", {}).get("code")))
        )
        evidence["state_manipulation_nodes"] = empty_manipulation_nodes

        if empty_manipulation_nodes > total_nodes * 0.5:
            issues.append("High ratio of state manipulation nodes")
            suggestions.append("Consider reducing implicit state passing")
            score -= 0.15
            df_error_codes.append("QE-DF-003")

        # Check for descriptive node names
        generic_names = sum(
            1 for n in nodes
            if any(
                generic in n.get("name", "").lower()
                for generic in ["node", "unnamed", "set", "code"]
            )
        )
        evidence["generic_node_names"] = generic_names

        if generic_names > total_nodes * 0.3:
            issues.append(f"{generic_names} nodes have generic/unclear names")
            suggestions.append("Use descriptive names for nodes to clarify data flow")
            score -= 0.1
            df_error_codes.append("QE-DF-002")

        # Boost for well-structured workflows
        if connection_coverage > 0.8 and generic_names < total_nodes * 0.2:
            score += 0.2

        if df_error_codes:
            evidence["error_codes"] = df_error_codes

        return DimensionScore(
            dimension=OrchestrationDimension.DATA_FLOW_CLARITY.value,
            score=min(max(score, 0.0), 1.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_complexity_management(
        self,
        workflow: Dict[str, Any],
        metrics: ComplexityMetrics,
        pattern: str,
    ) -> DimensionScore:
        """
        Score complexity management.

        Checks for:
        - Appropriate node count for pattern
        - Manageable depth
        - Reasonable cyclomatic complexity
        """
        issues = []
        suggestions = []
        evidence = {
            "pattern": pattern,
            "node_count": metrics.node_count,
            "cyclomatic_complexity": metrics.cyclomatic_complexity,
            "max_depth": metrics.max_depth,
        }
        score = 1.0

        thresholds = PATTERN_THRESHOLDS.get(pattern, PATTERN_THRESHOLDS["linear"])

        cm_error_codes = []

        # Check node count
        max_nodes = thresholds.get("max_nodes", 10)
        if metrics.node_count > max_nodes:
            score -= 0.2
            issues.append(f"Workflow has {metrics.node_count} nodes (recommended max: {max_nodes} for {pattern} pattern)")
            suggestions.append("Consider breaking into sub-workflows")
            cm_error_codes.append("QE-CM-001")

        # Check depth
        max_depth = thresholds.get("max_depth", 5)
        if metrics.max_depth > max_depth:
            score -= 0.2
            issues.append(f"Workflow depth ({metrics.max_depth}) exceeds recommended ({max_depth})")
            suggestions.append("Flatten deep nesting or extract sub-workflows")
            cm_error_codes.append("QE-CM-002")

        # Check cyclomatic complexity
        if metrics.cyclomatic_complexity > 10:
            score -= 0.2
            issues.append(f"High cyclomatic complexity ({metrics.cyclomatic_complexity})")
            suggestions.append("Reduce branching to improve maintainability")
            cm_error_codes.append("QE-CM-003")
        elif metrics.cyclomatic_complexity > 5:
            score -= 0.1

        # Check agent count relative to total
        if metrics.agent_count > 8:
            score -= 0.15
            issues.append(f"Many agents ({metrics.agent_count}) may be hard to coordinate")
            suggestions.append("Consider consolidating agent responsibilities")

        if cm_error_codes:
            evidence["error_codes"] = cm_error_codes

        return DimensionScore(
            dimension=OrchestrationDimension.COMPLEXITY_MANAGEMENT.value,
            score=max(score, 0.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_agent_coupling(
        self,
        workflow: Dict[str, Any],
        metrics: ComplexityMetrics,
    ) -> DimensionScore:
        """
        Score agent coupling/independence.

        Checks for:
        - Direct agent-to-agent coupling
        - Shared state dependencies
        - Single points of failure
        """
        issues = []
        suggestions = []
        evidence = {
            "coupling_ratio": metrics.coupling_ratio,
            "agent_count": metrics.agent_count,
        }
        score = 1.0

        if metrics.agent_count < 2:
            return DimensionScore(
                dimension=OrchestrationDimension.AGENT_COUPLING.value,
                score=0.9,  # Single agent workflows are fine
                issues=issues,
                evidence=evidence,
                suggestions=suggestions,
            )

        ac_error_codes = []

        # Check coupling ratio
        if metrics.coupling_ratio > 0.7:
            score -= 0.3
            issues.append("High agent coupling may cause cascading failures")
            suggestions.append("Add intermediate processing nodes between agents")
            ac_error_codes.append("QE-AC-002")
        elif metrics.coupling_ratio > 0.5:
            score -= 0.15
            suggestions.append("Consider reducing direct agent dependencies")

        # Check for agent chains (A -> B -> C -> D pattern)
        connections = workflow.get("connections", {})
        agent_names = {n.get("name") for n in self._find_agent_nodes(workflow)}

        chain_length = self._detect_agent_chain_length(connections, agent_names)
        evidence["max_agent_chain"] = chain_length

        if chain_length > 4:
            score -= 0.2
            issues.append(f"Long agent chain ({chain_length} agents in sequence)")
            suggestions.append("Add checkpoints or fan-out to reduce chain dependencies")
            ac_error_codes.append("QE-AC-001")

        if ac_error_codes:
            evidence["error_codes"] = ac_error_codes

        return DimensionScore(
            dimension=OrchestrationDimension.AGENT_COUPLING.value,
            score=max(score, 0.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _detect_agent_chain_length(
        self,
        connections: Dict[str, Any],
        agent_names: Set[str],
    ) -> int:
        """Detect the longest chain of consecutive agents."""
        if not agent_names:
            return 0

        # Build agent-only adjacency
        agent_adj: Dict[str, List[str]] = defaultdict(list)

        for source_name, node_conns in connections.items():
            if source_name not in agent_names:
                continue

            if isinstance(node_conns, dict):
                for output_type, targets in node_conns.items():
                    if isinstance(targets, list):
                        for target_list in targets:
                            if isinstance(target_list, list):
                                for target in target_list:
                                    if isinstance(target, dict):
                                        target_name = target.get("node", "")
                                        if target_name in agent_names:
                                            agent_adj[source_name].append(target_name)

        # DFS for longest path
        max_chain = 0
        visited: Set[str] = set()

        def dfs(node: str, depth: int):
            nonlocal max_chain
            max_chain = max(max_chain, depth)
            visited.add(node)

            for neighbor in agent_adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, depth + 1)

            visited.remove(node)

        for start in agent_names:
            dfs(start, 1)

        return max_chain

    def _score_observability(self, workflow: Dict[str, Any]) -> DimensionScore:
        """
        Score observability coverage.

        Checks for:
        - Checkpoint nodes
        - Logging/monitoring nodes
        - Error handling paths
        - State inspection points
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.5  # Start at middle

        nodes = workflow.get("nodes", [])
        total_nodes = len(nodes)

        if total_nodes == 0:
            return DimensionScore(
                dimension=OrchestrationDimension.OBSERVABILITY.value,
                score=0.0,
                issues=["Empty workflow"],
                evidence=evidence,
                suggestions=suggestions,
            )

        # Check for observability nodes
        observability_nodes = sum(
            1 for n in nodes
            if n.get("type") in OBSERVABILITY_NODE_TYPES
        )
        evidence["observability_nodes"] = observability_nodes

        ob_error_codes = []
        obs_ratio = observability_nodes / total_nodes
        if obs_ratio >= 0.2:
            score += 0.2
        elif obs_ratio == 0:
            issues.append("No checkpoint or logging nodes")
            suggestions.append("Add Set nodes as checkpoints for debugging")
            score -= 0.2
            ob_error_codes.append("QE-OB-001")

        # Check for HTTP nodes that might be monitoring webhooks
        http_nodes = [n for n in nodes if n.get("type") == "n8n-nodes-base.httpRequest"]
        monitoring_webhooks = sum(
            1 for n in http_nodes
            if any(kw in str(n.get("parameters", {})).lower() for kw in ["webhook", "monitor", "log", "mao"])
        )
        evidence["monitoring_webhooks"] = monitoring_webhooks

        if monitoring_webhooks > 0:
            score += 0.15
        else:
            ob_error_codes.append("QE-OB-003")

        # Check for error trigger nodes
        error_triggers = sum(
            1 for n in nodes
            if "error" in n.get("type", "").lower()
        )
        evidence["error_triggers"] = error_triggers

        if error_triggers > 0:
            score += 0.15
        else:
            suggestions.append("Add error trigger node for failure alerting")
            ob_error_codes.append("QE-OB-002")

        # Check agent nodes have alwaysOutputData
        agent_nodes = self._find_agent_nodes(workflow)
        agents_with_output = sum(1 for n in agent_nodes if n.get("alwaysOutputData", False))
        evidence["agents_with_always_output"] = agents_with_output

        if agent_nodes and agents_with_output == len(agent_nodes):
            score += 0.1
        elif agent_nodes and agents_with_output == 0:
            suggestions.append("Enable 'Always Output Data' on agent nodes for debugging")

        if ob_error_codes:
            evidence["error_codes"] = ob_error_codes

        return DimensionScore(
            dimension=OrchestrationDimension.OBSERVABILITY.value,
            score=min(max(score, 0.0), 1.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_best_practices(self, workflow: Dict[str, Any]) -> DimensionScore:
        """
        Score adherence to workflow-level best practices.

        BOUNDARY CLARIFICATION:
        This scores WORKFLOW-WIDE operational patterns, not individual node config.
        It answers: "Does the workflow have robust error handling architecture?"

        This is distinct from agent-level error handling scoring, which evaluates
        whether each node can individually recover from failures.

        Orchestration best practices (this method):
        - Global error handler presence (workflow-level catch-all)
        - Error branching patterns (dedicated error flows)
        - Coverage uniformity (are best practices consistently applied?)
        - Workflow settings for error data preservation

        Agent error handling (separate scorer):
        - Per-node retry/timeout/continueOnFail configuration
        - Individual node failure recovery capability

        Checks for:
        - Global error handler (25%) - workflow-level error catching
        - Error branching coverage (20%) - dedicated error flows
        - Configuration uniformity (15%) - consistent patterns across workflow
        - Workflow settings (15%) - error data preservation
        - Basic coverage reference (25%) - high-level coverage health
        """
        issues = []
        suggestions = []
        evidence = {}
        score = 0.0

        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        ai_nodes = self._find_agent_nodes(workflow)

        if not ai_nodes:
            return DimensionScore(
                dimension=OrchestrationDimension.BEST_PRACTICES.value,
                score=0.8,  # Non-AI workflows have fewer requirements
                issues=issues,
                evidence=evidence,
                suggestions=suggestions,
            )

        # NEW: Check for global error handler (workflow-level error catching)
        # This is an orchestration-level concern - having a catch-all for errors
        has_global_error_handler = any(
            "error" in n.get("type", "").lower() or
            n.get("type") == "n8n-nodes-base.errorTrigger"
            for n in nodes
        )
        evidence["has_global_error_handler"] = has_global_error_handler

        bp_error_codes = []
        if has_global_error_handler:
            score += 0.25
        else:
            issues.append("No global error handler in workflow")
            suggestions.append("Add an Error Trigger node to catch workflow-level failures")
            bp_error_codes.append("QE-BP-001")

        # NEW: Check for error branching patterns (dedicated error handling flows)
        # Count nodes that have explicit error output connections
        nodes_with_error_branches = 0
        for node_name, node_conns in connections.items():
            if isinstance(node_conns, dict):
                # Check if this node has error-specific outputs
                if "error" in node_conns or any(
                    "error" in str(output_key).lower()
                    for output_key in node_conns.keys()
                ):
                    nodes_with_error_branches += 1

        evidence["nodes_with_error_branches"] = nodes_with_error_branches
        error_branch_ratio = nodes_with_error_branches / len(nodes) if nodes else 0

        if error_branch_ratio >= 0.2:
            score += 0.20
        elif error_branch_ratio > 0:
            score += 0.10
        else:
            suggestions.append("Consider adding error branching for critical nodes")

        # Check configuration uniformity across AI nodes
        # (Do nodes consistently use the same patterns?)
        nodes_with_retry = sum(
            1 for n in ai_nodes
            if n.get("parameters", {}).get("options", {}).get("retryOnFail") or n.get("retryOnFail")
        )
        nodes_with_timeout = sum(
            1 for n in ai_nodes
            if n.get("parameters", {}).get("options", {}).get("timeout") or n.get("parameters", {}).get("timeout")
        )

        evidence["ai_nodes"] = len(ai_nodes)
        evidence["nodes_with_retry"] = nodes_with_retry
        evidence["nodes_with_timeout"] = nodes_with_timeout

        # Score uniformity - either all have it or none (consistent pattern)
        if len(ai_nodes) > 0:
            retry_coverage = nodes_with_retry / len(ai_nodes)
            timeout_coverage = nodes_with_timeout / len(ai_nodes)

            # Reward uniformity (all or none) rather than just coverage
            # This is an orchestration concern - consistent patterns
            retry_uniformity = 1.0 if retry_coverage in [0, 1.0] else (0.5 + retry_coverage * 0.3)
            timeout_uniformity = 1.0 if timeout_coverage in [0, 1.0] else (0.5 + timeout_coverage * 0.3)

            uniformity_score = (retry_uniformity + timeout_uniformity) / 2
            score += uniformity_score * 0.15
            evidence["config_uniformity"] = uniformity_score

            if retry_coverage > 0 and retry_coverage < 1.0:
                suggestions.append("Apply retry configuration consistently across all AI nodes")
                bp_error_codes.append("QE-BP-002")

        # Check workflow-level settings
        settings = workflow.get("settings", {})
        workflow_settings_score = 0.0

        if settings.get("saveManualExecutions"):
            workflow_settings_score += 0.5
        if settings.get("saveDataErrorExecution") == "all":
            workflow_settings_score += 0.5

        score += workflow_settings_score * 0.15
        evidence["workflow_settings_score"] = workflow_settings_score

        # Basic coverage health reference (high-level indicator, not per-node scoring)
        # This is a sanity check, not the primary scoring factor
        if len(ai_nodes) > 0:
            basic_coverage = (nodes_with_retry + nodes_with_timeout) / (len(ai_nodes) * 2)
            score += basic_coverage * 0.25
            evidence["basic_coverage"] = basic_coverage

            # Only flag as issue if severely lacking
            if basic_coverage < 0.25:
                issues.append("Workflow lacks basic resilience configuration")

        if bp_error_codes:
            evidence["error_codes"] = bp_error_codes

        return DimensionScore(
            dimension=OrchestrationDimension.BEST_PRACTICES.value,
            score=min(score, 1.0),
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_documentation_quality(self, workflow: Dict[str, Any]) -> Optional[DimensionScore]:
        """
        Score based on sticky note presence and content.

        Checks for:
        - Presence of sticky notes
        - Substantive content in notes
        - Multiple documentation sections
        """
        nodes = workflow.get("nodes", [])
        sticky_notes = [n for n in nodes if n.get("type") == "n8n-nodes-base.stickyNote"]

        # Only score if workflow has nodes
        if not nodes:
            return None

        issues = []
        suggestions = []
        evidence = {}
        score = 0.5  # Base score

        evidence["sticky_note_count"] = len(sticky_notes)
        evidence["total_nodes"] = len(nodes)

        if not sticky_notes:
            issues.append("No documentation (sticky notes) found")
            suggestions.append("Add sticky notes to document workflow sections")
            score = 0.3
        else:
            score += 0.2  # Has documentation

            # Check for substantive content
            total_content = sum(
                len(n.get("parameters", {}).get("content", ""))
                for n in sticky_notes
            )
            evidence["total_documentation_chars"] = total_content

            if total_content > 200:
                score += 0.2  # Good documentation
                if total_content > 500:
                    score += 0.1  # Excellent documentation
            else:
                suggestions.append("Expand documentation with more details")

            # Check for multiple sections
            if len(sticky_notes) >= 3:
                score += 0.1  # Multiple sections documented
            elif len(sticky_notes) == 1:
                suggestions.append("Consider adding more sticky notes for different sections")

        return DimensionScore(
            dimension=OrchestrationDimension.DOCUMENTATION_QUALITY.value,
            score=min(score, 1.0),
            weight=0.8,
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_ai_architecture(self, workflow: Dict[str, Any]) -> Optional[DimensionScore]:
        """
        Score AI-specific connection patterns.

        Checks for:
        - AI-specific connection types (ai_languageModel, ai_tool, ai_memory, etc.)
        - Sophisticated AI architecture
        - Proper use of AI components
        """
        connections = workflow.get("connections", {})
        nodes = workflow.get("nodes", [])

        # Check if this is an AI workflow
        ai_nodes = [
            n for n in nodes
            if "@n8n/n8n-nodes-langchain" in n.get("type", "") or "langchain" in n.get("type", "").lower()
        ]

        if not ai_nodes:
            return None  # Not an AI workflow, don't score this dimension

        issues = []
        suggestions = []
        evidence = {}

        ai_connection_types = {
            "ai_languageModel",
            "ai_tool",
            "ai_memory",
            "ai_retriever",
            "ai_embedding",
            "ai_outputParser",
            "ai_textSplitter",
            "ai_vectorStore",
        }

        # Count AI-specific connections
        ai_connections = 0
        connection_types_used = set()

        for node_connections in connections.values():
            if isinstance(node_connections, dict):
                for conn_type, conns in node_connections.items():
                    if conn_type in ai_connection_types:
                        if isinstance(conns, list):
                            ai_connections += len(conns)
                            connection_types_used.add(conn_type)

        evidence["ai_node_count"] = len(ai_nodes)
        evidence["ai_connections"] = ai_connections
        evidence["ai_connection_types_used"] = list(connection_types_used)
        evidence["unique_ai_connection_types"] = len(connection_types_used)

        # Score based on AI architecture sophistication
        score = 0.5  # Base score for having AI nodes

        if ai_connections == 0:
            issues.append("AI nodes present but no specialized AI connections configured")
            suggestions.append("Connect AI nodes using ai_languageModel, ai_tool, or ai_memory connections")
            score = 0.4
        else:
            # More connections = more sophisticated
            score += min(ai_connections * 0.05, 0.25)

            # Diversity of connection types
            if len(connection_types_used) >= 3:
                score += 0.15  # Using multiple AI component types
            elif len(connection_types_used) >= 2:
                score += 0.10

            # Check for best practices
            if "ai_memory" in connection_types_used:
                score += 0.05  # Has memory
            else:
                suggestions.append("Consider adding memory to AI agents for context persistence")

            if "ai_tool" in connection_types_used:
                score += 0.05  # Has tools
            else:
                suggestions.append("Consider adding tools to AI agents for enhanced capabilities")

        return DimensionScore(
            dimension=OrchestrationDimension.AI_ARCHITECTURE.value,
            score=min(score, 1.0),
            weight=0.9,
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_maintenance_quality(self, workflow: Dict[str, Any]) -> Optional[DimensionScore]:
        """
        Score workflow maintainability.

        Checks for:
        - Disabled nodes (dead code)
        - Outdated typeVersions
        - Unconfigured credentials
        """
        nodes = workflow.get("nodes", [])

        if not nodes:
            return None

        issues = []
        suggestions = []
        evidence = {}
        score = 1.0

        # Check for disabled nodes (dead code)
        disabled = [n for n in nodes if n.get("disabled")]
        evidence["disabled_nodes"] = len(disabled)

        if disabled:
            score -= 0.2
            issues.append(f"{len(disabled)} disabled node(s) left in workflow")
            suggestions.append("Remove or re-enable disabled nodes to reduce confusion")

        # Check for outdated typeVersions
        old_versions = [n for n in nodes if n.get("typeVersion", 1) < 1]
        evidence["outdated_nodes"] = len(old_versions)

        if old_versions:
            score -= 0.1
            issues.append(f"{len(old_versions)} node(s) using deprecated versions")
            suggestions.append("Update nodes to latest typeVersion for bug fixes and features")

        # Check credential configuration
        unconfigured_creds = []
        for n in nodes:
            creds = n.get("credentials", {})
            for name, config in creds.items():
                if isinstance(config, dict) and not config.get("id"):
                    unconfigured_creds.append(name)

        evidence["unconfigured_credentials"] = len(unconfigured_creds)

        if unconfigured_creds:
            score -= 0.15
            issues.append(f"{len(unconfigured_creds)} unconfigured credential(s)")
            suggestions.append("Configure all credentials before deployment")

        # Check for workflow metadata
        has_description = bool(workflow.get("meta", {}).get("description"))
        evidence["has_workflow_description"] = has_description

        if not has_description:
            score -= 0.05
            suggestions.append("Add workflow description in metadata for better maintainability")

        return DimensionScore(
            dimension=OrchestrationDimension.MAINTENANCE_QUALITY.value,
            score=max(score, 0.0),
            weight=0.7,
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _score_test_coverage(self, workflow: Dict[str, Any]) -> Optional[DimensionScore]:
        """
        Score based on pinData presence (test data).

        Checks for:
        - Presence of pinData on nodes
        - Coverage ratio of nodes with test data
        """
        nodes = workflow.get("nodes", [])

        if not nodes:
            return None

        issues = []
        suggestions = []
        evidence = {}

        # Check for pinData on nodes
        nodes_with_test_data = [n for n in nodes if n.get("pinData")]
        evidence["nodes_with_test_data"] = len(nodes_with_test_data)
        evidence["total_nodes"] = len(nodes)

        if not nodes_with_test_data:
            return DimensionScore(
                dimension=OrchestrationDimension.TEST_COVERAGE.value,
                score=0.4,
                weight=0.6,
                issues=["No test data (pinData) found"],
                suggestions=["Add test data to key nodes for debugging"],
                evidence=evidence,
            )

        coverage_ratio = len(nodes_with_test_data) / len(nodes)
        evidence["coverage_ratio"] = coverage_ratio
        score = min(0.5 + (coverage_ratio * 0.5), 1.0)

        if coverage_ratio < 0.3:
            suggestions.append("Increase test data coverage on more nodes")
        elif coverage_ratio >= 0.7:
            # Good coverage
            pass
        else:
            suggestions.append("Consider adding test data to more critical nodes")

        return DimensionScore(
            dimension=OrchestrationDimension.TEST_COVERAGE.value,
            score=score,
            weight=0.6,
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)

    def _score_layout_quality(self, workflow: Dict[str, Any]) -> Optional[DimensionScore]:
        """
        Score layout organization based on node positions.

        Checks for:
        - Overlapping nodes
        - Layout organization (grid alignment)
        - Scattered vs organized layout
        """
        nodes = workflow.get("nodes", [])
        positions = []
        for n in nodes:
            pos = n.get("position", [0, 0])
            # Handle both list [x, y] and dict {"x": x, "y": y} formats
            if isinstance(pos, list):
                x, y = pos[0] if len(pos) > 0 else 0, pos[1] if len(pos) > 1 else 0
            elif isinstance(pos, dict):
                x, y = pos.get("x", 0), pos.get("y", 0)
            else:
                x, y = 0, 0
            positions.append((x, y))

        if len(positions) < 2:
            return None

        issues = []
        suggestions = []
        evidence = {}
        score = 1.0

        # Check for overlapping nodes (same position)
        unique_positions = len(set(positions))
        evidence["total_nodes"] = len(positions)
        evidence["unique_positions"] = unique_positions

        if len(positions) != unique_positions:
            score -= 0.3
            issues.append("Overlapping node positions detected")
            suggestions.append("Ensure all nodes have unique positions")

        # Check for grid alignment (organized layout)
        x_coords = [p[0] for p in positions]
        y_coords = [p[1] for p in positions]

        # Variance check - high variance = scattered layout
        x_variance = self._calculate_variance(x_coords)
        y_variance = self._calculate_variance(y_coords)
        evidence["x_variance"] = x_variance
        evidence["y_variance"] = y_variance

        if x_variance > 100000:  # Threshold for scattered
            score -= 0.2
            issues.append("Scattered horizontal layout")
            suggestions.append("Organize nodes in a more structured layout")

        if y_variance > 100000:
            score -= 0.1
            suggestions.append("Consider aligning nodes vertically for better readability")

        return DimensionScore(
            dimension=OrchestrationDimension.LAYOUT_QUALITY.value,
            score=max(score, 0.0),
            weight=0.4,  # Lower weight - less critical
            issues=issues,
            evidence=evidence,
            suggestions=suggestions,
        )

    # --- LLM-Based Scoring Methods ---

    def _should_use_llm(self, heuristic_score: float) -> bool:
        """Determine if LLM evaluation should be used for this score."""
        if not self._judge:
            return False
        if self.use_llm_judge:
            return True
        # Escalate ambiguous scores
        return self.escalation_range[0] < heuristic_score < self.escalation_range[1]

    def _llm_score_orchestration(
        self,
        workflow: Dict[str, Any],
        complexity_metrics: ComplexityMetrics,
        detected_pattern: str,
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to semantically evaluate all 5 core orchestration dimensions in one call."""
        if not self._judge:
            return None

        from .prompts import format_orchestration_analysis_prompt

        # Build a compact workflow structure summary for the prompt
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        node_summaries = []
        for n in nodes[:30]:  # Cap to avoid prompt explosion
            node_summaries.append(
                f"  - {n.get('name', '?')} ({n.get('type', '?')})"
            )
        conn_summaries = []
        for source, conns in list(connections.items())[:20]:
            if isinstance(conns, dict):
                for output_type, targets in conns.items():
                    if isinstance(targets, list):
                        for target_list in targets:
                            if isinstance(target_list, list):
                                for t in target_list:
                                    if isinstance(t, dict):
                                        conn_summaries.append(
                                            f"  {source} --[{output_type}]--> {t.get('node', '?')}"
                                        )

        workflow_structure = "Nodes:\n" + "\n".join(node_summaries) if node_summaries else "Nodes: (none)"
        if conn_summaries:
            workflow_structure += "\nConnections:\n" + "\n".join(conn_summaries)

        metrics_dict = {
            "node_count": complexity_metrics.node_count,
            "agent_count": complexity_metrics.agent_count,
            "connection_count": complexity_metrics.connection_count,
            "max_depth": complexity_metrics.max_depth,
            "cyclomatic_complexity": complexity_metrics.cyclomatic_complexity,
            "coupling_ratio": round(complexity_metrics.coupling_ratio, 3),
            "ai_node_ratio": round(complexity_metrics.ai_node_ratio, 3),
        }

        prompt = format_orchestration_analysis_prompt(
            workflow_name=workflow.get("name", "Unnamed Workflow"),
            node_count=complexity_metrics.node_count,
            agent_count=complexity_metrics.agent_count,
            detected_pattern=detected_pattern,
            complexity_metrics=metrics_dict,
            workflow_structure=workflow_structure,
        )

        result = self._judge.judge(
            eval_type=None,
            output="",
            custom_prompt=prompt,
        )

        # Parse the structured JSON response
        try:
            parsed = json.loads(result.reasoning) if isinstance(result.reasoning, str) else {}
        except (json.JSONDecodeError, TypeError):
            # Try to extract from the raw result if reasoning isn't JSON
            parsed = {}

        # Use the parsed scores if available, otherwise fall back to the single score
        scores = {
            "data_flow_score": parsed.get("data_flow_score", result.score),
            "complexity_score": parsed.get("complexity_score", result.score),
            "coupling_score": parsed.get("coupling_score", result.score),
            "observability_score": parsed.get("observability_score", result.score),
            "best_practices_score": parsed.get("best_practices_score", result.score),
            "overall_assessment": parsed.get("overall_assessment", result.reasoning or ""),
            "tokens": result.tokens_used,
        }

        return scores

    def _blend_scores(
        self,
        heuristic_score: float,
        llm_result: Optional[Dict[str, Any]],
        dim_score: "DimensionScore",
    ) -> float:
        """Blend heuristic and LLM scores, annotating the dimension with reasoning."""
        if llm_result is None:
            return heuristic_score
        llm_score = llm_result["score"]
        tokens = llm_result.get("tokens", 0)
        reasoning = llm_result.get("reasoning", "")
        # If LLM call failed (0 tokens or API error), fall back to heuristic only
        if tokens == 0 or "API error" in reasoning or "Error" in reasoning[:20]:
            dim_score.evidence["llm_fallback"] = True
            dim_score.evidence["llm_error"] = reasoning
            return heuristic_score
        blended = 0.3 * heuristic_score + 0.7 * llm_score
        dim_score.evidence["llm_score"] = round(llm_score, 3)
        dim_score.evidence["heuristic_score"] = round(heuristic_score, 3)
        dim_score.evidence["llm_reasoning"] = reasoning
        dim_score.evidence["scoring_tier"] = "llm"
        dim_score.evidence["llm_tokens"] = tokens
        return blended
