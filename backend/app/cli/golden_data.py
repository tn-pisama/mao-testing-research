"""CLI commands for golden dataset generation and management."""

import click
import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.storage.database import get_db
from app.storage.models import Trace, Detection
from app.detection_enterprise.golden_generator import GoldenDataGenerator
from app.detection_enterprise.golden_dataset import GoldenDataset


@click.group()
def golden():
    """Manage golden datasets for detection validation."""
    pass


@golden.command()
@click.option(
    "--source",
    type=click.Choice(["production", "synthetic", "external", "all"]),
    default="all",
    help="Data source to generate from",
)
@click.option(
    "--output",
    type=click.Path(),
    default="backend/data/golden_dataset.json",
    help="Output path for golden dataset",
)
@click.option(
    "--limit",
    type=int,
    default=1000,
    help="Limit for external templates processing",
)
@click.option(
    "--augment/--no-augment",
    default=True,
    help="Whether to apply data augmentation",
)
@click.option(
    "--augment-multiplier",
    type=int,
    default=4,
    help="Number of augmented variants per sample",
)
def generate(
    source: str,
    output: str,
    limit: int,
    augment: bool,
    augment_multiplier: int,
):
    """Generate golden dataset from available data sources."""
    click.echo("🔧 Initializing golden data generator...")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize generator
    db = next(get_db())
    generator = GoldenDataGenerator(db)

    all_entries = []

    # Generate from production data
    if source in ["production", "all"]:
        click.echo("\n📊 Processing production data...")
        traces = db.query(Trace).filter(Trace.framework == "n8n").all()
        detections = db.query(Detection).join(Trace).filter(Trace.framework == "n8n").all()

        prod_entries = generator.from_production_traces(traces, detections)
        click.echo(f"  ✓ Generated {len(prod_entries)} entries from production")
        all_entries.extend(prod_entries)

    # Generate from synthetic workflows
    if source in ["synthetic", "all"]:
        click.echo("\n🧪 Processing synthetic workflows...")
        workflow_dir = Path("n8n-workflows")
        if workflow_dir.exists():
            synth_entries = generator.from_synthetic_workflows(workflow_dir)
            click.echo(f"  ✓ Generated {len(synth_entries)} entries from synthetic")
            all_entries.extend(synth_entries)
        else:
            click.echo("  ⚠ Synthetic workflow directory not found")

    # Generate from external templates
    if source in ["external", "all"]:
        click.echo(f"\n📚 Processing external templates (limit: {limit})...")
        template_dir = Path("backend/fixtures/external/n8n")
        if template_dir.exists():
            ext_entries = generator.from_external_templates(template_dir, limit=limit)
            click.echo(f"  ✓ Generated {len(ext_entries)} entries from external")
            all_entries.extend(ext_entries)
        else:
            click.echo("  ⚠ External template directory not found")

    # Apply augmentation
    if augment and all_entries:
        click.echo(f"\n✨ Applying data augmentation (multiplier: {augment_multiplier})...")
        augmented = generator.augment_samples(all_entries, multiplier=augment_multiplier)
        click.echo(f"  ✓ Generated {len(augmented)} augmented variants")
        all_entries.extend(augmented)

    # Validate
    click.echo("\n✅ Validating generated dataset...")
    validation_report = generator.validate_samples(all_entries)

    click.echo(f"\n📈 Generation Summary:")
    click.echo(f"  Total entries: {validation_report['total_samples']}")
    click.echo(f"\n  By source:")
    for src, count in validation_report["by_source"].items():
        click.echo(f"    - {src}: {count}")

    click.echo(f"\n  By detection type:")
    for dt, stats in validation_report["by_type"].items():
        click.echo(f"    - {dt}: {stats['total']} ({stats['positive']} pos, {stats['negative']} neg)")

    if validation_report["issues"]:
        click.echo(f"\n⚠ Issues found:")
        for issue in validation_report["issues"]:
            click.echo(f"    - {issue}")

    # Save dataset
    dataset = GoldenDataset()
    for entry in all_entries:
        dataset.add_entry(entry)

    dataset.save(output_path)
    click.echo(f"\n💾 Saved golden dataset to: {output_path}")
    click.echo("✨ Done!")


@golden.command()
@click.argument("dataset_path", type=click.Path(exists=True))
def validate(dataset_path: str):
    """Validate an existing golden dataset."""
    click.echo(f"🔍 Validating dataset: {dataset_path}")

    dataset = GoldenDataset(Path(dataset_path))
    summary = dataset.summary()

    click.echo(f"\n📊 Dataset Summary:")
    click.echo(f"  Total entries: {summary['total_entries']}")

    click.echo(f"\n  By detection type:")
    for dt, stats in summary["by_type"].items():
        click.echo(f"    - {dt}: {stats['total']} ({stats['positive']} pos, {stats['negative']} neg)")

    # Check balance
    click.echo(f"\n⚖️  Balance Analysis:")
    for dt, stats in summary["by_type"].items():
        if stats["total"] > 0:
            pos_ratio = stats["positive"] / stats["total"]
            if pos_ratio < 0.2 or pos_ratio > 0.8:
                click.echo(f"  ⚠ {dt}: Imbalanced ({pos_ratio:.1%} positive)")
            else:
                click.echo(f"  ✓ {dt}: Balanced ({pos_ratio:.1%} positive)")

    click.echo("\n✅ Validation complete!")


@golden.command()
@click.argument("dataset_path", type=click.Path(exists=True))
@click.option("--type", "detection_type", help="Filter by detection type")
@click.option("--tag", help="Filter by tag")
@click.option("--limit", type=int, default=10, help="Number of entries to show")
def show(dataset_path: str, detection_type: Optional[str], tag: Optional[str], limit: int):
    """Show entries from a golden dataset."""
    dataset = GoldenDataset(Path(dataset_path))

    entries = list(dataset.entries.values())

    # Apply filters
    if detection_type:
        from app.detection.validation import DetectionType
        dt = DetectionType(detection_type)
        entries = [e for e in entries if e.detection_type == dt]

    if tag:
        entries = [e for e in entries if tag in e.tags]

    # Show entries
    click.echo(f"\n📋 Showing {min(len(entries), limit)} of {len(entries)} entries:\n")

    for i, entry in enumerate(entries[:limit]):
        click.echo(f"Entry {i+1}: {entry.id}")
        click.echo(f"  Type: {entry.detection_type.value}")
        click.echo(f"  Expected: {'DETECTED' if entry.expected_detected else 'CLEAN'}")
        click.echo(f"  Confidence: {entry.expected_confidence_min:.2f}-{entry.expected_confidence_max:.2f}")
        click.echo(f"  Source: {entry.source}")
        click.echo(f"  Tags: {', '.join(entry.tags)}")
        if entry.description:
            click.echo(f"  Description: {entry.description}")
        click.echo("")


if __name__ == "__main__":
    golden()
