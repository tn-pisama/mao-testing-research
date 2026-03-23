"""Convert downloaded external datasets to Pisama GoldenDatasetEntry format.

Converts MAST-Data and SWE-bench Verified traces into the golden dataset
JSON format used by calibrate.py.

Output: data/golden_dataset_external.json
"""
import json
import os
import sys
import hashlib
import logging
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

# Need JWT_SECRET for app imports
os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")

from datasets import Dataset

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry, GoldenDataset
from app.core.mast_constants import ANNOTATION_MAP
from app.ingestion.importers.mast import MASTImporter

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MAST F-code -> Pisama DetectionType mapping
# Based on MAST failure taxonomy + Pisama detector coverage
# ---------------------------------------------------------------------------
MAST_F_TO_DETECTION = {
    "F1": DetectionType.SPECIFICATION,      # Specification Mismatch
    "F2": DetectionType.DECOMPOSITION,      # Poor Task Decomposition
    "F3": DetectionType.COORDINATION,       # Resource Misallocation -> coordination issues
    "F5": DetectionType.WORKFLOW,           # Flawed Workflow Design
    "F6": DetectionType.DERAILMENT,         # Task Derailment
    "F7": DetectionType.CONTEXT,            # Context Neglect
    "F8": DetectionType.LOOP,              # Info Withholding / Step Repetition
    "F9": DetectionType.PERSONA_DRIFT,      # Role Usurpation
    "F10": DetectionType.COMMUNICATION,     # Communication Breakdown
    "F11": DetectionType.COORDINATION,      # Coordination Failure
    # F12 removed: MAST traces don't have token counts needed by the overflow detector
    "F14": DetectionType.COMPLETION,        # Completion Misjudgment
}

# Direct annotation code -> DetectionType (for convenience)
MAST_ANN_TO_DETECTION = {}
for ann_code, f_code in ANNOTATION_MAP.items():
    if f_code in MAST_F_TO_DETECTION:
        MAST_ANN_TO_DETECTION[ann_code] = MAST_F_TO_DETECTION[f_code]


