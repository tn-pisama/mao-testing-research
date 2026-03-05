"""Diagnostics endpoints for detector health and readiness."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends

from app.core.auth import get_current_tenant

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _confidence_tier(confidence_pct: float) -> str:
    """Map 0-1 confidence to tier label."""
    if confidence_pct >= 0.80:
        return "HIGH"
    elif confidence_pct >= 0.60:
        return "LIKELY"
    elif confidence_pct >= 0.40:
        return "POSSIBLE"
    return "LOW"


@router.get("/detector-status")
async def get_detector_status(tenant_id: str = Depends(get_current_tenant)) -> Dict[str, Any]:
    """Return detector health and readiness based on latest calibration.

    Provides production/beta/experimental/failing status for each detector,
    along with F1 score and sample counts.
    """
    from app.detection_enterprise.calibrate import (
        READINESS_CRITERIA,
        DETECTOR_METADATA,
        _compute_readiness,
        calibrate_all,
    )

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
