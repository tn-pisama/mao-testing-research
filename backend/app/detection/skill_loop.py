"""Skill Loop Detection for Claude Code Sessions.

Detects failure patterns in Claude Code skill execution:
1. Skill invocation loops — same skill called repeatedly without progress
2. Tool loops within skills — tool call repetition during skill execution
3. Skill chain failures — skills invoking other skills that fail
4. Cost anomalies — skills consuming disproportionate tokens/cost

Designed for Claude Code hook traces captured via pisama-claude-code.
"""

import hashlib
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillTrace:
    """A single trace event from a Claude Code session."""
    timestamp: str
    tool_name: str
    hook_type: str = "unknown"
    session_id: str = "unknown"
    trace_type: Optional[str] = None  # tool, skill, task, mcp
    skill_name: Optional[str] = None
    skill_source: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class SkillLoopResult:
    """Result from skill loop detection."""
    detected: bool
    detection_type: str  # skill_loop, tool_loop_in_skill, skill_chain_failure, cost_anomaly
    confidence: float
    severity: str  # none, minor, moderate, severe
    description: str
    affected_skills: List[str] = field(default_factory=list)
    affected_tools: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggested_fix: Optional[str] = None


class SkillLoopDetector:
    """Detects skill invocation loops and related failures in Claude Code sessions.

    Analyzes sequences of tool/skill invocations for:
    - Repeated skill calls without meaningful output changes
    - Tool call repetition within skill contexts
    - Excessive skill chaining
    - Token/cost spikes from skill loops
    """

    # Thresholds
    MIN_SKILL_REPETITIONS = 3  # Same skill called 3+ times
    MIN_TOOL_REPETITIONS = 4  # Same tool called 4+ times within a skill
    MAX_SKILL_CHAIN_DEPTH = 5  # Skills invoking skills >5 deep
    COST_ANOMALY_MULTIPLIER = 3.0  # Skill costs >3x average

    def detect_all(self, traces: List[SkillTrace]) -> List[SkillLoopResult]:
        """Run all skill loop detection checks on a session's traces.

        Args:
            traces: Ordered list of trace events from a Claude Code session.

        Returns:
            List of detected issues (only those with detected=True).
        """
        results = []

        skill_loop = self._detect_skill_loops(traces)
        if skill_loop.detected:
            results.append(skill_loop)

        tool_loop = self._detect_tool_loops_in_skills(traces)
        if tool_loop.detected:
            results.append(tool_loop)

        chain_failure = self._detect_skill_chain_failure(traces)
        if chain_failure.detected:
            results.append(chain_failure)

        cost_anomaly = self._detect_cost_anomaly(traces)
        if cost_anomaly.detected:
            results.append(cost_anomaly)

        return results

    def _detect_skill_loops(self, traces: List[SkillTrace]) -> SkillLoopResult:
        """Detect repeated skill invocations without progress.

        A skill loop occurs when the same skill is invoked multiple times
        with similar inputs, suggesting the agent is stuck.
        """
        # Extract skill invocations
        skill_calls = [
            t for t in traces
            if t.trace_type == "skill" or t.skill_name
        ]

        if len(skill_calls) < self.MIN_SKILL_REPETITIONS:
            return SkillLoopResult(
                detected=False,
                detection_type="skill_loop",
                confidence=0.0,
                severity="none",
                description="Insufficient skill invocations for loop detection",
            )

        # Count skill name frequencies
        skill_counts = Counter(t.skill_name or t.tool_name for t in skill_calls)
        repeated = {
            name: count
            for name, count in skill_counts.items()
            if count >= self.MIN_SKILL_REPETITIONS
        }

        if not repeated:
            return SkillLoopResult(
                detected=False,
                detection_type="skill_loop",
                confidence=0.8,
                severity="none",
                description="No skill invocation loops detected",
            )

        # Check for output similarity (content-based loop)
        for skill_name, count in repeated.items():
            calls = [t for t in skill_calls if (t.skill_name or t.tool_name) == skill_name]
            output_hashes = set()
            for call in calls:
                output_str = str(call.tool_output or "")
                h = hashlib.md5(output_str.encode(), usedforsecurity=False).hexdigest()[:16]
                output_hashes.add(h)

            # If outputs are very similar (few unique hashes), it's likely a loop
            uniqueness_ratio = len(output_hashes) / len(calls) if calls else 1.0

            if uniqueness_ratio < 0.5:
                confidence = min(0.95, 0.6 + (count - self.MIN_SKILL_REPETITIONS) * 0.1)
                return SkillLoopResult(
                    detected=True,
                    detection_type="skill_loop",
                    confidence=confidence,
                    severity="severe" if count >= 5 else "moderate",
                    description=(
                        f"Skill '{skill_name}' invoked {count} times with similar outputs "
                        f"({len(output_hashes)} unique outputs) — likely stuck in a loop"
                    ),
                    affected_skills=[skill_name],
                    evidence={
                        "skill_name": skill_name,
                        "invocation_count": count,
                        "unique_outputs": len(output_hashes),
                        "uniqueness_ratio": round(uniqueness_ratio, 3),
                    },
                    suggested_fix=(
                        "Add exit conditions to the skill or check if the skill's "
                        "prerequisites are met before re-invoking. Consider caching "
                        "results to avoid redundant calls."
                    ),
                )

        # Repeated calls but with varying outputs (might be intentional)
        most_repeated = max(repeated.items(), key=lambda x: x[1])
        return SkillLoopResult(
            detected=True,
            detection_type="skill_loop",
            confidence=0.5,
            severity="minor",
            description=(
                f"Skill '{most_repeated[0]}' invoked {most_repeated[1]} times — "
                "outputs vary but frequency is high"
            ),
            affected_skills=[most_repeated[0]],
            evidence={
                "repeated_skills": repeated,
            },
            suggested_fix=(
                "Consider whether repeated invocations are necessary. "
                "If the skill is polling, add a maximum retry limit."
            ),
        )

    def _detect_tool_loops_in_skills(self, traces: List[SkillTrace]) -> SkillLoopResult:
        """Detect tool call repetition within skill contexts.

        When a skill is executing, underlying tools may loop. This detects
        that pattern by grouping tool calls by their enclosing skill.
        """
        # Group tool calls by skill context
        current_skill = None
        skill_tool_sequences: Dict[str, List[str]] = defaultdict(list)

        for t in traces:
            if t.trace_type == "skill" or t.skill_name:
                current_skill = t.skill_name or t.tool_name
            elif current_skill and t.trace_type in ("tool", None):
                skill_tool_sequences[current_skill].append(t.tool_name)

        # Check for tool repetition within each skill
        for skill_name, tool_names in skill_tool_sequences.items():
            if len(tool_names) < self.MIN_TOOL_REPETITIONS:
                continue

            tool_counts = Counter(tool_names)
            most_common_tool, most_common_count = tool_counts.most_common(1)[0]

            if most_common_count >= self.MIN_TOOL_REPETITIONS:
                # Check for consecutive repetitions (stronger signal)
                max_consecutive = 1
                current_consecutive = 1
                for i in range(1, len(tool_names)):
                    if tool_names[i] == tool_names[i - 1]:
                        current_consecutive += 1
                        max_consecutive = max(max_consecutive, current_consecutive)
                    else:
                        current_consecutive = 1

                confidence = min(0.90, 0.5 + max_consecutive * 0.1)
                severity = "severe" if max_consecutive >= 4 else "moderate"

                return SkillLoopResult(
                    detected=True,
                    detection_type="tool_loop_in_skill",
                    confidence=confidence,
                    severity=severity,
                    description=(
                        f"Tool '{most_common_tool}' called {most_common_count} times "
                        f"during skill '{skill_name}' (max {max_consecutive} consecutive)"
                    ),
                    affected_skills=[skill_name],
                    affected_tools=[most_common_tool],
                    evidence={
                        "skill_name": skill_name,
                        "tool_name": most_common_tool,
                        "total_calls": most_common_count,
                        "max_consecutive": max_consecutive,
                        "all_tool_counts": dict(tool_counts),
                    },
                    suggested_fix=(
                        f"Add a guard in '{skill_name}' to limit '{most_common_tool}' "
                        "calls. Use result caching or check if prior call already "
                        "produced the needed result."
                    ),
                )

        return SkillLoopResult(
            detected=False,
            detection_type="tool_loop_in_skill",
            confidence=0.8,
            severity="none",
            description="No tool loops detected within skill contexts",
        )

    def _detect_skill_chain_failure(self, traces: List[SkillTrace]) -> SkillLoopResult:
        """Detect skill chain depth or failure cascades.

        When skills invoke other skills (skill chaining), excessive depth
        can indicate design issues or recursive failures.
        """
        skill_invocations = [
            t for t in traces
            if t.trace_type == "skill" or t.skill_name
        ]

        if len(skill_invocations) < 2:
            return SkillLoopResult(
                detected=False,
                detection_type="skill_chain_failure",
                confidence=0.0,
                severity="none",
                description="Insufficient skill invocations for chain analysis",
            )

        # Count unique skills in sequence
        unique_skills = []
        seen = set()
        for t in skill_invocations:
            name = t.skill_name or t.tool_name
            if name not in seen:
                unique_skills.append(name)
                seen.add(name)

        chain_depth = len(unique_skills)

        if chain_depth > self.MAX_SKILL_CHAIN_DEPTH:
            return SkillLoopResult(
                detected=True,
                detection_type="skill_chain_failure",
                confidence=0.7,
                severity="moderate",
                description=(
                    f"Skill chain depth ({chain_depth}) exceeds maximum "
                    f"({self.MAX_SKILL_CHAIN_DEPTH}): {' → '.join(unique_skills[:8])}"
                ),
                affected_skills=unique_skills,
                evidence={
                    "chain_depth": chain_depth,
                    "skill_chain": unique_skills,
                },
                suggested_fix=(
                    "Reduce skill chain depth by combining related skills or "
                    "using direct tool calls instead of skill indirection."
                ),
            )

        return SkillLoopResult(
            detected=False,
            detection_type="skill_chain_failure",
            confidence=0.8,
            severity="none",
            description=f"Skill chain depth ({chain_depth}) is within limits",
        )

    def _detect_cost_anomaly(self, traces: List[SkillTrace]) -> SkillLoopResult:
        """Detect cost anomalies from skill executions.

        Flags skills that consume disproportionate tokens or cost compared
        to the session average.
        """
        # Group costs by skill
        skill_costs: Dict[str, float] = defaultdict(float)
        skill_tokens: Dict[str, int] = defaultdict(int)

        for t in traces:
            skill = t.skill_name or (t.tool_name if t.trace_type == "skill" else None)
            if skill:
                skill_costs[skill] += t.cost_usd
                skill_tokens[skill] += t.input_tokens + t.output_tokens

        if not skill_costs or all(v == 0 for v in skill_costs.values()):
            return SkillLoopResult(
                detected=False,
                detection_type="cost_anomaly",
                confidence=0.0,
                severity="none",
                description="No cost data available for skills",
            )

        total_cost = sum(skill_costs.values())
        avg_cost = total_cost / len(skill_costs) if skill_costs else 0

        # Find anomalies
        anomalies = {}
        for skill, cost in skill_costs.items():
            if avg_cost > 0 and cost > avg_cost * self.COST_ANOMALY_MULTIPLIER:
                anomalies[skill] = {
                    "cost_usd": round(cost, 4),
                    "tokens": skill_tokens[skill],
                    "ratio_to_avg": round(cost / avg_cost, 1),
                }

        if anomalies:
            worst = max(anomalies.items(), key=lambda x: x[1]["cost_usd"])
            return SkillLoopResult(
                detected=True,
                detection_type="cost_anomaly",
                confidence=0.65,
                severity="moderate" if worst[1]["cost_usd"] > 0.50 else "minor",
                description=(
                    f"Skill '{worst[0]}' costs ${worst[1]['cost_usd']:.4f} "
                    f"({worst[1]['ratio_to_avg']}x average) — possible inefficiency"
                ),
                affected_skills=list(anomalies.keys()),
                evidence={
                    "total_cost_usd": round(total_cost, 4),
                    "avg_cost_usd": round(avg_cost, 4),
                    "anomalies": anomalies,
                },
                suggested_fix=(
                    "Review skill prompts for efficiency. Consider caching "
                    "intermediate results or reducing context window usage."
                ),
            )

        return SkillLoopResult(
            detected=False,
            detection_type="cost_anomaly",
            confidence=0.8,
            severity="none",
            description="Skill costs are within normal range",
        )


def analyze_session(traces: List[SkillTrace]) -> List[SkillLoopResult]:
    """Convenience function: run all skill loop detections on a session.

    Args:
        traces: Ordered list of SkillTrace events from a Claude Code session.

    Returns:
        List of detected issues.
    """
    detector = SkillLoopDetector()
    return detector.detect_all(traces)
