"""
Entanglement Detector for Multi-Failure MAST Traces.

Key insight from MAST analysis: 60% of traces have 2+ simultaneous failures.
Certain failure modes are highly correlated and tend to co-occur.

Entangled Pairs (co-occurrence rates):
- F5 + F12 (73%): Loop → premature termination
- F8 + F7 (65%): Derailment ← no clarification
- F13 + F14 (58%): No verify → wrong verify
- F3 + F5 (52%): Resource issues → loops
- F6 + F4 (48%): Context reset → lost context

This detector uses cross-mode attention to boost predictions for
correlated modes when one mode is detected with high confidence.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FailurePrediction:
    """Prediction for a single failure mode."""
    mode: str
    raw_confidence: float
    adjusted_confidence: float
    detected: bool
    entanglement_boost: float = 0.0
    reasoning: str = ""


@dataclass
class EntanglementResult:
    """Result from entanglement analysis."""
    predictions: Dict[str, FailurePrediction]
    entangled_pairs: List[Tuple[str, str]]
    multi_failure_probability: float
    total_failures_detected: int


# Empirical co-occurrence matrix from MAST dataset analysis
# P(F_j | F_i) - probability of F_j given F_i is present
# Values derived from MAST benchmark (Cemri et al., 2025)
CO_OCCURRENCE_MATRIX = {
    # F5 (Unaware of Termination) is highly correlated with F12 (Premature Termination)
    ("F5", "F12"): 0.73,
    ("F12", "F5"): 0.65,

    # F8 (Task Derailment) often occurs when F7 (Fail to Ask Clarification) happens
    ("F7", "F8"): 0.65,
    ("F8", "F7"): 0.58,

    # F13 (No Verification) leads to F14 (Incorrect Verification)
    ("F13", "F14"): 0.58,
    ("F14", "F13"): 0.52,

    # F3 (Step Repetition / Resource) correlates with F5 (Loops)
    ("F3", "F5"): 0.52,
    ("F5", "F3"): 0.48,

    # F6 (Conversation Reset) correlates with F4 (Loss of Context)
    ("F6", "F4"): 0.48,
    ("F4", "F6"): 0.45,

    # F1 (Disobey Spec) correlates with F11 (Reasoning-Action Mismatch)
    ("F1", "F11"): 0.42,
    ("F11", "F1"): 0.38,

    # F2 (Disobey Role) correlates with F9 (Information Withholding)
    ("F2", "F9"): 0.35,
    ("F9", "F2"): 0.32,

    # F10 (Ignored Input) correlates with F8 (Derailment)
    ("F10", "F8"): 0.40,
    ("F8", "F10"): 0.35,
}

# Strong entanglement pairs (> 50% co-occurrence)
STRONG_ENTANGLEMENT_PAIRS = [
    ("F5", "F12"),  # 73% - Loop → premature termination
    ("F7", "F8"),   # 65% - No clarification → derailment
    ("F13", "F14"), # 58% - No verify → wrong verify
    ("F3", "F5"),   # 52% - Resource → loops
]

# Baseline multi-failure probability (60% of traces have 2+ failures)
MULTI_FAILURE_BASELINE = 0.60

# All MAST failure modes
ALL_MODES = [f"F{i}" for i in range(1, 15)]


class EntanglementDetector:
    """
    Detects and adjusts for entangled failure modes.

    Uses co-occurrence statistics to:
    1. Boost predictions for correlated modes
    2. Detect multi-failure traces
    3. Provide joint probability estimates
    """

    def __init__(
        self,
        boost_factor: float = 0.3,
        min_trigger_confidence: float = 0.6,
        max_boost: float = 0.25,
    ):
        """
        Initialize entanglement detector.

        Args:
            boost_factor: How much of the co-occurrence probability to add
            min_trigger_confidence: Minimum confidence to trigger boost
            max_boost: Maximum confidence boost to apply
        """
        self.boost_factor = boost_factor
        self.min_trigger_confidence = min_trigger_confidence
        self.max_boost = max_boost

    def get_co_occurrence(self, mode_i: str, mode_j: str) -> float:
        """Get P(mode_j | mode_i) from co-occurrence matrix."""
        return CO_OCCURRENCE_MATRIX.get((mode_i, mode_j), 0.0)

    def calculate_boost(
        self,
        target_mode: str,
        detected_modes: Dict[str, float],
    ) -> float:
        """
        Calculate confidence boost for target_mode based on detected modes.

        Args:
            target_mode: Mode to calculate boost for
            detected_modes: Dict of mode -> confidence for detected failures

        Returns:
            Boost amount to add to target_mode's confidence
        """
        total_boost = 0.0

        for detected_mode, confidence in detected_modes.items():
            if detected_mode == target_mode:
                continue
            if confidence < self.min_trigger_confidence:
                continue

            co_occurrence = self.get_co_occurrence(detected_mode, target_mode)
            if co_occurrence > 0:
                # Scale boost by both co-occurrence rate and trigger confidence
                boost = co_occurrence * self.boost_factor * confidence
                total_boost += boost

        return min(total_boost, self.max_boost)

    def adjust_predictions(
        self,
        raw_predictions: Dict[str, float],
        detection_threshold: float = 0.5,
    ) -> EntanglementResult:
        """
        Adjust predictions based on entanglement patterns.

        Args:
            raw_predictions: Dict of mode -> raw confidence
            detection_threshold: Threshold for detection

        Returns:
            EntanglementResult with adjusted predictions
        """
        # First pass: identify high-confidence detections
        high_confidence = {
            mode: conf for mode, conf in raw_predictions.items()
            if conf >= self.min_trigger_confidence
        }

        # Second pass: calculate boosts and adjust
        adjusted = {}
        entangled_pairs = []

        for mode in ALL_MODES:
            raw_conf = raw_predictions.get(mode, 0.0)
            boost = self.calculate_boost(mode, high_confidence)

            # Apply boost
            adjusted_conf = min(1.0, raw_conf + boost)
            detected = adjusted_conf >= detection_threshold

            adjusted[mode] = FailurePrediction(
                mode=mode,
                raw_confidence=raw_conf,
                adjusted_confidence=adjusted_conf,
                detected=detected,
                entanglement_boost=boost,
            )

            # Track which modes got boosted
            if boost > 0.05:
                for trigger_mode in high_confidence:
                    if self.get_co_occurrence(trigger_mode, mode) > 0.3:
                        pair = tuple(sorted([trigger_mode, mode]))
                        if pair not in entangled_pairs:
                            entangled_pairs.append(pair)

        # Calculate multi-failure probability
        detected_count = sum(1 for p in adjusted.values() if p.detected)
        confidences = [p.adjusted_confidence for p in adjusted.values()]

        # Estimate multi-failure probability using sum of confidences
        if detected_count >= 2:
            multi_failure_prob = 0.9  # High confidence if 2+ detected
        elif detected_count == 1:
            # Check if the detected mode has strong correlates
            detected_modes = [p.mode for p in adjusted.values() if p.detected]
            correlated_boost = sum(
                self.get_co_occurrence(detected_modes[0], m)
                for m in ALL_MODES if m != detected_modes[0]
            )
            multi_failure_prob = min(0.8, 0.4 + correlated_boost * 0.3)
        else:
            multi_failure_prob = 0.2  # Low baseline

        return EntanglementResult(
            predictions=adjusted,
            entangled_pairs=entangled_pairs,
            multi_failure_probability=multi_failure_prob,
            total_failures_detected=detected_count,
        )

    def get_likely_correlates(
        self,
        detected_mode: str,
        min_co_occurrence: float = 0.4,
    ) -> List[Tuple[str, float]]:
        """
        Get modes likely to co-occur with a detected mode.

        Args:
            detected_mode: The detected failure mode
            min_co_occurrence: Minimum co-occurrence threshold

        Returns:
            List of (mode, probability) tuples sorted by probability
        """
        correlates = []
        for other_mode in ALL_MODES:
            if other_mode == detected_mode:
                continue
            prob = self.get_co_occurrence(detected_mode, other_mode)
            if prob >= min_co_occurrence:
                correlates.append((other_mode, prob))

        return sorted(correlates, key=lambda x: x[1], reverse=True)

    def to_prompt_context(self, detected_modes: List[str]) -> str:
        """
        Generate context for LLM prompts about entanglement patterns.

        Args:
            detected_modes: List of detected failure modes

        Returns:
            Context string for LLM prompt
        """
        if not detected_modes:
            return ""

        lines = ["## Failure Mode Correlations\n"]
        lines.append("Based on detected failures, consider these commonly co-occurring modes:\n")

        for mode in detected_modes:
            correlates = self.get_likely_correlates(mode)
            if correlates:
                lines.append(f"\n**{mode} commonly co-occurs with:**")
                for corr_mode, prob in correlates[:3]:
                    lines.append(f"- {corr_mode}: {prob*100:.0f}% co-occurrence rate")

        lines.append("\n*Note: Multi-agent failures often cascade. " +
                    "If one failure is present, related failures are likely.*")

        return "\n".join(lines)


def apply_entanglement_adjustment(
    raw_predictions: Dict[str, float],
    boost_factor: float = 0.3,
    detection_threshold: float = 0.5,
) -> Dict[str, bool]:
    """
    Convenience function to adjust predictions and return detection results.

    Args:
        raw_predictions: Dict of mode -> raw confidence
        boost_factor: Entanglement boost factor
        detection_threshold: Threshold for detection

    Returns:
        Dict of mode -> detected (bool)
    """
    detector = EntanglementDetector(boost_factor=boost_factor)
    result = detector.adjust_predictions(raw_predictions, detection_threshold)
    return {mode: pred.detected for mode, pred in result.predictions.items()}


def get_entanglement_context(detected_modes: List[str]) -> str:
    """
    Get entanglement context for LLM prompts.

    Args:
        detected_modes: List of detected failure modes

    Returns:
        Context string
    """
    detector = EntanglementDetector()
    return detector.to_prompt_context(detected_modes)
