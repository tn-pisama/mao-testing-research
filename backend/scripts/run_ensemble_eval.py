#!/usr/bin/env python3 -u
"""Three-signal ensemble evaluation for hallucination and grounding detection.

Combines:
  Signal 1: Rule-based detector (free, instant)
  Signal 2: NLI entailment checker (free, ~50ms per sentence)
  Signal 3: Inverted LLM judge via Claude Haiku (ask "Is this CORRECT?")

Tests three ensemble strategies:
  - Majority vote (2/3 agree)
  - Any-positive (any signal flags it)
  - Weighted vote (weighted by historical accuracy)

Usage:
    cd ~/mao-testing-research/backend
    python scripts/run_ensemble_eval.py
"""

import argparse
import gc
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Environment setup (must happen before any app imports)
# ---------------------------------------------------------------------------
os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
sys.path.insert(0, "/Users/tuomonikulainen/mao-testing-research/backend")

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
from app.detection_enterprise.calibrate import _get_golden_dataset
from app.detection_enterprise.detector_adapters import DETECTOR_RUNNERS
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry

# Try to load NLI checker; may fail on some Python/transformers versions
_NLI_AVAILABLE = False
try:
    from app.detection.nli_checker import check_grounding as _check_grounding_fn
    # Test that the model can actually load (tokenizer issue on Python 3.14)
    _check_grounding_fn("test output", ["test source"])
    _NLI_AVAILABLE = True
except Exception as exc:
    logger.warning("NLI model unavailable: %s", exc)
    _check_grounding_fn = None

# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------
from anthropic import Anthropic

client = Anthropic()

HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_COST = {"input": 1 / 1_000_000, "output": 5 / 1_000_000}

MAX_ENTRIES_PER_DETECTOR = 30

# Placeholder phrases that indicate a stub entry
_STUB_MARKERS = [
    "benchmark trace",
    "Agent output for trace",
    "Task from gaia",
    "placeholder",
    "TODO: fill in",
]

# ---------------------------------------------------------------------------
# Inverted LLM judge prompts
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
}

# Ensemble weights from prior experiment results (inverted judge > NLI > rule)
ENSEMBLE_WEIGHTS = {
    "rule": 0.3,
    "nli": 0.4,
    "judge": 0.5,
}


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
                if any(isinstance(v, str) and len(v) > 30 for v in first.values()):
                    has_substance = True
            elif isinstance(first, str) and len(first) > 30:
                has_substance = True
    return has_substance


def _format_value(value: Any) -> str:
    """Format a single value for prompt substitution."""
    if isinstance(value, dict):
        if "content" in value:
            return str(value["content"])[:800]
        return json.dumps(value, indent=2)[:800]
    return str(value)[:800]


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
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def _get_balanced_entries(
    dataset, det_name: str
) -> Tuple[List[GoldenDatasetEntry], str]:
    """Get balanced, real-content entries for a detector (up to MAX_ENTRIES_PER_DETECTOR)."""
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

    pool = real_entries if len(real_entries) >= 10 else all_entries
    source_note = "real" if len(real_entries) >= 10 else f"all ({len(real_entries)} real)"

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


# ---------------------------------------------------------------------------
# Signal 1: Rule-based detector
# ---------------------------------------------------------------------------

def run_rule_signal(det_name: str, entry: GoldenDatasetEntry) -> Tuple[bool, float]:
    """Run the existing rule-based detector on an entry."""
    det_type = DetectionType(det_name)
    runner = DETECTOR_RUNNERS.get(det_type)
    if not runner:
        return False, 0.0
    try:
        detected, confidence = runner(entry)
        return detected, confidence
    except Exception as exc:
        logger.warning("Rule-based error on %s: %s", entry.id, exc)
        return False, 0.0


# ---------------------------------------------------------------------------
# Signal 2: NLI entailment check
# ---------------------------------------------------------------------------

def run_nli_signal(det_name: str, entry: GoldenDatasetEntry) -> Tuple[bool, float]:
    """Run NLI entailment check. Works for both hallucination and grounding."""
    if not _NLI_AVAILABLE:
        return False, 0.0

    # Extract output and sources from entry, handling both field naming conventions
    output = entry.input_data.get("output", entry.input_data.get("agent_output", ""))
    sources = entry.input_data.get("sources", entry.input_data.get("source_documents", []))

    if isinstance(sources, str):
        sources = [sources]

    # Normalize source items to plain strings
    normalized_sources = []
    for s in sources:
        if isinstance(s, str):
            normalized_sources.append(s)
        elif isinstance(s, dict):
            normalized_sources.append(s.get("content", str(s)))
        else:
            normalized_sources.append(str(s))

    if not output or not normalized_sources:
        return False, 0.0

    try:
        nli_det, nli_conf, _ = _check_grounding_fn(output, normalized_sources)
        return nli_det, nli_conf
    except Exception as exc:
        logger.warning("NLI error on %s: %s", entry.id, exc)
        return False, 0.0


