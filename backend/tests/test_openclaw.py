"""Tests for OpenClaw integration: parser and webhook endpoint."""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.ingestion.openclaw_parser import (
    openclaw_parser,
    OpenClawSession,
    OpenClawEvent,
)


class TestOpenClawParser:
    """Tests for OpenClawParser parsing and state extraction."""

    def test_parse_session_basic(self):
        raw_data = {
            "session_id": "sess-123",
            "instance_id": "inst-456",
            "agent_name": "support-bot",
            "channel": "whatsapp",
            "inbox_type": "dm",
            "started_at": "2024-01-01T00:00:00Z",
            "finished_at": "2024-01-01T00:00:10Z",
            "status": "completed",
            "elevated_mode": False,
            "sandbox_enabled": True,
            "events": [
                {
                    "type": "message.received",
                    "timestamp": "2024-01-01T00:00:01Z",
                    "agent_name": "support-bot",
                    "channel": "whatsapp",
                    "data": {"text": "Hello"},
                },
                {
                    "type": "agent.turn",
                    "timestamp": "2024-01-01T00:00:02Z",
                    "agent_name": "support-bot",
                    "data": {"response": "Hi, how can I help?"},
                    "token_count": 50,
                },
            ],
        }

        session = openclaw_parser.parse_session(raw_data)

        assert session.session_id == "sess-123"
        assert session.instance_id == "inst-456"
        assert session.agent_name == "support-bot"
        assert session.channel == "whatsapp"
        assert session.status == "completed"
        assert session.elevated_mode is False
        assert session.sandbox_enabled is True
        assert len(session.events) == 2
        assert session.events[0].event_type == "message.received"
        assert session.events[1].event_type == "agent.turn"
        assert session.events[1].token_count == 50

    def test_parse_to_states(self):
        now = datetime.utcnow()
        session = OpenClawSession(
            session_id="sess-123",
            instance_id="inst-456",
            agent_name="bot",
            channel="slack",
            inbox_type="dm",
            started_at=now,
            finished_at=now + timedelta(seconds=5),
            status="completed",
            events=[
                OpenClawEvent(
                    event_type="message.received",
                    timestamp=now,
                    agent_name="bot",
                    data={"text": "Hello"},
                ),
                OpenClawEvent(
                    event_type="agent.turn",
                    timestamp=now + timedelta(seconds=1),
                    agent_name="bot",
                    data={"response": "Hi"},
                    token_count=30,
                ),
                OpenClawEvent(
                    event_type="tool.call",
                    timestamp=now + timedelta(seconds=2),
                    agent_name="bot",
                    tool_name="search",
                    tool_input={"query": "test"},
                ),
            ],
        )

        states = openclaw_parser.parse_to_states(session, "tenant-123")

        assert len(states) == 3
        assert states[0].agent_id == "bot"
        assert states[0].sequence_num == 0
        assert states[1].sequence_num == 1
        assert states[1].token_count == 30
        assert states[2].sequence_num == 2

    def test_agent_event_detection(self):
        """Agent events should be flagged with is_agent_event=True."""
        now = datetime.utcnow()
        session = OpenClawSession(
            session_id="sess-1",
            instance_id="inst-1",
            agent_name="bot",
            channel="telegram",
            inbox_type="dm",
            started_at=now,
            finished_at=now,
            status="completed",
            events=[
                OpenClawEvent(
                    event_type="message.received", timestamp=now,
                ),
                OpenClawEvent(
                    event_type="agent.turn", timestamp=now,
                ),
                OpenClawEvent(
                    event_type="tool.call", timestamp=now,
                ),
                OpenClawEvent(
                    event_type="message.sent", timestamp=now,
                ),
            ],
        )

        states = openclaw_parser.parse_to_states(session, "tenant-1")

        assert states[0].is_agent_event is False  # message.received
        assert states[1].is_agent_event is True   # agent.turn
        assert states[2].is_agent_event is False  # tool.call
        assert states[3].is_agent_event is True   # message.sent

    def test_spawn_sessions_preserved(self):
        raw_data = {
            "session_id": "sess-1",
            "instance_id": "inst-1",
            "agent_name": "bot",
            "channel": "slack",
            "inbox_type": "dm",
            "started_at": "2024-01-01T00:00:00Z",
            "status": "completed",
            "spawned_sessions": ["sess-child-1", "sess-child-2"],
            "events": [],
        }

        session = openclaw_parser.parse_session(raw_data)
        assert session.spawned_sessions == ["sess-child-1", "sess-child-2"]


