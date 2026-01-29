#!/usr/bin/env python3
"""Generate golden dataset from n8n data sources."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.detection_enterprise.golden_generator import GoldenDataGenerator
from app.detection_enterprise.golden_dataset import GoldenDataset


def main():
    print("🔧 Generating golden dataset from n8n data sources...")

    generator = GoldenDataGenerator()
    all_entries = []

    # Generate from synthetic workflows
    print("\n🧪 Processing synthetic workflows...")
    workflow_dir = Path("n8n-workflows")
    if workflow_dir.exists():
        synth_entries = generator.from_synthetic_workflows(workflow_dir)
        print(f"  ✓ Generated {len(synth_entries)} entries from synthetic workflows")
        all_entries.extend(synth_entries)
    else:
        print(f"  ⚠ Workflow directory not found: {workflow_dir}")

    # Generate from external templates (limited to 100 for speed)
    print("\n📚 Processing external templates (limit: 100)...")
    template_dir = Path("backend/fixtures/external/n8n")
    if template_dir.exists():
        ext_entries = generator.from_external_templates(template_dir, limit=100)
        print(f"  ✓ Generated {len(ext_entries)} entries from external templates")
        all_entries.extend(ext_entries)
    else:
        print(f"  ⚠ Template directory not found: {template_dir}")

    # Apply augmentation
    if all_entries:
        print(f"\n✨ Applying data augmentation (multiplier: 4)...")
        augmented = generator.augment_samples(all_entries, multiplier=4)
        print(f"  ✓ Generated {len(augmented)} augmented variants")
        all_entries.extend(augmented)

    # Validate
    print("\n✅ Validating generated dataset...")
    validation_report = generator.validate_samples(all_entries)

    print(f"\n📈 Generation Summary:")
    print(f"  Total entries: {validation_report['total_samples']}")
    print(f"\n  By source:")
    for src, count in validation_report["by_source"].items():
        print(f"    - {src}: {count}")

    print(f"\n  By detection type:")
    for dt, stats in validation_report["by_type"].items():
        print(f"    - {dt}: {stats['total']} ({stats['positive']} pos, {stats['negative']} neg)")

    if validation_report["issues"]:
        print(f"\n⚠ Issues found:")
        for issue in validation_report["issues"]:
            print(f"    - {issue}")

    # Save dataset
    output_path = Path("backend/data/golden_dataset_n8n.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dataset = GoldenDataset()
    for entry in all_entries:
        dataset.add_entry(entry)

    dataset.save(output_path)
    print(f"\n💾 Saved golden dataset to: {output_path}")
    print("✨ Done!")


if __name__ == "__main__":
    main()
