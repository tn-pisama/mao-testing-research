import hashlib
import json
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from sklearn.cluster import KMeans
from app.config import get_settings, get_framework_thresholds, get_tenant_thresholds, FrameworkThresholds
from app.core.embeddings import get_embedder

settings = get_settings()


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
    
    def _calibrate_confidence(
        self,
        raw_score: float,
        method: str,
        evidence_strength: float,
        loop_length: int,
    ) -> float:
        """Calibrate confidence based on evidence strength and detection method."""
        base_confidence = {
            "structural": 0.85,
            "hash": 0.80,
            "semantic": 0.70,
            "semantic_clustering": 0.75,  # Slightly higher than basic semantic
        }.get(method, 0.5)
        
        length_factor = min(1.0, loop_length / 5)
        evidence_factor = evidence_strength
        
        calibrated = base_confidence * 0.4 + raw_score * 0.3 + length_factor * 0.15 + evidence_factor * 0.15
        calibrated = min(0.99, calibrated * self.confidence_scaling)
        
        return round(calibrated, 4)
    
    def detect_loop(self, states: List[StateSnapshot]) -> LoopDetectionResult:
        if len(states) < 3:
            return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0, framework=self.framework)

        current = states[-1]
        window = states[-self.window_size:-1] if len(states) > self.window_size else states[:-1]

        structural_matches = []
        for i, prev in enumerate(window):
            if self._structural_match(current, prev):
                if not self._has_meaningful_progress(prev, current):
                    structural_matches.append(i)

        if structural_matches:
            first_match = structural_matches[0]
            loop_length = len(window) - first_match
            window_start = max(0, len(states) - self.window_size - 1)
            loop_start_index = window_start + first_match
            raw_score = len(structural_matches) / len(window)
            evidence_strength = min(1.0, len(structural_matches) / 3)

            confidence = self._calibrate_confidence(
                raw_score=raw_score,
                method="structural",
                evidence_strength=evidence_strength,
                loop_length=loop_length,
            )

            return LoopDetectionResult(
                detected=True,
                confidence=confidence,
                method="structural",
                cost=0.0,
                loop_start_index=loop_start_index,
                loop_length=loop_length,
                raw_score=raw_score,
                evidence={
                    "structural_matches": len(structural_matches),
                    "window_size": len(window),
                    "structural_threshold": self.structural_threshold,
                },
                framework=self.framework,
            )

        current_hash = self._compute_state_hash(current)
        hash_matches = []
        for i, prev in enumerate(window):
            prev_hash = self._compute_state_hash(prev)
            if current_hash == prev_hash:
                hash_matches.append(i)

        if hash_matches:
            first_match = hash_matches[0]
            loop_length = len(window) - first_match
            raw_score = len(hash_matches) / len(window)
            evidence_strength = min(1.0, len(hash_matches) / 2)

            confidence = self._calibrate_confidence(
                raw_score=raw_score,
                method="hash",
                evidence_strength=evidence_strength,
                loop_length=loop_length,
            )

            return LoopDetectionResult(
                detected=True,
                confidence=confidence,
                method="hash",
                cost=0.0,
                loop_start_index=len(states) - 1 - loop_length,
                loop_length=loop_length,
                raw_score=raw_score,
                evidence={"hash_matches": len(hash_matches), "window_size": len(window)},
                framework=self.framework,
            )

        try:
            contents = [s.content for s in window] + [current.content]
            if len(contents) < 4:
                return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0, framework=self.framework)

            embeddings = self.embedder.encode(contents)

            current_emb = embeddings[-1]
            similarities = []
            for i, emb in enumerate(embeddings[:-1]):
                sim = self.embedder.similarity(current_emb, emb)
                similarities.append((i, sim))

            high_sim_matches = [(i, sim) for i, sim in similarities if sim > self.semantic_threshold]

            if len(high_sim_matches) >= self.min_matches_for_loop:
                first_match_idx = high_sim_matches[0][0]
                avg_similarity = sum(s for _, s in high_sim_matches) / len(high_sim_matches)
                max_similarity = max(s for _, s in high_sim_matches)
                loop_length = len(window) - first_match_idx
                window_start = max(0, len(states) - self.window_size - 1)

                raw_score = avg_similarity
                evidence_strength = min(1.0, len(high_sim_matches) / 4)

                confidence = self._calibrate_confidence(
                    raw_score=raw_score,
                    method="semantic",
                    evidence_strength=evidence_strength,
                    loop_length=loop_length,
                )

                return LoopDetectionResult(
                    detected=True,
                    confidence=confidence,
                    method="semantic",
                    cost=0.0,
                    loop_start_index=window_start + first_match_idx,
                    loop_length=loop_length,
                    raw_score=raw_score,
                    evidence={
                        "semantic_matches": len(high_sim_matches),
                        "avg_similarity": round(avg_similarity, 4),
                        "max_similarity": round(max_similarity, 4),
                        "threshold": self.semantic_threshold,
                    },
                    framework=self.framework,
                )
        except Exception:
            pass

        return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0, framework=self.framework)
    
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
        return len(delta_keys) > 0 or value_changes > 2
    
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

        This is more sophisticated than pairwise similarity because it can detect:
        - Paraphrased loops (same intent, different wording)
        - Escalating loops (slight variations that are semantically equivalent)
        - Multi-step cycles (A→B→C→A where steps are semantically related)
        """
        if len(states) < 6:  # Need enough states for meaningful clustering
            return None

        try:
            contents = [s.content for s in states]
            embeddings = self.embedder.encode(contents)

            # Determine optimal number of clusters
            # Use fewer clusters for shorter traces to avoid overfitting
            n_samples = len(embeddings)
            n_clusters = min(max(2, n_samples // 4), 5)

            if n_samples < n_clusters * 2:
                return None

            # Cluster the embeddings
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(embeddings)

            # Analyze recent cluster assignments (last window_size states)
            recent_window = min(self.window_size, len(cluster_labels))
            recent_labels = cluster_labels[-recent_window:]

            # Count how many times each cluster appears in recent window
            cluster_counts = {}
            for label in recent_labels:
                cluster_counts[label] = cluster_counts.get(label, 0) + 1

            # Check for semantic loop indicators:
            # 1. One cluster dominates (agent stuck doing same thing)
            # 2. Recent sequence shows repetition (cyclic pattern)
            max_cluster_count = max(cluster_counts.values())
            dominant_cluster = max(cluster_counts, key=cluster_counts.get)

            # Calculate dominance ratio
            dominance_ratio = max_cluster_count / len(recent_labels)

            # Check for cyclic patterns in cluster sequence
            cycle_detected = False
            cycle_length = 0
            for potential_cycle in range(2, len(recent_labels) // 2 + 1):
                # Check if last N elements match the N before them
                pattern = tuple(recent_labels[-potential_cycle:])
                check_against = tuple(recent_labels[-2*potential_cycle:-potential_cycle])
                if pattern == check_against:
                    cycle_detected = True
                    cycle_length = potential_cycle
                    break

            # Determine if this is a semantic loop
            is_loop = False
            evidence = {}

            if dominance_ratio >= 0.6 and max_cluster_count >= self.min_matches_for_loop:
                is_loop = True
                evidence["type"] = "cluster_dominance"
                evidence["dominant_cluster"] = int(dominant_cluster)
                evidence["dominance_ratio"] = round(dominance_ratio, 3)
                evidence["cluster_count"] = max_cluster_count

            if cycle_detected and cycle_length >= 2:
                is_loop = True
                evidence["type"] = evidence.get("type", "") + "_cycle" if evidence.get("type") else "cluster_cycle"
                evidence["cycle_length"] = cycle_length

            if not is_loop:
                return None

            # Calculate within-cluster similarity to validate
            cluster_indices = [i for i, l in enumerate(cluster_labels) if l == dominant_cluster]
            cluster_embeddings = [embeddings[i] for i in cluster_indices[-5:]]  # Last 5 in cluster

            if len(cluster_embeddings) >= 2:
                sims = []
                for i in range(len(cluster_embeddings)):
                    for j in range(i + 1, len(cluster_embeddings)):
                        sim = self.embedder.similarity(cluster_embeddings[i], cluster_embeddings[j])
                        sims.append(sim)
                avg_intra_cluster_sim = sum(sims) / len(sims) if sims else 0
            else:
                avg_intra_cluster_sim = 0

            evidence["avg_intra_cluster_similarity"] = round(avg_intra_cluster_sim, 4)
            evidence["n_clusters"] = n_clusters
            evidence["cluster_distribution"] = {int(k): v for k, v in cluster_counts.items()}

            # Calculate confidence
            raw_score = dominance_ratio * 0.5 + avg_intra_cluster_sim * 0.5
            evidence_strength = min(1.0, max_cluster_count / 5)

            confidence = self._calibrate_confidence(
                raw_score=raw_score,
                method="semantic_clustering",
                evidence_strength=evidence_strength,
                loop_length=max_cluster_count,
            )

            # Find loop start (first state in dominant cluster in recent window)
            loop_start_index = None
            for i in range(len(cluster_labels) - recent_window, len(cluster_labels)):
                if cluster_labels[i] == dominant_cluster:
                    loop_start_index = i
                    break

            return LoopDetectionResult(
                detected=True,
                confidence=confidence,
                method="semantic_clustering",
                cost=0.0,  # Local embeddings, no API cost
                loop_start_index=loop_start_index,
                loop_length=max_cluster_count,
                raw_score=raw_score,
                evidence=evidence,
                framework=self.framework,
            )

        except Exception:
            return None

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
