"""
Full LLM Detector
=================

Full LLM-based detector using Claude for all failure modes.
Unlike hybrid detection which only escalates ambiguous cases to LLM,
this detector uses LLM for every trace.
"""

from typing import Any, Dict, List, Optional

from ._enums import MASTFailureMode
from .judge import MASTLLMJudge


class FullLLMDetector:
    """
    Full LLM-based detector using Claude Opus 4.5 for all failure modes.

    Unlike hybrid detection which only escalates ambiguous cases to LLM,
    this detector uses LLM for every trace. Target: 50-60% F1 on MAST benchmark.

    Usage:
        detector = FullLLMDetector()
        results = detector.detect_all_modes(
            task="Build a REST API",
            trace_summary="Agent started by...",
            key_events=["Started coding", "Finished endpoint"]
        )

        # Check which modes were detected
        for mode, detected in results.items():
            if detected:
                print(f"{mode} failure detected!")
    """

    def __init__(self, api_key: Optional[str] = None, db_session=None):
        self._judge = MASTLLMJudge(api_key=api_key, db_session=db_session)

    def detect_all_modes(
        self,
        task: str,
        trace_summary: str,
        key_events: Optional[List[str]] = None,
        modes_to_check: Optional[List[str]] = None,
        full_conversation: str = "",
        agent_interactions: Optional[List[str]] = None,
        coordination_events: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Detect all failure modes for a trace.

        Args:
            task: The original task/goal
            trace_summary: Summary of agent output/behavior
            key_events: List of key events from the trace
            modes_to_check: Optional list of mode strings (e.g., ["F1", "F6"])
            full_conversation: Full conversation transcript for context
            agent_interactions: Agent-to-agent interaction patterns
            coordination_events: Coordination-related events

        Returns:
            Dict mapping mode string to detection status (True/False)
        """
        # Convert string modes to enums
        if modes_to_check:
            enum_modes = [MASTFailureMode(m) for m in modes_to_check]
        else:
            enum_modes = None

        # Get full LLM evaluation with enhanced context
        judgment_results = self._judge.evaluate_all_modes(
            task=task,
            trace_summary=trace_summary,
            key_events=key_events,
            modes_to_check=enum_modes,
            full_conversation=full_conversation,
            agent_interactions=agent_interactions,
            coordination_events=coordination_events,
        )

        # Convert to simple detected/not-detected
        detected = {}
        for mode, result in judgment_results.items():
            # Consider YES as detected (LLM already provides calibrated confidence)
            # Also consider UNCERTAIN with high confidence as borderline positive
            detected[mode] = (
                result.verdict == "YES" or
                (result.verdict == "UNCERTAIN" and result.confidence >= 0.7)
            )

        return detected

    def detect_with_details(
        self,
        task: str,
        trace_summary: str,
        key_events: Optional[List[str]] = None,
        modes_to_check: Optional[List[str]] = None,
        full_conversation: str = "",
        agent_interactions: Optional[List[str]] = None,
        coordination_events: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect with full details including confidence and reasoning.

        Args:
            task: The original task/goal
            trace_summary: Summary of agent output/behavior
            key_events: List of key events from the trace
            modes_to_check: Optional list of mode strings
            full_conversation: Full conversation transcript for context
            agent_interactions: Agent-to-agent interaction patterns
            coordination_events: Coordination-related events

        Returns:
            Dict with mode -> {detected, confidence, verdict, reasoning, cost}
        """
        if modes_to_check:
            enum_modes = [MASTFailureMode(m) for m in modes_to_check]
        else:
            enum_modes = None

        judgment_results = self._judge.evaluate_all_modes(
            task=task,
            trace_summary=trace_summary,
            key_events=key_events,
            modes_to_check=enum_modes,
            full_conversation=full_conversation,
            agent_interactions=agent_interactions,
            coordination_events=coordination_events,
        )

        details = {}
        for mode, result in judgment_results.items():
            # Match detect_all_modes logic: YES or high-confidence UNCERTAIN
            detected = (
                result.verdict == "YES" or
                (result.verdict == "UNCERTAIN" and result.confidence >= 0.7)
            )
            details[mode] = {
                "detected": detected,
                "confidence": result.confidence,
                "verdict": result.verdict,
                "reasoning": result.reasoning,
                "cost_usd": result.cost_usd,
                "tokens_used": result.tokens_used,
                "cached": result.cached,
            }

        return details
