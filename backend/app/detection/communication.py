"""
F10: Communication Breakdown Detection (MAST Taxonomy)
======================================================

Detects when a message between agents is misunderstood or 
misinterpreted, leading to incorrect behavior downstream.

This includes:
- Intent misalignment (sender meant X, receiver understood Y)
- Format mismatches (expected JSON, got prose)
- Semantic misinterpretation (ambiguous language)
"""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BreakdownType(str, Enum):
    INTENT_MISMATCH = "intent_mismatch"
    FORMAT_MISMATCH = "format_mismatch"
    SEMANTIC_AMBIGUITY = "semantic_ambiguity"
    INCOMPLETE_INFORMATION = "incomplete_information"
    CONFLICTING_INSTRUCTIONS = "conflicting_instructions"


class BreakdownSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class CommunicationBreakdownResult:
    detected: bool
    breakdown_type: Optional[BreakdownType]
    severity: BreakdownSeverity
    confidence: float
    intent_alignment: float
    format_match: bool
    explanation: str
    suggested_fix: Optional[str] = None


class CommunicationBreakdownDetector:
    """
    Detects F10: Communication Breakdown - message misunderstanding between agents.
    
    Analyzes message intent, format compliance, and semantic clarity
    to detect communication failures.
    """
    
    def __init__(
        self,
        intent_threshold: float = 0.45,  # v1.2: Lowered from 0.60 — paraphrased responses flagged as FP
        check_format: bool = True,
        check_ambiguity: bool = True,
    ):
        self.intent_threshold = intent_threshold
        self.check_format = check_format
        self.check_ambiguity = check_ambiguity

    def _detect_expected_format(self, message: str) -> Optional[str]:
        format_hints = {
            "json": [r'\bjson\b', r'\{.*\}', r'format.*json', r'return.*json'],
            "list": [r'\blist\b', r'enumerate', r'bullet.*point', r'\d+\.\s'],
            "code": [r'```', r'\bcode\b', r'implement', r'function.*def', r'class\s+\w+'],
            "markdown": [r'#\s+', r'\*\*.*\*\*', r'##\s+'],
            "csv": [r'\bcsv\b', r'comma.*separated', r',.*,.*,'],
        }
        
        message_lower = message.lower()
        for fmt, patterns in format_hints.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return fmt
        return None

    def _check_format_compliance(
        self,
        expected_format: Optional[str],
        response: str,
    ) -> tuple[bool, str]:
        if not expected_format:
            return True, "No specific format expected"
        
        if expected_format == "json":
            try:
                json.loads(response)
                return True, "Valid JSON"
            except json.JSONDecodeError:
                json_match = re.search(r'\{[^{}]*\}|\[[^\[\]]*\]', response)
                if json_match:
                    try:
                        json.loads(json_match.group())
                        return True, "JSON found in response"
                    except (json.JSONDecodeError, ValueError):
                        pass
                return False, "Expected JSON but response is not valid JSON"
        
        if expected_format == "list":
            list_patterns = [r'^\s*[-•*]\s+', r'^\s*\d+[.)]\s+']
            for pattern in list_patterns:
                if re.search(pattern, response, re.MULTILINE):
                    return True, "List format detected"
            return False, "Expected list format but none detected"
        
        if expected_format == "code":
            if '```' in response or re.search(r'\bdef\s+\w+|class\s+\w+|function\s+\w+', response):
                return True, "Code format detected"
            return False, "Expected code but none detected"
        
        return True, f"Format check passed for {expected_format}"

    def _detect_ambiguous_language(self, message: str) -> list[str]:
        ambiguous_patterns = [
            (r'\b(it|this|that|these|those)\b(?!\s+is|\s+are|\s+was)', "ambiguous pronoun"),
            (r'\bsome\s+\w+', "vague quantifier"),
            (r'\bmaybe|perhaps|possibly|probably\b', "uncertain language"),
            (r'\betc\.?|and\s+so\s+on|and\s+more\b', "incomplete enumeration"),
            (r'\bsoon|later|eventually\b', "vague timeline"),
            (r'\b(good|bad|nice|fine|okay)\b', "subjective descriptor"),
        ]
        
        issues = []
        for pattern, issue_type in ambiguous_patterns:
            if re.search(pattern, message.lower()):
                issues.append(issue_type)
        
        return issues

    def _compute_intent_alignment(
        self,
        request: str,
        response: str,
        action_taken: Optional[str] = None,
    ) -> float:
        request_words = set(request.lower().split())
        response_words = set(response.lower().split())
        
        action_verbs = {
            "create", "update", "delete", "get", "fetch", "send", "process",
            "analyze", "generate", "search", "find", "calculate", "compare",
            "summarize", "extract", "transform", "validate", "verify",
            "confirm", "acknowledge", "respond", "reply", "escalate",
            "delegate", "forward", "submit", "report", "transfer",
            "approve", "reject", "notify", "announce", "broadcast",
            "check", "monitor", "review", "implement", "deploy",
            "configure", "install", "migrate", "test", "debug",
            "fix", "resolve", "handle", "execute", "run",
        }
        
        request_actions = request_words & action_verbs
        response_actions = response_words & action_verbs
        
        if not request_actions:
            keyword_overlap = len(request_words & response_words) / max(len(request_words), 1)
            return min(keyword_overlap * 2, 1.0)
        
        action_match = len(request_actions & response_actions) / len(request_actions)
        
        negative_indicators = {"error", "failed", "cannot", "unable", "refused", "sorry"}
        if response_words & negative_indicators:
            action_match *= 0.5
        
        return action_match

    def detect(
        self,
        sender_message: str,
        receiver_response: str,
        receiver_action: Optional[str] = None,
        sender_name: Optional[str] = None,
        receiver_name: Optional[str] = None,
    ) -> CommunicationBreakdownResult:
        if self.check_format:
            expected_format = self._detect_expected_format(sender_message)
            format_ok, format_msg = self._check_format_compliance(expected_format, receiver_response)
        else:
            expected_format = None
            format_ok, format_msg = True, "Format check disabled"
        
        intent_alignment = self._compute_intent_alignment(
            sender_message, receiver_response, receiver_action
        )
        
        ambiguities = self._detect_ambiguous_language(sender_message)
        
        breakdown_type = None
        detected = False
        
        if not format_ok:
            detected = True
            breakdown_type = BreakdownType.FORMAT_MISMATCH
        elif intent_alignment < self.intent_threshold:
            detected = True
            breakdown_type = BreakdownType.INTENT_MISMATCH
        elif len(ambiguities) >= 4:
            detected = True
            breakdown_type = BreakdownType.SEMANTIC_AMBIGUITY

        if not detected:
            return CommunicationBreakdownResult(
                detected=False,
                breakdown_type=None,
                severity=BreakdownSeverity.NONE,
                confidence=intent_alignment,
                intent_alignment=intent_alignment,
                format_match=format_ok,
                explanation="Communication appears clear",
            )

        if breakdown_type == BreakdownType.FORMAT_MISMATCH:
            severity = BreakdownSeverity.MODERATE
            confidence = 0.9
            explanation = format_msg
            fix = f"Ensure response follows {expected_format} format. Add explicit format instructions."
        elif breakdown_type == BreakdownType.INTENT_MISMATCH:
            if intent_alignment < 0.2:
                severity = BreakdownSeverity.SEVERE
            else:
                severity = BreakdownSeverity.MODERATE
            confidence = 1 - intent_alignment
            # Moderate confidence when keywords overlap despite verb mismatch.
            # High keyword overlap means topics match — likely NOT a real breakdown.
            request_words = set(sender_message.lower().split())
            response_words = set(receiver_response.lower().split())
            # Filter stop words for more meaningful overlap
            _stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "to", "of", "in", "for", "on", "with", "at", "by", "from",
                      "and", "or", "but", "not", "no", "if", "it", "i", "you",
                      "we", "they", "he", "she", "this", "that", "will", "can",
                      "do", "does", "did", "has", "have", "had", "would", "could",
                      "should", "may", "might", "shall", "must", "need"}
            req_content = request_words - _stop
            resp_content = response_words - _stop
            if req_content:
                content_overlap = len(req_content & resp_content) / len(req_content)
                if content_overlap > 0.3:
                    # Topics overlap despite verb mismatch → reduce confidence
                    confidence *= max(0.4, 1.0 - content_overlap)
            explanation = (
                f"Response does not align with request intent. "
                f"Alignment score: {intent_alignment:.1%}"
            )
            fix = "Clarify request with specific action verbs and expected outcomes."
        else:
            severity = BreakdownSeverity.MINOR
            confidence = 0.6
            explanation = f"Ambiguous language detected: {', '.join(ambiguities)}"
            fix = "Replace ambiguous language with specific references."

        sender_label = f"'{sender_name}'" if sender_name else "sender"
        receiver_label = f"'{receiver_name}'" if receiver_name else "receiver"
        explanation = f"Communication from {sender_label} to {receiver_label}: {explanation}"

        return CommunicationBreakdownResult(
            detected=True,
            breakdown_type=breakdown_type,
            severity=severity,
            confidence=confidence,
            intent_alignment=intent_alignment,
            format_match=format_ok,
            explanation=explanation,
            suggested_fix=fix,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> list[CommunicationBreakdownResult]:
        results = []
        
        spans = trace.get("spans", [])
        for i in range(len(spans) - 1):
            sender = spans[i]
            receiver = spans[i + 1]
            
            sender_output = sender.get("output", {}).get("content", "")
            receiver_input = receiver.get("input", {}).get("message", "")
            receiver_output = receiver.get("output", {}).get("content", "")
            
            if sender_output and receiver_output:
                result = self.detect(
                    sender_message=sender_output,
                    receiver_response=receiver_output,
                    sender_name=sender.get("name"),
                    receiver_name=receiver.get("name"),
                )
                if result.detected:
                    results.append(result)
        
        return results
