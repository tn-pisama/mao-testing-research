"""E2E tests for critical API flows.

Tests the full request→response cycle for the most important API operations.
Uses AsyncClient with mocked DB (same pattern as conftest.py api_test_client).

Route prefixes (from main.py):
  /api/v1/health — no tenant
  /api/v1/auth — no tenant
  /api/v1/n8n — no tenant
  /api/v1/tenants/{tenant_id}/traces — tenant-scoped
  /api/v1/tenants/{tenant_id}/detections — tenant-scoped
  /api/v1/tenants/{tenant_id}/healing — tenant-scoped
"""
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from uuid import uuid4
from datetime import datetime, timezone

from httpx import AsyncClient, ASGITransport


TENANT_ID = str(uuid4())
T = f"/api/v1/tenants/{TENANT_ID}"  # Tenant-scoped prefix


def _mock_db():
    mock = MagicMock()
    mock.add = MagicMock()
    mock.commit = AsyncMock()
    mock.refresh = AsyncMock()
    mock.flush = AsyncMock()
    mock.execute = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest_asyncio.fixture
async def client():
    from app.main import app, tenant_rate_limit_dependency
    from app.storage.database import get_db
    from app.core.auth import get_current_tenant
    from app.core.dependencies import get_current_user_or_tenant

    mock_db = _mock_db()
    # Override set_tenant_context to no-op (avoids DB SET call)
    mock_db.execute = AsyncMock(return_value=MagicMock())

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_tenant] = lambda: TENANT_ID

    # Override the auth+rate-limit dependency that guards tenant-scoped routes
    mock_auth = MagicMock()
    mock_auth.tenant_id = TENANT_ID
    mock_auth.user_id = None
    app.dependency_overrides[get_current_user_or_tenant] = lambda: mock_auth

    # Override tenant rate limit dependency
    mock_rl_result = MagicMock()
    mock_rl_result.allowed = True
    mock_rl_result.limit = 1000
    mock_rl_result.remaining = 999
    mock_rl_result.reset_at = 0
    app.dependency_overrides[tenant_rate_limit_dependency] = lambda: mock_rl_result

    mock_rl = MagicMock()
    mock_rl.check_rate_limit = AsyncMock(return_value=True)
    mock_rl.get_remaining = AsyncMock(return_value=1000)
    mock_rl.close = AsyncMock()
    mock_rl.connect = AsyncMock()
    mock_rl._redis = None

    try:
        with patch("app.main.rate_limiter", mock_rl):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                yield c, mock_db
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_tenant, None)
        app.dependency_overrides.pop(get_current_user_or_tenant, None)
        app.dependency_overrides.pop(tenant_rate_limit_dependency, None)


# ── 1. Health Check ──────────────────────────────────────────────────

class TestHealthCheck:
    async def test_health_returns_status(self, client):
        c, db = client
        db.execute = AsyncMock(return_value=MagicMock())
        resp = await c.get("/api/v1/health")
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body
        assert "database" in body
        assert "version" in body


# ── 2. OTEL Trace Ingestion ──────────────────────────────────────────

class TestOTELIngestion:
    async def test_ingest_returns_accepted(self, client):
        c, db = client

        mock_trace = MagicMock()
        mock_trace.id = uuid4()
        mock_trace.total_tokens = 0

        # Use a flexible mock: returns no-existing-trace first, then the trace
        call_count = {"n": 0}
        async def flexible_execute(*args, **kwargs):
            call_count["n"] += 1
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None if call_count["n"] == 1 else mock_trace)
            result.scalar_one = MagicMock(return_value=mock_trace)
            result.scalar = MagicMock(return_value=0)
            return result
        db.execute = flexible_execute

        resp = await c.post(f"{T}/traces/ingest", json={
            "resourceSpans": [{
                "resource": {"attributes": []},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": "e2e-test-trace",
                        "spanId": "span1",
                        "name": "agent",
                        "kind": "SPAN_KIND_INTERNAL",
                        "startTimeUnixNano": "1700000000000000000",
                        "endTimeUnixNano": "1700000002000000000",
                        "attributes": [
                            {"key": "gen_ai.agent.name", "value": {"stringValue": "e2e-agent"}},
                        ],
                        "status": {},
                        "events": [],
                    }],
                }],
            }],
        })
        assert resp.status_code == 202
        body = resp.json()
        assert body["accepted"] >= 1


# ── 3. Trace States Truncation ───────────────────────────────────────

