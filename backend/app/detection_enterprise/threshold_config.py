"""Detection threshold configuration — the bridge between calibration and runtime.

Stores and retrieves optimal confidence thresholds per detector type.
Auto-updated by the calibration pipeline, read by the detection API.

Follows harness engineering principles: calibrate → measure → auto-correct.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD_PATH = Path(__file__).parent.parent.parent / "data" / "thresholds.json"

# Fallback thresholds if no calibration has been run
FACTORY_DEFAULTS: Dict[str, float] = {
    "loop": 0.5,
    "persona_drift": 0.5,
    "hallucination": 0.5,
    "injection": 0.5,
    "overflow": 0.5,
    "corruption": 0.5,
    "coordination": 0.5,
    "communication": 0.5,
    "context": 0.5,
    "grounding": 0.5,
    "retrieval_quality": 0.5,
    "completion": 0.5,
    "derailment": 0.5,
    "specification": 0.5,
    "decomposition": 0.5,
    "withholding": 0.5,
    "workflow": 0.5,
}


class ThresholdConfig:
    """Manages detection thresholds — auto-updated by calibration."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_THRESHOLD_PATH
        self._thresholds: Dict[str, float] = {}
        self._metadata: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load thresholds from JSON file, falling back to factory defaults."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    data = json.load(f)
                self._thresholds = data.get("thresholds", {})
                self._metadata = data.get("metadata", {})
                logger.info(
                    "Loaded %d thresholds from %s (calibrated: %s)",
                    len(self._thresholds),
                    self.path,
                    self._metadata.get("calibrated_at", "unknown"),
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load thresholds from %s: %s", self.path, exc)
                self._thresholds = dict(FACTORY_DEFAULTS)
        else:
            self._thresholds = dict(FACTORY_DEFAULTS)
            logger.info("No threshold file found, using factory defaults")

    def get(self, detection_type: str, default: Optional[float] = None) -> float:
        """Get the confidence threshold for a detection type.

        Args:
            detection_type: The detector type key (e.g., "loop", "hallucination").
            default: Fallback if no threshold found. Defaults to 0.5.

        Returns:
            The confidence threshold (0.0–1.0).
        """
        if default is None:
            default = FACTORY_DEFAULTS.get(detection_type, 0.5)
        return self._thresholds.get(detection_type, default)

    def get_all(self) -> Dict[str, float]:
        """Return all thresholds as a dict."""
        result = dict(FACTORY_DEFAULTS)
        result.update(self._thresholds)
        return result

    def update_from_calibration(self, report: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Update thresholds from a calibrate_all() report.

        Only updates a threshold if the calibrated F1 is above a minimum
        floor (0.30). This prevents obviously broken detectors from
        poisoning the threshold config.

        Args:
            report: The dict returned by calibrate_all().

        Returns:
            Dict of changes: {detector_type: {"old": float, "new": float, "f1": float}}
        """
        MIN_F1_FOR_UPDATE = 0.30
        changes = {}
        results = report.get("results", {})

        for dtype, metrics in results.items():
            f1 = metrics.get("f1", 0.0)
            new_threshold = metrics.get("optimal_threshold", 0.5)

            if f1 < MIN_F1_FOR_UPDATE:
                logger.warning(
                    "Skipping threshold update for %s: F1=%.4f below floor %.2f",
                    dtype, f1, MIN_F1_FOR_UPDATE,
                )
                continue

            old_threshold = self._thresholds.get(dtype, FACTORY_DEFAULTS.get(dtype, 0.5))
            if abs(new_threshold - old_threshold) > 0.001:
                changes[dtype] = {
                    "old": old_threshold,
                    "new": new_threshold,
                    "f1": f1,
                }
            self._thresholds[dtype] = new_threshold

        self._metadata = {
            "calibrated_at": report.get("calibrated_at", ""),
            "detector_count": report.get("detector_count", 0),
            "skipped": report.get("skipped", []),
        }

        return changes

    def save(self) -> None:
        """Persist thresholds to JSON file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "thresholds": self._thresholds,
            "metadata": self._metadata,
        }
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Thresholds saved to %s", self.path)

    @property
    def calibrated_at(self) -> Optional[str]:
        """When the thresholds were last calibrated."""
        return self._metadata.get("calibrated_at")

    def summary(self) -> str:
        """Human-readable threshold summary."""
        lines = ["Detection Thresholds:"]
        for dtype, threshold in sorted(self.get_all().items()):
            source = "calibrated" if dtype in self._thresholds else "default"
            lines.append(f"  {dtype}: {threshold:.2f} ({source})")
        if self.calibrated_at:
            lines.append(f"\nLast calibrated: {self.calibrated_at}")
        return "\n".join(lines)
