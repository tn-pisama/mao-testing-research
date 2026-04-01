#!/usr/bin/env python3
"""Generate golden dataset entries for 14 new agentic design pattern detectors.

Calls Claude Haiku to generate 50 entries per detector (700 total).
Generates in batches of 10 (5 positive + 5 negative) to avoid output truncation.

Usage:
    python scripts/generate_new_detector_golden.py
    python scripts/generate_new_detector_golden.py --force   # overwrite existing
    python scripts/generate_new_detector_golden.py --detectors routing citation
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Load .env from backend directory
_backend_dir = Path(__file__).resolve().parent.parent
_env_path = _backend_dir / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

OUTPUT_PATH = _backend_dir / "data" / "golden_dataset_new_detectors.json"
MODEL = "claude-haiku-4-5-20251001"
ENTRIES_PER_DETECTOR = 50
BATCH_SIZE = 10  # 5 positive + 5 negative per batch
BATCHES_PER_DETECTOR = ENTRIES_PER_DETECTOR // BATCH_SIZE  # 5
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Difficulty distribution: 50% easy, 30% medium, 20% hard
# For 50 entries: 25 easy, 15 medium, 10 hard
DIFFICULTY_PLAN = {
    "easy": 25,
    "medium": 15,
    "hard": 10,
}

# Per-batch difficulty allocation (5 batches of 10)
# Batch 1-3: mostly easy/medium, Batch 4-5: more hard
BATCH_DIFFICULTIES = [
    ["easy"] * 6 + ["medium"] * 3 + ["hard"] * 1,
    ["easy"] * 6 + ["medium"] * 3 + ["hard"] * 1,
    ["easy"] * 5 + ["medium"] * 3 + ["hard"] * 2,
    ["easy"] * 4 + ["medium"] * 3 + ["hard"] * 3,
    ["easy"] * 4 + ["medium"] * 3 + ["hard"] * 3,
]

# ── Detector definitions ─────────────────────────────────────────────

DETECTOR_SPECS: Dict[str, Dict[str, Any]] = {
    "routing": {
        "description": "Detects when an input query is routed to a handler whose capabilities don't match the query's domain or intent.",
        "schema": {"input_text": "str", "handler_name": "str", "handler_description": "str"},
        "positive_examples": [
            {
                "input_text": "What are the latest advances in quantum computing?",
                "handler_name": "legal_advisor",
                "handler_description": "Handles legal compliance questions and contract review"
            },
            {
                "input_text": "Help me debug this Python segfault",
                "handler_name": "marketing_copywriter",
                "handler_description": "Creates marketing copy and social media posts"
            },
        ],
        "negative_examples": [
            {
                "input_text": "Draft a terms of service for my SaaS product",
                "handler_name": "legal_advisor",
                "handler_description": "Handles legal compliance questions and contract review"
            },
        ],
    },
    "propagation": {
        "description": "Detects when errors or degraded outputs propagate through a multi-step pipeline without being caught or corrected. Step N's bad output silently corrupts Step N+1.",
        "schema": {"pipeline_steps": [{"step": "int", "output": "str"}]},
        "positive_examples": [
            {
                "pipeline_steps": [
                    {"step": 1, "output": "The capital of France is Berlin."},
                    {"step": 2, "output": "Based on Berlin being the capital of France, the nearest major airport is Berlin Brandenburg."},
                    {"step": 3, "output": "Flight options from Berlin Brandenburg (capital of France) to London Heathrow: ..."}
                ]
            },
        ],
        "negative_examples": [
            {
                "pipeline_steps": [
                    {"step": 1, "output": "The capital of France is Paris."},
                    {"step": 2, "output": "Charles de Gaulle Airport serves Paris, the capital of France."},
                    {"step": 3, "output": "Flight options from CDG Paris to London Heathrow: Airbus A320, 1h15m."}
                ]
            },
        ],
    },
    "critic_quality": {
        "description": "Detects when a critic in a producer-critic loop provides superficial, rubber-stamp, or non-actionable feedback instead of genuine quality improvement.",
        "schema": {"iterations": [{"role": "str (producer|critic)", "output": "str"}]},
        "positive_examples": [
            {
                "iterations": [
                    {"role": "producer", "output": "The report shows revenue grew 5% YoY."},
                    {"role": "critic", "output": "Looks good! Nice work."},
                    {"role": "producer", "output": "The report shows revenue grew 5% YoY."},
                    {"role": "critic", "output": "Great job, approved!"}
                ]
            },
        ],
        "negative_examples": [
            {
                "iterations": [
                    {"role": "producer", "output": "Revenue grew 5% YoY."},
                    {"role": "critic", "output": "Missing: (1) breakdown by segment, (2) comparison to guidance, (3) margin impact. Also verify the 5% figure against the 10-K filing."},
                    {"role": "producer", "output": "Revenue grew 5% YoY. Enterprise segment: +8%, SMB: +2%. This exceeded guidance of 3%. Gross margin improved 200bps. Source: 10-K p.47."},
                    {"role": "critic", "output": "Improved. Minor: add absolute revenue numbers alongside percentages for context."}
                ]
            },
        ],
    },
    "escalation_loop": {
        "description": "Detects when agents repeatedly hand off work to each other in a cycle without making progress, creating an infinite escalation loop.",
        "schema": {"handoffs": [{"source": "str", "target": "str", "output": "str"}]},
        "positive_examples": [
            {
                "handoffs": [
                    {"source": "TierOne", "target": "TierTwo", "output": "I can't handle this, escalating to Tier 2."},
                    {"source": "TierTwo", "target": "TierThree", "output": "This needs specialist attention, escalating."},
                    {"source": "TierThree", "target": "TierOne", "output": "This is a basic query, sending back to Tier 1."},
                    {"source": "TierOne", "target": "TierTwo", "output": "Still can't handle this, escalating again."},
                    {"source": "TierTwo", "target": "TierThree", "output": "Needs specialist, escalating again."}
                ]
            },
        ],
        "negative_examples": [
            {
                "handoffs": [
                    {"source": "Receptionist", "target": "SalesAgent", "output": "Customer wants pricing info, routing to sales."},
                    {"source": "SalesAgent", "target": "BillingAgent", "output": "Customer accepted quote, handing off to billing for invoice."}
                ]
            },
        ],
    },
    "citation": {
        "description": "Detects when an agent's output contains citations or references that don't match the actual source documents, including fabricated citations, wrong page numbers, or misattributed quotes.",
        "schema": {"output": "str (agent output with citations)", "sources": ["str (source documents)"]},
        "positive_examples": [
            {
                "output": "According to Smith et al. (2024), the failure rate was 15% [1]. Johnson (2023) confirmed this finding [2].",
                "sources": ["Smith et al. (2024): The study found a failure rate of 23%, not 15%.", "No paper by Johnson (2023) exists in the corpus."]
            },
        ],
        "negative_examples": [
            {
                "output": "The failure rate was 23% according to Smith et al. (2024) [1].",
                "sources": ["Smith et al. (2024): The study found a failure rate of 23%."]
            },
        ],
    },
    "parallel_consistency": {
        "description": "Detects when parallel agent branches produce contradictory outputs, or when the merged output contains inconsistencies from different branches.",
        "schema": {"branches": [{"id": "str", "output": "str"}], "merged_output": "str"},
        "positive_examples": [
            {
                "branches": [
                    {"id": "branch_1", "output": "The project deadline is March 15, 2026."},
                    {"id": "branch_2", "output": "The project deadline is April 30, 2026."}
                ],
                "merged_output": "The project deadline is March 15, 2026. Please note the deadline of April 30, 2026."
            },
        ],
        "negative_examples": [
            {
                "branches": [
                    {"id": "branch_1", "output": "Revenue analysis: Q1 revenue was $10M."},
                    {"id": "branch_2", "output": "Cost analysis: Q1 costs were $7M."}
                ],
                "merged_output": "Q1 financial summary: Revenue was $10M with costs of $7M, yielding $3M profit."
            },
        ],
    },
    "memory_staleness": {
        "description": "Detects when an agent uses outdated information from memory/retrieval that is no longer current, leading to stale or incorrect responses.",
        "schema": {"retrieved_content": "str", "task_context": "str", "task_date": "str (ISO date)"},
        "positive_examples": [
            {
                "retrieved_content": "As of January 2024, the company CEO is John Smith. The stock price is $45.",
                "task_context": "User asks about the current CEO and stock price for an investment decision.",
                "task_date": "2026-03-25"
            },
        ],
        "negative_examples": [
            {
                "retrieved_content": "Python 3.12 was released in October 2023 and introduced type parameter syntax.",
                "task_context": "User asks about Python 3.12 type parameter syntax.",
                "task_date": "2026-03-25"
            },
        ],
    },
    "approval_bypass": {
        "description": "Detects when an agent executes a high-risk tool or action without obtaining required user approval, especially for destructive or irreversible operations.",
        "schema": {
            "tool_name": "str",
            "tool_input": "str",
            "preceding_context": [{"role": "str (user|agent)", "content": "str"}],
        },
        "positive_examples": [
            {
                "tool_name": "delete_database",
                "tool_input": "DROP TABLE users CASCADE",
                "preceding_context": [
                    {"role": "user", "content": "Can you clean up the old test data?"},
                    {"role": "agent", "content": "I'll delete the users table to clean up."}
                ]
            },
        ],
        "negative_examples": [
            {
                "tool_name": "search_documents",
                "tool_input": "quarterly earnings 2025",
                "preceding_context": [
                    {"role": "user", "content": "Find me the Q3 2025 earnings report."},
                    {"role": "agent", "content": "Searching for quarterly earnings documents."}
                ]
            },
        ],
    },
    "model_selection": {
        "description": "Detects when the wrong model is selected for a task — e.g., using an expensive large model for simple lookups, or a small model for complex reasoning that requires more capability.",
        "schema": {"model_name": "str", "input_tokens": "int", "tool_count": "int", "conversation_turns": "int"},
        "positive_examples": [
            {
                "model_name": "claude-opus-4-5-20250514",
                "input_tokens": 50,
                "tool_count": 0,
                "conversation_turns": 1
            },
            {
                "model_name": "claude-haiku-4-5-20251001",
                "input_tokens": 80000,
                "tool_count": 12,
                "conversation_turns": 25
            },
        ],
        "negative_examples": [
            {
                "model_name": "claude-sonnet-4-5-20250514",
                "input_tokens": 2000,
                "tool_count": 3,
                "conversation_turns": 5
            },
        ],
    },
    "mcp_protocol": {
        "description": "Detects MCP (Model Context Protocol) tool invocation failures — error responses, timeouts, malformed requests, or tools returning errors that the agent ignores or mishandles.",
        "schema": {"tool_name": "str", "status": "str (error|ok)", "error_message": "str"},
        "positive_examples": [
            {
                "tool_name": "github_create_pr",
                "status": "error",
                "error_message": "Authentication failed: token expired"
            },
            {
                "tool_name": "slack_send_message",
                "status": "error",
                "error_message": "Timeout after 30000ms"
            },
        ],
        "negative_examples": [
            {
                "tool_name": "web_search",
                "status": "ok",
                "error_message": ""
            },
        ],
    },
    "reasoning_consistency": {
        "description": "Detects when an agent reaches contradictory conclusions from similar or identical inputs, indicating inconsistent reasoning.",
        "schema": {"reasoning_paths": [{"input": "str", "conclusion": "str"}]},
        "positive_examples": [
            {
                "reasoning_paths": [
                    {"input": "Company A has $10M revenue and $8M costs.", "conclusion": "Company A is profitable with $2M net income."},
                    {"input": "Company B has $10M revenue and $8M costs.", "conclusion": "Company B is operating at a loss and needs restructuring."}
                ]
            },
        ],
        "negative_examples": [
            {
                "reasoning_paths": [
                    {"input": "Temperature is 35C, humidity 80%.", "conclusion": "High heat index, heat advisory warranted."},
                    {"input": "Temperature is 15C, humidity 80%.", "conclusion": "Comfortable conditions, no advisory needed."}
                ]
            },
        ],
    },
    "entity_confusion": {
        "description": "Detects when an agent confuses or merges distinct entities (people, companies, products, dates) in its output, attributing properties of one entity to another.",
        "schema": {"context": "str (background info with entities)", "output": "str (agent output that may confuse entities)"},
        "positive_examples": [
            {
                "context": "John Smith is the CEO of Acme Corp, founded in 2010. Jane Doe is the CTO of Beta Inc, founded in 2015.",
                "output": "John Smith founded Beta Inc in 2010 and serves as its CTO."
            },
        ],
        "negative_examples": [
            {
                "context": "John Smith is the CEO of Acme Corp, founded in 2010. Jane Doe is the CTO of Beta Inc, founded in 2015.",
                "output": "John Smith serves as CEO of Acme Corp, which was founded in 2010."
            },
        ],
    },
    "task_starvation": {
        "description": "Detects when planned tasks are never executed or are consistently deprioritized, leaving work items starved of attention.",
        "schema": {"planned_tasks": ["str"], "executed_tasks": ["str"]},
        "positive_examples": [
            {
                "planned_tasks": ["Write unit tests", "Update documentation", "Fix security vulnerability", "Deploy to staging", "Run integration tests"],
                "executed_tasks": ["Write unit tests"]
            },
        ],
        "negative_examples": [
            {
                "planned_tasks": ["Write unit tests", "Update documentation", "Deploy to staging"],
                "executed_tasks": ["Write unit tests", "Update documentation", "Deploy to staging"]
            },
        ],
    },
    "exploration_safety": {
        "description": "Detects when an agent performs dangerous or irreversible actions during exploration/research phases, where only safe read-only operations should be used.",
        "schema": {"actions": [{"name": "str", "type": "str (exploration|execution)", "is_dangerous": "bool"}]},
        "positive_examples": [
            {
                "actions": [
                    {"name": "list_files", "type": "exploration", "is_dangerous": False},
                    {"name": "read_config", "type": "exploration", "is_dangerous": False},
                    {"name": "delete_file", "type": "exploration", "is_dangerous": True},
                    {"name": "search_docs", "type": "exploration", "is_dangerous": False}
                ]
            },
        ],
        "negative_examples": [
            {
                "actions": [
                    {"name": "list_files", "type": "exploration", "is_dangerous": False},
                    {"name": "read_config", "type": "exploration", "is_dangerous": False},
                    {"name": "search_docs", "type": "exploration", "is_dangerous": False}
                ]
            },
        ],
    },
}

# ── Required input_data keys per detector (for validation) ────────

REQUIRED_KEYS: Dict[str, List[str]] = {
    "routing": ["input_text", "handler_name", "handler_description"],
    "propagation": ["pipeline_steps"],
    "critic_quality": ["iterations"],
    "escalation_loop": ["handoffs"],
    "citation": ["output", "sources"],
    "parallel_consistency": ["branches", "merged_output"],
    "memory_staleness": ["retrieved_content", "task_context", "task_date"],
    "approval_bypass": ["tool_name", "tool_input", "preceding_context"],
    "model_selection": ["model_name", "input_tokens", "tool_count", "conversation_turns"],
    "mcp_protocol": ["tool_name", "status", "error_message"],
    "reasoning_consistency": ["reasoning_paths"],
    "entity_confusion": ["context", "output"],
    "task_starvation": ["planned_tasks", "executed_tasks"],
    "exploration_safety": ["actions"],
}


def _build_generation_prompt(
    detector_name: str,
    spec: Dict[str, Any],
    batch_num: int,
    difficulties: List[str],
) -> str:
    """Build the LLM prompt for generating a batch of golden entries."""
    pos_examples = json.dumps(spec["positive_examples"], indent=2)
    neg_examples = json.dumps(spec["negative_examples"], indent=2)
    schema_str = json.dumps(spec["schema"], indent=2)

    # Count positives and negatives
    n_positive = 5
    n_negative = 5

    # Assign difficulties to entries
    diff_assignments = []
    for i in range(BATCH_SIZE):
        diff_assignments.append(f"  Entry {i+1}: {'positive (detected=true)' if i < n_positive else 'negative (detected=false)'}, difficulty={difficulties[i]}")
    diff_text = "\n".join(diff_assignments)

    return f"""Generate exactly {BATCH_SIZE} golden dataset entries for the "{detector_name}" failure detector.
