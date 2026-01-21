"""
Hybrid Detection Module
========================

Contains LLM-based and hybrid detectors for semantic failure detection:

F6 (Task Derailment):
1. LLMDerailmentDetector - Pure LLM-based F6 detection using Claude
2. HybridDerailmentDetector - Pattern-first, LLM-escalation approach

F9 (Role Usurpation):
3. LLMRoleUsurpationDetector - Pure LLM-based F9 detection
4. HybridRoleUsurpationDetector - Pattern-first, LLM-escalation approach

5. analyze_conversation_turns - Convenience function to run all detectors

The hybrid approach achieves ~80% cost savings vs LLM-only while maintaining accuracy.
"""

import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from ._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    MODULE_VERSION,
    MAX_TURNS_BEFORE_SUMMARIZATION,
    MAX_TOKENS_BEFORE_SUMMARIZATION,
)

if TYPE_CHECKING:
    from ..task_extractors import ConversationTurn

logger = logging.getLogger(__name__)


class LLMDerailmentDetector:
    """
    LLM-based F6 (Task Derailment) detector using Claude Opus 4.5.

    Unlike the pattern-based TurnAwareDerailmentDetector which uses keyword drift,
    this detector uses semantic understanding to detect when agents diverge from
    the original task. Required for MAST benchmark where agents stay on-topic
    but derail semantically.

    Usage:
        detector = LLMDerailmentDetector()
        result = detector.detect(snapshots, metadata)
    """

    name = "LLMDerailmentDetector"
    version = "1.0"
    supported_failure_modes = ["F6"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        confidence_threshold: float = 0.6,
    ):
        self.api_key = api_key
        self.confidence_threshold = confidence_threshold
        self._judge = None

    @property
    def judge(self):
        """Lazy-load the LLM judge."""
        if self._judge is None:
            from ..llm_judge import MASTLLMJudge
            self._judge = MASTLLMJudge(api_key=self.api_key)
        return self._judge

    def _convert_to_conversation_turns(
        self,
        snapshots: List[TurnSnapshot],
    ) -> List["ConversationTurn"]:
        """Convert TurnSnapshots to ConversationTurns for task extraction."""
        from ..task_extractors import ConversationTurn

        turns = []
        for snapshot in snapshots:
            turns.append(ConversationTurn(
                role=snapshot.participant_type,
                content=snapshot.content,
                participant_id=snapshot.participant_id,
                metadata=snapshot.turn_metadata or {},
            ))
        return turns

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """
        Detect F6 (Task Derailment) using LLM verification.

        Args:
            turns: List of turn snapshots
            conversation_metadata: Optional metadata about the conversation

        Returns:
            TurnAwareDetectionResult with LLM-based detection
        """
        if len(turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for LLM derailment analysis",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        metadata = conversation_metadata or {}

        # Convert to ConversationTurns and extract task
        conv_turns = self._convert_to_conversation_turns(turns)

        try:
            from ..task_extractors import extract_task
            extraction = extract_task(conv_turns, metadata)
        except Exception as e:
            logger.warning(f"Task extraction failed: {e}")
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation=f"Task extraction failed: {e}",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        if not extraction.task:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No task found in conversation",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Enhance agent output summary if it's too sparse
        # MAST trajectories often have sparse parsed content but rich raw data
        agent_summary = extraction.agent_output_summary
        if len(agent_summary) < 200:
            # Build summary from actual turn content
            agent_content = []
            for t in turns:
                if t.participant_type == "agent" and len(t.content) > 30:
                    # Skip metadata-only content
                    if not t.content.startswith("[") or len(t.content) > 100:
                        agent_content.append(t.content[:300])
            if agent_content:
                agent_summary = "\n---\n".join(agent_content[:5])

        # Call LLM judge
        try:
            from ..llm_judge import MASTFailureMode

            result = self.judge.evaluate(
                failure_mode=MASTFailureMode.F6,
                task=extraction.task[:2000],  # Truncate for token limits
                trace_summary=agent_summary[:2000],  # Use enhanced summary
                key_events=extraction.key_events,
            )
        except Exception as e:
            logger.error(f"LLM judge call failed: {e}")
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation=f"LLM verification failed: {e}",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Convert LLM verdict to detection result
        detected = result.verdict == "YES" and result.confidence >= self.confidence_threshold

        if detected:
            if result.confidence >= 0.85:
                severity = TurnAwareSeverity.SEVERE
            elif result.confidence >= 0.7:
                severity = TurnAwareSeverity.MODERATE
            else:
                severity = TurnAwareSeverity.MINOR
        else:
            severity = TurnAwareSeverity.NONE

        return TurnAwareDetectionResult(
            detected=detected,
            severity=severity,
            confidence=result.confidence,
            failure_mode="F6" if detected else None,
            explanation=result.reasoning if result.reasoning else (
                "LLM detected task derailment" if detected else "LLM found no task derailment"
            ),
            evidence={
                "llm_verdict": result.verdict,
                "llm_confidence": result.confidence,
                "llm_reasoning": result.reasoning,
                "task_extracted": extraction.task[:500],
                "framework_detected": extraction.framework,
                "model_used": result.model_used,
                "tokens_used": result.tokens_used,
                "cost_usd": result.cost_usd,
            },
            suggested_fix=(
                "Review agent focus and add task reminders. Consider: "
                "'Stay focused on: [ORIGINAL_TASK]. Do not address unrelated topics.'"
            ),
            detector_name=self.name,
            detector_version=MODULE_VERSION,
        )


class HybridDerailmentDetector:
    """
    Hybrid F6 (Task Derailment) detector: pattern-first, LLM-escalation.

    Cost optimization strategy:
    1. Run fast pattern detector first (free, <50ms)
    2. If pattern confidence >= 0.7, use pattern result (clear detection or clear negative)
    3. If pattern confidence < 0.7 (ambiguous), escalate to LLM (~$0.03/trace)

    This achieves ~80% cost savings vs LLM-only while maintaining accuracy.

    Usage:
        detector = HybridDerailmentDetector()
        result = detector.detect(snapshots, metadata)
    """

    name = "HybridDerailmentDetector"
    version = "1.0"
    supported_failure_modes = ["F6"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        escalation_threshold: float = 0.7,  # Below this confidence, escalate to LLM
        confidence_threshold: float = 0.6,  # Min confidence for LLM to detect
    ):
        self.api_key = api_key
        self.escalation_threshold = escalation_threshold
        self.confidence_threshold = confidence_threshold
        self._pattern_detector = None
        self._llm_detector = None

    @property
    def pattern_detector(self):
        """Lazy-load pattern detector."""
        if self._pattern_detector is None:
            from .derailment import TurnAwareDerailmentDetector
            self._pattern_detector = TurnAwareDerailmentDetector(
                drift_threshold=0.5,  # Sensitive for initial detection
                require_strong_evidence=False,
            )
        return self._pattern_detector

    @property
    def llm_detector(self):
        """Lazy-load LLM detector."""
        if self._llm_detector is None:
            self._llm_detector = LLMDerailmentDetector(
                api_key=self.api_key,
                confidence_threshold=self.confidence_threshold,
            )
        return self._llm_detector

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """
        Detect F6 (Task Derailment) using hybrid approach.

        Strategy:
        - Pattern detector first (fast, free)
        - Escalate to LLM only on ambiguous cases

        Args:
            turns: List of turn snapshots
            conversation_metadata: Optional metadata about the conversation

        Returns:
            TurnAwareDetectionResult with detection decision
        """
        if len(turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for derailment analysis",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Step 1: Run pattern detector
        pattern_result = self.pattern_detector.detect(turns, conversation_metadata)

        # Step 2: Decide if we need LLM escalation
        should_escalate = (
            pattern_result.confidence < self.escalation_threshold
            or (pattern_result.detected and pattern_result.confidence < 0.8)
        )

        if not should_escalate:
            # High confidence from pattern detector - use its result
            return TurnAwareDetectionResult(
                detected=pattern_result.detected,
                severity=pattern_result.severity,
                confidence=pattern_result.confidence,
                failure_mode=pattern_result.failure_mode,
                explanation=f"[Pattern] {pattern_result.explanation}",
                affected_turns=pattern_result.affected_turns,
                evidence={
                    **(pattern_result.evidence or {}),
                    "detection_method": "pattern",
                    "llm_escalated": False,
                },
                suggested_fix=pattern_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Step 3: Escalate to LLM for borderline cases
        try:
            llm_result = self.llm_detector.detect(turns, conversation_metadata)

            # Combine evidence from both detectors
            combined_evidence = {
                **(pattern_result.evidence or {}),
                **(llm_result.evidence or {}),
                "detection_method": "hybrid",
                "llm_escalated": True,
                "pattern_confidence": pattern_result.confidence,
                "pattern_detected": pattern_result.detected,
            }

            return TurnAwareDetectionResult(
                detected=llm_result.detected,
                severity=llm_result.severity,
                confidence=llm_result.confidence,
                failure_mode=llm_result.failure_mode,
                explanation=f"[LLM-verified] {llm_result.explanation}",
                affected_turns=llm_result.affected_turns or pattern_result.affected_turns,
                evidence=combined_evidence,
                suggested_fix=llm_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        except Exception as e:
            # LLM failed - fall back to pattern result
            logger.warning(f"LLM escalation failed, using pattern result: {e}")
            return TurnAwareDetectionResult(
                detected=pattern_result.detected,
                severity=pattern_result.severity,
                confidence=pattern_result.confidence,
                failure_mode=pattern_result.failure_mode,
                explanation=f"[Pattern-fallback] {pattern_result.explanation}",
                affected_turns=pattern_result.affected_turns,
                evidence={
                    **(pattern_result.evidence or {}),
                    "detection_method": "pattern_fallback",
                    "llm_escalated": True,
                    "llm_error": str(e),
                },
                suggested_fix=pattern_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )


# ==============================================================================
# F9 (Role Usurpation) Hybrid Detection
# ==============================================================================


class LLMRoleUsurpationDetector:
    """
    LLM-based F9 (Role Usurpation) detector using Claude.

    Detects when agents act outside their designated roles, exceed boundaries,
    or take over responsibilities assigned to other agents. Required for MAST
    benchmark where role usurpation is subtle and context-dependent.

    Key insight: F9 in MAST always co-occurs with other failures (F1, F3, F5,
    F7, F8, F11, F12, F14). Rule-based detection achieves only 2.5% recall.

    Usage:
        detector = LLMRoleUsurpationDetector()
        result = detector.detect(snapshots, metadata)
    """

    name = "LLMRoleUsurpationDetector"
    version = "1.0"
    supported_failure_modes = ["F9"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        confidence_threshold: float = 0.6,
    ):
        self.api_key = api_key
        self.confidence_threshold = confidence_threshold
        self._judge = None

    @property
    def judge(self):
        """Lazy-load the LLM judge."""
        if self._judge is None:
            from ..llm_judge import MASTLLMJudge
            self._judge = MASTLLMJudge(api_key=self.api_key)
        return self._judge

    def _convert_to_conversation_turns(
        self,
        snapshots: List[TurnSnapshot],
    ) -> List["ConversationTurn"]:
        """Convert TurnSnapshots to ConversationTurns for task extraction."""
        from ..task_extractors import ConversationTurn

        turns = []
        for snapshot in snapshots:
            turns.append(ConversationTurn(
                role=snapshot.participant_type,
                content=snapshot.content,
                participant_id=snapshot.participant_id,
                metadata=snapshot.turn_metadata or {},
            ))
        return turns

    def _extract_role_context(self, turns: List[TurnSnapshot]) -> str:
        """Extract role assignments and agent actions for F9 analysis."""
        role_info = []

        # Identify unique agents and their apparent roles
        agents = {}
        for turn in turns:
            pid = turn.participant_id or "unknown"
            if pid not in agents:
                agents[pid] = {
                    "first_action": turn.content[:200],
                    "turn_count": 0,
                }
            agents[pid]["turn_count"] += 1

        role_info.append("## Agent Roles Observed:")
        for agent_id, info in agents.items():
            role_info.append(f"- {agent_id}: {info['turn_count']} turns")

        # Extract key agent actions
        role_info.append("\n## Key Agent Actions:")
        for i, turn in enumerate(turns[:10]):  # First 10 turns for context
            if turn.participant_type == "agent":
                pid = turn.participant_id or "Agent"
                action_preview = turn.content[:150].replace("\n", " ")
                role_info.append(f"Turn {i}: [{pid}] {action_preview}...")

        return "\n".join(role_info)

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """
        Detect F9 (Role Usurpation) using LLM verification.

        Args:
            turns: List of turn snapshots
            conversation_metadata: Optional metadata about the conversation

        Returns:
            TurnAwareDetectionResult with LLM-based detection
        """
        if len(turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for LLM role usurpation analysis",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        metadata = conversation_metadata or {}

        # Convert to ConversationTurns and extract task
        conv_turns = self._convert_to_conversation_turns(turns)

        try:
            from ..task_extractors import extract_task
            extraction = extract_task(conv_turns, metadata)
        except Exception as e:
            logger.warning(f"Task extraction failed: {e}")
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation=f"Task extraction failed: {e}",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Build role context for LLM analysis
        role_context = self._extract_role_context(turns)

        # Build trace summary focusing on role-related actions
        agent_actions = []
        for t in turns:
            if t.participant_type == "agent" and len(t.content) > 30:
                pid = t.participant_id or "Agent"
                # Include participant ID in summary for role tracking
                agent_actions.append(f"[{pid}]: {t.content[:250]}")

        trace_summary = f"{role_context}\n\n## Agent Trace:\n" + "\n---\n".join(agent_actions[:8])

        # Call LLM judge for F9
        try:
            from ..llm_judge import MASTFailureMode

            result = self.judge.evaluate(
                failure_mode=MASTFailureMode.F9,
                task=extraction.task[:1500] if extraction.task else "Unknown task",
                trace_summary=trace_summary[:3000],
                key_events=extraction.key_events,
            )
        except Exception as e:
            logger.error(f"LLM judge call failed: {e}")
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation=f"LLM verification failed: {e}",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Convert LLM verdict to detection result
        detected = result.verdict == "YES" and result.confidence >= self.confidence_threshold

        if detected:
            if result.confidence >= 0.85:
                severity = TurnAwareSeverity.SEVERE
            elif result.confidence >= 0.7:
                severity = TurnAwareSeverity.MODERATE
            else:
                severity = TurnAwareSeverity.MINOR
        else:
            severity = TurnAwareSeverity.NONE

        return TurnAwareDetectionResult(
            detected=detected,
            severity=severity,
            confidence=result.confidence,
            failure_mode="F9" if detected else None,
            explanation=result.reasoning if result.reasoning else (
                "LLM detected role usurpation" if detected else "LLM found no role usurpation"
            ),
            evidence={
                "llm_verdict": result.verdict,
                "llm_confidence": result.confidence,
                "llm_reasoning": result.reasoning,
                "task_extracted": extraction.task[:500] if extraction.task else None,
                "framework_detected": extraction.framework,
                "model_used": result.model_used,
                "tokens_used": result.tokens_used,
                "cost_usd": result.cost_usd,
            },
            suggested_fix=(
                "Enforce role boundaries: 1) Define clear role responsibilities upfront, "
                "2) Add permission checks before cross-role actions, 3) Require explicit "
                "delegation for role handoffs, 4) Monitor for unauthorized decision-making."
            ),
            detector_name=self.name,
            detector_version=MODULE_VERSION,
        )


class HybridRoleUsurpationDetector:
    """
    Hybrid F9 (Role Usurpation) detector: pattern-first, LLM-escalation.

    Cost optimization strategy:
    1. Run fast pattern detector first (free, <50ms)
    2. If pattern confidence >= 0.7, use pattern result
    3. If pattern confidence < 0.7 (ambiguous), escalate to LLM (~$0.03/trace)

    Key insight: Rule-based F9 detection achieves only 2.5% recall on MAST.
    This hybrid approach uses LLM for most cases while benefiting from
    pattern detection for clear positives/negatives.

    Usage:
        detector = HybridRoleUsurpationDetector()
        result = detector.detect(snapshots, metadata)
    """

    name = "HybridRoleUsurpationDetector"
    version = "1.0"
    supported_failure_modes = ["F9"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        escalation_threshold: float = 0.7,
        confidence_threshold: float = 0.6,
    ):
        self.api_key = api_key
        self.escalation_threshold = escalation_threshold
        self.confidence_threshold = confidence_threshold
        self._pattern_detector = None
        self._llm_detector = None

    @property
    def pattern_detector(self):
        """Lazy-load pattern detector."""
        if self._pattern_detector is None:
            from .role_usurpation import TurnAwareRoleUsurpationDetector
            self._pattern_detector = TurnAwareRoleUsurpationDetector(
                min_turns=3,
                strict_mode=False,
                min_violations=1,
            )
        return self._pattern_detector

    @property
    def llm_detector(self):
        """Lazy-load LLM detector."""
        if self._llm_detector is None:
            self._llm_detector = LLMRoleUsurpationDetector(
                api_key=self.api_key,
                confidence_threshold=self.confidence_threshold,
            )
        return self._llm_detector

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """
        Detect F9 (Role Usurpation) using hybrid approach.

        Strategy:
        - Pattern detector first (fast, free)
        - Escalate to LLM on ambiguous cases (which is most cases for F9)

        Args:
            turns: List of turn snapshots
            conversation_metadata: Optional metadata about the conversation

        Returns:
            TurnAwareDetectionResult with detection decision
        """
        if len(turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for role usurpation analysis",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Step 1: Run pattern detector
        pattern_result = self.pattern_detector.detect(turns, conversation_metadata)

        # Step 2: Decide if we need LLM escalation
        # For F9, we escalate more aggressively since pattern detection is weak
        should_escalate = (
            pattern_result.confidence < self.escalation_threshold
            or not pattern_result.detected  # Always escalate if pattern didn't detect
        )

        if not should_escalate:
            # High confidence detection from pattern detector - use its result
            return TurnAwareDetectionResult(
                detected=pattern_result.detected,
                severity=pattern_result.severity,
                confidence=pattern_result.confidence,
                failure_mode=pattern_result.failure_mode,
                explanation=f"[Pattern] {pattern_result.explanation}",
                affected_turns=pattern_result.affected_turns,
                evidence={
                    **(pattern_result.evidence or {}),
                    "detection_method": "pattern",
                    "llm_escalated": False,
                },
                suggested_fix=pattern_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Step 3: Escalate to LLM for borderline/undetected cases
        try:
            llm_result = self.llm_detector.detect(turns, conversation_metadata)

            # Combine evidence from both detectors
            combined_evidence = {
                **(pattern_result.evidence or {}),
                **(llm_result.evidence or {}),
                "detection_method": "hybrid",
                "llm_escalated": True,
                "pattern_confidence": pattern_result.confidence,
                "pattern_detected": pattern_result.detected,
            }

            return TurnAwareDetectionResult(
                detected=llm_result.detected,
                severity=llm_result.severity,
                confidence=llm_result.confidence,
                failure_mode=llm_result.failure_mode,
                explanation=f"[LLM-verified] {llm_result.explanation}",
                affected_turns=llm_result.affected_turns or pattern_result.affected_turns,
                evidence=combined_evidence,
                suggested_fix=llm_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        except Exception as e:
            # LLM failed - fall back to pattern result
            logger.warning(f"LLM escalation failed, using pattern result: {e}")
            return TurnAwareDetectionResult(
                detected=pattern_result.detected,
                severity=pattern_result.severity,
                confidence=pattern_result.confidence,
                failure_mode=pattern_result.failure_mode,
                explanation=f"[Pattern-fallback] {pattern_result.explanation}",
                affected_turns=pattern_result.affected_turns,
                evidence={
                    **(pattern_result.evidence or {}),
                    "detection_method": "pattern_fallback",
                    "llm_escalated": True,
                    "llm_error": str(e),
                },
                suggested_fix=pattern_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )


# Convenience function to run all turn-aware detectors
def analyze_conversation_turns(
    turns: List[TurnSnapshot],
    conversation_metadata: Optional[Dict[str, Any]] = None,
    detectors: Optional[List[TurnAwareDetector]] = None,
    use_summarization: bool = True,
) -> List[TurnAwareDetectionResult]:
    """Run multiple turn-aware detectors on a conversation.

    Args:
        turns: List of conversation turns
        conversation_metadata: Optional metadata
        detectors: Optional list of detectors to run. If None, runs all defaults.
        use_summarization: Whether to use summarization for long conversations

    Returns:
        List of detection results (only those with detected=True)
    """
    if detectors is None:
        # Import all detector classes
        from .specification import TurnAwareSpecificationMismatchDetector
        from .task_decomposition import TurnAwareTaskDecompositionDetector
        from .resource import TurnAwareResourceMisallocationDetector
        from .conversation import TurnAwareConversationHistoryDetector
        from .loop import TurnAwareLoopDetector
        from .derailment import TurnAwareDerailmentDetector
        from .context_neglect import TurnAwareContextNeglectDetector
        from .withholding import TurnAwareInformationWithholdingDetector
        from .role_usurpation import TurnAwareRoleUsurpationDetector
        from .communication import TurnAwareCommunicationBreakdownDetector
        from .coordination import TurnAwareCoordinationFailureDetector
        from .output_validation import TurnAwareOutputValidationDetector
        from .quality_gate import TurnAwareQualityGateBypassDetector
        from .completion import TurnAwareCompletionMisjudgmentDetector
        from .termination import TurnAwareTerminationAwarenessDetector
        from .reasoning_action import TurnAwareReasoningActionMismatchDetector
        from .clarification import TurnAwareClarificationRequestDetector

        detectors = [
            TurnAwareSpecificationMismatchDetector(),  # F1
            TurnAwareTaskDecompositionDetector(),  # F2
            TurnAwareResourceMisallocationDetector(),  # F3
            TurnAwareConversationHistoryDetector(),  # F4
            TurnAwareLoopDetector(),  # F5
            TurnAwareDerailmentDetector(),  # F6
            TurnAwareContextNeglectDetector(),  # F7
            TurnAwareInformationWithholdingDetector(),  # F8
            TurnAwareRoleUsurpationDetector(),  # F9
            TurnAwareCommunicationBreakdownDetector(),  # F10
            TurnAwareCoordinationFailureDetector(),  # F11
            TurnAwareOutputValidationDetector(),  # F12
            TurnAwareQualityGateBypassDetector(),  # F13
            TurnAwareCompletionMisjudgmentDetector(),  # F14
            # New MAST-aligned detectors (NeurIPS 2025)
            TurnAwareTerminationAwarenessDetector(),  # F15 (FM-1.5, 40% of FC1)
            TurnAwareReasoningActionMismatchDetector(),  # F16 (FM-2.6, 26% of FC2)
            TurnAwareClarificationRequestDetector(),  # F17 (FM-2.2, 18% of FC2)
        ]

    # Check if conversation is long enough to need summarization
    working_turns = turns
    summarization_applied = False

    if use_summarization and len(turns) > MAX_TURNS_BEFORE_SUMMARIZATION:
        try:
            from app.core.summarizer import SlidingWindowManager, count_tokens

            # Check total tokens
            total_content = " ".join(t.content for t in turns)
            total_tokens = count_tokens(total_content)

            if total_tokens > MAX_TOKENS_BEFORE_SUMMARIZATION:
                logger.info(
                    f"Long conversation detected ({len(turns)} turns, ~{total_tokens} tokens). "
                    "Using sliding window for detection."
                )

                # For long conversations, we analyze in chunks
                # and aggregate results
                window_manager = SlidingWindowManager()

                # Convert TurnSnapshots to dicts for the window manager
                turn_dicts = [
                    {
                        "turn_number": t.turn_number,
                        "role": t.participant_type,
                        "participant_id": t.participant_id,
                        "content": t.content,
                        "content_hash": t.content_hash,
                    }
                    for t in turns
                ]

                # Get chunks for batch detection
                chunks = window_manager.chunk_for_batch_detection(turn_dicts)
                summarization_applied = True

                # For now, we'll just use the last chunk (most recent context)
                # Future enhancement: aggregate results from all chunks
                if chunks:
                    # Get turns covered by the last chunk
                    last_chunk = chunks[-1]
                    start_turn, end_turn = last_chunk.recent_turns

                    # Filter to recent turns
                    working_turns = [
                        t for t in turns
                        if start_turn <= t.turn_number <= end_turn
                    ]

                    # Always include first turn (task) if not already
                    first_turn = next((t for t in turns if t.turn_number == 1), None)
                    if first_turn and first_turn not in working_turns:
                        working_turns = [first_turn] + working_turns

        except ImportError as e:
            logger.warning(f"Summarizer not available, using full conversation: {e}")
        except Exception as e:
            logger.warning(f"Summarization failed, using full conversation: {e}")

    results = []
    for detector in detectors:
        try:
            result = detector.detect(working_turns, conversation_metadata)
            if result.detected:
                # Add summarization info to evidence if applicable
                if summarization_applied:
                    result.evidence["summarization_applied"] = True
                    result.evidence["original_turns"] = len(turns)
                    result.evidence["analyzed_turns"] = len(working_turns)
                results.append(result)
        except Exception as e:
            logger.error(f"Detector {detector.name} failed: {e}")

    return results
