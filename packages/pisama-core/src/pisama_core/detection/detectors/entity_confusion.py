"""Entity confusion detector for identifying when agents mix up entities.

Detects:
- Attribute swaps: entity A's known attribute applied to entity B
- Entity merging: two distinct entities treated as one in the output
- Role/property confusion between named entities

Version History:
- v1.0: Initial implementation
"""

import re
from typing import Any

from pisama_core.detection.base import BaseDetector
from pisama_core.detection.result import DetectionResult, FixType
from pisama_core.traces.models import Trace, Span
from pisama_core.traces.enums import SpanKind

# Common role/title words for entity profiling
_ROLE_INDICATORS = {
    "ceo", "cto", "cfo", "coo", "cio", "vp", "director", "manager",
    "engineer", "developer", "designer", "architect", "analyst", "lead",
    "president", "founder", "co-founder", "chief", "head", "partner",
    "consultant", "advisor", "intern", "assistant", "coordinator",
    "specialist", "officer", "supervisor",
}

# Attribute type indicators
_LOCATION_INDICATORS = {
    "located", "based", "headquarters", "office", "city", "country",
    "state", "region", "address", "branch",
}

_PRICE_INDICATORS = {
    "costs", "priced", "price", "worth", "$", "dollars", "euros",
    "revenue", "salary", "budget", "fee", "rate",
}

# Words to skip when extracting named entities
_ENTITY_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "has", "have", "had",
    "will", "would", "could", "should", "may", "might", "can", "do",
    "does", "did", "been", "being", "that", "this", "these", "those",
    "and", "but", "or", "not", "for", "with", "from", "into", "about",
    "between", "through", "during", "before", "after", "above", "below",
    "then", "than", "when", "where", "while", "because", "since",
    "also", "however", "therefore", "thus", "hence", "so", "yet",
    "very", "most", "more", "less", "much", "many", "some", "any",
    "each", "every", "all", "both", "either", "neither", "such",
    "here", "there", "now", "just", "only", "even", "still",
    "already", "always", "never", "often", "sometimes", "usually",
    # Common sentence starters that get capitalized but aren't entities
    "However", "Therefore", "Furthermore", "Additionally", "Moreover",
    "Meanwhile", "Nevertheless", "Consequently", "Specifically",
    "First", "Second", "Third", "Next", "Finally", "Then", "Also",
    "Based", "According", "Note", "Please", "Step", "Task",
}


