#!/usr/bin/env python3
"""Convert real n8n workflow JSON fixtures into golden dataset entries.

Loads ~200 random workflow JSON files from fixtures/external/n8n/, runs all 6
n8n detectors on each, and creates golden entries based on whether each
detector fires. Entries are merged into data/golden_dataset_external.json.

Usage:
    python -m scripts.generate_n8n_real_traces
    python -m scripts.generate_n8n_real_traces --limit 300
    python -m scripts.generate_n8n_real_traces --dry-run
"""

import argparse
import glob
import hashlib
import json
import logging
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDataset, GoldenDatasetEntry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("generate_n8n_real")

BACKEND_DIR = Path(__file__).resolve().parent.parent
FIXTURE_DIRS = [
    BACKEND_DIR / "fixtures" / "external" / "n8n" / "ai-templates",
    BACKEND_DIR / "fixtures" / "external" / "n8n" / "zie619-workflows" / "workflows",
]
EXTERNAL_DATASET_PATH = BACKEND_DIR / "data" / "golden_dataset_external.json"

N8N_DETECTOR_MAP = {
    DetectionType.N8N_CYCLE: ("app.detection.n8n.cycle_detector", "N8NCycleDetector"),
    DetectionType.N8N_ERROR: ("app.detection.n8n.error_detector", "N8NErrorDetector"),
    DetectionType.N8N_SCHEMA: ("app.detection.n8n.schema_detector", "N8NSchemaDetector"),
    DetectionType.N8N_COMPLEXITY: ("app.detection.n8n.complexity_detector", "N8NComplexityDetector"),
    DetectionType.N8N_TIMEOUT: ("app.detection.n8n.timeout_detector", "N8NTimeoutDetector"),
    DetectionType.N8N_RESOURCE: ("app.detection.n8n.resource_detector", "N8NResourceDetector"),
}

# Target entries per detector per label (positive/negative)
TARGET_PER_LABEL = 20


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate golden entries from real n8n workflow fixtures",
    )
    parser.add_argument(
        "--limit", type=int, default=200,
        help="Max workflow files to load (default: 200)",
    )
    parser.add_argument(
        "--target-per-label", type=int, default=TARGET_PER_LABEL,
        help="Target positive/negative entries per detector (default: 20)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show plan without saving",
    )
    return parser.parse_args()


def collect_workflow_files() -> list[Path]:
    """Find all .json workflow files in fixture directories."""
    files = []
    for d in FIXTURE_DIRS:
        if d.exists():
            files.extend(d.rglob("*.json"))
    return files


def load_workflow(path: Path) -> dict | None:
    """Load and validate a single n8n workflow JSON file."""
    try:
        with open(path) as f:
            data = json.load(f)
        # Must have nodes and connections
        if "nodes" not in data or "connections" not in data:
            return None
        if not isinstance(data["nodes"], list) or len(data["nodes"]) == 0:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def load_detectors() -> dict:
    """Import and instantiate all 6 n8n detectors."""
    import importlib

    detectors = {}
    for det_type, (module_path, class_name) in N8N_DETECTOR_MAP.items():
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            detectors[det_type] = cls()
            logger.info("Loaded detector: %s", det_type.value)
        except Exception as exc:
            logger.warning("Could not import %s: %s", det_type.value, exc)
    return detectors


def make_entry_id(det_type: DetectionType, workflow_name: str) -> str:
    """Create a deterministic entry ID from detector type and workflow name."""
    name_hash = hashlib.sha256(workflow_name.encode()).hexdigest()[:12]
    return f"n8n_real_{det_type.value}_{name_hash}"


def run_detectors_on_workflow(
    detectors: dict,
    workflow_data: dict,
) -> dict[DetectionType, tuple[bool, float]]:
    """Run all detectors on a single workflow. Returns {type: (detected, confidence)}."""
    results = {}
    for det_type, detector in detectors.items():
        try:
            result = detector.detect_workflow(workflow_data)
            results[det_type] = (result.detected, result.confidence)
        except Exception as exc:
            logger.debug(
                "Detector %s failed on workflow %s: %s",
                det_type.value,
                workflow_data.get("name", "unknown"),
                exc,
            )
    return results


