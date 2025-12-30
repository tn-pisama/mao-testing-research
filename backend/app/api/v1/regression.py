"""Regression module API routes - Baseline management and drift detection."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_tenant
from app.regression import (
    baseline_store,
    model_fingerprinter,
    DriftDetector,
    DriftSeverity,
    alert_manager,
)

router = APIRouter(prefix="/regression", tags=["regression"])


# Response models
class BaselineEntryResponse(BaseModel):
    id: str
    prompt_hash: str
    prompt_text: str
    output_text: str
    model: str
    model_version: Optional[str]
    tokens_used: int
    latency_ms: int
    created_at: datetime
    tags: list[str]


class BaselineResponse(BaseModel):
    id: str
    name: str
    description: str
    entry_count: int
    model: str
    created_at: datetime
    updated_at: datetime
    last_tested: Optional[datetime] = None


class DriftAlertResponse(BaseModel):
    id: str
    severity: str
    drift_type: str
    prompt: str
    similarity: float
    detected_at: datetime
    baseline_id: str
    details: dict = Field(default_factory=dict)


class ModelFingerprintResponse(BaseModel):
    model: str
    version: str
    provider: str
    fingerprint_hash: str
    last_seen: datetime
    status: str
    change_detected: bool


class DriftSummaryResponse(BaseModel):
    total_alerts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    models_affected: list[str]
    recent_alerts: list[DriftAlertResponse]


# Request models
class CreateBaselineRequest(BaseModel):
    name: str
    description: str = ""
    model: str
    entries: list[dict] = Field(default_factory=list)


class AddEntryRequest(BaseModel):
    prompt: str
    output: str
    model: str
    model_version: Optional[str] = None
    tokens_used: int = 0
    latency_ms: int = 0
    tags: list[str] = Field(default_factory=list)


class TestBaselineRequest(BaseModel):
    baseline_id: str
    current_outputs: list[dict]  # [{prompt_hash, output}]


class CheckDriftRequest(BaseModel):
    baseline_id: str
    prompt: str
    current_output: str
    model: str


@router.get("/baselines", response_model=list[BaselineResponse])
async def list_baselines(
    limit: int = 20,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
):
    """List baselines for the tenant."""
    baselines = baseline_store.get_baselines_for_tenant(tenant_id)

    result = []
    for bl in baselines[offset:offset + limit]:
        result.append(BaselineResponse(
            id=bl.id,
            name=bl.name,
            description=bl.description,
            entry_count=len(bl.entries),
            model=bl.models_covered[0] if bl.models_covered else "unknown",
            created_at=bl.created_at,
            updated_at=bl.updated_at,
            last_tested=None,
        ))
    return result


@router.post("/baselines", response_model=BaselineResponse, status_code=status.HTTP_201_CREATED)
async def create_baseline(
    request: CreateBaselineRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Create a new baseline."""
    baseline = baseline_store.create_baseline(
        name=request.name,
        description=request.description,
        tenant_id=tenant_id,
    )

    # Add entries if provided
    for entry_data in request.entries:
        baseline_store.add_entry_to_baseline(
            baseline_id=baseline.id,
            prompt=entry_data.get("prompt", ""),
            output=entry_data.get("output", ""),
            model=request.model,
        )

    return BaselineResponse(
        id=baseline.id,
        name=baseline.name,
        description=baseline.description,
        entry_count=len(baseline.entries),
        model=request.model,
        created_at=baseline.created_at,
        updated_at=baseline.updated_at,
    )


