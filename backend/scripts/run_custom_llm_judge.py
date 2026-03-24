#!/usr/bin/env python3 -u
"""Custom per-detector LLM judge evaluation.

The previous MASTLLMJudge approach failed because it used generic MAST failure
mode prompts (F1-F14) that expect full agent traces, but our golden entries are
specific field pairs like {output, sources} or {task, output}. The judge said
NO to everything because the prompts didn't match the data.

This script uses the Anthropic API directly with custom prompts designed for
the EXACT input format each detector uses.

Usage:
    cd ~/mao-testing-research/backend
    python scripts/run_custom_llm_judge.py
"""

import os
import sys
import json
import time
import gc
from typing import Any
import logging

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
MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Custom per-detector prompts
# ---------------------------------------------------------------------------
DETECTOR_PROMPTS = {
    "hallucination": """You are evaluating whether an AI agent's output contains hallucinations (fabricated claims not supported by the provided sources).

Sources provided to the agent:
{sources}

Agent's output:
{output}

Does the output contain any claims, facts, citations, or details that are NOT supported by or directly contradicted by the provided sources?

Answer YES if hallucinated content is present, NO if the output is faithful to the sources.
Think step by step, then answer YES or NO on the final line.""",

    "grounding": """You are evaluating whether an AI agent's output is properly grounded in source documents.

Source documents:
{source_documents}

Agent's output:
{agent_output}

Is the agent's output well-grounded in the source documents? Are all factual claims supported by the sources?

Answer YES if there are ungrounded claims (detection should fire), NO if properly grounded.
Think step by step, then answer YES or NO on the final line.""",

    "specification": """You are evaluating whether a task specification matches the user's original intent.

User's intent:
{user_intent}

Task specification:
{task_specification}

Does the specification meaningfully differ from what the user asked for? Look for scope drift, missing requirements, or added complexity not requested.

Answer YES if there's a mismatch (detection should fire), NO if they match.
Think step by step, then answer YES or NO on the final line.""",

    "derailment": """You are evaluating whether an AI agent stayed on task.

Original task:
{task}

Agent's output:
{output}

Did the agent deviate from the assigned task without justification? Note: exploring related topics briefly before converging is normal, not derailment.

Answer YES if the agent went off-task, NO if it addressed the task.
Think step by step, then answer YES or NO on the final line.""",

    "completion": """You are evaluating whether an AI agent correctly assessed task completion.

Task:
{task}

Subtasks:
{subtasks}

Success criteria:
{success_criteria}

Agent's output:
{agent_output}

Did the agent claim completion while missing subtasks or criteria? Or did it accurately report its progress?

Answer YES if there's a completion misjudgment, NO if the completion assessment is accurate.
Think step by step, then answer YES or NO on the final line.""",

    "context": """You are evaluating whether an AI agent used the provided context.

Context provided:
{context}

Agent's output:
{output}

Did the agent ignore important information from the context? Or did it properly incorporate the context into its response?

Answer YES if context was neglected, NO if it was properly used.
Think step by step, then answer YES or NO on the final line.""",

    "communication": """You are evaluating inter-agent communication quality.

Sender's message:
{sender_message}

Receiver's response:
{receiver_response}

Did the receiver adequately address the sender's message? Or was there a communication breakdown where the response doesn't relate to the message?

Answer YES if there's a breakdown, NO if communication was adequate.
Think step by step, then answer YES or NO on the final line.""",

    "withholding": """You are evaluating whether an agent withheld important information.

Agent's internal state/findings:
{internal_state}

What the agent communicated:
{agent_output}

Did the agent withhold critical information (errors, security issues, blockers) that was in its internal state but not communicated? Note: summarizing or paraphrasing is OK, only flag deliberate omission of critical info.

Answer YES if critical info was withheld, NO if the agent communicated appropriately.
Think step by step, then answer YES or NO on the final line.""",

    # Note: convergence entries may have 'metric_name' or 'window_size' depending on source.
    # The _format_prompt function handles missing placeholders gracefully (leaves them as-is),
    # so we include both and clean up in _format_prompt.
    "convergence": """You are evaluating whether optimization metrics are converging properly.

Direction: {direction} (lower is better if "minimize", higher is better if "maximize")

Metrics over time (list of step/value pairs):
{metrics}

Are the metrics showing healthy convergence (steady improvement in the specified direction)? Or are they plateauing, diverging, thrashing, or regressing?

Answer YES if there's a convergence failure (plateau, divergence, thrashing, or regression), NO if metrics are converging normally.
Think step by step, then answer YES or NO on the final line.""",

    "retrieval_quality": """You are evaluating retrieval quality in a RAG system.

Query:
{query}

Retrieved documents:
{retrieved_documents}

Agent's output based on retrieval:
{agent_output}

Were the retrieved documents relevant to the query? Did retrieval quality affect the output?

Answer YES if retrieval was poor/irrelevant, NO if retrieval was adequate.
Think step by step, then answer YES or NO on the final line.""",
}

