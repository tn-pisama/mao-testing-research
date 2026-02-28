#!/usr/bin/env python3
"""CLI for generating OpenClaw-native golden dataset entries using Claude API.

Usage:
    python -m scripts.generate_openclaw_golden_dataset --target-per-type 100
    python -m scripts.generate_openclaw_golden_dataset --dry-run
    python -m scripts.generate_openclaw_golden_dataset --resume --types loop,corruption
    python -m scripts.generate_openclaw_golden_dataset --validate-only
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDataset
from app.detection_enterprise.openclaw_golden_data_generator import OpenClawGoldenDataGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("generate_openclaw")

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "golden_dataset_openclaw_expanded.json"

ALL_TYPE_NAMES = [dt.value for dt in DetectionType]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate OpenClaw-native golden dataset entries using Claude API",
    )
    parser.add_argument(
        "--target-per-type", type=int, default=100,
        help="Target entries per detection type (default: 100)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=None,
        help="Entries per API call (default: auto — 5 for session, 8 for text types)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output JSON file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Continue from existing output file (skip types at target)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print generation plan without calling API",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Load existing file and re-validate all entries",
    )
    parser.add_argument(
        "--types", type=str, default=None,
        help=f"Comma-separated types to generate (default: all). Available: {', '.join(ALL_TYPE_NAMES)}",
    )
    parser.add_argument(
        "--difficulty-distribution", type=str, default="0.20,0.45,0.35",
        help="Easy,medium,hard ratio (default: 0.20,0.45,0.35)",
    )
    parser.add_argument(
        "--model-easy", type=str, default=None,
        help="Override model for easy entries (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--model-hard", type=str, default=None,
        help="Override model for medium/hard entries (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Disable prompt caching",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Delay between API calls in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="Anthropic API key (default: ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--to-db", action="store_true",
        help="Write generated entries directly to PostgreSQL (requires DATABASE_URL)",
    )
    parser.add_argument(
        "--from-db", action="store_true",
        help="Read entries from PostgreSQL for validation (with --validate-only)",
    )
    return parser.parse_args()


def parse_detection_types(types_str: str) -> list:
    """Parse comma-separated detection type names into DetectionType list."""
    names = [t.strip() for t in types_str.split(",")]
    types = []
    for name in names:
        try:
            types.append(DetectionType(name))
        except ValueError:
            logger.error("Unknown detection type: %s (available: %s)", name, ", ".join(ALL_TYPE_NAMES))
            sys.exit(1)
    return types


def validate_existing(output_path: Path):
    """Load and re-validate all entries in the existing dataset."""
    if not output_path.exists():
        logger.error("File not found: %s", output_path)
        sys.exit(1)

    dataset = GoldenDataset(output_path)
    total = len(dataset.entries)
    logger.info("Loaded %d entries from %s", total, output_path)

    # Schema validation
    valid_count = 0
    invalid_count = 0
    errors_by_type: dict = {}

    try:
        from app.detection_enterprise.input_schemas import validate_input
    except ImportError:
        logger.error("input_schemas not available")
        sys.exit(1)

    try:
        from app.detection_enterprise.openclaw_session_validator import validate_openclaw_input_data
        has_oc_validator = True
    except ImportError:
        has_oc_validator = False
        logger.warning("openclaw_session_validator not available, skipping OpenClaw validation")

    for entry in dataset.entries.values():
        type_key = entry.detection_type.value

        # Standard schema validation
        ok, err = validate_input(type_key, entry.input_data)
        if not ok:
            invalid_count += 1
            errors_by_type.setdefault(type_key, []).append(f"[{entry.id}] {err}")
            continue

        # OpenClaw-specific validation
        if has_oc_validator:
            ok, err = validate_openclaw_input_data(type_key, entry.input_data)
            if not ok:
                invalid_count += 1
                errors_by_type.setdefault(type_key, []).append(f"[{entry.id}] openclaw: {err}")
                continue

        valid_count += 1

    # Print summary
    print(f"\n{'='*60}")
    print(f"Validation Results: {output_path.name}")
    print(f"{'='*60}")
    print(f"Total entries:   {total}")
    print(f"Valid:           {valid_count}")
    print(f"Invalid:         {invalid_count}")

    if errors_by_type:
        print(f"\nErrors by type:")
        for type_key, errs in sorted(errors_by_type.items()):
            print(f"  {type_key}: {len(errs)} errors")
            for e in errs[:3]:
                print(f"    - {e}")
            if len(errs) > 3:
                print(f"    ... and {len(errs) - 3} more")

    # Per-type breakdown
    print(f"\nPer-type breakdown:")
    summary = dataset.summary()
    for type_key, info in sorted(summary.get("by_type", {}).items()):
        oc_entries = [e for e in dataset.get_entries_by_type(DetectionType(type_key)) if "openclaw" in e.tags]
        difficulties = {}
        for e in oc_entries:
            difficulties[e.difficulty] = difficulties.get(e.difficulty, 0) + 1
        diff_str = ", ".join(f"{k}={v}" for k, v in sorted(difficulties.items()))
        print(f"  {type_key:30s}: {len(oc_entries):4d} openclaw entries ({diff_str})")

    print(f"{'='*60}")


def validate_from_db():
    """Validate entries loaded from the database."""
    import asyncio
    from app.detection_enterprise.golden_dataset import GoldenDatasetDB
    from app.storage.database import async_session_maker

    async def _load():
        async with async_session_maker() as session:
            return await GoldenDatasetDB.from_db(session)

    dataset = asyncio.run(_load())
    total = len(dataset.entries)
    logger.info("Loaded %d entries from database", total)

    # Schema validation
    valid_count = 0
    invalid_count = 0
    errors_by_type: dict = {}

    try:
        from app.detection_enterprise.input_schemas import validate_input
    except ImportError:
        logger.error("input_schemas not available")
        sys.exit(1)

    for entry in dataset.entries.values():
        type_key = entry.detection_type.value
        ok, err = validate_input(type_key, entry.input_data)
        if not ok:
            invalid_count += 1
            errors_by_type.setdefault(type_key, []).append(f"[{entry.id}] {err}")
            continue
        valid_count += 1

    print(f"\n{'='*60}")
    print(f"DB Validation Results")
    print(f"{'='*60}")
    print(f"Total entries:   {total}")
    print(f"Valid:           {valid_count}")
    print(f"Invalid:         {invalid_count}")

    if errors_by_type:
        print(f"\nErrors by type:")
        for type_key, errs in sorted(errors_by_type.items()):
            print(f"  {type_key}: {len(errs)} errors")
            for e in errs[:3]:
                print(f"    - {e}")
            if len(errs) > 3:
                print(f"    ... and {len(errs) - 3} more")

    summary = dataset.summary()
    print(f"\nPer-type breakdown:")
    for type_key, info in sorted(summary.get("by_type", {}).items()):
        print(f"  {type_key:30s}: {info['total']:4d} entries (pos={info['positive']}, neg={info['negative']})")
    print(f"{'='*60}")


def main():
    args = parse_args()

    # Parse difficulty distribution
    try:
        dist = tuple(float(x) for x in args.difficulty_distribution.split(","))
        if len(dist) != 3 or abs(sum(dist) - 1.0) > 0.01:
            raise ValueError
    except ValueError:
        logger.error("Invalid difficulty distribution: %s (must be 3 floats summing to 1.0)", args.difficulty_distribution)
        sys.exit(1)

    # Parse detection types
    types = None
    if args.types:
        types = parse_detection_types(args.types)

    # Validate-only mode
    if args.validate_only:
        if getattr(args, "from_db", False):
            validate_from_db()
        else:
            validate_existing(args.output)
        return

    # Create generator
    generator = OpenClawGoldenDataGenerator(
        api_key=args.api_key,
        easy_model=args.model_easy,
        hard_model=args.model_hard,
        use_cache=not args.no_cache,
        delay_between_calls=args.delay,
    )

    # Dry run mode (no API key needed)
    if args.dry_run:
        existing = None
        if args.resume and args.output.exists():
            existing = GoldenDataset(args.output)
            logger.info("Loaded %d existing entries for resume calculation", len(existing.entries))

        plan = generator.dry_run(
            detection_types=types,
            target_per_type=args.target_per_type,
            difficulty_distribution=dist,
            existing_dataset=existing,
        )

        print(f"\n{'='*60}")
        print("DRY RUN — OpenClaw Generation Plan")
        print(f"{'='*60}")

        for type_key, info in sorted(plan.items()):
            if type_key.startswith("_"):
                continue
            if info.get("status") == "skip":
                print(f"  {type_key:30s}: SKIP (already {info['existing']} entries)")
            else:
                print(
                    f"  {type_key:30s}: {info['needed']:4d} needed "
                    f"(E={info['easy']}, M={info['medium']}, H={info['hard']}) "
                    f"→ {info['api_calls']} API calls"
                )

        summary = plan.get("_summary", {})
        print(f"\nTotal entries to generate: {summary.get('total_entries_to_generate', 0)}")
        print(f"Total API calls:          {summary.get('total_api_calls', 0)}")
        print(f"Estimated input tokens:   {summary.get('estimated_input_tokens', 0):,}")
        print(f"Estimated output tokens:  {summary.get('estimated_output_tokens', 0):,}")
        print(f"Estimated cost:           ${summary.get('estimated_cost_usd', 0):.2f}")
        print(f"{'='*60}")
        return

    # Full generation — requires API key
    if not generator.is_available:
        logger.error(
            "Generator not available. Set ANTHROPIC_API_KEY or pass --api-key. "
            "Install anthropic SDK: pip install anthropic"
        )
        sys.exit(1)

    logger.info("Starting OpenClaw golden dataset generation")
    logger.info("Target: %d per type, output: %s, resume: %s", args.target_per_type, args.output, args.resume)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Get DB session if --to-db
    db_session = None
    if getattr(args, "to_db", False):
        import asyncio
        from app.storage.database import async_session_maker
        _async_session = asyncio.get_event_loop().run_until_complete(
            async_session_maker().__aenter__()
        )
        db_session = _async_session
        logger.info("Writing entries to database (--to-db)")

    stats = generator.generate_batch(
        detection_types=types,
        target_per_type=args.target_per_type,
        difficulty_distribution=dist,
        output_path=args.output,
        resume=args.resume,
        batch_size=args.batch_size,
        db_session=db_session,
    )

    if db_session:
        import asyncio
        asyncio.get_event_loop().run_until_complete(db_session.__aexit__(None, None, None))

    # Print summary
    summary = stats.get("_summary", {})
    print(f"\n{'='*60}")
    print("OpenClaw Generation Complete")
    print(f"{'='*60}")
    print(f"Total generated:    {summary.get('total_generated', 0)}")
    print(f"Total in dataset:   {summary.get('total_entries', 0)}")
    print(f"API calls:          {summary.get('api_calls', 0)}")
    print(f"Input tokens:       {summary.get('input_tokens', 0):,}")
    print(f"Output tokens:      {summary.get('output_tokens', 0):,}")
    print(f"Estimated cost:     ${summary.get('estimated_cost_usd', 0):.2f}")
    print(f"Output file:        {args.output}")

    print(f"\nPer-type results:")
    for type_key, info in sorted(stats.items()):
        if type_key.startswith("_"):
            continue
        if info.get("skipped"):
            print(f"  {type_key:30s}: SKIPPED (existing: {info.get('existing', 0)})")
        else:
            print(
                f"  {type_key:30s}: {info.get('generated', 0):4d} generated, "
                f"{info.get('errors', 0)} errors, {info.get('retries', 0)} retries"
            )

    print(f"{'='*60}")


if __name__ == "__main__":
    main()