def main():
    args = parse_args()
    random.seed(args.seed)

    # Step 1: Collect workflow files
    logger.info("Scanning fixture directories for workflow JSON files...")
    all_files = collect_workflow_files()
    logger.info("Found %d workflow files", len(all_files))

    if not all_files:
        logger.error("No workflow files found. Check fixture directories.")
        sys.exit(1)

    # Step 2: Sample
    sample_size = min(args.limit, len(all_files))
    sampled_files = random.sample(all_files, sample_size)
    logger.info("Sampled %d workflow files", sample_size)

    # Step 3: Load detectors
    detectors = load_detectors()
    if not detectors:
        logger.error("No detectors could be loaded.")
        sys.exit(1)
    logger.info("Loaded %d detectors", len(detectors))

    # Step 4: Run detectors on all workflows, collect results
    # Track positive/negative per detector type
    positives: dict[DetectionType, list[tuple[dict, float]]] = defaultdict(list)
    negatives: dict[DetectionType, list[tuple[dict, float]]] = defaultdict(list)

    loaded_count = 0
    for i, fpath in enumerate(sampled_files):
        workflow_data = load_workflow(fpath)
        if workflow_data is None:
            continue
        loaded_count += 1

        results = run_detectors_on_workflow(detectors, workflow_data)
        for det_type, (detected, confidence) in results.items():
            if detected:
                positives[det_type].append((workflow_data, confidence))
            else:
                negatives[det_type].append((workflow_data, confidence))

        if (i + 1) % 50 == 0:
            logger.info("Processed %d/%d files...", i + 1, sample_size)

    logger.info("Successfully loaded and processed %d workflows", loaded_count)

    # Step 5: Show detection rates
    logger.info("--- Detection rates ---")
    for det_type in N8N_DETECTOR_MAP:
        if det_type in detectors:
            pos_n = len(positives[det_type])
            neg_n = len(negatives[det_type])
            total = pos_n + neg_n
            rate = pos_n / total * 100 if total > 0 else 0
            logger.info(
                "  %s: %d positive / %d negative (%.1f%% detection rate)",
                det_type.value, pos_n, neg_n, rate,
            )

    # Step 6: Balance and create golden entries
    target = args.target_per_label
    entries: list[GoldenDatasetEntry] = []

    for det_type in N8N_DETECTOR_MAP:
        if det_type not in detectors:
            continue

        # Sample up to target positives
        pos_pool = positives[det_type]
        neg_pool = negatives[det_type]

        random.shuffle(pos_pool)
        random.shuffle(neg_pool)

        pos_selected = pos_pool[:target]
        neg_selected = neg_pool[:target]

        for workflow_data, confidence in pos_selected:
            wf_name = workflow_data.get("name", "unknown")
            entry_id = make_entry_id(det_type, wf_name)
            # Check for duplicate IDs and make unique
            existing_ids = {e.id for e in entries}
            if entry_id in existing_ids:
                extra = hashlib.sha256(
                    json.dumps(workflow_data, sort_keys=True).encode()
                ).hexdigest()[:6]
                entry_id = f"{entry_id}_{extra}"

            entries.append(GoldenDatasetEntry(
                id=entry_id,
                detection_type=det_type,
                input_data={"workflow_json": workflow_data},
                expected_detected=True,
                expected_confidence_min=max(0.0, confidence - 0.2),
                expected_confidence_max=min(1.0, confidence + 0.2),
                description=f"Real n8n workflow: {wf_name}",
                source="n8n_real",
                difficulty="medium",
                split="test",
                tags=["real_trace", "n8n", "fixture", "positive"],
            ))

        for workflow_data, confidence in neg_selected:
            wf_name = workflow_data.get("name", "unknown")
            entry_id = make_entry_id(det_type, wf_name)
            existing_ids = {e.id for e in entries}
            if entry_id in existing_ids:
                extra = hashlib.sha256(
                    json.dumps(workflow_data, sort_keys=True).encode()
                ).hexdigest()[:6]
                entry_id = f"{entry_id}_{extra}"

            entries.append(GoldenDatasetEntry(
                id=entry_id,
                detection_type=det_type,
                input_data={"workflow_json": workflow_data},
                expected_detected=False,
                expected_confidence_min=0.0,
                expected_confidence_max=0.3,
                description=f"Real n8n workflow (clean): {wf_name}",
                source="n8n_real",
                difficulty="medium",
                split="test",
                tags=["real_trace", "n8n", "fixture", "negative"],
            ))

    logger.info("Created %d golden entries total", len(entries))

    # Per-detector summary
    for det_type in N8N_DETECTOR_MAP:
        type_entries = [e for e in entries if e.detection_type == det_type]
        pos = sum(1 for e in type_entries if e.expected_detected)
        neg = len(type_entries) - pos
        logger.info("  %s: %d entries (%d+ / %d-)", det_type.value, len(type_entries), pos, neg)

    if args.dry_run:
        logger.info("Dry run - not saving.")
        return

    # Step 7: Merge into external golden dataset
    logger.info("Loading existing external dataset from %s", EXTERNAL_DATASET_PATH)
    dataset = GoldenDataset()
    if EXTERNAL_DATASET_PATH.exists():
        dataset.load(EXTERNAL_DATASET_PATH)
        logger.info("Loaded %d existing entries", len(dataset.entries))

    # Remove old n8n_real entries to avoid duplicates
    old_ids = [eid for eid in dataset.entries if dataset.entries[eid].source == "n8n_real"]
    for eid in old_ids:
        dataset.remove_entry(eid)
    if old_ids:
        logger.info("Removed %d old n8n_real entries", len(old_ids))

    # Add new entries
    for entry in entries:
        dataset.add_entry(entry)

    dataset.save(EXTERNAL_DATASET_PATH)
    logger.info(
        "Saved external dataset with %d total entries to %s",
        len(dataset.entries), EXTERNAL_DATASET_PATH,
    )


if __name__ == "__main__":
    main()
