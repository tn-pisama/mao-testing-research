import hashlib
import json
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from app.config import get_settings

settings = get_settings()


@dataclass
class LoopDetectionResult:
    detected: bool
    confidence: float
    method: Optional[str]
    cost: float
    loop_start_index: Optional[int] = None
    loop_length: Optional[int] = None


@dataclass
class StateSnapshot:
    agent_id: str
    state_delta: dict
    content: str
    sequence_num: int


class MultiLevelLoopDetector:
    def __init__(self):
        self._embedder = None
        self.structural_threshold = settings.structural_threshold
        self.semantic_threshold = settings.semantic_threshold
        self.window_size = settings.loop_detection_window
    
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = SentenceTransformer(settings.embedding_model)
        return self._embedder
    
    def detect_loop(self, states: List[StateSnapshot]) -> LoopDetectionResult:
        if len(states) < 3:
            return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0)
        
        current = states[-1]
        window = states[-self.window_size:-1] if len(states) > self.window_size else states[:-1]
        
        for i, prev in enumerate(window):
            if self._structural_match(current, prev):
                if not self._has_meaningful_progress(prev, current):
                    loop_length = len(states) - 1 - (len(states) - self.window_size + i)
                    return LoopDetectionResult(
                        detected=True,
                        confidence=0.95,
                        method="structural",
                        cost=0.0,
                        loop_start_index=len(states) - 1 - loop_length,
                        loop_length=loop_length,
                    )
        
        current_hash = self._compute_state_hash(current)
        for i, prev in enumerate(window):
            prev_hash = self._compute_state_hash(prev)
            if current_hash == prev_hash:
                loop_length = len(window) - i
                return LoopDetectionResult(
                    detected=True,
                    confidence=0.90,
                    method="hash",
                    cost=0.0,
                    loop_start_index=len(states) - 1 - loop_length,
                    loop_length=loop_length,
                )
        
        try:
            contents = [s.content for s in window] + [current.content]
            embeddings = self.embedder.encode(contents)
            
            n_clusters = min(3, len(embeddings))
            if n_clusters < 2:
                return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0)
            
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            clusters = kmeans.fit_predict(embeddings)
            
            if len(set(clusters)) == 1:
                return LoopDetectionResult(
                    detected=True,
                    confidence=0.80,
                    method="clustering",
                    cost=0.0,
                    loop_start_index=len(states) - len(embeddings),
                    loop_length=len(embeddings),
                )
        except Exception:
            pass
        
        return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0)
    
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


loop_detector = MultiLevelLoopDetector()
