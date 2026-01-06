"""Realistic evaluation pipeline.

1. Generate semantic traces (LLM-generated, no artificial markers)
2. Generate adversarial traces (edge cases, deceptive scenarios)
3. Evaluate with semantic detector (LLM-based analysis)
4. Compare with pattern-based detector (current approach)
"""

import asyncio
import json
import os
from pathlib import Path
from collections import defaultdict

from src.semantic_trace_generator import SemanticTraceGenerator
from src.semantic_detector import SemanticDetector
from src.adversarial_generator import AdversarialGenerator


async def run_full_evaluation(
    api_key: str,
    traces_per_mode: int = 5,
    failure_modes: list[str] = None,
):
    """Run complete realistic evaluation."""

    if failure_modes is None:
        failure_modes = ["F1", "F6", "F14", "F7", "F8"]  # Key modes

    output_dir = Path("traces/realistic_eval")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("REALISTIC EVALUATION PIPELINE")
    print("=" * 70)

    # Step 1: Generate semantic traces
    print("\n[1/4] Generating semantic traces...")
    semantic_gen = SemanticTraceGenerator(api_key=api_key, output_dir=str(output_dir))
    await semantic_gen.generate_and_save(
        failure_modes=failure_modes,
        traces_per_mode=traces_per_mode,
    )

    # Step 2: Generate adversarial traces
    print("\n[2/4] Generating adversarial traces...")
    adversarial_gen = AdversarialGenerator(api_key=api_key, output_dir=str(output_dir))
    await adversarial_gen.generate_and_save(failure_modes=failure_modes)

    # Step 3: Evaluate with semantic detector
    print("\n[3/4] Evaluating with semantic detector...")
    detector = SemanticDetector(api_key=api_key)

    # Load semantic traces
    semantic_traces = []
    semantic_file = output_dir / "langchain_semantic_traces.jsonl"
    if semantic_file.exists():
        with open(semantic_file) as f:
            for line in f:
                if line.strip():
                    semantic_traces.append(json.loads(line))

    # Load adversarial traces
    adversarial_traces = []
    adversarial_file = output_dir / "adversarial_traces.jsonl"
    if adversarial_file.exists():
        with open(adversarial_file) as f:
            for line in f:
                if line.strip():
                    adversarial_traces.append(json.loads(line))

    # Evaluate semantic traces
    print("\n  Evaluating semantic traces...")
    semantic_results = {}
    for mode in failure_modes:
        mode_traces = [t for t in semantic_traces if t["failure_mode"] == mode]
        if mode_traces:
            result = await detector.evaluate_traces(mode_traces, mode)
            semantic_results[mode] = result
            print(f"    {mode}: P={result['precision']*100:.0f}% R={result['recall']*100:.0f}% F1={result['f1']*100:.0f}%")

    # Evaluate adversarial traces
    print("\n  Evaluating adversarial traces...")
    adversarial_results = {"by_type": {}, "by_difficulty": {}, "details": []}

    for trace in adversarial_traces:
        mode = trace["failure_mode"]
        result = await detector.analyze_trace(trace, mode)

        expected_failure = trace["is_failure"]
        detected_failure = result.get("is_failure", False)
        correct = (expected_failure == detected_failure)

        adversarial_results["details"].append({
            "trace_id": trace["trace_id"],
            "mode": mode,
            "scenario_type": trace["scenario_type"],
            "difficulty": trace["difficulty"],
            "expected_failure": expected_failure,
            "detected_failure": detected_failure,
            "correct": correct,
            "confidence": result.get("confidence", 0),
            "reason": result.get("reason", ""),
        })

        # Aggregate by type
        stype = trace["scenario_type"]
        if stype not in adversarial_results["by_type"]:
            adversarial_results["by_type"][stype] = {"total": 0, "correct": 0}
        adversarial_results["by_type"][stype]["total"] += 1
        if correct:
            adversarial_results["by_type"][stype]["correct"] += 1

        # Aggregate by difficulty
        diff = trace["difficulty"]
        if diff not in adversarial_results["by_difficulty"]:
            adversarial_results["by_difficulty"][diff] = {"total": 0, "correct": 0}
        adversarial_results["by_difficulty"][diff]["total"] += 1
        if correct:
            adversarial_results["by_difficulty"][diff]["correct"] += 1

    # Step 4: Print results
    print("\n[4/4] Results Summary")
    print("=" * 70)

    print("\nSEMANTIC TRACES (LLM-generated, no markers):")
    print("-" * 50)
    print(f"{'Mode':<6} {'Precision':>10} {'Recall':>10} {'F1':>10} {'FPR':>10}")
    print("-" * 50)

    total_tp, total_fp, total_tn, total_fn = 0, 0, 0, 0
    for mode, result in sorted(semantic_results.items()):
        print(f"{mode:<6} {result['precision']*100:>9.1f}% {result['recall']*100:>9.1f}% {result['f1']*100:>9.1f}% {result['fpr']*100:>9.1f}%")
        total_tp += result["true_positives"]
        total_fp += result["false_positives"]
        total_tn += result["true_negatives"]
        total_fn += result["false_negatives"]

    if total_tp + total_fp + total_tn + total_fn > 0:
        overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0
        overall_fpr = total_fp / (total_fp + total_tn) if (total_fp + total_tn) > 0 else 0

        print("-" * 50)
        print(f"{'TOTAL':<6} {overall_precision*100:>9.1f}% {overall_recall*100:>9.1f}% {overall_f1*100:>9.1f}% {overall_fpr*100:>9.1f}%")

    print("\n\nADVERSARIAL TRACES (edge cases, deceptive scenarios):")
    print("-" * 50)

    print("\nBy scenario type:")
    for stype, stats in sorted(adversarial_results["by_type"].items()):
        accuracy = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {stype:<20}: {stats['correct']}/{stats['total']} correct ({accuracy:.0f}%)")

    print("\nBy difficulty:")
    for diff, stats in sorted(adversarial_results["by_difficulty"].items()):
        accuracy = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {diff:<15}: {stats['correct']}/{stats['total']} correct ({accuracy:.0f}%)")

    # Show some failure cases
    incorrect = [d for d in adversarial_results["details"] if not d["correct"]]
    if incorrect:
        print("\n\nMISCLASSIFIED ADVERSARIAL CASES:")
        print("-" * 50)
        for case in incorrect[:5]:
            print(f"\n  Trace: {case['trace_id']}")
            print(f"  Mode: {case['mode']}, Type: {case['scenario_type']}, Difficulty: {case['difficulty']}")
            print(f"  Expected: {'FAILURE' if case['expected_failure'] else 'SUCCESS'}")
            print(f"  Detected: {'FAILURE' if case['detected_failure'] else 'SUCCESS'}")
            print(f"  Reason: {case['reason'][:100]}...")

    # Save full results
    results_file = output_dir / "evaluation_results.json"
    with open(results_file, "w") as f:
        json.dump({
            "semantic_results": {k: {**v, "details": v.get("details", [])[:5]} for k, v in semantic_results.items()},
            "adversarial_results": adversarial_results,
        }, f, indent=2, default=str)

    print(f"\n\nFull results saved to: {results_file}")

    return semantic_results, adversarial_results


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    await run_full_evaluation(
        api_key=api_key,
        traces_per_mode=5,  # 5 failure + 5 healthy per mode
        failure_modes=["F1", "F6", "F14"],  # Start with 3 modes for speed
    )


if __name__ == "__main__":
    asyncio.run(main())
