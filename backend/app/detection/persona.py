from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import get_settings

settings = get_settings()


@dataclass
class Agent:
    id: str
    persona_description: str
    allowed_actions: List[str]


@dataclass
class PersonaConsistencyResult:
    consistent: bool
    score: float
    method: str
    drift_detected: bool
    drift_magnitude: Optional[float] = None
    issues: Optional[List[str]] = None


class PersonaConsistencyScorer:
    def __init__(self):
        self._embedder = None
        self.consistency_threshold = 0.7
        self.drift_threshold = 0.15
    
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = SentenceTransformer(settings.embedding_model)
        return self._embedder
    
    def score_consistency(
        self,
        agent: Agent,
        output: str,
        recent_outputs: Optional[List[str]] = None,
    ) -> PersonaConsistencyResult:
        persona_embedding = self.embedder.encode(agent.persona_description)
        output_embedding = self.embedder.encode(output)
        cosine_sim = self._cosine_similarity(persona_embedding, output_embedding)
        
        if cosine_sim > self.consistency_threshold:
            return PersonaConsistencyResult(
                consistent=True,
                score=float(cosine_sim),
                method="cosine_similarity",
                drift_detected=False,
            )
        
        drift_detected = False
        drift_magnitude = None
        
        if recent_outputs and len(recent_outputs) >= 3:
            recent_embeddings = self.embedder.encode(recent_outputs)
            avg_recent = np.mean(recent_embeddings, axis=0)
            drift_magnitude = float(1 - self._cosine_similarity(avg_recent, output_embedding))
            drift_detected = drift_magnitude > self.drift_threshold
        
        issues = []
        if cosine_sim < self.consistency_threshold:
            issues.append(f"Output deviates from persona (similarity: {cosine_sim:.2f})")
        if drift_detected:
            issues.append(f"Persona drift detected (magnitude: {drift_magnitude:.2f})")
        
        return PersonaConsistencyResult(
            consistent=cosine_sim > self.consistency_threshold and not drift_detected,
            score=float(cosine_sim),
            method="cosine_similarity_with_drift",
            drift_detected=drift_detected,
            drift_magnitude=drift_magnitude,
            issues=issues if issues else None,
        )
    
    def detect_role_usurpation(
        self,
        agent: Agent,
        output: str,
        all_agents: List[Agent],
    ) -> Optional[str]:
        agent_embedding = self.embedder.encode(agent.persona_description)
        output_embedding = self.embedder.encode(output)
        
        own_similarity = self._cosine_similarity(agent_embedding, output_embedding)
        
        for other_agent in all_agents:
            if other_agent.id == agent.id:
                continue
            
            other_embedding = self.embedder.encode(other_agent.persona_description)
            other_similarity = self._cosine_similarity(other_embedding, output_embedding)
            
            if other_similarity > own_similarity + 0.1:
                return other_agent.id
        
        return None
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


persona_scorer = PersonaConsistencyScorer()
