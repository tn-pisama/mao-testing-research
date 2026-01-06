"""
Drift Detector - Detects behavioral drift from baseline.

Compares new outputs to baseline using:
- Semantic similarity
- Behavioral patterns
- Performance metrics
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .baseline import Baseline, BaselineEntry, baseline_store

logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftType(str, Enum):
    SEMANTIC = "semantic"
    BEHAVIORAL = "behavioral"
    PERFORMANCE = "performance"
    FORMAT = "format"


@dataclass
class DriftResult:
    detected: bool
    drift_type: Optional[DriftType]
    severity: DriftSeverity
    
    similarity_score: float
    baseline_entry_id: Optional[str]
    
    prompt: str
    baseline_output: str
    current_output: str
    
    latency_delta_ms: int = 0
    token_delta: int = 0
    
    explanation: str = ""
    suggested_action: Optional[str] = None


class DriftDetector:
    """
    Detects drift between current outputs and baseline.
    """
    
    def __init__(
        self,
        semantic_threshold: float = 0.7,
        latency_threshold_pct: float = 0.5,
        token_threshold_pct: float = 0.3,
    ):
        self.semantic_threshold = semantic_threshold
        self.latency_threshold_pct = latency_threshold_pct
        self.token_threshold_pct = token_threshold_pct
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                self._embedder = "fallback"
        return self._embedder

    def _compute_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0 if text1 != text2 else 1.0
        
        embedder = self._get_embedder()
        
        if embedder == "fallback":
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            return len(words1 & words2) / len(words1 | words2)
        
        try:
            import numpy as np
            embeddings = embedder.encode([text1, text2])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except:
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            return len(words1 & words2) / len(words1 | words2)

    def detect(
        self,
        prompt: str,
        current_output: str,
        baseline: Baseline,
        current_latency_ms: int = 0,
        current_tokens: int = 0,
    ) -> DriftResult:
        entry = baseline.get_entry_by_prompt(prompt)
        
        if not entry:
            return DriftResult(
                detected=False,
                drift_type=None,
                severity=DriftSeverity.NONE,
                similarity_score=1.0,
                baseline_entry_id=None,
                prompt=prompt,
                baseline_output="",
                current_output=current_output,
                explanation="No baseline entry for this prompt",
            )
        
        similarity = self._compute_similarity(entry.output_text, current_output)
        
        latency_delta = current_latency_ms - entry.latency_ms
        token_delta = current_tokens - entry.tokens_used
        
        drift_type = None
        detected = False
        severity = DriftSeverity.NONE
        
        if similarity < self.semantic_threshold:
            detected = True
            drift_type = DriftType.SEMANTIC
            
            if similarity < 0.3:
                severity = DriftSeverity.CRITICAL
            elif similarity < 0.5:
                severity = DriftSeverity.HIGH
            elif similarity < 0.6:
                severity = DriftSeverity.MEDIUM
            else:
                severity = DriftSeverity.LOW
        
        if entry.latency_ms > 0:
            latency_change_pct = abs(latency_delta) / entry.latency_ms
            if latency_change_pct > self.latency_threshold_pct:
                detected = True
                if drift_type is None:
                    drift_type = DriftType.PERFORMANCE
                if latency_delta > 0:
                    severity = max(severity, DriftSeverity.MEDIUM)
        
        if entry.tokens_used > 0:
            token_change_pct = abs(token_delta) / entry.tokens_used
            if token_change_pct > self.token_threshold_pct:
                detected = True
                if drift_type is None:
                    drift_type = DriftType.PERFORMANCE

        explanation = self._generate_explanation(
            detected, drift_type, severity, similarity, latency_delta, token_delta
        )
        
        suggested_action = None
        if detected:
            suggested_action = self._suggest_action(drift_type, severity)

        return DriftResult(
            detected=detected,
            drift_type=drift_type,
            severity=severity,
            similarity_score=similarity,
            baseline_entry_id=entry.id,
            prompt=prompt,
            baseline_output=entry.output_text,
            current_output=current_output,
            latency_delta_ms=latency_delta,
            token_delta=token_delta,
            explanation=explanation,
            suggested_action=suggested_action,
        )

    def detect_batch(
        self,
        prompts_and_outputs: list[tuple[str, str]],
        baseline: Baseline,
    ) -> list[DriftResult]:
        return [
            self.detect(prompt, output, baseline)
            for prompt, output in prompts_and_outputs
        ]

    def compute_drift_rate(
        self,
        results: list[DriftResult],
    ) -> dict:
        total = len(results)
        if total == 0:
            return {"drift_rate": 0, "by_severity": {}, "by_type": {}}
        
        drifted = sum(1 for r in results if r.detected)
        
        by_severity = {}
        for sev in DriftSeverity:
            count = sum(1 for r in results if r.severity == sev)
            by_severity[sev.value] = count
        
        by_type = {}
        for dt in DriftType:
            count = sum(1 for r in results if r.drift_type == dt)
            by_type[dt.value] = count
        
        return {
            "total": total,
            "drifted": drifted,
            "drift_rate": drifted / total,
            "by_severity": by_severity,
            "by_type": by_type,
        }

    def _generate_explanation(
        self,
        detected: bool,
        drift_type: Optional[DriftType],
        severity: DriftSeverity,
        similarity: float,
        latency_delta: int,
        token_delta: int,
    ) -> str:
        if not detected:
            return f"No significant drift detected. Similarity: {similarity:.1%}"
        
        parts = [f"{drift_type.value.title()} drift detected ({severity.value})."]
        
        if drift_type == DriftType.SEMANTIC:
            parts.append(f"Output similarity dropped to {similarity:.1%}.")
        
        if latency_delta != 0:
            direction = "increased" if latency_delta > 0 else "decreased"
            parts.append(f"Latency {direction} by {abs(latency_delta)}ms.")
        
        if token_delta != 0:
            direction = "increased" if token_delta > 0 else "decreased"
            parts.append(f"Token usage {direction} by {abs(token_delta)}.")
        
        return " ".join(parts)

    def _suggest_action(
        self,
        drift_type: Optional[DriftType],
        severity: DriftSeverity,
    ) -> str:
        if severity == DriftSeverity.CRITICAL:
            return "URGENT: Review immediately. Consider rolling back model version or adjusting prompts."
        
        if severity == DriftSeverity.HIGH:
            return "Review output changes. May need prompt adjustments for new model behavior."
        
        if drift_type == DriftType.SEMANTIC:
            return "Output meaning has changed. Verify if changes are acceptable or update baseline."
        
        if drift_type == DriftType.PERFORMANCE:
            return "Performance characteristics changed. Monitor for impact on user experience."
        
        return "Monitor for further drift. Consider updating baseline if changes are acceptable."


drift_detector = DriftDetector()
