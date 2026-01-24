"""
F3/F6: Resource and Token Explosion Detection for n8n Workflows
================================================================

Detects resource-related failures in n8n workflows:
- Token/context explosion (unbounded growth)
- Memory/data size explosion
- API call rate explosion
- Cost explosion patterns

These manifest differently in n8n than conversational agents because
data flow is explicit and measurable at each node.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.detection.turn_aware._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)

logger = logging.getLogger(__name__)


class N8NResourceDetector(TurnAwareDetector):
    """Detects F3/F6: Resource Misallocation / Context Overflow in n8n workflows.

    Analyzes workflow execution for:
    1. Token/content explosion (unbounded growth)
    2. Data size explosion through workflow
    3. Repetitive API calls (cost explosion)
    4. Memory-intensive operations

    Maps to:
    - F3 (Resource Misallocation): Excessive API calls, inefficient data handling
    - F6 (Task Derailment/Context Overflow): Token explosion, scope creep

    n8n-specific: Data sizes are explicitly observable at each node output.
    """

    name = "N8NResourceDetector"
    version = "1.0"
    supported_failure_modes = ["F3", "F6"]

    def __init__(
        self,
        growth_rate_threshold: float = 5.0,
        max_content_size: int = 50000,
        api_call_threshold: int = 10,
    ):
        """Initialize resource detector.

        Args:
            growth_rate_threshold: Flag if content grows by this factor (5x = 500%)
            max_content_size: Maximum acceptable content size in characters
            api_call_threshold: Maximum healthy API calls to same endpoint
        """
        self.growth_rate_threshold = growth_rate_threshold
        self.max_content_size = max_content_size
        self.api_call_threshold = api_call_threshold

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect resource-related failures in n8n workflow."""
        if len(turns) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 2 nodes to analyze resource usage",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Detect token/content explosion
        explosion = self._detect_content_explosion(turns)
        if explosion["detected"]:
            issues.append(explosion)
            affected_turns.extend(explosion.get("turns", []))

        # 2. Detect data amplification (one item -> many items)
        amplification = self._detect_data_amplification(turns)
        if amplification["detected"]:
            issues.append(amplification)
            affected_turns.extend(amplification.get("turns", []))

        # 3. Detect repeated API calls
        api_abuse = self._detect_api_abuse(turns)
        if api_abuse["detected"]:
            issues.append(api_abuse)
            affected_turns.extend(api_abuse.get("turns", []))

        # 4. Detect runaway accumulation
        accumulation = self._detect_runaway_accumulation(turns)
        if accumulation["detected"]:
            issues.append(accumulation)
            affected_turns.extend(accumulation.get("turns", []))

        # 5. Detect over-sized payloads
        oversized = self._detect_oversized_payload(turns)
        if oversized["detected"]:
            issues.append(oversized)
            affected_turns.extend(oversized.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No resource abuse patterns detected",
                detector_name=self.name,
            )

        # Determine failure mode and severity
        has_explosion = any(i.get("type") in ("content_explosion", "data_amplification") for i in issues)
        has_api_abuse = any(i.get("type") == "api_abuse" for i in issues)

        # F6 for explosion, F3 for resource misallocation
        failure_mode = "F6" if has_explosion else "F3"

        # Severity based on magnitude
        max_growth = max((i.get("growth_rate", 1) for i in issues), default=1)
        if max_growth >= 20 or any(i.get("type") == "oversized_payload" for i in issues):
            severity = TurnAwareSeverity.SEVERE
        elif max_growth >= 10 or has_api_abuse:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.95, 0.6 + len(issues) * 0.1)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode=failure_mode,
            explanation=f"Resource issue: {len(issues)} patterns detected (growth: {max_growth:.1f}x)",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "total_nodes": len(turns),
            },
            suggested_fix=(
                "Add data size limits and pagination. "
                "Use n8n's Limit node to cap item counts. "
                "Implement chunked processing for large datasets. "
                "Add caching for repeated API calls."
            ),
            detector_name=self.name,
        )

    def _detect_content_explosion(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect unbounded content/token growth through workflow.

        Example: First node outputs 100 chars, last node outputs 50,000 chars
        """
        sizes = [len(t.content) for t in turns]

        if not sizes or sizes[0] == 0:
            return {"detected": False}

        # Calculate overall growth
        initial_size = sizes[0]
        max_size = max(sizes)
        final_size = sizes[-1]

        overall_growth = max_size / initial_size if initial_size > 0 else 0

        # Also check for monotonic growth (each step bigger than last)
        monotonic_growth = 0
        for i in range(1, len(sizes)):
            if sizes[i] > sizes[i - 1]:
                monotonic_growth += 1

        monotonic_ratio = monotonic_growth / (len(sizes) - 1) if len(sizes) > 1 else 0

        if overall_growth >= self.growth_rate_threshold:
            # Find the turn where explosion happened
            explosion_turn = max(range(len(sizes)), key=lambda i: sizes[i])

            return {
                "detected": True,
                "type": "content_explosion",
                "initial_size": initial_size,
                "max_size": max_size,
                "final_size": final_size,
                "growth_rate": overall_growth,
                "monotonic_ratio": monotonic_ratio,
                "explosion_node": turns[explosion_turn].participant_id,
                "turns": [turns[explosion_turn].turn_number],
                "description": f"Content explosion: {initial_size} -> {max_size} chars ({overall_growth:.1f}x growth)",
            }

        return {"detected": False}

    def _detect_data_amplification(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect data amplification where one item becomes many.

        Example: Fetching one user, then expanding to all their friends,
        then all friends' posts, etc.
        """
        item_counts = []

        for turn in turns:
            count = self._estimate_item_count(turn.content)
            item_counts.append(count)

        if not item_counts or max(item_counts) <= 1:
            return {"detected": False}

        # Find amplification points
        for i in range(1, len(item_counts)):
            if item_counts[i - 1] > 0:
                amplification = item_counts[i] / item_counts[i - 1]
                if amplification >= self.growth_rate_threshold:
                    return {
                        "detected": True,
                        "type": "data_amplification",
                        "before_count": item_counts[i - 1],
                        "after_count": item_counts[i],
                        "growth_rate": amplification,
                        "amplifying_node": turns[i].participant_id,
                        "turns": [turns[i - 1].turn_number, turns[i].turn_number],
                        "description": f"Data amplification: {item_counts[i-1]} -> {item_counts[i]} items ({amplification:.1f}x)",
                    }

        return {"detected": False}

    def _estimate_item_count(self, content: str) -> int:
        """Estimate number of items in node output."""
        content = content.strip()

        # Try to parse as JSON array
        if content.startswith('['):
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return len(data)
            except json.JSONDecodeError:
                pass

        # Count array elements in JSON object
        if content.startswith('{'):
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    # Find arrays in values
                    for value in data.values():
                        if isinstance(value, list):
                            return len(value)
            except json.JSONDecodeError:
                pass

        # Count key: value lines as single item
        lines = [l for l in content.split('\n') if l.strip()]
        if lines:
            return 1

        return 1

    def _detect_api_abuse(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect repeated API calls suggesting inefficiency or loop.

        Look for HTTP/API nodes executing many times.
        """
        api_nodes = []
        api_patterns = ['http', 'api', 'request', 'fetch', 'webhook', 'graphql', 'rest']

        for turn in turns:
            node_lower = turn.participant_id.lower()
            if any(p in node_lower for p in api_patterns):
                api_nodes.append(turn)

        if not api_nodes:
            return {"detected": False}

        # Count calls per unique API node
        from collections import Counter
        call_counts = Counter(t.participant_id for t in api_nodes)

        for node, count in call_counts.items():
            if count > self.api_call_threshold:
                affected = [t.turn_number for t in api_nodes if t.participant_id == node]
                return {
                    "detected": True,
                    "type": "api_abuse",
                    "node": node,
                    "call_count": count,
                    "threshold": self.api_call_threshold,
                    "turns": affected,
                    "description": f"API abuse: {node} called {count} times (threshold: {self.api_call_threshold})",
                }

        return {"detected": False}

    def _detect_runaway_accumulation(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect runaway accumulation where data keeps getting appended.

        Common in workflows that aggregate without cleanup.
        """
        sizes = [len(t.content) for t in turns]

        if len(sizes) < 4:
            return {"detected": False}

        # Check for consistent growth
        growth_count = 0
        for i in range(1, len(sizes)):
            if sizes[i] > sizes[i - 1] * 1.1:  # >10% growth
                growth_count += 1

        # If >70% of steps show growth, this is runaway accumulation
        if growth_count >= len(sizes) * 0.7:
            total_growth = sizes[-1] / sizes[0] if sizes[0] > 0 else 0

            return {
                "detected": True,
                "type": "runaway_accumulation",
                "initial_size": sizes[0],
                "final_size": sizes[-1],
                "growth_rate": total_growth,
                "growth_steps": growth_count,
                "total_steps": len(sizes) - 1,
                "turns": [turns[i].turn_number for i in range(len(turns)) if i == 0 or sizes[i] > sizes[i - 1] * 1.1],
                "description": f"Runaway accumulation: {growth_count}/{len(sizes)-1} steps showed growth ({total_growth:.1f}x total)",
            }

        return {"detected": False}

    def _detect_oversized_payload(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect payloads that exceed safe size limits."""
        for turn in turns:
            size = len(turn.content)
            if size > self.max_content_size:
                return {
                    "detected": True,
                    "type": "oversized_payload",
                    "node": turn.participant_id,
                    "size": size,
                    "limit": self.max_content_size,
                    "turns": [turn.turn_number],
                    "description": f"Oversized payload: {turn.participant_id} output {size} chars (limit: {self.max_content_size})",
                }

        return {"detected": False}

    def _extract_token_count(self, content: str) -> int:
        """Estimate token count from content.

        Uses simple heuristic: ~4 characters per token for English text.
        """
        # Remove JSON structure noise for better estimation
        cleaned = re.sub(r'[{}\[\]":,]', ' ', content)
        words = cleaned.split()
        return len(words) + len(content) // 4
