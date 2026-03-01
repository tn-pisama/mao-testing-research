"""Playbook Registry — graduates successful AI fixes to deterministic playbooks.

Tracks fix effectiveness over time. When a (detection_type, fix_type) pair
succeeds consistently (configurable threshold), it is promoted to a
"graduated playbook" that auto-applies without approval on future occurrences.

ICP-tier: In-memory registry with serialization support for persistence.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default graduation threshold: number of consecutive successes
DEFAULT_GRADUATION_THRESHOLD = 3


@dataclass
class FixOutcome:
    """Record of a single fix application outcome."""
    detection_type: str
    fix_type: str
    success: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    healing_id: Optional[str] = None
    confidence: float = 0.0


@dataclass
class PlaybookEntry:
    """A tracked fix pattern with its effectiveness history."""
    detection_type: str
    fix_type: str
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0
    consecutive_successes: int = 0
    graduated: bool = False
    graduated_at: Optional[datetime] = None
    last_applied: Optional[datetime] = None
    avg_confidence: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    @property
    def key(self) -> str:
        return f"{self.detection_type}::{self.fix_type}"

    def record(self, outcome: FixOutcome) -> None:
        """Record a fix outcome and update stats."""
        self.total_count += 1
        self.last_applied = outcome.timestamp

        if outcome.success:
            self.success_count += 1
            self.consecutive_successes += 1
        else:
            self.failure_count += 1
            self.consecutive_successes = 0
            # Revoke graduation on failure
            if self.graduated:
                logger.info(
                    f"Playbook revoked: {self.key} failed after graduation"
                )
                self.graduated = False
                self.graduated_at = None

        # Running average confidence
        if outcome.confidence > 0:
            if self.total_count == 1:
                self.avg_confidence = outcome.confidence
            else:
                self.avg_confidence = (
                    self.avg_confidence * (self.total_count - 1) + outcome.confidence
                ) / self.total_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detection_type": self.detection_type,
            "fix_type": self.fix_type,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_count": self.total_count,
            "consecutive_successes": self.consecutive_successes,
            "success_rate": round(self.success_rate, 3),
            "graduated": self.graduated,
            "graduated_at": self.graduated_at.isoformat() if self.graduated_at else None,
            "last_applied": self.last_applied.isoformat() if self.last_applied else None,
            "avg_confidence": round(self.avg_confidence, 3),
        }


class PlaybookRegistry:
    """Registry of fix effectiveness patterns and graduated playbooks.

    Tracks which (detection_type, fix_type) pairs have been applied
    and their outcomes. When a pair reaches the graduation threshold
    of consecutive successes, it becomes a "graduated playbook" that
    can be auto-applied without approval in the future.

    Usage:
        registry = PlaybookRegistry(graduation_threshold=3)

        # Record outcomes
        registry.record_outcome(FixOutcome(
            detection_type="infinite_loop",
            fix_type="retry_limit",
            success=True,
        ))

        # Check if graduated
        if registry.is_graduated("infinite_loop", "retry_limit"):
            # Auto-apply without approval
            ...

        # Get recommended fix for a detection type
        recommended = registry.get_recommended_fix("infinite_loop")
    """

    def __init__(self, graduation_threshold: int = DEFAULT_GRADUATION_THRESHOLD):
        self.graduation_threshold = graduation_threshold
        self._entries: Dict[str, PlaybookEntry] = {}

    def _key(self, detection_type: str, fix_type: str) -> str:
        return f"{detection_type}::{fix_type}"

    def record_outcome(self, outcome: FixOutcome) -> PlaybookEntry:
        """Record a fix outcome and check for graduation.

        Returns the updated PlaybookEntry.
        """
        key = self._key(outcome.detection_type, outcome.fix_type)

        if key not in self._entries:
            self._entries[key] = PlaybookEntry(
                detection_type=outcome.detection_type,
                fix_type=outcome.fix_type,
            )

        entry = self._entries[key]
        entry.record(outcome)

        # Check graduation
        if (
            not entry.graduated
            and entry.consecutive_successes >= self.graduation_threshold
        ):
            entry.graduated = True
            entry.graduated_at = datetime.now(timezone.utc)
            logger.info(
                f"Playbook graduated: {key} "
                f"({entry.consecutive_successes} consecutive successes, "
                f"{entry.success_rate:.0%} overall)"
            )

        return entry

    def is_graduated(self, detection_type: str, fix_type: str) -> bool:
        """Check if a (detection_type, fix_type) pair is a graduated playbook."""
        key = self._key(detection_type, fix_type)
        entry = self._entries.get(key)
        return entry is not None and entry.graduated

    def get_graduated_fix(self, detection_type: str) -> Optional[str]:
        """Get the graduated fix_type for a detection_type, if one exists.

        If multiple fix_types are graduated for the same detection_type,
        returns the one with the highest success rate.
        """
        candidates = [
            entry for entry in self._entries.values()
            if entry.detection_type == detection_type and entry.graduated
        ]

        if not candidates:
            return None

        best = max(candidates, key=lambda e: (e.success_rate, e.success_count))
        return best.fix_type

    def get_recommended_fix(self, detection_type: str) -> Optional[PlaybookEntry]:
        """Get the best fix recommendation for a detection type.

        Prefers graduated playbooks. Falls back to highest success rate
        among non-graduated entries with at least 1 success.
        """
        candidates = [
            entry for entry in self._entries.values()
            if entry.detection_type == detection_type
        ]

        if not candidates:
            return None

        # Prefer graduated
        graduated = [e for e in candidates if e.graduated]
        if graduated:
            return max(graduated, key=lambda e: (e.success_rate, e.success_count))

        # Fall back to best performing non-graduated
        with_successes = [e for e in candidates if e.success_count > 0]
        if with_successes:
            return max(with_successes, key=lambda e: (e.success_rate, e.success_count))

        return None

    def get_all_graduated(self) -> List[PlaybookEntry]:
        """Get all graduated playbook entries."""
        return [e for e in self._entries.values() if e.graduated]

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        entries = list(self._entries.values())
        graduated = [e for e in entries if e.graduated]
        return {
            "total_patterns": len(entries),
            "graduated_count": len(graduated),
            "total_outcomes": sum(e.total_count for e in entries),
            "overall_success_rate": (
                sum(e.success_count for e in entries) /
                max(sum(e.total_count for e in entries), 1)
            ),
            "graduation_threshold": self.graduation_threshold,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize registry state for persistence."""
        return {
            "graduation_threshold": self.graduation_threshold,
            "entries": {k: v.to_dict() for k, v in self._entries.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaybookRegistry":
        """Restore registry from serialized state."""
        registry = cls(
            graduation_threshold=data.get(
                "graduation_threshold", DEFAULT_GRADUATION_THRESHOLD
            )
        )
        for key, entry_data in data.get("entries", {}).items():
            entry = PlaybookEntry(
                detection_type=entry_data["detection_type"],
                fix_type=entry_data["fix_type"],
                success_count=entry_data.get("success_count", 0),
                failure_count=entry_data.get("failure_count", 0),
                total_count=entry_data.get("total_count", 0),
                consecutive_successes=entry_data.get("consecutive_successes", 0),
                graduated=entry_data.get("graduated", False),
                avg_confidence=entry_data.get("avg_confidence", 0.0),
            )
            if entry_data.get("graduated_at"):
                entry.graduated_at = datetime.fromisoformat(entry_data["graduated_at"])
            if entry_data.get("last_applied"):
                entry.last_applied = datetime.fromisoformat(entry_data["last_applied"])
            registry._entries[key] = entry
        return registry

    def should_auto_apply(
        self,
        detection_type: str,
        fix_type: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a fix should be auto-applied based on playbook graduation.

        Returns (should_auto_apply, reason).
        """
        if self.is_graduated(detection_type, fix_type):
            entry = self._entries[self._key(detection_type, fix_type)]
            return True, (
                f"Graduated playbook: {entry.success_count} successes, "
                f"{entry.success_rate:.0%} success rate"
            )
        return False, None