# ---------------------------------------------------------------------------
# Signal 3: Inverted LLM judge
# ---------------------------------------------------------------------------

def run_inverted_judge(det_name: str, entry: GoldenDatasetEntry) -> Tuple[bool, float]:
    """Call Claude Haiku with inverted prompt. Returns (detected, cost_usd)."""
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

    # Remove unfilled placeholders
    formatted = re.sub(r"\{[a-z_]+\}", "[not provided]", formatted)

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=500,
        timeout=60.0,
        messages=[{"role": "user", "content": formatted}],
    )
    text = response.content[0].text.strip()
    last_line = text.split("\n")[-1].strip().upper()
    detected = "INCORRECT" in last_line

    cost = (
        response.usage.input_tokens * HAIKU_COST["input"]
        + response.usage.output_tokens * HAIKU_COST["output"]
    )
    return detected, cost


# ---------------------------------------------------------------------------
# Ensemble strategies
# ---------------------------------------------------------------------------

def ensemble_majority(rule: bool, nli: bool, judge: bool) -> bool:
    """Majority vote: 2 out of 3 agree = verdict."""
    return sum([rule, nli, judge]) >= 2


def ensemble_any_positive(rule: bool, nli: bool, judge: bool) -> bool:
    """Any-positive: if ANY signal says failure, flag it."""
    return rule or nli or judge


def ensemble_weighted(rule: bool, nli: bool, judge: bool) -> bool:
    """Weighted vote: weight by each signal's historical accuracy."""
    score = (
        rule * ENSEMBLE_WEIGHTS["rule"]
        + nli * ENSEMBLE_WEIGHTS["nli"]
        + judge * ENSEMBLE_WEIGHTS["judge"]
    )
    return score > 0.5


