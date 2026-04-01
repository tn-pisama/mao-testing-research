"""Golden dataset for detection validation and calibration."""

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from app.detection.validation import DetectionType, LabeledSample, DetectionPrediction


@dataclass
class GoldenDatasetEntry:
    """A single entry in the golden dataset."""
    id: str
    detection_type: DetectionType
    input_data: Dict[str, Any]
    expected_detected: bool
    expected_confidence_min: float = 0.0
    expected_confidence_max: float = 1.0
    description: str = ""
    source: str = "manual"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: List[str] = field(default_factory=list)
    source_trace_id: Optional[str] = None
    source_workflow_id: Optional[str] = None
    augmentation_method: Optional[str] = None
    human_verified: bool = False
    difficulty: str = "easy"  # easy, medium, hard
    split: str = "train"  # train, val, test

    def to_labeled_sample(self) -> LabeledSample:
        return LabeledSample(
            sample_id=self.id,
            detection_type=self.detection_type,
            input_data=self.input_data,
            ground_truth=self.expected_detected,
            ground_truth_confidence=(self.expected_confidence_min + self.expected_confidence_max) / 2,
            metadata={
                "description": self.description,
                "source": self.source,
                "tags": self.tags,
            },
        )


class GoldenDataset:
    """Manages a golden dataset for detection validation."""

    def __init__(self, dataset_path: Optional[Path] = None):
        self.entries: Dict[str, GoldenDatasetEntry] = {}
        self.dataset_path = dataset_path
        if dataset_path and dataset_path.exists():
            self.load(dataset_path)

    def add_entry(self, entry: GoldenDatasetEntry) -> None:
        self.entries[entry.id] = entry

    def remove_entry(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            return True
        return False

    def cap_per_type(self, max_per_type: int) -> int:
        """Trim entries so no detection type exceeds max_per_type. Returns count removed."""
        import random
        by_type: Dict[DetectionType, List[str]] = {}
        for eid, entry in self.entries.items():
            by_type.setdefault(entry.detection_type, []).append(eid)
        removed = 0
        for dt, ids in by_type.items():
            if len(ids) > max_per_type:
                random.seed(42)
                to_remove = random.sample(ids, len(ids) - max_per_type)
                for eid in to_remove:
                    del self.entries[eid]
                removed += len(to_remove)
        return removed

    def get_entries_by_type(self, detection_type: DetectionType) -> List[GoldenDatasetEntry]:
        return [e for e in self.entries.values() if e.detection_type == detection_type]

    def get_entries_by_type_and_split(
        self, detection_type: DetectionType, splits: List[str],
    ) -> List[GoldenDatasetEntry]:
        """Get entries filtered by both detection type and split(s)."""
        return [
            e for e in self.entries.values()
            if e.detection_type == detection_type and e.split in splits
        ]

    def get_entries_by_tag(self, tag: str) -> List[GoldenDatasetEntry]:
        return [e for e in self.entries.values() if tag in e.tags]

    def get_difficulty_distribution(self, detection_type: DetectionType) -> Dict[str, int]:
        """Get count of entries per difficulty level for a detection type."""
        entries = self.get_entries_by_type(detection_type)
        dist: Dict[str, int] = {}
        for e in entries:
            dist[e.difficulty] = dist.get(e.difficulty, 0) + 1
        return dist

    def to_labeled_samples(self) -> List[LabeledSample]:
        return [e.to_labeled_sample() for e in self.entries.values()]

    def assign_splits(self, train: float = 0.70, val: float = 0.15, seed: int = 42) -> None:
        """Assign train/val/test splits stratified by detection type and label.

        Uses deterministic hashing so splits are reproducible across runs.
        Stratifies within each (detection_type, expected_detected) group so
        class balance is preserved per split.
        """
        # Group entries by (detection_type, expected_detected)
        groups: Dict[str, List[GoldenDatasetEntry]] = {}
        for entry in self.entries.values():
            key = f"{entry.detection_type.value}_{entry.expected_detected}"
            groups.setdefault(key, []).append(entry)

        for group_entries in groups.values():
            # Deterministic sort by entry ID hash for reproducibility
            sorted_entries = sorted(
                group_entries,
                key=lambda e: hashlib.md5(f"{seed}_{e.id}".encode()).hexdigest(),
            )
            n = len(sorted_entries)
            n_train = max(1, round(n * train))  # at least 1 in train
            n_val = round(n * val)
            # Remaining go to test
            for i, entry in enumerate(sorted_entries):
                if i < n_train:
                    entry.split = "train"
                elif i < n_train + n_val:
                    entry.split = "val"
                else:
                    entry.split = "test"

    def validate_splits(self) -> List[str]:
        """Check for content-identical entries across different splits.

        Returns a list of warning strings for each duplicate pair found.
        An empty list means no contamination detected.
        """
        from collections import defaultdict
        # Group entries by content hash
        content_hashes: Dict[str, List[GoldenDatasetEntry]] = defaultdict(list)
        for entry in self.entries.values():
            h = hashlib.sha256(
                json.dumps(entry.input_data, sort_keys=True).encode()
            ).hexdigest()[:16]
            content_hashes[h].append(entry)

        warnings_list: List[str] = []
        for h, entries in content_hashes.items():
            if len(entries) < 2:
                continue
            splits_seen = {e.split for e in entries}
            if len(splits_seen) > 1:
                ids = [e.id for e in entries]
                warnings_list.append(
                    f"Content-identical entries across splits {splits_seen}: {ids}"
                )
        return warnings_list

    def compute_content_hash(self) -> str:
        """Compute a SHA-256 hash of all entry content for versioning.

        Hashes sorted (id, detection_type, expected_detected, input_data_hash)
        tuples so the hash changes when any entry content changes, even if
        counts stay the same.
        """
        items = []
        for entry in sorted(self.entries.values(), key=lambda e: e.id):
            input_hash = hashlib.sha256(
                json.dumps(entry.input_data, sort_keys=True).encode()
            ).hexdigest()[:16]
            items.append(f"{entry.id}:{entry.detection_type.value}:{entry.expected_detected}:{input_hash}")
        combined = "\n".join(items)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def generate_manifest(self) -> Dict[str, Any]:
        """Generate a dataset manifest for reproducibility tracking.

        Returns a dict with version info, entry counts, content hash,
        and split distribution.
        """
        by_type: Dict[str, int] = {}
        by_split: Dict[str, int] = {}
        for entry in self.entries.values():
            dt = entry.detection_type.value
            by_type[dt] = by_type.get(dt, 0) + 1
            by_split[entry.split] = by_split.get(entry.split, 0) + 1

        return {
            "version": "1.0",
            "total_entries": len(self.entries),
            "content_hash": self.compute_content_hash(),
            "entries_by_type": dict(sorted(by_type.items())),
            "entries_by_split": dict(sorted(by_split.items())),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self, path: Optional[Path] = None) -> None:
        save_path = path or self.dataset_path
        if not save_path:
            raise ValueError("No path specified for saving")

        data = {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entries": [
                {
                    **asdict(e),
                    "detection_type": e.detection_type.value,
                }
                for e in self.entries.values()
            ],
        }

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: Path) -> None:
        if path.suffix == '.jsonl':
            self.load_jsonl(path)
        else:
            self.load_json(path)

    def load_json(
        self,
        path: Path,
        *,
        skip_types: Optional[set] = None,
        only_types: Optional[set] = None,
    ) -> None:
        """Load golden dataset from JSON format.

        Args:
            skip_types: Exclude entries with these detection types.
            only_types: If set, only load entries with these detection types.
        """
        with open(path) as f:
            data = json.load(f)

        entries = data.get("entries", []) if isinstance(data, dict) else data
        skipped_types: set = set()
        for entry_data in entries:
            try:
                entry_data["detection_type"] = DetectionType(entry_data["detection_type"])
            except ValueError:
                skipped_types.add(entry_data["detection_type"])
                continue
            dt = entry_data["detection_type"]
            if skip_types and dt in skip_types:
                continue
            if only_types and dt not in only_types:
                continue
            entry = GoldenDatasetEntry(**entry_data)
            self.entries[entry.id] = entry
        if skipped_types:
            logger.warning("Skipped unknown detection types in %s: %s", path.name, sorted(skipped_types))

    def load_jsonl(self, path: Path) -> None:
        """Load golden dataset from JSONL format (one entry per line)."""
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry_data = json.loads(line)
                entry_data["detection_type"] = DetectionType(entry_data["detection_type"])
                entry = GoldenDatasetEntry(**entry_data)
                self.entries[entry.id] = entry

    def summary(self) -> Dict[str, Any]:
        by_type = {}
        for dt in DetectionType:
            entries = self.get_entries_by_type(dt)
            if entries:
                positive = sum(1 for e in entries if e.expected_detected)
                splits = {}
                for split_name in ("train", "val", "test"):
                    split_entries = [e for e in entries if e.split == split_name]
                    if split_entries:
                        splits[split_name] = len(split_entries)
                by_type[dt.value] = {
                    "total": len(entries),
                    "positive": positive,
                    "negative": len(entries) - positive,
                    "splits": splits,
                }

        return {
            "total_entries": len(self.entries),
            "by_type": by_type,
        }