@router.get("/baselines/{baseline_id}", response_model=BaselineResponse)
async def get_baseline(
    baseline_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Get a specific baseline."""
    baseline = baseline_store.get_baseline(baseline_id)

    if not baseline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline not found"
        )

    if baseline.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return BaselineResponse(
        id=baseline.id,
        name=baseline.name,
        description=baseline.description,
        entry_count=len(baseline.entries),
        model=baseline.models_covered[0] if baseline.models_covered else "unknown",
        created_at=baseline.created_at,
        updated_at=baseline.updated_at,
    )


@router.delete("/baselines/{baseline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_baseline(
    baseline_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Delete a baseline."""
    baseline = baseline_store.get_baseline(baseline_id)

    if baseline and baseline.tenant_id == tenant_id:
        baseline_store.delete_baseline(baseline_id)


@router.post("/baselines/{baseline_id}/entries", response_model=BaselineEntryResponse)
async def add_entry(
    baseline_id: str,
    request: AddEntryRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Add an entry to a baseline."""
    baseline = baseline_store.get_baseline(baseline_id)

    if not baseline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline not found"
        )

    if baseline.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    entry = baseline_store.add_entry_to_baseline(
        baseline_id=baseline_id,
        prompt=request.prompt,
        output=request.output,
        model=request.model,
        model_version=request.model_version,
        tokens_used=request.tokens_used,
        latency_ms=request.latency_ms,
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add entry"
        )

    return BaselineEntryResponse(
        id=entry.id,
        prompt_hash=entry.prompt_hash,
        prompt_text=entry.prompt_text,
        output_text=entry.output_text,
        model=entry.model,
        model_version=entry.model_version,
        tokens_used=entry.tokens_used,
        latency_ms=entry.latency_ms,
        created_at=entry.created_at,
        tags=entry.tags,
    )


@router.get("/baselines/{baseline_id}/entries", response_model=list[BaselineEntryResponse])
async def list_entries(
    baseline_id: str,
    limit: int = 50,
    tenant_id: str = Depends(get_current_tenant),
):
    """List entries in a baseline."""
    baseline = baseline_store.get_baseline(baseline_id)

    if not baseline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline not found"
        )

    if baseline.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    entries = []
    for entry in baseline.entries[:limit]:
        entries.append(BaselineEntryResponse(
            id=entry.id,
            prompt_hash=entry.prompt_hash,
            prompt_text=entry.prompt_text,
            output_text=entry.output_text,
            model=entry.model,
            model_version=entry.model_version,
            tokens_used=entry.tokens_used,
            latency_ms=entry.latency_ms,
            created_at=entry.created_at,
            tags=entry.tags,
        ))
    return entries


@router.post("/baselines/{baseline_id}/test", response_model=DriftSummaryResponse)
async def test_baseline(
    baseline_id: str,
    request: TestBaselineRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Test current outputs against a baseline."""
    baseline = baseline_store.get_baseline(baseline_id)

    if not baseline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline not found"
        )

    if baseline.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    detector = DriftDetector()
    alerts: list[DriftAlertResponse] = []

    for output_data in request.current_outputs:
        prompt_hash = output_data.get("prompt_hash", "")
        current_output = output_data.get("output", "")

        # Find matching baseline entry
        for entry in baseline.entries:
            if entry.prompt_hash == prompt_hash:
                # Detect drift
                drift_result = detector.detect_semantic_drift(
                    original=entry.output_text,
                    current=current_output,
                )

                if drift_result.has_drift:
                    alerts.append(DriftAlertResponse(
                        id=f"alert-{len(alerts):03d}",
                        severity=drift_result.severity.value,
                        drift_type=drift_result.drift_type.value,
                        prompt=entry.prompt_text[:100],
                        similarity=drift_result.similarity,
                        detected_at=datetime.utcnow(),
                        baseline_id=baseline_id,
                        details=drift_result.details,
                    ))
                break

    return DriftSummaryResponse(
        total_alerts=len(alerts),
        critical_count=sum(1 for a in alerts if a.severity == "critical"),
        high_count=sum(1 for a in alerts if a.severity == "high"),
        medium_count=sum(1 for a in alerts if a.severity == "medium"),
        low_count=sum(1 for a in alerts if a.severity == "low"),
        models_affected=list(set(baseline.models_covered)),
        recent_alerts=alerts,
    )


@router.post("/drift/check", response_model=DriftAlertResponse)
async def check_drift(
    request: CheckDriftRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Check for drift on a single prompt/output pair."""
    baseline = baseline_store.get_baseline(request.baseline_id)

    if not baseline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline not found"
        )

    # Find the original entry
    entry = baseline.get_entry_by_prompt(request.prompt)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found in baseline"
        )

    detector = DriftDetector()
    drift_result = detector.detect_semantic_drift(
        original=entry.output_text,
        current=request.current_output,
    )

    return DriftAlertResponse(
        id=f"alert-{datetime.utcnow().timestamp():.0f}",
        severity=drift_result.severity.value,
        drift_type=drift_result.drift_type.value,
        prompt=request.prompt[:100],
        similarity=drift_result.similarity,
        detected_at=datetime.utcnow(),
        baseline_id=request.baseline_id,
        details={
            "model": request.model,
            "output_length": len(request.current_output),
            **drift_result.details,
        },
    )


@router.get("/alerts", response_model=list[DriftAlertResponse])
async def list_alerts(
    severity: Optional[str] = None,
    limit: int = 20,
    tenant_id: str = Depends(get_current_tenant),
):
    """List drift alerts."""
    alerts = alert_manager.get_alerts_for_tenant(tenant_id)

    result = []
    for alert in alerts:
        drift_type = "semantic"
        prompt = ""
        similarity = 0.0

        if alert.drift_results:
            drift = alert.drift_results[0]
            drift_type = drift.drift_type.value
            similarity = drift.similarity

        alert_response = DriftAlertResponse(
            id=alert.id,
            severity=alert.priority.value.replace("p", ""),
            drift_type=drift_type,
            prompt=prompt,
            similarity=similarity,
            detected_at=alert.created_at,
            baseline_id=alert.metadata.get("baseline_id", ""),
            details=alert.metadata,
        )

        if severity is None or alert_response.severity == severity:
            result.append(alert_response)

    return result[:limit]


@router.get("/fingerprints", response_model=list[ModelFingerprintResponse])
async def list_fingerprints(
    tenant_id: str = Depends(get_current_tenant),
):
    """List model fingerprints."""
    fingerprints = []

    for model_id, fp in model_fingerprinter.known_fingerprints.items():
        # Check version history for changes
        change_detected = False
        for hist_model, hist_version, hist_time in model_fingerprinter.version_history:
            if hist_model == model_id:
                change_detected = True
                break

        status = "stable"
        if fp.is_deprecated:
            status = "deprecated"
        elif change_detected:
            status = "updated"

        fingerprints.append(ModelFingerprintResponse(
            model=fp.model_id,
            version=fp.version or "latest",
            provider=fp.provider,
            fingerprint_hash=fp.fingerprint_hash,
            last_seen=fp.detected_at,
            status=status,
            change_detected=change_detected,
        ))

    # If no fingerprints tracked, return common models
    if not fingerprints:
        now = datetime.utcnow()
        common_models = [
            ("gpt-4o", "2024-11-20", "openai"),
            ("claude-3-5-sonnet", "20241022", "anthropic"),
            ("gemini-1.5-pro", "002", "google"),
        ]
        for model, version, provider in common_models:
            fp = model_fingerprinter.fingerprint(f"{model}-{version}" if version else model)
            fingerprints.append(ModelFingerprintResponse(
                model=fp.model_id,
                version=fp.version or version,
                provider=fp.provider,
                fingerprint_hash=fp.fingerprint_hash,
                last_seen=fp.detected_at,
                status="stable",
                change_detected=False,
            ))

    return fingerprints


@router.post("/fingerprints/refresh")
async def refresh_fingerprints(
    tenant_id: str = Depends(get_current_tenant),
):
    """Refresh model fingerprints by probing models."""
    models_to_probe = ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]

    # Queue fingerprinting for each model
    for model in models_to_probe:
        model_fingerprinter.fingerprint(model)

    return {
        "status": "refreshing",
        "models_queued": models_to_probe,
        "estimated_time_seconds": 30,
    }
