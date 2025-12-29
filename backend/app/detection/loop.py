import hashlib
import json
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from sklearn.cluster import KMeans
from app.config import get_settings
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
            self._embedder = get_embedder()
        return self._embedder
    
    def detect_loop(self, states: List[StateSnapshot]) -> LoopDetectionResult:
        if len(states) < 3:
            return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0)
        
        current = states[-1]
        window = states[-self.window_size:-1] if len(states) > self.window_size else states[:-1]
        
        for i, prev in enumerate(window):
            if self._structural_match(current, prev):
                if not self._has_meaningful_progress(prev, current):
                    loop_length = len(window) - i
                    window_start = max(0, len(states) - self.window_size - 1)
                    loop_start_index = window_start + i
                    return LoopDetectionResult(
                        detected=True,
                        confidence=0.95,
                        method="structural",
                        cost=0.0,
                        loop_start_index=loop_start_index,
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
            if len(contents) < 4:
                return LoopDetectionResult(detected=False, confidence=0.0, method=None, cost=0.0)
            
            embeddings = self.embedder.encode(contents)
            
            current_emb = embeddings[-1]
            similarities = []
            for i, emb in enumerate(embeddings[:-1]):
                sim = self.embedder.similarity(current_emb, emb)
                similarities.append((i, sim))
            
            high_sim_matches = [(i, sim) for i, sim in similarities if sim > self.semantic_threshold]
            
            if len(high_sim_matches) >= 2:
                first_match_idx = high_sim_matches[0][0]
                avg_similarity = sum(s for _, s in high_sim_matches) / len(high_sim_matches)
                loop_length = len(window) - first_match_idx
                window_start = max(0, len(states) - self.window_size - 1)
                
                return LoopDetectionResult(
                    detected=True,
                    confidence=min(0.85, avg_similarity),
                    method="semantic",
                    cost=0.0,
                    loop_start_index=window_start + first_match_idx,
                    loop_length=loop_length,
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