# ---------------------------------------------------------------------------
# Seed data loading from JSON
# ---------------------------------------------------------------------------

_GOLDEN_SEEDS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "golden_seeds.json"


def _load_seed_entries() -> List[GoldenDatasetEntry]:
    """Load built-in seed entries from golden_seeds.json."""
    with open(_GOLDEN_SEEDS_PATH) as f:
        data = json.load(f)
    entries = []
    for entry_data in data["entries"]:
        try:
            entry_data["detection_type"] = DetectionType(entry_data["detection_type"])
        except ValueError:
            continue
        entries.append(GoldenDatasetEntry(**entry_data))
    return entries


def create_default_golden_dataset(assign_splits: bool = True) -> GoldenDataset:
    """Create a golden dataset with default samples.

    Args:
        assign_splits: If True, assign deterministic train/val/test splits
            (70/15/15) stratified by detection type and label.
    """
    dataset = GoldenDataset()

    for sample in _load_seed_entries():
        dataset.add_entry(sample)

    # Load framework-specific golden entries from JSON data files
    from app.detection_enterprise.type_prompts_loader import load_golden_entries
    for source in ("claude_code", "convergence", "n8n"):
        for sample in load_golden_entries(source):
            dataset.add_entry(sample)

    # Framework-specific expanded golden datasets.
    _generic_types = {DetectionType.LOOP}
    _oc_types = {dt for dt in DetectionType if dt.value.startswith("openclaw_")} | _generic_types
    _dify_types = {dt for dt in DetectionType if dt.value.startswith("dify_")} | _generic_types
    _lg_types = {dt for dt in DetectionType if dt.value.startswith("langgraph_")} | _generic_types
    _n8n_types = {dt for dt in DetectionType if dt.value.startswith("n8n_")} | _generic_types
    data_dir = Path(__file__).parent.parent.parent / "data"
    _expanded_configs = [
        ("golden_dataset_openclaw_expanded.json", _oc_types),
        ("golden_dataset_dify_expanded.json", _dify_types),
        ("golden_dataset_langgraph_expanded.json", _lg_types),
        ("golden_dataset_n8n_expanded.json", _n8n_types),
    ]
    for filename, allowed in _expanded_configs:
        filepath = data_dir / filename
        if filepath.exists():
            dataset.load_json(filepath, only_types=allowed)
            logger.info("Loaded framework golden dataset: %s", filename)

    if assign_splits:
        dataset.assign_splits()

    return dataset