class EntityConfusionDetector(BaseDetector):
    """Detects when an agent mixes up entities from context or memory.

    Analyzes agent spans and LLM spans to find:
    - Attribute swaps between named entities
    - Entity merging (two distinct entities conflated)
    - Role/property confusion
    """

    name = "entity_confusion"
    description = "Detects entity attribute swaps and confusion between named entities"
    version = "1.0.0"
    platforms = []  # All platforms
    severity_range = (30, 80)
    realtime_capable = False

    # Configuration
    min_entities = 2  # Need at least 2 entities to detect confusion
    attribute_confidence_threshold = 0.6

    async def detect(self, trace: Trace) -> DetectionResult:
        """Detect entity confusion in a trace."""
        # Collect input context and output text from relevant spans
        context_texts: list[str] = []
        output_texts: list[str] = []
        relevant_span_ids: list[str] = []

        for span in trace.spans:
            if span.kind in (SpanKind.LLM, SpanKind.AGENT, SpanKind.AGENT_TURN):
                input_text = self._get_text(span.input_data)
                output_text = self._get_text(span.output_data)
                if input_text:
                    context_texts.append(input_text)
                if output_text:
                    output_texts.append(output_text)
                    relevant_span_ids.append(span.span_id)

        if not context_texts or not output_texts:
            return DetectionResult.no_issue(self.name)

        full_context = " ".join(context_texts)
        full_output = " ".join(output_texts)

        # Extract named entities from context
        entities = self._extract_entities(full_context)
        if len(entities) < self.min_entities:
            return DetectionResult.no_issue(self.name)

        # Build entity profiles from context
        profiles = self._build_profiles(entities, full_context)

        issues: list[str] = []
        severity = 0
        evidence_data: dict[str, Any] = {}

        # Check for attribute swaps in output
        swaps = self._check_attribute_swaps(profiles, full_output)
        if swaps:
            severity += 45
            for swap in swaps:
                issues.append(swap["message"])
            evidence_data["attribute_swaps"] = swaps

        # Check for entity merging in output
        merges = self._check_entity_merging(entities, profiles, full_output)
        if merges:
            severity += 35
            for merge in merges:
                issues.append(merge["message"])
            evidence_data["entity_merges"] = merges

        if not issues:
            return DetectionResult.no_issue(self.name)

        severity = min(self.severity_range[1], max(self.severity_range[0], severity))

        result = DetectionResult.issue_found(
            detector_name=self.name,
            severity=severity,
            summary=issues[0],
            fix_type=FixType.RESET_CONTEXT,
            fix_instruction=(
                "Re-read the source context carefully. "
                "Verify that each entity's attributes match the original data."
            ),
        )

        for issue in issues:
            result.add_evidence(
                description=issue,
                span_ids=relevant_span_ids[:10],
                data=evidence_data,
            )

        return result

    def _extract_entities(self, text: str) -> list[str]:
        """Extract named entities from text using capitalization heuristics."""
        entities: list[str] = []
        seen_lower: set[str] = set()

        # Match capitalized multi-word phrases (e.g., "John Smith", "Acme Corp")
        multi_word = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text)
        for phrase in multi_word:
            if phrase not in _ENTITY_STOP_WORDS and phrase.lower() not in seen_lower:
                entities.append(phrase)
                seen_lower.add(phrase.lower())

        # Match single capitalized words that appear after entity-introducing patterns
        # e.g., "John is the CEO" or "about Alice"
        introducing_patterns = [
            r'(?:about|named|called|for|by|of|from)\s+([A-Z][a-z]{2,})',
            r'([A-Z][a-z]{2,})\s+(?:is|was|has|works|lives|said|told|asked)',
            r'([A-Z][a-z]{2,})(?:\'s)\b',
        ]
        for pattern in introducing_patterns:
            matches = re.findall(pattern, text)
            for name in matches:
                if name not in _ENTITY_STOP_WORDS and name.lower() not in seen_lower:
                    entities.append(name)
                    seen_lower.add(name.lower())

        return entities

    def _build_profiles(
        self, entities: list[str], context: str,
    ) -> dict[str, dict[str, list[str]]]:
        """Build attribute profiles for each entity from context text.

        Returns: {entity_name: {"roles": [...], "locations": [...], "values": [...]}}
        """
        profiles: dict[str, dict[str, list[str]]] = {}

        for entity in entities:
            profile: dict[str, list[str]] = {"roles": [], "locations": [], "values": []}

            # Find sentences containing this entity
            sentences = self._get_sentences_with_entity(entity, context)

            for sentence in sentences:
                sent_lower = sentence.lower()
                entity_lower = entity.lower()

                # Extract roles
                for role in _ROLE_INDICATORS:
                    if role in sent_lower and entity_lower in sent_lower:
                        # Verify the role is associated with this entity (within proximity)
                        entity_pos = sent_lower.find(entity_lower)
                        role_pos = sent_lower.find(role)
                        if abs(entity_pos - role_pos) < 60:
                            profile["roles"].append(role)

                # Extract locations
                for loc_word in _LOCATION_INDICATORS:
                    if loc_word in sent_lower and entity_lower in sent_lower:
                        # Extract the value after the location indicator
                        value = self._extract_value_near(loc_word, sentence)
                        if value:
                            profile["locations"].append(value.lower())

                # Extract numeric values/prices
                for price_word in _PRICE_INDICATORS:
                    if price_word in sent_lower and entity_lower in sent_lower:
                        numbers = re.findall(
                            r'[\$\€]?\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|k|m))?',
                            sentence,
                        )
                        profile["values"].extend(n.strip() for n in numbers if n.strip())

            if any(v for v in profile.values()):
                profiles[entity] = profile

        return profiles

    def _check_attribute_swaps(
        self, profiles: dict[str, dict[str, list[str]]], output: str,
    ) -> list[dict[str, Any]]:
        """Check if attributes of one entity are applied to another in output."""
        swaps: list[dict[str, Any]] = []
        entity_list = list(profiles.keys())

        for i, entity_a in enumerate(entity_list):
            for entity_b in entity_list[i + 1:]:
                profile_a = profiles[entity_a]
                profile_b = profiles[entity_b]

                # Check if entity_a's roles are attributed to entity_b in output
                for attr_type in ("roles", "locations", "values"):
                    for attr_val in profile_a.get(attr_type, []):
                        if self._attribute_applied_to(entity_b, attr_val, output):
                            # Verify this attribute is NOT also in entity_b's profile
                            if attr_val not in profile_b.get(attr_type, []):
                                swaps.append({
                                    "message": (
                                        f"Entity confusion: {entity_a}'s {attr_type[:-1]} "
                                        f"'{attr_val}' is attributed to {entity_b} in output"
                                    ),
                                    "entity_a": entity_a,
                                    "entity_b": entity_b,
                                    "attribute_type": attr_type,
                                    "attribute_value": attr_val,
                                })

                    for attr_val in profile_b.get(attr_type, []):
                        if self._attribute_applied_to(entity_a, attr_val, output):
                            if attr_val not in profile_a.get(attr_type, []):
                                swaps.append({
                                    "message": (
                                        f"Entity confusion: {entity_b}'s {attr_type[:-1]} "
                                        f"'{attr_val}' is attributed to {entity_a} in output"
                                    ),
                                    "entity_a": entity_b,
                                    "entity_b": entity_a,
                                    "attribute_type": attr_type,
                                    "attribute_value": attr_val,
                                })

        return swaps

    def _check_entity_merging(
        self,
        entities: list[str],
        profiles: dict[str, dict[str, list[str]]],
        output: str,
    ) -> list[dict[str, Any]]:
        """Check if two distinct entities are merged into one in the output."""
        merges: list[dict[str, Any]] = []
        output_lower = output.lower()

        for i, entity_a in enumerate(entities):
            for entity_b in entities[i + 1:]:
                a_lower = entity_a.lower()
                b_lower = entity_b.lower()

                # Check for merged references: "entity_a/entity_b" or "entity_a (entity_b)"
                merge_patterns = [
                    re.escape(a_lower) + r'\s*/\s*' + re.escape(b_lower),
                    re.escape(b_lower) + r'\s*/\s*' + re.escape(a_lower),
                    re.escape(a_lower) + r'\s*\(\s*' + re.escape(b_lower) + r'\s*\)',
                    re.escape(b_lower) + r'\s*\(\s*' + re.escape(a_lower) + r'\s*\)',
                    re.escape(a_lower) + r'\s+(?:aka|or|and)\s+' + re.escape(b_lower),
                ]

                for pattern in merge_patterns:
                    if re.search(pattern, output_lower):
                        # Only flag if both entities have distinct profiles
                        if entity_a in profiles and entity_b in profiles:
                            merges.append({
                                "message": (
                                    f"Entity merging: '{entity_a}' and '{entity_b}' "
                                    f"appear to be treated as the same entity in output"
                                ),
                                "entity_a": entity_a,
                                "entity_b": entity_b,
                            })
                            break

                # Check if only one entity is mentioned but has attributes from both
                a_in_output = a_lower in output_lower
                b_in_output = b_lower in output_lower
                if a_in_output and not b_in_output:
                    # entity_b is missing -- check if entity_a has entity_b's attributes
                    if entity_a in profiles and entity_b in profiles:
                        b_attrs = set()
                        for vals in profiles[entity_b].values():
                            b_attrs.update(vals)
                        a_attrs = set()
                        for vals in profiles[entity_a].values():
                            a_attrs.update(vals)
                        # entity_b's unique attributes found near entity_a
                        unique_b = b_attrs - a_attrs
                        if unique_b:
                            applied = [
                                attr for attr in unique_b
                                if self._attribute_applied_to(entity_a, attr, output)
                            ]
                            if applied:
                                merges.append({
                                    "message": (
                                        f"Entity merging: '{entity_b}' is absent from output "
                                        f"but its attributes ({', '.join(applied[:3])}) are "
                                        f"attributed to '{entity_a}'"
                                    ),
                                    "entity_a": entity_a,
                                    "entity_b": entity_b,
                                    "merged_attributes": applied[:5],
                                })

        return merges

    @staticmethod
    def _get_sentences_with_entity(entity: str, text: str) -> list[str]:
        """Get sentences containing a specific entity."""
        sentences = re.split(r'[.!?\n]+', text)
        entity_lower = entity.lower()
        return [s.strip() for s in sentences if entity_lower in s.lower() and s.strip()]

    @staticmethod
    def _extract_value_near(indicator: str, sentence: str) -> str | None:
        """Extract a value word/phrase near an indicator word in a sentence."""
        pattern = rf'{re.escape(indicator)}\s+(?:in|at|is)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _attribute_applied_to(entity: str, attribute: str, text: str) -> bool:
        """Check if an attribute is mentioned near an entity in the text."""
        text_lower = text.lower()
        entity_lower = entity.lower()
        attr_lower = attribute.lower()

        if entity_lower not in text_lower or attr_lower not in text_lower:
            return False

        # Check proximity: attribute within 100 chars of entity mention
        entity_positions = [
            m.start() for m in re.finditer(re.escape(entity_lower), text_lower)
        ]
        attr_positions = [
            m.start() for m in re.finditer(re.escape(attr_lower), text_lower)
        ]

        for e_pos in entity_positions:
            for a_pos in attr_positions:
                if abs(e_pos - a_pos) < 100:
                    return True

        return False

    @staticmethod
    def _get_text(data: dict[str, Any] | None) -> str:
        """Extract text from span data dict."""
        if not data:
            return ""
        for key in ("content", "text", "response", "prompt", "context", "input", "output"):
            val = data.get(key, "")
            if isinstance(val, str) and val:
                return val
        # Fallback: join string values
        parts = [str(v) for v in data.values() if isinstance(v, str) and v]
        return " ".join(parts)
