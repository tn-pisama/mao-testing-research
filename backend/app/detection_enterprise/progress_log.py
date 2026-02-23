"""Progress tracking for long-running agent sessions.

Records actions across calibration, healing, and golden data generation
into a single JSONL log. Agents can read this file to understand what
has been done and what remains.

Follows the Anthropic "progress tracking file" pattern for multi-session agents.

Usage:
    from app.detection_enterprise.progress_log import ProgressLog

    progress = ProgressLog()
    progress.log("calibration_run", "calibrate.py", "Calibrated 17 detectors, avg F1=0.75")
    print(progress.format_status())
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_PROGRESS_PATH = Path(__file__).parent.parent.parent / "data" / "progress_log.jsonl"


@dataclass
class ProgressEntry:
    """A single progress log entry."""

    timestamp: str
    action: str          # "calibration_run", "threshold_update", "registry_updated",
                         # "healing_fix_applied", "smoke_test_passed"
    actor: str           # "calibrate.py", "healing_engine", "bootstrap.sh"
    summary: str         # Human-readable one-liner
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProgressEntry":
        return cls(
            timestamp=data.get("timestamp", ""),
            action=data.get("action", ""),
            actor=data.get("actor", ""),
            summary=data.get("summary", ""),
            details=data.get("details", {}),
        )


class ProgressLog:
    """Manages the progress log JSONL file."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_PROGRESS_PATH

    def append(self, entry: ProgressEntry) -> None:
        """Append a progress entry."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(entry.to_dict(), default=str) + "\n")

    def log(self, action: str, actor: str, summary: str, **details: Any) -> None:
        """Convenience method to log a progress entry."""
        entry = ProgressEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            actor=actor,
            summary=summary,
            details=details,
        )
        self.append(entry)

    def load_all(self) -> List[ProgressEntry]:
        """Load all entries from the progress log."""
        if not self.path.exists():
            return []
        entries = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(ProgressEntry.from_dict(data))
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("Skipping malformed progress entry: %s", exc)
        return entries

    def load_recent(self, n: int = 20) -> List[ProgressEntry]:
        """Load the N most recent entries."""
        return self.load_all()[-n:]

    def format_status(self, n: int = 20) -> str:
        """Format a human-readable status summary."""
        entries = self.load_recent(n)
        if not entries:
            return "No progress history available."

        lines = []
        lines.append("=" * 72)
        lines.append("  PISAMA PROGRESS LOG (last {} entries)".format(min(n, len(entries))))
        lines.append("=" * 72)

        for entry in reversed(entries):
            ts = entry.timestamp[:19]  # Trim timezone suffix
            lines.append(f"\n  [{ts}] {entry.action}")
            lines.append(f"    {entry.summary}")
            lines.append(f"    actor: {entry.actor}")

        lines.append("\n" + "=" * 72)
        return "\n".join(lines)
