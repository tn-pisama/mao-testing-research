"""Episodic Memory Service for per-tenant adaptive detection.

Learns from detection feedback to adjust thresholds, suppress known
false positives, and calibrate confidence per tenant. New tenants get
default behavior (no row = None context); tuning kicks in after enough
feedback accumulates.

All DB queries hit indexed columns for <5ms lookup. Stats updates use
INSERT ON CONFLICT (upsert) to avoid race conditions.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import TenantDetectorStats, TenantPatternCache

logger = logging.getLogger(__name__)


@dataclass
class TenantDetectionContext:
    """Per-tenant detection parameters looked up before each detector run."""

    adjusted_threshold: float
    confidence_multiplier: float  # 0.5 - 1.5
    suppressed_pattern_hashes: set
    detection_frequency_24h: int
    historical_precision: float
    historical_recall: float
    learning_enabled: bool


def compute_adjusted_threshold(
    base: float,
    precision: float,
    recall: float,
    total_feedback: int,
    max_adj: float = 0.15,
) -> float:
    """Compute an adjusted detection threshold from feedback stats.

    - High FP rate (low precision) -> raise threshold to reduce FPs
    - High FN rate (low recall)    -> lower threshold to catch more
    - Balanced                     -> small nudge toward equilibrium
    - Damped by feedback volume (need >= 5 samples to move at all)
    """
    if total_feedback < 5:
        return base
    damping = min(1.0, total_feedback / 50)
    if precision < 0.5:
        direction = (0.5 - precision) * damping
    elif recall < 0.5:
        direction = -(0.5 - recall) * damping
    else:
        direction = (precision - recall) * 0.1 * damping
    clamped = max(-max_adj, min(max_adj, direction))
    return max(0.1, min(0.9, base + clamped))


def _compute_confidence_multiplier(precision: float, total_feedback: int) -> float:
    """Map historical precision to a confidence multiplier (0.5 - 1.5).

    High precision -> boost confidence (multiplier > 1).
    Low precision  -> dampen confidence (multiplier < 1).
    Not enough data -> neutral (1.0).
    """
    if total_feedback < 5:
        return 1.0
    # Linear mapping: precision 0.0 -> 0.5, precision 1.0 -> 1.5
    return max(0.5, min(1.5, 0.5 + precision))


def _compute_rates(tp: int, fp: int, fn: int):
    """Compute precision, recall, F1 from confusion counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.5
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.5
    if (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    return precision, recall, f1


def hash_input(input_data: dict) -> str:
    """SHA-256 hash of deterministically serialised input_data."""
    return hashlib.sha256(
        json.dumps(input_data, sort_keys=True, default=str).encode()
    ).hexdigest()


class EpisodicMemoryService:
    """Per-tenant episodic memory for adaptive detection.

    Provides fast context lookups, detection recording, feedback ingestion,
    FP suppression checks, and confidence adjustment -- all scoped to a
    single tenant.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Context lookup
    # ------------------------------------------------------------------

    async def get_tenant_context(
        self, detection_type: str, framework: Optional[str] = None,
    ) -> Optional[TenantDetectionContext]:
        """Fast lookup (<5ms) of tenant-specific detection parameters.

        Returns None when the tenant has no stats row for this detector,
        meaning the orchestrator should use default behavior.
        """
        stmt = select(TenantDetectorStats).where(
            TenantDetectorStats.tenant_id == self.tenant_id,
            TenantDetectorStats.detection_type == detection_type,
            TenantDetectorStats.framework == framework,
        )
        result = await self.session.execute(stmt)
        stats = result.scalar_one_or_none()
        if stats is None:
            return None

        # Load suppressed patterns for this detector
        pattern_stmt = select(TenantPatternCache.pattern_hash).where(
            TenantPatternCache.tenant_id == self.tenant_id,
            TenantPatternCache.detection_type == detection_type,
            TenantPatternCache.pattern_type == "false_positive",
            TenantPatternCache.is_active.is_(True),
        )
        pattern_result = await self.session.execute(pattern_stmt)
        suppressed = {row[0] for row in pattern_result.fetchall()}

        total_feedback = stats.true_positives + stats.false_positives + stats.false_negatives + stats.true_negatives

        return TenantDetectionContext(
            adjusted_threshold=stats.adjusted_threshold,
            confidence_multiplier=_compute_confidence_multiplier(stats.precision, total_feedback),
            suppressed_pattern_hashes=suppressed,
            detection_frequency_24h=stats.detection_frequency_24h,
            historical_precision=stats.precision,
            historical_recall=stats.recall,
            learning_enabled=stats.learning_enabled,
        )

    # ------------------------------------------------------------------
    # Record a detection event
    # ------------------------------------------------------------------

    async def record_detection(
        self,
        detection_type: str,
        confidence: float,
        detected: bool,
        framework: Optional[str] = None,
        input_hash: Optional[str] = None,
    ) -> None:
        """Record a detection event, incrementally updating stats.

        Uses INSERT ON CONFLICT to create or update the stats row atomically.
        """
        now = datetime.now(timezone.utc)
        values = {
            "tenant_id": self.tenant_id,
            "detection_type": detection_type,
            "framework": framework,
            "total_detections": 1,
            "last_detection_at": now,
            "detection_frequency_24h": 1,
        }
        insert_stmt = pg_insert(TenantDetectorStats).values(**values)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_tenant_detector_stats",
            set_={
                "total_detections": TenantDetectorStats.total_detections + 1,
                "last_detection_at": now,
                "detection_frequency_24h": TenantDetectorStats.detection_frequency_24h + 1,
                "updated_at": now,
            },
        )
        await self.session.execute(upsert_stmt)

    # ------------------------------------------------------------------
    # Record feedback
    # ------------------------------------------------------------------

    async def record_feedback(
        self,
        detection_id: UUID,
        feedback_type: str,
        detection_type: str,
        confidence: float,
        framework: Optional[str] = None,
        input_data: Optional[dict] = None,
    ) -> None:
        """Record feedback, update stats, recompute threshold, and cache FP patterns.

        Args:
            detection_id: UUID of the detection being rated.
            feedback_type: One of true_positive, false_positive, false_negative, true_negative.
            detection_type: The detector name (e.g. "loop", "corruption").
            confidence: The original detection confidence.
            framework: Optional framework string.
            input_data: Optional input dict for FP pattern hashing.
        """
        now = datetime.now(timezone.utc)

        # Map feedback_type to column increments
        increment_col = {
            "true_positive": "true_positives",
            "false_positive": "false_positives",
            "false_negative": "false_negatives",
            "true_negative": "true_negatives",
        }.get(feedback_type)

        if increment_col is None:
            logger.warning("Unknown feedback_type %s, skipping", feedback_type)
            return

        # Upsert: create stats row if it doesn't exist, then increment
        values = {
            "tenant_id": self.tenant_id,
            "detection_type": detection_type,
            "framework": framework,
            increment_col: 1,
            "last_feedback_at": now,
        }
        insert_stmt = pg_insert(TenantDetectorStats).values(**values)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_tenant_detector_stats",
            set_={
                increment_col: getattr(TenantDetectorStats, increment_col) + 1,
                "last_feedback_at": now,
                "updated_at": now,
            },
        )
        await self.session.execute(upsert_stmt)

        # Reload stats to recompute derived fields
        stmt = select(TenantDetectorStats).where(
            TenantDetectorStats.tenant_id == self.tenant_id,
            TenantDetectorStats.detection_type == detection_type,
            TenantDetectorStats.framework == framework,
        )
        result = await self.session.execute(stmt)
        stats = result.scalar_one_or_none()
        if stats is None:
            return

        # Recompute precision, recall, F1
        precision, recall, f1 = _compute_rates(
            stats.true_positives, stats.false_positives, stats.false_negatives,
        )
        total_feedback = stats.true_positives + stats.false_positives + stats.false_negatives + stats.true_negatives

        # Recompute adjusted threshold
        adjusted = compute_adjusted_threshold(
            stats.base_threshold, precision, recall, total_feedback,
        )

        # Build reason string
        if adjusted != stats.base_threshold:
            reason = (
                f"Auto-adjusted from {stats.base_threshold:.3f} -> {adjusted:.3f} "
                f"(P={precision:.2f} R={recall:.2f} F1={f1:.2f}, "
                f"n={total_feedback})"
            )
        else:
            reason = stats.threshold_adjustment_reason

        await self.session.execute(
            update(TenantDetectorStats)
            .where(TenantDetectorStats.id == stats.id)
            .values(
                precision=precision,
                recall=recall,
                f1=f1,
                adjusted_threshold=adjusted,
                threshold_adjustment_reason=reason,
                updated_at=now,
            )
        )

        # If false positive with input data, cache the pattern
        if feedback_type == "false_positive" and input_data:
            await self._cache_fp_pattern(
                detection_type=detection_type,
                framework=framework,
                input_data=input_data,
                detection_id=detection_id,
                confidence=confidence,
            )

    async def _cache_fp_pattern(
        self,
        detection_type: str,
        framework: Optional[str],
        input_data: dict,
        detection_id: UUID,
        confidence: float,
    ) -> None:
        """Cache a false-positive pattern hash for future suppression."""
        p_hash = hash_input(input_data)
        summary = json.dumps(input_data, default=str)[:500]

        # Check if this pattern already exists
        stmt = select(TenantPatternCache).where(
            TenantPatternCache.tenant_id == self.tenant_id,
            TenantPatternCache.pattern_hash == p_hash,
            TenantPatternCache.detection_type == detection_type,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.occurrence_count += 1
            existing.confidence = min(1.0, existing.confidence + 0.1)
            existing.is_active = True
        else:
            pattern = TenantPatternCache(
                tenant_id=self.tenant_id,
                detection_type=detection_type,
                framework=framework,
                pattern_hash=p_hash,
                pattern_summary=summary,
                pattern_type="false_positive",
                confidence=confidence,
                occurrence_count=1,
                source_detection_id=detection_id,
                is_active=True,
            )
            self.session.add(pattern)

    # ------------------------------------------------------------------
    # FP suppression check
    # ------------------------------------------------------------------

    async def should_suppress(
        self,
        detection_type: str,
        input_data: dict,
        framework: Optional[str] = None,
    ) -> tuple:
        """Check if a detection should be suppressed as a likely FP.

        Returns:
            (should_suppress: bool, reason: Optional[str])
        """
        p_hash = hash_input(input_data)

        stmt = select(TenantPatternCache).where(
            TenantPatternCache.tenant_id == self.tenant_id,
            TenantPatternCache.detection_type == detection_type,
            TenantPatternCache.pattern_hash == p_hash,
            TenantPatternCache.pattern_type == "false_positive",
            TenantPatternCache.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        pattern = result.scalar_one_or_none()

        if pattern is None:
            return False, None

        # Require at least 2 occurrences and confidence >= 0.6 to suppress
        if pattern.occurrence_count >= 2 and pattern.confidence >= 0.6:
            return True, (
                f"Suppressed: pattern seen {pattern.occurrence_count}x as FP "
                f"(confidence={pattern.confidence:.2f})"
            )

        return False, None

    # ------------------------------------------------------------------
    # Confidence adjustment
    # ------------------------------------------------------------------

    async def adjust_confidence(
        self,
        detection_type: str,
        raw_confidence: float,
        framework: Optional[str] = None,
    ) -> float:
        """Adjust confidence based on historical accuracy.

        Multiplies raw_confidence by a precision-derived multiplier.
        Returns the raw value if no tenant context exists.
        """
        ctx = await self.get_tenant_context(detection_type, framework)
        if ctx is None:
            return raw_confidence
        adjusted = raw_confidence * ctx.confidence_multiplier
        return max(0.0, min(1.0, adjusted))
