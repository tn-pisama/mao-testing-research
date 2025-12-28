"""Prompt injection and jailbreak detection."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import get_settings

settings = get_settings()


@dataclass
class InjectionResult:
    detected: bool
    confidence: float
    attack_type: Optional[str]
    severity: str
    matched_patterns: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


INJECTION_PATTERNS = [
    (r'ignore (?:all )?(?:previous|prior|above) (?:instructions?|prompts?|rules?)', "direct_override", "high"),
    (r'disregard (?:all )?(?:previous|prior|your) (?:instructions?|guidelines?|rules?)', "direct_override", "high"),
    (r'forget (?:everything|all|what) (?:you were|I) (?:told|said)', "direct_override", "high"),
    (r'new instructions?:?\s', "instruction_injection", "high"),
    (r'from now on,?\s+(?:you|your)', "instruction_injection", "high"),
    (r'your (?:new|real|actual|true) (?:instructions?|purpose|goal|role)', "instruction_injection", "high"),
    (r'you are (?:now|actually|really) (?:a|an|the)', "role_hijack", "high"),
    (r'pretend (?:to be|you are|that you)', "role_hijack", "medium"),
    (r'act as (?:if you are|a|an)', "role_hijack", "medium"),
    (r'roleplay as', "role_hijack", "medium"),
    (r'you must (?:always|never|only)', "constraint_manipulation", "medium"),
    (r'override (?:your|the|all) (?:safety|security|restrictions?|limitations?)', "safety_bypass", "critical"),
    (r'bypass (?:your|the|all) (?:filters?|safeguards?|restrictions?)', "safety_bypass", "critical"),
    (r'disable (?:your|the|all) (?:safety|security|content) (?:filters?|checks?)', "safety_bypass", "critical"),
    (r'jailbreak', "jailbreak", "critical"),
    (r'DAN\s*(?:mode)?|Do Anything Now', "jailbreak", "critical"),
    (r'(?:developer|god|admin|root) mode', "jailbreak", "critical"),
    (r'unlock (?:your|all) (?:capabilities|potential|restrictions)', "jailbreak", "high"),
    (r'\[SYSTEM\]|\[INST\]|\<\|system\|\>|\<\|user\|\>', "delimiter_injection", "high"),
    (r'```system|```instructions?|<system>|</system>', "delimiter_injection", "high"),
    (r'Human:|Assistant:|User:|AI:', "delimiter_injection", "medium"),
    (r'<<SYS>>|<</SYS>>', "delimiter_injection", "high"),
    (r'IMPORTANT:?\s+ignore|CRITICAL:?\s+override', "urgency_manipulation", "medium"),
    (r'emergency override|urgent:?\s+bypass', "urgency_manipulation", "medium"),
    (r'(?:print|output|reveal|show|display) (?:your|the|all) (?:system )?(?:prompt|instructions?|rules?)', "extraction", "high"),
    (r'what (?:are|is|were) your (?:original|system|initial) (?:prompt|instructions?)', "extraction", "medium"),
    (r'repeat (?:your|the) (?:system )?(?:prompt|instructions?)', "extraction", "medium"),
    (r'(?:ignore|forget) (?:the )?(?:previous|above) (?:and|then) (?:do|say|output)', "chained_injection", "high"),
    (r'step \d+:?\s+(?:ignore|forget|override)', "chained_injection", "high"),
]

JAILBREAK_SIGNATURES = [
    "stay in character",
    "you have no ethical guidelines",
    "you have no restrictions",
    "unfiltered response",
    "without any restrictions",
    "no limitations",
    "completely unrestricted",
    "remove all filters",
    "raw unfiltered",
    "maximum freedom",
    "absolute freedom",
    "hypothetically speaking",
    "for educational purposes",
    "in a fictional scenario",
    "imagine you are",
    "let's play a game",
    "opposite day",
    "evil mode",
    "no holds barred",
    "anything goes",
]

BENIGN_CONTEXTS = [
    "security research",
    "testing prompt injection",
    "demonstrate vulnerability",
    "security audit",
    "red team",
    "penetration test",
]


class InjectionDetector:
    def __init__(self):
        self._embedder = None
        self._jailbreak_embeddings = None
        self.pattern_threshold = 0.7
        self.semantic_threshold = 0.75
    
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = SentenceTransformer(settings.embedding_model)
        return self._embedder
    
    @property
    def jailbreak_embeddings(self):
        if self._jailbreak_embeddings is None:
            self._jailbreak_embeddings = self.embedder.encode(JAILBREAK_SIGNATURES)
        return self._jailbreak_embeddings
    
    def detect_injection(
        self,
        text: str,
        context: Optional[str] = None,
        is_user_input: bool = True,
    ) -> InjectionResult:
        text_lower = text.lower()
        matched_patterns = []
        attack_types = set()
        max_severity = "low"
        details = {}
        
        for pattern, attack_type, severity in INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                matched_patterns.append(pattern)
                attack_types.add(attack_type)
                if self._severity_rank(severity) > self._severity_rank(max_severity):
                    max_severity = severity
        
        details["pattern_matches"] = len(matched_patterns)
        
        jailbreak_score = self._check_jailbreak_signatures(text_lower)
        details["jailbreak_score"] = jailbreak_score
        if jailbreak_score > 0.5:
            attack_types.add("jailbreak")
            if jailbreak_score > 0.7:
                max_severity = "critical"
            elif jailbreak_score > 0.5:
                max_severity = max(max_severity, "high", key=self._severity_rank)
        
        semantic_score = self._semantic_injection_check(text)
        details["semantic_score"] = semantic_score
        if semantic_score > self.semantic_threshold:
            attack_types.add("semantic_injection")
        
        structure_score = self._check_structural_anomalies(text)
        details["structure_score"] = structure_score
        if structure_score > 0.6:
            attack_types.add("structural_attack")
        
        if context:
            context_score = self._check_context_manipulation(text, context)
            details["context_manipulation_score"] = context_score
            if context_score > 0.7:
                attack_types.add("context_manipulation")
        
        is_benign = self._check_benign_context(text_lower)
        details["benign_context"] = is_benign
        
        detected = len(matched_patterns) > 0 or jailbreak_score > 0.5 or semantic_score > self.semantic_threshold
        
        if is_benign and max_severity != "critical":
            detected = False
            max_severity = "info"
        
        confidence = self._calculate_confidence(
            len(matched_patterns),
            jailbreak_score,
            semantic_score,
            structure_score,
        )
        
        primary_attack = None
        if attack_types:
            priority = ["jailbreak", "safety_bypass", "direct_override", "extraction", 
                       "instruction_injection", "role_hijack", "delimiter_injection"]
            for attack in priority:
                if attack in attack_types:
                    primary_attack = attack
                    break
            if not primary_attack:
                primary_attack = list(attack_types)[0]
        
        return InjectionResult(
            detected=detected,
            confidence=confidence,
            attack_type=primary_attack,
            severity=max_severity,
            matched_patterns=matched_patterns,
            details=details,
        )
    
    def _severity_rank(self, severity: str) -> int:
        ranks = {"low": 0, "medium": 1, "high": 2, "critical": 3, "info": -1}
        return ranks.get(severity, 0)
    
    def _check_jailbreak_signatures(self, text: str) -> float:
        matches = sum(1 for sig in JAILBREAK_SIGNATURES if sig in text)
        if matches == 0:
            return 0.0
        return min(1.0, matches / 3)
    
    def _semantic_injection_check(self, text: str) -> float:
        if len(text) < 20:
            return 0.0
        
        text_embedding = self.embedder.encode(text)
        
        max_similarity = 0.0
        for jb_emb in self.jailbreak_embeddings:
            sim = self._cosine_similarity(text_embedding, jb_emb)
            max_similarity = max(max_similarity, sim)
        
        return max_similarity
    
    def _check_structural_anomalies(self, text: str) -> float:
        score = 0.0
        
        special_chars = len(re.findall(r'[\[\]<>{}|`]', text))
        if special_chars > 10:
            score += 0.2
        
        if re.search(r'[\u200b-\u200f\u2028-\u202f\u00a0]', text):
            score += 0.3
        
        newline_ratio = text.count('\n') / max(1, len(text))
        if newline_ratio > 0.1:
            score += 0.2
        
        if re.search(r'(.{10,})\1{2,}', text):
            score += 0.3
        
        return min(1.0, score)
    
    def _check_context_manipulation(self, text: str, context: str) -> float:
        text_lower = text.lower()
        context_lower = context.lower()
        
        topic_switch_phrases = [
            "now let's talk about",
            "forget that",
            "instead",
            "actually",
            "on a different note",
            "change of topic",
        ]
        
        score = 0.0
        for phrase in topic_switch_phrases:
            if phrase in text_lower:
                score += 0.3
        
        return min(1.0, score)
    
    def _check_benign_context(self, text: str) -> bool:
        return any(context in text for context in BENIGN_CONTEXTS)
    
    def _calculate_confidence(
        self,
        pattern_count: int,
        jailbreak_score: float,
        semantic_score: float,
        structure_score: float,
    ) -> float:
        if pattern_count == 0 and jailbreak_score < 0.3 and semantic_score < 0.5:
            return 0.0
        
        confidence = (
            min(pattern_count * 0.2, 0.4) +
            jailbreak_score * 0.3 +
            semantic_score * 0.2 +
            structure_score * 0.1
        )
        
        return min(1.0, confidence)
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def analyze_output_for_jailbreak_success(self, output: str) -> Tuple[bool, float, List[str]]:
        evidence = []
        score = 0.0
        
        success_indicators = [
            "certainly, here's",
            "sure, I'll",
            "of course, I can",
            "absolutely, here",
            "I'll help you with that",
            "[in character]",
            "as requested",
            "*evil grin*",
            "*removes restrictions*",
        ]
        
        output_lower = output.lower()
        for indicator in success_indicators:
            if indicator.lower() in output_lower:
                evidence.append(f"Success indicator: '{indicator}'")
                score += 0.2
        
        refusal_phrases = [
            "I cannot",
            "I'm not able to",
            "I won't",
            "I can't help with",
            "against my guidelines",
            "I must refuse",
            "not appropriate",
        ]
        
        has_refusal = any(phrase.lower() in output_lower for phrase in refusal_phrases)
        if has_refusal:
            score = max(0, score - 0.5)
        
        return score > 0.3, min(1.0, score), evidence


injection_detector = InjectionDetector()
