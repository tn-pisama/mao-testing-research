"""
Loop Detection for Multi-Agent Systems (MAST F8)
=================================================

Detects infinite loops and repetitive patterns in agent behavior.

Version History:
- v1.0: Initial implementation with structural, hash, and semantic detection
- v1.1: Added semantic clustering for paraphrased loops
- v1.2: Added summary/recap whitelisting to reduce false positives
  - Agents summarizing their work shouldn't be flagged as loops
  - Recap/review patterns are benign repetition
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import List, Optional
from sklearn.cluster import KMeans
from app.config import get_settings, get_tenant_thresholds
from app.core.embeddings import get_embedder

# Detector version
DETECTOR_VERSION = "1.2"

settings = get_settings()

# v1.2: Summary/recap patterns that indicate benign repetition, not loops
SUMMARY_WHITELIST_PATTERNS = [
    r"\b(?:to summarize|in summary|summarizing|to recap|recapping)\b",
    r"\b(?:so far|thus far|up to this point|at this point)\b",
    r"\b(?:what we've done|what i've done|what has been done)\b",
    r"\b(?:reviewing|let me review|to review)\b",
    r"\b(?:accomplishments|completed so far|progress report)\b",
    r"\b(?:status update|current status|where we are)\b",
    r"\b(?:here's what|here is what)\s+(?:we've|i've|has been)\b",
    r"\b(?:quick recap|brief summary|overview of)\b",
    r"\b(?:wrapping up|to wrap up|in conclusion)\b",
    r"\b(?:let me go over|going over what)\b",
]

# v1.2: Progress reporting patterns
PROGRESS_WHITELIST_PATTERNS = [
    r"\b(?:step \d+ of \d+|task \d+ of \d+)\b",
    r"\b(?:phase \d+|iteration \d+|round \d+)\b",
    r"\b(?:checkpoint|milestone|progress)\b",
    r"\b(?:moving on to|proceeding to|next up)\b",
    r"\b(?:completed step \d+|finished step \d+)\b",
]


@dataclass
class LoopDetectionResult:
    detected: bool
    confidence: float
    method: Optional[str]
    cost: float
    loop_start_index: Optional[int] = None
    loop_length: Optional[int] = None
    raw_score: Optional[float] = None
    evidence: Optional[dict] = None
    framework: Optional[str] = None  # Framework used for detection thresholds


@dataclass
class StateSnapshot:
    agent_id: str
    state_delta: dict
    content: str
    sequence_num: int


class MultiLevelLoopDetector:
    def __init__(
        self,
        structural_threshold: Optional[float] = None,
        semantic_threshold: Optional[float] = None,
        window_size: Optional[int] = None,
        min_matches_for_loop: Optional[int] = None,
        confidence_scaling: Optional[float] = None,
        framework: Optional[str] = None,
        tenant_settings: Optional[dict] = None,
    ):
        self._embedder = None
        self.framework = framework
        self.tenant_settings = tenant_settings

        # Get thresholds with tenant overrides if available
        if tenant_settings or framework:
            thresholds = get_tenant_thresholds(tenant_settings, framework)
            self.structural_threshold = structural_threshold or thresholds.structural_threshold
            self.semantic_threshold = semantic_threshold or thresholds.semantic_threshold
            self.window_size = window_size or thresholds.loop_detection_window
            self.min_matches_for_loop = min_matches_for_loop or thresholds.min_matches_for_loop
            self.confidence_scaling = confidence_scaling or thresholds.confidence_scaling
        else:
            # Fall back to global settings
            self.structural_threshold = structural_threshold or settings.structural_threshold
            self.semantic_threshold = semantic_threshold or settings.semantic_threshold
            self.window_size = window_size or settings.loop_detection_window
            self.min_matches_for_loop = min_matches_for_loop or 2
            self.confidence_scaling = confidence_scaling or 1.0

    @classmethod
    def for_framework(cls, framework: str) -> "MultiLevelLoopDetector":
        """Create a detector configured for a specific framework.

        Args:
            framework: Framework name (langgraph, autogen, crewai, etc.)

        Returns:
            MultiLevelLoopDetector with framework-specific thresholds
        """
        return cls(framework=framework)

    @classmethod
    def for_tenant(cls, tenant_settings: Optional[dict], framework: Optional[str] = None) -> "MultiLevelLoopDetector":
        """Create a detector configured for a specific tenant.

        Uses tenant-specific threshold overrides merged with framework defaults.

        Args:
            tenant_settings: Tenant's settings dict (from tenant.settings)
            framework: Framework name for framework-specific defaults

        Returns:
            MultiLevelLoopDetector with tenant-specific thresholds
        """
        return cls(framework=framework, tenant_settings=tenant_settings)

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    def _is_summary_or_progress(self, text: str) -> bool:
        """
        v1.2: Check if text is a summary/recap or progress report.

        These patterns indicate benign repetition (agent reviewing work)
        rather than an actual loop.
        """
        text_lower = text.lower()

        for pattern in SUMMARY_WHITELIST_PATTERNS:
            if re.search(pattern, text_lower):
                return True

        for pattern in PROGRESS_WHITELIST_PATTERNS:
            if re.search(pattern, text_lower):
                return True

        return False

    def _has_summary_pattern_in_window(self, states: List["StateSnapshot"]) -> bool:
        """
        v1.2: Check if any state in the window contains summary patterns.

        If the recent window contains summary/recap language, the repetition
        might be benign rather than a loop.
        """
        for state in states[-5:]:  # Check last 5 states
            if self._is_summary_or_progress(state.content):
                return True
        return False

    def _calibrate_confidence(
        self,
        raw_score: float,
        method: str,
        evidence_strength: float,
        loop_length: int,
    ) -> float:
        """Calibrate confidence based on evidence strength and detection method."""
        base_confidence = {
            "structural": 0.96,
            "hash": 0.80,
            "semantic": 0.70,
            "semantic_clustering": 0.75,  # Slightly higher than basic semantic
        }.get(method, 0.5)

        length_factor = min(1.0, loop_length / 5)
        evidence_factor = evidence_strength

        calibrated = base_confidence * 0.5 + raw_score * 0.25 + length_factor * 0.15 + evidence_factor * 0.10
        calibrated = min(0.99, calibrated * self.confidence_scaling)

        return round(calibrated, 4)

    def _no_loop(self, **kwargs) -> LoopDetectionResult:
        return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0, framework=self.framework, **kwargs)

    def detect_loop(self, states: List[StateSnapshot]) -> LoopDetectionResult:
        if len(states) < 3:
            return self._no_loop()

        # v1.2: Check for summary patterns (informational, doesn't short-circuit)
        self._has_summary_pattern_in_window(states)

        current = states[-1]
        window = states[-self.window_size:-1] if len(states) > self.window_size else states[:-1]

        return (
            self._detect_structural_loop(current, window, states)
            or self._detect_hash_loop(current, window, states)
            or self._detect_semantic_loop(current, window, states)
            or self._no_loop()
        )

    def _detect_structural_loop(
        self, current: StateSnapshot, window: List[StateSnapshot], states: List[StateSnapshot]
    ) -> Optional[LoopDetectionResult]:
        """Tier 1: Structural matching — same agent, same state keys, no progress."""
        matches = [
            i for i, prev in enumerate(window)
            if self._structural_match(current, prev) and not self._has_meaningful_progress(prev, current)
        ]
        if not matches:
            return None

        first_match = matches[0]
        loop_length = len(window) - first_match
        window_start = max(0, len(states) - self.window_size - 1)
        raw_score = len(matches) / len(window)

        return LoopDetectionResult(
            detected=True,
            confidence=self._calibrate_confidence(raw_score, "structural", min(1.0, len(matches) / 2), loop_length),
            method="structural",
            cost=0.0,
            loop_start_index=window_start + first_match,
            loop_length=loop_length,
            raw_score=raw_score,
            evidence={"structural_matches": len(matches), "window_size": len(window), "structural_threshold": self.structural_threshold},
            framework=self.framework,
        )

    def _detect_hash_loop(
        self, current: StateSnapshot, window: List[StateSnapshot], states: List[StateSnapshot]
    ) -> Optional[LoopDetectionResult]:
        """Tier 2: Hash collision — identical state_delta content."""
        current_hash = self._compute_state_hash(current)
        matches = [i for i, prev in enumerate(window) if self._compute_state_hash(prev) == current_hash]
        if not matches:
            return None

        first_match = matches[0]
        loop_length = len(window) - first_match
        raw_score = len(matches) / len(window)

        return LoopDetectionResult(
            detected=True,
            confidence=self._calibrate_confidence(raw_score, "hash", min(1.0, len(matches) / 2), loop_length),
            method="hash",
            cost=0.0,
            loop_start_index=len(states) - 1 - loop_length,
            loop_length=loop_length,
            raw_score=raw_score,
            evidence={"hash_matches": len(matches), "window_size": len(window)},
            framework=self.framework,
        )

    def _detect_semantic_loop(
        self, current: StateSnapshot, window: List[StateSnapshot], states: List[StateSnapshot]
    ) -> Optional[LoopDetectionResult]:
        """Tier 3: Semantic similarity — embedding-based with progress filter."""
        try:
            contents = [s.content for s in window] + [current.content]
            if len(contents) < 4:
                return None

            embeddings = self.embedder.encode(contents)
            current_emb = embeddings[-1]

            high_sim_matches = [
                (i, self.embedder.similarity(current_emb, emb))
                for i, emb in enumerate(embeddings[:-1])
            ]
            high_sim_matches = [
                (i, sim) for i, sim in high_sim_matches
                if sim > self.semantic_threshold and not self._has_meaningful_progress(window[i], current)
            ]

            # v1.2: If current state is a summary/recap, don't flag as loop
            if self._is_summary_or_progress(current.content):
                return self._no_loop(evidence={"summary_pattern_detected": True}) if high_sim_matches else None

            if len(high_sim_matches) < self.min_matches_for_loop:
                return None

            first_match_idx = high_sim_matches[0][0]
            avg_similarity = sum(s for _, s in high_sim_matches) / len(high_sim_matches)
            max_similarity = max(s for _, s in high_sim_matches)
            loop_length = len(window) - first_match_idx
            window_start = max(0, len(states) - self.window_size - 1)

            return LoopDetectionResult(
                detected=True,
                confidence=self._calibrate_confidence(avg_similarity, "semantic", min(1.0, len(high_sim_matches) / 4), loop_length),
                method="semantic",
                cost=0.0,
                loop_start_index=window_start + first_match_idx,
                loop_length=loop_length,
                raw_score=avg_similarity,
                evidence={
                    "semantic_matches": len(high_sim_matches),
                    "avg_similarity": round(avg_similarity, 4),
                    "max_similarity": round(max_similarity, 4),
                    "threshold": self.semantic_threshold,
                },
                framework=self.framework,
            )
        except Exception:
            return None

    def _structural_match(self, a: StateSnapshot, b: StateSnapshot) -> bool:
        return (
            a.agent_id == b.agent_id and
            set(a.state_delta.keys()) == set(b.state_delta.keys())
        )

    def _has_meaningful_progress(self, prev: StateSnapshot, current: StateSnapshot) -> bool:
        delta_keys = set(current.state_delta.keys()) - set(prev.state_delta.keys())
        value_changes = sum(
            1 for k in current.state_delta
            if k in prev.state_delta and current.state_delta[k] != prev.state_delta[k]
        )
        # v1.2.1: Lowered from > 2 to >= 2 — if 2+ fields change value between
        # states, that's meaningful progress (e.g., batch processing where each
        # item has a different ID and amount but the same action key).
        return len(delta_keys) > 0 or value_changes >= 2

    def _compute_state_hash(self, state: StateSnapshot) -> str:
        normalized = json.dumps(state.state_delta, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def detect_semantic_loop_with_clustering(
        self, states: List[StateSnapshot]
    ) -> Optional[LoopDetectionResult]:
        """Advanced semantic loop detection using embedding clustering.

        Uses KMeans clustering to find groups of semantically similar states,
        then checks if recent states are repeatedly falling into the same cluster
        (indicating a semantic loop where the agent keeps doing similar things).
        """
        if len(states) < 6:
            return None

        try:
            embeddings = self.embedder.encode([s.content for s in states])
            n_samples = len(embeddings)
            n_clusters = min(max(2, n_samples // 4), 5)

            if n_samples < n_clusters * 2:
                return None

            cluster_labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(embeddings)
            recent_window = min(self.window_size, len(cluster_labels))
            recent_labels = cluster_labels[-recent_window:]

            evidence = self._find_cluster_pattern(recent_labels, cluster_labels)
            if evidence is None:
                return None

            return self._build_clustering_result(embeddings, cluster_labels, recent_window, n_clusters, evidence)
        except Exception:
            return None

    def _find_cluster_pattern(self, recent_labels, cluster_labels) -> Optional[dict]:
        """Analyze cluster assignments for dominance or cyclic patterns."""
        cluster_counts = {}
        for label in recent_labels:
            cluster_counts[label] = cluster_counts.get(label, 0) + 1

        max_cluster_count = max(cluster_counts.values())
        dominant_cluster = max(cluster_counts, key=cluster_counts.get)
        dominance_ratio = max_cluster_count / len(recent_labels)

        # Check for cyclic patterns in cluster sequence
        cycle_length = 0
        for potential_cycle in range(2, len(recent_labels) // 2 + 1):
            pattern = tuple(recent_labels[-potential_cycle:])
            check_against = tuple(recent_labels[-2*potential_cycle:-potential_cycle])
            if pattern == check_against:
                cycle_length = potential_cycle
                break

        evidence = {}
        is_loop = False

        if dominance_ratio >= 0.6 and max_cluster_count >= self.min_matches_for_loop:
            is_loop = True
            evidence["type"] = "cluster_dominance"
            evidence["dominant_cluster"] = int(dominant_cluster)
            evidence["dominance_ratio"] = round(dominance_ratio, 3)
            evidence["cluster_count"] = max_cluster_count

        if cycle_length >= 2:
            is_loop = True
            evidence["type"] = evidence.get("type", "") + "_cycle" if evidence.get("type") else "cluster_cycle"
            evidence["cycle_length"] = cycle_length

        if not is_loop:
            return None

        evidence["cluster_distribution"] = {int(k): v for k, v in cluster_counts.items()}
        return evidence

    def _build_clustering_result(
        self, embeddings, cluster_labels, recent_window: int, n_clusters: int, evidence: dict
    ) -> LoopDetectionResult:
        """Validate cluster loop with intra-cluster similarity and build result."""
        dominant_cluster = evidence.get("dominant_cluster", 0)
        max_cluster_count = evidence.get("cluster_count", 0)
        dominance_ratio = evidence.get("dominance_ratio", 0.0)

        # Calculate within-cluster similarity to validate
        cluster_indices = [i for i, label in enumerate(cluster_labels) if label == dominant_cluster]
        cluster_embs = [embeddings[i] for i in cluster_indices[-5:]]

        avg_intra_sim = 0.0
        if len(cluster_embs) >= 2:
            sims = [
                self.embedder.similarity(cluster_embs[i], cluster_embs[j])
                for i in range(len(cluster_embs)) for j in range(i + 1, len(cluster_embs))
            ]
            avg_intra_sim = sum(sims) / len(sims) if sims else 0.0

        evidence["avg_intra_cluster_similarity"] = round(avg_intra_sim, 4)
        evidence["n_clusters"] = n_clusters

        raw_score = dominance_ratio * 0.5 + avg_intra_sim * 0.5

        # Find loop start (first state in dominant cluster in recent window)
        loop_start_index = None
        for i in range(len(cluster_labels) - recent_window, len(cluster_labels)):
            if cluster_labels[i] == dominant_cluster:
                loop_start_index = i
                break

        return LoopDetectionResult(
            detected=True,
            confidence=self._calibrate_confidence(raw_score, "semantic_clustering", min(1.0, max_cluster_count / 5), max_cluster_count),
            method="semantic_clustering",
            cost=0.0,
            loop_start_index=loop_start_index,
            loop_length=max_cluster_count,
            raw_score=raw_score,
            evidence=evidence,
            framework=self.framework,
        )

    def detect_loop_enhanced(self, states: List[StateSnapshot]) -> LoopDetectionResult:
        """Enhanced loop detection with all methods including clustering.

        Order of detection (cheapest to most expensive):
        1. Structural matching (O(n), no API calls)
        2. Hash collision (O(n), no API calls)
        3. Basic semantic similarity (embedding generation + pairwise comparison)
        4. Clustering-based semantic (embedding generation + KMeans)
        """
        # First try the standard methods
        result = self.detect_loop(states)
        if result.detected:
            return result

        # If standard methods didn't detect, try clustering-based semantic
        clustering_result = self.detect_semantic_loop_with_clustering(states)
        if clustering_result:
            return clustering_result

        return LoopDetectionResult(
            detected=False,
            confidence=0.0,
            method=None,
            cost=0.0,
            framework=self.framework,
        )


loop_detector = MultiLevelLoopDetector()
