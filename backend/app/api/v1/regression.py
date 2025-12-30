"""Regression module API routes - Baseline management and drift detection."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_tenant
from app.regression import (
    BaselineStore,
    Baseline,
    BaselineEntry,
    ModelFingerprint,
    model_fingerprinter,
    DriftDetector,
    DriftResult,
    DriftSeverity,
    RegressionAlert,
    AlertType,
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


# In-memory storage (replace with DB in production)
_baselines: dict[str, dict] = {}
_alerts: list[dict] = []


@router.get("/baselines", response_model=list[BaselineResponse])
async def list_baselines(
    limit: int = 20,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
):
    """List baselines for the tenant."""
    # Return demo baselines
    baselines = [
        BaselineResponse(
            id="bl-001",
            name="Production Prompts v2.1",
            description="Main production prompt baseline",
            entry_count=47,
            model="gpt-4o-2024-08-06",
            created_at=datetime(2024, 12, 15),
            updated_at=datetime(2024, 12, 28),
            last_tested=datetime(2024, 12, 29),
        ),
        BaselineResponse(
            id="bl-002",
            name="Customer Service Prompts",
            description="Customer support agent prompts",
            entry_count=23,
            model="claude-3-5-sonnet-20241022",
            created_at=datetime(2024, 12, 10),
            updated_at=datetime(2024, 12, 25),
            last_tested=datetime(2024, 12, 28),
        ),
        BaselineResponse(
            id="bl-003",
            name="Code Review Agent",
            description="Code analysis prompts",
            entry_count=31,
            model="gpt-4o",
            created_at=datetime(2024, 12, 5),
            updated_at=datetime(2024, 12, 20),
            last_tested=datetime(2024, 12, 27),
        ),
    ]
    return baselines[offset:offset + limit]


@router.post("/baselines", response_model=BaselineResponse, status_code=status.HTTP_201_CREATED)
async def create_baseline(
    request: CreateBaselineRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Create a new baseline."""
    import uuid

    baseline_id = f"bl-{str(uuid.uuid4())[:8]}"
    now = datetime.utcnow()

    baseline = BaselineResponse(
        id=baseline_id,
        name=request.name,
        description=request.description,
        entry_count=len(request.entries),
        model=request.model,
        created_at=now,
        updated_at=now,
    )

    _baselines[baseline_id] = baseline.model_dump()

    return baseline


