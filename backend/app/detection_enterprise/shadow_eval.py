"""Shadow evaluation for runtime judge drift detection.

Periodically runs golden-dataset samples through the live detection pipeline
and compares results against known labels. Detects when production judge
accuracy drifts from calibration-time accuracy.

Inspired by Anthropic's harness design principle: "don't trust self-evaluation."
Applied to Pisama's own LLM judges — verify they maintain calibration quality.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Tier thresholds (mirrors calibrate.py TIER_GATES)
TIER_ACCURACY_THRESHOLDS = {
    "production": 0.70,
    "beta": 0.40,
    "experimental": 0.30,
}


@dataclass
class ShadowEvalResult:
    """Result of a single shadow evaluation run."""
    detector_type: str
    golden_entry_id: str
    expected_detected: bool
    actual_detected: bool
    expected_confidence_min: float
    expected_confidence_max: float
    actual_confidence: float
    match: bool  # Did the live result match the golden label?
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None


@dataclass
class DriftReport:
    """Aggregated drift report across recent shadow evaluations."""
    detector_type: str
    total_evaluations: int
    correct: int
    accuracy: float
    tier: str
    threshold: float
    drifted: bool  # accuracy < tier threshold
    recent_mismatches: List[ShadowEvalResult] = field(default_factory=list)


def pick_shadow_sample(
    golden_entries: List[Dict[str, Any]],
    detector_types: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Pick a random golden-dataset entry for shadow evaluation.

    Args:
        golden_entries: List of golden dataset entry dicts.
        detector_types: Optional filter — only pick from these detector types.

    Returns:
        A golden entry dict, or None if no suitable entries exist.
    """
    candidates = golden_entries
    if detector_types:
        candidates = [e for e in candidates if e.get("detection_type") in detector_types]

    # Prefer human-verified entries for higher-quality signal
    verified = [e for e in candidates if e.get("human_verified")]
    pool = verified if verified else candidates

    if not pool:
        return None

    return random.choice(pool)


def run_shadow_eval(
    entry: Dict[str, Any],
    runner_fn,
) -> ShadowEvalResult:
    """Run a single shadow evaluation against a golden-dataset entry.

    Args:
        entry: Golden dataset entry with input_data, expected_detected, etc.
        runner_fn: Callable(input_data) -> (detected: bool, confidence: float)

    Returns:
        ShadowEvalResult with match status.
    """
    entry_id = entry.get("id", entry.get("entry_key", "unknown"))
    detection_type = entry.get("detection_type", "unknown")
    expected = entry.get("expected_detected", False)
    conf_min = entry.get("expected_confidence_min", 0.0)
    conf_max = entry.get("expected_confidence_max", 1.0)

    try:
        detected, confidence = runner_fn(entry.get("input_data", {}))

        # Match = correct label AND confidence in expected range
        label_match = detected == expected
        confidence_in_range = conf_min <= confidence <= conf_max if detected else True
        match = label_match and confidence_in_range

        return ShadowEvalResult(
            detector_type=detection_type,
            golden_entry_id=entry_id,
            expected_detected=expected,
            actual_detected=detected,
            expected_confidence_min=conf_min,
            expected_confidence_max=conf_max,
            actual_confidence=confidence,
            match=match,
        )
    except Exception as exc:
        logger.warning("Shadow eval failed for %s/%s: %s", detection_type, entry_id, exc)
        return ShadowEvalResult(
            detector_type=detection_type,
            golden_entry_id=entry_id,
            expected_detected=expected,
            actual_detected=False,
            expected_confidence_min=conf_min,
            expected_confidence_max=conf_max,
            actual_confidence=0.0,
            match=False,
            error=str(exc),
        )


def compute_drift_report(
    results: List[ShadowEvalResult],
    detector_tier: str = "production",
) -> DriftReport:
    """Compute drift report from a list of shadow eval results.

    Args:
        results: Recent shadow eval results for a single detector type.
        detector_tier: The detector's calibration tier (production/beta/experimental).
    """
    if not results:
        return DriftReport(
            detector_type="unknown",
            total_evaluations=0,
            correct=0,
            accuracy=0.0,
            tier=detector_tier,
            threshold=TIER_ACCURACY_THRESHOLDS.get(detector_tier, 0.70),
            drifted=False,
        )

    detector_type = results[0].detector_type
    correct = sum(1 for r in results if r.match)
    total = len(results)
    accuracy = correct / total if total > 0 else 0.0
    threshold = TIER_ACCURACY_THRESHOLDS.get(detector_tier, 0.70)

    mismatches = [r for r in results if not r.match]

    return DriftReport(
        detector_type=detector_type,
        total_evaluations=total,
        correct=correct,
        accuracy=accuracy,
        tier=detector_tier,
        threshold=threshold,
        drifted=accuracy < threshold,
        recent_mismatches=mismatches[-5:],  # Keep last 5 for diagnostics
    )
