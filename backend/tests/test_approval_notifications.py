"""Tests for the approval notification system (Gap 4).

Tests webhook notifier, notification router approval flow,
and Slack payload formatting.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.notifications.webhook import WebhookNotifier, ApprovalPayload
from app.notifications.router import (
    NotificationRouter,
    NotifyConfig,
    create_notification_router,
)


# ---------------------------------------------------------------------------
# ApprovalPayload tests
# ---------------------------------------------------------------------------

class TestApprovalPayload:
    """Test approval payload construction and serialization."""

    def _make_payload(self, **overrides) -> ApprovalPayload:
        defaults = {
            "healing_id": "heal-123",
            "detection_id": "det-456",
            "fix_type": "retry_limit",
            "fix_title": "Add retry limit to prevent infinite loops",
            "fix_description": "Add a maximum retry limit of 5 iterations.",
            "risk_level": "MEDIUM",
            "workflow_name": "My Workflow",
            "approve_url": "https://app.example.com/healing?action=approve&id=heal-123",
            "reject_url": "https://app.example.com/healing?action=reject&id=heal-123",
            "dashboard_url": "https://app.example.com/healing",
        }
        defaults.update(overrides)
        return ApprovalPayload(**defaults)

    def test_to_dict_includes_all_fields(self):
        payload = self._make_payload()
        d = payload.to_dict()
        assert d["healing_id"] == "heal-123"
        assert d["detection_id"] == "det-456"
        assert d["fix_type"] == "retry_limit"
        assert d["risk_level"] == "MEDIUM"
        assert "timestamp" in d

    def test_to_slack_payload_has_blocks(self):
        payload = self._make_payload()
        slack = payload.to_slack_payload()
        assert "text" in slack
        assert "blocks" in slack
        assert len(slack["blocks"]) >= 3

    def test_to_slack_payload_has_action_buttons(self):
        payload = self._make_payload()
        slack = payload.to_slack_payload()
        action_blocks = [b for b in slack["blocks"] if b["type"] == "actions"]
        assert len(action_blocks) == 1
        buttons = action_blocks[0]["elements"]
        labels = [b["text"]["text"] for b in buttons]
        assert "Approve" in labels
        assert "Reject" in labels
        assert "View in Dashboard" in labels

    def test_to_slack_payload_dangerous_emoji(self):
        payload = self._make_payload(risk_level="DANGEROUS")
        slack = payload.to_slack_payload()
        header = slack["blocks"][0]
        assert ":rotating_light:" in header["text"]["text"]

    def test_to_slack_payload_safe_emoji(self):
        payload = self._make_payload(risk_level="SAFE")
        slack = payload.to_slack_payload()
        header = slack["blocks"][0]
        assert ":white_check_mark:" in header["text"]["text"]

    def test_to_slack_payload_no_urls_no_actions(self):
        payload = self._make_payload(
            approve_url=None, reject_url=None, dashboard_url=None
        )
        slack = payload.to_slack_payload()
        action_blocks = [b for b in slack["blocks"] if b["type"] == "actions"]
        # No action block when no URLs
        assert len(action_blocks) == 0


# ---------------------------------------------------------------------------
# WebhookNotifier tests
# ---------------------------------------------------------------------------

class TestWebhookNotifier:
    """Test the generic webhook notifier."""

    def test_is_slack_detection(self):
        slack = WebhookNotifier("https://hooks.slack.com/services/T00/B00/xxx")
        assert slack._is_slack is True

        generic = WebhookNotifier("https://example.com/webhook")
        assert generic._is_slack is False

    @pytest.mark.asyncio
    async def test_send_raw_no_url(self):
        notifier = WebhookNotifier("")
        result = await notifier.send_raw({"test": True})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_approval_required_slack_format(self):
        """Slack webhook should use Block Kit format."""
        notifier = WebhookNotifier("https://hooks.slack.com/services/T00/B00/xxx")
        payload = ApprovalPayload(
            healing_id="h1",
            detection_id="d1",
            fix_type="retry_limit",
            fix_title="Add retry limit",
            fix_description="Adds a retry limit",
            risk_level="MEDIUM",
        )

        with patch.object(notifier, "send_raw", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            result = await notifier.send_approval_required(payload)

            assert result is True
            call_args = mock_send.call_args[0][0]
            # Slack format has 'blocks' key
            assert "blocks" in call_args

    @pytest.mark.asyncio
    async def test_send_approval_required_generic_format(self):
        """Generic webhook should use plain JSON format."""
        notifier = WebhookNotifier("https://example.com/webhook")
        payload = ApprovalPayload(
            healing_id="h1",
            detection_id="d1",
            fix_type="retry_limit",
            fix_title="Add retry limit",
            fix_description="Adds a retry limit",
            risk_level="SAFE",
        )

        with patch.object(notifier, "send_raw", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            result = await notifier.send_approval_required(payload)

            assert result is True
            call_args = mock_send.call_args[0][0]
            # Generic format has 'event' key
            assert call_args["event"] == "approval_required"
            assert call_args["healing_id"] == "h1"


# ---------------------------------------------------------------------------
# NotificationRouter approval tests
# ---------------------------------------------------------------------------

class TestNotificationRouterApproval:
    """Test the notification router's approval workflow."""

    def test_build_approval_payload_with_ui_url(self):
        config = NotifyConfig(
            webhook_url="https://hooks.slack.com/services/T00/B00/xxx",
            ui_base_url="https://app.example.com",
        )
        router = NotificationRouter(config)
        payload = router.build_approval_payload(
            healing_id="h-123",
            detection_id="d-456",
            fix_type="circuit_breaker",
            fix_title="Add circuit breaker",
            fix_description="Prevents cascade failures",
            risk_level="DANGEROUS",
            tenant_id="t-1",
        )
        assert payload.approve_url == "https://app.example.com/healing?action=approve&id=h-123"
        assert payload.reject_url == "https://app.example.com/healing?action=reject&id=h-123"
        assert payload.dashboard_url == "https://app.example.com/healing"

    def test_build_approval_payload_no_ui_url(self):
        config = NotifyConfig(
            webhook_url="https://hooks.slack.com/services/T00/B00/xxx",
        )
        router = NotificationRouter(config)
        payload = router.build_approval_payload(
            healing_id="h-123",
            detection_id="d-456",
            fix_type="circuit_breaker",
            fix_title="Add circuit breaker",
            fix_description="Prevents cascade failures",
        )
        assert payload.approve_url is None
        assert payload.reject_url is None
        assert payload.dashboard_url is None

    @pytest.mark.asyncio
    async def test_notify_approval_required_skipped_when_disabled(self):
        config = NotifyConfig(
            webhook_url="https://hooks.slack.com/services/T00/B00/xxx",
            notify_on_approval_required=False,
        )
        router = NotificationRouter(config)
        payload = ApprovalPayload(
            healing_id="h1",
            detection_id="d1",
            fix_type="retry_limit",
            fix_title="test",
            fix_description="test",
            risk_level="SAFE",
        )
        result = await router.notify_approval_required(payload)
        assert result == {"skipped": True}

    @pytest.mark.asyncio
    async def test_notify_approval_required_routes_to_webhook(self):
        config = NotifyConfig(
            webhook_url="https://hooks.slack.com/services/T00/B00/xxx",
        )
        router = NotificationRouter(config)
        payload = ApprovalPayload(
            healing_id="h1",
            detection_id="d1",
            fix_type="retry_limit",
            fix_title="test fix",
            fix_description="test desc",
            risk_level="MEDIUM",
        )

        with patch.object(
            router._webhook, "send_approval_required", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True
            result = await router.notify_approval_required(payload)
            assert result["webhook"] is True
            mock_send.assert_called_once_with(payload)

    def test_create_notification_router_factory(self):
        router = create_notification_router(
            webhook_url="https://hooks.slack.com/services/T00/B00/xxx",
            ui_base_url="https://app.example.com",
        )
        assert router._webhook is not None
        assert router.config.ui_base_url == "https://app.example.com"

    def test_notify_config_from_dict(self):
        config = NotifyConfig.from_dict({
            "webhook_url": "https://hooks.slack.com/services/T00/B00/xxx",
            "ui_base_url": "https://app.example.com",
            "notify_on_approval_required": True,
        })
        assert config.webhook_url == "https://hooks.slack.com/services/T00/B00/xxx"
        assert config.ui_base_url == "https://app.example.com"
        assert config.notify_on_approval_required is True
