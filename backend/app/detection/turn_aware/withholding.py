"""
F8: Information Withholding Detector
====================================

Analyzes whether agents properly share information:
1. Unanswered questions - agent asks but gets no answer
2. Missing context - agent responds without using provided info
3. Incomplete sharing - partial information provided
4. Ignored requests - explicit requests for info not addressed

Based on MAST research (NeurIPS 2025): FM-2.4 Information Withholding (12%)
"""

import logging
from typing import List, Optional, Dict, Any

from ._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)
from ._embedding_mixin import EmbeddingMixin

logger = logging.getLogger(__name__)


class TurnAwareInformationWithholdingDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F8: Information Withholding in conversations.

    Analyzes whether agents properly share information:
    1. Unanswered questions - agent asks but gets no answer
    2. Missing context - agent responds without using provided info
    3. Incomplete sharing - partial information provided
    4. Ignored requests - explicit requests for info not addressed

    Enhanced with semantic analysis (v2.0):
    - Information density scoring for response completeness
    - Semantic similarity for question-answer relevance
    - Entity tracking across turns

    Based on MAST research (NeurIPS 2025): FM-2.4 Information Withholding (12%)
    """

    name = "TurnAwareInformationWithholdingDetector"
    version = "2.0"  # Semantic enhancement
    supported_failure_modes = ["F8"]

    # Question indicators
    QUESTION_PATTERNS = [
        "?", "what is", "how do", "can you", "could you",
        "please provide", "please share", "need to know",
        "tell me", "explain", "clarify", "which",
    ]

    # Withholding indicators in responses - enhanced for MAST
    WITHHOLDING_INDICATORS = [
        "can't share", "cannot disclose", "not allowed to",
        "confidential", "private", "restricted",
        "don't have that", "no information", "unknown",
        "not sure", "i don't know", "unclear",
        # Added for better MAST recall
        "didn't provide", "didn't include", "didn't mention",
        "missing", "not provided", "incomplete",
        "omitted", "left out", "didn't answer",
        "you didn't", "wasn't included", "should have",
    ]

    # Missing context indicators
    MISSING_CONTEXT = [
        "what do you mean", "more context", "be more specific",
        "unclear what", "don't understand", "confused about",
        "missing information", "need more details", "incomplete",
    ]

    def __init__(
        self,
        min_turns: int = 2,  # Lowered from 3 for better MAST recall
        min_issues_to_flag: int = 2,  # Added to reduce FPs (18.2% FPR)
    ):
        self.min_turns = min_turns
        self.min_issues_to_flag = min_issues_to_flag

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect information withholding issues."""
        if len(turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for unanswered questions
        unanswered = self._detect_unanswered_questions(turns)
        issues.extend(unanswered)
        for issue in unanswered:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for withholding indicators
        withholding = self._detect_withholding(turns)
        issues.extend(withholding)
        for issue in withholding:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for missing context complaints
        missing = self._detect_missing_context(turns)
        issues.extend(missing)
        for issue in missing:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for ignored information requests
        ignored = self._detect_ignored_requests(turns)
        issues.extend(ignored)
        for issue in ignored:
            affected_turns.extend(issue.get("turns", []))

        if len(issues) < self.min_issues_to_flag:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issues < {self.min_issues_to_flag} required)",
                detector_name=self.name,
            )

        if len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F8",
            explanation=f"Information withholding: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Improve information sharing: 1) Ensure all questions are addressed, "
                "2) Share full context when responding, 3) Proactively share relevant info, "
                "4) Ask clarifying questions when info is incomplete."
            ),
            detector_name=self.name,
        )

    def _detect_unanswered_questions(self, turns: List[TurnSnapshot]) -> list:
        """Detect questions that weren't answered.

        Enhanced with semantic similarity (v2.0):
        - Uses embedding similarity to check if response addresses question
        - Also checks information density of response
        """
        issues = []
        for i, turn in enumerate(turns[:-1]):
            content = turn.content
            # Check if this turn contains a question
            if "?" in content:
                # Look at next 2 turns for an answer
                answered = False
                answer_quality = "none"

                for j in range(i + 1, min(i + 3, len(turns))):
                    next_turn = turns[j]
                    # Different participant responding
                    if next_turn.participant_id != turn.participant_id:
                        # Check semantic relevance of response to question
                        similarity = self.semantic_similarity(content, next_turn.content)

                        if similarity >= 0:  # Embeddings available
                            if similarity >= 0.5:  # Raised from 0.4 to reduce FPs
                                response_density = self.compute_information_density(next_turn.content)
                                if response_density >= 0.3:  # Substantive response
                                    answered = True
                                    answer_quality = "good"
                                else:
                                    answer_quality = "low_density"
                                break
                        else:
                            # Fallback: length-based check
                            if len(next_turn.content) > 50:
                                answered = True
                                answer_quality = "length_only"
                                break

                if not answered:
                    issues.append({
                        "type": "unanswered_question",
                        "turns": [turn.turn_number],
                        "description": "Question appears unanswered",
                        "answer_quality": answer_quality,
                    })
        return issues[:3]

    def _detect_withholding(self, turns: List[TurnSnapshot]) -> list:
        """Detect explicit withholding of information."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.WITHHOLDING_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "explicit_withholding",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Info withheld: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_missing_context(self, turns: List[TurnSnapshot]) -> list:
        """Detect complaints about missing context."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.MISSING_CONTEXT:
                if indicator in content_lower:
                    issues.append({
                        "type": "missing_context",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Missing context: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_ignored_requests(self, turns: List[TurnSnapshot]) -> list:
        """Detect explicit info requests that were ignored."""
        issues = []
        request_phrases = [
            "please provide", "please share", "send me",
            "give me", "need the", "what about",
        ]

        for i, turn in enumerate(turns[:-1]):
            content_lower = turn.content.lower()
            for phrase in request_phrases:
                if phrase in content_lower:
                    # Check if next response addresses it
                    addressed = False
                    for j in range(i + 1, min(i + 3, len(turns))):
                        next_turn = turns[j]
                        if next_turn.participant_id != turn.participant_id:
                            # Check for substantive response
                            if len(next_turn.content) > 100:
                                addressed = True
                                break
                    if not addressed:
                        issues.append({
                            "type": "ignored_request",
                            "turns": [turn.turn_number],
                            "phrase": phrase,
                            "description": f"Request ignored: '{phrase}'",
                        })
                    break
        return issues[:2]
