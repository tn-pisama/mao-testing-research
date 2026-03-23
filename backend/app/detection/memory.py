"""Detection memory — cross-trace learning and baseline engine.

Tracks detection patterns across traces to:
1. Establish baselines per agent/project
2. Detect anomalies (new failure patterns)
3. Suppress known false positives
4. Correlate recurring failures

Closes gap with Patronus AI's episodic + semantic memory.
"""

import hashlib
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class FailurePattern:
    """A recurring failure pattern observed across traces."""
    pattern_id: str
    failure_type: str
    signature: str  # Hash of key failure characteristics
    occurrences: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    agent_ids: List[str] = field(default_factory=list)
    suppressed: bool = False  # User marked as false positive
    confidence_avg: float = 0.0
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentBaseline:
    """Baseline detection rates for an agent."""
    agent_id: str
    total_traces: int = 0
    detection_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    detection_rates: Dict[str, float] = field(default_factory=dict)
    last_updated: Optional[str] = None

    def update(self, detections: Dict[str, bool]) -> None:
        """Update baseline with new detection results."""
        self.total_traces += 1
        for det_type, detected in detections.items():
            if detected:
                self.detection_counts[det_type] += 1

        # Recalculate rates
        if self.total_traces > 0:
            self.detection_rates = {
                det_type: count / self.total_traces
                for det_type, count in self.detection_counts.items()
            }
        self.last_updated = datetime.now(timezone.utc).isoformat()


@dataclass
class AnomalyAlert:
    """Alert when detection pattern deviates from baseline."""
    agent_id: str
    detection_type: str
    baseline_rate: float
    current_rate: float
    deviation: float  # How far from baseline (in standard deviations or ratio)
    message: str


@dataclass
class MemoryState:
    """Serializable memory state."""
    baselines: Dict[str, Dict] = field(default_factory=dict)
    patterns: Dict[str, Dict] = field(default_factory=dict)
    suppressed_signatures: List[str] = field(default_factory=list)