ENSEMBLE_STRATEGIES = {
    "Majority": ensemble_majority,
    "Any-Pos": ensemble_any_positive,
    "Weighted": ensemble_weighted,
}


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def evaluate_detector(
    dataset, det_name: str, skip_judge: bool = False,
) -> Dict[str, Any]:
    """Run all 3 signals + ensemble strategies on a single detector type."""
    entries, source_note = _get_balanced_entries(dataset, det_name)
    if not entries:
        print(f"  SKIP {det_name}: no entries with real content")
        return {}

    n_pos = sum(1 for e in entries if e.expected_detected)
    n_neg = len(entries) - n_pos
    print(f"\n{'=' * 78}")
    print(f"  {det_name} ({len(entries)} entries: {n_pos}+/{n_neg}-, source={source_note})")
    print(f"{'=' * 78}")

    ground_truths = [e.expected_detected for e in entries]

    # Collect per-signal predictions
    rule_preds = []
    nli_preds = []
    judge_preds = []
    total_cost = 0.0
    judge_errors = 0

    for i, entry in enumerate(entries):
        # Signal 1: Rule-based
        rule_det, _ = run_rule_signal(det_name, entry)
        rule_preds.append(rule_det)

        # Signal 2: NLI
        nli_det, _ = run_nli_signal(det_name, entry)
        nli_preds.append(nli_det)

        # Signal 3: Inverted LLM judge
        if skip_judge:
            judge_preds.append(False)
        else:
            try:
                judge_det, cost = run_inverted_judge(det_name, entry)
                judge_preds.append(judge_det)
                total_cost += cost
            except Exception as exc:
                judge_errors += 1
                judge_preds.append(False)
                logger.warning("Judge error on %s: %s", entry.id, exc)

            # Rate limit: brief pause every 15 calls
            if (i + 1) % 15 == 0:
                time.sleep(0.3)

        if (i + 1) % 10 == 0:
            print(f"    ... processed {i + 1}/{len(entries)}")

    # Compute individual signal metrics
    rule_metrics = _compute_f1(rule_preds, ground_truths)
    nli_metrics = _compute_f1(nli_preds, ground_truths)
    judge_metrics = _compute_f1(judge_preds, ground_truths)

    # Compute ensemble metrics
    ensemble_results = {}
    for strategy_name, strategy_fn in ENSEMBLE_STRATEGIES.items():
        preds = [
            strategy_fn(r, n, j)
            for r, n, j in zip(rule_preds, nli_preds, judge_preds)
        ]
        ensemble_results[strategy_name] = _compute_f1(preds, ground_truths)

    # Print results
    print(f"\n  {det_name} Results:")
    print(f"    Rule:     F1={rule_metrics['f1']:.3f}  P={rule_metrics['precision']:.3f}  R={rule_metrics['recall']:.3f}  [TP={rule_metrics['tp']} FP={rule_metrics['fp']} FN={rule_metrics['fn']} TN={rule_metrics['tn']}]")
    print(f"    NLI:      F1={nli_metrics['f1']:.3f}  P={nli_metrics['precision']:.3f}  R={nli_metrics['recall']:.3f}  [TP={nli_metrics['tp']} FP={nli_metrics['fp']} FN={nli_metrics['fn']} TN={nli_metrics['tn']}]")
    print(f"    Judge:    F1={judge_metrics['f1']:.3f}  P={judge_metrics['precision']:.3f}  R={judge_metrics['recall']:.3f}  [TP={judge_metrics['tp']} FP={judge_metrics['fp']} FN={judge_metrics['fn']} TN={judge_metrics['tn']}]")
    for strategy_name, metrics in ensemble_results.items():
        print(f"    {strategy_name:9s} F1={metrics['f1']:.3f}  P={metrics['precision']:.3f}  R={metrics['recall']:.3f}  [TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} TN={metrics['tn']}]")
    if not skip_judge:
        print(f"    Judge cost: ${total_cost:.4f} ({len(entries)} calls, {judge_errors} errors)")

    # Per-entry detail for debugging
    entry_details = []
    for i, entry in enumerate(entries):
        entry_details.append({
            "entry_id": entry.id,
            "expected": ground_truths[i],
            "rule": rule_preds[i],
            "nli": nli_preds[i],
            "judge": judge_preds[i],
            "majority": ensemble_majority(rule_preds[i], nli_preds[i], judge_preds[i]),
            "any_pos": ensemble_any_positive(rule_preds[i], nli_preds[i], judge_preds[i]),
            "weighted": ensemble_weighted(rule_preds[i], nli_preds[i], judge_preds[i]),
        })

    # Show mismatches for best ensemble
    best_strategy = max(ensemble_results, key=lambda k: ensemble_results[k]["f1"])
    best_key = best_strategy.lower().replace("-", "_")
    if best_key == "any_pos":
        best_key = "any_pos"
    elif best_key == "majority":
        best_key = "majority"
    elif best_key == "weighted":
        best_key = "weighted"

    mismatches = [d for d in entry_details if d.get(best_key) != d["expected"]]
    if mismatches:
        print(f"\n  Mismatches for {best_strategy} ({len(mismatches)}):")
        for m in mismatches[:5]:
            exp = "+" if m["expected"] else "-"
            pred = "+" if m[best_key] else "-"
            signals = f"rule={'+'if m['rule'] else '-'} nli={'+'if m['nli'] else '-'} judge={'+'if m['judge'] else '-'}"
            print(f"    {m['entry_id'][:40]}: expected={exp} pred={pred} ({signals})")
        if len(mismatches) > 5:
            print(f"    ... and {len(mismatches) - 5} more")

    return {
        "detector": det_name,
        "n_entries": len(entries),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "source": source_note,
        "rule": rule_metrics,
        "nli": nli_metrics,
        "judge": judge_metrics,
        "ensembles": ensemble_results,
        "best_ensemble": best_strategy,
        "best_ensemble_f1": ensemble_results[best_strategy]["f1"],
        "cost_usd": round(total_cost, 4),
        "judge_errors": judge_errors,
        "entry_details": entry_details,
    }


