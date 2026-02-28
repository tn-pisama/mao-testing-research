"""Async repository for golden dataset entries in PostgreSQL."""

import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func, update, delete, case, literal
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import GoldenDatasetEntryModel

logger = logging.getLogger(__name__)


class GoldenDatasetRepository:
    """Async database-backed repository for golden dataset entries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_entry(self, entry: GoldenDatasetEntryModel) -> GoldenDatasetEntryModel:
        """Add a single entry. Returns the persisted model."""
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def add_entries_bulk(self, entries: List[GoldenDatasetEntryModel]) -> int:
        """Bulk insert entries, skipping duplicates on entry_key conflict.

        Returns the number of entries actually inserted.
        """
        if not entries:
            return 0

        values = []
        for e in entries:
            values.append({
                "id": e.id or uuid.uuid4(),
                "tenant_id": e.tenant_id,
                "entry_key": e.entry_key,
                "detection_type": e.detection_type,
                "input_data": e.input_data,
                "expected_detected": e.expected_detected,
                "expected_confidence_min": e.expected_confidence_min or 0.0,
                "expected_confidence_max": e.expected_confidence_max or 1.0,
                "description": e.description or "",
                "source": e.source or "manual",
                "tags": e.tags if e.tags is not None else [],
                "difficulty": e.difficulty or "easy",
                "split": e.split or "train",
                "source_trace_id": e.source_trace_id,
                "source_workflow_id": e.source_workflow_id,
                "augmentation_method": e.augmentation_method,
                "human_verified": e.human_verified or False,
                "entry_metadata": e.entry_metadata if e.entry_metadata is not None else {},
            })

        stmt = pg_insert(GoldenDatasetEntryModel).values(values)
        stmt = stmt.on_conflict_do_nothing(index_elements=["entry_key"])
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_by_key(self, entry_key: str) -> Optional[GoldenDatasetEntryModel]:
        """Get a single entry by its human-readable key."""
        stmt = select(GoldenDatasetEntryModel).where(
            GoldenDatasetEntryModel.entry_key == entry_key
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_entries_by_type(
        self,
        detection_type: str,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> List[GoldenDatasetEntryModel]:
        """Get entries by detection type. Includes global (tenant_id=NULL) entries."""
        stmt = select(GoldenDatasetEntryModel).where(
            GoldenDatasetEntryModel.detection_type == detection_type
        )
        if tenant_id is not None:
            stmt = stmt.where(
                (GoldenDatasetEntryModel.tenant_id.is_(None))
                | (GoldenDatasetEntryModel.tenant_id == tenant_id)
            )
        else:
            stmt = stmt.where(GoldenDatasetEntryModel.tenant_id.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_entries_by_type_and_split(
        self,
        detection_type: str,
        splits: List[str],
        tenant_id: Optional[uuid.UUID] = None,
    ) -> List[GoldenDatasetEntryModel]:
        """Get entries filtered by detection type and split(s)."""
        stmt = select(GoldenDatasetEntryModel).where(
            GoldenDatasetEntryModel.detection_type == detection_type,
            GoldenDatasetEntryModel.split.in_(splits),
        )
        if tenant_id is not None:
            stmt = stmt.where(
                (GoldenDatasetEntryModel.tenant_id.is_(None))
                | (GoldenDatasetEntryModel.tenant_id == tenant_id)
            )
        else:
            stmt = stmt.where(GoldenDatasetEntryModel.tenant_id.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_entries_by_tag(self, tag: str) -> List[GoldenDatasetEntryModel]:
        """Get entries containing a specific tag (uses GIN index)."""
        stmt = select(GoldenDatasetEntryModel).where(
            GoldenDatasetEntryModel.tags.contains([tag])
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(
        self,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> List[GoldenDatasetEntryModel]:
        """Get all entries, optionally scoped to a tenant (plus globals)."""
        stmt = select(GoldenDatasetEntryModel)
        if tenant_id is not None:
            stmt = stmt.where(
                (GoldenDatasetEntryModel.tenant_id.is_(None))
                | (GoldenDatasetEntryModel.tenant_id == tenant_id)
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_total(self) -> int:
        """Count total entries in the table."""
        stmt = select(func.count()).select_from(GoldenDatasetEntryModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_by_type(self) -> Dict[str, int]:
        """Count entries grouped by detection_type."""
        stmt = (
            select(
                GoldenDatasetEntryModel.detection_type,
                func.count().label("cnt"),
            )
            .group_by(GoldenDatasetEntryModel.detection_type)
        )
        result = await self.session.execute(stmt)
        return {row.detection_type: row.cnt for row in result}

    async def summary(self) -> Dict[str, Any]:
        """Return a summary matching GoldenDataset.summary() format."""
        total = await self.count_total()
        type_counts = await self.count_by_type()

        # Per-type breakdown with positive/negative counts
        by_type: Dict[str, Any] = {}
        for det_type, count in type_counts.items():
            pos_stmt = (
                select(func.count())
                .select_from(GoldenDatasetEntryModel)
                .where(
                    GoldenDatasetEntryModel.detection_type == det_type,
                    GoldenDatasetEntryModel.expected_detected.is_(True),
                )
            )
            pos_result = await self.session.execute(pos_stmt)
            positive = pos_result.scalar() or 0

            by_type[det_type] = {
                "total": count,
                "positive": positive,
                "negative": count - positive,
            }

        return {
            "total_entries": total,
            "by_type": by_type,
        }

    async def assign_splits(
        self,
        train: float = 0.70,
        val: float = 0.15,
        seed: int = 42,
    ) -> None:
        """Assign train/val/test splits, stratified by (detection_type, expected_detected).

        Uses deterministic hashing for reproducibility.
        """
        all_entries = await self.get_all()

        # Group by (detection_type, expected_detected)
        groups: Dict[str, List[GoldenDatasetEntryModel]] = {}
        for entry in all_entries:
            key = f"{entry.detection_type}_{entry.expected_detected}"
            groups.setdefault(key, []).append(entry)

        updates = []  # (entry_key, new_split) pairs
        for group_entries in groups.values():
            sorted_entries = sorted(
                group_entries,
                key=lambda e: hashlib.md5(f"{seed}_{e.entry_key}".encode()).hexdigest(),
            )
            n = len(sorted_entries)
            n_train = max(1, round(n * train))
            n_val = round(n * val)

            for i, entry in enumerate(sorted_entries):
                if i < n_train:
                    new_split = "train"
                elif i < n_train + n_val:
                    new_split = "val"
                else:
                    new_split = "test"
                if entry.split != new_split:
                    updates.append((entry.entry_key, new_split))

        # Batch update
        if updates:
            for entry_key, new_split in updates:
                stmt = (
                    update(GoldenDatasetEntryModel)
                    .where(GoldenDatasetEntryModel.entry_key == entry_key)
                    .values(split=new_split)
                )
                await self.session.execute(stmt)
            await self.session.flush()
            logger.info("Updated splits for %d entries", len(updates))

    async def remove_entry(self, entry_key: str) -> bool:
        """Remove an entry by key. Returns True if deleted."""
        stmt = delete(GoldenDatasetEntryModel).where(
            GoldenDatasetEntryModel.entry_key == entry_key
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# Conversion utilities
# ---------------------------------------------------------------------------

def model_to_dataclass(model: GoldenDatasetEntryModel):
    """Convert a DB model to the existing GoldenDatasetEntry dataclass."""
    from app.detection.validation import DetectionType
    from app.detection_enterprise.golden_dataset import GoldenDatasetEntry

    return GoldenDatasetEntry(
        id=model.entry_key,
        detection_type=DetectionType(model.detection_type),
        input_data=model.input_data,
        expected_detected=model.expected_detected,
        expected_confidence_min=model.expected_confidence_min or 0.0,
        expected_confidence_max=model.expected_confidence_max or 1.0,
        description=model.description or "",
        source=model.source or "manual",
        created_at=model.created_at.isoformat() if model.created_at else "",
        tags=model.tags or [],
        source_trace_id=model.source_trace_id,
        source_workflow_id=model.source_workflow_id,
        augmentation_method=model.augmentation_method,
        human_verified=model.human_verified or False,
        difficulty=model.difficulty or "easy",
        split=model.split or "train",
    )


def dataclass_to_model(
    entry,
    tenant_id: Optional[uuid.UUID] = None,
) -> GoldenDatasetEntryModel:
    """Convert a GoldenDatasetEntry dataclass to a DB model."""
    return GoldenDatasetEntryModel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        entry_key=entry.id,
        detection_type=(
            entry.detection_type.value
            if hasattr(entry.detection_type, "value")
            else str(entry.detection_type)
        ),
        input_data=entry.input_data,
        expected_detected=entry.expected_detected,
        expected_confidence_min=getattr(entry, "expected_confidence_min", 0.0),
        expected_confidence_max=getattr(entry, "expected_confidence_max", 1.0),
        description=getattr(entry, "description", ""),
        source=getattr(entry, "source", "manual"),
        tags=getattr(entry, "tags", []),
        difficulty=getattr(entry, "difficulty", "easy"),
        split=getattr(entry, "split", "train"),
        source_trace_id=getattr(entry, "source_trace_id", None),
        source_workflow_id=getattr(entry, "source_workflow_id", None),
        augmentation_method=getattr(entry, "augmentation_method", None),
        human_verified=getattr(entry, "human_verified", False),
        entry_metadata=getattr(entry, "metadata", {}) if hasattr(entry, "metadata") else {},
    )
