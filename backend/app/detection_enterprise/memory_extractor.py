"""Atomic fact extraction service for PISAMA's cognitive memory.

Uses Claude Haiku to decompose large texts (diagnosis reports, calibration
summaries, evaluation results) into atomic facts. Each fact is a single,
self-contained statement that can be stored as an independent memory.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Haiku pricing per million tokens
HAIKU_INPUT_PRICE = 1.0   # $1 per 1M input tokens
HAIKU_OUTPUT_PRICE = 5.0  # $5 per 1M output tokens
HAIKU_MODEL_ID = "claude-haiku-4-5-20251001"

VALID_MEMORY_TYPES = {
    "detection_pattern",
    "evaluation_insight",
    "fix_outcome",
    "threshold_learning",
    "false_positive_pattern",
    "framework_pattern",
}

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge extraction system. Your job is to decompose analysis text into individual, atomic facts.

Rules:
- Each fact must be a single, self-contained statement
- Each fact must be actionable for improving detection/evaluation quality
- Score importance from 0.0 (trivial) to 1.0 (critical insight)
- Classify each fact into a memory_type and domain
- Include relevant tags for filtering

Memory types: detection_pattern, evaluation_insight, fix_outcome, threshold_learning, false_positive_pattern, framework_pattern

Return a JSON array of objects with keys: content, importance, memory_type, domain, tags"""

CONTRADICTION_SYSTEM_PROMPT = """You are a knowledge consistency checker. Given a new fact and a list of existing memories, identify any contradictions.

A contradiction exists when the new fact directly opposes or invalidates an existing memory.

Return a JSON array of objects with keys: existing_index, explanation
Each object represents one contradiction between the new fact and the existing memory at that index.
Return an empty array [] if there are no contradictions."""

# Context type to default memory type mapping
_CONTEXT_TYPE_DEFAULTS = {
    "detection": "detection_pattern",
    "evaluation": "evaluation_insight",
    "fix": "fix_outcome",
    "calibration": "threshold_learning",
    "threshold": "threshold_learning",
}


@dataclass
class ExtractedFact:
    """A single atomic fact extracted from analysis text."""

    content: str           # The atomic fact
    importance: float      # 0-1
    memory_type: str       # detection_pattern, evaluation_insight, fix_outcome, threshold_learning
    domain: str            # Detection type or "evaluation", "fix"
    tags: List[str] = field(default_factory=list)


@dataclass
class Contradiction:
    """A detected contradiction between a new fact and an existing memory."""

    new_fact: str
    existing_memory_id: str
    existing_content: str
    explanation: str


@dataclass
class MemoryExtractionResult:
    """Result of an atomic fact extraction operation."""

    facts: List[ExtractedFact]
    contradictions: List[Contradiction]
    total_extracted: int
    deduplicated: int
    cost_usd: float
    tokens_used: int