def main():
    parser = argparse.ArgumentParser(description="Three-signal ensemble evaluation")
    parser.add_argument(
        "--skip-judge", action="store_true",
        help="Skip LLM judge calls (test rule + NLI only)",
    )
    args = parser.parse_args()

    print("=" * 78)
    print("THREE-SIGNAL ENSEMBLE EVALUATION")
    print("  Signal 1: Rule-based detector (free, instant)")
    print("  Signal 2: NLI entailment checker (free, ~50ms)")
    print("  Signal 3: Inverted LLM judge - Claude Haiku ($0.002/call)")
    print("=" * 78)

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.skip_judge:
        print("\nERROR: No ANTHROPIC_API_KEY found. Use --skip-judge to test without LLM.")
        sys.exit(1)
    if api_key:
        print(f"\nAPI key: ...{api_key[-8:]}")

    if _NLI_AVAILABLE:
        print("\nNLI model: loaded (DeBERTa-v3)")
    else:
        print("\nNLI model: UNAVAILABLE (transformers/tokenizer error)")
        print("  Ensemble will use rule + judge only (NLI signal = False for all)")

    print("\nEnsemble strategies:")
    print(f"  Majority: 2/3 signals agree")
    print(f"  Any-Pos:  any signal flags = flag")
    print(f"  Weighted: rule={ENSEMBLE_WEIGHTS['rule']}, nli={ENSEMBLE_WEIGHTS['nli']}, judge={ENSEMBLE_WEIGHTS['judge']} (threshold 0.5)")

    # Load golden dataset
    print("\nLoading golden dataset...")
    dataset = _get_golden_dataset()
    print(f"Total entries: {len(dataset.entries)}")

    # Run evaluation for both detectors
    detectors = ["hallucination", "grounding"]
    all_results = {}

    for det_name in detectors:
        result = evaluate_detector(dataset, det_name, skip_judge=args.skip_judge)
        if result:
            all_results[det_name] = result
        gc.collect()

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)

    for det_name in detectors:
        if det_name not in all_results:
            continue
        r = all_results[det_name]
        print(f"\n{det_name}:")
        print(f"  Rule:     F1={r['rule']['f1']:.3f}")
        print(f"  NLI:      F1={r['nli']['f1']:.3f}")
        print(f"  Judge:    F1={r['judge']['f1']:.3f}")
        for strategy_name in ENSEMBLE_STRATEGIES:
            f1 = r["ensembles"][strategy_name]["f1"]
            marker = " <-- BEST" if strategy_name == r["best_ensemble"] else ""
            print(f"  {strategy_name:9s} F1={f1:.3f}{marker}")

    # Find overall best approach per detector
    print("\n" + "-" * 78)
    print(f"{'Detector':<18} {'Rule':>7} {'NLI':>7} {'Judge':>7} {'Majority':>9} {'Any-Pos':>9} {'Weighted':>9} {'Best':>12}")
    print("-" * 78)

    total_cost = 0.0
    for det_name in detectors:
        if det_name not in all_results:
            continue
        r = all_results[det_name]
        total_cost += r["cost_usd"]

        all_f1s = {
            "Rule": r["rule"]["f1"],
            "NLI": r["nli"]["f1"],
            "Judge": r["judge"]["f1"],
        }
        for sname in ENSEMBLE_STRATEGIES:
            all_f1s[sname] = r["ensembles"][sname]["f1"]

        best_name = max(all_f1s, key=all_f1s.get)
        print(
            f"  {det_name:<16} "
            f"{r['rule']['f1']:>6.3f} "
            f"{r['nli']['f1']:>6.3f} "
            f"{r['judge']['f1']:>6.3f} "
            f"{r['ensembles']['Majority']['f1']:>8.3f} "
            f"{r['ensembles']['Any-Pos']['f1']:>8.3f} "
            f"{r['ensembles']['Weighted']['f1']:>8.3f} "
            f"{best_name:>12}"
        )

    print(f"\nTotal judge cost: ${total_cost:.4f}")

    # ---------------------------------------------------------------------------
    # Save results
    # ---------------------------------------------------------------------------
    output_path = Path("/Users/tuomonikulainen/mao-testing-research/backend/data/ensemble_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Strip entry_details for the saved file (keep it manageable)
    save_results = {}
    for det_name, r in all_results.items():
        save_results[det_name] = {
            k: v for k, v in r.items() if k != "entry_details"
        }

    output = {
        "run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "approach": "three_signal_ensemble",
        "signals": {
            "rule": "Existing rule-based detector (DETECTOR_RUNNERS)",
            "nli": "DeBERTa-v3 NLI entailment (check_grounding)",
            "judge": f"Inverted LLM judge ({HAIKU_MODEL})",
        },
        "ensemble_weights": ENSEMBLE_WEIGHTS,
        "results": save_results,
        "summary": [],
    }

    for det_name in detectors:
        if det_name not in all_results:
            continue
        r = all_results[det_name]

        all_f1s = {
            "rule": r["rule"]["f1"],
            "nli": r["nli"]["f1"],
            "judge": r["judge"]["f1"],
        }
        for sname in ENSEMBLE_STRATEGIES:
            all_f1s[sname.lower().replace("-", "_")] = r["ensembles"][sname]["f1"]

        best_method = max(all_f1s, key=all_f1s.get)
        output["summary"].append({
            "detector": det_name,
            "rule_f1": r["rule"]["f1"],
            "nli_f1": r["nli"]["f1"],
            "judge_f1": r["judge"]["f1"],
            "majority_f1": r["ensembles"]["Majority"]["f1"],
            "any_pos_f1": r["ensembles"]["Any-Pos"]["f1"],
            "weighted_f1": r["ensembles"]["Weighted"]["f1"],
            "best_method": best_method,
            "best_f1": all_f1s[best_method],
            "cost_usd": r["cost_usd"],
        })

    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to {output_path}")
    print("Done.")


if __name__ == "__main__":
    main()