class DetectionMemory:
    """Cross-trace detection memory with baseline tracking.

    Usage:
        memory = DetectionMemory()

        # Record detection results for each trace
        memory.record("agent-1", {"loop": True, "injection": False, "corruption": False})
        memory.record("agent-1", {"loop": True, "injection": False, "corruption": False})
        memory.record("agent-1", {"loop": False, "injection": True, "corruption": False})

        # Check for anomalies
        anomalies = memory.check_anomalies("agent-1", {"loop": False, "injection": False, "corruption": True})
        # -> AnomalyAlert: corruption detected for first time (0% baseline)

        # Suppress false positives
        memory.suppress_pattern("loop", agent_id="agent-1")

        # Save/load state
        memory.save("detection_memory.json")
        memory = DetectionMemory.load("detection_memory.json")
    """

    def __init__(self):
        self._baselines: Dict[str, AgentBaseline] = {}
        self._patterns: Dict[str, FailurePattern] = {}
        self._suppressed: Set[str] = set()
        self._recent_window: Dict[str, List[Dict[str, bool]]] = defaultdict(list)
        self._window_size = 20  # Last N traces for anomaly detection

    def record(
        self,
        agent_id: str,
        detections: Dict[str, bool],
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[AnomalyAlert]:
        """Record detection results and check for anomalies.

        Args:
            agent_id: Agent identifier
            detections: Dict of {detector_name: detected_bool}
            trace_id: Optional trace ID
            metadata: Optional additional context

        Returns:
            List of anomaly alerts (empty if no anomalies)
        """
        # Initialize baseline if needed
        if agent_id not in self._baselines:
            self._baselines[agent_id] = AgentBaseline(agent_id=agent_id)

        # Check for anomalies BEFORE updating baseline
        alerts = self.check_anomalies(agent_id, detections)

        # Update baseline with new data
        self._baselines[agent_id].update(detections)

        # Track in recent window
        self._recent_window[agent_id].append(detections)
        if len(self._recent_window[agent_id]) > self._window_size:
            self._recent_window[agent_id].pop(0)

        # Record failure patterns
        for det_type, detected in detections.items():
            if detected:
                self._record_pattern(det_type, agent_id, metadata)

        return alerts

    def check_anomalies(
        self,
        agent_id: str,
        current_detections: Dict[str, bool],
    ) -> List[AnomalyAlert]:
        """Check if current detections deviate from baseline.

        Args:
            agent_id: Agent identifier
            current_detections: Current detection results

        Returns:
            List of anomaly alerts
        """
        baseline = self._baselines.get(agent_id)
        if not baseline or baseline.total_traces < 5:
            return []  # Not enough data for baseline

        alerts = []

        for det_type, detected in current_detections.items():
            if not detected:
                continue

            baseline_rate = baseline.detection_rates.get(det_type, 0.0)

            # Alert on new failure types (never seen before)
            if baseline_rate == 0.0 and baseline.total_traces >= 5:
                alerts.append(AnomalyAlert(
                    agent_id=agent_id,
                    detection_type=det_type,
                    baseline_rate=0.0,
                    current_rate=1.0,
                    deviation=float("inf"),
                    message=f"New failure type '{det_type}' detected for agent '{agent_id}' "
                            f"(never seen in {baseline.total_traces} previous traces)",
                ))

            # Alert on significant spikes (>3x baseline rate in recent window)
            elif baseline_rate > 0:
                recent = self._recent_window.get(agent_id, [])
                if len(recent) >= 5:
                    recent_rate = sum(
                        1 for r in recent[-5:] if r.get(det_type, False)
                    ) / 5
                    if recent_rate > baseline_rate * 3:
                        alerts.append(AnomalyAlert(
                            agent_id=agent_id,
                            detection_type=det_type,
                            baseline_rate=baseline_rate,
                            current_rate=recent_rate,
                            deviation=recent_rate / baseline_rate if baseline_rate > 0 else float("inf"),
                            message=f"Spike in '{det_type}' for agent '{agent_id}': "
                                    f"{recent_rate:.1%} recent vs {baseline_rate:.1%} baseline ({recent_rate/baseline_rate:.1f}x)",
                        ))

        return alerts

    def is_suppressed(self, detection_type: str, agent_id: Optional[str] = None) -> bool:
        """Check if a detection type is suppressed (marked as known FP).

        Args:
            detection_type: Detector name
            agent_id: Optional agent ID for agent-specific suppression

        Returns:
            True if suppressed
        """
        sig = self._make_suppression_key(detection_type, agent_id)
        return sig in self._suppressed or self._make_suppression_key(detection_type) in self._suppressed

    def suppress_pattern(self, detection_type: str, agent_id: Optional[str] = None) -> None:
        """Suppress a detection pattern (mark as known false positive).

        Args:
            detection_type: Detector name
            agent_id: Optional agent ID for agent-specific suppression
        """
        sig = self._make_suppression_key(detection_type, agent_id)
        self._suppressed.add(sig)
        logger.info(f"Suppressed pattern: {sig}")

    def unsuppress_pattern(self, detection_type: str, agent_id: Optional[str] = None) -> None:
        """Remove suppression for a detection pattern."""
        sig = self._make_suppression_key(detection_type, agent_id)
        self._suppressed.discard(sig)

    def get_baseline(self, agent_id: str) -> Optional[AgentBaseline]:
        """Get baseline for an agent."""
        return self._baselines.get(agent_id)

    def get_patterns(self, failure_type: Optional[str] = None) -> List[FailurePattern]:
        """Get recorded failure patterns."""
        patterns = list(self._patterns.values())
        if failure_type:
            patterns = [p for p in patterns if p.failure_type == failure_type]
        return sorted(patterns, key=lambda p: p.occurrences, reverse=True)

    def get_correlated_failures(self, agent_id: str) -> Dict[str, List[str]]:
        """Find failures that tend to co-occur for an agent.

        Returns:
            Dict of {failure_type: [correlated_failure_types]}
        """
        recent = self._recent_window.get(agent_id, [])
        if len(recent) < 5:
            return {}

        # Count co-occurrences
        co_occur: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for trace_dets in recent:
            active = [k for k, v in trace_dets.items() if v]
            for i, a in enumerate(active):
                for b in active[i + 1:]:
                    co_occur[a][b] += 1
                    co_occur[b][a] += 1

        # Filter to significant correlations (co-occur > 50% of time)
        correlations = {}
        for det_type, others in co_occur.items():
            det_count = sum(1 for t in recent if t.get(det_type, False))
            if det_count < 2:
                continue
            correlated = [
                other for other, count in others.items()
                if count / det_count > 0.5
            ]
            if correlated:
                correlations[det_type] = correlated

        return correlations

    def save(self, path: str) -> None:
        """Save memory state to JSON file."""
        state = {
            "baselines": {
                aid: {
                    "agent_id": b.agent_id,
                    "total_traces": b.total_traces,
                    "detection_counts": dict(b.detection_counts),
                    "detection_rates": b.detection_rates,
                    "last_updated": b.last_updated,
                }
                for aid, b in self._baselines.items()
            },
            "patterns": {
                pid: {
                    "pattern_id": p.pattern_id,
                    "failure_type": p.failure_type,
                    "signature": p.signature,
                    "occurrences": p.occurrences,
                    "first_seen": p.first_seen,
                    "last_seen": p.last_seen,
                    "agent_ids": p.agent_ids,
                    "suppressed": p.suppressed,
                    "confidence_avg": p.confidence_avg,
                }
                for pid, p in self._patterns.items()
            },
            "suppressed": list(self._suppressed),
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved detection memory to {path}")

    @classmethod
    def load(cls, path: str) -> "DetectionMemory":
        """Load memory state from JSON file."""
        memory = cls()

        if not os.path.exists(path):
            return memory

        with open(path) as f:
            state = json.load(f)

        for aid, bdata in state.get("baselines", {}).items():
            baseline = AgentBaseline(
                agent_id=bdata["agent_id"],
                total_traces=bdata["total_traces"],
                detection_rates=bdata.get("detection_rates", {}),
                last_updated=bdata.get("last_updated"),
            )
            baseline.detection_counts = defaultdict(int, bdata.get("detection_counts", {}))
            memory._baselines[aid] = baseline

        for pid, pdata in state.get("patterns", {}).items():
            memory._patterns[pid] = FailurePattern(
                pattern_id=pdata["pattern_id"],
                failure_type=pdata["failure_type"],
                signature=pdata["signature"],
                occurrences=pdata["occurrences"],
                first_seen=pdata.get("first_seen"),
                last_seen=pdata.get("last_seen"),
                agent_ids=pdata.get("agent_ids", []),
                suppressed=pdata.get("suppressed", False),
                confidence_avg=pdata.get("confidence_avg", 0.0),
            )

        memory._suppressed = set(state.get("suppressed", []))

        logger.debug(f"Loaded detection memory from {path}: {len(memory._baselines)} baselines, {len(memory._patterns)} patterns")
        return memory

    def _record_pattern(
        self,
        det_type: str,
        agent_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a failure pattern occurrence."""
        sig = hashlib.sha256(f"{det_type}:{agent_id}".encode()).hexdigest()[:16]
        now = datetime.now(timezone.utc).isoformat()

        if sig not in self._patterns:
            self._patterns[sig] = FailurePattern(
                pattern_id=sig,
                failure_type=det_type,
                signature=sig,
                first_seen=now,
            )

        pattern = self._patterns[sig]
        pattern.occurrences += 1
        pattern.last_seen = now
        if agent_id not in pattern.agent_ids:
            pattern.agent_ids.append(agent_id)

    def _make_suppression_key(self, detection_type: str, agent_id: Optional[str] = None) -> str:
        """Create a suppression key."""
        if agent_id:
            return f"{detection_type}:{agent_id}"
        return detection_type
