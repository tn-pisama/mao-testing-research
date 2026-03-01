"""Generic webhook notifier for healing approval events.

Sends structured JSON payloads to a configurable webhook URL.
Compatible with Slack incoming webhooks out of the box.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ApprovalPayload:
    """Structured payload for approval notifications."""
    healing_id: str
    detection_id: str
    fix_type: str
    fix_title: str
    fix_description: str
    risk_level: str
    workflow_name: Optional[str] = None
    approve_url: Optional[str] = None
    reject_url: Optional[str] = None
    dashboard_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healing_id": self.healing_id,
            "detection_id": self.detection_id,
            "fix_type": self.fix_type,
            "fix_title": self.fix_title,
            "fix_description": self.fix_description,
            "risk_level": self.risk_level,
            "workflow_name": self.workflow_name,
            "approve_url": self.approve_url,
            "reject_url": self.reject_url,
            "dashboard_url": self.dashboard_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def to_slack_payload(self) -> Dict[str, Any]:
        """Format as a Slack incoming webhook payload with Block Kit."""
        risk_emoji = {
            "SAFE": ":white_check_mark:",
            "MEDIUM": ":warning:",
            "DANGEROUS": ":rotating_light:",
        }.get(self.risk_level, ":question:")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{risk_emoji} Fix Awaiting Approval",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Fix:*\n{self.fix_title}"},
                    {"type": "mrkdwn", "text": f"*Risk Level:*\n{self.risk_level}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{self.fix_type}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:*\n{self.fix_description[:500]}",
                },
            },
        ]

        if self.workflow_name:
            blocks[1]["fields"].append(
                {"type": "mrkdwn", "text": f"*Workflow:*\n{self.workflow_name}"}
            )

        # Action buttons with deep links
        actions = []
        if self.approve_url:
            actions.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve"},
                "style": "primary",
                "url": self.approve_url,
            })
        if self.reject_url:
            actions.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Reject"},
                "style": "danger",
                "url": self.reject_url,
            })
        if self.dashboard_url:
            actions.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "View in Dashboard"},
                "url": self.dashboard_url,
            })

        if actions:
            blocks.append({"type": "actions", "elements": actions})

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Healing ID: `{self.healing_id[:12]}...` | "
                            f"Detection: `{self.detection_id[:12]}...`",
                },
            ],
        })

        return {
            "text": f"Fix awaiting approval: {self.fix_title} ({self.risk_level})",
            "blocks": blocks,
        }


class WebhookNotifier:
    """Generic webhook notifier.

    Sends JSON payloads to a configurable URL. Automatically detects
    Slack-style webhooks and formats with Block Kit.

    Usage:
        notifier = WebhookNotifier("https://hooks.slack.com/services/...")
        await notifier.send_approval_required(payload)
    """

    def __init__(
        self,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}
        self._client: Optional[httpx.AsyncClient] = None
        self._is_slack = "hooks.slack.com" in webhook_url

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def send_raw(self, payload: Dict[str, Any]) -> bool:
        """Send a raw JSON payload to the webhook URL."""
        if not self.webhook_url:
            logger.warning("Webhook URL not configured")
            return False

        try:
            client = await self._get_client()
            response = await client.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
            )

            if response.status_code in (200, 204):
                logger.debug("Webhook notification sent successfully")
                return True
            else:
                logger.error(
                    f"Webhook failed: {response.status_code} {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return False

    async def send_approval_required(self, payload: ApprovalPayload) -> bool:
        """Send an approval-required notification.

        Uses Slack Block Kit formatting if the URL looks like a Slack webhook,
        otherwise sends a plain JSON payload.
        """
        if self._is_slack:
            data = payload.to_slack_payload()
        else:
            data = {
                "event": "approval_required",
                **payload.to_dict(),
            }

        return await self.send_raw(data)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
