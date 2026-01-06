"""Ensemble detection with structural feature calibration.

Combines content-based detection with structural/behavioral features to
reduce overfitting and improve detection reliability.
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.feature_extraction import TraceFeatureExtractor


@dataclass
class EnsembleResult:
    """Result from ensemble detection."""
    detected: bool
    content_detected: bool
    structural_score: float
    calibrated_confidence: float
    failure_mode: str
    explanation: str


class EnsembleDetector:
    """Ensemble detector combining content and structural signals."""

    # Structural feature thresholds for each failure mode
    # These represent expected structural patterns for each failure type
    STRUCTURAL_PROFILES = {
        "F1": {  # Specification Mismatch
            "relevant_features": ["behav_completion_score", "behav_failure_score", "coord_handoff_quality_score"],
            "expected_ranges": {
                "behav_failure_score": (1, 10),  # Expect some failure indicators
                "coord_handoff_quality_score": (0, 0.5),  # Poor handoff quality
            },
        },
        "F2": {  # Task Decomposition Failure
            "relevant_features": ["struct_max_depth", "struct_span_count", "behav_tool_call_count"],
            "expected_ranges": {
                "struct_max_depth": (0, 2),  # Shallow decomposition
                "struct_span_count": (1, 4),  # Few spans
            },
        },
        "F3": {  # Resource Misallocation
            "relevant_features": ["behav_span_error_rate", "behav_total_retries", "struct_avg_span_duration_ms"],
            "expected_ranges": {
                "behav_span_error_rate": (0.1, 1.0),  # Some errors
                "behav_total_retries": (1, 100),  # Retries present
            },
        },
        "F4": {  # Tool Provision Failure
            "relevant_features": ["behav_tool_call_count", "behav_tool_failure_rate", "behav_failure_score"],
            "expected_ranges": {
                "behav_tool_failure_rate": (0.2, 1.0),  # Tool failures
            },
        },
        "F5": {  # Flawed Workflow
            "relevant_features": ["coord_transition_diversity", "struct_max_branching_factor", "behav_span_error_rate"],
            "expected_ranges": {
                "coord_transition_diversity": (0, 0.3),  # Limited transitions
            },
        },
        "F6": {  # Task Derailment
            "relevant_features": ["coord_context_passes", "behav_delegation_score", "struct_unique_agents"],
            "expected_ranges": {
                "coord_context_passes": (0, 1),  # Poor context passing
            },
        },
        "F7": {  # Context Neglect
            "relevant_features": ["behav_info_preservation_ratio", "coord_context_passes", "behav_avg_output_size"],
            "expected_ranges": {
                "behav_info_preservation_ratio": (0, 1.0),  # Low info preservation
                "coord_context_passes": (0, 1),
            },
        },
        "F8": {  # Information Withholding
            "relevant_features": ["behav_info_preservation_ratio", "behav_avg_output_size", "coord_handoff_quality_score"],
            "expected_ranges": {
                "behav_info_preservation_ratio": (0, 0.8),  # Info loss
            },
        },
        "F9": {  # Role Usurpation
            "relevant_features": ["struct_unique_agents", "coord_agents_with_multiple_calls", "behav_delegation_score"],
            "expected_ranges": {
                "coord_agents_with_multiple_calls": (2, 100),  # Multiple calls indicate scope creep
            },
        },
        "F10": {  # Communication Breakdown
            "relevant_features": ["coord_handoff_quality_score", "coord_unique_transition_types", "behav_uncertainty_score"],
            "expected_ranges": {
                "coord_handoff_quality_score": (0, 0.4),  # Poor handoffs
                "behav_uncertainty_score": (1, 100),  # Uncertainty present
            },
        },
        "F11": {  # Coordination Failure
            "relevant_features": ["coord_total_agent_transitions", "coord_handoff_quality_score", "struct_has_parallel_execution"],
            "expected_ranges": {
                "coord_handoff_quality_score": (0, 0.4),
            },
        },
        "F12": {  # Output Validation Failure
            "relevant_features": ["behav_completion_score", "behav_failure_score", "struct_span_count"],
            "expected_ranges": {
                "behav_failure_score": (1, 100),  # Validation failures
            },
        },
        "F13": {  # Quality Gate Bypass
            "relevant_features": ["struct_span_count", "behav_completion_score", "coord_transition_diversity"],
            "expected_ranges": {
                "struct_span_count": (1, 4),  # Fewer spans = skipped steps
            },
        },
        "F14": {  # Completion Misjudgment
            "relevant_features": ["behav_completion_score", "behav_failure_score", "behav_info_preservation_ratio"],
            "expected_ranges": {
                "behav_completion_score": (0, 2),  # Low actual completion indicators
                "behav_failure_score": (1, 100),  # But some failure indicators
            },
        },
    }

    def __init__(self, content_weight: float = 0.6, structural_weight: float = 0.4):
        """Initialize ensemble detector.

        Args:
            content_weight: Weight for content-based detection (0-1)
            structural_weight: Weight for structural features (0-1)
        """
        assert abs(content_weight + structural_weight - 1.0) < 0.001
        self.content_weight = content_weight
        self.structural_weight = structural_weight
        self.feature_extractor = TraceFeatureExtractor()

    def compute_structural_score(self, trace: dict, failure_mode: str) -> float:
        """Compute structural consistency score for a failure mode.

        Returns a score from 0 to 1 indicating how well the trace's
        structural features match the expected profile for the failure mode.
        """
        if failure_mode not in self.STRUCTURAL_PROFILES:
            return 0.5  # Neutral score for unknown modes

        profile = self.STRUCTURAL_PROFILES[failure_mode]
        features = self.feature_extractor.extract_all_features(trace)

        matches = 0
        total_checks = 0

        for feature_name, (min_val, max_val) in profile.get("expected_ranges", {}).items():
            feature_value = features.get(feature_name, 0)

            # Handle dict values (like status_distribution)
            if isinstance(feature_value, dict):
                continue

            total_checks += 1
            if min_val <= feature_value <= max_val:
                matches += 1
            elif feature_value < min_val:
                # Partial credit for being close
                if min_val > 0:
                    matches += max(0, 1 - (min_val - feature_value) / min_val)
            else:
                # Partial credit for being close
                if max_val > 0:
                    matches += max(0, 1 - (feature_value - max_val) / max_val)

        if total_checks == 0:
            return 0.5

        return min(1.0, matches / total_checks)

    def detect(
        self,
        trace: dict,
        failure_mode: str,
        content_detected: bool,
        content_confidence: float = 0.7,
    ) -> EnsembleResult:
        """Run ensemble detection combining content and structural signals.

        Args:
            trace: The trace to analyze
            failure_mode: The failure mode being detected (F1-F14)
            content_detected: Whether content-based detection flagged this trace
            content_confidence: Confidence from content-based detection (0-1)

        Returns:
            EnsembleResult with calibrated detection result
        """
        structural_score = self.compute_structural_score(trace, failure_mode)

        # Combine scores
        content_score = content_confidence if content_detected else 0.0
        combined_score = (
            self.content_weight * content_score +
            self.structural_weight * structural_score
        )

        # Determine final detection
        # Detection threshold adjusts based on structural consistency
        base_threshold = 0.4
        # If structural score is high, we're more confident in content detection
        # If structural score is low, we need higher content confidence
        adjusted_threshold = base_threshold + (0.2 * (1 - structural_score))

        final_detected = combined_score >= adjusted_threshold

        # Generate explanation
        if final_detected:
            if content_detected and structural_score > 0.5:
                explanation = f"Both content patterns and structural features support {failure_mode} detection"
            elif content_detected:
                explanation = f"Content patterns detected {failure_mode}, structural consistency is {structural_score:.1%}"
            else:
                explanation = f"Structural features suggest {failure_mode} (score: {structural_score:.1%})"
        else:
            if content_detected and structural_score < 0.3:
                explanation = f"Content detection overridden by low structural consistency ({structural_score:.1%})"
            else:
                explanation = f"No strong evidence for {failure_mode}"

        return EnsembleResult(
            detected=final_detected,
            content_detected=content_detected,
            structural_score=structural_score,
            calibrated_confidence=combined_score,
            failure_mode=failure_mode,
            explanation=explanation,
        )


def run_ensemble_detection(
    traces: list[dict],
    failure_mode: str,
    content_detector: Callable[[dict], tuple[bool, float]],
    content_weight: float = 0.6,
    structural_weight: float = 0.4,
) -> dict:
    """Run ensemble detection on a set of traces.

    Args:
        traces: List of trace dictionaries
        failure_mode: The failure mode being detected
        content_detector: Function that takes a trace and returns (detected, confidence)
        content_weight: Weight for content-based detection
        structural_weight: Weight for structural features

    Returns:
        Detection results with statistics
    """
    ensemble = EnsembleDetector(content_weight, structural_weight)

    results = {
        "detected": 0,
        "total": len(traces),
        "content_only_detected": 0,
        "structural_boosted": 0,
        "content_overridden": 0,
        "samples": [],
    }

    for trace in traces:
        # Run content-based detection
        content_detected, content_confidence = content_detector(trace)

        # Run ensemble detection
        result = ensemble.detect(
            trace=trace,
            failure_mode=failure_mode,
            content_detected=content_detected,
            content_confidence=content_confidence,
        )

        if result.detected:
            results["detected"] += 1

            if content_detected:
                results["content_only_detected"] += 1
            else:
                results["structural_boosted"] += 1
        elif content_detected:
            # Content said yes, ensemble said no
            results["content_overridden"] += 1

        if len(results["samples"]) < 5:
            results["samples"].append({
                "trace_id": trace.get("trace_id", "unknown"),
                "detected": result.detected,
                "content_detected": content_detected,
                "structural_score": result.structural_score,
                "calibrated_confidence": result.calibrated_confidence,
                "explanation": result.explanation,
            })

    results["detection_rate"] = (
        results["detected"] / results["total"] * 100
        if results["total"] > 0 else 0
    )

    return results


def evaluate_on_healthy_traces(
    healthy_traces: list[dict],
    failure_mode: str,
    content_detector: Callable[[dict], tuple[bool, float]],
) -> dict:
    """Evaluate false positive rate on healthy traces.

    Healthy traces should NOT be detected as failures.
    This helps calibrate detection thresholds.
    """
    ensemble = EnsembleDetector()

    results = {
        "total_healthy": len(healthy_traces),
        "content_false_positives": 0,
        "ensemble_false_positives": 0,
        "false_positive_rate_content": 0,
        "false_positive_rate_ensemble": 0,
    }

    for trace in healthy_traces:
        content_detected, content_confidence = content_detector(trace)

        if content_detected:
            results["content_false_positives"] += 1

        result = ensemble.detect(
            trace=trace,
            failure_mode=failure_mode,
            content_detected=content_detected,
            content_confidence=content_confidence,
        )

        if result.detected:
            results["ensemble_false_positives"] += 1

    if results["total_healthy"] > 0:
        results["false_positive_rate_content"] = (
            results["content_false_positives"] / results["total_healthy"] * 100
        )
        results["false_positive_rate_ensemble"] = (
            results["ensemble_false_positives"] / results["total_healthy"] * 100
        )

    return results