def _stable_id(prefix: str, *parts: str) -> str:
    """Generate a deterministic ID from components."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]
    return f"{prefix}_{h}"


def _truncate(text: str, max_chars: int = 4000) -> str:
    """Truncate text to max_chars preserving word boundaries."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def _extract_task_from_mast(row: dict) -> str:
    """Extract the task description from a MAST row."""
    trajectory = row["trace"].get("trajectory", "") or ""
    framework = row.get("mas_name", "")

    # ChatDev: look for task_prompt
    if framework == "ChatDev":
        import re
        m = re.search(r"\*\*task_prompt\*\*:\s*([^\n|]+)", trajectory)
        if m:
            return m.group(1).strip()

    # MetaGPT: look for UserRequirement
    if framework == "MetaGPT":
        import re
        m = re.search(r"UserRequirement\s*\nCONTENT:\s*\n(.+?)(?:\n\n|\n\[)", trajectory, re.DOTALL)
        if m:
            return m.group(1).strip()

    # AG2/AutoGen: problem_statement
    if framework in ("AG2", "AutoGen"):
        import re
        m = re.search(r"(?:problem_statement|task):\s*(.+?)(?:\n[a-z_]+:|$)", trajectory, re.DOTALL)
        if m:
            return m.group(1).strip()

    # Generic: first line or Task: pattern
    import re
    m = re.search(r"(?:Task|Query|Prompt|Problem):\s*(.+?)(?:\n\n|\n\[|$)", trajectory, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Fallback: first 200 chars
    return trajectory[:200].strip()


def _extract_last_agent_message(agent_turns: list, trajectory_text: str) -> str:
    """Extract the last substantive agent message from the trajectory.

    Walks the parsed turns in reverse and returns the first turn with
    meaningful content (>30 chars, role == agent). Falls back to
    the last paragraph of the raw trajectory text.
    """
    # Walk backwards through parsed turns looking for agent content
    for turn in reversed(agent_turns):
        role = turn.get("role", "")
        content = (turn.get("content", "") or "").strip()
        if role in ("agent", "tool") and len(content) > 30:
            return content

    # Fallback: last non-empty paragraph from the raw trajectory
    import re as _re
    paragraphs = [p.strip() for p in _re.split(r"\n\n+", trajectory_text) if p.strip()]
    for p in reversed(paragraphs):
        if len(p) > 30:
            return p

    return trajectory_text[-3000:] if trajectory_text else ""


def _extract_subtask_list(agent_turns: list, trajectory_text: str, framework: str) -> str:
    """Parse trajectory to extract a structured subtask / step list.

    Looks for role changes and phase boundaries in agent turns to
    identify individual steps. Produces a newline-separated numbered
    list suitable for the decomposition detector.
    """
    steps: list[str] = []

    if agent_turns:
        prev_role = None
        for turn in agent_turns:
            pid = turn.get("participant_id", "unknown")
            content = (turn.get("content", "") or "").strip()
            summary = content[:200].split("\n")[0].strip()  # first line, max 200 chars

            # New step on role change or explicit phase marker
            if pid != prev_role and summary:
                steps.append(f"Step {len(steps)+1} ({pid}): {summary}")
                prev_role = pid
            elif summary and len(steps) > 0:
                # Same agent continuing — only add if content looks like a new action
                if any(kw in summary.lower() for kw in ("next", "then", "now", "step", "phase", "finally")):
                    steps.append(f"Step {len(steps)+1} ({pid}): {summary}")

    # Fallback: split trajectory by common delimiters
    if len(steps) < 2:
        import re as _re
        # Try numbered list, markdown headers, or dashes
        items = _re.findall(
            r"(?:^|\n)\s*(?:\d+[\.\)]\s+|[-*]\s+|#{1,3}\s+)(.+)",
            trajectory_text,
        )
        if items:
            steps = [f"Step {i+1}: {item.strip()[:200]}" for i, item in enumerate(items[:30])]

    # Ultra-fallback: paragraph boundaries
    if len(steps) < 2:
        paragraphs = [p.strip() for p in trajectory_text.split("\n\n") if len(p.strip()) > 30]
        steps = [f"Step {i+1}: {p[:200]}" for i, p in enumerate(paragraphs[:20])]

    return "\n".join(steps) if steps else trajectory_text[:3000]


def _build_input_data(detection_type: DetectionType, task: str, trajectory_text: str,
                      framework: str, agent_turns: list) -> dict:
    """Build detector-specific input_data from a MAST trace.

    Maps the extracted trace data to the format each Pisama detector expects.
    """
    task_raw = task  # preserve untruncated version for detectors that need full context
    task = _truncate(task, 2000)
    traj_short = _truncate(trajectory_text, 3000)

    if detection_type == DetectionType.LOOP:
        # Loop detector expects: {"states": [{"agent_id": ..., "content": ..., "state_delta": {}}, ...]}
        states = []
        for turn in agent_turns[:30]:  # limit to 30 turns
            states.append({
                "agent_id": turn.get("participant_id", "unknown"),
                "content": _truncate(turn.get("content", ""), 1500),
                "state_delta": {},
            })
        if not states:
            states = [{"agent_id": "agent", "content": traj_short, "state_delta": {}}]
        return {"states": states}

    elif detection_type == DetectionType.COORDINATION:
        # Coordination: {"messages": [...], "agent_ids": [...]}
        # IMPORTANT: timestamps must be Unix floats — the detector does float arithmetic
        base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
        messages = []
        agent_ids = set()
        for turn in agent_turns[:20]:
            pid = turn.get("participant_id", "unknown")
            agent_ids.add(pid)
            messages.append({
                "from_agent": pid,
                "to_agent": "system",
                "content": _truncate(turn.get("content", ""), 1000),
                "timestamp": base_ts + float(len(messages)),
            })
        if not messages:
            messages = [{"from_agent": "agent", "to_agent": "system", "content": traj_short, "timestamp": base_ts}]
            agent_ids = {"agent"}
        return {"messages": messages, "agent_ids": sorted(agent_ids)}

    elif detection_type == DetectionType.COMMUNICATION:
        # Communication: {"sender_message": ..., "receiver_response": ...}
        if len(agent_turns) >= 2:
            return {
                "sender_message": _truncate(agent_turns[0].get("content", ""), 2000),
                "receiver_response": _truncate(agent_turns[1].get("content", ""), 2000),
            }
        return {
            "sender_message": task,
            "receiver_response": traj_short,
        }

    elif detection_type == DetectionType.CONTEXT:
        # context = FULL original task (not truncated — critical markers must survive)
        # output  = last substantive agent message (not the full trajectory log)
        last_output = _extract_last_agent_message(agent_turns, trajectory_text)
        return {"context": _truncate(task_raw, 4000), "output": _truncate(last_output, 3000)}

    elif detection_type == DetectionType.DERAILMENT:
        # task = full original task description (not truncated)
        # output = final agent output / last meaningful response (not system logs)
        last_output = _extract_last_agent_message(agent_turns, trajectory_text)
        return {"task": _truncate(task_raw, 4000), "output": _truncate(last_output, 3000)}

    elif detection_type == DetectionType.COMPLETION:
        return {
            "task": task,
            "subtasks": [task],  # single task since MAST doesn't decompose
            "success_criteria": [f"Complete the task: {task[:100]}"],
            "agent_output": traj_short,
        }

    elif detection_type == DetectionType.PERSONA_DRIFT:
        # Find agent IDs from turns
        agent_id = "unknown"
        if agent_turns:
            agent_id = agent_turns[0].get("participant_id", "unknown")
        return {
            "agent": {
                "id": agent_id,
                "persona_description": f"{framework} agent with assigned role",
            },
            "output": traj_short,
        }

    elif detection_type == DetectionType.SPECIFICATION:
        return {"user_intent": task, "task_specification": traj_short}

    elif detection_type == DetectionType.WORKFLOW:
        return {
            "workflow_definition": {"name": task[:200], "steps": [{"id": "s1", "name": task[:100]}]},
            "execution_result": {"status": "completed", "output": traj_short},
        }

    elif detection_type == DetectionType.OVERFLOW:
        # Should not be reached — MAST traces lack token counts required by overflow detector.
        # Return empty dict to avoid silent errors if mapping is accidentally re-added.
        return {}

    elif detection_type == DetectionType.DECOMPOSITION:
        # task_description = original MAST task (full)
        # decomposition = structured subtask list extracted from the trajectory
        subtasks = _extract_subtask_list(agent_turns, trajectory_text, framework)
        return {"task_description": _truncate(task_raw, 4000), "decomposition": subtasks}

    else:
        # Fallback for any unmapped type
        return {"task": task, "output": traj_short}


def convert_mast_full(dataset_path: str) -> list:
    """Convert MAST full dataset to GoldenDatasetEntry list."""
    log.info("Converting MAST full dataset...")
    mast = Dataset.load_from_disk(dataset_path)
    importer = MASTImporter()

    entries = []
    stats = Counter()

    for idx, row in enumerate(mast):
        annotations = row["mast_annotation"]
        framework = row.get("mas_name", "unknown")
        trace_id = row.get("trace_id", str(idx))
        trajectory = row["trace"].get("trajectory", "") or ""

        # Use row index as unique identifier (trace_id is NOT unique across frameworks)
        row_key = str(idx)

        if len(trajectory) < 100:
            stats["skipped_short"] += 1
            continue

        task = _extract_task_from_mast(row)

        # Parse turns using MASTImporter
        try:
            trace = importer.import_conversation(json.dumps(row))
            agent_turns = [
                {"participant_id": t.participant_id, "content": t.content, "role": t.role}
                for t in trace.turns
            ]
        except Exception:
            agent_turns = []

        # Check which failure modes are active
        active_failures = {}
        for ann_code, value in annotations.items():
            if isinstance(value, (int, float)) and value > 0:
                if ann_code in MAST_ANN_TO_DETECTION:
                    dt = MAST_ANN_TO_DETECTION[ann_code]
                    active_failures[dt] = ann_code

        is_healthy = len(active_failures) == 0

        if is_healthy:
            # Create one negative sample per trace, mapped to a random detector type
            neg_types = [
                DetectionType.LOOP, DetectionType.COORDINATION, DetectionType.DERAILMENT,
                DetectionType.CONTEXT, DetectionType.SPECIFICATION, DetectionType.COMPLETION,
            ]
            # Deterministic selection based on row index
            dt = neg_types[idx % len(neg_types)]
            entry_id = _stable_id("mast_neg", row_key, framework, dt.value)

            input_data = _build_input_data(dt, task, trajectory, framework, agent_turns)
            entry = GoldenDatasetEntry(
                id=entry_id,
                detection_type=dt,
                input_data=input_data,
                expected_detected=False,
                expected_confidence_min=0.0,
                expected_confidence_max=0.3,
                description=f"Healthy {framework} trace (no failures annotated)",
                source="mast_real",
                difficulty="medium",
                split="test",
                tags=["real_trace", "mast", "negative", framework.lower()],
            )
            entries.append(entry)
            stats[f"negative_{dt.value}"] += 1
        else:
            # Create one entry per active failure mode
            for dt, ann_code in active_failures.items():
                entry_id = _stable_id("mast_pos", row_key, framework, dt.value, ann_code)
                input_data = _build_input_data(dt, task, trajectory, framework, agent_turns)

                entry = GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=dt,
                    input_data=input_data,
                    expected_detected=True,
                    expected_confidence_min=0.3,
                    expected_confidence_max=1.0,
                    description=f"MAST {framework} failure: {ann_code} -> {dt.value}",
                    source="mast_real",
                    difficulty="hard",
                    split="test",
                    tags=["real_trace", "mast", "positive", framework.lower(), f"ann_{ann_code}"],
                )
                entries.append(entry)
                stats[f"positive_{dt.value}"] += 1

    log.info(f"  MAST full: {len(entries)} entries from {len(mast)} traces")
    for k, v in sorted(stats.items()):
        log.info(f"    {k}: {v}")

    return entries