class MemoryExtractor:
    """Extracts atomic facts from analysis text using Claude Haiku.

    Falls back to simple sentence splitting when no LLM client is available.
    """

    def __init__(self, llm_client: Optional[Anthropic] = None):
        """Initialize the memory extractor.

        Args:
            llm_client: An Anthropic client instance. If None, attempts to
                create one from ANTHROPIC_API_KEY env var. If no key is
                available, extraction will use the rule-based fallback.
        """
        if llm_client is not None:
            self._client = llm_client
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self._client = Anthropic(api_key=api_key)
            else:
                logger.warning(
                    "No ANTHROPIC_API_KEY found; MemoryExtractor will use fallback extraction"
                )
                self._client = None

    def extract(
        self,
        text: str,
        context_type: str,
        domain_hint: Optional[str] = None,
        max_facts: int = 20,
    ) -> MemoryExtractionResult:
        """Extract atomic facts from analysis text.

        Args:
            text: The analysis text to decompose.
            context_type: Type of analysis (e.g. "detection", "evaluation",
                "calibration", "fix").
            domain_hint: Optional domain hint (e.g. "loop", "corruption").
                If None, the LLM will auto-detect.
            max_facts: Maximum number of facts to extract.

        Returns:
            MemoryExtractionResult with extracted facts and metadata.
        """
        if self._client is None:
            return self._fallback_extract(text, context_type, domain_hint, max_facts)

        user_prompt = (
            f"Extract atomic facts from this {context_type} analysis.\n"
            f"Domain hint: {domain_hint or 'auto-detect'}\n"
            f"Maximum facts: {max_facts}\n\n"
            f"Return a JSON array of fact objects.\n\n"
            f"---\n{text}\n---"
        )

        try:
            response = self._client.messages.create(
                model=HAIKU_MODEL_ID,
                max_tokens=2000,
                system=EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:
            logger.error("LLM extraction failed, using fallback: %s", e)
            return self._fallback_extract(text, context_type, domain_hint, max_facts)

        raw = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        tokens_used = input_tokens + output_tokens
        cost_usd = (
            input_tokens * HAIKU_INPUT_PRICE + output_tokens * HAIKU_OUTPUT_PRICE
        ) / 1_000_000

        parsed = self._extract_json(raw)
        if not isinstance(parsed, list):
            parsed = [parsed] if isinstance(parsed, dict) else []

        facts: List[ExtractedFact] = []
        for item in parsed[:max_facts]:
            if not isinstance(item, dict) or "content" not in item:
                continue
            memory_type = item.get("memory_type", "detection_pattern")
            if memory_type not in VALID_MEMORY_TYPES:
                memory_type = "detection_pattern"
            facts.append(
                ExtractedFact(
                    content=item["content"],
                    importance=max(0.0, min(1.0, float(item.get("importance", 0.5)))),
                    memory_type=memory_type,
                    domain=item.get("domain", domain_hint or "unknown"),
                    tags=item.get("tags", []),
                )
            )

        total_extracted = len(facts)
        facts = self._deduplicate(facts)
        deduplicated = total_extracted - len(facts)

        return MemoryExtractionResult(
            facts=facts,
            contradictions=[],
            total_extracted=total_extracted,
            deduplicated=deduplicated,
            cost_usd=cost_usd,
            tokens_used=tokens_used,
        )

    def detect_contradictions(
        self,
        new_fact: str,
        existing_memories: List[Dict[str, str]],
    ) -> List[Contradiction]:
        """Detect contradictions between a new fact and existing memories.

        Args:
            new_fact: The new fact to check.
            existing_memories: List of dicts with at least "id" and "content" keys.

        Returns:
            List of Contradiction objects for any detected conflicts.
        """
        if not existing_memories:
            return []

        if self._client is None:
            contradictions = []
            for mem in existing_memories:
                if self._heuristic_contradiction(new_fact, mem.get("content", "")):
                    contradictions.append(
                        Contradiction(
                            new_fact=new_fact,
                            existing_memory_id=mem.get("id", "unknown"),
                            existing_content=mem.get("content", ""),
                            explanation="Heuristic: negation pattern detected",
                        )
                    )
            return contradictions

        memories_text = "\n".join(
            f"[{i}] (id={m.get('id', 'unknown')}): {m.get('content', '')}"
            for i, m in enumerate(existing_memories)
        )
        user_prompt = (
            f"New fact: {new_fact}\n\n"
            f"Existing memories:\n{memories_text}\n\n"
            f"Identify any contradictions. Return a JSON array."
        )

        try:
            response = self._client.messages.create(
                model=HAIKU_MODEL_ID,
                max_tokens=1000,
                system=CONTRADICTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:
            logger.error("LLM contradiction check failed: %s", e)
            return []

        raw = response.content[0].text
        parsed = self._extract_json(raw)
        if not isinstance(parsed, list):
            return []

        contradictions: List[Contradiction] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            idx = item.get("existing_index")
            if idx is None or not isinstance(idx, int):
                continue
            if 0 <= idx < len(existing_memories):
                mem = existing_memories[idx]
                contradictions.append(
                    Contradiction(
                        new_fact=new_fact,
                        existing_memory_id=mem.get("id", "unknown"),
                        existing_content=mem.get("content", ""),
                        explanation=item.get("explanation", "LLM-detected contradiction"),
                    )
                )

        return contradictions

    def _fallback_extract(
        self,
        text: str,
        context_type: str,
        domain_hint: Optional[str],
        max_facts: int,
    ) -> MemoryExtractionResult:
        """Simple sentence-based extraction when no LLM is available.

        Splits text into sentences, filters short ones, and wraps them as
        ExtractedFact objects with default metadata.
        """
        # Determine default memory type from context
        memory_type = _CONTEXT_TYPE_DEFAULTS.get(context_type, "detection_pattern")
        domain = domain_hint or context_type

        # Split into sentences on period, exclamation, question mark
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        facts: List[ExtractedFact] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and len(facts) < max_facts:
                facts.append(
                    ExtractedFact(
                        content=sentence,
                        importance=0.5,
                        memory_type=memory_type,
                        domain=domain,
                        tags=[],
                    )
                )

        return MemoryExtractionResult(
            facts=facts,
            contradictions=[],
            total_extracted=len(facts),
            deduplicated=0,
            cost_usd=0.0,
            tokens_used=0,
        )

    def _heuristic_contradiction(self, new_fact: str, existing_content: str) -> bool:
        """Check for negation patterns that suggest contradiction.

        Very simple heuristic: looks for negation words in the new fact that
        could indicate it contradicts existing content.
        """
        negation_patterns = [
            r"\bnot\b",
            r"\bno longer\b",
            r"\binstead of\b",
            r"\bunlike\b",
            r"\bcontrary\b",
            r"\bworse\b.*\bbetter\b",
            r"\bbetter\b.*\bworse\b",
            r"\bnever\b",
            r"\bincorrect\b",
        ]
        new_lower = new_fact.lower()
        existing_lower = existing_content.lower()

        # Extract key terms from existing content (words > 4 chars)
        existing_terms = {
            w for w in re.findall(r'\b\w+\b', existing_lower) if len(w) > 4
        }
        new_terms = {w for w in re.findall(r'\b\w+\b', new_lower) if len(w) > 4}

        # Need some topic overlap to be a contradiction
        overlap = existing_terms & new_terms
        if len(overlap) < 2:
            return False

        for pattern in negation_patterns:
            if re.search(pattern, new_lower):
                return True

        return False

    def _deduplicate(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        """Remove near-duplicate facts based on word overlap.

        Two facts are considered duplicates if their word overlap ratio
        exceeds 0.9.
        """
        if not facts:
            return facts

        unique: List[ExtractedFact] = [facts[0]]
        for fact in facts[1:]:
            is_dup = False
            fact_words = set(fact.content.lower().split())
            for existing in unique:
                existing_words = set(existing.content.lower().split())
                if not fact_words or not existing_words:
                    continue
                intersection = fact_words & existing_words
                union = fact_words | existing_words
                similarity = len(intersection) / len(union) if union else 0.0
                if similarity > 0.9:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(fact)

        return unique

    def _extract_json(self, text: str) -> Any:
        """Extract JSON from LLM response, handling various formats.

        Tries multiple strategies:
        1. Direct json.loads
        2. Extract from ```json code blocks
        3. Extract from ``` code blocks
        4. Find JSON array/object with brace/bracket matching
        5. Return empty list on failure
        """
        # Try direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try ```json ... ``` blocks
        match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # Try ``` ... ``` blocks
        match = re.search(r"```\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # Try finding JSON array
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

        # Try finding JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

        logger.warning("Failed to extract JSON from LLM response")
        return []
