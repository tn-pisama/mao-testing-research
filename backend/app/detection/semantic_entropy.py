"""Semantic Entropy for Hallucination Detection.

Implements the approach from Kuhn et al. (Oxford, 2023):
"Detecting Hallucinations in Large Language Models Using Semantic Entropy"
(arXiv:2306.15880)

Instead of checking if output is grounded in sources (NLI approach),
semantic entropy measures consistency across multiple response samples.
High semantic entropy = the model gives semantically different answers
each time = likely hallucinating.

Cost: $0 (uses local embeddings, no LLM calls)
Latency: ~200ms for 5 samples
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EntropyResult:
    """Result of semantic entropy analysis."""
    entropy: float  # 0.0 = fully consistent, 1.0+ = highly inconsistent
    n_clusters: int  # Number of semantic clusters found
    consistency: float  # 1.0 - normalized_entropy (0-1 quality score)
    is_reliable: bool  # entropy < threshold
    cluster_sizes: List[int] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class SemanticEntropyEstimator:
    """Estimates semantic entropy from multiple response samples.

    Algorithm:
    1. Embed all response samples
    2. Compute pairwise cosine similarity
    3. Cluster responses by semantic similarity (threshold-based)
    4. Compute entropy over cluster distribution
    5. High entropy = unreliable (hallucination signal)
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        entropy_threshold: float = 0.5,
    ):
        self.similarity_threshold = similarity_threshold
        self.entropy_threshold = entropy_threshold
        self._embedder = None

    @property
    def embedder(self):
        if self._embedder is None:
            from app.core.embeddings import get_embedder
            self._embedder = get_embedder()
        return self._embedder

    def estimate(
        self,
        responses: List[str],
        question: Optional[str] = None,
    ) -> EntropyResult:
        """Estimate semantic entropy from multiple response samples.

        Args:
            responses: List of response strings (ideally 3-5 samples)
            question: Optional question for context

        Returns:
            EntropyResult with entropy, consistency, and cluster info
        """
        if len(responses) < 2:
            return EntropyResult(
                entropy=0.0, n_clusters=1, consistency=1.0,
                is_reliable=True, cluster_sizes=[len(responses)],
            )

        # Embed all responses
        embeddings = []
        for resp in responses:
            text = resp[:2000]  # Limit length
            emb = self.embedder.encode(text)
            embeddings.append(np.asarray(emb).flatten())

        # Cluster by semantic similarity
        clusters = self._cluster_responses(embeddings)
        n_clusters = len(clusters)
        cluster_sizes = [len(c) for c in clusters]

        # Compute entropy
        total = sum(cluster_sizes)
        entropy = 0.0
        for size in cluster_sizes:
            p = size / total
            if p > 0:
                entropy -= p * math.log2(p)

        # Normalize: max entropy for N items = log2(N)
        max_entropy = math.log2(len(responses)) if len(responses) > 1 else 1.0
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0
        consistency = 1.0 - normalized

        return EntropyResult(
            entropy=round(entropy, 4),
            n_clusters=n_clusters,
            consistency=round(consistency, 4),
            is_reliable=entropy < self.entropy_threshold,
            cluster_sizes=cluster_sizes,
            details={
                "n_responses": len(responses),
                "normalized_entropy": round(normalized, 4),
                "similarity_threshold": self.similarity_threshold,
            },
        )

    def _cluster_responses(
        self, embeddings: List[np.ndarray]
    ) -> List[List[int]]:
        """Cluster embeddings by semantic similarity (greedy)."""
        n = len(embeddings)
        assigned = [False] * n
        clusters = []

        for i in range(n):
            if assigned[i]:
                continue
            cluster = [i]
            assigned[i] = True
            for j in range(i + 1, n):
                if assigned[j]:
                    continue
                sim = self._cosine_sim(embeddings[i], embeddings[j])
                if sim >= self.similarity_threshold:
                    cluster.append(j)
                    assigned[j] = True
            clusters.append(cluster)

        return clusters

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(dot / norm) if norm > 0 else 0.0

    def score_hallucination_risk(
        self,
        responses: List[str],
        sources: Optional[List[str]] = None,
    ) -> Tuple[float, EntropyResult]:
        """Combined hallucination risk score using entropy + source grounding.

        Returns (risk_score, entropy_result) where:
        - risk_score 0.0 = reliable, 1.0 = likely hallucinating
        """
        entropy_result = self.estimate(responses)

        # Base risk from entropy
        risk = 1.0 - entropy_result.consistency

        # If sources available, boost risk when responses disagree WITH sources
        if sources and self.embedder:
            source_text = " ".join(s[:500] for s in sources[:3])
            source_emb = np.asarray(self.embedder.encode(source_text)).flatten()

            # Check if any response cluster aligns with sources
            best_alignment = 0.0
            for resp in responses[:5]:
                resp_emb = np.asarray(self.embedder.encode(resp[:1000])).flatten()
                sim = self._cosine_sim(source_emb, resp_emb)
                best_alignment = max(best_alignment, sim)

            # Low alignment + high entropy = very likely hallucination
            if best_alignment < 0.5:
                risk = min(1.0, risk * 1.5)
            elif best_alignment > 0.8:
                risk = risk * 0.5  # Well-grounded, reduce risk

        return round(risk, 4), entropy_result


# Singleton
semantic_entropy = SemanticEntropyEstimator()