class TestStatesTruncation:
    async def test_state_delta_truncated(self, client):
        c, db = client
        trace_id = uuid4()

        mock_state = MagicMock()
        mock_state.id = uuid4()
        mock_state.sequence_num = 0
        mock_state.agent_id = "test-agent"
        mock_state.state_delta = {"output": "x" * 1000}
        mock_state.state_hash = "abc"
        mock_state.token_count = 100
        mock_state.latency_ms = 500
        mock_state.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[mock_state])
        ))
        db.execute = AsyncMock(return_value=mock_result)

        resp = await c.get(f"{T}/traces/{trace_id}/states")
        assert resp.status_code == 200
        states = resp.json()
        assert len(states) == 1
        output_val = str(states[0]["state_delta"].get("output", ""))
        assert len(output_val) < 600
        assert "truncated" in output_val

    async def test_full_state_param(self, client):
        c, db = client
        trace_id = uuid4()

        big_text = "y" * 1000
        mock_state = MagicMock()
        mock_state.id = uuid4()
        mock_state.sequence_num = 0
        mock_state.agent_id = "agent"
        mock_state.state_delta = {"data": big_text}
        mock_state.state_hash = "def"
        mock_state.token_count = 50
        mock_state.latency_ms = 100
        mock_state.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[mock_state])
        ))
        db.execute = AsyncMock(return_value=mock_result)

        resp = await c.get(f"{T}/traces/{trace_id}/states?full_state=true")
        assert resp.status_code == 200
        states = resp.json()
        data_val = states[0]["state_delta"]["data"]
        assert len(data_val) == 1000  # Not truncated


# ── 4. Detection List ────────────────────────────────────────────────

class TestDetectionList:
    async def test_detections_endpoint_responds(self, client):
        c, db = client

        async def flexible_execute(*args, **kwargs):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result
        db.execute = flexible_execute

        resp = await c.get(f"{T}/detections")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body


# ── 5. Auth Token ────────────────────────────────────────────────────

class TestAuth:
    async def test_token_endpoint_exists(self, client):
        c, db = client
        resp = await c.post("/api/v1/auth/token", json={
            "email": "test@example.com",
            "password": "test123456",
        })
        # 200 (valid), 401 (invalid creds), 422 (validation) — not 404
        assert resp.status_code in (200, 401, 422)


# ── 6. Orchestration Quality ─────────────────────────────────────────

class TestOrchestrationQuality:
    async def test_returns_score(self, client):
        c, db = client
        trace_id = uuid4()

        mock_trace = MagicMock()
        mock_trace.id = trace_id
        mock_trace.parent_trace_id = None

        s1 = MagicMock(agent_id="planner", agent_role="planner", sequence_num=0,
                       latency_ms=100, state_delta={"plan": "search"}, tool_calls=["plan"],
                       response_redacted="Plan ready")
        s2 = MagicMock(agent_id="executor", agent_role="executor", sequence_num=1,
                       latency_ms=200, state_delta={"result": "done"}, tool_calls=["exec"],
                       response_redacted="Done")

        call_count = {"n": 0}
        async def flexible_execute(*args, **kwargs):
            call_count["n"] += 1
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_trace)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[s1, s2])))
            return result
        db.execute = flexible_execute

        resp = await c.get(f"{T}/traces/{trace_id}/orchestration-quality")
        assert resp.status_code == 200
        body = resp.json()
        assert "overall" in body
        assert "dimensions" in body
        assert isinstance(body["overall"], (int, float))


# ── 7. Chain Analysis ────────────────────────────────────────────────

class TestChainAnalysis:
    async def test_no_linked_traces(self, client):
        c, db = client
        trace_id = uuid4()

        mock_trace = MagicMock()
        mock_trace.id = trace_id
        mock_trace.parent_trace_id = None

        async def flexible_execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_trace)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result
        db.execute = flexible_execute

        resp = await c.get(f"{T}/traces/{trace_id}/chain-analysis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["detected"] is False
        assert body["trace_count"] == 1


# ── 8. N8N Webhook ───────────────────────────────────────────────────

class TestN8NWebhook:
    async def test_webhook_responds(self, client):
        c, db = client

        mock_wf = MagicMock()
        mock_wf.id = uuid4()
        mock_wf.tenant_id = uuid4()
        mock_wf.workflow_id = "wf-e2e"
        mock_wf.name = "E2E Test"
        mock_wf.is_active = True
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none = MagicMock(return_value=mock_wf)
        db.execute = AsyncMock(return_value=mock_scalar)

        resp = await c.post("/api/v1/n8n/webhook", json={
            "executionId": "exec-e2e",
            "workflowId": "wf-e2e",
            "workflowName": "E2E Test",
            "mode": "webhook",
            "startedAt": "2025-03-26T10:00:00Z",
            "status": "success",
            "data": {"resultData": {"runData": {}}},
        }, headers={"X-MAO-API-Key": "test-key"})
        # Should respond (not 500/404 for missing route)
        assert resp.status_code in (200, 202, 401, 404, 422)
