from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import numpy as np
from app.config import get_settings
from app.core.embeddings import get_embedder

settings = get_settings()


class RoleType(Enum):
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    ASSISTANT = "assistant"
    SPECIALIST = "specialist"
    CONVERSATIONAL = "conversational"


ROLE_THRESHOLDS: Dict[RoleType, Dict[str, float]] = {
    RoleType.CREATIVE: {
        "consistency_threshold": 0.55,
        "drift_threshold": 0.25,
        "flexibility_bonus": 0.15,
    },
    RoleType.ANALYTICAL: {
        "consistency_threshold": 0.75,
        "drift_threshold": 0.12,
        "flexibility_bonus": 0.0,
    },
    RoleType.ASSISTANT: {
        "consistency_threshold": 0.65,
        "drift_threshold": 0.18,
        "flexibility_bonus": 0.08,
    },
    RoleType.SPECIALIST: {
        "consistency_threshold": 0.72,
        "drift_threshold": 0.14,
        "flexibility_bonus": 0.05,
    },
    RoleType.CONVERSATIONAL: {
        "consistency_threshold": 0.58,
        "drift_threshold": 0.22,
        "flexibility_bonus": 0.12,
    },
}

ROLE_KEYWORDS: Dict[RoleType, List[str]] = {
    RoleType.CREATIVE: ["writer", "artist", "creative", "storyteller", "poet", "designer", "imaginative"],
    RoleType.ANALYTICAL: ["analyst", "researcher", "data", "scientific", "logical", "statistical"],
    RoleType.ASSISTANT: ["assistant", "helper", "support", "general", "helpful"],
    RoleType.SPECIALIST: ["expert", "specialist", "professional", "domain", "technical"],
    RoleType.CONVERSATIONAL: ["chat", "conversational", "friendly", "casual", "companion"],
}


@dataclass
class Agent:
    id: str
    persona_description: str
    allowed_actions: List[str]
    role_type: Optional[RoleType] = None
    custom_thresholds: Optional[Dict[str, float]] = None


@dataclass
class PersonaConsistencyResult:
    consistent: bool
    score: float
    method: str
    drift_detected: bool
    drift_magnitude: Optional[float] = None
    issues: Optional[List[str]] = None
    role_type: Optional[RoleType] = None
    confidence: float = 0.0
    factors: Dict[str, float] = field(default_factory=dict)
    raw_score: Optional[float] = None
    evidence: Optional[Dict] = None


