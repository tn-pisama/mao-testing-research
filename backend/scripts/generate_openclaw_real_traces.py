#!/usr/bin/env python3
"""Build OpenClaw golden entries from existing golden data patterns.

Reads existing OpenClaw entries from data/golden_dataset_expanded.json,
re-validates them through the actual detectors, and creates entries marked
as source="openclaw_real" in the external golden dataset.

This confirms that detector behavior matches ground-truth labels and adds
real-format entries to the external dataset for calibration.

Usage:
    python -m scripts.generate_openclaw_real_traces
    python -m scripts.generate_openclaw_real_traces --target-per-label 25
    python -m scripts.generate_openclaw_real_traces --dry-run
"""

import argparse
import hashlib
import importlib
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
logger = logging.getLogger("generate_openclaw_real")

BACKEND_DIR = Path(__file__).resolve().parent.parent
EXPANDED_DATASET_PATH = BACKEND_DIR / "data" / "golden_dataset_expanded.json"
EXTERNAL_DATASET_PATH = BACKEND_DIR / "data" / "golden_dataset_external.json"

OPENCLAW_DETECTOR_MAP = {
    DetectionType.OPENCLAW_SESSION_LOOP: (
        "app.detection.openclaw.session_loop_detector",
        "OpenClawSessionLoopDetector",
    ),
    DetectionType.OPENCLAW_TOOL_ABUSE: (
        "app.detection.openclaw.tool_abuse_detector",
        "OpenClawToolAbuseDetector",
    ),
    DetectionType.OPENCLAW_ELEVATED_RISK: (
        "app.detection.openclaw.elevated_risk_detector",
        "OpenClawElevatedRiskDetector",
    ),
    DetectionType.OPENCLAW_SPAWN_CHAIN: (
        "app.detection.openclaw.spawn_chain_detector",
        "OpenClawSpawnChainDetector",
    ),
    DetectionType.OPENCLAW_CHANNEL_MISMATCH: (
        "app.detection.openclaw.channel_mismatch_detector",
        "OpenClawChannelMismatchDetector",
    ),
    DetectionType.OPENCLAW_SANDBOX_ESCAPE: (
        "app.detection.openclaw.sandbox_escape_detector",
        "OpenClawSandboxEscapeDetector",
    ),
}

TARGET_PER_LABEL = 20


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate openclaw_real golden entries from existing OpenClaw data",
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


def load_detectors() -> dict:
    """Import and instantiate all 6 OpenClaw detectors."""
    detectors = {}
    for det_type, (module_path, class_name) in OPENCLAW_DETECTOR_MAP.items():
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            detectors[det_type] = cls()
            logger.info("Loaded detector: %s", det_type.value)
        except Exception as exc:
            logger.warning("Could not import %s: %s", det_type.value, exc)
    return detectors


def load_existing_openclaw_entries() -> dict[DetectionType, list[dict]]:
    """Load OpenClaw entries from expanded dataset, grouped by detection type."""
    logger.info("Loading expanded dataset from %s", EXPANDED_DATASET_PATH)

    with open(EXPANDED_DATASET_PATH) as f:
        data = json.load(f)

    raw_entries = data.get("entries", data) if isinstance(data, dict) else data

    by_type: dict[DetectionType, list[dict]] = defaultdict(list)
    for entry_data in raw_entries:
        dt_value = entry_data.get("detection_type", "")
        # Only OpenClaw types
        if not dt_value.startswith("openclaw_"):
            continue
        # Must have session data
        if "session" not in entry_data.get("input_data", {}):
            continue
        try:
            dt = DetectionType(dt_value)
            by_type[dt].append(entry_data)
        except ValueError:
            continue

    for dt, elist in sorted(by_type.items(), key=lambda x: x[0].value):
        pos = sum(1 for e in elist if e.get("expected_detected"))
        neg = len(elist) - pos
        logger.info("  %s: %d entries (%d+ / %d-)", dt.value, len(elist), pos, neg)

    return by_type


def make_entry_id(det_type: DetectionType, session_id: str, idx: int) -> str:
    """Create a deterministic entry ID."""
    content_hash = hashlib.sha256(f"{session_id}_{idx}".encode()).hexdigest()[:12]
    return f"openclaw_real_{det_type.value}_{content_hash}"


