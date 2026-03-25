"""Fix Effectiveness Tracking — learns which fixes actually work.

Tracks success/failure rates per (fix_type, detection_type) pair.
When generating fixes, sorts by historical effectiveness.
Seeds from E2E healing test results.

This closes the learning loop: detection → fix → verify → learn → better fixes.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FixEffectivenessRecord:
    """Tracks how effective a fix type is for a detection type."""
    fix_type: str
    detection_type: str
    success_count: int = 0
    fail_count: int = 0
    total_confidence_drop: float = 0.0
    avg_confidence_drop: float = 0.0
    best_drop: float = 0.0
    last_used: Optional[str] = None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def total_uses(self) -> int:
        return self.success_count + self.fail_count


class FixEffectivenessTracker:
    """Tracks and retrieves fix effectiveness data.

    Persists to JSON file. In production, would use the database
    (fix_effectiveness table), but file-based is simpler for now.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self._data_dir = Path(data_dir or Path(__file__).parent.parent.parent / "data")
        self._file = self._data_dir / "fix_effectiveness.json"
        self._records: Dict[str, FixEffectivenessRecord] = {}
        self._load()

    def _key(self, fix_type: str, detection_type: str) -> str:
        return f"{fix_type}:{detection_type}"

    def _load(self):
        if self._file.exists():
            try:
                with open(self._file) as f:
                    data = json.load(f)
                for item in data.get("records", []):
                    key = self._key(item["fix_type"], item["detection_type"])
                    self._records[key] = FixEffectivenessRecord(**item)
            except Exception as e:
                logger.warning("Failed to load fix effectiveness data: %s", e)

    def _save(self):
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "records": [
                {
                    "fix_type": r.fix_type,
                    "detection_type": r.detection_type,
                    "success_count": r.success_count,
                    "fail_count": r.fail_count,
                    "total_confidence_drop": r.total_confidence_drop,
                    "avg_confidence_drop": r.avg_confidence_drop,
                    "best_drop": r.best_drop,
                    "last_used": r.last_used,
                }
                for r in self._records.values()
            ],
        }
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._file, "w") as f:
            json.dump(data, f, indent=2)

    def record_outcome(
        self,
        fix_type: str,
        detection_type: str,
        before_confidence: float,
        after_confidence: float,
        success: bool,
    ):
        """Record the outcome of applying a fix."""
        key = self._key(fix_type, detection_type)
        if key not in self._records:
            self._records[key] = FixEffectivenessRecord(
                fix_type=fix_type, detection_type=detection_type
            )

        rec = self._records[key]
        drop = before_confidence - after_confidence
        if success:
            rec.success_count += 1
        else:
            rec.fail_count += 1
        rec.total_confidence_drop += drop
        rec.avg_confidence_drop = rec.total_confidence_drop / rec.total_uses
        rec.best_drop = max(rec.best_drop, drop)
        rec.last_used = datetime.now(timezone.utc).isoformat()
        self._save()

    def get_effectiveness(
        self, fix_type: str, detection_type: str
    ) -> Optional[FixEffectivenessRecord]:
        """Get effectiveness record for a fix type + detection type."""
        return self._records.get(self._key(fix_type, detection_type))

    def rank_fixes_for_detection(
        self, detection_type: str, fix_types: List[str]
    ) -> List[Tuple[str, float]]:
        """Rank fix types by historical effectiveness for a detection type.

        Returns list of (fix_type, score) sorted by score descending.
        Score combines success rate + average confidence drop.
        """
        scored = []
        for ft in fix_types:
            rec = self.get_effectiveness(ft, detection_type)
            if rec and rec.total_uses >= 1:
                # Score = 0.6 * success_rate + 0.4 * normalized_avg_drop
                score = 0.6 * rec.success_rate + 0.4 * min(1.0, rec.avg_confidence_drop)
            else:
                score = 0.5  # Unknown — neutral score
            scored.append((ft, score))

        scored.sort(key=lambda x: -x[1])
        return scored

    def seed_from_e2e_results(self, results_path: Optional[str] = None):
        """Seed effectiveness data from E2E healing test results."""
        path = Path(results_path or self._data_dir / "healing_e2e_results.json")
        if not path.exists():
            logger.info("No E2E results to seed from: %s", path)
            return

        with open(path) as f:
            data = json.load(f)

        seeded = 0
        for r in data.get("results", []):
            if r.get("result") in ("SKIP", "ERROR"):
                continue
            det_type = r.get("detector", "")
            before = r.get("before", 0)
            after = r.get("after", 0)
            success = r.get("result") in ("FIXED", "PARTIAL")

            # Map detector to likely fix type
            fix_type = _detector_to_fix_type(det_type)
            if fix_type:
                self.record_outcome(fix_type, det_type, before, after, success)
                seeded += 1

        logger.info("Seeded %d fix effectiveness records from E2E results", seeded)


def _detector_to_fix_type(det_type: str) -> Optional[str]:
    """Map detector type to the most common fix type applied."""
    mapping = {
        "loop": "retry_limit",
        "corruption": "state_validation",
        "persona_drift": "prompt_reinforcement",
        "hallucination": "fact_checking",
        "injection": "input_filtering",
        "overflow": "context_pruning",
        "derailment": "task_anchoring",
        "context": "task_anchoring",
        "communication": "message_schema",
        "specification": "spec_validation",
        "decomposition": "task_decomposer",
        "completion": "completion_gate",
        "convergence": "strategy_switch",
        "delegation": "task_decomposer",
        "n8n_timeout": "timeout_addition",
        "n8n_error": "step_validator",
        "n8n_schema": "schema_enforcement",
        "n8n_cycle": "circuit_breaker",
        "n8n_resource": "budget_limiter",
        "n8n_complexity": "circuit_breaker",
        "grounding": "source_grounding",
    }
    # Framework detectors
    if det_type.startswith("openclaw_"):
        return "safety_boundary"
    if det_type.startswith("dify_"):
        return "workflow_guard"
    if det_type.startswith("langgraph_"):
        return "step_validator"
    return mapping.get(det_type)


# Singleton
fix_tracker = FixEffectivenessTracker()