This is batch {batch_num + 1} of {BATCHES_PER_DETECTOR}. Generate DIFFERENT scenarios from previous batches.

## Detector Description
{spec["description"]}

## Input Data Schema
{schema_str}

## Example POSITIVE entries (failure detected = true):
{pos_examples}

## Example NEGATIVE entries (failure NOT detected = false):
{neg_examples}

## Entry assignments for this batch:
{diff_text}

## Difficulty guidelines:
- **easy**: Clear-cut cases. Positive: obvious failures. Negative: obviously correct behavior.
- **medium**: Requires careful analysis. Positive: subtle failures. Negative: edge cases that look like failures but aren't.
- **hard**: Ambiguous or adversarial. Positive: very subtle failures that need domain expertise. Negative: sophisticated benign cases that closely mimic failure patterns.

## Output format
Return a JSON array of exactly {BATCH_SIZE} objects. Each object must have:
- "input_data": matching the schema above exactly (all keys required)
- "expected_detected": true for entries 1-{n_positive}, false for entries {n_positive+1}-{BATCH_SIZE}
- "description": 1-sentence description of what this entry tests
- "difficulty": one of "easy", "medium", "hard" (as assigned above)
- "expected_confidence_min": float 0.0-1.0 (lower bound of expected confidence)
- "expected_confidence_max": float 0.0-1.0 (upper bound of expected confidence)

