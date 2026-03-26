"""Tests for marketplace SNS webhook endpoint and signature verification."""

import json
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest_asyncio.fixture
async def mp_client(mock_db):
    """Async client for marketplace endpoints (no auth required)."""
    from app.main import app
    from app.storage.database import get_db
    from app.config import get_settings

    def override_get_db():
        return mock_db

    app.dependency_overrides[get_db] = override_get_db

    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    # Enable marketplace for tests
    mock_settings = MagicMock()
    mock_settings.aws_marketplace_enabled = True

    mock_config = MagicMock()
    mock_config.enabled = True
    mock_config.product_code = "test-product"

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter), \
             patch('app.api.v1.marketplace.get_marketplace_config', return_value=mock_config), \
             patch('app.api.v1.marketplace._verify_sns_signature', new_callable=AsyncMock, return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield client, mock_db
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_sns_confirmation_valid(mp_client):
    """SubscriptionConfirmation with valid AWS URL succeeds."""
    client, mock_db = mp_client

    with patch('app.api.v1.marketplace.httpx.AsyncClient') as MockClient:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        payload = {
            "Type": "SubscriptionConfirmation",
            "MessageId": "test-123",
            "SubscribeURL": "https://sns.us-east-1.amazonaws.com/confirm?token=abc",
            "TopicArn": "arn:aws:sns:us-east-1:123456789:test",
            "Timestamp": "2026-03-11T00:00:00Z",
        }

        resp = await client.post(
            "/api/v1/marketplace/webhook",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "x-amz-sns-message-type": "SubscriptionConfirmation",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_sns_confirmation_bad_url(mp_client):
    """SubscriptionConfirmation with non-AWS URL is rejected."""
    client, mock_db = mp_client

    payload = {
        "Type": "SubscriptionConfirmation",
        "MessageId": "test-123",
        "SubscribeURL": "https://evil.com/steal-data",
        "TopicArn": "arn:aws:sns:us-east-1:123456789:test",
        "Timestamp": "2026-03-11T00:00:00Z",
    }

    resp = await client.post(
        "/api/v1/marketplace/webhook",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "x-amz-sns-message-type": "SubscriptionConfirmation",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sns_notification_subscribe(mp_client):
    """Notification with subscribe-success action is processed."""
    client, mock_db = mp_client

    # Mock tenant lookup
    result = MagicMock()
    tenant = MagicMock()
    tenant.id = uuid4()
    result.scalar_one_or_none.return_value = tenant
    mock_db.execute = AsyncMock(return_value=result)

    payload = {
        "Type": "Notification",
        "MessageId": "test-456",
        "Message": json.dumps({
            "action": "subscribe-success",
            "customer-identifier": "CUST-001",
        }),
        "TopicArn": "arn:aws:sns:us-east-1:123456789:test",
        "Timestamp": "2026-03-11T00:00:00Z",
    }

    resp = await client.post(
        "/api/v1/marketplace/webhook",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "x-amz-sns-message-type": "Notification",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert "subscribe-success" in resp.json()["message"]


@pytest.mark.asyncio
async def test_sns_notification_unsubscribe(mp_client):
    """Notification with unsubscribe-success action is processed."""
    client, mock_db = mp_client

    result = MagicMock()
    tenant = MagicMock()
    tenant.id = uuid4()
    tenant.plan = "pro"
    result.scalar_one_or_none.return_value = tenant
    mock_db.execute = AsyncMock(return_value=result)

    payload = {
        "Type": "Notification",
        "MessageId": "test-789",
        "Message": json.dumps({
            "action": "unsubscribe-success",
            "customer-identifier": "CUST-002",
        }),
        "TopicArn": "arn:aws:sns:us-east-1:123456789:test",
        "Timestamp": "2026-03-11T00:00:00Z",
    }

    resp = await client.post(
        "/api/v1/marketplace/webhook",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "x-amz-sns-message-type": "Notification",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"


@pytest.mark.asyncio
async def test_sns_invalid_json(mp_client):
    """POST with non-JSON body returns 400."""
    client, mock_db = mp_client

    resp = await client.post(
        "/api/v1/marketplace/webhook",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sns_signature_failure():
    """Valid structure but failed signature verification returns 403."""
    from app.main import app
    from app.storage.database import get_db

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    mock_config = MagicMock()
    mock_config.enabled = True

    payload = {
        "Type": "Notification",
        "MessageId": "test-bad-sig",
        "Message": json.dumps({"action": "subscribe-success", "customer-identifier": "X"}),
        "TopicArn": "arn:aws:sns:us-east-1:123456789:test",
        "Timestamp": "2026-03-11T00:00:00Z",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
        "Signature": "badsignature==",
    }

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter), \
             patch('app.api.v1.marketplace.get_marketplace_config', return_value=mock_config), \
             patch('app.api.v1.marketplace._verify_sns_signature', new_callable=AsyncMock, return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/marketplace/webhook",
                    content=json.dumps(payload),
                    headers={
                        "Content-Type": "application/json",
                        "x-amz-sns-message-type": "Notification",
                    },
                )
                assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
