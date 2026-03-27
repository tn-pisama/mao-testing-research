#!/usr/bin/env python3
"""Extract REAL golden dataset entries from local Claude Code traces.

Parses ~/.claude/projects/*/subagents/agent-*.jsonl transcripts to create
golden dataset entries for adaptive_thinking, subagent_boundary, agent_teams,
and scheduled_task detectors.

Uses ACTUAL token counts, tool calls, and session data from real Claude Code usage.

Usage:
    cd backend && python scripts/extract_claude_code_golden.py
"""

import json
import os
import sys
import uuid
from collections import defaultdict
from glob import glob
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CLAUDE_DIR = os.path.expanduser("~/.claude")
PROJECTS_DIR = os.path.join(CLAUDE_DIR, "projects", "-Users-tuomonikulainen")

# Model pricing (per token, approximate)
MODEL_PRICING = {
    "claude-opus-4-6": {"input": 0.000015, "output": 0.000075, "cache_read": 0.0000015},
    "claude-sonnet-4-6": {"input": 0.000003, "output": 0.000015, "cache_read": 0.0000003},
    "claude-haiku-4-5-20251001": {"input": 0.000001, "output": 0.000005, "cache_read": 0.0000001},
}

# Subagent type → expected tools
SUBAGENT_EXPECTED_TOOLS = {
    "Explore": {"Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"},
    "Plan": {"Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"},
    "general-purpose": {"Read", "Write", "Edit", "Bash", "Grep", "Glob", "Agent", "WebSearch", "WebFetch"},
}

# Tools that are read-only (safe for any subagent)
READ_ONLY_TOOLS = {"Read", "Grep", "Glob", "WebSearch", "WebFetch"}
# Tools that modify state (restricted for explore/plan agents)
WRITE_TOOLS = {"Write", "Edit", "Bash", "NotebookEdit"}


def parse_transcript(filepath):
    """Parse a subagent JSONL transcript into structured data."""
    messages = []
    metadata = {}
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_creation = 0
    total_cache_read = 0
    tools_used = set()
    model = None

    with open(filepath) as f:
        for line in f:
            try:
                d = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            msg = d.get("message", {})

            if not metadata:
                metadata = {
                    "session_id": d.get("sessionId", ""),
                    "agent_id": d.get("agentId", ""),
                    "slug": d.get("slug", ""),
                    "timestamp": d.get("timestamp", ""),
                    "cwd": d.get("cwd", ""),
                }

            if msg.get("role") == "assistant":
                usage = msg.get("usage", {})
                if usage:
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)
                    total_cache_creation += usage.get("cache_creation_input_tokens", 0)
                    total_cache_read += usage.get("cache_read_input_tokens", 0)
                    if not model:
                        model = msg.get("model", "")

                for c in msg.get("content", []):
                    if c.get("type") == "tool_use":
                        tools_used.add(c.get("name", ""))
                    if c.get("type") == "text":
                        text = c.get("text", "")
                        messages.append({"role": "assistant", "text": text[:200]})

            elif msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    messages.append({"role": "user", "text": content[:200]})

    return {
        "metadata": metadata,
        "model": model or "unknown",
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cache_creation": total_cache_creation,
        "total_cache_read": total_cache_read,
        "tools_used": sorted(tools_used),
        "message_count": len(messages),
        "messages_sample": messages[:5],  # First 5 for context
    }


def extract_adaptive_thinking(transcripts):
    """Extract adaptive_thinking entries from real token usage."""
    entries = []

    for t in transcripts:
        if t["total_output_tokens"] == 0:
            continue

        thinking_tokens = t["total_cache_creation"]  # Thinking generates cache
        output_tokens = t["total_output_tokens"]
        input_tokens = t["total_input_tokens"] + t["total_cache_read"]

        # Estimate cost
        pricing = MODEL_PRICING.get(t["model"], MODEL_PRICING["claude-haiku-4-5-20251001"])
        cost = (input_tokens * pricing["input"] +
                output_tokens * pricing["output"] +
                t["total_cache_read"] * pricing["cache_read"])

        # Estimate latency (rough: ~3ms per output token)
        latency_ms = output_tokens * 3 + 1000  # Base 1s + token time

        # Determine effort level from model
        if "opus" in t["model"]:
            effort = "max" if thinking_tokens > 10000 else "high"
        elif "sonnet" in t["model"]:
            effort = "high" if thinking_tokens > 5000 else "medium"
        else:
            effort = "medium" if thinking_tokens > 2000 else "low"

        # Label: is this overthinking, underthinking, or normal?
        ratio = thinking_tokens / max(output_tokens, 1)
        if ratio > 20 or cost > 1.0:
            expected = True
            desc = f"REAL: {t['model']} overthinking ({ratio:.0f}x ratio, ${cost:.3f})"
            difficulty = "medium"
        elif output_tokens < 20 and effort == "low":
            expected = True
            desc = f"REAL: {t['model']} underthinking ({output_tokens} output tokens)"
            difficulty = "easy"
        elif ratio < 15 and cost < 0.50:
            expected = False
            desc = f"REAL: {t['model']} normal ({ratio:.0f}x ratio, ${cost:.3f})"
            difficulty = "easy"
        else:
            # Ambiguous — skip to avoid mislabeling
            continue

        entries.append({
            "id": f"adaptive_thinking-real-{uuid.uuid4().hex[:8]}",
            "detection_type": "adaptive_thinking",
            "input_data": {
                "effort_level": effort,
                "thinking_tokens": thinking_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "cost_usd": round(cost, 4),
            },
            "expected_detected": expected,
            "description": desc,
            "source": "claude_code_real",
            "difficulty": difficulty,
            "split": "train",
        })

    return entries