def convert_swebench(dataset_path: str) -> list:
    """Convert SWE-bench Verified to negative golden samples.

    SWE-bench contains well-structured software engineering tasks with known
    solutions. These serve as negative samples (no agent failure) since the
    problem statements are clear and the patches are correct.
    """
    log.info("Converting SWE-bench Verified...")
    swe = Dataset.load_from_disk(dataset_path)

    entries = []
    # Use SWE-bench as negative samples for specification and decomposition detectors
    # These are well-formed task descriptions that should NOT trigger failure detection
    target_types = [
        DetectionType.SPECIFICATION,
        DetectionType.DECOMPOSITION,
        DetectionType.DERAILMENT,
    ]

    for idx, row in enumerate(swe):
        problem = row.get("problem_statement", "")
        if not problem or len(problem) < 50:
            continue

        # Rotate through detector types
        dt = target_types[idx % len(target_types)]
        entry_id = _stable_id("swe_neg", row["instance_id"], dt.value)

        # The problem statement is a well-formed spec; the patch is correct execution
        patch = row.get("patch", "")
        hints = row.get("hints_text", "")

        if dt == DetectionType.SPECIFICATION:
            input_data = {
                "user_intent": _truncate(problem, 2000),
                "task_specification": _truncate(problem + "\n\n" + hints, 3000) if hints else _truncate(problem, 3000),
            }
        elif dt == DetectionType.DECOMPOSITION:
            input_data = {
                "task_description": _truncate(problem, 2000),
                "decomposition": _truncate(
                    f"Repository: {row['repo']}\n"
                    f"Fix: Apply patch to resolve the issue.\n"
                    f"Tests to pass: {row.get('FAIL_TO_PASS', '')[:500]}",
                    3000,
                ),
            }
        else:  # DERAILMENT
            input_data = {
                "task": _truncate(problem, 2000),
                "output": _truncate(
                    f"Applied fix to {row['repo']}:\n{patch[:2000]}" if patch else "Fix applied successfully.",
                    3000,
                ),
            }

        difficulty_map = {
            "15 min - 1 hour": "easy",
            "1-4 hours": "medium",
        }
        raw_diff = row.get("difficulty", "medium")
        difficulty = difficulty_map.get(raw_diff, "medium")

        entry = GoldenDatasetEntry(
            id=entry_id,
            detection_type=dt,
            input_data=input_data,
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description=f"SWE-bench {row['repo']}: well-formed task (no failure)",
            source="swebench_real",
            difficulty=difficulty,
            split="test",
            tags=["real_trace", "swebench", "negative", row["repo"].split("/")[0]],
        )
        entries.append(entry)

    log.info(f"  SWE-bench: {len(entries)} negative entries from {len(swe)} tasks")
    return entries


