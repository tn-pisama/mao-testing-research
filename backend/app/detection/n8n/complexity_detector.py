"""
F15: Workflow Complexity Detection for n8n
==========================================

Detects overly complex n8n workflows that are hard to maintain:
- Node count > 50 (workflow too large)
- Branch depth > 10 (deeply nested conditions)
- Cyclomatic complexity > threshold (too many execution paths)
- Execution time consistently > 5 minutes
- Single workflow doing too many unrelated tasks

This is n8n-specific because it analyzes workflow graph structure complexity
rather than conversational interaction complexity.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from app.detection.turn_aware._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)

logger = logging.getLogger(__name__)

# Complexity thresholds
DEFAULT_MAX_NODE_COUNT = 50
DEFAULT_MAX_BRANCH_DEPTH = 10
DEFAULT_MAX_CYCLOMATIC_COMPLEXITY = 20
DEFAULT_MAX_EXECUTION_TIME_MS = 300_000  # 5 minutes

# Node types that indicate branching (increase cyclomatic complexity)
BRANCHING_NODE_TYPES = {
    "n8n-nodes-base.if",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.router",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.split",
}


class N8NComplexityDetector(TurnAwareDetector):
    """Detects F15: Workflow Complexity issues in n8n workflows.

    Analyzes workflow structure for:
    1. Excessive node count (>50 nodes)
    2. Deep branching (>10 levels of conditions)
    3. High cyclomatic complexity (many execution paths)
    4. Long execution times (>5 minutes consistently)
    5. Multiple unrelated concerns in single workflow

    n8n-specific manifestation of F15 (Workflow Complexity):
    In conversational agents, this is about task decomposition.
    In n8n workflows, this is about graph structure and maintainability.
    """

    name = "N8NComplexityDetector"
    version = "1.0"
    supported_failure_modes = ["F15"]

    def __init__(
        self,
        max_node_count: int = DEFAULT_MAX_NODE_COUNT,
        max_branch_depth: int = DEFAULT_MAX_BRANCH_DEPTH,
        max_cyclomatic_complexity: int = DEFAULT_MAX_CYCLOMATIC_COMPLEXITY,
        max_execution_time_ms: int = DEFAULT_MAX_EXECUTION_TIME_MS,
    ):
        """Initialize complexity detector.

        Args:
            max_node_count: Maximum nodes before flagging as too complex
            max_branch_depth: Maximum nesting level of branches
            max_cyclomatic_complexity: Maximum cyclomatic complexity score
            max_execution_time_ms: Maximum execution time threshold
        """
        self.max_node_count = max_node_count
        self.max_branch_depth = max_branch_depth
        self.max_cyclomatic_complexity = max_cyclomatic_complexity
        self.max_execution_time_ms = max_execution_time_ms

    def _detect_excessive_nodes(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect if workflow has too many nodes."""
        node_count = len(turns)

        if node_count > self.max_node_count:
            return {
                "detected": True,
                "type": "excessive_nodes",
                "node_count": node_count,
                "threshold": self.max_node_count,
                "explanation": f"Workflow has {node_count} nodes (threshold: {self.max_node_count})",
                "turns": list(range(len(turns))),
            }

        return None

    def _calculate_branch_depth(self, turns: List[TurnSnapshot]) -> int:
        """Calculate maximum branch depth in workflow."""
        max_depth = 0
        current_depth = 0
        depth_stack = []

        for turn in turns:
            node_type = turn.turn_metadata.get("node_type", "")

            # Branching nodes increase depth
            if node_type in {"n8n-nodes-base.if", "n8n-nodes-base.switch"}:
                depth_stack.append(current_depth)
                current_depth += 1
                max_depth = max(max_depth, current_depth)

            # Merge nodes decrease depth
            elif node_type in {"n8n-nodes-base.merge"}:
                if depth_stack:
                    current_depth = depth_stack.pop()

        return max_depth

    def _detect_deep_branching(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect if workflow has deeply nested branches."""
        branch_depth = self._calculate_branch_depth(turns)

        if branch_depth > self.max_branch_depth:
            return {
                "detected": True,
                "type": "deep_branching",
                "branch_depth": branch_depth,
                "threshold": self.max_branch_depth,
                "explanation": f"Workflow has {branch_depth} levels of nested branches (threshold: {self.max_branch_depth})",
                "turns": [
                    i
                    for i, turn in enumerate(turns)
                    if turn.turn_metadata.get("node_type") in BRANCHING_NODE_TYPES
                ],
            }

        return None

    def _calculate_cyclomatic_complexity(self, turns: List[TurnSnapshot]) -> int:
        """Calculate cyclomatic complexity of workflow.

        Cyclomatic complexity = E - N + 2P where:
        - E = number of edges (connections between nodes)
        - N = number of nodes
        - P = number of connected components (usually 1)

        Simplified: Start at 1, +1 for each branching node
        """
        complexity = 1  # Base complexity

        for turn in turns:
            node_type = turn.turn_metadata.get("node_type", "")
            if node_type in BRANCHING_NODE_TYPES:
                # Each branching node adds at least 1 to complexity
                complexity += 1
                # Switch nodes can add more based on number of cases
                if node_type == "n8n-nodes-base.switch":
                    cases = turn.turn_metadata.get("switch_cases", 2)
                    complexity += max(0, cases - 2)

        return complexity

    def _detect_high_cyclomatic_complexity(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect if workflow has high cyclomatic complexity."""
        complexity = self._calculate_cyclomatic_complexity(turns)

        if complexity > self.max_cyclomatic_complexity:
            return {
                "detected": True,
                "type": "high_cyclomatic_complexity",
                "complexity": complexity,
                "threshold": self.max_cyclomatic_complexity,
                "explanation": f"Workflow has cyclomatic complexity of {complexity} (threshold: {self.max_cyclomatic_complexity})",
                "turns": [
                    i
                    for i, turn in enumerate(turns)
                    if turn.turn_metadata.get("node_type") in BRANCHING_NODE_TYPES
                ],
            }

        return None

    def _detect_long_execution(
        self, turns: List[TurnSnapshot], metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect if workflow consistently takes too long to execute."""
        # Get execution time from metadata
        execution_time_ms = None
        if metadata:
            execution_time_ms = metadata.get("workflow_duration_ms")

        if execution_time_ms is None and turns:
            # Try to calculate from turn timestamps
            if turns[0].turn_metadata.get("timestamp") and turns[
                -1
            ].turn_metadata.get("timestamp"):
                try:
                    from datetime import datetime

                    start = turns[0].turn_metadata["timestamp"]
                    end = turns[-1].turn_metadata["timestamp"]

                    if isinstance(start, str):
                        start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    if isinstance(end, str):
                        end = datetime.fromisoformat(end.replace("Z", "+00:00"))

                    execution_time_ms = int((end - start).total_seconds() * 1000)
                except Exception as e:
                    logger.warning(f"Failed to calculate execution time: {e}")

        if (
            execution_time_ms is not None
            and execution_time_ms > self.max_execution_time_ms
        ):
            return {
                "detected": True,
                "type": "long_execution",
                "execution_time_ms": execution_time_ms,
                "threshold": self.max_execution_time_ms,
                "explanation": f"Workflow took {execution_time_ms / 1000:.1f}s (threshold: {self.max_execution_time_ms / 1000:.1f}s)",
                "turns": list(range(len(turns))),
            }

        return None

    def _detect_multiple_concerns(
        self, turns: List[TurnSnapshot]
    ) -> Optional[Dict[str, Any]]:
        """Detect if workflow handles multiple unrelated concerns.

        Heuristic: Group nodes by type and check if there are many distinct
        functional groups (data fetch, transform, validation, notification, etc.)
        """
        # Categorize nodes by function
        categories = defaultdict(list)

        for i, turn in enumerate(turns):
            node_type = turn.turn_metadata.get("node_type", "unknown")

            # Categorize by node type
            if "http" in node_type.lower() or "api" in node_type.lower():
                categories["data_fetch"].append(i)
            elif "function" in node_type.lower() or "code" in node_type.lower():
                categories["transform"].append(i)
            elif "if" in node_type.lower() or "switch" in node_type.lower():
                categories["validation"].append(i)
            elif (
                "email" in node_type.lower()
                or "slack" in node_type.lower()
                or "webhook" in node_type.lower()
            ):
                categories["notification"].append(i)
            elif "database" in node_type.lower() or "sql" in node_type.lower():
                categories["storage"].append(i)
            elif "ai" in node_type.lower() or "openai" in node_type.lower():
                categories["ai_processing"].append(i)
            else:
                categories["other"].append(i)

        # Filter out empty categories
        active_categories = {k: v for k, v in categories.items() if v}

        # If workflow has 4+ distinct functional categories, it might be too complex
        if len(active_categories) >= 4:
            return {
                "detected": True,
                "type": "multiple_concerns",
                "categories": list(active_categories.keys()),
                "category_count": len(active_categories),
                "explanation": f"Workflow handles {len(active_categories)} distinct concerns: {', '.join(active_categories.keys())}",
                "turns": list(range(len(turns))),
            }

        return None

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect complexity issues in n8n workflow."""
        if len(turns) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 2 nodes to detect complexity issues",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Detect excessive nodes
        excessive_nodes = self._detect_excessive_nodes(turns)
        if excessive_nodes:
            issues.append(excessive_nodes)
            affected_turns.extend(excessive_nodes.get("turns", []))

        # 2. Detect deep branching
        deep_branching = self._detect_deep_branching(turns)
        if deep_branching:
            issues.append(deep_branching)
            affected_turns.extend(deep_branching.get("turns", []))

        # 3. Detect high cyclomatic complexity
        high_complexity = self._detect_high_cyclomatic_complexity(turns)
        if high_complexity:
            issues.append(high_complexity)
            affected_turns.extend(high_complexity.get("turns", []))

        # 4. Detect long execution time
        long_execution = self._detect_long_execution(turns, conversation_metadata)
        if long_execution:
            issues.append(long_execution)
            affected_turns.extend(long_execution.get("turns", []))

        # 5. Detect multiple concerns
        multiple_concerns = self._detect_multiple_concerns(turns)
        if multiple_concerns:
            issues.append(multiple_concerns)
            affected_turns.extend(multiple_concerns.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No complexity issues detected",
                detector_name=self.name,
            )

        # Determine severity
        severity = TurnAwareSeverity.MINOR
        if excessive_nodes or high_complexity:
            severity = TurnAwareSeverity.MODERATE
        if len(issues) >= 3:  # Multiple complexity indicators
            severity = TurnAwareSeverity.SEVERE

        # Calculate confidence
        confidence = 0.85 if len(issues) >= 2 else 0.75

        # Build explanation
        explanations = [issue["explanation"] for issue in issues]
        full_explanation = "; ".join(explanations)

        # Suggest fixes
        fixes = []
        if excessive_nodes or multiple_concerns:
            fixes.append("Split workflow into smaller sub-workflows using Execute Workflow nodes")
        if deep_branching or high_complexity:
            fixes.append("Simplify branching logic - consider using Switch node instead of nested IFs")
        if long_execution:
            fixes.append("Optimize slow operations or split into async sub-workflows")

        suggested_fix = "; ".join(fixes) if fixes else None

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F15",
            explanation=full_explanation,
            affected_turns=sorted(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=suggested_fix,
            detector_name=self.name,
            detector_version=self.version,
        )