def extract_subagent_boundary(transcripts):
    """Extract subagent_boundary entries from real tool usage."""
    entries = []

    for t in transcripts:
        if not t["tools_used"]:
            continue

        slug = t["metadata"].get("slug", "")
        tools = set(t["tools_used"])

        # Infer expected tools from subagent type
        if any(kw in slug.lower() for kw in ["explore", "search", "find", "research"]):
            expected_type = "Explore"
            allowed = SUBAGENT_EXPECTED_TOOLS["Explore"]
        elif any(kw in slug.lower() for kw in ["plan", "design", "architect"]):
            expected_type = "Plan"
            allowed = SUBAGENT_EXPECTED_TOOLS["Plan"]
        else:
            expected_type = "general-purpose"
            allowed = SUBAGENT_EXPECTED_TOOLS["general-purpose"]

        violations = tools - allowed
        # For explore/plan agents, check if they used write tools
        write_violations = tools & WRITE_TOOLS if expected_type in ("Explore", "Plan") else set()

        instruction = ""
        if t["messages_sample"]:
            for m in t["messages_sample"]:
                if m["role"] == "user":
                    instruction = m["text"]
                    break

        if write_violations and expected_type in ("Explore", "Plan"):
            expected = True
            desc = f"REAL: {expected_type} agent used {write_violations} (should be read-only)"
        elif not violations:
            expected = False
            desc = f"REAL: {expected_type} agent used only allowed tools: {sorted(tools)}"
        else:
            continue  # Ambiguous

        entries.append({
            "id": f"subagent_boundary-real-{uuid.uuid4().hex[:8]}",
            "detection_type": "subagent_boundary",
            "input_data": {
                "allowed_tools": sorted(allowed),
                "actual_tool_calls": sorted(tools),
                "parent_instruction": instruction[:200],
                "subagent_output": "",  # Redacted for privacy
                "spawn_attempts": 0,
            },
            "expected_detected": expected,
            "description": desc,
            "source": "claude_code_real",
            "difficulty": "medium",
            "split": "train",
        })

    return entries


def extract_agent_teams(session_transcripts):
    """Extract agent_teams entries from multi-subagent sessions."""
    entries = []

    for session_id, transcripts in session_transcripts.items():
        if len(transcripts) < 2:
            continue

        # Build task list from subagent prompts
        task_list = []
        messages = []
        for i, t in enumerate(transcripts):
            agent_id = t["metadata"].get("agent_id", f"agent_{i}")
            # First user message = the task assignment
            for m in t["messages_sample"]:
                if m["role"] == "user":
                    task_list.append({
                        "id": f"t{i}",
                        "assigned_to": agent_id[:12],
                        "status": "done" if t["total_output_tokens"] > 50 else "pending",
                        "description": m["text"][:100],
                    })
                    messages.append({
                        "from": "lead",
                        "to": agent_id[:12],
                        "content": m["text"][:100],
                    })
                    break
            # Check for tool overlap (file conflicts)
            for m in t["messages_sample"]:
                if m["role"] == "assistant":
                    messages.append({
                        "from": agent_id[:12],
                        "to": "lead",
                        "content": m["text"][:100],
                    })

        # Check for duplicate task descriptions (real conflict indicator)
        task_descs = [t.get("description", "") for t in task_list]
        has_duplicate = len(task_descs) != len(set(task_descs))
        all_done = all(t.get("status") == "done" for t in task_list)

        if has_duplicate:
            expected = True
            desc = f"REAL: {len(transcripts)} agents, duplicate task assignments"
        elif all_done and len(messages) > 2:
            expected = False
            desc = f"REAL: {len(transcripts)} agents, all tasks completed cleanly"
        else:
            expected = False
            desc = f"REAL: {len(transcripts)} agents, normal parallel work"

        entries.append({
            "id": f"agent_teams-real-{uuid.uuid4().hex[:8]}",
            "detection_type": "agent_teams",
            "input_data": {
                "task_list": task_list,
                "messages": messages[:20],  # Cap at 20
                "team_size": len(transcripts),
            },
            "expected_detected": expected,
            "description": desc,
            "source": "claude_code_real",
            "difficulty": "medium",
            "split": "train",
        })

    return entries


