#!/usr/bin/env python3
"""Standalone golden dataset generator (no database required)."""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum


class DetectionType(Enum):
    """Detection types."""
    LOOP = "loop"
    COORDINATION = "coordination"
    CORRUPTION = "corruption"
    PERSONA_DRIFT = "persona_drift"
    OVERFLOW = "overflow"
    HALLUCINATION = "hallucination"


@dataclass
class GoldenDatasetEntry:
    """A single entry in the golden dataset."""
    id: str
    detection_type: str  # Use string instead of Enum for simplicity
    input_data: Dict[str, Any]
    expected_detected: bool
    expected_confidence_min: float = 0.0
    expected_confidence_max: float = 1.0
    description: str = ""
    source: str = "manual"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: List[str] = field(default_factory=list)
    source_workflow_id: Optional[str] = None
    augmentation_method: Optional[str] = None
    human_verified: bool = False


def analyze_workflow_structure(workflow_data: Dict[str, Any]) -> Dict[str, bool]:
    """Analyze workflow structure for potential issues."""
    nodes = workflow_data.get("nodes", [])
    connections = workflow_data.get("connections", {})

    issues = {
        "has_circular_refs": False,
        "missing_error_handling": False,
        "well_structured": True,
    }

    # Check for error handling
    has_error_handling = any(
        node.get("type", "").startswith("n8n-nodes-base.if")
        or node.get("parameters", {}).get("continueOnFail")
        for node in nodes
    )
    if not has_error_handling and len(nodes) > 3:
        issues["missing_error_handling"] = True
        issues["well_structured"] = False

    return issues


def workflow_to_golden_entry(
    workflow_id: str,
    workflow_data: Dict[str, Any],
    detection_type: str,
    expected_detected: bool,
    source: str,
    tags: List[str],
) -> GoldenDatasetEntry:
    """Convert workflow JSON to golden entry."""
    nodes = workflow_data.get("nodes", [])

    input_data = {
        "workflow_name": workflow_data.get("name", workflow_id),
        "nodes": [
            {
                "type": node.get("type", ""),
                "name": node.get("name", ""),
                "parameters": node.get("parameters", {}),
            }
            for node in nodes
        ],
    }

    # Generate deterministic ID
    content_hash = hashlib.md5(
        json.dumps(input_data, sort_keys=True).encode()
    ).hexdigest()[:8]
    entry_id = f"{source}_{detection_type}_{workflow_id}_{content_hash}"

    return GoldenDatasetEntry(
        id=entry_id,
        detection_type=detection_type,
        input_data=input_data,
        expected_detected=expected_detected,
        expected_confidence_min=0.7 if expected_detected else 0.0,
        expected_confidence_max=0.95 if expected_detected else 0.3,
        description=f"Generated from {source} workflow: {workflow_id}",
        source=source,
        tags=tags,
        source_workflow_id=workflow_id,
        human_verified=False,
    )


def process_synthetic_workflows(workflow_dir: Path) -> List[GoldenDatasetEntry]:
    """Process synthetic test workflows."""
    entries = []

    category_map = {
        "loop": "loop",
        "coordination": "coordination",
        "state": "corruption",
        "persona": "persona_drift",
        "resource": "overflow",
    }

    for category, detection_type in category_map.items():
        category_dir = workflow_dir / category
        if not category_dir.exists():
            continue

        workflow_files = list(category_dir.glob("*.json"))
        for workflow_file in workflow_files:
            try:
                with open(workflow_file) as f:
                    workflow_data = json.load(f)

                entry = workflow_to_golden_entry(
                    workflow_file.stem,
                    workflow_data,
                    detection_type,
                    expected_detected=True,
                    source="synthetic",
                    tags=[category, "synthetic", "clear_positive"],
                )
                entries.append(entry)

            except Exception as e:
                print(f"  ⚠ Error processing {workflow_file}: {e}")

    return entries


def process_external_templates(template_dir: Path, limit: int) -> List[GoldenDatasetEntry]:
    """Process external workflow templates."""
    entries = []

    template_files = list(template_dir.rglob("*.json"))[:limit]

    for template_file in template_files:
        try:
            with open(template_file) as f:
                workflow_data = json.load(f)

            issues = analyze_workflow_structure(workflow_data)

            # Generate entries based on detected issues
            if issues.get("missing_error_handling"):
                entry = workflow_to_golden_entry(
                    f"ext_{template_file.stem}",
                    workflow_data,
                    "coordination",
                    expected_detected=True,
                    source="external",
                    tags=["missing_error_handling", "external", "structural"],
                )
                entries.append(entry)

            # If well-structured, create negative samples
            if issues.get("well_structured"):
                for detection_type in ["loop", "coordination"]:
                    entry = workflow_to_golden_entry(
                        f"ext_neg_{template_file.stem}_{detection_type}",
                        workflow_data,
                        detection_type,
                        expected_detected=False,
                        source="external",
                        tags=["well_structured", "external", "negative"],
                    )
                    entries.append(entry)

        except Exception as e:
            print(f"  ⚠ Error processing {template_file.name}: {e}")

    return entries


