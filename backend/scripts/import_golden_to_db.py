#!/usr/bin/env python3
"""Import golden dataset from JSON files and hardcoded samples into PostgreSQL.

One-time migration script. Idempotent (uses ON CONFLICT DO NOTHING on entry_key).

Usage:
    python -m scripts.import_golden_to_db
    python -m scripts.import_golden_to_db --json-path data/golden_dataset_n8n_expanded.json
    python -m scripts.import_golden_to_db --dry-run
    python -m scripts.import_golden_to_db --no-hardcoded
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDataset, create_default_golden_dataset
from app.storage.golden_dataset_repo import GoldenDatasetRepository, dataclass_to_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("import_golden")

DEFAULT_JSON = Path(__file__).resolve().parent.parent / "data" / "golden_dataset_n8n_expanded.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import golden dataset into PostgreSQL",
    )
    parser.add_argument(
        "--json-path", type=Path, default=DEFAULT_JSON,
        help=f"Path to JSON dataset file (default: {DEFAULT_JSON})",
    )
    parser.add_argument(
        "--no-hardcoded", action="store_true",
        help="Skip importing hardcoded in-code samples",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be imported without writing to DB",
    )
    parser.add_argument(
        "--assign-splits", action="store_true",
        help="Run split assignment after import",
    )
    return parser.parse_args()


async def import_golden_dataset(
    json_path: Path,
    include_hardcoded: bool = True,
    dry_run: bool = False,
    assign_splits: bool = False,
):
    """Import golden dataset entries into PostgreSQL."""
    from app.storage.database import async_session_maker

    # 1. Collect all entries
    all_entries = {}

    # Load hardcoded samples first (lower priority on conflict)
    if include_hardcoded:
        logger.info("Loading hardcoded in-code samples...")
        hardcoded = create_default_golden_dataset(assign_splits=False)
        for key, entry in hardcoded.entries.items():
            all_entries[key] = entry
        logger.info("  Loaded %d hardcoded entries", len(hardcoded.entries))

    # Load JSON file (higher priority — overwrites hardcoded on conflict)
    if json_path.exists():
        logger.info("Loading JSON file: %s", json_path)
        file_dataset = GoldenDataset(json_path)
        for key, entry in file_dataset.entries.items():
            all_entries[key] = entry
        logger.info("  Loaded %d entries from JSON", len(file_dataset.entries))
    else:
        logger.warning("JSON file not found: %s", json_path)

    logger.info("Total unique entries to import: %d", len(all_entries))

    # Print summary
    type_counts = {}
    for entry in all_entries.values():
        dt = entry.detection_type.value if hasattr(entry.detection_type, "value") else str(entry.detection_type)
        type_counts[dt] = type_counts.get(dt, 0) + 1

    print(f"\n{'='*60}")
    print(f"Import Plan: {len(all_entries)} entries across {len(type_counts)} types")
    print(f"{'='*60}")
    for dt, count in sorted(type_counts.items()):
        print(f"  {dt:25s}: {count:4d}")
    print(f"{'='*60}")

    if dry_run:
        print("\nDRY RUN — no database changes made.")
        return

    # 2. Convert to DB models
    models = [dataclass_to_model(entry) for entry in all_entries.values()]

    # 3. Bulk insert in batches
    batch_size = 500
    total_inserted = 0

    async with async_session_maker() as session:
        repo = GoldenDatasetRepository(session)

        for i in range(0, len(models), batch_size):
            batch = models[i:i + batch_size]
            inserted = await repo.add_entries_bulk(batch)
            total_inserted += inserted
            logger.info(
                "  Batch %d/%d: inserted %d entries",
                i // batch_size + 1,
                (len(models) + batch_size - 1) // batch_size,
                inserted,
            )

        if assign_splits:
            logger.info("Assigning train/val/test splits...")
            await repo.assign_splits()

        await session.commit()

    print(f"\nImport complete: {total_inserted} entries inserted into golden_dataset_entries")

    # 4. Verify
    async with async_session_maker() as session:
        repo = GoldenDatasetRepository(session)
        summary = await repo.summary()
        total = summary["total_entries"]
        print(f"Total entries in DB: {total}")
        print(f"\nPer-type counts:")
        for dt, info in sorted(summary["by_type"].items()):
            print(f"  {dt:25s}: {info['total']:4d} (pos={info['positive']}, neg={info['negative']})")


def main():
    args = parse_args()
    asyncio.run(
        import_golden_dataset(
            json_path=args.json_path,
            include_hardcoded=not args.no_hardcoded,
            dry_run=args.dry_run,
            assign_splits=args.assign_splits,
        )
    )


if __name__ == "__main__":
    main()