@router.get("/baselines/{baseline_id}", response_model=BaselineResponse)
async def get_baseline(
    baseline_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Get a specific baseline."""
    if baseline_id in _baselines:
        return BaselineResponse(**_baselines[baseline_id])

    # Return demo baseline
    return BaselineResponse(
        id=baseline_id,
        name=f"Baseline {baseline_id}",
        description="Demo baseline",
        entry_count=25,
        model="gpt-4o",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.delete("/baselines/{baseline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_baseline(
    baseline_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Delete a baseline."""
    if baseline_id in _baselines:
        del _baselines[baseline_id]


@router.post("/baselines/{baseline_id}/entries", response_model=BaselineEntryResponse)
async def add_entry(
    baseline_id: str,
    request: AddEntryRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Add an entry to a baseline."""
    import hashlib
    import uuid

    entry = BaselineEntryResponse(
        id=str(uuid.uuid4())[:8],
        prompt_hash=hashlib.sha256(request.prompt.encode()).hexdigest()[:32],
        prompt_text=request.prompt,
        output_text=request.output,
        model=request.model,
        model_version=request.model_version,
        tokens_used=request.tokens_used,
        latency_ms=request.latency_ms,
        created_at=datetime.utcnow(),
        tags=request.tags,
    )

    return entry


@router.get("/baselines/{baseline_id}/entries", response_model=list[BaselineEntryResponse])
async def list_entries(
    baseline_id: str,
    limit: int = 50,
    tenant_id: str = Depends(get_current_tenant),
):
    """List entries in a baseline."""
    # Return demo entries
    entries = [
        BaselineEntryResponse(
            id=f"entry-{i:03d}",
            prompt_hash=f"hash{i:06d}",
            prompt_text=f"Sample prompt {i}",
            output_text=f"Expected output {i}",
            model="gpt-4o",
            model_version="2024-08-06",
            tokens_used=150 + i * 10,
            latency_ms=200 + i * 5,
            created_at=datetime.utcnow(),
            tags=["production"],
        )
        for i in range(1, min(limit + 1, 11))
    ]
    return entries


@router.post("/baselines/{baseline_id}/test", response_model=DriftSummaryResponse)
async def test_baseline(
    baseline_id: str,
    request: TestBaselineRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Test current outputs against a baseline."""
    detector = DriftDetector()

    # Simulate drift detection
    alerts = [
        DriftAlertResponse(
            id=f"alert-{i:03d}",
            severity=["critical", "high", "medium", "low"][i % 4],
            drift_type=["semantic", "performance", "format"][i % 3],
            prompt=f"Prompt that drifted {i}",
            similarity=0.75 + (i % 20) / 100,
            detected_at=datetime.utcnow(),
            baseline_id=baseline_id,
            details={"expected_tokens": 150, "actual_tokens": 180},
        )
        for i in range(5)
    ]

    return DriftSummaryResponse(
        total_alerts=len(alerts),
        critical_count=sum(1 for a in alerts if a.severity == "critical"),
        high_count=sum(1 for a in alerts if a.severity == "high"),
        medium_count=sum(1 for a in alerts if a.severity == "medium"),
        low_count=sum(1 for a in alerts if a.severity == "low"),
        models_affected=["gpt-4o"],
        recent_alerts=alerts,
    )


@router.post("/drift/check", response_model=DriftAlertResponse)
async def check_drift(
    request: CheckDriftRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Check for drift on a single prompt/output pair."""
    detector = DriftDetector()

    # Simulate drift check
    import uuid
    import random

    similarity = random.uniform(0.7, 1.0)
    severity = "low"
    if similarity < 0.8:
        severity = "critical"
    elif similarity < 0.85:
        severity = "high"
    elif similarity < 0.9:
        severity = "medium"

    return DriftAlertResponse(
        id=str(uuid.uuid4())[:8],
        severity=severity,
        drift_type="semantic",
        prompt=request.prompt[:100],
        similarity=similarity,
        detected_at=datetime.utcnow(),
        baseline_id=request.baseline_id,
        details={
            "model": request.model,
            "output_length": len(request.current_output),
        },
    )


@router.get("/alerts", response_model=list[DriftAlertResponse])
async def list_alerts(
    severity: Optional[str] = None,
    limit: int = 20,
    tenant_id: str = Depends(get_current_tenant),
):
    """List drift alerts."""
    alerts = [
        DriftAlertResponse(
            id=f"alert-{i:03d}",
            severity=["critical", "high", "medium", "low"][i % 4],
            drift_type=["semantic", "performance", "format"][i % 3],
            prompt=f"Prompt showing drift {i}",
            similarity=0.65 + (i % 30) / 100,
            detected_at=datetime.utcnow(),
            baseline_id=f"bl-00{(i % 3) + 1}",
            details={},
        )
        for i in range(10)
    ]

    if severity:
        alerts = [a for a in alerts if a.severity == severity]

    return alerts[:limit]


@router.get("/fingerprints", response_model=list[ModelFingerprintResponse])
async def list_fingerprints(
    tenant_id: str = Depends(get_current_tenant),
):
    """List model fingerprints."""
    fingerprints = [
        ModelFingerprintResponse(
            model="gpt-4o",
            version="2024-11-20",
            provider="openai",
            fingerprint_hash="a1b2c3d4e5f6",
            last_seen=datetime.utcnow(),
            status="stable",
            change_detected=False,
        ),
        ModelFingerprintResponse(
            model="gpt-4o",
            version="2024-08-06",
            provider="openai",
            fingerprint_hash="f6e5d4c3b2a1",
            last_seen=datetime(2024, 11, 15),
            status="deprecated",
            change_detected=True,
        ),
        ModelFingerprintResponse(
            model="claude-3-5-sonnet",
            version="20241022",
            provider="anthropic",
            fingerprint_hash="1a2b3c4d5e6f",
            last_seen=datetime.utcnow(),
            status="stable",
            change_detected=False,
        ),
        ModelFingerprintResponse(
            model="gemini-1.5-pro",
            version="002",
            provider="google",
            fingerprint_hash="6f5e4d3c2b1a",
            last_seen=datetime.utcnow(),
            status="updated",
            change_detected=True,
        ),
    ]
    return fingerprints


@router.post("/fingerprints/refresh")
async def refresh_fingerprints(
    tenant_id: str = Depends(get_current_tenant),
):
    """Refresh model fingerprints by probing models."""
    return {
        "status": "refreshing",
        "models_queued": ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"],
        "estimated_time_seconds": 30,
    }