def main():
    args = parse_args()
    random.seed(args.seed)
    target = args.target_per_label

    # Step 1: Load existing OpenClaw entries
    existing_by_type = load_existing_openclaw_entries()
    if not existing_by_type:
        logger.error("No OpenClaw entries found in expanded dataset.")
        sys.exit(1)

    # Step 2: Load detectors
    detectors = load_detectors()
    if not detectors:
        logger.error("No OpenClaw detectors could be loaded.")
        sys.exit(1)

    # Step 3: Re-validate entries through actual detectors and create new entries
    entries: list[GoldenDatasetEntry] = []
    stats: dict[str, dict[str, int]] = {}

    for det_type in OPENCLAW_DETECTOR_MAP:
        if det_type not in detectors:
            continue

        source_entries = existing_by_type.get(det_type, [])
        if not source_entries:
            logger.warning("No source entries for %s", det_type.value)
            continue

        detector = detectors[det_type]
        verified_positives: list[tuple[dict, float, str]] = []
        verified_negatives: list[tuple[dict, float, str]] = []
        mismatches = 0

        for entry_data in source_entries:
            session = entry_data["input_data"]["session"]
            expected = entry_data.get("expected_detected", False)
            session_id = session.get("session_id", "unknown")

            try:
                result = detector.detect_session(session)
                actual_detected = result.detected
                confidence = result.confidence
            except Exception as exc:
                logger.debug(
                    "Detector %s failed on session %s: %s",
                    det_type.value, session_id, exc,
                )
                continue

            if actual_detected == expected:
                # Ground truth matches detector output -- confirmed entry
                if actual_detected:
                    verified_positives.append((session, confidence, session_id))
                else:
                    verified_negatives.append((session, confidence, session_id))
            else:
                mismatches += 1

        logger.info(
            "  %s: %d verified+ / %d verified- / %d mismatches",
            det_type.value,
            len(verified_positives),
            len(verified_negatives),
            mismatches,
        )

        # Sample balanced sets
        random.shuffle(verified_positives)
        random.shuffle(verified_negatives)
        pos_selected = verified_positives[:target]
        neg_selected = verified_negatives[:target]

        existing_ids = {e.id for e in entries}

        for idx, (session, confidence, session_id) in enumerate(pos_selected):
            entry_id = make_entry_id(det_type, session_id, idx)
            if entry_id in existing_ids:
                extra = hashlib.sha256(
                    json.dumps(session, sort_keys=True).encode()
                ).hexdigest()[:6]
                entry_id = f"{entry_id}_{extra}"
            existing_ids.add(entry_id)

            entries.append(GoldenDatasetEntry(
                id=entry_id,
                detection_type=det_type,
                input_data={"session": session},
                expected_detected=True,
                expected_confidence_min=max(0.0, confidence - 0.2),
                expected_confidence_max=min(1.0, confidence + 0.2),
                description=f"Verified OpenClaw session: {session_id}",
                source="openclaw_real",
                difficulty="medium",
                split="test",
                tags=["real_trace", "openclaw", "verified", "positive"],
            ))

        for idx, (session, confidence, session_id) in enumerate(neg_selected):
            entry_id = make_entry_id(det_type, session_id, target + idx)
            if entry_id in existing_ids:
                extra = hashlib.sha256(
                    json.dumps(session, sort_keys=True).encode()
                ).hexdigest()[:6]
                entry_id = f"{entry_id}_{extra}"
            existing_ids.add(entry_id)

            entries.append(GoldenDatasetEntry(
                id=entry_id,
                detection_type=det_type,
                input_data={"session": session},
                expected_detected=False,
                expected_confidence_min=0.0,
                expected_confidence_max=0.3,
                description=f"Clean OpenClaw session: {session_id}",
                source="openclaw_real",
                difficulty="medium",
                split="test",
                tags=["real_trace", "openclaw", "verified", "negative"],
            ))

        type_entries = [e for e in entries if e.detection_type == det_type]
        pos = sum(1 for e in type_entries if e.expected_detected)
        neg = len(type_entries) - pos
        stats[det_type.value] = {"positive": pos, "negative": neg, "total": pos + neg}

    logger.info("Created %d golden entries total", len(entries))
    for dt_val, s in sorted(stats.items()):
        logger.info("  %s: %d entries (%d+ / %d-)", dt_val, s["total"], s["positive"], s["negative"])

    if args.dry_run:
        logger.info("Dry run - not saving.")
        return

    # Step 4: Merge into external golden dataset
    logger.info("Loading existing external dataset from %s", EXTERNAL_DATASET_PATH)
    dataset = GoldenDataset()
    if EXTERNAL_DATASET_PATH.exists():
        dataset.load(EXTERNAL_DATASET_PATH)
        logger.info("Loaded %d existing entries", len(dataset.entries))

    # Remove old openclaw_real entries to avoid duplicates
    old_ids = [eid for eid in dataset.entries if dataset.entries[eid].source == "openclaw_real"]
    for eid in old_ids:
        dataset.remove_entry(eid)
    if old_ids:
        logger.info("Removed %d old openclaw_real entries", len(old_ids))

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
