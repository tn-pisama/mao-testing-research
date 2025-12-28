"""Hallucination detection for LLM agent outputs."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import get_settings

settings = get_settings()


@dataclass
class HallucinationResult:
    detected: bool
    confidence: float
    hallucination_type: Optional[str]
    evidence: List[str]
    grounding_score: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceDocument:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class HallucinationDetector:
    def __init__(self):
        self._embedder = None
        self.grounding_threshold = 0.65
        self.citation_pattern = re.compile(r'\[(\d+)\]|\(source:?\s*([^)]+)\)|\{\{cite:[^}]+\}\}', re.IGNORECASE)
        self.confidence_phrases = [
            "I'm not sure", "I don't know", "I cannot confirm",
            "I believe", "I think", "possibly", "perhaps", "might be",
            "as far as I know", "to my knowledge",
        ]
        self.definitive_phrases = [
            "definitely", "certainly", "absolutely", "always", "never",
            "100%", "guaranteed", "proven fact", "undoubtedly",
        ]
    
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = SentenceTransformer(settings.embedding_model)
        return self._embedder
    
    def detect_hallucination(
        self,
        output: str,
        sources: Optional[List[SourceDocument]] = None,
        context: Optional[str] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> HallucinationResult:
        evidence = []
        details = {}
        
        grounding_score = 1.0
        hallucination_type = None
        
        if sources:
            source_score, source_evidence = self._check_source_grounding(output, sources)
            grounding_score = min(grounding_score, source_score)
            evidence.extend(source_evidence)
            details["source_grounding_score"] = source_score
        
        if context:
            context_score, context_evidence = self._check_context_consistency(output, context)
            grounding_score = min(grounding_score, context_score)
            evidence.extend(context_evidence)
            details["context_consistency_score"] = context_score
        
        if tool_results:
            tool_score, tool_evidence = self._check_tool_result_consistency(output, tool_results)
            grounding_score = min(grounding_score, tool_score)
            evidence.extend(tool_evidence)
            details["tool_result_score"] = tool_score
        
        fabrication_score, fabrication_evidence = self._detect_fabricated_facts(output)
        if fabrication_score < 0.7:
            evidence.extend(fabrication_evidence)
            details["fabrication_indicators"] = fabrication_evidence
        
        citation_score, citation_evidence = self._check_citation_validity(output, sources)
        if citation_score < 0.8:
            evidence.extend(citation_evidence)
            details["citation_issues"] = citation_evidence
        
        confidence_score = self._analyze_confidence_calibration(output)
        details["confidence_calibration"] = confidence_score
        
        detected = grounding_score < self.grounding_threshold
        
        if detected:
            if details.get("source_grounding_score", 1.0) < 0.5:
                hallucination_type = "ungrounded_claim"
            elif details.get("tool_result_score", 1.0) < 0.5:
                hallucination_type = "tool_result_contradiction"
            elif details.get("citation_issues"):
                hallucination_type = "invalid_citation"
            elif fabrication_score < 0.5:
                hallucination_type = "fabricated_fact"
            else:
                hallucination_type = "general_hallucination"
        
        return HallucinationResult(
            detected=detected,
            confidence=1 - grounding_score if detected else grounding_score,
            hallucination_type=hallucination_type,
            evidence=evidence,
            grounding_score=grounding_score,
            details=details,
        )
    
    def _check_source_grounding(
        self,
        output: str,
        sources: List[SourceDocument],
    ) -> Tuple[float, List[str]]:
        if not sources:
            return 1.0, []
        
        evidence = []
        
        output_sentences = self._split_sentences(output)
        if not output_sentences:
            return 1.0, []
        
        source_texts = [s.content for s in sources]
        all_texts = output_sentences + source_texts
        embeddings = self.embedder.encode(all_texts)
        
        output_embeddings = embeddings[:len(output_sentences)]
        source_embeddings = embeddings[len(output_sentences):]
        
        grounded_count = 0
        for i, sent_emb in enumerate(output_embeddings):
            max_sim = 0.0
            for src_emb in source_embeddings:
                sim = self._cosine_similarity(sent_emb, src_emb)
                max_sim = max(max_sim, sim)
            
            if max_sim >= 0.6:
                grounded_count += 1
            elif max_sim < 0.4 and len(output_sentences[i]) > 30:
                evidence.append(f"Ungrounded claim: '{output_sentences[i][:80]}...'")
        
        grounding_ratio = grounded_count / len(output_sentences)
        return grounding_ratio, evidence
    
    def _check_context_consistency(
        self,
        output: str,
        context: str,
    ) -> Tuple[float, List[str]]:
        evidence = []
        
        output_emb = self.embedder.encode(output)
        context_emb = self.embedder.encode(context)
        
        similarity = self._cosine_similarity(output_emb, context_emb)
        
        if similarity < 0.4:
            evidence.append("Output has low semantic similarity to context")
        
        return similarity, evidence
    
    def _check_tool_result_consistency(
        self,
        output: str,
        tool_results: List[Dict[str, Any]],
    ) -> Tuple[float, List[str]]:
        evidence = []
        output_lower = output.lower()
        
        contradictions = 0
        total_checks = 0
        
        for result in tool_results:
            tool_name = result.get("tool", "unknown")
            tool_output = str(result.get("result", ""))
            
            if not tool_output:
                continue
            
            total_checks += 1
            
            numbers_in_tool = re.findall(r'\b\d+\.?\d*\b', tool_output)
            for num in numbers_in_tool[:5]:
                if num in output:
                    continue
                try:
                    num_val = float(num)
                    if num_val > 100:
                        pattern = rf'\b{int(num_val)}\b'
                        if not re.search(pattern, output):
                            contradictions += 0.5
                            evidence.append(f"Tool '{tool_name}' returned {num} but value not reflected in output")
                except ValueError:
                    pass
        
        if total_checks == 0:
            return 1.0, []
        
        consistency_score = max(0, 1 - (contradictions / total_checks))
        return consistency_score, evidence
    
    def _detect_fabricated_facts(self, output: str) -> Tuple[float, List[str]]:
        evidence = []
        score = 1.0
        
        specific_patterns = [
            (r'founded in \d{4}', "Specific founding year"),
            (r'according to (?:a )?\d{4} (?:study|report|survey)', "Specific study reference"),
            (r'\d+(?:\.\d+)?% of (?:people|users|companies)', "Specific percentage statistic"),
            (r'(?:Dr\.|Professor) [A-Z][a-z]+ [A-Z][a-z]+', "Named expert"),
            (r'published in (?:the )?[A-Z][a-zA-Z\s]+ Journal', "Journal reference"),
        ]
        
        for pattern, desc in specific_patterns:
            matches = re.findall(pattern, output)
            if matches:
                for match in matches[:2]:
                    evidence.append(f"Potential fabrication ({desc}): '{match}'")
                    score -= 0.1
        
        definitive_count = sum(1 for phrase in self.definitive_phrases if phrase.lower() in output.lower())
        if definitive_count >= 3:
            evidence.append(f"High definitiveness ({definitive_count} definitive phrases) may indicate overconfidence")
            score -= 0.15
        
        return max(0, score), evidence
    
    def _check_citation_validity(
        self,
        output: str,
        sources: Optional[List[SourceDocument]],
    ) -> Tuple[float, List[str]]:
        evidence = []
        
        citations = self.citation_pattern.findall(output)
        if not citations:
            return 1.0, []
        
        if sources is None:
            if citations:
                evidence.append(f"Output contains {len(citations)} citations but no sources provided")
                return 0.5, evidence
            return 1.0, []
        
        num_sources = len(sources)
        invalid_citations = 0
        
        for match in citations:
            cite_num = match[0] if match[0] else None
            if cite_num:
                try:
                    idx = int(cite_num)
                    if idx < 1 or idx > num_sources:
                        invalid_citations += 1
                        evidence.append(f"Citation [{cite_num}] references non-existent source")
                except ValueError:
                    pass
        
        if invalid_citations > 0:
            score = max(0, 1 - (invalid_citations / len(citations)))
            return score, evidence
        
        return 1.0, []
    
    def _analyze_confidence_calibration(self, output: str) -> float:
        output_lower = output.lower()
        
        uncertainty_count = sum(1 for phrase in self.confidence_phrases if phrase.lower() in output_lower)
        definitive_count = sum(1 for phrase in self.definitive_phrases if phrase.lower() in output_lower)
        
        if definitive_count > uncertainty_count + 2:
            return 0.6
        elif uncertainty_count > definitive_count:
            return 0.9
        return 0.75
    
    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 20]
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


hallucination_detector = HallucinationDetector()
