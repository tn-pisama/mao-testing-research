#!/usr/bin/env python3 -u
"""Inverted LLM judge evaluation: ask "Is this CORRECT?" instead of "Is this a failure?"

Previous approaches asked "Is this a failure?" and the LLM said NO to everything
(conservative bias). This script flips the question: "Is this CORRECT?" — now a
NO means failure detected, which exploits the same conservative bias in our favor.

Round 1: Haiku with inverted prompts on all 10 struggling detectors (30 entries each)
Round 2: Sonnet on top 5 hardest (if Round 1 shows improvement)

Usage:
    cd ~/mao-testing-research/backend
    python scripts/run_inverted_judge.py
"""

import argparse
import os
import sys
import json
import time
import re
import gc
import random
import logging
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Environment setup (must happen before any app imports)
# ---------------------------------------------------------------------------
os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
sys.path.insert(0, "/Users/tuomonikulainen/mao-testing-research/backend")

from pathlib import Path

env_path = Path("/Users/tuomonikulainen/mao-testing-research/backend/.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App imports
# ---------------------------------------------------------------------------
from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
from app.detection_enterprise.calibrate import _get_golden_dataset
from app.detection_enterprise.detector_adapters import DETECTOR_RUNNERS

# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------
from anthropic import Anthropic

client = Anthropic()

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-20250514"

# Cost per token (USD) for each model
HAIKU_COST = {"input": 1 / 1_000_000, "output": 5 / 1_000_000}
SONNET_COST = {"input": 3 / 1_000_000, "output": 15 / 1_000_000}

# ---------------------------------------------------------------------------
# INVERTED prompts: ask "Is this CORRECT?" — NO means failure detected
# ---------------------------------------------------------------------------
INVERTED_PROMPTS = {
    "hallucination": """Evaluate this agent output for factual accuracy.

Sources provided:
{sources}

Agent output:
{output}

Is the agent's output factually accurate and fully supported by the sources? Does it contain ONLY information that can be verified from the provided sources?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "grounding": """Evaluate whether this agent output is properly grounded.

Source documents:
{source_documents}

Agent output:
{agent_output}

Is every factual claim in the output directly supported by the source documents?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "specification": """Evaluate whether this task specification matches the user's intent.

User's intent: {user_intent}

Task specification: {task_specification}

Does the specification accurately capture what the user asked for, without adding unrequested scope or missing key requirements?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "derailment": """Evaluate whether this agent stayed on task.

Task: {task}

Agent output: {output}

Did the agent address the assigned task? Is the output relevant to what was asked?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "completion": """Evaluate whether this agent's completion assessment is accurate.

Task: {task}
Required subtasks: {subtasks}
Success criteria: {success_criteria}

Agent output: {agent_output}

Did the agent accurately assess and report its progress? Are all subtasks and criteria addressed?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "context": """Evaluate whether this agent properly used the provided context.

Context: {context}

Agent output: {output}

Did the agent incorporate the key information from the context into its response?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "communication": """Evaluate this inter-agent communication.

Message from sender: {sender_message}

Response from receiver: {receiver_response}

Does the receiver's response adequately address what the sender communicated?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "withholding": """Evaluate whether this agent communicated all important findings.

Agent's internal findings: {internal_state}

What agent communicated: {agent_output}

Did the agent share all critical information (errors, security issues, blockers) from its findings?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "convergence": """Evaluate these optimization metrics.

Metrics: {metrics}
Direction: {direction}
Window: {window_size}

Are these metrics showing healthy progress in the desired direction?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",

    "retrieval_quality": """Evaluate this retrieval result.

Query: {query}
Retrieved documents: {retrieved_documents}
Agent output: {agent_output}

Are the retrieved documents relevant to the query? Did the retrieval serve the agent's needs?

Think step by step. Then on the final line, answer exactly one word: CORRECT or INCORRECT""",
}

# Detectors to test (all 10 struggling ones)
TARGETS = [
    "hallucination",
    "grounding",
    "specification",
    "derailment",
    "completion",
    "context",
    "communication",
    "withholding",
    "convergence",
    "retrieval_quality",
]

# Top 5 hardest for Sonnet round
SONNET_TARGETS = [
    "hallucination",
    "grounding",
    "context",
    "derailment",
    "retrieval_quality",
]

MAX_ENTRIES_PER_DETECTOR = 30

# Placeholder phrases that indicate a stub entry with no real content
_STUB_MARKERS = [
    "benchmark trace",
    "Agent output for trace",
    "Task from gaia",
    "placeholder",
    "TODO: fill in",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_real_content(entry: GoldenDatasetEntry) -> bool:
    """Return True if the entry has substantive content (not a stub)."""
    has_substance = False
    for key, value in entry.input_data.items():
        text = ""
        if isinstance(value, str):
            text = value
        elif isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                text = " ".join(str(v) for v in first.values())
            elif isinstance(first, str):
                text = first
            elif isinstance(first, (int, float)):
                has_substance = True
                continue
        elif isinstance(value, dict):
            text = " ".join(str(v) for v in value.values())

        if any(marker.lower() in text.lower() for marker in _STUB_MARKERS):
            return False
        if isinstance(value, str) and len(value) > 30:
            has_substance = True
        elif isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                if any(isinstance(v, (int, float)) for v in first.values()):
                    has_substance = True
                elif any(isinstance(v, str) and len(v) > 30 for v in first.values()):
                    has_substance = True
            elif isinstance(first, str) and len(first) > 30:
                has_substance = True
            elif isinstance(first, (int, float)):
                has_substance = True
    return has_substance


def _format_value(value: Any) -> str:
    """Format a single value for prompt substitution."""
    if isinstance(value, dict):
        if "content" in value:
            return str(value["content"])[:800]
        return json.dumps(value, indent=2)[:800]
    return str(value)[:800]


def _format_prompt(det_name: str, entry: GoldenDatasetEntry) -> str:
    """Format an inverted prompt by substituting fields from entry.input_data."""
    template = INVERTED_PROMPTS[det_name]
    formatted = template
    for key, value in entry.input_data.items():
        placeholder = "{" + key + "}"
        if placeholder not in formatted:
            continue
        if isinstance(value, list):
            parts = []
            for i, item in enumerate(value[:10]):
                parts.append(f"[{i+1}] {_format_value(item)}")
            value_str = "\n".join(parts)
        elif isinstance(value, dict):
            value_str = _format_value(value)
        else:
            value_str = str(value)[:1000]
        formatted = formatted.replace(placeholder, value_str)

    # Remove any unfilled placeholders
    formatted = re.sub(r"\{[a-z_]+\}", "[not provided]", formatted)
    return formatted


def _call_inverted_judge(
    model: str, prompt: str, cost_rates: Dict[str, float]
) -> Tuple[bool, float, str]:
    """Call LLM with inverted prompt.

    Returns (detected, cost_usd, raw_answer).
    INVERTED logic: INCORRECT = failure detected.
    """
    response = client.messages.create(
        model=model,
        max_tokens=500,
        timeout=60.0,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = response.content[0].text.strip()
    last_line = answer.strip().split("\n")[-1].strip().upper()

    # INVERTED: "INCORRECT" means failure detected
    detected = "INCORRECT" in last_line

    cost = (
        response.usage.input_tokens * cost_rates["input"]
        + response.usage.output_tokens * cost_rates["output"]
    )
    return detected, cost, answer


def _compute_f1(predictions: list, ground_truths: list) -> dict:
    """Compute precision, recall, F1."""
    tp = fp = fn = tn = 0
    for predicted, expected in zip(predictions, ground_truths):
        if expected and predicted:
            tp += 1
        elif expected and not predicted:
            fn += 1
        elif not expected and predicted:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "f1": round(f1, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def _get_entries_for_detector(
    dataset, det_name: str
) -> Tuple[List[GoldenDatasetEntry], str]:
    """Get balanced, real-content entries for a detector."""
    det_type = DetectionType(det_name)
    all_entries = dataset.get_entries_by_type(det_type)
    all_entries = [e for e in all_entries if _has_real_content(e)]

    if not all_entries:
        return [], "none"

    real_sources = {
        "real", "structural", "mast_benchmark", "swe_bench",
        "real_trace", "n8n_production", "production", "external",
    }
    real_entries = [
        e for e in all_entries
        if any(rs in (e.source or "").lower() for rs in real_sources)
    ]

    if len(real_entries) >= 10:
        pool = real_entries
        source_note = "real"
    else:
        pool = all_entries
        source_note = f"all ({len(real_entries)} real)"

    # Balance positive and negative entries
    positives = [e for e in pool if e.expected_detected]
    negatives = [e for e in pool if not e.expected_detected]
    half = MAX_ENTRIES_PER_DETECTOR // 2
    entries = positives[:half] + negatives[:half]

    if len(entries) < MAX_ENTRIES_PER_DETECTOR:
        used_ids = {e.id for e in entries}
        remaining = [e for e in pool if e.id not in used_ids]
        entries.extend(remaining[: MAX_ENTRIES_PER_DETECTOR - len(entries)])

    return entries, source_note


def _run_round(
    dataset,
    targets: List[str],
    model: str,
    model_label: str,
    cost_rates: Dict[str, float],
    entry_cache: Dict[str, Tuple[List[GoldenDatasetEntry], List[bool], List[bool], str]],
) -> Dict[str, dict]:
    """Run one round of inverted judge evaluation.

    Returns dict mapping detector name -> metrics dict.
    Populates entry_cache with entries, ground_truths, rule_preds for reuse.
    """
    results = {}
    round_cost = 0.0
    round_calls = 0

    for det_name in targets:
        if det_name not in INVERTED_PROMPTS:
            print(f"  SKIP {det_name}: no inverted prompt defined")
            continue

        # Reuse cached entries and rule predictions from Round 1
        if det_name in entry_cache:
            entries, ground_truths, rule_preds, source_note = entry_cache[det_name]
        else:
            entries, source_note = _get_entries_for_detector(dataset, det_name)
            if not entries:
                print(f"  SKIP {det_name}: no entries with real content")
                continue

            det_type = DetectionType(det_name)
            runner = DETECTOR_RUNNERS.get(det_type)
            ground_truths = []
            rule_preds = []
            for entry in entries:
                ground_truths.append(entry.expected_detected)
                if runner:
                    try:
                        detected, _conf = runner(entry)
                        rule_preds.append(detected)
                    except Exception:
                        rule_preds.append(False)
                else:
                    rule_preds.append(False)
            entry_cache[det_name] = (entries, ground_truths, rule_preds, source_note)

        n_pos = sum(1 for e in entries if e.expected_detected)
        n_neg = len(entries) - n_pos
        print(f"\n{'=' * 78}")
        print(
            f"  {det_name} ({len(entries)} entries: {n_pos}+/{n_neg}-, "
            f"source={source_note})"
        )
        print(f"{'=' * 78}")

        rule_metrics = _compute_f1(rule_preds, ground_truths)
        print(
            f"  Rule-based: F1={rule_metrics['f1']:.3f} "
            f"P={rule_metrics['precision']:.3f} R={rule_metrics['recall']:.3f} "
            f"[TP={rule_metrics['tp']} FP={rule_metrics['fp']} "
            f"FN={rule_metrics['fn']} TN={rule_metrics['tn']}]"
        )

        # Run inverted judge
        inv_preds = []
        det_cost = 0.0
        errors = 0
        entry_details = []

        for i, entry in enumerate(entries):
            try:
                prompt = _format_prompt(det_name, entry)
                detected, cost, raw_answer = _call_inverted_judge(
                    model, prompt, cost_rates
                )
                inv_preds.append(detected)
                det_cost += cost
                round_calls += 1

                last_line = raw_answer.strip().split("\n")[-1][:100]
                entry_details.append(
                    {
                        "entry_id": entry.id,
                        "expected": entry.expected_detected,
                        "rule_pred": rule_preds[i],
                        "inv_pred": detected,
                        "llm_last_line": last_line,
                    }
                )

                if (i + 1) % 10 == 0:
                    print(f"    ... processed {i + 1}/{len(entries)}")

            except Exception as exc:
                errors += 1
                inv_preds.append(False)
                entry_details.append(
                    {
                        "entry_id": entry.id,
                        "expected": entry.expected_detected,
                        "rule_pred": rule_preds[i],
                        "inv_pred": False,
                        "error": str(exc),
                    }
                )
                logger.warning(f"  LLM error on {entry.id}: {exc}")

            # Brief pause every 20 calls to avoid rate limits
            if round_calls % 20 == 0:
                time.sleep(0.3)

        inv_metrics = _compute_f1(inv_preds, ground_truths)
        round_cost += det_cost
        improvement = inv_metrics["f1"] - rule_metrics["f1"]

        print(
            f"  {model_label} Inverted: F1={inv_metrics['f1']:.3f} "
            f"P={inv_metrics['precision']:.3f} R={inv_metrics['recall']:.3f} "
            f"[TP={inv_metrics['tp']} FP={inv_metrics['fp']} "
            f"FN={inv_metrics['fn']} TN={inv_metrics['tn']}]"
        )
        print(
            f"  Delta: {'+' if improvement >= 0 else ''}{improvement:.3f} "
            f"| Cost: ${det_cost:.4f} | Errors: {errors}"
        )

        # Show per-entry mismatches
        mismatches = [
            d
            for d in entry_details
            if d.get("inv_pred") != d.get("expected")
        ]
        if mismatches:
            print(f"  Mismatches ({len(mismatches)}):")
            for m in mismatches[:5]:
                expected_str = "+" if m["expected"] else "-"
                inv_str = "+" if m["inv_pred"] else "-"
                print(
                    f"    {m['entry_id'][:30]}: expected={expected_str} "
                    f"inv={inv_str} | {m.get('llm_last_line', '')[:60]}"
                )
            if len(mismatches) > 5:
                print(f"    ... and {len(mismatches) - 5} more")

        results[det_name] = {
            "n_entries": len(entries),
            "n_positive": n_pos,
            "n_negative": n_neg,
            "rule_f1": rule_metrics["f1"],
            "rule_precision": rule_metrics["precision"],
            "rule_recall": rule_metrics["recall"],
            "rule_tp": rule_metrics["tp"],
            "rule_fp": rule_metrics["fp"],
            "rule_fn": rule_metrics["fn"],
            "rule_tn": rule_metrics["tn"],
            "inv_f1": inv_metrics["f1"],
            "inv_precision": inv_metrics["precision"],
            "inv_recall": inv_metrics["recall"],
            "inv_tp": inv_metrics["tp"],
            "inv_fp": inv_metrics["fp"],
            "inv_fn": inv_metrics["fn"],
            "inv_tn": inv_metrics["tn"],
            "improvement": round(improvement, 3),
            "cost_usd": round(det_cost, 4),
            "errors": errors,
            "entry_details": entry_details,
        }

    print(f"\n  Round cost: ${round_cost:.4f} ({round_calls} calls)")
    return results


def main():
    parser = argparse.ArgumentParser(description="Inverted LLM judge evaluation")
    parser.add_argument(
        "--sonnet-only",
        action="store_true",
        help="Skip Haiku round; load previous results and run only Sonnet round",
    )
    args = parser.parse_args()

    print("=" * 78)
    print("INVERTED Judge Evaluation: 'Is this CORRECT?' (NO = failure detected)")
    print("=" * 78)
    print(
        "\nKey insight: Previous judge asked 'Is this a failure?' -> LLM says NO"
        "\n(conservative bias). Now we ask 'Is this CORRECT?' -> LLM says NO when"
        "\nsomething is wrong, flipping the bias in our favor."
    )

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\nERROR: No ANTHROPIC_API_KEY found.")
        sys.exit(1)
    print(f"\nAPI key: ...{api_key[-8:]}")

    # Load golden dataset
    print("\nLoading golden dataset...")
    dataset = _get_golden_dataset()
    print(f"Total entries: {len(dataset.entries)}")

    # Shared cache for entries/rule_preds between rounds
    entry_cache: Dict[str, Tuple] = {}

    output_path = Path(
        "/Users/tuomonikulainen/mao-testing-research/backend/data/inverted_judge_results.json"
    )

    if args.sonnet_only:
        # Load previous Haiku results
        if not output_path.exists():
            print("\nERROR: No previous results found. Run without --sonnet-only first.")
            sys.exit(1)
        prev = json.loads(output_path.read_text())
        haiku_results = prev.get("round1_results", {})
        print(f"\nLoaded previous Haiku results for {len(haiku_results)} detectors")
    else:
        # -----------------------------------------------------------------------
        # Round 1: Haiku with inverted prompts (all 10 detectors)
        # -----------------------------------------------------------------------
        print("\n" + "=" * 78)
        print("ROUND 1: Haiku with Inverted Prompts (all 10 detectors)")
        print(f"Model: {HAIKU_MODEL}")
        print("=" * 78)

        haiku_results = _run_round(
            dataset, TARGETS, HAIKU_MODEL, "Haiku", HAIKU_COST, entry_cache
        )

        # Decide whether to run Sonnet round
        improved_count = sum(
            1 for r in haiku_results.values() if r["improvement"] > 0
        )
        avg_improvement = (
            sum(r["improvement"] for r in haiku_results.values()) / len(haiku_results)
            if haiku_results
            else 0
        )

        print("\n" + "=" * 78)
        print("ROUND 1 SUMMARY")
        print("=" * 78)
        print(
            f"\n{'Detector':<22} {'Rule F1':>8} {'Haiku-Inv':>10} {'Delta':>8} {'Verdict':>10}"
        )
        print("-" * 62)
        for det_name in TARGETS:
            if det_name not in haiku_results:
                continue
            r = haiku_results[det_name]
            delta = r["improvement"]
            verdict = "BETTER" if delta > 0.02 else ("SAME" if delta > -0.02 else "WORSE")
            print(
                f"  {det_name:<20} {r['rule_f1']:>7.3f} {r['inv_f1']:>10.3f} "
                f"{'+' if delta >= 0 else ''}{delta:>7.3f} {verdict:>10}"
            )

        print(f"\nImproved: {improved_count}/{len(haiku_results)}")
        print(f"Avg delta: {avg_improvement:+.3f}")

    # -----------------------------------------------------------------------
    # Round 2: Sonnet on top 5 hardest (if Round 1 shows promise)
    # -----------------------------------------------------------------------
    if args.sonnet_only:
        run_sonnet = True
    else:
        run_sonnet = improved_count >= 2 or avg_improvement > -0.05
    sonnet_results = {}

    if run_sonnet:
        print("\n" + "=" * 78)
        print("ROUND 2: Sonnet on Top 5 Hardest Detectors")
        print(f"Model: {SONNET_MODEL}")
        print("=" * 78)

        sonnet_results = _run_round(
            dataset,
            SONNET_TARGETS,
            SONNET_MODEL,
            "Sonnet",
            SONNET_COST,
            entry_cache,
        )
    else:
        print(
            f"\nSkipping Sonnet round: only {improved_count} improved, "
            f"avg delta={avg_improvement:+.3f}"
        )

    # -----------------------------------------------------------------------
    # Final comparison table
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("FINAL COMPARISON TABLE")
    print("=" * 78)
    header = (
        f"{'Detector':<22} {'Rule F1':>8} {'Haiku-Inv':>10} "
        f"{'Sonnet-Inv':>11} {'Best':>12}"
    )
    print(f"\n{header}")
    print("-" * 67)

    for det_name in TARGETS:
        rule_f1 = haiku_results.get(det_name, {}).get("rule_f1", 0)
        haiku_f1 = haiku_results.get(det_name, {}).get("inv_f1", 0)
        sonnet_f1 = sonnet_results.get(det_name, {}).get("inv_f1", 0)

        candidates = {"Rule": rule_f1, "Haiku-Inv": haiku_f1}
        if det_name in sonnet_results:
            candidates["Sonnet-Inv"] = sonnet_f1

        best_name = max(candidates, key=candidates.get)
        best_f1 = candidates[best_name]

        sonnet_str = f"{sonnet_f1:.3f}" if det_name in sonnet_results else "   ---"

        print(
            f"  {det_name:<20} {rule_f1:>7.3f} {haiku_f1:>10.3f} "
            f"{sonnet_str:>11} {best_name:>12}"
        )

    # -----------------------------------------------------------------------
    # Save results
    # -----------------------------------------------------------------------
    # Strip entry_details from saved results to keep file manageable
    def _strip_details(results_dict):
        stripped = {}
        for k, v in results_dict.items():
            stripped[k] = {dk: dv for dk, dv in v.items() if dk != "entry_details"}
        return stripped

    output = {
        "run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "approach": "inverted_prompting",
        "insight": "Ask 'Is this CORRECT?' instead of 'Is this a failure?' to flip conservative LLM bias",
        "round1_model": HAIKU_MODEL,
        "round2_model": SONNET_MODEL if sonnet_results else None,
        "round1_results": _strip_details(haiku_results),
        "round2_results": _strip_details(sonnet_results) if sonnet_results else {},
        "summary": [],
    }

    for det_name in TARGETS:
        rule_f1 = haiku_results.get(det_name, {}).get("rule_f1", 0)
        haiku_f1 = haiku_results.get(det_name, {}).get("inv_f1", 0)
        sonnet_f1 = sonnet_results.get(det_name, {}).get("inv_f1", 0)

        candidates = {"rule": rule_f1, "haiku_inverted": haiku_f1}
        if det_name in sonnet_results:
            candidates["sonnet_inverted"] = sonnet_f1
        best_method = max(candidates, key=candidates.get)

        output["summary"].append(
            {
                "detector": det_name,
                "rule_f1": rule_f1,
                "haiku_inv_f1": haiku_f1,
                "sonnet_inv_f1": sonnet_f1 if det_name in sonnet_results else None,
                "best_method": best_method,
                "best_f1": candidates[best_method],
            }
        )

    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to {output_path}")

    # Total cost
    total_cost = sum(r.get("cost_usd", 0) for r in haiku_results.values())
    total_cost += sum(r.get("cost_usd", 0) for r in sonnet_results.values())
    print(f"Total cost: ${total_cost:.4f}")
    print("\nDone.")


if __name__ == "__main__":
    main()
