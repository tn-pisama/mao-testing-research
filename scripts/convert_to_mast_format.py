#!/usr/bin/env python3
"""
Convert unified training data to MAST format for benchmarking.

Reads: data/training/unified_training_data.json
Writes: data/training/n8n_mast_format.json
"""

import json
from pathlib import Path

# Mapping from our failure modes to MAST annotation keys
FM_TO_MAST = {
    "F1": "1.1", "F2": "1.2", "F3": "1.3", "F4": "1.4", "F5": "1.5",
    "F6": "2.1", "F7": "2.2", "F8": "2.3", "F9": "2.4", "F10": "2.5", "F11": "2.6",
    "F12": "3.1", "F13": "3.2", "F14": "3.3",
}

ALL_MAST_KEYS = ["1.1", "1.2", "1.3", "1.4", "1.5", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "3.1", "3.2", "3.3"]


def convert_to_mast_format(input_path: Path, output_path: Path):
    """Convert unified training data to MAST format."""

    with open(input_path) as f:
        data = json.load(f)

    mast_records = []

    for trace in data["traces"]:
        # Build trajectory from conversation
        if trace["conversation"]:
            trajectory_parts = []
            for turn in trace["conversation"]:
                agent = turn.get("agent", "system")
                content = turn.get("content", "")
                trajectory_parts.append(f"[{agent}] {content}")
            trajectory = "\n\n".join(trajectory_parts)
        else:
            trajectory = ""

        # Build MAST annotations (dict with 0/1 values)
        annotations = {key: 0 for key in ALL_MAST_KEYS}
        for fm in trace.get("failure_modes", []):
            if fm in FM_TO_MAST:
                annotations[FM_TO_MAST[fm]] = 1

        # Map source to framework name
        source = trace.get("source", "")
        framework_map = {
            "n8n_cloud": "n8n",
            "toolbench": "ToolBench",
            "mast_hf": trace.get("framework", "MAST"),
        }
        framework = framework_map.get(source, source)

        # Create MAST-format record
        record = {
            "mas_name": framework,
            "llm_name": trace.get("metadata", {}).get("llm", "unknown"),
            "benchmark_name": trace.get("task", "")[:100] if trace.get("task") else source,
            "trace_id": trace["trace_id"],
            "trace": {
                "key": trace["trace_id"],
                "index": len(mast_records),
                "trajectory": trajectory,
            },
            "mast_annotation": annotations,
        }
        mast_records.append(record)

    # Write output
    with open(output_path, "w") as f:
        json.dump(mast_records, f, indent=2)

    print(f"Converted {len(mast_records)} records to MAST format")
    print(f"Output: {output_path}")

    # Statistics
    failure_counts = {fm: 0 for fm in FM_TO_MAST.keys()}
    for record in mast_records:
        for fm, mast_key in FM_TO_MAST.items():
            if record["mast_annotation"].get(mast_key) == 1:
                failure_counts[fm] += 1

    print("\nFailure mode distribution:")
    for fm, count in sorted(failure_counts.items(), key=lambda x: -x[1]):
        print(f"  {fm}: {count}")


if __name__ == "__main__":
    input_path = Path("data/training/unified_training_data.json")
    output_path = Path("data/training/n8n_mast_format.json")

    convert_to_mast_format(input_path, output_path)