@pytest_asyncio.fixture
async def openclaw_webhook_client():
    """Async client for OpenClaw webhook tests with mocked DB."""
    from app.storage.database import get_db
    from app.core.auth import get_current_tenant

    mock_tenant = MagicMock()
    mock_tenant.id = uuid4()
    mock_tenant.name = "Test Tenant"

    mock_api_key = MagicMock()
    mock_api_key.key_prefix = "mao_testkey1"
    mock_api_key.key_hash = "hashed_key"
    mock_api_key.tenant_id = mock_tenant.id
    mock_api_key.revoked_at = None

    call_count = [0]

    def create_mock_result():
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            # API key lookup (verify_api_key_and_get_tenant step 1)
            mock_result.scalar_one_or_none.return_value = mock_api_key
        elif call_count[0] == 2:
            # Tenant lookup (verify_api_key_and_get_tenant step 2)
            mock_result.scalar_one_or_none.return_value = mock_tenant
        elif call_count[0] == 3:
            # set_tenant_context (verify_api_key_and_get_tenant step 3)
            return mock_result
        elif call_count[0] == 4:
            # OpenClawAgent lookup
            mock_result.scalar_one_or_none.return_value = None
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=lambda *a, **k: create_mock_result())
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    def override_get_db():
        return mock_db

    def override_get_tenant():
        return str(mock_tenant.id)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_tenant] = override_get_tenant

    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client, mock_db, mock_tenant
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_tenant, None)


class TestOpenClawWebhook:
    """Tests for POST /api/v1/openclaw/webhook."""

    @pytest.mark.asyncio
    async def test_webhook_creates_trace(self, openclaw_webhook_client):
        """OpenClaw webhook should create a trace successfully."""
        client, mock_db, mock_tenant = openclaw_webhook_client

        with patch('app.core.auth.verify_api_key', return_value=True), \
             patch('app.api.v1.openclaw.verify_webhook_if_configured', new_callable=AsyncMock):
            payload = {
                "session_id": "sess-123",
                "instance_id": "inst-456",
                "agent_name": "support-bot",
                "channel": "whatsapp",
                "inbox_type": "dm",
                "started_at": "2024-01-01T00:00:00Z",
                "finished_at": "2024-01-01T00:00:10Z",
                "status": "completed",
                "events": [
                    {
                        "type": "message.received",
                        "timestamp": "2024-01-01T00:00:01Z",
                        "data": {"text": "Hello"},
                    },
                    {
                        "type": "agent.turn",
                        "timestamp": "2024-01-01T00:00:02Z",
                        "data": {"response": "Hi"},
                    },
                ],
                "message_count": 2,
            }

            response = await client.post(
                "/api/v1/openclaw/webhook",
                json=payload,
                headers={"X-MAO-API-Key": "mao_testkey123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "trace_id" in data

    @pytest.mark.asyncio
    async def test_webhook_missing_api_key(self, openclaw_webhook_client):
        """Missing API key should return 422."""
        client, _, _ = openclaw_webhook_client

        payload = {
            "session_id": "sess-123",
            "instance_id": "inst-456",
            "agent_name": "bot",
            "channel": "slack",
            "started_at": "2024-01-01T00:00:00Z",
            "status": "completed",
            "events": [],
        }

        response = await client.post(
            "/api/v1/openclaw/webhook",
            json=payload,
        )

        assert response.status_code == 422