# ---------------------------------------------------------------------------
# Target detectors (the 10 with custom prompts)
# ---------------------------------------------------------------------------
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

MAX_ENTRIES_PER_DETECTOR = 30

# Placeholder phrases that indicate a stub entry with no real content
_STUB_MARKERS = [
    "benchmark trace",
    "Agent output for trace",
    "Task from gaia",
    "placeholder",
    "TODO: fill in",
]


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
                # Numeric lists (e.g. convergence metrics) are real content
                has_substance = True
                continue
        elif isinstance(value, dict):
            text = " ".join(str(v) for v in value.values())

        if any(marker.lower() in text.lower() for marker in _STUB_MARKERS):
            return False
        # At least one field should have substantive text (>30 chars)
        if isinstance(value, str) and len(value) > 30:
            has_substance = True
        elif isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                # Dicts with numeric values (like convergence metrics) are real
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
        # If dict has a 'content' key, use that directly
        if "content" in value:
            return str(value["content"])[:800]
        return json.dumps(value, indent=2)[:800]
    return str(value)[:800]


def _format_prompt(det_name: str, entry: GoldenDatasetEntry) -> str:
    """Format a custom prompt by substituting fields from entry.input_data."""
    template = DETECTOR_PROMPTS[det_name]
    formatted = template
    for key, value in entry.input_data.items():
        placeholder = "{" + key + "}"
        if placeholder not in formatted:
            continue
        if isinstance(value, list):
            # Format list items intelligently
            parts = []
            for i, item in enumerate(value[:10]):
                parts.append(f"[{i+1}] {_format_value(item)}")
            value_str = "\n".join(parts)
        elif isinstance(value, dict):
            value_str = _format_value(value)
        else:
            value_str = str(value)[:1000]
        formatted = formatted.replace(placeholder, value_str)
    return formatted


