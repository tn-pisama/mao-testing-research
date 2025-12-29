"""
F7: Context Neglect Detection (MAST Taxonomy)
==============================================

Detects when an agent ignores or fails to use upstream context
provided by previous agents or steps in the workflow.

This is a critical failure mode in multi-agent systems where
information is passed between agents via handoffs.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re

logger = logging.getLogger(__name__)


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
        
        detected = utilization < self.utilization_threshold
        
        if not detected:
            return ContextNeglectResult(
                detected=False,
                severity=NeglectSeverity.NONE,
                confidence=utilization,
                context_utilization=utilization,
                missing_elements=[],
                explanation="Agent properly utilized upstream context",
            )

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
