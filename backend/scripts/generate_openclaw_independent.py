#!/usr/bin/env python3
"""Generate independently-labeled OpenClaw golden entries for 6 detectors.

Labels are computed from STRUCTURAL analysis of session data (event counts,
field matching, etc.), NOT from running Pisama detectors. This provides an
independent ground truth for calibration validation.

Output: merges into data/golden_dataset_external.json

Usage:
    python -m scripts.generate_openclaw_independent
    python -m scripts.generate_openclaw_independent --dry-run
"""

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
from app.detection_enterprise.golden_dataset import (
    GoldenDataset,
    GoldenDatasetEntry,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

BACKEND = Path(__file__).resolve().parent.parent
EXPANDED_PATH = BACKEND / "data" / "golden_dataset_openclaw_expanded.json"
EXTERNAL_PATH = BACKEND / "data" / "golden_dataset_external.json"

SOURCE_TAG = "openclaw_structural"
TARGET_PER_DETECTOR = 20

# ---------------------------------------------------------------------------
# Independent labeling functions (DO NOT use Pisama detectors)
# ---------------------------------------------------------------------------


def label_session_loop_independently(session: dict) -> bool:
    """True if 3+ identical consecutive tool calls (same name + same input)."""
    events = [e for e in session.get("events", []) if e.get("type") == "tool.call"]
    if len(events) >= 3:
        for i in range(len(events) - 2):
            if (
                events[i].get("tool_name")
                == events[i + 1].get("tool_name")
                == events[i + 2].get("tool_name")
            ):
                if events[i].get("tool_input") == events[i + 1].get("tool_input"):
                    return True

    # Also check for repeated messages
    msgs = []
    for e in session.get("events", []):
        if e.get("type") in ("message.sent", "agent.turn"):
            content = ""
            if isinstance(e.get("data"), dict):
                content = e["data"].get("content", "") or e["data"].get("message", "")
            if content:
                msgs.append(content)
    for i in range(len(msgs) - 2):
        if msgs[i] == msgs[i + 1] == msgs[i + 2] and msgs[i]:
            return True

    return False


def label_tool_abuse_independently(session: dict) -> bool:
    """True if >4 tool calls OR >50% tool error rate."""
    tool_calls = [e for e in session.get("events", []) if e.get("type") == "tool.call"]
    if len(tool_calls) > 4:
        return True

    result_events = [
        e for e in session.get("events", []) if e.get("type") == "tool.result"
    ]
    if not result_events:
        return False

    error_count = 0
    for e in result_events:
        # Check multiple error indicators
        if e.get("error"):
            error_count += 1
        elif isinstance(e.get("tool_result"), dict) and "error" in str(
            e.get("tool_result", {})
        ).lower():
            error_count += 1
        elif isinstance(e.get("data"), dict) and "error" in str(
            e.get("data", {})
        ).lower():
            error_count += 1

    if error_count / len(result_events) > 0.5:
        return True

    return False


def label_sandbox_escape_independently(session: dict) -> bool:
    """True if sandbox_enabled=True AND restricted tool used."""
    if not session.get("sandbox_enabled", False):
        return False

    RESTRICTED = {
        "file_read",
        "file_write",
        "read_file",
        "write_file",
        "exec",
        "shell",
        "http_request",
        "api_call",
        "call_api",
        "db_query",
        "code_execute",
        "system_command",
        "run_command",
        "execute_code",
        "browser",
        "filesystem",
        "query_database",
    }

    for e in session.get("events", []):
        if e.get("type") == "tool.call":
            tool = (e.get("tool_name") or "").lower()
            if tool in RESTRICTED or any(r in tool for r in RESTRICTED):
                return True

    return False


def label_elevated_risk_independently(session: dict) -> bool:
    """True if elevated_mode=True AND risky operations detected."""
    if not session.get("elevated_mode", False):
        return False

    RISKY_OPS = {
        "delete",
        "drop",
        "admin",
        "sudo",
        "root",
        "modify_permissions",
        "grant",
        "reset_all",
        "truncate",
        "remove_all",
    }

    for e in session.get("events", []):
        if e.get("type") == "tool.call":
            tool = (e.get("tool_name") or "").lower()
            tool_input = str(e.get("tool_input", "")).lower()
            if any(op in tool or op in tool_input for op in RISKY_OPS):
                return True

    return False


def label_channel_mismatch_independently(session: dict) -> bool:
    """True if events use channels different from the session channel.

    The primary structural signal is that tool calls or messages are
    routed through a channel that differs from the session's declared
    channel -- e.g., a WhatsApp session with tool calls on Slack.
    """
    session_channel = (session.get("channel") or "").lower()
    if not session_channel:
        return False

    for e in session.get("events", []):
        event_channel = (e.get("channel") or "").lower()
        if not event_channel:
            continue
        if event_channel != session_channel:
            return True

    # Also check message format vs channel (secondary signal)
    for e in session.get("events", []):
        if e.get("type") == "message.sent":
            content = ""
            if isinstance(e.get("data"), dict):
                content = str(
                    e["data"].get("content", "") or e["data"].get("message", "")
                )
            if not content:
                continue
            if session_channel in ("whatsapp", "sms"):
                if "<html>" in content or "<div>" in content or "```" in content:
                    return True
            if session_channel == "telegram":
                if len(content) > 4096:
                    return True

    return False


def label_spawn_chain_independently(session: dict) -> bool:
    """True if session spawn depth > 2."""
    spawn_events = [
        e
        for e in session.get("events", [])
        if e.get("type") in ("session.spawn", "sessions_spawn")
    ]
    if len(spawn_events) > 2:
        return True

    # Also check spawned_sessions field
    spawned = session.get("spawned_sessions", [])
    if isinstance(spawned, list) and len(spawned) > 2:
        return True

    return False


LABELERS = {
    DetectionType.OPENCLAW_SESSION_LOOP: label_session_loop_independently,
    DetectionType.OPENCLAW_TOOL_ABUSE: label_tool_abuse_independently,
    DetectionType.OPENCLAW_SANDBOX_ESCAPE: label_sandbox_escape_independently,
    DetectionType.OPENCLAW_ELEVATED_RISK: label_elevated_risk_independently,
    DetectionType.OPENCLAW_CHANNEL_MISMATCH: label_channel_mismatch_independently,
    DetectionType.OPENCLAW_SPAWN_CHAIN: label_spawn_chain_independently,
}


# ---------------------------------------------------------------------------
# Entry generation
# ---------------------------------------------------------------------------


def _stable_id(prefix: str, *parts: str) -> str:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]
    return f"{prefix}_{h}"


