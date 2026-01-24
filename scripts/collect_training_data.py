#!/usr/bin/env python3
"""
Collect and unify training data from multiple sources:
1. Our n8n cloud executions (actual data)
2. Synthetic n8n workflows (designed failure patterns)
3. External datasets (ToolBench, MAST-Data)

Output: Unified dataset for training failure detectors
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import httpx

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


# =============================================================================
# Configuration
# =============================================================================

N8N_HOST = os.getenv("N8N_HOST", "https://pisama.app.n8n.cloud")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "training"


# =============================================================================
# Source 1: Our n8n Cloud Executions
# =============================================================================

def collect_n8n_cloud_executions(limit: int = 100) -> List[Dict[str, Any]]:
    """Pull execution data from our n8n cloud instance."""
    print(f"Collecting executions from {N8N_HOST}...")

    if not N8N_API_KEY:
        print("  Warning: N8N_API_KEY not set, skipping n8n cloud data")
        return []

    traces = []

    try:
        with httpx.Client(timeout=30.0) as client:
            # Get executions
            resp = client.get(
                f"{N8N_HOST}/api/v1/executions",
                params={"limit": limit, "includeData": "true"},
                headers={"X-N8N-API-KEY": N8N_API_KEY},
            )
            resp.raise_for_status()

            data = resp.json()
            executions = data.get("data", [])

            # Get workflow metadata for mapping to failure modes
            workflows_resp = client.get(
                f"{N8N_HOST}/api/v1/workflows",
                params={"active": "true", "limit": 200},
                headers={"X-N8N-API-KEY": N8N_API_KEY},
            )
            workflows_resp.raise_for_status()
            workflow_map = {str(w["id"]): w for w in workflows_resp.json().get("data", [])}

            for exec_data in executions:
                workflow_id = str(exec_data.get("workflowId", ""))
                workflow = workflow_map.get(workflow_id, {})
                workflow_name = workflow.get("name", "")

                # Determine failure mode from workflow name
                failure_mode = infer_failure_mode_from_name(workflow_name)

                trace = {
                    "source": "n8n_cloud",
                    "trace_id": f"n8n_{exec_data.get('id')}",
                    "workflow_id": workflow_id,
                    "workflow_name": workflow_name,
                    "status": exec_data.get("status"),
                    "started_at": exec_data.get("startedAt"),
                    "finished_at": exec_data.get("stoppedAt"),
                    "failure_mode": failure_mode,
                    "conversation": extract_conversation_from_n8n(exec_data),
                    "raw_data": {},  # Don't store raw data to save space
                }
                traces.append(trace)

            print(f"  Collected {len(traces)} executions from n8n cloud")

    except Exception as e:
        print(f"  Error collecting n8n data: {e}")
        import traceback
        traceback.print_exc()

    return traces


def infer_failure_mode_from_name(workflow_name: str) -> Optional[str]:
    """Infer MAST failure mode from workflow name."""
    name_upper = workflow_name.upper()

    # Map n8n categories to MAST failure modes
    mappings = {
        "LOOP-001": "F3",   # Exact message repetition
        "LOOP-002": "F11",  # Semantic loop
        "LOOP-003": "F11",  # Delegation loop
        "LOOP-004": "F3",   # Echo loop
        "LOOP-005": "F11",  # Negotiation loop
        "LOOP-006": "F11",  # Escalation loop
        "COORD-001": "F4",  # Deadlock
        "COORD-002": "F4",  # Priority inversion
        "COORD-003": "F5",  # Resource contention
        "COORD-004": "F4",  # Queue violation
        "COORD-005": "F5",  # Race condition
        "COORD-006": "F4",  # Circular wait
        "STATE-001": "F12", # State corruption
        "STATE-002": "F12", # State regression
        "STATE-003": "F12", # Schema drift
        "STATE-004": "F12", # Data loss
        "STATE-005": "F12", # Inconsistency
        "STATE-006": "F12", # Merge conflict
        "PERSONA-001": "F7", # Vocabulary drift
        "PERSONA-002": "F7", # Role violation
        "PERSONA-003": "F7", # Tone shift
        "PERSONA-004": "F7", # Expertise leak
        "PERSONA-005": "F7", # Character break
        "RESOURCE-001": "F6", # Context overflow
        "RESOURCE-002": "F6", # Token limit
        "RESOURCE-003": "F6", # Memory exhaustion
        "RESOURCE-004": "F6", # Timeout
        "RESOURCE-005": "F6", # Rate limit
    }

    for pattern, mode in mappings.items():
        if pattern in name_upper:
            return mode

    return None


def extract_conversation_from_n8n(exec_data: Dict) -> List[Dict[str, Any]]:
    """Convert n8n execution data to conversation format."""
    conversation = []

    try:
        run_data = exec_data.get("data", {}).get("resultData", {}).get("runData", {})
        if not isinstance(run_data, dict):
            return conversation

        seq = 0
        for node_name, runs in run_data.items():
            if not isinstance(runs, list):
                continue

            for run in runs:
                if not isinstance(run, dict):
                    continue

                # Extract output data
                output = run.get("data", {}).get("main", [[]])
                output_text = ""

                if output and isinstance(output, list) and output[0]:
                    for item in output[0]:
                        if not isinstance(item, dict):
                            continue
                        json_data = item.get("json", {})
                        if json_data and isinstance(json_data, dict):
                            # Try to extract meaningful text
                            for key in ["output", "text", "response", "message", "content"]:
                                if key in json_data:
                                    output_text += str(json_data[key]) + "\n"
                            if not output_text:
                                output_text = json.dumps(json_data)[:500]

                turn = {
                    "turn": seq,
                    "agent": node_name,
                    "content": output_text.strip() or f"[Node {node_name} executed]",
                    "latency_ms": run.get("executionTime", 0),
                }
                conversation.append(turn)
                seq += 1

    except Exception as e:
        print(f"    Warning: Error extracting conversation: {e}")

    return conversation


# =============================================================================
# Source 2: Synthetic n8n Workflows (trigger and collect)
# =============================================================================

def trigger_synthetic_workflows(workflow_dir: Path, limit: int = 10) -> List[str]:
    """Trigger synthetic n8n workflows via webhooks and return triggered IDs."""
    print(f"Triggering synthetic workflows from {workflow_dir}...")

    triggered = []

    for wf_file in sorted(workflow_dir.glob("*.json"))[:limit]:
        try:
            with open(wf_file) as f:
                wf_data = json.load(f)

            # Find webhook path
            webhook_path = None
            for node in wf_data.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    webhook_path = node.get("parameters", {}).get("path")
                    break

            if webhook_path:
                # Trigger the workflow
                url = f"{N8N_HOST}/webhook/{webhook_path}"
                try:
                    with httpx.Client(timeout=60.0) as client:
                        resp = client.post(url, json={})
                        if resp.status_code < 400:
                            triggered.append(wf_file.stem)
                            print(f"  Triggered: {wf_file.stem}")
                except Exception as e:
                    print(f"  Failed to trigger {wf_file.stem}: {e}")

        except Exception as e:
            print(f"  Error reading {wf_file}: {e}")

    print(f"  Triggered {len(triggered)} workflows")
    return triggered


# =============================================================================
# Source 3: External Datasets
# =============================================================================

def collect_toolbench_data(limit: int = 1000) -> List[Dict[str, Any]]:
    """Download ToolBench data from HuggingFace."""
    print("Collecting ToolBench data...")

    try:
        from datasets import load_dataset

        ds = load_dataset("tuandunghcmut/toolbench-v1", split="train", streaming=True)

        traces = []
        for i, sample in enumerate(ds):
            if i >= limit:
                break

            # Parse ToolBench format
            conversations = sample.get("conversations", {})
            from_list = conversations.get("from", [])
            value_list = conversations.get("value", [])

            # Convert to our format
            conv = []
            for j, (speaker, content) in enumerate(zip(from_list, value_list)):
                # Detect potential failures in the trace
                conv.append({
                    "turn": j,
                    "agent": speaker,
                    "content": content[:2000] if isinstance(content, str) else str(content)[:2000],
                })

            # Infer failure mode from conversation patterns
            failure_mode = infer_failure_from_toolbench(conv)

            trace = {
                "source": "toolbench",
                "trace_id": f"toolbench_{sample.get('id', i)}",
                "task": sample.get("id", ""),
                "failure_mode": failure_mode,
                "conversation": conv,
            }
            traces.append(trace)

            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1} ToolBench samples...")

        print(f"  Collected {len(traces)} ToolBench traces")
        return traces

    except ImportError:
        print("  Error: datasets library not installed")
        return []
    except Exception as e:
        print(f"  Error collecting ToolBench: {e}")
        return []


def infer_failure_from_toolbench(conversation: List[Dict]) -> Optional[str]:
    """Infer failure mode from ToolBench conversation patterns."""
    # Look for patterns in the conversation
    text = " ".join(c.get("content", "") for c in conversation).lower()

    # Check for repetition (F3)
    if conversation:
        contents = [c.get("content", "")[:100] for c in conversation if c.get("agent") == "assistant"]
        if len(contents) >= 3:
            if len(set(contents)) < len(contents) / 2:
                return "F3"  # Repetitive behavior

    # Check for failure keywords
    if "give up" in text or "restart" in text:
        return "F1"  # Task failure
    if "error" in text and "api" in text:
        return "F5"  # Resource/API failure
    if "timeout" in text or "rate limit" in text:
        return "F6"  # Context overflow / resource

    return None


def collect_mast_huggingface_data(limit: int = 2000) -> List[Dict[str, Any]]:
    """Download MAST-Data from HuggingFace."""
    print("Collecting MAST-Data from HuggingFace...")

    try:
        from datasets import load_dataset

        ds = load_dataset("mcemri/MAST-Data", split="train", streaming=True)

        traces = []
        for i, sample in enumerate(ds):
            if i >= limit:
                break

            # Parse MAST annotations - dict with 0/1 values for each failure mode
            # MAST uses categories 1.x, 2.x, 3.x for different failure types
            annotations = sample.get("mast_annotation", {})
            failure_modes = set()

            # Map MAST category.sub to our failure modes
            mast_to_fm = {
                "1.1": "F1", "1.2": "F2", "1.3": "F3", "1.4": "F4", "1.5": "F5",
                "2.1": "F6", "2.2": "F7", "2.3": "F8", "2.4": "F9", "2.5": "F10", "2.6": "F11",
                "3.1": "F12", "3.2": "F13", "3.3": "F14",
            }

            # annotations is a dict like {"1.1": 0, "1.2": 1, ...}
            if isinstance(annotations, dict):
                for ann_key, ann_value in annotations.items():
                    if ann_value == 1 and ann_key in mast_to_fm:
                        failure_modes.add(mast_to_fm[ann_key])
            elif isinstance(annotations, list):
                # Fallback for old format
                for ann in annotations:
                    if ann in mast_to_fm:
                        failure_modes.add(mast_to_fm[ann])

            # Parse trace - it's a dict with 'trajectory' key
            trace_data = sample.get("trace", {})
            conversation = []

            if isinstance(trace_data, dict):
                trajectory = trace_data.get("trajectory", "")
                if trajectory:
                    # Parse the trajectory into conversation turns
                    # Format: [timestamp INFO] Message patterns
                    lines = trajectory.split("\n")
                    turn = 0
                    current_content = []

                    for line in lines:
                        # Detect turn boundaries (e.g., "[2025-31-03 19:09:41 INFO]")
                        if "[20" in line and "INFO]" in line:
                            if current_content:
                                conversation.append({
                                    "turn": turn,
                                    "agent": "system",
                                    "content": "\n".join(current_content)[:2000],
                                })
                                turn += 1
                                current_content = []
                        current_content.append(line)

                    # Add last turn
                    if current_content:
                        conversation.append({
                            "turn": turn,
                            "agent": "system",
                            "content": "\n".join(current_content)[:2000],
                        })

            trace = {
                "source": "mast_hf",
                "trace_id": f"mast_hf_{sample.get('trace_id', i)}",
                "framework": sample.get("mas_name"),
                "llm": sample.get("llm_name"),
                "benchmark": sample.get("benchmark_name"),
                "failure_modes": list(failure_modes),
                "conversation": conversation,
                "task": trace_data.get("key", "") if isinstance(trace_data, dict) else "",
            }
            traces.append(trace)

            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1} MAST-Data samples...")

        print(f"  Collected {len(traces)} MAST-Data traces")
        return traces

    except Exception as e:
        print(f"  Error collecting MAST-Data: {e}")
        import traceback
        traceback.print_exc()
        return []


# =============================================================================
# Unification and Output
# =============================================================================

def unify_datasets(
    n8n_traces: List[Dict],
    toolbench_traces: List[Dict],
    mast_traces: List[Dict],
) -> Dict[str, Any]:
    """Combine all traces into unified dataset."""
    print("Unifying datasets...")

    all_traces = []

    # Add n8n traces
    for t in n8n_traces:
        all_traces.append({
            "trace_id": t["trace_id"],
            "source": t["source"],
            "framework": "n8n",
            "task": t.get("workflow_name", ""),
            "failure_modes": [t["failure_mode"]] if t.get("failure_mode") else [],
            "conversation": t["conversation"],
            "metadata": {
                "workflow_id": t.get("workflow_id"),
                "status": t.get("status"),
            },
        })

    # Add ToolBench traces
    for t in toolbench_traces:
        all_traces.append({
            "trace_id": t["trace_id"],
            "source": t["source"],
            "framework": "toolbench",
            "task": t.get("task", ""),
            "failure_modes": [t["failure_mode"]] if t.get("failure_mode") else [],
            "conversation": t["conversation"],
            "metadata": {},
        })

    # Add MAST traces
    for t in mast_traces:
        all_traces.append({
            "trace_id": t["trace_id"],
            "source": t["source"],
            "framework": t.get("framework", ""),
            "task": t.get("benchmark", ""),
            "failure_modes": t.get("failure_modes", []),
            "conversation": t["conversation"],
            "metadata": {
                "llm": t.get("llm"),
            },
        })

    # Statistics
    stats = {
        "total_traces": len(all_traces),
        "by_source": {},
        "by_framework": {},
        "by_failure_mode": {},
    }

    for t in all_traces:
        src = t["source"]
        stats["by_source"][src] = stats["by_source"].get(src, 0) + 1

        fw = t["framework"]
        stats["by_framework"][fw] = stats["by_framework"].get(fw, 0) + 1

        for fm in t["failure_modes"]:
            stats["by_failure_mode"][fm] = stats["by_failure_mode"].get(fm, 0) + 1

    return {
        "created_at": datetime.utcnow().isoformat(),
        "statistics": stats,
        "traces": all_traces,
    }


def main():
    """Main data collection pipeline."""
    print("=" * 60)
    print("Training Data Collection Pipeline")
    print("=" * 60)

    # Load env vars from backend/.env
    env_file = Path(__file__).parent.parent / "backend" / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key in ["N8N_HOST", "N8N_API_KEY"]:
                        os.environ[key] = value

    global N8N_HOST, N8N_API_KEY
    N8N_HOST = os.getenv("N8N_HOST", "https://pisama.app.n8n.cloud")
    N8N_API_KEY = os.getenv("N8N_API_KEY", "")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect from all sources
    print("\n[1/3] Collecting n8n cloud data...")
    n8n_traces = collect_n8n_cloud_executions(limit=200)

    print("\n[2/3] Collecting ToolBench data...")
    toolbench_traces = collect_toolbench_data(limit=500)

    print("\n[3/3] Collecting MAST-Data...")
    mast_traces = collect_mast_huggingface_data(limit=1000)

    # Unify
    print("\n[4/4] Unifying datasets...")
    unified = unify_datasets(n8n_traces, toolbench_traces, mast_traces)

    # Save
    output_file = OUTPUT_DIR / "unified_training_data.json"
    with open(output_file, "w") as f:
        json.dump(unified, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("Collection Complete!")
    print("=" * 60)
    print(f"\nOutput: {output_file}")
    print(f"\nStatistics:")
    print(f"  Total traces: {unified['statistics']['total_traces']}")
    print(f"\n  By source:")
    for src, count in sorted(unified['statistics']['by_source'].items()):
        print(f"    {src}: {count}")
    print(f"\n  By failure mode:")
    for fm, count in sorted(unified['statistics']['by_failure_mode'].items()):
        print(f"    {fm}: {count}")


if __name__ == "__main__":
    main()