def main():
    print("=" * 60)
    print("Extracting REAL Claude Code Golden Data")
    print("=" * 60)

    # Find all subagent transcripts
    pattern = os.path.join(PROJECTS_DIR, "*/subagents/agent-*.jsonl")
    transcript_files = glob(pattern)
    print(f"\nFound {len(transcript_files)} subagent transcripts")

    # Parse all transcripts
    print("Parsing transcripts...")
    transcripts = []
    session_groups = defaultdict(list)

    for i, filepath in enumerate(transcript_files):
        if i % 100 == 0 and i > 0:
            print(f"  Parsed {i}/{len(transcript_files)}...")
        try:
            t = parse_transcript(filepath)
            transcripts.append(t)
            session_groups[t["metadata"]["session_id"]].append(t)
        except Exception as e:
            continue

    print(f"Successfully parsed {len(transcripts)} transcripts")
    print(f"Unique sessions: {len(session_groups)}")

    # Extract entries for each detector
    print("\n--- Phase 1: adaptive_thinking ---")
    at_entries = extract_adaptive_thinking(transcripts)
    tp = sum(1 for e in at_entries if e["expected_detected"])
    tn = len(at_entries) - tp
    print(f"  Extracted {len(at_entries)} entries ({tp} TP, {tn} TN)")

    print("\n--- Phase 2: subagent_boundary ---")
    sb_entries = extract_subagent_boundary(transcripts)
    tp = sum(1 for e in sb_entries if e["expected_detected"])
    tn = len(sb_entries) - tp
    print(f"  Extracted {len(sb_entries)} entries ({tp} TP, {tn} TN)")

    print("\n--- Phase 3: agent_teams ---")
    at2_entries = extract_agent_teams(session_groups)
    tp = sum(1 for e in at2_entries if e["expected_detected"])
    tn = len(at2_entries) - tp
    print(f"  Extracted {len(at2_entries)} entries ({tp} TP, {tn} TN)")

    all_real = at_entries + sb_entries + at2_entries
    print(f"\nTotal real entries: {len(all_real)}")

    # Load and update golden dataset
    golden_path = os.path.join(os.path.dirname(__file__), "..", "data", "golden_dataset_expanded.json")
    with open(golden_path) as f:
        existing = json.load(f)

    # Remove previous real entries (keep synthetic as fallback)
    existing = [e for e in existing if e.get("source") != "claude_code_real"]
    existing.extend(all_real)

    with open(golden_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    print(f"\nSaved to golden dataset. Total: {len(existing)} entries")

    # Run detectors on real entries
    print("\n" + "=" * 60)
    print("Validating detectors on REAL data")
    print("=" * 60)

    from app.detection_enterprise.detector_adapters import DETECTOR_RUNNERS
    from app.detection.validation import DetectionType
    from app.detection_enterprise.golden_dataset import GoldenDatasetEntry

    for det_type_str in ["adaptive_thinking", "subagent_boundary", "agent_teams"]:
        dt = DetectionType(det_type_str)
        runner = DETECTOR_RUNNERS.get(dt)
        if not runner:
            print(f"\n{det_type_str}: NO RUNNER")
            continue

        real_entries = [e for e in all_real if e["detection_type"] == det_type_str]
        if not real_entries:
            print(f"\n{det_type_str}: No real entries")
            continue

        tp, tn, fp, fn = 0, 0, 0, 0
        for e in real_entries:
            entry = GoldenDatasetEntry(id=e["id"], detection_type=dt,
                                       input_data=e["input_data"],
                                       expected_detected=e["expected_detected"])
            try:
                detected, confidence = runner(entry)
            except Exception:
                fn += 1
                continue
            if e["expected_detected"] and detected: tp += 1
            elif not e["expected_detected"] and not detected: tn += 1
            elif detected and not e["expected_detected"]: fp += 1
            else: fn += 1

        total = tp + tn + fp + fn
        acc = (tp + tn) / total if total else 0
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        print(f"\n{det_type_str} (REAL data):")
        print(f"  {total} entries | TP={tp} TN={tn} FP={fp} FN={fn}")
        print(f"  Accuracy={acc:.0%} P={prec:.2f} R={rec:.2f} F1={f1:.3f}")


if __name__ == "__main__":
    main()