def load_openclaw_entries() -> dict[DetectionType, list[dict]]:
    """Load OpenClaw entries from the expanded dataset, grouped by type."""
    log.info("Loading OpenClaw expanded dataset from %s", EXPANDED_PATH)

    with open(EXPANDED_PATH) as f:
        data = json.load(f)

    raw = data.get("entries", data) if isinstance(data, dict) else data

    by_type: dict[DetectionType, list[dict]] = defaultdict(list)
    for entry_data in raw:
        dt_value = entry_data.get("detection_type", "")
        if not dt_value.startswith("openclaw_"):
            continue
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
        log.info("  %s: %d entries (%d+ / %d-)", dt.value, len(elist), pos, neg)

    return by_type


def generate_independent_entries(dry_run: bool = False) -> list[GoldenDatasetEntry]:
    """For each OpenClaw type, run independent labeling and create entries."""
    by_type = load_openclaw_entries()
    rng = random.Random(42)

    all_entries: list[GoldenDatasetEntry] = []
    stats: dict[str, dict] = {}

    for det_type, labeler in LABELERS.items():
        source_entries = by_type.get(det_type, [])
        if not source_entries:
            log.warning("No source entries for %s", det_type.value)
            continue

        # Run independent labeling on each session
        agree_pos: list[dict] = []  # independent=True, original=True
        agree_neg: list[dict] = []  # independent=False, original=False
        disagree_pos: list[dict] = []  # independent=True, original=False
        disagree_neg: list[dict] = []  # independent=False, original=True

        for entry_data in source_entries:
            session = entry_data["input_data"]["session"]
            original_label = entry_data.get("expected_detected", False)

            try:
                independent_label = labeler(session)
            except Exception as exc:
                log.debug(
                    "Labeler %s failed on %s: %s",
                    det_type.value,
                    session.get("session_id", "?"),
                    exc,
                )
                continue

            item = {
                "session": session,
                "session_id": session.get("session_id", "unknown"),
                "independent_label": independent_label,
                "original_label": original_label,
            }

            if independent_label and original_label:
                agree_pos.append(item)
            elif not independent_label and not original_label:
                agree_neg.append(item)
            elif independent_label and not original_label:
                disagree_pos.append(item)
            else:
                disagree_neg.append(item)

        log.info(
            "  %s: agree+=%d, agree-=%d, disagree(ind+/orig-)=%d, disagree(ind-/orig+)=%d",
            det_type.value,
            len(agree_pos),
            len(agree_neg),
            len(disagree_pos),
            len(disagree_neg),
        )

        # Build entries: use independent label as ground truth
        # Prioritize agreement entries but also include disagreements
        target = TARGET_PER_DETECTOR
        half = target // 2

        # Select positives: prefer agreements, fill with disagreements
        rng.shuffle(agree_pos)
        rng.shuffle(disagree_pos)
        positives = agree_pos[:half]
        remaining_pos = max(0, half - len(positives))
        if remaining_pos > 0:
            positives.extend(disagree_pos[:remaining_pos])

        # Select negatives: prefer agreements, fill with disagreements
        rng.shuffle(agree_neg)
        rng.shuffle(disagree_neg)
        negatives = agree_neg[:half]
        remaining_neg = max(0, half - len(negatives))
        if remaining_neg > 0:
            negatives.extend(disagree_neg[:remaining_neg])

        type_entries = []
        for idx, item in enumerate(positives):
            entry_id = _stable_id(
                f"oc_ind_{det_type.value}_pos", item["session_id"], str(idx)
            )
            agrees = item["independent_label"] == item["original_label"]
            type_entries.append(
                GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=det_type,
                    input_data={"session": item["session"]},
                    expected_detected=True,  # independent label
                    expected_confidence_min=0.3,
                    expected_confidence_max=1.0,
                    description=f"Independent structural label: {item['session_id']} ({'agrees' if agrees else 'DISAGREES'} with original)",
                    source=SOURCE_TAG,
                    difficulty="medium" if agrees else "hard",
                    split="test",
                    tags=[
                        "independent_label",
                        "openclaw",
                        "positive",
                        det_type.value,
                        "agreement" if agrees else "disagreement",
                    ],
                )
            )

        for idx, item in enumerate(negatives):
            entry_id = _stable_id(
                f"oc_ind_{det_type.value}_neg", item["session_id"], str(idx)
            )
            agrees = item["independent_label"] == item["original_label"]
            type_entries.append(
                GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=det_type,
                    input_data={"session": item["session"]},
                    expected_detected=False,  # independent label
                    expected_confidence_min=0.0,
                    expected_confidence_max=0.3,
                    description=f"Independent structural label: {item['session_id']} ({'agrees' if agrees else 'DISAGREES'} with original)",
                    source=SOURCE_TAG,
                    difficulty="medium" if agrees else "hard",
                    split="test",
                    tags=[
                        "independent_label",
                        "openclaw",
                        "negative",
                        det_type.value,
                        "agreement" if agrees else "disagreement",
                    ],
                )
            )

        all_entries.extend(type_entries)
        pos_count = sum(1 for e in type_entries if e.expected_detected)
        neg_count = len(type_entries) - pos_count
        stats[det_type.value] = {
            "total": len(type_entries),
            "positive": pos_count,
            "negative": neg_count,
            "agreements": sum(
                1 for e in type_entries if "agreement" in e.tags
            ),
            "disagreements": sum(
                1 for e in type_entries if "disagreement" in e.tags
            ),
        }

    log.info("")
    log.info("=" * 60)
    log.info("Independent Labeling Summary")
    log.info("=" * 60)
    total = 0
    for dt_val, s in sorted(stats.items()):
        log.info(
            "  %s: %d entries (%d+ / %d-) [%d agree, %d disagree]",
            dt_val,
            s["total"],
            s["positive"],
            s["negative"],
            s["agreements"],
            s["disagreements"],
        )
        total += s["total"]
    log.info("Total: %d entries", total)
    log.info("=" * 60)

    return all_entries