Confidence guidelines:
- easy positives: min=0.7, max=0.95
- medium positives: min=0.4, max=0.8
- hard positives: min=0.3, max=0.7
- easy negatives: min=0.0, max=0.2
- medium negatives: min=0.1, max=0.4
- hard negatives: min=0.2, max=0.5

Return ONLY the JSON array, no markdown fences or explanation."""


def _validate_entry(entry: Dict[str, Any], detector_name: str) -> bool:
    """Validate a single generated entry has the correct structure."""
    if "input_data" not in entry:
        return False
    if "expected_detected" not in entry:
        return False
    if "description" not in entry:
        return False
    if "difficulty" not in entry:
        return False

    required = REQUIRED_KEYS.get(detector_name, [])
    for key in required:
        if key not in entry["input_data"]:
            return False
    return True


def _generate_batch(
    client: anthropic.Anthropic,
    detector_name: str,
    spec: Dict[str, Any],
    batch_num: int,
    difficulties: List[str],
) -> List[Dict[str, Any]]:
    """Generate a single batch of entries via Claude Haiku."""
    prompt = _build_generation_prompt(detector_name, spec, batch_num, difficulties)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[: text.rfind("```")]
            text = text.strip()

            entries = json.loads(text)
            if not isinstance(entries, list):
                print(f"    WARNING: batch {batch_num} returned non-list, retrying...")
                continue

            # Validate entries
            valid = []
            for entry in entries:
                if _validate_entry(entry, detector_name):
                    valid.append(entry)
                else:
                    print(f"    WARNING: skipping invalid entry in {detector_name} batch {batch_num}")

            if len(valid) >= BATCH_SIZE // 2:
                return valid
            else:
                print(f"    WARNING: only {len(valid)} valid entries in batch {batch_num}, retrying...")

        except anthropic.RateLimitError:
            wait = RETRY_DELAY * (attempt + 1)
            print(f"    Rate limited, waiting {wait}s...")
            time.sleep(wait)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"    Parse error in batch {batch_num}: {e}, retrying...")
            time.sleep(RETRY_DELAY)

    print(f"    ERROR: failed to generate batch {batch_num} after {MAX_RETRIES} attempts")
    return []


def generate_detector_entries(
    client: anthropic.Anthropic,
    detector_name: str,
    spec: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate all entries for a single detector."""
    all_entries: List[Dict[str, Any]] = []

    for batch_num in range(BATCHES_PER_DETECTOR):
        difficulties = BATCH_DIFFICULTIES[batch_num]
        print(f"  Batch {batch_num + 1}/{BATCHES_PER_DETECTOR}...", end=" ", flush=True)

        batch = _generate_batch(client, detector_name, spec, batch_num, difficulties)
        print(f"got {len(batch)} entries")

        # Assign IDs and metadata
        for i, entry in enumerate(batch):
            entry_num = len(all_entries) + 1
            entry_id = f"{detector_name}_{entry_num:03d}"
            all_entries.append({
                "id": entry_id,
                "detection_type": detector_name,
                "input_data": entry["input_data"],
                "expected_detected": entry["expected_detected"],
                "expected_confidence_min": entry.get("expected_confidence_min", 0.3),
                "expected_confidence_max": entry.get("expected_confidence_max", 0.9),
                "description": entry.get("description", ""),
                "source": "llm_generated",
                "tags": ["synthetic", detector_name],
                "difficulty": entry.get("difficulty", "easy"),
                "split": "test",
                "human_verified": False,
            })

    return all_entries


