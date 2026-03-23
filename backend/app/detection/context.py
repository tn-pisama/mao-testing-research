"""
F7: Context Neglect Detection (MAST Taxonomy)
==============================================

Detects when an agent ignores or fails to use upstream context
provided by previous agents or steps in the workflow.

This is a critical failure mode in multi-agent systems where
information is passed between agents via handoffs.

Version History:
- v1.0: Initial implementation with keyword element matching
- v1.1: Reduced over-detection on legitimate adaptations
  - Added task completion check (if task addressed, be lenient)
  - Added adaptation recognition (reformats, methodology changes, rewrites)
  - Added conceptual overlap scoring for semantic matching
- v1.2: Stricter detection for critical context
  - Added CRITICAL/IMPORTANT marker detection
  - Raised task_addressed threshold from 0.15 to 0.25
  - Added critical keyword requirement check
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re

logger = logging.getLogger(__name__)

# Detector version for tracking
DETECTOR_VERSION = "1.2"
DETECTOR_NAME = "ContextNeglectDetector"

# v1.2: Markers indicating critical context that should not be ignored
# v1.2.1: Made more strict - only explicit critical/important markers, not soft markers
CRITICAL_CONTEXT_MARKERS = [
    "critical:", "important:", "critical -", "important -",
    "must handle", "must address", "must review", "must consider",
    "required:", "mandatory:",
    "do not ignore", "don't ignore",
]

# Phrases that indicate the output is building on/referencing prior context
CONTEXT_REFERENCE_PHRASES = [
    "based on", "building on", "as discussed", "as mentioned",
    "from the previous", "from earlier", "continuing from",
    "following up on", "as per", "according to",
    "incorporating", "using the", "reviewing the",
    "analyzed the", "examined the", "looked at the",
    "the existing", "the current", "the original",
    # v1.1: Additional patterns
    "our previous", "the previous", "previous analysis",
    "previous research", "previous work", "prior work",
    "reflecting on", "building upon", "extending",
    "referenced", "referring to", "as noted",
]

# Phrases that indicate legitimate adaptation of context
ADAPTATION_PHRASES = [
    "reformatted", "restructured", "reorganized", "updated format",
    "different approach", "alternative method", "new methodology",
    "refactored", "rewritten", "rewrote", "reimplemented",
    "improved", "enhanced", "optimized", "streamlined",
    "modernized", "simplified", "clarified",
    # v1.1: Additional patterns
    "pivot", "pivoting", "adjusted", "modified approach",
    "adapted", "evolved", "iterated",
]


class NeglectSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class ContextNeglectResult:
    detected: bool
    severity: NeglectSeverity
    confidence: float
    context_utilization: float
    missing_elements: list[str]
    explanation: str
    suggested_fix: Optional[str] = None
    context_referenced: bool = False  # v1.1: Output explicitly references context
    adaptation_detected: bool = False  # v1.1: Output adapts rather than ignores
    version: str = DETECTOR_VERSION


class ContextNeglectDetector:
    """
    Detects F7: Context Neglect - when an agent ignores upstream context.
    
    Analyzes whether key information from the provided context
    is reflected in the agent's output.
    """
    
    def __init__(
        self,
        utilization_threshold: float = 0.3,
        min_context_length: int = 50,
        extract_entities: bool = True,
    ):
        self.utilization_threshold = utilization_threshold
        self.min_context_length = min_context_length
        self.extract_entities = extract_entities

    def _extract_key_elements(self, text: str) -> dict[str, set[str]]:
        elements = {
            "numbers": set(),
            "dates": set(),
            "names": set(),
            "urls": set(),
            "emails": set(),
            "keywords": set(),
        }
        
        numbers = re.findall(r'\b\d+(?:\.\d+)?(?:%|k|m|b)?\b', text.lower())
        elements["numbers"] = set(numbers)
        
        dates = re.findall(
            r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|'
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s+\d{4})?)\b',
            text.lower()
        )
        elements["dates"] = set(dates)
        
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        elements["names"] = set(capitalized)
        
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
        elements["urls"] = set(urls)
        
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        elements["emails"] = set(emails)
        
        words = text.lower().split()
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "and", "but", "or", "nor", "so", "yet", "not", "it",
        }
        keywords = {w for w in words if len(w) > 4 and w not in stopwords}
        elements["keywords"] = keywords
        
        return elements

    def _compute_utilization(
        self,
        context_elements: dict[str, set[str]],
        output_elements: dict[str, set[str]],
    ) -> tuple[float, list[str]]:
        total_weight = 0
        utilized_weight = 0
        missing = []
        
        weights = {
            "numbers": 3.0,
            "dates": 3.0,
            "names": 2.5,
            "urls": 2.0,
            "emails": 2.0,
            "keywords": 1.0,
        }
        
        for element_type, weight in weights.items():
            context_set = context_elements.get(element_type, set())
            output_set = output_elements.get(element_type, set())
            
            for item in context_set:
                total_weight += weight
                if any(item.lower() in o.lower() or o.lower() in item.lower() 
                       for o in output_set):
                    utilized_weight += weight
                else:
                    if element_type in ["numbers", "dates", "names"]:
                        missing.append(f"{element_type}: {item}")
        
        if total_weight == 0:
            return 1.0, []

        return utilized_weight / total_weight, missing[:10]

    def _check_context_reference(self, output: str) -> bool:
        """v1.1: Check if output explicitly references prior context."""
        output_lower = output.lower()
        for phrase in CONTEXT_REFERENCE_PHRASES:
            if phrase in output_lower:
                return True
        return False

    def _check_adaptation(self, output: str) -> bool:
        """v1.1: Check if output indicates legitimate adaptation of context."""
        output_lower = output.lower()
        for phrase in ADAPTATION_PHRASES:
            if phrase in output_lower:
                return True
        return False

    def _has_critical_context(self, context: str) -> bool:
        """v1.2: Check if context contains critical markers requiring strict matching."""
        context_lower = context.lower()
        for marker in CRITICAL_CONTEXT_MARKERS:
            if marker in context_lower:
                return True
        return False

    def _extract_critical_topics(self, context: str) -> set[str]:
        """v1.2: Extract key topic words from context sections marked as critical/important.

        Finds words near CRITICAL/IMPORTANT markers that represent the key topics
        that should be addressed in the output.
        """
        context_lower = context.lower()
        critical_topics = set()

        # Split into sentences/sections
        sections = re.split(r'[.!?]', context_lower)

        for section in sections:
            # Check if section has critical markers
            has_marker = any(marker in section for marker in CRITICAL_CONTEXT_MARKERS)
            if has_marker:
                # Extract significant words from this section (domain-specific terms)
                # Look for hyphenated terms (like "token-expiration-cleanup")
                hyphenated = re.findall(r'\b[a-z]+-[a-z]+(?:-[a-z]+)*\b', section)
                critical_topics.update(hyphenated)

                # Look for capitalized terms that were lowercased (like "SessionManager")
                # These would appear as camelCase or compound words
                compounds = re.findall(r'\b[a-z]+(?:manager|handler|controller|service|config|policy|hook|store)\b', section)
                critical_topics.update(compounds)

        return critical_topics

    def _check_critical_topics_addressed(self, critical_topics: set[str], output: str) -> tuple[bool, set[str]]:
        """v1.2: Check if critical topics from context are addressed in output.

        Returns (addressed, missing) where addressed is True if enough critical
        topics are mentioned, and missing contains the unaddressed topics.

        v1.2.1: Made matching stricter - require either full topic or
        multiple significant parts (at least 2) to match.
        """
        if not critical_topics:
            return True, set()

        output_lower = output.lower()
        addressed = set()
        missing = set()

        for topic in critical_topics:
            # Check if full topic appears in output
            if topic in output_lower:
                addressed.add(topic)
                continue

            # For hyphenated topics, require at least 2 significant parts to match
            topic_parts = [p for p in topic.split('-') if len(p) > 4]
            if len(topic_parts) >= 2:
                # Count how many parts appear in output
                parts_matched = sum(1 for part in topic_parts if part in output_lower)
                if parts_matched >= 2:
                    addressed.add(topic)
                    continue

            # For compound words (like sessionmanager), check if they appear
            if len(topic) > 10 and topic in output_lower:
                addressed.add(topic)
                continue

            missing.add(topic)

        # v1.3: Require at least 50% of critical topics to be addressed (raised from 30%)
        if not critical_topics:
            return True, set()

        coverage = len(addressed) / len(critical_topics)
        return coverage >= 0.5, missing

    def _is_task_addressed(self, task: str, output: str) -> bool:
        """v1.1: Check if output addresses the core task request.

        If the task is addressed, we should be more lenient about
        exact context element matching.
        """
        if not task:
            return False

        task_lower = task.lower()
        output_lower = output.lower()

        # Extract key action from task
        action_patterns = [
            ("update", ["updated", "updating", "incorporated", "added new"]),
            ("continue", ["continued", "continuing", "building on", "following up"]),
            ("improve", ["improved", "improving", "enhanced", "optimized"]),
            ("fix", ["fixed", "fixing", "resolved", "corrected", "patched"]),
            ("analyze", ["analyzed", "analysis", "examined", "reviewed"]),
            ("report", ["reported", "report", "findings", "documented"]),
            ("review", ["reviewed", "review", "examined", "checked"]),
            ("document", ["documented", "documentation", "docs"]),
        ]

        for action, indicators in action_patterns:
            if action in task_lower:
                if any(ind in output_lower for ind in indicators):
                    return True

        # Check if core task nouns appear in output
        task_words = set(task_lower.split())
        output_words = set(output_lower.split())
        stopwords = {"the", "a", "an", "to", "for", "with", "from", "and", "or", "in", "on"}
        task_keywords = {w for w in task_words if len(w) > 3 and w not in stopwords}

        if task_keywords:
            overlap = task_keywords & output_words
            if len(overlap) >= len(task_keywords) * 0.5:
                return True

        return False

    def detect(
        self,
        context: str,
        output: str,
        task: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> ContextNeglectResult:
        if len(context) < self.min_context_length:
            return ContextNeglectResult(
                detected=False,
                severity=NeglectSeverity.NONE,
                confidence=0.0,
                context_utilization=1.0,
                missing_elements=[],
                explanation="Context too short to analyze",
            )

        context_elements = self._extract_key_elements(context)
        output_elements = self._extract_key_elements(output)

        utilization, missing = self._compute_utilization(
            context_elements, output_elements
        )

        # v1.1: Check for context references and adaptations
        context_referenced = self._check_context_reference(output)
        adaptation_detected = self._check_adaptation(output)
        task_addressed = self._is_task_addressed(task, output) if task else False

        # v1.2: Check if context has critical markers (requires stricter matching)
        has_critical_context = self._has_critical_context(context)

        # v1.2: Extract and check critical topics if present
        critical_topics = set()
        critical_topics_addressed = True
        critical_topics_missing = set()
        if has_critical_context:
            critical_topics = self._extract_critical_topics(context)
            critical_topics_addressed, critical_topics_missing = self._check_critical_topics_addressed(
                critical_topics, output
            )

        # v1.2: Set thresholds based on context importance
        # Critical context requires higher utilization to pass
        task_utilization_threshold = 0.35 if has_critical_context else 0.15  # Raised from 0.25 for critical context

        # v1.3: Improved detection logic with tighter skip conditions.
        # Key insight: explicit context reference shows awareness, but
        # saying "based on your context" while ignoring actual content
        # should still be flagged.
        #
        # v1.2.2: CRITICAL CONTEXT OVERRIDE
        # If there are critical topics that aren't addressed, detect failure
        # regardless of other heuristics (context reference, adaptation, etc.)
        if has_critical_context and not critical_topics_addressed:
            detected = True
            # Add critical topics to missing elements for explanation
            missing.extend([f"critical: {t}" for t in list(critical_topics_missing)[:5]])
        # 1. If utilization is good, no neglect
        elif utilization >= self.utilization_threshold:
            detected = False
        # 2. If output explicitly references prior context → OK only if some
        #    utilization exists. v1.3: reference without any actual context usage
        #    (utilization < 0.10) suggests a superficial reference.
        elif context_referenced and utilization >= 0.10:
            detected = False
        # 3. If output shows adaptation AND addresses task AND uses some context → OK
        #    (legitimate methodology change while doing the task)
        #    v1.3: Require utilization >= 0.15 to prevent bypass with just an adaptation phrase
        elif adaptation_detected and task_addressed and utilization >= 0.15:
            detected = False
        # 4. If task is addressed AND utilization meets threshold → OK
        elif task_addressed and utilization >= task_utilization_threshold:
            detected = False
        # 5. Otherwise, context neglect detected
        else:
            detected = True

        if not detected:
            explanation = "Agent properly utilized upstream context"
            if context_referenced:
                explanation = "Agent explicitly referenced prior context"
            elif adaptation_detected and task_addressed:
                explanation = "Agent adapted context with different approach while addressing task"
            elif task_addressed:
                explanation = "Agent addressed task requirements using context appropriately"

            return ContextNeglectResult(
                detected=False,
                severity=NeglectSeverity.NONE,
                confidence=max(utilization, 0.7 if task_addressed else utilization),
                context_utilization=utilization,
                missing_elements=[],
                explanation=explanation,
                context_referenced=context_referenced,
                adaptation_detected=adaptation_detected,
            )

        # Neglect detected - determine severity
        if utilization < 0.1:
            severity = NeglectSeverity.SEVERE
        elif utilization < 0.2:
            severity = NeglectSeverity.MODERATE
        else:
            severity = NeglectSeverity.MINOR

        confidence = 1 - utilization

        agent_prefix = f"Agent '{agent_name}'" if agent_name else "Agent"
        explanation = (
            f"{agent_prefix} failed to utilize upstream context. "
            f"Context utilization: {utilization:.1%} (threshold: {self.utilization_threshold:.1%}). "
            f"Missing key elements: {', '.join(missing[:5]) if missing else 'general context'}."
        )

        suggested_fix = (
            "Ensure the agent's prompt explicitly references the context. "
            "Add instructions like: 'Use the following context to inform your response: [CONTEXT]. "
            "Make sure to reference specific details from the context.'"
        )

        return ContextNeglectResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            context_utilization=utilization,
            missing_elements=missing,
            explanation=explanation,
            suggested_fix=suggested_fix,
            context_referenced=context_referenced,
            adaptation_detected=adaptation_detected,
        )

    def detect_handoff(
        self,
        sender_output: str,
        receiver_input: str,
        receiver_output: str,
        sender_name: Optional[str] = None,
        receiver_name: Optional[str] = None,
    ) -> ContextNeglectResult:
        result = self.detect(
            context=sender_output,
            output=receiver_output,
            agent_name=receiver_name,
        )
        
        if result.detected and sender_name:
            result.explanation = (
                f"Agent '{receiver_name or 'downstream'}' ignored context from "
                f"'{sender_name}'. " + result.explanation
            )
        
        return result

    def detect_from_trace(
        self,
        trace: dict,
    ) -> list[ContextNeglectResult]:
        results = []
        
        spans = trace.get("spans", [])
        for i, span in enumerate(spans):
            context = span.get("input", {}).get("context", "")
            output = span.get("output", {}).get("content", "")
            agent_name = span.get("name", "")
            
            if i > 0 and spans[i-1].get("output", {}).get("content"):
                prev_output = spans[i-1]["output"]["content"]
                context = f"{context}\n{prev_output}" if context else prev_output
            
            if context and output:
                result = self.detect(
                    context=context,
                    output=output,
                    agent_name=agent_name,
                )
                if result.detected:
                    results.append(result)

        return results

    def get_config(self) -> dict:
        """Return detector configuration for versioning."""
        return {
            "name": DETECTOR_NAME,
            "version": DETECTOR_VERSION,
            "thresholds": {
                "utilization_threshold": self.utilization_threshold,
                "min_context_length": self.min_context_length,
            },
            "description": "Context neglect detection with adaptation recognition",
        }
