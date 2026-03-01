"""Diagnostics endpoints for detector health, readiness, and calibration monitoring.

Provides two tiers of diagnostics:
- ICP tier: In-memory calibration monitor that tracks detection metrics across
  diagnose runs without requiring enterprise features or database access.
- Enterprise tier: Full golden-dataset-based calibration (requires enterprise modules).
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# --------------------------------------------------------------------------- #
#  ICP-Tier Calibration Monitor (in-memory, no DB required)
# --------------------------------------------------------------------------- #

class _CalibrationMonitor:
    """In-memory monitor that tracks detection metrics from diagnose runs.

    Records confidence distributions, detection rates, and timing per
    failure mode, enabling lightweight drift detection without enterprise
    calibration infrastructure.

    Thread-safe via append-only semantics; list.append is atomic in CPython.
    """

    # Alert thresholds
    HIGH_FPR_THRESHOLD = 0.50  # Detectors firing >50% of runs
    LOW_CONFIDENCE_THRESHOLD = 0.40  # Average confidence below this
    MAX_WINDOW = 500  # Keep last N records per detector

    def __init__(self):
        self._records: Dict[str, list] = defaultdict(list)
        self._global_runs = 0
        self._started_at = datetime.now(timezone.utc)

    def record(self, failure_mode: str, detected: bool, confidence: float,
               severity: str, detection_time_ms: int = 0):
        """Record a single detection result for monitoring."""
        bucket = self._records[failure_mode]
        bucket.append({
            "detected": detected,
            "confidence": confidence,
            "severity": severity,
            "detection_time_ms": detection_time_ms,
            "timestamp": time.time(),
        })
        # Trim to window
        if len(bucket) > self.MAX_WINDOW:
            self._records[failure_mode] = bucket[-self.MAX_WINDOW:]

    def record_run(self):
        """Record that a full diagnose run completed."""
        self._global_runs += 1

    def get_stats(self) -> Dict[str, Any]:
        """Compute per-detector statistics from recorded observations."""
        stats: Dict[str, Any] = {}

        for mode, records in self._records.items():
            if not records:
                continue

            n = len(records)
            detected_count = sum(1 for r in records if r["detected"])
            detection_rate = detected_count / n if n > 0 else 0.0

            confidences = [r["confidence"] for r in records if r["detected"]]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Confidence distribution buckets
            buckets = {"high": 0, "likely": 0, "possible": 0, "low": 0}
            for c in confidences:
                if c >= 0.80:
                    buckets["high"] += 1
                elif c >= 0.60:
                    buckets["likely"] += 1
                elif c >= 0.40:
                    buckets["possible"] += 1
                else:
                    buckets["low"] += 1

            # Severity distribution
            severity_dist = defaultdict(int)
            for r in records:
                if r["detected"]:
                    severity_dist[r["severity"]] += 1

            # Timing
            times = [r["detection_time_ms"] for r in records if r["detection_time_ms"] > 0]
            avg_time_ms = sum(times) / len(times) if times else 0

            # Alerts
            alerts = []
            if detection_rate > self.HIGH_FPR_THRESHOLD:
                alerts.append({
                    "type": "high_detection_rate",
                    "message": f"{mode} fires {detection_rate:.0%} of the time — possible false positive issue",
                    "severity": "warning",
                })
            if avg_confidence > 0 and avg_confidence < self.LOW_CONFIDENCE_THRESHOLD:
                alerts.append({
                    "type": "low_avg_confidence",
                    "message": f"{mode} avg confidence {avg_confidence:.2f} — detector may be poorly calibrated",
                    "severity": "warning",
                })

            stats[mode] = {
                "total_observations": n,
                "detected_count": detected_count,
                "detection_rate": round(detection_rate, 4),
                "avg_confidence": round(avg_confidence, 4),
                "confidence_distribution": buckets,
                "severity_distribution": dict(severity_dist),
                "avg_detection_time_ms": round(avg_time_ms, 1),
                "alerts": alerts,
            }

        return stats

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts across detectors."""
        alerts = []
        stats = self.get_stats()
        for mode, s in stats.items():
            for alert in s.get("alerts", []):
                alerts.append({**alert, "detector": mode})
        return alerts

    def get_summary(self) -> Dict[str, Any]:
        """Get overall monitoring summary."""
        stats = self.get_stats()
        total_detectors = len(stats)
        detectors_with_alerts = sum(1 for s in stats.values() if s["alerts"])
        total_observations = sum(s["total_observations"] for s in stats.values())

        return {
            "total_detectors_observed": total_detectors,
            "total_observations": total_observations,
            "total_diagnose_runs": self._global_runs,
            "detectors_with_alerts": detectors_with_alerts,
            "monitoring_since": self._started_at.isoformat(),
            "alert_count": sum(len(s["alerts"]) for s in stats.values()),
        }


# Singleton monitor instance
calibration_monitor = _CalibrationMonitor()


def _confidence_tier(confidence_pct: float) -> str:
    """Map 0-1 confidence to tier label."""
    if confidence_pct >= 0.80:
        return "HIGH"
    elif confidence_pct >= 0.60:
        return "LIKELY"
    elif confidence_pct >= 0.40:
        return "POSSIBLE"
    return "LOW"


# --------------------------------------------------------------------------- #
#  ICP-Tier Endpoints (always available)
# --------------------------------------------------------------------------- #

@router.get("/monitor")
async def get_calibration_monitor() -> Dict[str, Any]:
    """ICP-tier detector calibration monitor.

    Returns real-time monitoring data from recent diagnose runs:
    - Per-detector detection rates and confidence distributions
    - Drift alerts (high FPR, low confidence)
    - Overall monitoring summary

    No enterprise features or database required.
    """
    return {
        "summary": calibration_monitor.get_summary(),
        "detectors": calibration_monitor.get_stats(),
        "alerts": calibration_monitor.get_alerts(),
    }


