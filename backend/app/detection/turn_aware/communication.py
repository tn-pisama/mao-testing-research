"""
F10: Communication Breakdown Detector
======================================

Detects F10: Communication Breakdown between agents.

Analyzes inter-agent communication for:
1. Intent misalignment - sender meant X, receiver understood Y
2. Format mismatches - expected JSON, got prose
3. Semantic ambiguity - unclear or ambiguous language
4. Information loss - key details dropped between agents
5. Conflicting instructions - contradictory directives

Particularly important for multi-agent orchestration systems.
"""

import json as json_lib
import logging
import re
from typing import List, Optional, Dict, Any

from ._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)

logger = logging.getLogger(__name__)


class TurnAwareCommunicationBreakdownDetector(TurnAwareDetector):
    """Detects F10: Communication Breakdown between agents.

    Analyzes inter-agent communication for:
    1. Intent misalignment - sender meant X, receiver understood Y
    2. Format mismatches - expected JSON, got prose
    3. Semantic ambiguity - unclear or ambiguous language
    4. Information loss - key details dropped between agents
    5. Conflicting instructions - contradictory directives

    Particularly important for multi-agent orchestration systems.
    """

    name = "TurnAwareCommunicationBreakdownDetector"
    version = "1.0"
    supported_failure_modes = ["F10"]

    # Intent action verbs for alignment checking
    ACTION_VERBS = [
        "create", "update", "delete", "get", "fetch", "send", "process",
        "analyze", "generate", "search", "find", "calculate", "compare",
        "summarize", "extract", "transform", "validate", "verify",
        "implement", "build", "deploy", "test", "review",
    ]

    # Ambiguous language patterns
    AMBIGUOUS_PATTERNS = [
        (r'\b(it|this|that|these|those)\b(?!\s+(?:is|are|was|were|has|have))', "ambiguous_pronoun"),
        (r'\bsome\s+\w+', "vague_quantifier"),
        (r'\bmaybe|perhaps|possibly|probably\b', "uncertain_language"),
        (r'\betc\.?|and\s+so\s+on|and\s+more\b', "incomplete_enumeration"),
        (r'\bsoon|later|eventually\b', "vague_timeline"),
    ]

    # Misunderstanding indicators (reduced to strong signals only)
    # Removed benign clarification phrases like "actually", "to clarify", "let me clarify"
    MISUNDERSTANDING_INDICATORS = [
        "not sure what you", "misunderstood", "didn't understand",
        "that's not what i", "you got it wrong",
        "communication breakdown", "miscommunication",
    ]

    # Format expectation keywords
    FORMAT_KEYWORDS = {
        "json": ["json", "object", "dictionary", "{}"],
        "list": ["list", "array", "items", "enumerate"],
        "code": ["code", "implement", "function", "class"],
        "markdown": ["markdown", "formatted", "headers"],
    }

    def __init__(
        self,
        intent_threshold: float = 0.60,  # Raised from 0.35 to reduce FPR
        max_ambiguity_issues: int = 5,   # Raised from 3 to reduce FPR
    ):
        self.intent_threshold = intent_threshold
        self.max_ambiguity_issues = max_ambiguity_issues

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect communication breakdowns in multi-turn conversation."""
        if len(turns) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 2 turns for communication analysis",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # Analyze consecutive turn pairs
        for i in range(len(turns) - 1):
            sender = turns[i]
            receiver = turns[i + 1]

            # Skip if same participant (monologue)
            if sender.participant_id == receiver.participant_id:
                continue

            # Check for misunderstanding indicators
            misunderstanding = self._check_misunderstanding(sender, receiver)
            if misunderstanding:
                issues.append(misunderstanding)
                affected_turns.extend([sender.turn_number, receiver.turn_number])

            # Check intent alignment
            intent_issue = self._check_intent_alignment(sender, receiver)
            if intent_issue:
                issues.append(intent_issue)
                affected_turns.extend([sender.turn_number, receiver.turn_number])

            # Check for format mismatches
            format_issue = self._check_format_compliance(sender, receiver)
            if format_issue:
                issues.append(format_issue)
                affected_turns.extend([sender.turn_number, receiver.turn_number])

        # Check for overall ambiguity in agent messages
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        for turn in agent_turns:
            ambiguity_issues = self._check_ambiguity(turn)
            if len(ambiguity_issues) >= self.max_ambiguity_issues:
                issues.append({
                    "type": "semantic_ambiguity",
                    "turn": turn.turn_number,
                    "issues": ambiguity_issues,
                    "description": f"Turn {turn.turn_number} has {len(ambiguity_issues)} ambiguous language patterns",
                })
                affected_turns.append(turn.turn_number)

        # Require 2+ issues to flag (a single ambiguity isn't a breakdown)
        has_strong_signal = any(
            i["type"] in ("intent_mismatch", "explicit_misunderstanding") for i in issues
        )
        if not issues or (len(issues) < 2 and not has_strong_signal):
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="Communication appears clear between participants",
                detector_name=self.name,
            )

        # Determine severity
        if any(i["type"] == "intent_mismatch" for i in issues) and len(issues) >= 2:
            severity = TurnAwareSeverity.SEVERE
        elif any(i["type"] == "explicit_misunderstanding" for i in issues):
            severity = TurnAwareSeverity.MODERATE
        elif len(issues) >= 4:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F10",
            explanation=f"Communication breakdown: {len(issues)} issues detected",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "turn_pairs_analyzed": len(turns) - 1,
            },
            suggested_fix=(
                "Improve communication clarity: 1) Use explicit references instead of pronouns, "
                "2) Specify expected formats clearly, 3) Confirm understanding before proceeding."
            ),
            detector_name=self.name,
        )

    def _check_misunderstanding(
        self,
        sender: TurnSnapshot,
        receiver: TurnSnapshot,
    ) -> Optional[dict]:
        """Check for explicit misunderstanding indicators."""
        receiver_lower = receiver.content.lower()

        for indicator in self.MISUNDERSTANDING_INDICATORS:
            if indicator in receiver_lower:
                return {
                    "type": "explicit_misunderstanding",
                    "indicator": indicator,
                    "sender_turn": sender.turn_number,
                    "receiver_turn": receiver.turn_number,
                    "description": f"Explicit misunderstanding detected: '{indicator}'",
                }
        return None

    def _check_intent_alignment(
        self,
        sender: TurnSnapshot,
        receiver: TurnSnapshot,
    ) -> Optional[dict]:
        """Check if receiver's response aligns with sender's intent.

        Note: Action verb matching is unreliable without semantic similarity.
        Only flag when there is zero overlap AND the sender had 2+ clear actions,
        combined with the receiver addressing a completely different topic.
        """
        sender_words = set(sender.content.lower().split())
        receiver_words = set(receiver.content.lower().split())

        # Extract actions from both
        sender_actions = sender_words & set(self.ACTION_VERBS)
        receiver_actions = receiver_words & set(self.ACTION_VERBS)

        if len(sender_actions) < 2:
            # Need 2+ clear actions to make a reliable judgment
            return None

        # Check if receiver addressed the requested actions
        action_match = len(sender_actions & receiver_actions) / len(sender_actions)

        # Check for negative indicators (errors, refusals)
        negative_indicators = {"error", "failed", "cannot", "unable", "refused", "sorry", "can't"}
        has_negative = bool(receiver_words & negative_indicators)

        # Only flag on zero overlap (complete mismatch) with no negatives
        if action_match == 0.0 and not has_negative:
            # Additional check: ensure receiver talks about something completely different
            # by checking noun/keyword overlap is also very low
            sender_nouns = {w for w in sender_words if len(w) > 4}
            receiver_nouns = {w for w in receiver_words if len(w) > 4}
            noun_overlap = len(sender_nouns & receiver_nouns) / max(len(sender_nouns), 1)
            if noun_overlap < 0.1:
                return {
                    "type": "intent_mismatch",
                    "sender_turn": sender.turn_number,
                    "receiver_turn": receiver.turn_number,
                    "alignment_score": action_match,
                    "requested_actions": list(sender_actions),
                    "addressed_actions": list(receiver_actions),
                    "description": f"Response doesn't address requested actions ({action_match:.0%} alignment)",
                }
        return None

    def _check_format_compliance(
        self,
        sender: TurnSnapshot,
        receiver: TurnSnapshot,
    ) -> Optional[dict]:
        """Check if receiver followed expected format.

        Only flags when sender explicitly requests a format (e.g., "return JSON",
        "give me a list", "provide code"). Casual mentions don't count.
        """
        sender_lower = sender.content.lower()
        expected_format = None

        # Only detect explicit format requests (not casual mentions)
        explicit_format_patterns = {
            "json": ["return json", "provide json", "output json", "respond with json", "give me json", "in json format"],
            "code": ["write code", "provide code", "give me code", "show me the code"],
        }

        for fmt, patterns in explicit_format_patterns.items():
            if any(p in sender_lower for p in patterns):
                expected_format = fmt
                break

        if not expected_format:
            return None

        # Check if receiver complied
        receiver_content = receiver.content

        if expected_format == "json":
            try:
                json_lib.loads(receiver_content)
                return None  # Valid JSON
            except:
                # Check for embedded JSON
                if re.search(r'\{[^{}]+\}', receiver_content):
                    return None  # Has JSON-like content
                return {
                    "type": "format_mismatch",
                    "expected": "json",
                    "sender_turn": sender.turn_number,
                    "receiver_turn": receiver.turn_number,
                    "description": "Expected JSON format but received prose",
                }

        elif expected_format == "code":
            if "```" in receiver_content or "def " in receiver_content or "class " in receiver_content:
                return None  # Has code
            return {
                "type": "format_mismatch",
                "expected": "code",
                "sender_turn": sender.turn_number,
                "receiver_turn": receiver.turn_number,
                "description": "Expected code format but received prose",
            }

        return None

    def _check_ambiguity(self, turn: TurnSnapshot) -> List[str]:
        """Check for ambiguous language in a turn."""
        issues = []

        for pattern, issue_type in self.AMBIGUOUS_PATTERNS:
            if re.search(pattern, turn.content, re.IGNORECASE):
                issues.append(issue_type)

        return issues
