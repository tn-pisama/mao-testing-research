"""Tests for onboarding API endpoints."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_tenant():
    tenant = MagicMock()
    tenant.id = uuid4()
    tenant.name = "Test Tenant"
    return tenant


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest_asyncio.fixture
async def tenant_client(mock_db, mock_tenant):
    """Async client with mocked auth + DB for tenant-scoped endpoints."""
    from app.main import app, tenant_rate_limit_dependency
    from app.storage.database import get_db
    from app.core.auth import get_current_tenant
    from app.core.rate_limit import RateLimitResult
    import time

    tenant_id = str(mock_tenant.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_tenant] = lambda: tenant_id
    app.dependency_overrides[tenant_rate_limit_dependency] = lambda: RateLimitResult(
        allowed=True, limit=1000, remaining=999, reset_at=int(time.time()) + 60
    )

    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield client, mock_db, mock_tenant
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_tenant, None)
        app.dependency_overrides.pop(tenant_rate_limit_dependency, None)


@pytest.mark.asyncio
async def test_onboarding_status_no_traces(tenant_client):
    """GET /onboarding/status returns has_traces=False when no traces exist."""
    client, mock_db, mock_tenant = tenant_client
    tenant_id = str(mock_tenant.id)

    # Mock: count returns 0, detection count returns 0
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    mock_db.execute = AsyncMock(return_value=count_result)

    resp = await client.get(f"/api/v1/tenants/{tenant_id}/onboarding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_traces"] is False
    assert data["trace_count"] == 0
    assert data["first_trace_id"] is None


@pytest.mark.asyncio
async def test_onboarding_status_with_traces(tenant_client):
    """GET /onboarding/status returns trace info when traces exist."""
    client, mock_db, mock_tenant = tenant_client
    tenant_id = str(mock_tenant.id)

    trace_id = uuid4()
    trace_time = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)

    call_count = [0]

    def make_result(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # Count traces
            result.scalar.return_value = 3
        elif call_count[0] == 2:
            # First trace row
            row = MagicMock()
            row.__getitem__ = lambda self, idx: [trace_id, trace_time][idx]
            result.first.return_value = row
        elif call_count[0] == 3:
            # Detection count
            result.scalar.return_value = 0
        return result

    mock_db.execute = AsyncMock(side_effect=make_result)

    resp = await client.get(f"/api/v1/tenants/{tenant_id}/onboarding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_traces"] is True
    assert data["trace_count"] == 3
    assert data["first_trace_id"] == str(trace_id)


@pytest.mark.asyncio
async def test_run_detection_valid_trace(tenant_client):
    """POST /onboarding/run-detection returns detections for a valid trace."""
    client, mock_db, mock_tenant = tenant_client
    tenant_id = str(mock_tenant.id)
    trace_id = str(uuid4())

    call_count = [0]

    def make_result(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # Trace lookup
            trace = MagicMock()
            trace.id = trace_id
            trace.tenant_id = tenant_id
            result.scalar_one_or_none.return_value = trace
        elif call_count[0] == 2:
            # Detections
            detection = MagicMock()
            detection.id = uuid4()
            detection.detection_type = "loop"
            detection.confidence = 85
            detection.description = "Loop detected"
            result.scalars.return_value.all.return_value = [detection]
        return result

    mock_db.execute = AsyncMock(side_effect=make_result)

    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/onboarding/run-detection",
        json={"trace_id": trace_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["types"] == ["loop"]
    assert data["highest_confidence"] == 85


@pytest.mark.asyncio
async def test_run_detection_missing_trace(tenant_client):
    """POST /onboarding/run-detection returns 404 for nonexistent trace."""
    client, mock_db, mock_tenant = tenant_client
    tenant_id = str(mock_tenant.id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/onboarding/run-detection",
        json={"trace_id": str(uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_detection_missing_body(tenant_client):
    """POST /onboarding/run-detection with empty body returns 422."""
    client, mock_db, mock_tenant = tenant_client
    tenant_id = str(mock_tenant.id)

    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/onboarding/run-detection",
        json={},
    )
    assert resp.status_code == 422