@router.get("/monitor/alerts")
async def get_calibration_alerts() -> Dict[str, Any]:
    """Get active calibration alerts only.

    Returns detectors that may need threshold tuning based on
    observed detection patterns from recent diagnose runs.
    """
    alerts = calibration_monitor.get_alerts()
    return {
        "alert_count": len(alerts),
        "alerts": alerts,
    }


@router.get("/icp-detectors")
async def get_icp_detector_inventory() -> Dict[str, Any]:
    """List all ICP-tier detectors with their configuration.

    Returns the full inventory of turn-aware detectors available
    without enterprise features, including failure mode mapping
    and supported detection types.
    """
    from app.detection.turn_aware import _DETECTOR_MODULES

    # Group by failure mode
    detectors = []
    failure_mode_titles = {
        "F1": "Specification Mismatch",
        "F2": "Poor Task Decomposition",
        "F3": "Resource Misallocation",
        "F4": "Tool Provision Failure",
        "F5": "Flawed Workflow",
        "F6": "Task Derailment",
        "F7": "Context Neglect",
        "F8": "Information Withholding",
        "F9": "Role Usurpation",
        "F10": "Communication Breakdown",
        "F11": "Coordination Failure",
        "F12": "Output Validation Failure",
        "F13": "Quality Gate Bypass",
        "F14": "Completion Misjudgment",
        "F15": "Termination Awareness",
        "F16": "Reasoning-Action Mismatch",
        "F17": "Clarification Request Failure",
    }

    # Detector class → module mapping (skip functions like analyze_conversation_turns)
    for name, module_path in _DETECTOR_MODULES.items():
        if name.startswith("_") or not name[0].isupper():
            continue
        # Infer failure mode from known patterns
        fm = None
        if "Specification" in name:
            fm = "F1"
        elif "TaskDecomposition" in name:
            fm = "F2"
        elif "Resource" in name:
            fm = "F3"
        elif "Conversation" in name:
            fm = "F4"
        elif "Loop" in name and "Turn" in name:
            fm = "F5"
        elif "Derailment" in name:
            fm = "F6"
        elif "ContextNeglect" in name:
            fm = "F7"
        elif "Withholding" in name:
            fm = "F8"
        elif "Usurpation" in name:
            fm = "F9"
        elif "Communication" in name:
            fm = "F10"
        elif "Coordination" in name:
            fm = "F11"
        elif "OutputValidation" in name:
            fm = "F12"
        elif "QualityGate" in name:
            fm = "F13"
        elif "Completion" in name:
            fm = "F14"
        elif "Termination" in name:
            fm = "F15"
        elif "Reasoning" in name:
            fm = "F16"
        elif "Clarification" in name:
            fm = "F17"

        detectors.append({
            "name": name,
            "module": module_path,
            "failure_mode": fm,
            "failure_mode_title": failure_mode_titles.get(fm, "Unknown") if fm else None,
            "tier": "icp",
        })

    return {
        "tier": "icp",
        "total_detectors": len(detectors),
        "failure_modes_covered": len(set(d["failure_mode"] for d in detectors if d["failure_mode"])),
        "detectors": detectors,
    }


# --------------------------------------------------------------------------- #
#  Enterprise-Tier Endpoint (requires enterprise modules)
# --------------------------------------------------------------------------- #

@router.get("/detector-status")
async def get_detector_status() -> Dict[str, Any]:
    """Return detector health and readiness based on latest calibration.

    Provides production/beta/experimental/failing status for each detector,
    along with F1 score and sample counts.

    **Requires enterprise calibration modules.**
    """
    try:
        from app.detection_enterprise.calibrate import (
            READINESS_CRITERIA,
            DETECTOR_METADATA,
            _compute_readiness,
            calibrate_all,
        )
    except ImportError:
        return {
            "error": "Enterprise calibration modules not available",
            "hint": "Use /diagnostics/monitor for ICP-tier monitoring or /diagnostics/icp-detectors for detector inventory",
            "detectors": [],
            "summary": {},
        }

    # Run calibration (cached in practice, fast on golden dataset)
    report = calibrate_all()
    results = report.get("results", {})
    skipped = set(report.get("skipped", []))

    detectors: List[Dict[str, Any]] = []
    summary = {"production": 0, "beta": 0, "experimental": 0, "failing": 0, "untested": 0}

    for dtype_value, meta in DETECTOR_METADATA.items():
        if dtype_value in skipped or dtype_value not in results:
            summary["untested"] += 1
            detectors.append({
                "name": dtype_value,
                "readiness": "untested",
                "description": meta.get("description", ""),
                "enabled": False,
                "f1_score": None,
                "sample_count": 0,
            })
            continue

        cal = results[dtype_value]
        f1 = cal.get("f1", 0.0)
        precision = cal.get("precision", 0.0)
        sample_count = cal.get("sample_count", 0)
        readiness = _compute_readiness(f1, precision, sample_count)
        summary[readiness] += 1

        detectors.append({
            "name": dtype_value,
            "readiness": readiness,
            "description": meta.get("description", ""),
            "enabled": readiness != "failing",
            "f1_score": round(f1, 4),
            "precision": round(precision, 4),
            "recall": round(cal.get("recall", 0.0), 4),
            "sample_count": sample_count,
            "optimal_threshold": cal.get("optimal_threshold"),
        })

    return {
        "detectors": detectors,
        "summary": summary,
        "calibrated_at": report.get("calibrated_at"),
        "readiness_criteria": READINESS_CRITERIA,
    }
