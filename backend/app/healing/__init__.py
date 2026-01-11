"""Self-healing engine for automated fix application and validation."""

from .engine import SelfHealingEngine
from .analyzer import FailureAnalyzer
from .applicator import FixApplicator
from .validator import FixValidator
from .models import (
    HealingResult,
    HealingStatus,
    ValidationResult,
    AppliedFix,
)
from .auto_apply import (
    AutoApplyService,
    AutoApplyConfig,
    ApplyResult,
    RateLimiter,
)
from .git_backup import (
    GitBackupService,
    GitBackupConfig,
    BackupRecord,
    create_git_backup_service,
)

__all__ = [
    # Engine
    "SelfHealingEngine",
    "FailureAnalyzer",
    "FixApplicator",
    "FixValidator",
    # Models
    "HealingResult",
    "HealingStatus",
    "ValidationResult",
    "AppliedFix",
    # Auto-apply
    "AutoApplyService",
    "AutoApplyConfig",
    "ApplyResult",
    "RateLimiter",
    # Git backup
    "GitBackupService",
    "GitBackupConfig",
    "BackupRecord",
    "create_git_backup_service",
]
