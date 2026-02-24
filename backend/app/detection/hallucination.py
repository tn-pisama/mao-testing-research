"""Hallucination detection for LLM agent outputs."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import re
import numpy as np
from app.config import get_settings
from app.core.embeddings import get_embedder

settings = get_settings()


@dataclass
class HallucinationResult:
    detected: bool
    confidence: float
    hallucination_type: Optional[str]
    evidence: List[str]
    grounding_score: float
    details: Dict[str, Any] = field(default_factory=dict)
    raw_score: Optional[float] = None
    calibration_info: Optional[Dict[str, Any]] = None


@dataclass
class SourceDocument:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class HallucinationDetector:
    def __init__(
        self,
        grounding_threshold: Optional[float] = None,
        confidence_scaling: float = 1.0,
    ):
        self._embedder = None
        self.grounding_threshold = grounding_threshold or 0.65
        self.confidence_scaling = confidence_scaling
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
            self._embedder = get_embedder()
        return self._embedder
    
    def _calibrate_confidence(
        self,
        grounding_score: float,
        evidence_count: int,
        has_sources: bool,
        fabrication_score: float,
    ) -> Tuple[float, Dict[str, Any]]:
        """Calibrate confidence based on evidence quality."""
        base_confidence = 0.5
        
        if has_sources:
            base_confidence += 0.2
        
        evidence_factor = min(0.15, evidence_count * 0.03)
        base_confidence += evidence_factor
        
        grounding_factor = (1 - grounding_score) * 0.15
        base_confidence += grounding_factor
        
        fabrication_factor = (1 - fabrication_score) * 0.1
        base_confidence += fabrication_factor
        
        calibrated = min(0.99, base_confidence * self.confidence_scaling)
        
        calibration_info = {
            "base_confidence": round(base_confidence, 4),
            "evidence_count": evidence_count,
            "has_sources": has_sources,
            "grounding_factor": round(grounding_factor, 4),
            "fabrication_factor": round(fabrication_factor, 4),
        }
        
        return round(calibrated, 4), calibration_info
    
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
        if fabrication_score < 0.95:
            evidence.extend(fabrication_evidence)
            details["fabrication_indicators"] = fabrication_evidence
            # Include fabrication score in grounding decision
            grounding_score = min(grounding_score, fabrication_score)

        citation_score, citation_evidence = self._check_citation_validity(output, sources)
        if citation_score < 0.8:
            evidence.extend(citation_evidence)
            details["citation_issues"] = citation_evidence
            # Include citation score in grounding decision
            grounding_score = min(grounding_score, citation_score)

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
        
        raw_score = grounding_score
        calibrated_confidence, calibration_info = self._calibrate_confidence(
            grounding_score=grounding_score,
            evidence_count=len(evidence),
            has_sources=sources is not None and len(sources) > 0,
            fabrication_score=fabrication_score,
        )
        
        return HallucinationResult(
            detected=detected,
            confidence=calibrated_confidence,
            hallucination_type=hallucination_type,
            evidence=evidence,
            grounding_score=grounding_score,
            details=details,
            raw_score=raw_score,
            calibration_info=calibration_info,
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
        hedging_words = {"however", "though", "note", "should", "could", "might",
                         "further", "additionally", "also", "needed", "workup"}
        # Phrases that indicate the agent is honestly admitting uncertainty
        uncertainty_phrases = [
            "i don't have", "i don't know", "i'm not sure", "i cannot confirm",
            "not available", "no information", "not specified", "not mentioned",
            "no details", "no specific", "unclear whether", "unable to confirm",
        ]
        for i, sent_emb in enumerate(output_embeddings):
            max_sim = 0.0
            for src_emb in source_embeddings:
                sim = self.embedder.similarity(sent_emb, src_emb)
                max_sim = max(max_sim, sim)

            sent_lower = output_sentences[i].lower()
            sent_stripped = sent_lower.lstrip()

            # Sentences admitting uncertainty are inherently grounded (honest)
            is_uncertainty = any(p in sent_lower for p in uncertainty_phrases)
            if is_uncertainty:
                grounded_count += 1
                continue

            # Sentences that hedge, qualify, or continue a previous thought
            is_hedging = any(w in sent_lower for w in hedging_words)
            # Transition-initial sentences ("Then, ...", "Next, ...", etc.)
            # are continuations that don't need strict grounding
            transition_starts = ("then,", "then ", "next,", "next ", "finally,",
                                 "finally ", "after that,", "second,", "third,",
                                 "in summary,", "overall,", "in conclusion,")
            is_transition = any(sent_stripped.startswith(t) for t in transition_starts)
            grounding_bar = 0.45 if (is_hedging or is_transition) else 0.6

            if max_sim >= grounding_bar:
                grounded_count += 1
            elif max_sim < 0.4 and len(output_sentences[i]) > 30:
                evidence.append(f"Ungrounded claim: '{output_sentences[i][:80]}...'")

        embedding_ratio = grounded_count / len(output_sentences)

        # Entity/numerical cross-check: penalize numbers and named entities
        # in output that don't appear in any source text.
        source_blob_lower = " ".join(source_texts).lower()
        source_blob_original = " ".join(source_texts)
        novelty_penalty = self._compute_novelty_penalty(output, source_blob_lower, source_blob_original)
        if novelty_penalty > 0:
            evidence.append(f"Output introduces {novelty_penalty:.0%} novel numbers/entities not in sources")

        grounding_ratio = max(0.0, embedding_ratio - novelty_penalty)
        return grounding_ratio, evidence

    @staticmethod
    def _compute_novelty_penalty(output: str, source_blob_lower: str, source_blob_original: str = "") -> float:
        """Compute a penalty for numbers and proper nouns in output absent from sources."""
        # Extract numbers from output and sources
        output_numbers = set(re.findall(r'\b\d[\d,.]*\b', output))
        source_numbers = set(re.findall(r'\b\d[\d,.]*\b', source_blob_lower))
        novel_numbers = output_numbers - source_numbers
        # Ignore trivially small numbers (1-digit) and years already in source
        novel_numbers = {n for n in novel_numbers if len(n) > 1}

        # Extract capitalized multi-word names (potential proper nouns)
        # Use original-case source text for name extraction (regex needs uppercase)
        output_names = set(re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', output))
        source_names = set(re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', source_blob_original or source_blob_lower))
        # Check lowercase match and substring containment (e.g. "San Francisco"
        # in source should match "San Francisco Bay Area" in output).
        source_names_lower = {n.lower() for n in source_names}
        def _name_is_known(name: str) -> bool:
            nl = name.lower()
            if nl in source_names_lower:
                return True
            # Check if any source name is a prefix/substring of the output name
            for sn in source_names_lower:
                if sn in nl or nl in sn:
                    return True
            return False
        novel_names = {n for n in output_names if not _name_is_known(n)}

        total_claims = max(1, len(output_numbers) + len(output_names))
        novel_count = len(novel_numbers) + len(novel_names)
        if novel_count == 0:
            return 0.0
        # Penalty proportional to fraction of novel entities, scaled aggressively.
        # Even 1-2 novel entities in a short output is a strong hallucination signal.
        base_penalty = (novel_count / total_claims) * 0.8
        # Minimum penalty per novel entity (0.15 each, up to 0.7)
        floor_penalty = min(0.7, novel_count * 0.15)
        return min(0.7, max(base_penalty, floor_penalty))
    
    def _check_context_consistency(
        self,
        output: str,
        context: str,
    ) -> Tuple[float, List[str]]:
        evidence = []
        
        output_emb = self.embedder.encode(output)
        context_emb = self.embedder.encode(context)
        
        similarity = self.embedder.similarity(output_emb, context_emb)
        
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
        
        # (pattern, description, penalty) — higher penalty for strong signals
        specific_patterns = [
            (r'founded in \d{4}', "Specific founding year", 0.1),
            (r'according to (?:a )?\d{4} (?:study|report|survey)', "Specific study reference", 0.1),
            (r'\d+(?:\.\d+)?% of (?:people|users|companies)', "Specific percentage statistic", 0.1),
            (r'(?:Dr\.|Professor) [A-Z][a-z]+ [A-Z][a-z]+', "Named expert", 0.15),
            (r'published in (?:the )?[A-Z][a-zA-Z\s]+ Journal', "Journal reference", 0.1),
            # Fabricated URL patterns
            (r'https?://(?:www\.)?[a-z]+(?:-[a-z]+)+\.(?:com|org|io)/[a-z0-9/-]+', "Specific URL", 0.1),
            (r'https?://(?:docs|api|support)\.[a-z]+\.(?:com|org)/[a-z0-9/-]+', "Documentation URL", 0.1),
            (r'(?:visit|see|check|refer to)\s+https?://\S+', "Referenced URL", 0.1),
            # Causal/conclusion fabrication — strong signals, higher penalties
            (r'directly (?:drove|caused|led to|resulted in)', "Fabricated causal claim", 0.2),
            (r'exceeding (?:internal |expected )?(?:projections|estimates|targets)', "Fabricated comparison", 0.2),
            (r'scientists predict|experts forecast|analysts expect', "Fabricated prediction", 0.2),
            (r'which (?:scientists|researchers|experts) (?:predict|expect|forecast)', "Attributed prediction", 0.2),
        ]

        for pattern, desc, penalty in specific_patterns:
            matches = re.findall(pattern, output)
            if matches:
                for match in matches[:2]:
                    evidence.append(f"Potential fabrication ({desc}): '{match}'")
                    score -= penalty
        
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
    


hallucination_detector = HallucinationDetector()
