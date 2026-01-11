"""
Hybrid Detection Pipeline
==========================

Combines fast pattern-based detection with LLM verification for ambiguous cases.

Architecture:
1. Pattern detectors run first (fast, free)
2. Results with confidence in [0.40, 0.85] go to LLM judge
3. High confidence (>0.85) accepted directly
4. Low confidence (<0.40) rejected directly

This achieves high accuracy while minimizing LLM API costs.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .mast_llm_judge import (
    MASTFailureMode,
    MASTLLMJudge,
    JudgmentResult,
    get_cost_tracker,
    get_model_for_failure_mode,
    DEFAULT_MODEL_KEY,
    HIGH_STAKES_MODEL_KEY,
    HIGH_STAKES_FAILURE_MODES,
)
from .task_extractors import (
    ConversationTurn,
    ExtractionResult,
    extract_task,
    detect_framework,
)
from .turn_aware import (
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    TurnSnapshot,
)

logger = logging.getLogger(__name__)


class VerificationDecision(str, Enum):
    """Decision for ambiguous detections."""
    ACCEPT = "accept"       # High confidence, no LLM needed
    REJECT = "reject"       # Low confidence, skip
    VERIFY = "verify"       # Ambiguous, send to LLM
    LLM_YES = "llm_yes"     # LLM confirmed detection
    LLM_NO = "llm_no"       # LLM rejected detection
    LLM_UNCERTAIN = "llm_uncertain"  # LLM unsure


@dataclass
class HybridDetectionResult:
    """Result from hybrid detection pipeline."""
    # Original pattern detection
    pattern_result: TurnAwareDetectionResult
    # LLM verification (if performed)
    llm_result: Optional[JudgmentResult] = None
    # Final decision
    decision: VerificationDecision = VerificationDecision.REJECT
    # Final confidence (may be updated by LLM)
    final_confidence: float = 0.0
    # Final detected status
    final_detected: bool = False
    # Explanation combining pattern + LLM reasoning
    combined_explanation: str = ""
    # Cost tracking
    llm_cost_usd: float = 0.0
    llm_tokens_used: int = 0


@dataclass
class HybridPipelineConfig:
    """Configuration for hybrid detection pipeline."""
    # Confidence thresholds for routing
    high_confidence_threshold: float = 0.85
    low_confidence_threshold: float = 0.40

    # Which failure modes to send to LLM for verification
    # (only high-FPR modes benefit from LLM verification)
    llm_verify_modes: List[str] = field(default_factory=lambda: [
        "F1",   # Specification Violation - 60% FPR
        "F3",   # Coordination Failure - 10% FPR
        "F8",   # Step Repetition - 20% FPR
        "F12",  # Resource Limit - 20% FPR
        "F13",  # Stalling - 10% FPR
    ])

    # Enable/disable LLM verification
    llm_enabled: bool = True

    # Maximum LLM cost per trace (USD)
    max_llm_cost_per_trace: float = 0.10

    # Tiered model selection (based on benchmark results)
    # Default: sonnet-4 (97.1% accuracy, $0.48/100 judgments)
    # High-stakes: sonnet-4-thinking (99.0% accuracy, $1.66/100 judgments)
    use_tiered_models: bool = True
    default_model_key: str = DEFAULT_MODEL_KEY
    high_stakes_model_key: str = HIGH_STAKES_MODEL_KEY
    high_stakes_modes: List[str] = field(default_factory=lambda: list(HIGH_STAKES_FAILURE_MODES))


class HybridDetectionPipeline:
    """
    Hybrid detection combining pattern matching with LLM verification.

    Usage:
        pipeline = HybridDetectionPipeline()

        # From TurnSnapshots
        results = pipeline.detect_from_snapshots(snapshots, metadata)

        # From ConversationTurns
        results = pipeline.detect_from_turns(turns, metadata)
    """

    def __init__(
        self,
        config: Optional[HybridPipelineConfig] = None,
        llm_judge: Optional[MASTLLMJudge] = None,
    ):
        self.config = config or HybridPipelineConfig()
        self._llm_judge = llm_judge
        # Cache for tiered model judges
        self._judges_by_model: Dict[str, MASTLLMJudge] = {}

    @property
    def llm_judge(self) -> MASTLLMJudge:
        """Lazy-load default LLM judge."""
        if self._llm_judge is None:
            self._llm_judge = MASTLLMJudge(model_key=self.config.default_model_key)
        return self._llm_judge

    def _get_judge_for_mode(self, failure_mode: str) -> MASTLLMJudge:
        """
        Get the appropriate LLM judge for a failure mode.

        Uses tiered model selection when enabled:
        - High-stakes modes (F6, F8): sonnet-4-thinking (99% accuracy)
        - Standard modes: sonnet-4 (97.1% accuracy, lower cost)

        Args:
            failure_mode: MAST failure mode code

        Returns:
            MASTLLMJudge configured with appropriate model
        """
        if not self.config.use_tiered_models:
            return self.llm_judge

        # Determine model key based on failure mode
        if failure_mode in self.config.high_stakes_modes:
            model_key = self.config.high_stakes_model_key
            logger.info(f"Using high-stakes model ({model_key}) for {failure_mode}")
        else:
            model_key = self.config.default_model_key

        # Cache judges by model key
        if model_key not in self._judges_by_model:
            self._judges_by_model[model_key] = MASTLLMJudge(model_key=model_key)

        return self._judges_by_model[model_key]

    def _should_verify_with_llm(
        self,
        pattern_result: TurnAwareDetectionResult,
    ) -> VerificationDecision:
        """Determine if result should go to LLM for verification."""

        if not self.config.llm_enabled:
            return VerificationDecision.ACCEPT if pattern_result.detected else VerificationDecision.REJECT

        confidence = pattern_result.confidence
        failure_mode = pattern_result.failure_mode

        # High confidence: accept directly
        if confidence >= self.config.high_confidence_threshold:
            return VerificationDecision.ACCEPT

        # Low confidence: reject directly
        if confidence < self.config.low_confidence_threshold:
            return VerificationDecision.REJECT

        # Check if this mode benefits from LLM verification
        if failure_mode not in self.config.llm_verify_modes:
            # Not a high-FPR mode, use pattern result
            return VerificationDecision.ACCEPT if pattern_result.detected else VerificationDecision.REJECT

        # Ambiguous case: send to LLM
        return VerificationDecision.VERIFY

    def _convert_snapshots_to_turns(
        self,
        snapshots: List[TurnSnapshot],
    ) -> List[ConversationTurn]:
        """Convert TurnSnapshots to ConversationTurns for extraction."""
        turns = []
        for snapshot in snapshots:
            turns.append(ConversationTurn(
                role=snapshot.participant_type,
                content=snapshot.content,
                participant_id=snapshot.participant_id,
                metadata=snapshot.turn_metadata,
            ))
        return turns

    def _verify_with_llm(
        self,
        pattern_result: TurnAwareDetectionResult,
        extraction: ExtractionResult,
    ) -> JudgmentResult:
        """Send detection to LLM for verification using tiered model selection."""

        # Map failure mode string to enum
        try:
            failure_mode = MASTFailureMode(pattern_result.failure_mode)
        except ValueError:
            # Unknown failure mode, skip LLM
            logger.warning(f"Unknown failure mode for LLM: {pattern_result.failure_mode}")
            return JudgmentResult(
                failure_mode=MASTFailureMode.F1,  # Placeholder
                verdict="UNCERTAIN",
                confidence=0.0,
                reasoning="Unknown failure mode",
                raw_response="",
                model_used="none",
                tokens_used=0,
                cost_usd=0.0,
            )

        # Get the appropriate judge for this failure mode (tiered selection)
        judge = self._get_judge_for_mode(pattern_result.failure_mode)

        return judge.evaluate(
            failure_mode=failure_mode,
            task=extraction.task,
            trace_summary=extraction.agent_output_summary,
            key_events=extraction.key_events,
        )

    def _combine_results(
        self,
        pattern_result: TurnAwareDetectionResult,
        llm_result: Optional[JudgmentResult],
        decision: VerificationDecision,
    ) -> HybridDetectionResult:
        """Combine pattern and LLM results into final detection."""

        # Determine final detection status and confidence
        if decision == VerificationDecision.ACCEPT:
            final_detected = pattern_result.detected
            final_confidence = pattern_result.confidence
            explanation = pattern_result.explanation
        elif decision == VerificationDecision.REJECT:
            final_detected = False
            final_confidence = pattern_result.confidence
            explanation = f"Low confidence ({pattern_result.confidence:.2f}), skipped"
        elif decision == VerificationDecision.LLM_YES:
            final_detected = True
            # Boost confidence based on LLM agreement
            final_confidence = min(0.95, pattern_result.confidence + 0.2)
            explanation = f"Pattern detected, LLM confirmed: {llm_result.reasoning}"
        elif decision == VerificationDecision.LLM_NO:
            final_detected = False
            # LLM says no, override pattern detection
            final_confidence = max(0.0, pattern_result.confidence - 0.3)
            explanation = f"Pattern detected but LLM rejected: {llm_result.reasoning}"
        elif decision == VerificationDecision.LLM_UNCERTAIN:
            # LLM uncertain, fall back to pattern result with slight discount
            final_detected = pattern_result.detected
            final_confidence = pattern_result.confidence * 0.9
            explanation = f"LLM uncertain, using pattern result: {pattern_result.explanation}"
        else:
            final_detected = pattern_result.detected
            final_confidence = pattern_result.confidence
            explanation = pattern_result.explanation

        return HybridDetectionResult(
            pattern_result=pattern_result,
            llm_result=llm_result,
            decision=decision,
            final_confidence=final_confidence,
            final_detected=final_detected,
            combined_explanation=explanation,
            llm_cost_usd=llm_result.cost_usd if llm_result else 0.0,
            llm_tokens_used=llm_result.tokens_used if llm_result else 0,
        )

    def verify_detection(
        self,
        pattern_result: TurnAwareDetectionResult,
        turns: List[ConversationTurn],
        metadata: Dict[str, Any],
    ) -> HybridDetectionResult:
        """
        Verify a single pattern detection result with optional LLM.

        Args:
            pattern_result: Result from pattern-based detector
            turns: Conversation turns for context extraction
            metadata: Trace metadata

        Returns:
            HybridDetectionResult with final decision
        """
        # Check if LLM verification needed
        decision = self._should_verify_with_llm(pattern_result)

        if decision != VerificationDecision.VERIFY:
            return self._combine_results(pattern_result, None, decision)

        # Extract task and context for LLM
        extraction = extract_task(turns, metadata)

        # Call LLM judge
        llm_result = self._verify_with_llm(pattern_result, extraction)

        # Update decision based on LLM verdict
        if llm_result.verdict == "YES":
            decision = VerificationDecision.LLM_YES
        elif llm_result.verdict == "NO":
            decision = VerificationDecision.LLM_NO
        else:
            decision = VerificationDecision.LLM_UNCERTAIN

        return self._combine_results(pattern_result, llm_result, decision)

    def verify_detections(
        self,
        pattern_results: List[TurnAwareDetectionResult],
        turns: List[ConversationTurn],
        metadata: Dict[str, Any],
    ) -> List[HybridDetectionResult]:
        """
        Verify multiple pattern detections with LLM.

        Optimized to:
        - Skip LLM for high/low confidence results
        - Share extraction across multiple verifications
        - Respect cost budget

        Args:
            pattern_results: Results from pattern-based detectors
            turns: Conversation turns for context extraction
            metadata: Trace metadata

        Returns:
            List of HybridDetectionResults
        """
        results = []
        total_cost = 0.0

        # Pre-extract once for efficiency
        extraction = None

        for pattern_result in pattern_results:
            # Check if we should verify
            decision = self._should_verify_with_llm(pattern_result)

            if decision != VerificationDecision.VERIFY:
                results.append(self._combine_results(pattern_result, None, decision))
                continue

            # Check cost budget
            if total_cost >= self.config.max_llm_cost_per_trace:
                logger.warning(f"LLM cost budget exceeded ({total_cost:.4f} >= {self.config.max_llm_cost_per_trace})")
                results.append(self._combine_results(pattern_result, None, VerificationDecision.ACCEPT))
                continue

            # Lazy extraction
            if extraction is None:
                extraction = extract_task(turns, metadata)

            # Call LLM
            llm_result = self._verify_with_llm(pattern_result, extraction)
            total_cost += llm_result.cost_usd

            # Update decision
            if llm_result.verdict == "YES":
                decision = VerificationDecision.LLM_YES
            elif llm_result.verdict == "NO":
                decision = VerificationDecision.LLM_NO
            else:
                decision = VerificationDecision.LLM_UNCERTAIN

            results.append(self._combine_results(pattern_result, llm_result, decision))

        return results

    def detect_from_snapshots(
        self,
        snapshots: List[TurnSnapshot],
        metadata: Dict[str, Any],
        pattern_detectors: Optional[List] = None,
    ) -> List[HybridDetectionResult]:
        """
        Run full hybrid detection pipeline on TurnSnapshots.

        Args:
            snapshots: List of TurnSnapshots
            metadata: Trace metadata
            pattern_detectors: Optional list of pattern detectors to use

        Returns:
            List of HybridDetectionResults
        """
        # Convert to turns for extraction
        turns = self._convert_snapshots_to_turns(snapshots)

        # Run pattern detectors
        if pattern_detectors is None:
            # Import default detectors
            from .turn_aware import (
                TurnAwareContextNeglectDetector,
                TurnAwareDerailmentDetector,
                TurnAwareSpecificationMismatchDetector,
                TurnAwareLoopDetector,
            )
            pattern_detectors = [
                TurnAwareContextNeglectDetector(),
                TurnAwareDerailmentDetector(),
                TurnAwareSpecificationMismatchDetector(),
                TurnAwareLoopDetector(),
            ]

        pattern_results = []
        for detector in pattern_detectors:
            result = detector.detect(snapshots)
            if result.detected or result.confidence > 0.3:  # Include borderline cases
                pattern_results.append(result)

        # Verify with LLM
        return self.verify_detections(pattern_results, turns, metadata)


def create_hybrid_pipeline(
    llm_enabled: bool = True,
    high_threshold: float = 0.85,
    low_threshold: float = 0.40,
) -> HybridDetectionPipeline:
    """
    Factory function to create a configured hybrid pipeline.

    Args:
        llm_enabled: Whether to enable LLM verification
        high_threshold: Confidence above which to accept directly
        low_threshold: Confidence below which to reject directly

    Returns:
        Configured HybridDetectionPipeline
    """
    config = HybridPipelineConfig(
        llm_enabled=llm_enabled,
        high_confidence_threshold=high_threshold,
        low_confidence_threshold=low_threshold,
    )
    return HybridDetectionPipeline(config=config)
