"""Discord webhook notifier for healing events.

Simple webhook-based notifications for solo developers.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DiscordMessage:
    """Discord webhook message structure."""
    content: Optional[str] = None
    username: str = "MAO Healer"
    avatar_url: Optional[str] = None
    embeds: Optional[list] = None


class DiscordNotifier:
    """
    Discord webhook notifier for healing events.

    Sends formatted messages to a Discord channel when:
    - A failure is detected
    - A fix is applied
    - A rollback occurs

    Usage:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/...")
        await notifier.send_healing_result(result)
    """

    def __init__(
        self,
        webhook_url: str,
        username: str = "MAO Healer",
        avatar_url: Optional[str] = None,
    ):
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def send(
        self,
        content: Optional[str] = None,
        embeds: Optional[list] = None,
    ) -> bool:
        """
        Send a message to Discord webhook.

        Args:
            content: Plain text content
            embeds: List of embed objects

        Returns:
            True if message sent successfully
        """
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        payload = {
            "username": self.username,
        }

        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        try:
            client = await self._get_client()
            response = await client.post(self.webhook_url, json=payload)

            if response.status_code in (200, 204):
                logger.debug("Discord notification sent successfully")
                return True
            else:
                logger.error(f"Discord webhook failed: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    async def send_healing_result(
        self,
        result: Any,
        workflow_name: Optional[str] = None,
    ) -> bool:
        """
        Send a formatted healing result notification.

        Args:
            result: HealingResult object
            workflow_name: Optional workflow name for display

        Returns:
            True if sent successfully
        """
        # Determine status color
        status = getattr(result, "status", None)
        status_value = status.value if status else "unknown"

        color_map = {
            "success": 0x2ECC71,  # Green
            "partial_success": 0xF1C40F,  # Yellow
            "failed": 0xE74C3C,  # Red
            "pending": 0x3498DB,  # Blue
            "rollback": 0x9B59B6,  # Purple
        }
        color = color_map.get(status_value, 0x95A5A6)  # Gray default

        # Build embed
        embed = {
            "title": self._get_title(status_value),
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields": [],
        }

        # Add workflow info
        if workflow_name:
            embed["fields"].append({
                "name": "Workflow",
                "value": workflow_name,
                "inline": True,
            })

        # Add detection ID
        detection_id = getattr(result, "detection_id", None)
        if detection_id:
            embed["fields"].append({
                "name": "Detection",
                "value": f"`{detection_id[:16]}...`" if len(detection_id) > 16 else f"`{detection_id}`",
                "inline": True,
            })

        # Add failure category
        signature = getattr(result, "failure_signature", None)
        if signature:
            category = getattr(signature, "category", None)
            if category:
                embed["fields"].append({
                    "name": "Failure Type",
                    "value": category.value.replace("_", " ").title(),
                    "inline": True,
                })

        # Add applied fixes count
        applied_fixes = getattr(result, "applied_fixes", [])
        if applied_fixes:
            embed["fields"].append({
                "name": "Fixes Applied",
                "value": str(len(applied_fixes)),
                "inline": True,
            })

        # Add error message if failed
        error = getattr(result, "error", None)
        if error and status_value in ("failed", "rollback"):
            embed["fields"].append({
                "name": "Error",
                "value": error[:200] + "..." if len(error) > 200 else error,
                "inline": False,
            })

        # Add backup SHA if available
        metadata = getattr(result, "metadata", {})
        backup_sha = metadata.get("backup_commit_sha")
        if backup_sha:
            embed["fields"].append({
                "name": "Backup",
                "value": f"`{backup_sha[:8]}`",
                "inline": True,
            })

        # Add footer
        embed["footer"] = {
            "text": "MAO Healer",
        }

        return await self.send(embeds=[embed])

    async def send_detection_alert(
        self,
        detection: Dict[str, Any],
        workflow_name: Optional[str] = None,
    ) -> bool:
        """
        Send a detection alert notification.

        Args:
            detection: Detection result dict
            workflow_name: Optional workflow name

        Returns:
            True if sent successfully
        """
        failure_mode = detection.get("failure_mode", "Unknown")
        confidence = detection.get("confidence", 0)

        embed = {
            "title": "Failure Detected",
            "color": 0xE74C3C,  # Red
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields": [
                {
                    "name": "Failure Mode",
                    "value": failure_mode,
                    "inline": True,
                },
                {
                    "name": "Confidence",
                    "value": f"{confidence:.1%}",
                    "inline": True,
                },
            ],
        }

        if workflow_name:
            embed["fields"].insert(0, {
                "name": "Workflow",
                "value": workflow_name,
                "inline": True,
            })

        explanation = detection.get("explanation")
        if explanation:
            embed["fields"].append({
                "name": "Explanation",
                "value": explanation[:500] + "..." if len(explanation) > 500 else explanation,
                "inline": False,
            })

        embed["footer"] = {"text": "MAO Healer"}

        return await self.send(embeds=[embed])

    def _get_title(self, status: str) -> str:
        """Get notification title based on status."""
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
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
