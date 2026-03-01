#!/usr/bin/env python3
"""
Phase 4 Final Evaluation Runner
================================

Runs the complete evaluation pipeline on the MAST held-out test set (373 traces)
across all detection tiers:

    Tier 0: Pattern-only (keyword fallback, no embeddings)
    Tier 1: Pattern + Embeddings (semantic analysis via bge-m3)
    Tier 2: Hybrid (Pattern + Embeddings + selective LLM verification)
    Tier 3: Full LLM (Claude Opus 4.5 for all 14 failure modes)

Usage:
    # Run available tiers automatically (skips unavailable ones)
    python benchmarks/evaluation/run_phase4_eval.py

    # Force specific tier
    python benchmarks/evaluation/run_phase4_eval.py --tier 0
    python benchmarks/evaluation/run_phase4_eval.py --tier 2

    # Run on dev set instead of test set
    python benchmarks/evaluation/run_phase4_eval.py --dev-set

Prerequisites:
    Tier 0: No external dependencies (always available)
    Tier 1: sentence-transformers + BAAI/bge-m3 model download
    Tier 2: Tier 1 + ANTHROPIC_API_KEY env var
    Tier 3: Tier 2 + DATABASE_URL with populated MAST embeddings

Environment Variables:
    JWT_SECRET       - Required (any 32+ char random string)
    DATABASE_URL     - PostgreSQL URL (for Tier 3)
    ANTHROPIC_API_KEY - Anthropic API key (for Tier 2+)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add paths for imports
_ROOT = Path(__file__).parent.parent.parent
_BACKEND_PATH = str(_ROOT / "backend")
_BENCHMARKS_PATH = str(_ROOT / "benchmarks")
sys.path.insert(0, _BACKEND_PATH)
sys.path.insert(0, _BENCHMARKS_PATH)


def check_tier_availability() -> dict:
    """Check which evaluation tiers are available in the current environment."""
    tiers = {0: True, 1: False, 2: False, 3: False}

    # Tier 1: Check embedding model availability
    try:
        from app.core.embeddings import EmbeddingService
        EmbeddingService.preload()
        tiers[1] = True
    except Exception:
        pass

    # Tier 2: Check LLM API availability
    if tiers[1] and os.environ.get("ANTHROPIC_API_KEY"):
        tiers[2] = True

    # Tier 3: Check database with MAST embeddings
    if tiers[2] and os.environ.get("DATABASE_URL"):
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.orm import sessionmaker
            db_url = os.environ["DATABASE_URL"]
            if "+asyncpg" in db_url:
                db_url = db_url.replace("+asyncpg", "")
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
            result = session.execute(text("SELECT COUNT(*) FROM mast_trace_embeddings"))
            count = result.scalar()
            if count and count > 0:
                tiers[3] = True
            session.close()
        except Exception:
            pass

    return tiers


def run_evaluation(tier: int, data_file: Path, limit: int | None = None) -> dict:
    """Run evaluation at the specified tier."""
    from benchmarks.evaluation.test_mast_conversation import (
        evaluate_mast_dataset,
        save_results,
    )

    use_hybrid = tier >= 2
    use_full_llm = tier >= 3

    result = evaluate_mast_dataset(
        data_file=data_file,
        limit=limit,
        use_hybrid=use_hybrid and not use_full_llm,
        llm_enabled=use_hybrid,
        use_full_llm=use_full_llm,
    )

    # Save results with tier label
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_label = "test" if "test" in str(data_file) else "dev"
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"phase4_tier{tier}_{dataset_label}_{timestamp}.json"

    data = {
        "evaluation": "Phase 4 Final",
        "tier": tier,
        "tier_description": {
            0: "Pattern-only (keyword fallback)",
            1: "Pattern + Embeddings (semantic)",
            2: "Hybrid (Pattern + Embeddings + LLM)",
            3: "Full LLM (Claude Opus 4.5 + RAG)",
        }[tier],
        "dataset": str(data_file),
        "dataset_label": dataset_label,
        "timestamp": result.timestamp,
        "total_traces": result.total_traces,
        "parsed_traces": result.parsed_traces,
        "extraction_rate": result.extraction_rate,
        "avg_turns_per_trace": result.avg_turns_per_trace,
        "overall_f1": result.overall_f1,
        "overall_accuracy": result.overall_accuracy,
        "framework_breakdown": result.framework_breakdown,
        "metrics_by_mode": {
            mode: {
                "precision": m.precision,
                "recall": m.recall,
                "f1": m.f1,
                "fpr": m.fpr,
                "true_positives": m.true_positives,
                "false_positives": m.false_positives,
                "true_negatives": m.true_negatives,
                "false_negatives": m.false_negatives,
                "total_samples": m.total_samples,
            }
            for mode, m in result.metrics_by_mode.items()
        },
        "errors": result.errors,
    }

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nResults saved to: {output_file}")
    return data


def print_comparison(results: list[dict]) -> None:
    """Print a comparison table across tiers."""
    if not results:
        return

    mode_names = {
        'F1': 'Spec Mismatch', 'F2': 'Decomposition', 'F3': 'Resource',
        'F4': 'Tool Provision', 'F5': 'Workflow', 'F6': 'Derailment',
        'F7': 'Context', 'F8': 'Withholding', 'F9': 'Usurpation',
        'F10': 'Communication', 'F11': 'Coordination', 'F12': 'Output Val',
        'F13': 'Quality Gate', 'F14': 'Completion',
    }

    print("\n" + "=" * 90)
    print("PHASE 4 EVALUATION — TIER COMPARISON")
    print("=" * 90)

    # Header
    header = f"{'Mode':<6} {'Name':<16}"
    for r in results:
        header += f" {'T' + str(r['tier']) + ' F1':>8}"
    print(header)
    print("-" * 90)

    # All modes across all results
    all_modes = sorted(set(
        mode for r in results for mode in r["metrics_by_mode"]
    ))

    for mode in all_modes:
        name = mode_names.get(mode, "Unknown")[:16]
        row = f"{mode:<6} {name:<16}"
        for r in results:
            m = r["metrics_by_mode"].get(mode)
            f1 = m["f1"] * 100 if m else 0
            row += f" {f1:>7.1f}%"
        print(row)

    print("-" * 90)
    row = f"{'OVERALL':<23}"
    for r in results:
        row += f" {r['overall_f1'] * 100:>7.1f}%"
    print(row)
    print("=" * 90)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 4 Final Evaluation Runner")
    parser.add_argument("--tier", type=int, choices=[0, 1, 2, 3], help="Force specific tier")
    parser.add_argument("--dev-set", action="store_true", help="Use dev set instead of test set")
    parser.add_argument("--sample", "-n", type=int, help="Limit number of traces")
    parser.add_argument("--all-tiers", action="store_true", help="Run all available tiers")
    args = parser.parse_args()

    # Select dataset
    if args.dev_set:
        data_file = _ROOT / "data" / "mast_dev_869.json"
    else:
        data_file = _ROOT / "data" / "mast_test_373.json"

    if not data_file.exists():
        print(f"Dataset not found: {data_file}")
        return 1

    print(f"Dataset: {data_file}")
    print(f"File size: {data_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Check tier availability
    available = check_tier_availability()
    print("\nTier Availability:")
    tier_labels = {
        0: "Pattern-only (keyword fallback)",
        1: "Pattern + Embeddings (semantic)",
        2: "Hybrid (Pattern + LLM verification)",
        3: "Full LLM (Claude Opus 4.5 + RAG few-shot)",
    }
    for tier, avail in available.items():
        status = "AVAILABLE" if avail else "UNAVAILABLE"
        print(f"  Tier {tier}: {tier_labels[tier]} — {status}")

    # Determine which tiers to run
    if args.tier is not None:
        tiers_to_run = [args.tier]
        if not available[args.tier]:
            print(f"\nWarning: Tier {args.tier} is not available. Running anyway (will use fallbacks).")
    elif args.all_tiers:
        tiers_to_run = [t for t, a in available.items() if a]
    else:
        # Run the highest available tier
        tiers_to_run = [max(t for t, a in available.items() if a)]

    print(f"\nRunning tiers: {tiers_to_run}")

    # Run evaluations
    results = []
    for tier in tiers_to_run:
        print(f"\n{'='*60}")
        print(f"TIER {tier}: {tier_labels[tier]}")
        print(f"{'='*60}")
        result = run_evaluation(tier, data_file, args.sample)
        results.append(result)

    # Print comparison if multiple tiers
    if len(results) > 1:
        print_comparison(results)

    # Print summary
    best = max(results, key=lambda r: r["overall_f1"])
    print(f"\nBest F1: {best['overall_f1'] * 100:.1f}% (Tier {best['tier']})")

    target = 0.70
    if best["overall_f1"] >= target:
        print(f"TARGET ACHIEVED: {best['overall_f1']*100:.1f}% >= {target*100:.0f}%")
        return 0
    else:
        gap = target - best["overall_f1"]
        print(f"Gap to target: {gap*100:.1f}% ({best['overall_f1']*100:.1f}% < {target*100:.0f}%)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
