"""Notification router for routing alerts to configured channels.

Routes healing events to Discord, email, or both based on configuration.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .discord import DiscordNotifier
from .email import EmailNotifier, EmailConfig

logger = logging.getLogger(__name__)


@dataclass
class NotifyConfig:
    """Configuration for notification routing."""
    # Discord settings
    discord_webhook: Optional[str] = None
    discord_username: str = "MAO Healer"

    # Email settings
    email_enabled: bool = False
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_smtp_user: Optional[str] = None
    email_smtp_password: Optional[str] = None
    email_from: str = "mao-healer@local"
    email_to: List[str] = field(default_factory=list)

    # Routing settings
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notify_on_detection: bool = True
    notify_on_rollback: bool = True

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "NotifyConfig":
        """Create config from dictionary."""
        return cls(
            discord_webhook=config.get("discord_webhook"),
            discord_username=config.get("discord_username", "MAO Healer"),
            email_enabled=config.get("email", {}).get("enabled", False),
            email_smtp_host=config.get("email", {}).get("smtp_host", "smtp.gmail.com"),
            email_smtp_port=config.get("email", {}).get("smtp_port", 587),
            email_smtp_user=config.get("email", {}).get("smtp_user"),
            email_smtp_password=config.get("email", {}).get("smtp_password"),
            email_from=config.get("email", {}).get("from", "mao-healer@local"),
            email_to=config.get("email", {}).get("to", []),
            notify_on_success=config.get("notify_on_success", True),
            notify_on_failure=config.get("notify_on_failure", True),
            notify_on_detection=config.get("notify_on_detection", True),
            notify_on_rollback=config.get("notify_on_rollback", True),
        )


class NotificationRouter:
    """
    Routes notifications to configured channels.

    Supports:
    - Discord webhooks
    - Email via SMTP
    - Filtering by event type

    Usage:
        config = NotifyConfig(
            discord_webhook="https://discord.com/api/webhooks/...",
            email_to=["alerts@example.com"],
        )
        router = NotificationRouter(config)

        # On healing result
        await router.notify_healing_result(result, workflow_name="My Workflow")

        # On detection
        await router.notify_detection(detection, workflow_name="My Workflow")
    """

    def __init__(self, config: NotifyConfig):
        self.config = config
        self._discord: Optional[DiscordNotifier] = None
        self._email: Optional[EmailNotifier] = None

        # Initialize notifiers
        if config.discord_webhook:
            self._discord = DiscordNotifier(
                webhook_url=config.discord_webhook,
                username=config.discord_username,
            )

        if config.email_enabled and config.email_to:
            email_config = EmailConfig(
                smtp_host=config.email_smtp_host,
                smtp_port=config.email_smtp_port,
                smtp_user=config.email_smtp_user,
                smtp_password=config.email_smtp_password,
                from_address=config.email_from,
                to_addresses=config.email_to,
            )
            self._email = EmailNotifier(email_config)

    async def notify(
        self,
        result: Any,
        workflow_name: Optional[str] = None,
    ) -> Dict[str, bool]:
        """
        Send notification for a healing result.

        Alias for notify_healing_result for simpler API.

        Returns:
            Dict with success status per channel
        """
        return await self.notify_healing_result(result, workflow_name)

    async def notify_healing_result(
        self,
        result: Any,
        workflow_name: Optional[str] = None,
    ) -> Dict[str, bool]:
        """
        Send notification for a healing result.

        Args:
            result: HealingResult object
            workflow_name: Optional workflow name

        Returns:
            Dict with success status per channel
        """
        status = getattr(result, "status", None)
        status_value = status.value if status else "unknown"

        # Check if we should notify for this status
        if status_value == "success" and not self.config.notify_on_success:
            return {"skipped": True}
        if status_value == "failed" and not self.config.notify_on_failure:
            return {"skipped": True}
        if status_value == "rollback" and not self.config.notify_on_rollback:
            return {"skipped": True}

        results = {}

        # Send to Discord
        if self._discord:
            try:
                results["discord"] = await self._discord.send_healing_result(
                    result, workflow_name
                )
            except Exception as e:
                logger.error(f"Discord notification failed: {e}")
                results["discord"] = False

        # Send to Email
        if self._email:
            try:
                results["email"] = await self._email.send_healing_result(
                    result, workflow_name
                )
            except Exception as e:
                logger.error(f"Email notification failed: {e}")
                results["email"] = False

        return results

    async def notify_detection(
        self,
        detection: Dict[str, Any],
        workflow_name: Optional[str] = None,
    ) -> Dict[str, bool]:
        """
        Send notification for a detection event.

        Args:
            detection: Detection result dict
            workflow_name: Optional workflow name

        Returns:
            Dict with success status per channel
        """
        if not self.config.notify_on_detection:
            return {"skipped": True}

        results = {}

        # Send to Discord
        if self._discord:
            try:
                results["discord"] = await self._discord.send_detection_alert(
                    detection, workflow_name
                )
            except Exception as e:
                logger.error(f"Discord notification failed: {e}")
                results["discord"] = False

        # Send to Email
        if self._email:
            try:
                results["email"] = await self._email.send_detection_alert(
                    detection, workflow_name
                )
            except Exception as e:
                logger.error(f"Email notification failed: {e}")
                results["email"] = False

        return results

    async def notify_custom(
        self,
        title: str,
        message: str,
        level: str = "info",
    ) -> Dict[str, bool]:
        """
        Send a custom notification message.

        Args:
            title: Notification title
            message: Notification message
            level: Severity level (info, warning, error)

        Returns:
            Dict with success status per channel
        """
        results = {}

        # Color based on level
        colors = {
            "info": 0x3498DB,
            "warning": 0xF1C40F,
            "error": 0xE74C3C,
        }
        color = colors.get(level, 0x95A5A6)

        # Send to Discord
        if self._discord:
            try:
                embed = {
                    "title": title,
                    "description": message,
                    "color": color,
                }
                results["discord"] = await self._discord.send(embeds=[embed])
            except Exception as e:
                logger.error(f"Discord notification failed: {e}")
                results["discord"] = False

        # Send to Email
        if self._email:
            try:
                subject = f"[MAO Healer] {title}"
                results["email"] = await self._email.send(
                    subject=subject,
                    body=message,
                )
            except Exception as e:
                logger.error(f"Email notification failed: {e}")
                results["email"] = False

        return results

    async def test_notifications(self) -> Dict[str, bool]:
        """
        Send test notifications to all configured channels.

        Returns:
            Dict with success status per channel
        """
        return await self.notify_custom(
            title="Test Notification",
            message="This is a test notification from MAO Healer. If you see this, notifications are working correctly!",
            level="info",
        )

    async def close(self) -> None:
        """Close all notifier connections."""
        if self._discord:
            await self._discord.close()


def create_notification_router(
    discord_webhook: Optional[str] = None,
    email_config: Optional[Dict[str, Any]] = None,
) -> NotificationRouter:
    """
    Factory function to create a notification router.

    Args:
        discord_webhook: Discord webhook URL
        email_config: Email configuration dict

    Returns:
        Configured NotificationRouter
    """
    config = NotifyConfig(
        discord_webhook=discord_webhook,
    )

    if email_config:
        config.email_enabled = True
        config.email_smtp_host = email_config.get("smtp_host", "smtp.gmail.com")
        config.email_smtp_port = email_config.get("smtp_port", 587)
        config.email_smtp_user = email_config.get("smtp_user")
        config.email_smtp_password = email_config.get("smtp_password")
        config.email_from = email_config.get("from", "mao-healer@local")
        config.email_to = email_config.get("to", [])

    return NotificationRouter(config)
