"""Configuration management for MAO Healer CLI.

Handles YAML config file loading and defaults.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


CONFIG_DIR = Path.home() / ".mao-healer"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


@dataclass
class N8nConfig:
    """n8n connection configuration."""
    webhook_secret: str = ""
    api_url: str = "http://localhost:5678"
    api_key: str = ""


@dataclass
class DetectionConfig:
    """Detection settings."""
    enabled_modes: List[str] = field(default_factory=lambda: [
        "F1", "F2", "F3", "F6", "F7", "F8", "F12", "F14"
    ])
    llm_verification: bool = False


@dataclass
class AutoApplyConfig:
    """Auto-apply settings."""
    enabled: bool = True
    max_fixes_per_hour: int = 5
    git_backup: bool = True
    git_repo: str = "~/n8n-workflows-backup"


@dataclass
class NotificationsConfig:
    """Notification settings."""
    discord_webhook: str = ""
    slack_webhook: str = ""
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""


@dataclass
class HealerConfig:
    """Complete MAO Healer configuration."""
    n8n: N8nConfig = field(default_factory=N8nConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    auto_apply: AutoApplyConfig = field(default_factory=AutoApplyConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    server_port: int = 8080
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "HealerConfig":
        """Load configuration from YAML file."""
        config_path = path or CONFIG_FILE

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealerConfig":
        """Create config from dictionary."""
        n8n_data = data.get("n8n", {})
        detection_data = data.get("detection", {})
        auto_apply_data = data.get("auto_apply", {})
        notifications_data = data.get("notifications", {})

        return cls(
            n8n=N8nConfig(
                webhook_secret=n8n_data.get("webhook_secret", ""),
                api_url=n8n_data.get("api_url", "http://localhost:5678"),
                api_key=n8n_data.get("api_key", ""),
            ),
            detection=DetectionConfig(
                enabled_modes=detection_data.get("enabled_modes", [
                    "F1", "F2", "F3", "F6", "F7", "F8", "F12", "F14"
                ]),
                llm_verification=detection_data.get("llm_verification", False),
            ),
            auto_apply=AutoApplyConfig(
                enabled=auto_apply_data.get("enabled", True),
                max_fixes_per_hour=auto_apply_data.get("max_fixes_per_hour", 5),
                git_backup=auto_apply_data.get("git_backup", True),
                git_repo=auto_apply_data.get("git_repo", "~/n8n-workflows-backup"),
            ),
            notifications=NotificationsConfig(
                discord_webhook=notifications_data.get("discord_webhook", ""),
                slack_webhook=notifications_data.get("slack_webhook", ""),
                email_smtp_host=notifications_data.get("email", {}).get("smtp_host", "smtp.gmail.com"),
                email_smtp_port=notifications_data.get("email", {}).get("smtp_port", 587),
                email_smtp_user=notifications_data.get("email", {}).get("smtp_user", ""),
                email_smtp_password=notifications_data.get("email", {}).get("smtp_password", ""),
                email_from=notifications_data.get("email", {}).get("from", ""),
                email_to=notifications_data.get("email", {}).get("to", ""),
            ),
            server_port=data.get("server_port", 8080),
            log_level=data.get("log_level", "INFO"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "n8n": {
                "webhook_secret": self.n8n.webhook_secret,
                "api_url": self.n8n.api_url,
                "api_key": self.n8n.api_key,
            },
            "detection": {
                "enabled_modes": self.detection.enabled_modes,
                "llm_verification": self.detection.llm_verification,
            },
            "auto_apply": {
                "enabled": self.auto_apply.enabled,
                "max_fixes_per_hour": self.auto_apply.max_fixes_per_hour,
                "git_backup": self.auto_apply.git_backup,
                "git_repo": self.auto_apply.git_repo,
            },
            "notifications": {
                "discord_webhook": self.notifications.discord_webhook,
                "slack_webhook": self.notifications.slack_webhook,
                "email": {
                    "smtp_host": self.notifications.email_smtp_host,
                    "smtp_port": self.notifications.email_smtp_port,
                    "smtp_user": self.notifications.email_smtp_user,
                    "smtp_password": self.notifications.email_smtp_password,
                    "from": self.notifications.email_from,
                    "to": self.notifications.email_to,
                },
            },
            "server_port": self.server_port,
            "log_level": self.log_level,
        }

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to YAML file."""
        config_path = path or CONFIG_FILE
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)


def get_default_config_template() -> str:
    """Get default config template as YAML string."""
    return """# MAO Healer Configuration
# https://github.com/your-org/mao-healer

# n8n connection settings
n8n:
  # HMAC secret for webhook verification (generate with: openssl rand -hex 32)
  webhook_secret: "your-webhook-secret-here"
  # n8n API URL
  api_url: "http://localhost:5678"
  # n8n API key (Settings > API > Create API Key)
  api_key: "your-n8n-api-key-here"

# Detection settings
detection:
  # Enabled failure modes (all are FREE pattern-based detectors)
  enabled_modes:
    - F1   # Specification Mismatch
    - F2   # Context Neglect
    - F3   # Coordination Failure
    - F6   # State Corruption
    - F7   # Derailment
    - F8   # Infinite Loop
    - F12  # Resource Overflow
    - F14  # Communication Breakdown
  # Enable LLM verification for ambiguous cases (costs ~$0.003/judgment)
  llm_verification: false

# Auto-apply settings
auto_apply:
  # Enable automatic fix application
  enabled: true
  # Maximum fixes per hour per workflow (rate limiting)
  max_fixes_per_hour: 5
  # Create Git backup before applying fixes
  git_backup: true
  # Path to Git backup repository
  git_repo: "~/n8n-workflows-backup"

# Notification settings
notifications:
  # Discord webhook URL (right-click channel > Edit Channel > Integrations > Webhooks)
  discord_webhook: ""
  # Slack webhook URL (Apps > Incoming Webhooks > Add New Webhook)
  slack_webhook: ""
  # Email settings (optional)
  email:
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: ""
    smtp_password: ""  # Use app password for Gmail
    from: ""
    to: ""

# Server settings
server_port: 8080
log_level: "INFO"
"""


def ensure_config_dir() -> Path:
    """Ensure config directory exists and return path."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR
