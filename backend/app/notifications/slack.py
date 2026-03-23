"""Slack webhook notifier for healing events.

Sends Block Kit formatted messages to Slack channels.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class SlackNotifier:
    """
    Slack webhook notifier for healing events.

    Sends formatted messages to a Slack channel when:
    - A failure is detected
    - A fix is applied
    - A rollback occurs

    Usage:
        notifier = SlackNotifier("https://hooks.slack.com/services/...")
        await notifier.send_healing_result(result)
    """

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def send(self, blocks: List[Dict], text: str = "") -> bool:
        """
        Send a Block Kit message to Slack webhook.

        Args:
            blocks: Slack Block Kit blocks
            text: Fallback plain text

        Returns:
            True if message sent successfully
        """
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        payload: Dict[str, Any] = {"blocks": blocks}
        if text:
            payload["text"] = text

        try:
            client = await self._get_client()
            response = await client.post(self.webhook_url, json=payload)

            if response.status_code == 200 and response.text == "ok":
                logger.debug("Slack notification sent successfully")
                return True
            else:
                logger.error(f"Slack webhook failed: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def send_healing_result(
        self,
        result: Any,
        workflow_name: Optional[str] = None,
    ) -> bool:
        status = getattr(result, "status", None)
        status_value = status.value if status else "unknown"

        emoji_map = {
            "success": ":white_check_mark:",
            "partial_success": ":warning:",
            "failed": ":x:",
            "pending": ":hourglass_flowing_sand:",
            "rollback": ":rewind:",
        }
        emoji = emoji_map.get(status_value, ":grey_question:")

        title = self._get_title(status_value)

        blocks: List[Dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {title}"},
            },
        ]

        fields = []
        if workflow_name:
            fields.append({"type": "mrkdwn", "text": f"*Workflow*\n{workflow_name}"})

        detection_id = getattr(result, "detection_id", None)
        if detection_id:
            short_id = f"{detection_id[:16]}..." if len(detection_id) > 16 else detection_id
            fields.append({"type": "mrkdwn", "text": f"*Detection*\n`{short_id}`"})

        signature = getattr(result, "failure_signature", None)
        if signature:
            category = getattr(signature, "category", None)
            if category:
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*Failure Type*\n{category.value.replace('_', ' ').title()}",
                })

        applied_fixes = getattr(result, "applied_fixes", [])
        if applied_fixes:
            fields.append({"type": "mrkdwn", "text": f"*Fixes Applied*\n{len(applied_fixes)}"})

        if fields:
            blocks.append({"type": "section", "fields": fields})

        error = getattr(result, "error", None)
        if error and status_value in ("failed", "rollback"):
            truncated = error[:500] + "..." if len(error) > 500 else error
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Error*\n```{truncated}```"},
            })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Pisama | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"},
            ],
        })

        return await self.send(blocks=blocks, text=f"{emoji} {title}")

    async def send_detection_alert(
        self,
        detection: Dict[str, Any],
        workflow_name: Optional[str] = None,
    ) -> bool:
        failure_mode = detection.get("failure_mode", "Unknown")
        confidence = detection.get("confidence", 0)

        blocks: List[Dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": ":rotating_light: Failure Detected"},
            },
        ]

        fields = [
            {"type": "mrkdwn", "text": f"*Failure Mode*\n{failure_mode}"},
            {"type": "mrkdwn", "text": f"*Confidence*\n{confidence:.1%}"},
        ]

        if workflow_name:
            fields.insert(0, {"type": "mrkdwn", "text": f"*Workflow*\n{workflow_name}"})

        blocks.append({"type": "section", "fields": fields})

        explanation = detection.get("explanation")
        if explanation:
            truncated = explanation[:500] + "..." if len(explanation) > 500 else explanation
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Explanation*\n{truncated}"},
            })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Pisama | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"},
            ],
        })

        return await self.send(
            blocks=blocks,
            text=f":rotating_light: Failure Detected: {failure_mode} ({confidence:.1%})",
        )

    def _get_title(self, status: str) -> str:
        titles = {
            "success": "Fix Applied Successfully",
            "partial_success": "Partial Fix Applied",
            "failed": "Fix Failed",
            "pending": "Fix Pending Approval",
            "rollback": "Fix Rolled Back",
            "analyzing": "Analyzing Failure",
            "generating_fix": "Generating Fix",
            "applying_fix": "Applying Fix",
            "validating": "Validating Fix",
        }
        return titles.get(status, "Healing Update")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