def main():
    """Main conversion pipeline."""
    all_entries = []

    # Convert MAST full dataset
    mast_path = "data/external/mast_full"
    if os.path.exists(mast_path):
        all_entries.extend(convert_mast_full(mast_path))
    else:
        log.warning(f"MAST full dataset not found at {mast_path}")

    # Convert SWE-bench
    swe_path = "data/external/swebench"
    if os.path.exists(swe_path):
        all_entries.extend(convert_swebench(swe_path))
    else:
        log.warning(f"SWE-bench dataset not found at {swe_path}")

    if not all_entries:
        log.error("No entries converted!")
        sys.exit(1)

    # Build summary
    type_counts = Counter()
    pos_counts = Counter()
    neg_counts = Counter()
    source_counts = Counter()
    for e in all_entries:
        type_counts[e.detection_type.value] += 1
        source_counts[e.source] += 1
        if e.expected_detected:
            pos_counts[e.detection_type.value] += 1
        else:
            neg_counts[e.detection_type.value] += 1

    log.info(f"\n=== Total: {len(all_entries)} entries ===")
    log.info(f"Sources: {dict(source_counts)}")
    log.info(f"\nPer detection type:")
    for dt_val in sorted(type_counts.keys()):
        log.info(f"  {dt_val:20s}: {type_counts[dt_val]:4d} total ({pos_counts.get(dt_val, 0)} pos, {neg_counts.get(dt_val, 0)} neg)")

    # Save as golden dataset JSON
    dataset = GoldenDataset()
    for entry in all_entries:
        dataset.add_entry(entry)

    output_path = Path("data/golden_dataset_external.json")
    dataset.save(output_path)
    log.info(f"\nSaved to {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