def _call_llm(prompt: str) -> tuple[bool, str]:
    """Call Claude Haiku with a prompt, return (detected, raw_answer)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = response.content[0].text.strip()
    # Parse YES/NO from last line
    last_line = answer.strip().split("\n")[-1].strip().upper()
    detected = last_line.startswith("YES")
    return detected, answer


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
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "f1": round(f1, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def main():
    print("=" * 78)
    print("Custom Per-Detector LLM Judge Evaluation")
    print("=" * 78)
    print(f"Model: {MODEL}")
    print(f"Max entries per detector: {MAX_ENTRIES_PER_DETECTOR}")

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\nERROR: No ANTHROPIC_API_KEY found.")
        sys.exit(1)
    print(f"API key: ...{api_key[-8:]}")

    # Load golden dataset
    print("\nLoading golden dataset...")
    dataset = _get_golden_dataset()
    print(f"Total entries: {len(dataset.entries)}")

    # Prefer real-sourced entries
    real_sources = {
        "real", "structural", "mast_benchmark", "swe_bench",
        "real_trace", "n8n_production", "production", "external",
    }

    results = []
    all_entry_results = []
    total_llm_calls = 0

    for det_name in TARGETS:
        try:
            det_type = DetectionType(det_name)
        except ValueError:
            print(f"\n  SKIP {det_name}: not in DetectionType enum")
            continue

        if det_name not in DETECTOR_PROMPTS:
            print(f"\n  SKIP {det_name}: no custom prompt defined")
            continue

        runner = DETECTOR_RUNNERS.get(det_type)

        # Get entries -- filter out stubs with placeholder content
        all_entries = dataset.get_entries_by_type(det_type)
        all_entries = [e for e in all_entries if _has_real_content(e)]
        if not all_entries:
            print(f"\n  SKIP {det_name}: no golden entries with real content")
            continue

        # Prefer real-sourced entries (but only those with actual content)
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

        # If the pool is heavily imbalanced, supplement from the full set
        if len(negatives) < half // 2:
            extra_neg = [e for e in all_entries if not e.expected_detected and e not in negatives]
            negatives.extend(extra_neg)
        if len(positives) < half // 2:
            extra_pos = [e for e in all_entries if e.expected_detected and e not in positives]
            positives.extend(extra_pos)

        entries = positives[:half] + negatives[:half]
        # If one side is short, fill from the other
        if len(entries) < MAX_ENTRIES_PER_DETECTOR:
            used_ids = {e.id for e in entries}
            remaining = [e for e in pool if e.id not in used_ids]
            entries.extend(remaining[:MAX_ENTRIES_PER_DETECTOR - len(entries)])

        n_pos = sum(1 for e in entries if e.expected_detected)
        n_neg = len(entries) - n_pos
        print(f"\n{'=' * 78}")
        print(f"  {det_name} ({len(entries)} entries: {n_pos}+/{n_neg}-, source={source_note})")
        print(f"{'=' * 78}")

        # Run rule-based detector
        rule_preds = []
        ground_truths = []
        for entry in entries:
            ground_truths.append(entry.expected_detected)
            if runner:
                try:
                    detected, confidence = runner(entry)
                    rule_preds.append(detected)
                except Exception:
                    rule_preds.append(False)
            else:
                rule_preds.append(False)

        rule_metrics = _compute_f1(rule_preds, ground_truths)
        print(f"  Rule-based: F1={rule_metrics['f1']:.3f} P={rule_metrics['precision']:.3f} "
              f"R={rule_metrics['recall']:.3f} "
              f"[TP={rule_metrics['tp']} FP={rule_metrics['fp']} "
              f"FN={rule_metrics['fn']} TN={rule_metrics['tn']}]")

        # Run custom LLM judge
        llm_preds = []
        errors = 0
        det_entry_results = []

        for i, entry in enumerate(entries):
            try:
                prompt = _format_prompt(det_name, entry)
                detected, raw_answer = _call_llm(prompt)
                llm_preds.append(detected)
                total_llm_calls += 1

                det_entry_results.append({
                    "entry_id": entry.id,
                    "expected": entry.expected_detected,
                    "rule_pred": rule_preds[i],
                    "llm_pred": detected,
                    "llm_answer_last_line": raw_answer.strip().split("\n")[-1][:100],
                })

                if (i + 1) % 10 == 0:
                    print(f"    ... processed {i + 1}/{len(entries)}")

            except Exception as exc:
                errors += 1
                llm_preds.append(False)
                det_entry_results.append({
                    "entry_id": entry.id,
                    "expected": entry.expected_detected,
                    "rule_pred": rule_preds[i],
                    "llm_pred": False,
                    "error": str(exc),
                })
                logger.warning(f"  LLM error on {entry.id}: {exc}")

            # Brief pause every 20 calls
            if total_llm_calls % 20 == 0:
                time.sleep(0.3)

        llm_metrics = _compute_f1(llm_preds, ground_truths)
        print(f"  LLM judge:  F1={llm_metrics['f1']:.3f} P={llm_metrics['precision']:.3f} "
              f"R={llm_metrics['recall']:.3f} "
              f"[TP={llm_metrics['tp']} FP={llm_metrics['fp']} "
              f"FN={llm_metrics['fn']} TN={llm_metrics['tn']}]")
        if errors:
            print(f"  LLM errors: {errors}")

        # Combined: use LLM when rule-based is uncertain (disagree = escalate)
        combined_preds = []
        escalated = 0
        for i in range(len(entries)):
            if rule_preds[i] != llm_preds[i]:
                # Disagreement: use LLM judgment (it has the custom prompt)
                combined_preds.append(llm_preds[i])
                escalated += 1
            else:
                combined_preds.append(rule_preds[i])

        combo_metrics = _compute_f1(combined_preds, ground_truths)
        print(f"  Combined:   F1={combo_metrics['f1']:.3f} P={combo_metrics['precision']:.3f} "
              f"R={combo_metrics['recall']:.3f} "
              f"[TP={combo_metrics['tp']} FP={combo_metrics['fp']} "
              f"FN={combo_metrics['fn']} TN={combo_metrics['tn']}] "
              f"(escalated={escalated})")

        llm_improvement = llm_metrics["f1"] - rule_metrics["f1"]
        combo_improvement = combo_metrics["f1"] - rule_metrics["f1"]
        print(f"  LLM vs Rule: {llm_improvement:+.3f} | Combined vs Rule: {combo_improvement:+.3f}")

        results.append({
            "detector": det_name,
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
            "llm_f1": llm_metrics["f1"],
            "llm_precision": llm_metrics["precision"],
            "llm_recall": llm_metrics["recall"],
            "llm_tp": llm_metrics["tp"],
            "llm_fp": llm_metrics["fp"],
            "llm_fn": llm_metrics["fn"],
            "llm_tn": llm_metrics["tn"],
            "combo_f1": combo_metrics["f1"],
            "combo_precision": combo_metrics["precision"],
            "combo_recall": combo_metrics["recall"],
            "llm_improvement": llm_improvement,
            "combo_improvement": combo_improvement,
            "escalated": escalated,
            "errors": errors,
        })

        all_entry_results.extend(det_entry_results)
        gc.collect()

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SUMMARY: Rule-Based vs Custom LLM Judge vs Combined")
    print("=" * 78)
    print(f"{'Detector':<22} {'N':>4} {'Rule F1':>8} {'LLM F1':>8} {'Combo F1':>9} {'LLM vs Rule':>12}")
    print("-" * 78)

    llm_wins = []
    for r in sorted(results, key=lambda x: x["llm_improvement"], reverse=True):
        marker = ""
        if r["llm_improvement"] > 0.05:
            marker = " **"
            llm_wins.append(r["detector"])
        elif r["llm_improvement"] > 0:
            marker = " +"
        print(f"  {r['detector']:<20} {r['n_entries']:>4} {r['rule_f1']:>7.3f} "
              f"{r['llm_f1']:>8.3f} {r['combo_f1']:>9.3f} {r['llm_improvement']:>+11.3f}{marker}")

    print("-" * 78)
    print(f"  Total LLM calls: {total_llm_calls}")
    print(f"  ** = LLM F1 > Rule F1 by 5%+")
    print(f"  +  = LLM F1 > Rule F1 by 0-5%")

    if llm_wins:
        print(f"\n  LLM judge WINS on: {', '.join(llm_wins)}")
        print("  These detectors should integrate custom LLM prompts into tiered detection.")

    # ---------------------------------------------------------------------------
    # Save results
    # ---------------------------------------------------------------------------
    output_path = Path("/Users/tuomonikulainen/mao-testing-research/backend/data/custom_judge_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": MODEL,
            "total_llm_calls": total_llm_calls,
            "summary": results,
            "entry_details": all_entry_results,
        }, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