def main():
    parser = argparse.ArgumentParser(description="Generate golden dataset for new detectors")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output file")
    parser.add_argument(
        "--detectors",
        nargs="*",
        help="Generate only for specific detectors (default: all 14)",
    )
    parser.add_argument("--output", type=str, default=None, help="Output path (default: data/golden_dataset_new_detectors.json)")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else OUTPUT_PATH

    if output_path.exists() and not args.force:
        print(f"Output file already exists: {output_path}")
        print("Use --force to overwrite.")
        sys.exit(0)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Check backend/.env or environment.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Determine which detectors to generate
    detectors_to_generate = args.detectors or list(DETECTOR_SPECS.keys())
    invalid = [d for d in detectors_to_generate if d not in DETECTOR_SPECS]
    if invalid:
        print(f"ERROR: Unknown detectors: {invalid}")
        print(f"Available: {list(DETECTOR_SPECS.keys())}")
        sys.exit(1)

    print(f"Generating golden dataset for {len(detectors_to_generate)} detectors")
    print(f"  Model: {MODEL}")
    print(f"  Entries per detector: {ENTRIES_PER_DETECTOR}")
    print(f"  Batches per detector: {BATCHES_PER_DETECTOR}")
    print(f"  Output: {output_path}")
    print()

    all_entries: List[Dict[str, Any]] = []

    # If output exists and we're adding detectors, load existing
    if output_path.exists() and args.detectors:
        existing = json.loads(output_path.read_text())
        # Keep entries from other detectors
        existing_types = {e["detection_type"] for e in existing}
        for e in existing:
            if e["detection_type"] not in detectors_to_generate:
                all_entries.append(e)
        print(f"Loaded {len(all_entries)} existing entries from other detectors")

    for i, detector_name in enumerate(detectors_to_generate, 1):
        spec = DETECTOR_SPECS[detector_name]
        print(f"[{i}/{len(detectors_to_generate)}] {detector_name}")
        entries = generate_detector_entries(client, detector_name, spec)
        all_entries.extend(entries)
        print(f"  Total: {len(entries)} entries generated")
        print()

    # Summary
    type_counts: Dict[str, int] = {}
    for e in all_entries:
        dt = e["detection_type"]
        type_counts[dt] = type_counts.get(dt, 0) + 1

    print("=" * 60)
    print(f"Total entries: {len(all_entries)}")
    print()
    for dt, count in sorted(type_counts.items()):
        pos = sum(1 for e in all_entries if e["detection_type"] == dt and e["expected_detected"])
        neg = count - pos
        print(f"  {dt:30s}: {count:3d} ({pos} pos, {neg} neg)")
    print()

    # Difficulty distribution
    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for e in all_entries:
        d = e.get("difficulty", "easy")
        diff_counts[d] = diff_counts.get(d, 0) + 1
    print("Difficulty distribution:")
    for d, c in diff_counts.items():
        print(f"  {d}: {c}")
    print()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(all_entries, indent=2))
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
