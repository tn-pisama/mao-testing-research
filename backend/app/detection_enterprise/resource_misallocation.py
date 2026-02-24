"""
F3: Resource Misallocation Detection (MAST Taxonomy)
====================================================

Detects when multiple agents compete for shared resources:
- Resource contention (multiple agents waiting for same resource)
- Starvation (some agents never get resources)
- Deadlock potential (circular wait conditions)
- Inefficient allocation (resources not distributed optimally)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class ResourceSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class ResourceIssueType(str, Enum):
    CONTENTION = "contention"
    STARVATION = "starvation"
    DEADLOCK_RISK = "deadlock_risk"
    INEFFICIENT_ALLOCATION = "inefficient_allocation"
    EXCESSIVE_WAIT = "excessive_wait"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


@dataclass
class ResourceEvent:
    """Represents a resource access event."""
    agent_id: str
    resource_id: str
    event_type: str  # "request", "acquire", "release", "wait", "timeout"
    timestamp: float
    wait_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceIssue:
    issue_type: ResourceIssueType
    resource_id: str
    agents_involved: List[str]
    description: str
    severity: ResourceSeverity


@dataclass
class ResourceMisallocationResult:
    detected: bool
    severity: ResourceSeverity
    confidence: float
    issues: List[ResourceIssue] = field(default_factory=list)
    contention_count: int = 0
    total_wait_time_ms: float = 0.0
    starved_agents: List[str] = field(default_factory=list)
    explanation: str = ""
    suggested_fix: Optional[str] = None


class ResourceMisallocationDetector:
    """
    Detects F3: Resource Misallocation - contention for shared resources.

    Analyzes resource access patterns to identify contention, starvation,
    and inefficient allocation across multiple agents.
    """

    def __init__(
        self,
        max_wait_time_ms: float = 5000.0,
        contention_threshold: int = 2,
        starvation_threshold: float = 0.1,
    ):
        self.max_wait_time_ms = max_wait_time_ms
        self.contention_threshold = contention_threshold
        self.starvation_threshold = starvation_threshold

    def _detect_contention(
        self,
        events: List[ResourceEvent],
    ) -> List[ResourceIssue]:
        """Detect resource contention events."""
        issues = []

        # Group events by resource
        by_resource: Dict[str, List[ResourceEvent]] = defaultdict(list)
        for event in events:
            by_resource[event.resource_id].append(event)

        for resource_id, resource_events in by_resource.items():
            # Sort by timestamp
            resource_events.sort(key=lambda e: e.timestamp)

            # Find overlapping requests
            waiting_agents: Set[str] = set()
            contentions: List[Set[str]] = []

            for event in resource_events:
                if event.event_type in ["request", "wait"]:
                    waiting_agents.add(event.agent_id)
                elif event.event_type in ["acquire", "release"]:
                    waiting_agents.discard(event.agent_id)

                if len(waiting_agents) >= self.contention_threshold:
                    contentions.append(waiting_agents.copy())

            if contentions:
                all_contending = set()
                for c in contentions:
                    all_contending.update(c)

                issues.append(ResourceIssue(
                    issue_type=ResourceIssueType.CONTENTION,
                    resource_id=resource_id,
                    agents_involved=list(all_contending),
                    description=f"Resource '{resource_id}' had {len(contentions)} contention events with {len(all_contending)} agents competing",
                    severity=ResourceSeverity.MODERATE if len(contentions) < 5 else ResourceSeverity.SEVERE,
                ))

        return issues

    def _detect_starvation(
        self,
        events: List[ResourceEvent],
        agent_ids: List[str],
    ) -> List[ResourceIssue]:
        """Detect agents that never acquire resources."""
        issues = []

        # Track which agents acquired resources
        acquired_by_agent: Dict[str, int] = defaultdict(int)
        for event in events:
            if event.event_type == "acquire":
                acquired_by_agent[event.agent_id] += 1

        total_acquisitions = sum(acquired_by_agent.values())
        if total_acquisitions == 0:
            return issues

        # Find starved agents
        starved = []
        for agent in agent_ids:
            agent_share = acquired_by_agent.get(agent, 0) / total_acquisitions
            if agent_share < self.starvation_threshold:
                starved.append(agent)

        if starved:
            issues.append(ResourceIssue(
                issue_type=ResourceIssueType.STARVATION,
                resource_id="all",
                agents_involved=starved,
                description=f"{len(starved)} agents received less than {self.starvation_threshold*100:.0f}% of resources: {', '.join(starved)}",
                severity=ResourceSeverity.SEVERE,
            ))

        return issues

    def _detect_excessive_wait(
        self,
        events: List[ResourceEvent],
    ) -> List[ResourceIssue]:
        """Detect agents with excessive wait times."""
        issues = []

        excessive_waits: Dict[str, List[float]] = defaultdict(list)
        for event in events:
            if event.wait_time_ms and event.wait_time_ms > self.max_wait_time_ms:
                excessive_waits[event.agent_id].append(event.wait_time_ms)

        for agent_id, waits in excessive_waits.items():
            avg_wait = sum(waits) / len(waits)
            issues.append(ResourceIssue(
                issue_type=ResourceIssueType.EXCESSIVE_WAIT,
                resource_id="various",
                agents_involved=[agent_id],
                description=f"Agent '{agent_id}' had {len(waits)} excessive waits (avg: {avg_wait:.0f}ms, threshold: {self.max_wait_time_ms}ms)",
                severity=ResourceSeverity.MODERATE,
            ))

        return issues

    def _detect_deadlock_risk(
        self,
        events: List[ResourceEvent],
    ) -> List[ResourceIssue]:
        """Detect circular wait patterns that could cause deadlocks."""
        issues = []

        # Build hold-wait graph
        # Agent A holds resource R1 while waiting for R2
        agent_holds: Dict[str, Set[str]] = defaultdict(set)
        agent_waits: Dict[str, Set[str]] = defaultdict(set)

        for event in events:
            if event.event_type == "acquire":
                agent_holds[event.agent_id].add(event.resource_id)
            elif event.event_type == "release":
                agent_holds[event.agent_id].discard(event.resource_id)
            elif event.event_type == "wait":
                agent_waits[event.agent_id].add(event.resource_id)

        # Check for circular waits
        # A simple check: if agent A holds R1 and waits for R2,
        # and agent B holds R2 and waits for R1, that's a deadlock risk
        for agent_a, waits_a in agent_waits.items():
            holds_a = agent_holds.get(agent_a, set())
            for agent_b, waits_b in agent_waits.items():
                if agent_a == agent_b:
                    continue
                holds_b = agent_holds.get(agent_b, set())

                # Check for circular dependency
                if (waits_a & holds_b) and (waits_b & holds_a):
                    issues.append(ResourceIssue(
                        issue_type=ResourceIssueType.DEADLOCK_RISK,
                        resource_id=str(waits_a & holds_b | waits_b & holds_a),
                        agents_involved=[agent_a, agent_b],
                        description=f"Circular wait detected between '{agent_a}' and '{agent_b}' - potential deadlock",
                        severity=ResourceSeverity.CRITICAL,
                    ))

        return issues

    def detect(
        self,
        events: List[ResourceEvent],
        agent_ids: Optional[List[str]] = None,
    ) -> ResourceMisallocationResult:
        """
        Detect resource misallocation issues.

        Args:
            events: List of resource access events
            agent_ids: Optional list of all agent IDs

        Returns:
            ResourceMisallocationResult with detection outcome
        """
        if not events:
            return ResourceMisallocationResult(
                detected=False,
                severity=ResourceSeverity.NONE,
                confidence=0.0,
                explanation="No resource events to analyze",
            )

        # Get all agent IDs from events if not provided
        if agent_ids is None:
            agent_ids = list(set(e.agent_id for e in events))

        issues = []

        # Run all detection methods
        issues.extend(self._detect_contention(events))
        issues.extend(self._detect_starvation(events, agent_ids))
        issues.extend(self._detect_excessive_wait(events))
        issues.extend(self._detect_deadlock_risk(events))

        if not issues:
            return ResourceMisallocationResult(
                detected=False,
                severity=ResourceSeverity.NONE,
                confidence=0.9,
                explanation="No resource misallocation detected",
            )

        # Calculate metrics
        contention_count = len([i for i in issues if i.issue_type == ResourceIssueType.CONTENTION])
        total_wait = sum(e.wait_time_ms or 0 for e in events)
        starved = []
        for issue in issues:
            if issue.issue_type == ResourceIssueType.STARVATION:
                starved.extend(issue.agents_involved)

        # Determine overall severity
        if any(i.severity == ResourceSeverity.CRITICAL for i in issues):
            severity = ResourceSeverity.CRITICAL
        elif any(i.severity == ResourceSeverity.SEVERE for i in issues):
            severity = ResourceSeverity.SEVERE
        elif any(i.severity == ResourceSeverity.MODERATE for i in issues):
            severity = ResourceSeverity.MODERATE
        else:
            severity = ResourceSeverity.MINOR

        # Calculate confidence
        confidence = min(0.95, 0.5 + (len(issues) * 0.1))

        # Build explanation
        issue_types = set(i.issue_type.value for i in issues)
        explanation = f"Detected {len(issues)} resource issue(s): {', '.join(issue_types)}"

        # Suggest fix
        fixes = []
        if contention_count > 0:
            fixes.append("increase resource pool size or implement resource partitioning")
        if starved:
            fixes.append(f"implement fair scheduling for agents: {', '.join(starved[:3])}")
        if any(i.issue_type == ResourceIssueType.DEADLOCK_RISK for i in issues):
            fixes.append("implement deadlock prevention (resource ordering or timeout)")

        return ResourceMisallocationResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            issues=issues,
            contention_count=contention_count,
            total_wait_time_ms=total_wait,
            starved_agents=list(set(starved)),
            explanation=explanation,
            suggested_fix="; ".join(fixes) if fixes else None,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> ResourceMisallocationResult:
        """
        Detect resource misallocation from trace data.

        Extracts resource events from span metadata.
        """
        spans = trace.get("spans", [])
        if not spans:
            return ResourceMisallocationResult(
                detected=False,
                severity=ResourceSeverity.NONE,
                confidence=0.0,
                explanation="No spans in trace",
            )

        events = []
        agent_ids = set()
        has_metadata_signal = False  # v1.1: Track if we have structural evidence

        for span in spans:
            agent_id = span.get("agent_id", span.get("name", "unknown"))
            agent_ids.add(agent_id)

            metadata = span.get("metadata", {})

            # Check for resource contention indicators (structural signal)
            if metadata.get("resource_contention"):
                has_metadata_signal = True
                events.append(ResourceEvent(
                    agent_id=agent_id,
                    resource_id=metadata.get("resource_id", "shared_pool"),
                    event_type="wait",
                    timestamp=span.get("start_time", 0),
                    wait_time_ms=metadata.get("resource_wait_ms", 0),
                ))

            # Check for resource wait time (structural signal)
            wait_ms = metadata.get("resource_wait_ms", 0)
            if wait_ms > 0:
                has_metadata_signal = True
                events.append(ResourceEvent(
                    agent_id=agent_id,
                    resource_id=metadata.get("resource_id", "shared_pool"),
                    event_type="wait",
                    timestamp=span.get("start_time", 0),
                    wait_time_ms=wait_ms,
                ))

            # Check output for contention indicators (text signal — weak)
            output = span.get("output_data", {}).get("result", "")
            if isinstance(output, str):
                if "contention" in output.lower() or "waiting" in output.lower():
                    events.append(ResourceEvent(
                        agent_id=agent_id,
                        resource_id="detected_from_output",
                        event_type="wait",
                        timestamp=span.get("start_time", 0),
                    ))
                if "exhausted" in output.lower() or "pool" in output.lower():
                    events.append(ResourceEvent(
                        agent_id=agent_id,
                        resource_id="connection_pool",
                        event_type="wait",
                        timestamp=span.get("start_time", 0),
                    ))

        # v1.1 Ensemble voting: require at least one metadata-based signal.
        # Output-text-only matches (keyword "waiting", "pool", etc.) are too
        # unreliable to trigger detection on their own.
        if events and not has_metadata_signal:
            return ResourceMisallocationResult(
                detected=False,
                severity=ResourceSeverity.NONE,
                confidence=0.3,
                explanation=(
                    "Resource keywords found in output text but no structural "
                    "metadata signals (resource_contention, resource_wait_ms). "
                    "Suppressed to reduce false positives."
                ),
            )

        return self.detect(events, list(agent_ids))


# Singleton instance
resource_misallocation_detector = ResourceMisallocationDetector()