def get_golden_dataset_path() -> Path:
    """Get the default path for the golden dataset."""
    return Path(__file__).parent.parent.parent / "data" / "golden_dataset.json"


# ---------------------------------------------------------------------------
# Database-backed golden dataset
# ---------------------------------------------------------------------------

class GoldenDatasetDB(GoldenDataset):
    """Database-backed golden dataset that eagerly loads entries into memory.

    This subclass IS-A GoldenDataset, so all existing synchronous consumers
    (calibrate.py, test harness, train pipeline) work unchanged. The dataset
    is small enough (~2300 entries) to fit comfortably in memory.

    Usage::

        async with get_db() as session:
            dataset = await GoldenDatasetDB.from_db(session)
            # Use exactly like a regular GoldenDataset
            entries = dataset.get_entries_by_type(DetectionType.LOOP)
    """

    @classmethod
    async def from_db(
        cls,
        session,
        tenant_id=None,
    ) -> "GoldenDatasetDB":
        """Factory: load all entries from DB into memory.

        Args:
            session: An AsyncSession instance.
            tenant_id: Optional tenant UUID. If provided, includes both
                global (tenant_id=NULL) and tenant-specific entries.
        """
        from app.storage.golden_dataset_repo import (
            GoldenDatasetRepository,
            model_to_dataclass,
        )

        repo = GoldenDatasetRepository(session)
        models = await repo.get_all(tenant_id)
        instance = cls()
        for m in models:
            entry = model_to_dataclass(m)
            instance.entries[entry.id] = entry
        return instance


async def create_default_golden_dataset_from_db(
    session,
    tenant_id=None,
    assign_splits: bool = True,
) -> GoldenDataset:
    """Load the golden dataset from the database.

    Falls back to in-memory creation if the database table is empty,
    ensuring backward compatibility during migration.

    Args:
        session: An AsyncSession instance.
        tenant_id: Optional tenant UUID for scoped queries.
        assign_splits: If True and falling back to in-memory, assign splits.
    """
    from app.storage.golden_dataset_repo import GoldenDatasetRepository

    repo = GoldenDatasetRepository(session)
    count = await repo.count_total()

    if count > 0:
        return await GoldenDatasetDB.from_db(session, tenant_id)

    # Fallback: DB is empty, use in-memory default
    return create_default_golden_dataset(assign_splits)
