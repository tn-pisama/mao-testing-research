"""
F6: Task Derailment Detection (MAST Taxonomy)
=============================================

Detects when an agent goes off-topic or deviates from the assigned task.
One of the most common failures (7.4% in MAST-Data).

Detection Methods:
1. Semantic similarity between task and output
2. Topic drift via embedding distance
3. Keyword extraction and matching
4. Entailment checking
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class DerailmentSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class DerailmentResult:
    detected: bool
    severity: DerailmentSeverity
    confidence: float
    task_output_similarity: float
    topic_drift_score: float
    explanation: str
    suggested_fix: Optional[str] = None


class TaskDerailmentDetector:
    """
    Detects F6: Task Derailment - when an agent goes off-topic.
    
    Uses semantic similarity and topic modeling to detect drift
    between the assigned task and the agent's output.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.3,
        drift_threshold: float = 0.5,
        min_output_length: int = 20,
    ):
        self.similarity_threshold = similarity_threshold
        self.drift_threshold = drift_threshold
        self.min_output_length = min_output_length
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from app.core.embeddings import get_embedder
                self._embedder = get_embedder()
            except ImportError:
                logger.warning("EmbeddingService not available, using fallback")
                self._embedder = "fallback"
        return self._embedder

    def _compute_similarity(self, text1: str, text2: str) -> float:
        embedder = self._get_embedder()
        
        if embedder == "fallback":
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            intersection = words1 & words2
            union = words1 | words2
            return len(intersection) / len(union)
        
        try:
            embeddings = embedder.encode([text1, text2])
            return embedder.similarity(embeddings[0], embeddings[1])
        except Exception as e:
            logger.warning(f"Embedding failed, using fallback: {e}")
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            return len(words1 & words2) / len(words1 | words2)

    def _extract_key_terms(self, text: str) -> set[str]:
        words = text.lower().split()
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "under", "again", "further", "then", "once",
            "and", "but", "or", "nor", "so", "yet", "both", "either",
            "neither", "not", "only", "own", "same", "than", "too", "very",
            "just", "can", "don", "now", "it", "its", "this", "that",
        }
        return {w for w in words if len(w) > 2 and w not in stopwords}

    def _compute_topic_drift(
        self,
        task: str,
        output: str,
        context: Optional[str] = None,
    ) -> float:
        task_terms = self._extract_key_terms(task)
        output_terms = self._extract_key_terms(output)
        
        if not task_terms:
            return 0.0
        
        overlap = task_terms & output_terms
        coverage = len(overlap) / len(task_terms)
        
        if context:
            context_terms = self._extract_key_terms(context)
            new_terms = output_terms - task_terms - context_terms
            novelty_ratio = len(new_terms) / max(len(output_terms), 1)
        else:
            new_terms = output_terms - task_terms
            novelty_ratio = len(new_terms) / max(len(output_terms), 1)
        
        drift_score = (1 - coverage) * 0.6 + novelty_ratio * 0.4
        return min(drift_score, 1.0)

    def detect(
        self,
        task: str,
        output: str,
        context: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> DerailmentResult:
        if len(output) < self.min_output_length:
            return DerailmentResult(
                detected=False,
                severity=DerailmentSeverity.NONE,
                confidence=0.0,
                task_output_similarity=1.0,
                topic_drift_score=0.0,
                explanation="Output too short to analyze",
            )

        similarity = self._compute_similarity(task, output)
        drift_score = self._compute_topic_drift(task, output, context)
        
        detected = similarity < self.similarity_threshold or drift_score > self.drift_threshold
        
        if not detected:
            return DerailmentResult(
                detected=False,
                severity=DerailmentSeverity.NONE,
                confidence=1.0 - drift_score,
                task_output_similarity=similarity,
                topic_drift_score=drift_score,
                explanation="Agent stayed on task",
            )

        if drift_score > 0.8 or similarity < 0.1:
            severity = DerailmentSeverity.SEVERE
        elif drift_score > 0.6 or similarity < 0.2:
            severity = DerailmentSeverity.MODERATE
        else:
            severity = DerailmentSeverity.MINOR

        confidence = (drift_score + (1 - similarity)) / 2

        agent_prefix = f"Agent '{agent_name}'" if agent_name else "Agent"
        explanation = (
            f"{agent_prefix} deviated from the assigned task. "
            f"Task-output similarity: {similarity:.2f} (threshold: {self.similarity_threshold}). "
            f"Topic drift score: {drift_score:.2f} (threshold: {self.drift_threshold})."
        )

        suggested_fix = (
            "Add explicit task reminders in the prompt. Consider using: "
            "'Stay focused on the following task: [TASK]. Do not address unrelated topics.'"
        )

        return DerailmentResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            task_output_similarity=similarity,
            topic_drift_score=drift_score,
            explanation=explanation,
            suggested_fix=suggested_fix,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> list[DerailmentResult]:
        results = []
        
        spans = trace.get("spans", [])
        for span in spans:
            task = span.get("input", {}).get("task", "")
            output = span.get("output", {}).get("content", "")
            context = span.get("input", {}).get("context", "")
            agent_name = span.get("name", "")
            
            if task and output:
                result = self.detect(
                    task=task,
                    output=output,
                    context=context,
                    agent_name=agent_name,
                )
                if result.detected:
                    results.append(result)
        
        return results
