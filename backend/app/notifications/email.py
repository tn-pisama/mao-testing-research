"""Email notifier for healing events.

Simple SMTP-based notifications for solo developers.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Email configuration for SMTP."""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_address: str = "mao-healer@local"
    to_addresses: List[str] = field(default_factory=list)
    use_tls: bool = True


class EmailNotifier:
    """
    Email notifier for healing events.

    Sends formatted emails when:
    - A failure is detected
    - A fix is applied
    - A rollback occurs

    Usage:
        config = EmailConfig(
            smtp_host="smtp.gmail.com",
            smtp_user="your-email",
            smtp_password="app-password",
            to_addresses=["alerts@example.com"],
        )
        notifier = EmailNotifier(config)
        await notifier.send_healing_result(result)
    """

    def __init__(self, config: EmailConfig):
        self.config = config

    async def send(
        self,
        to: Optional[str] = None,
        subject: str = "MAO Healer Notification",
        body: str = "",
        html_body: Optional[str] = None,
    ) -> bool:
        """
        Send an email notification.

        Args:
            to: Recipient email (uses config.to_addresses if not provided)
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body

        Returns:
            True if email sent successfully
        """
        recipients = [to] if to else self.config.to_addresses
        if not recipients:
            logger.warning("No email recipients configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.from_address
            msg["To"] = ", ".join(recipients)

            # Add plain text body
            msg.attach(MIMEText(body, "plain"))

            # Add HTML body if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            # Send email
            await self._send_smtp(msg, recipients)

            logger.debug(f"Email sent to {recipients}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def _send_smtp(
        self,
        msg: MIMEMultipart,
        recipients: List[str],
    ) -> None:
        """Send email via SMTP."""
        # Use synchronous SMTP (async SMTP libraries add complexity)
        # For solo dev use case, this is acceptable
        if self.config.use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls(context=context)
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.from_address,
                    recipients,
                    msg.as_string(),
                )
        else:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.from_address,
                    recipients,
                    msg.as_string(),
                )

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
        status = getattr(result, "status", None)
        status_value = status.value if status else "unknown"

        subject = f"[MAO Healer] {self._get_subject(status_value)}"
        if workflow_name:
            subject += f" - {workflow_name}"

        # Build plain text body
        body_lines = [
            f"Status: {status_value.upper()}",
            f"Time: {datetime.now(timezone.utc).isoformat()}",
            "",
        ]

        if workflow_name:
            body_lines.append(f"Workflow: {workflow_name}")

        detection_id = getattr(result, "detection_id", None)
        if detection_id:
            body_lines.append(f"Detection ID: {detection_id}")

        signature = getattr(result, "failure_signature", None)
        if signature:
            category = getattr(signature, "category", None)
            if category:
                body_lines.append(f"Failure Type: {category.value.replace('_', ' ').title()}")

        applied_fixes = getattr(result, "applied_fixes", [])
        if applied_fixes:
            body_lines.append(f"Fixes Applied: {len(applied_fixes)}")

        error = getattr(result, "error", None)
        if error:
            body_lines.append("")
            body_lines.append(f"Error: {error}")

        metadata = getattr(result, "metadata", {})
        backup_sha = metadata.get("backup_commit_sha")
        if backup_sha:
            body_lines.append(f"Backup SHA: {backup_sha[:8]}")

        body_lines.append("")
        body_lines.append("--")
        body_lines.append("MAO Healer")

        body = "\n".join(body_lines)

        # Build HTML body
        html_body = self._build_html_body(result, workflow_name)

        return await self.send(subject=subject, body=body, html_body=html_body)

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

        subject = f"[MAO Healer] Failure Detected: {failure_mode}"
        if workflow_name:
            subject += f" - {workflow_name}"

        body_lines = [
            "A failure has been detected in your workflow.",
            "",
            f"Failure Mode: {failure_mode}",
            f"Confidence: {confidence:.1%}",
            f"Time: {datetime.now(timezone.utc).isoformat()}",
        ]

        if workflow_name:
            body_lines.append(f"Workflow: {workflow_name}")

        explanation = detection.get("explanation")
        if explanation:
            body_lines.append("")
            body_lines.append(f"Explanation: {explanation}")

        body_lines.append("")
        body_lines.append("--")
        body_lines.append("MAO Healer")

        return await self.send(subject=subject, body="\n".join(body_lines))

    def _get_subject(self, status: str) -> str:
        """Get email subject based on status."""
        subjects = {
            "success": "Fix Applied Successfully",
            "partial_success": "Partial Fix Applied",
            "failed": "Fix Failed",
            "pending": "Fix Pending Approval",
            "rollback": "Fix Rolled Back",
        }
        return subjects.get(status, "Healing Update")

    def _build_html_body(
        self,
        result: Any,
        workflow_name: Optional[str] = None,
    ) -> str:
        """Build HTML email body."""
        status = getattr(result, "status", None)
        status_value = status.value if status else "unknown"

        color_map = {
            "success": "#2ECC71",
            "partial_success": "#F1C40F",
            "failed": "#E74C3C",
            "pending": "#3498DB",
            "rollback": "#9B59B6",
        }
        color = color_map.get(status_value, "#95A5A6")

        rows = []

        if workflow_name:
            rows.append(f"<tr><td><strong>Workflow</strong></td><td>{workflow_name}</td></tr>")

        detection_id = getattr(result, "detection_id", None)
        if detection_id:
            rows.append(f"<tr><td><strong>Detection ID</strong></td><td><code>{detection_id}</code></td></tr>")

        signature = getattr(result, "failure_signature", None)
        if signature:
            category = getattr(signature, "category", None)
            if category:
                rows.append(f"<tr><td><strong>Failure Type</strong></td><td>{category.value.replace('_', ' ').title()}</td></tr>")

        applied_fixes = getattr(result, "applied_fixes", [])
        if applied_fixes:
            rows.append(f"<tr><td><strong>Fixes Applied</strong></td><td>{len(applied_fixes)}</td></tr>")

        error = getattr(result, "error", None)
        if error:
            rows.append(f"<tr><td><strong>Error</strong></td><td style='color: #E74C3C;'>{error}</td></tr>")

        metadata = getattr(result, "metadata", {})
        backup_sha = metadata.get("backup_commit_sha")
        if backup_sha:
            rows.append(f"<tr><td><strong>Backup SHA</strong></td><td><code>{backup_sha[:8]}</code></td></tr>")

        rows_html = "\n".join(rows)

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 10px; border-bottom: 1px solid #eee; }}
                code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
                .footer {{ padding: 20px; color: #666; font-size: 12px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{self._get_subject(status_value)}</h1>
            </div>
            <div class="content">
                <table>
                    {rows_html}
                </table>
            </div>
            <div class="footer">
                MAO Healer - Self-healing for n8n workflows
            </div>
        </body>
        </html>
        """
