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


def main():
    print("🔧 Generating golden dataset from n8n data sources...")

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

    # Process external templates
    print("\n📚 Processing external templates (limit: 100)...")
    template_dir = Path("backend/fixtures/external/n8n")
    if template_dir.exists():
        ext_entries = process_external_templates(template_dir, limit=100)
        print(f"  ✓ Generated {len(ext_entries)} entries from external templates")
        all_entries.extend(ext_entries)
    else:
        print(f"  ⚠ Template directory not found: {template_dir}")

    # Summary
    print(f"\n📈 Generation Summary:")
    print(f"  Total entries: {len(all_entries)}")

    by_source = {}
    by_type = {}
    for entry in all_entries:
        by_source[entry.source] = by_source.get(entry.source, 0) + 1
        by_type[entry.detection_type] = by_type.get(entry.detection_type, 0) + 1

    print(f"\n  By source:")
    for src, count in by_source.items():
        print(f"    - {src}: {count}")

    print(f"\n  By detection type:")
    for dt, count in by_type.items():
        print(f"    - {dt}: {count}")

    # Save dataset
    output_path = Path("backend/data/golden_dataset_n8n.json")
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