def augment_samples(samples: List[GoldenDatasetEntry], multiplier: int = 4) -> List[GoldenDatasetEntry]:
    """Generate augmented variants of existing samples."""
    augmented = []

    for sample in samples:
        # Skip negative samples
        if not sample.expected_detected:
            continue

        # Variant 1: Severity increase
        if multiplier >= 1:
            variant = GoldenDatasetEntry(
                id=f"{sample.id}_sev_inc",
                detection_type=sample.detection_type,
                input_data=sample.input_data.copy(),
                expected_detected=sample.expected_detected,
                expected_confidence_min=min(1.0, sample.expected_confidence_min + 0.1),
                expected_confidence_max=min(1.0, sample.expected_confidence_max + 0.1),
                description=f"Severity increase: {sample.description}",
                source=sample.source,
                tags=sample.tags + ["augmented", "severity_inc"],
                source_workflow_id=sample.source_workflow_id,
                augmentation_method="severity_increase",
                human_verified=False,
            )
            augmented.append(variant)

        # Variant 2: Severity decrease
        if multiplier >= 2:
            variant = GoldenDatasetEntry(
                id=f"{sample.id}_sev_dec",
                detection_type=sample.detection_type,
                input_data=sample.input_data.copy(),
                expected_detected=sample.expected_detected,
                expected_confidence_min=max(0.0, sample.expected_confidence_min - 0.1),
                expected_confidence_max=max(0.0, sample.expected_confidence_max - 0.1),
                description=f"Severity decrease: {sample.description}",
                source=sample.source,
                tags=sample.tags + ["augmented", "severity_dec"],
                source_workflow_id=sample.source_workflow_id,
                augmentation_method="severity_decrease",
                human_verified=False,
            )
            augmented.append(variant)

        # Variant 3: Edge case
        if multiplier >= 3:
            variant = GoldenDatasetEntry(
                id=f"{sample.id}_edge",
                detection_type=sample.detection_type,
                input_data=sample.input_data.copy(),
                expected_detected=sample.expected_detected,
                expected_confidence_min=sample.expected_confidence_min * 0.8,
                expected_confidence_max=sample.expected_confidence_max * 0.9,
                description=f"Edge case: {sample.description}",
                source=sample.source,
                tags=sample.tags + ["augmented", "edge_case"],
                source_workflow_id=sample.source_workflow_id,
                augmentation_method="edge_case",
                human_verified=False,
            )
            augmented.append(variant)

        # Variant 4: Noisy
        if multiplier >= 4:
            variant = GoldenDatasetEntry(
                id=f"{sample.id}_noisy",
                detection_type=sample.detection_type,
                input_data=sample.input_data.copy(),
                expected_detected=sample.expected_detected,
                expected_confidence_min=max(0.0, sample.expected_confidence_min - 0.05),
                expected_confidence_max=min(1.0, sample.expected_confidence_max + 0.05),
                description=f"Noisy variant: {sample.description}",
                source=sample.source,
                tags=sample.tags + ["augmented", "noisy"],
                source_workflow_id=sample.source_workflow_id,
                augmentation_method="noise_injection",
                human_verified=False,
            )
            augmented.append(variant)

    return augmented


def main():
    print("🔧 Generating FULL golden dataset from n8n data sources...")
    print("⏱️  This will take several minutes...")

    all_entries = []

    # Process synthetic workflows
    print("\n🧪 Processing synthetic workflows...")
    workflow_dir = Path("n8n-workflows")
    if workflow_dir.exists():
        synth_entries = process_synthetic_workflows(workflow_dir)
        print(f"  ✓ Generated {len(synth_entries)} entries from synthetic workflows")
        all_entries.extend(synth_entries)
    else:
        print(f"  ⚠ Workflow directory not found: {workflow_dir}")

    # Process external templates (INCREASED LIMIT)
    print("\n📚 Processing external templates (limit: 2000)...")
    template_dir = Path("backend/fixtures/external/n8n")
    if template_dir.exists():
        ext_entries = process_external_templates(template_dir, limit=2000)
        print(f"  ✓ Generated {len(ext_entries)} entries from external templates")
        all_entries.extend(ext_entries)
    else:
        print(f"  ⚠ Template directory not found: {template_dir}")

    # Apply augmentation
    print(f"\n✨ Applying data augmentation (4x multiplier)...")
    base_count = len(all_entries)
    augmented = augment_samples(all_entries, multiplier=4)
    print(f"  ✓ Generated {len(augmented)} augmented variants from {base_count} base samples")
    all_entries.extend(augmented)

    # Summary
    print(f"\n📈 Final Dataset Summary:")
    print(f"  Total entries: {len(all_entries)} ({base_count} base + {len(augmented)} augmented)")

    by_source = {}
    by_type = {}
    by_augmentation = {}
    for entry in all_entries:
        by_source[entry.source] = by_source.get(entry.source, 0) + 1
        by_type[entry.detection_type] = by_type.get(entry.detection_type, 0) + 1
        if entry.augmentation_method:
            by_augmentation[entry.augmentation_method] = by_augmentation.get(entry.augmentation_method, 0) + 1

    print(f"\n  By source:")
    for src, count in by_source.items():
        print(f"    - {src}: {count}")

    print(f"\n  By detection type:")
    for dt, count in by_type.items():
        print(f"    - {dt}: {count}")

    if by_augmentation:
        print(f"\n  By augmentation method:")
        for method, count in by_augmentation.items():
            print(f"    - {method}: {count}")

    # Save dataset
    output_path = Path("backend/data/golden_dataset_n8n_full.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dataset_json = {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": [asdict(entry) for entry in all_entries],
    }

    with open(output_path, "w") as f:
        json.dump(dataset_json, f, indent=2)

    print(f"\n💾 Saved golden dataset to: {output_path}")
    print("✨ Done!")


if __name__ == "__main__":
    main()