def merge_to_external(entries: list[GoldenDatasetEntry]) -> int:
    """Merge entries into the external golden dataset, replacing old ones."""
    log.info("Loading external dataset from %s", EXTERNAL_PATH)
    dataset = GoldenDataset()
    if EXTERNAL_PATH.exists():
        dataset.load(EXTERNAL_PATH)
        log.info("Loaded %d existing entries", len(dataset.entries))

    # Remove old openclaw_structural entries
    old_ids = [
        eid
        for eid in dataset.entries
        if dataset.entries[eid].source == SOURCE_TAG
    ]
    for eid in old_ids:
        dataset.remove_entry(eid)
    if old_ids:
        log.info("Removed %d old %s entries", len(old_ids), SOURCE_TAG)

    # Add new entries
    for entry in entries:
        dataset.add_entry(entry)

    dataset.save(EXTERNAL_PATH)
    log.info(
        "Saved external dataset: %d total entries to %s",
        len(dataset.entries),
        EXTERNAL_PATH,
    )
    return len(dataset.entries)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate independently-labeled OpenClaw golden entries"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show plan only")
    args = parser.parse_args()

    entries = generate_independent_entries(dry_run=args.dry_run)

    if args.dry_run:
        log.info("Dry run -- not saving.")
        return

    if entries:
        merge_to_external(entries)
    else:
        log.warning("No entries generated.")


if __name__ == "__main__":
    main()