class PersonaConsistencyScorer:
    def __init__(
        self,
        consistency_threshold: Optional[float] = None,
        drift_threshold: Optional[float] = None,
        confidence_scaling: float = 1.0,
    ):
        self._embedder = None
        self.default_consistency_threshold = consistency_threshold or 0.7
        self.default_drift_threshold = drift_threshold or 0.15
        self.confidence_scaling = confidence_scaling
        self._role_embedding_cache: Dict[str, np.ndarray] = {}
    
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder
    
    def _calibrate_confidence(
        self,
        semantic_sim: float,
        lexical_overlap: float,
        tone_score: float,
        output_length: int,
        drift_detected: bool = False,
    ) -> float:
        """Calibrate confidence based on evidence quality.

        Returns high confidence for consistent personas (so drift confidence
        is low when inverted), and lower confidence when drift is detected
        (so drift confidence is higher when inverted).

        v1.1: Better separation between strong drift (low similarity) and
        borderline drift (moderate similarity). Strong drift gets lower scores
        (higher drift confidence); borderline cases get moderate scores.
        """
        length_factor = min(1.0, output_length / 500)
        signal_count = sum([
            semantic_sim > 0.5,
            lexical_overlap > 0.3,
            tone_score > 0.6,
        ])
        signal_factor = signal_count / 3

        if drift_detected:
            # Drift detected → return LOW score so 1-score gives HIGH drift confidence
            # v1.1: Scale by how far below threshold — strong drift gets lower score
            if semantic_sim < 0.3:
                # Strong drift — high confidence
                base_confidence = 0.15 + (signal_factor * 0.05)
            elif semantic_sim < 0.5:
                # Clear drift — moderate-high confidence
                base_confidence = 0.25 + (signal_factor * 0.08)
            else:
                # Borderline drift — moderate confidence
                base_confidence = 0.35 + (signal_factor * 0.10)
        else:
            # Consistent → return HIGH score so 1-score gives LOW drift confidence
            base_confidence = 0.7 + (semantic_sim * 0.15) + (length_factor * 0.05) + (signal_factor * 0.1)

        calibrated = min(0.99, base_confidence * self.confidence_scaling)
        return round(calibrated, 4)
    
    def _detect_role_type(self, persona_description: str) -> RoleType:
        """Auto-detect role type from persona description."""
        desc_lower = persona_description.lower()
        
        scores = {}
        for role_type, keywords in ROLE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in desc_lower)
            scores[role_type] = score
        
        if max(scores.values()) == 0:
            return RoleType.ASSISTANT
        
        return max(scores, key=scores.get)
    
    def _get_thresholds(self, agent: Agent) -> Dict[str, float]:
        """Get role-specific thresholds for the agent."""
        if agent.custom_thresholds:
            return agent.custom_thresholds
        
        role_type = agent.role_type or self._detect_role_type(agent.persona_description)
        return ROLE_THRESHOLDS.get(role_type, ROLE_THRESHOLDS[RoleType.ASSISTANT])
    
    def _compute_semantic_similarity(self, agent: Agent, output: str) -> float:
        """Compute semantic similarity with caching."""
        cache_key = f"{agent.id}:{agent.persona_description[:50]}"
        
        if cache_key not in self._role_embedding_cache:
            self._role_embedding_cache[cache_key] = self.embedder.encode(agent.persona_description)
        
        persona_embedding = self._role_embedding_cache[cache_key]
        output_embedding = self.embedder.encode(output)
        
        return float(self.embedder.similarity(persona_embedding, output_embedding))
    
    def _compute_lexical_overlap(self, persona: str, output: str) -> float:
        """Compute lexical overlap as secondary signal."""
        persona_words = set(persona.lower().split())
        output_words = set(output.lower().split())
        
        if not persona_words:
            return 0.0
        
        overlap = len(persona_words & output_words)
        return min(1.0, overlap / (len(persona_words) * 0.3))
    
    def _compute_tone_consistency(self, output: str, expected_tone: str = "neutral") -> float:
        """Check if output matches expected tone."""
        formal_markers = ["therefore", "consequently", "furthermore", "regarding"]
        casual_markers = ["hey", "yeah", "cool", "awesome", "lol"]
        
        output_lower = output.lower()
        formal_score = sum(1 for m in formal_markers if m in output_lower)
        casual_score = sum(1 for m in casual_markers if m in output_lower)
        
        if expected_tone == "formal":
            return min(1.0, 0.5 + formal_score * 0.1 - casual_score * 0.15)
        elif expected_tone == "casual":
            return min(1.0, 0.5 + casual_score * 0.1 - formal_score * 0.15)
        
        return 0.7
    
    def score_consistency(
        self,
        agent: Agent,
        output: str,
        recent_outputs: Optional[List[str]] = None,
    ) -> PersonaConsistencyResult:
        thresholds = self._get_thresholds(agent)
        consistency_threshold = thresholds["consistency_threshold"]
        drift_threshold = thresholds["drift_threshold"]
        flexibility_bonus = thresholds.get("flexibility_bonus", 0.0)
        
        role_type = agent.role_type or self._detect_role_type(agent.persona_description)
        
        semantic_sim = self._compute_semantic_similarity(agent, output)
        lexical_overlap = self._compute_lexical_overlap(agent.persona_description, output)
        tone_score = self._compute_tone_consistency(output)
        
        raw_score = semantic_sim
        
        weighted_score = (
            semantic_sim * 0.6 +
            lexical_overlap * 0.2 +
            tone_score * 0.2 +
            flexibility_bonus
        )
        weighted_score = min(1.0, weighted_score)
        
        factors = {
            "semantic_similarity": round(semantic_sim, 4),
            "lexical_overlap": round(lexical_overlap, 4),
            "tone_consistency": round(tone_score, 4),
            "flexibility_bonus": flexibility_bonus,
        }
        
        drift_detected = False
        drift_magnitude = None
        
        if recent_outputs and len(recent_outputs) >= 3:
            recent_embeddings = self.embedder.encode(recent_outputs)
            avg_recent = np.mean(recent_embeddings, axis=0)
            output_embedding = self.embedder.encode(output)
            drift_magnitude = float(1 - self.embedder.similarity(avg_recent, output_embedding))
            
            adjusted_drift_threshold = drift_threshold
            if role_type == RoleType.CREATIVE:
                adjusted_drift_threshold *= 1.3
            
            drift_detected = drift_magnitude > adjusted_drift_threshold
            factors["drift_magnitude"] = round(drift_magnitude, 4)
        
        confidence = self._calibrate_confidence(
            semantic_sim=semantic_sim,
            lexical_overlap=lexical_overlap,
            tone_score=tone_score,
            output_length=len(output),
            drift_detected=drift_detected,
        )
        
        evidence = {
            "output_length": len(output),
            "consistency_threshold": consistency_threshold,
            "role_type": role_type.value if role_type else None,
        }
        
        if weighted_score > consistency_threshold and not drift_detected:
            return PersonaConsistencyResult(
                consistent=True,
                score=float(weighted_score),
                method="multi_factor_scoring",
                drift_detected=False,
                role_type=role_type,
                confidence=confidence,
                factors=factors,
                raw_score=raw_score,
                evidence=evidence,
            )
        
        issues = []
        if weighted_score < consistency_threshold:
            issues.append(f"Output deviates from persona (score: {weighted_score:.2f}, threshold: {consistency_threshold:.2f})")
        if drift_detected:
            issues.append(f"Persona drift detected (magnitude: {drift_magnitude:.2f})")
        
        return PersonaConsistencyResult(
            consistent=weighted_score > consistency_threshold and not drift_detected,
            score=float(weighted_score),
            method="multi_factor_scoring_with_drift",
            drift_detected=drift_detected,
            drift_magnitude=drift_magnitude,
            issues=issues if issues else None,
            role_type=role_type,
            confidence=confidence,
            factors=factors,
            raw_score=raw_score,
            evidence=evidence,
        )
    
    def detect_role_usurpation(
        self,
        agent: Agent,
        output: str,
        all_agents: List[Agent],
    ) -> Optional[str]:
        agent_embedding = self.embedder.encode(agent.persona_description)
        output_embedding = self.embedder.encode(output)
        
        own_similarity = self.embedder.similarity(agent_embedding, output_embedding)
        
        for other_agent in all_agents:
            if other_agent.id == agent.id:
                continue
            
            other_embedding = self.embedder.encode(other_agent.persona_description)
            other_similarity = self.embedder.similarity(other_embedding, output_embedding)
            
            if other_similarity > own_similarity + 0.1:
                return other_agent.id
        
        return None
    


persona_scorer = PersonaConsistencyScorer()
