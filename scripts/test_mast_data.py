#!/usr/bin/env python3
"""
Test MAO detectors against UC Berkeley MAST-Data benchmark.

MAST-Data contains 1,600+ annotated multi-agent system traces with
14 failure modes that align with our taxonomy.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from huggingface_hub import hf_hub_download

# Import our detectors
from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.derailment import TaskDerailmentDetector
from app.detection.context import ContextNeglectDetector
from app.detection.withholding import InformationWithholdingDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.coordination import CoordinationAnalyzer, Message


# MAST failure mode mapping to our detectors
# Based on MAST taxonomy: https://arxiv.org/abs/2503.13657
# MAST uses numeric codes: 1.1, 1.2, etc. with binary labels (0/1)
MAST_NUMERIC_TO_MAO = {
    # Category 1: System Design Issues
    "1.1": "F1",   # Specification Mismatch
    "1.2": "F2",   # Poor Task Decomposition
    "1.3": "F3",   # Resource Misallocation
    "1.4": "F4",   # Inadequate Tool Provision
    "1.5": "F5",   # Flawed Workflow Design

    # Category 2: Inter-Agent Misalignment
    "2.1": "F6",   # Task Derailment
    "2.2": "F7",   # Context Neglect
    "2.3": "F8",   # Information Withholding
    "2.4": "F9",   # Role Usurpation
    "2.5": "F10",  # Communication Breakdown
    "2.6": "F11",  # Coordination Failure

    # Category 3: Task Verification
    "3.1": "F12",  # Output Validation Failure
    "3.2": "F13",  # Quality Gate Bypass
    "3.3": "F14",  # Completion Misjudgment
}

MAST_TO_MAO_MAPPING = {
    # Text-based labels (fallback)
    "specification_mismatch": "F1",
    "poor_task_decomposition": "F2",
    "resource_misallocation": "F3",
    "inadequate_tool_provision": "F4",
    "flawed_workflow_design": "F5",
    "task_derailment": "F6",
    "context_neglect": "F7",
    "information_withholding": "F8",
    "role_usurpation": "F9",
    "communication_breakdown": "F10",
    "coordination_failure": "F11",
    "output_validation_failure": "F12",
    "quality_gate_bypass": "F13",
    "completion_misjudgment": "F14",
}


def download_mast_data() -> List[Dict]:
    """Download MAST-Data from HuggingFace."""
    print("Downloading MAST-Data from HuggingFace...")

    try:
        # Try the main dataset first
        file_path = hf_hub_download(
            repo_id="mcemri/MAD",
            filename="MAD_full_dataset.json",
            repo_type="dataset"
        )
        with open(file_path, "r") as f:
            data = json.load(f)
        print(f"Loaded {len(data)} records from MAD dataset")
        return data
    except Exception as e:
        print(f"Could not download MAD dataset: {e}")

    try:
        # Try alternative dataset
        file_path = hf_hub_download(
            repo_id="mcemri/MAST-Data",
            filename="mast_data.json",
            repo_type="dataset"
        )
        with open(file_path, "r") as f:
            data = json.load(f)
        print(f"Loaded {len(data)} records from MAST-Data")
        return data
    except Exception as e:
        print(f"Could not download MAST-Data: {e}")
        return []


def extract_trace_info(record: Dict) -> Dict:
    """Extract relevant info from a MAST record for testing.

    MAST format:
    - mas_name: Multi-agent system (ChatDev, MetaGPT, etc.)
    - llm_name: LLM used
    - benchmark_name: Benchmark
    - trace: Contains trajectory with task and output
    - mast_annotation: Dict with numeric codes (1.1, 2.1, etc.) as keys and 0/1 as values
    """
    import re

    info = {
        "task": "",
        "output": "",
        "context": "",
        "messages": [],
        "failure_modes": {},  # Dict of mode -> is_present
        "framework": record.get("mas_name", "unknown"),
        "llm": record.get("llm_name", "unknown"),
        "benchmark": record.get("benchmark_name", "unknown"),
    }

    # Extract trace info
    trace = record.get("trace", {})
    if isinstance(trace, dict):
        trajectory = trace.get("trajectory", "")

        # Try multiple patterns for task extraction
        task_patterns = [
            # ChatDev format
            r'\*\*task_prompt\*\*:\s*([^\n|]+)',
            r'\| \*\*task_prompt\*\* \| ([^|]+) \|',
            # Generic patterns
            r'Task:\s*(.+?)(?:\n\n|\n\[|$)',
            r'User Request:\s*(.+?)(?:\n\n|\n\[|$)',
            # MetaGPT, HyperAgent formats
            r'"task":\s*"([^"]+)"',
            r'task:\s*(.+?)(?:\n|$)',
        ]

        for pattern in task_patterns:
            match = re.search(pattern, trajectory, re.IGNORECASE)
            if match:
                task_text = match.group(1).strip()
                # Clean up common artifacts
                task_text = re.sub(r'\s*\|.*$', '', task_text)
                task_text = task_text.strip()
                if len(task_text) > 10:  # Must be meaningful
                    info["task"] = task_text[:1000]
                    break

        # Extract output - look for final sections or use last portion
        output_patterns = [
            r'\*\*\[Final Output\]\*\*(.+?)(?:\*\*\[|$)',
            r'\[Final\](.+?)(?:\[|$)',
            r'Result:(.+?)(?:\n\n|$)',
            r'Output:(.+?)(?:\n\n|$)',
        ]

        output_found = False
        for pattern in output_patterns:
            match = re.search(pattern, trajectory[-50000:], re.DOTALL | re.IGNORECASE)
            if match:
                info["output"] = match.group(1).strip()[:3000]
                output_found = True
                break

        if not output_found:
            # Use last 3000 chars of trajectory as output
            info["output"] = trajectory[-3000:] if len(trajectory) > 3000 else trajectory

        # Use first 3000 chars as context
        info["context"] = trajectory[:3000] if len(trajectory) > 3000 else trajectory

    # Extract failure modes from mast_annotation
    annotation = record.get("mast_annotation", {})
    if isinstance(annotation, dict):
        for code, value in annotation.items():
            mao_mode = MAST_NUMERIC_TO_MAO.get(code)
            if mao_mode:
                info["failure_modes"][mao_mode] = (value == 1 or value == "1" or value is True)

    return info


def run_detector(failure_mode: str, trace_info: Dict) -> bool:
    """Run the appropriate detector for a failure mode."""
    task = trace_info["task"]
    output = trace_info["output"]
    context = trace_info["context"] or task

    if not task or not output:
        return False

    try:
        if failure_mode == "F1":
            detector = SpecificationMismatchDetector()
            result = detector.detect(user_intent=task, task_specification=output)
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F2":
            detector = TaskDecompositionDetector()
            result = detector.detect(task_description=task, decomposition=output)
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F6":
            detector = TaskDerailmentDetector()
            result = detector.detect(task=task, output=output, context=None, agent_name="agent")
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F7":
            detector = ContextNeglectDetector()
            result = detector.detect(context=context, output=output, task=task, agent_name="agent")
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F8":
            detector = InformationWithholdingDetector()
            result = detector.detect(internal_state=context, agent_output=output)
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F14":
            detector = CompletionMisjudgmentDetector()
            result = detector.detect(task=task, agent_output=output)
            return result.detected if hasattr(result, 'detected') else bool(result)

        # For other failure modes, return False (not supported yet)
        return False

    except Exception as e:
        print(f"  Error running detector for {failure_mode}: {e}")
        return False


def evaluate_mast_data(data: List[Dict]) -> Dict:
    """Run MAO detectors against MAST data and evaluate accuracy.

    MAST uses multi-label annotation - each trace can have multiple failure modes.
    We evaluate each detector independently against its ground truth label.
    """

    results = {
        "total_records": 0,
        "total_evaluations": 0,
        "skipped_records": 0,
        "by_mode": defaultdict(lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0}),
        "by_framework": defaultdict(lambda: {"correct": 0, "total": 0}),
        "by_llm": defaultdict(lambda: {"correct": 0, "total": 0}),
        "label_distribution": defaultdict(int),
    }

    # Supported detectors for this evaluation
    supported_modes = ["F1", "F2", "F6", "F7", "F8", "F14"]

    print(f"\nEvaluating {len(data)} MAST records...")
    print(f"Supported detectors: {supported_modes}")
    print("=" * 60)

    for i, record in enumerate(data):
        if i % 200 == 0:
            print(f"Processing record {i}/{len(data)}...")

        trace_info = extract_trace_info(record)
        framework = trace_info["framework"]
        llm = trace_info["llm"]
        failure_modes = trace_info["failure_modes"]

        # Skip if no task/output extracted
        if not trace_info["task"] or not trace_info["output"]:
            results["skipped_records"] += 1
            continue

        results["total_records"] += 1

        # Count label distribution
        for mode, is_present in failure_modes.items():
            if is_present:
                results["label_distribution"][mode] += 1

        # Evaluate each supported detector
        for mode in supported_modes:
            ground_truth = failure_modes.get(mode, False)
            detected = run_detector(mode, trace_info)

            results["total_evaluations"] += 1

            # Update confusion matrix
            mode_stats = results["by_mode"][mode]
            if ground_truth:  # Failure expected
                if detected:
                    mode_stats["tp"] += 1
                else:
                    mode_stats["fn"] += 1
            else:  # No failure expected
                if detected:
                    mode_stats["fp"] += 1
                else:
                    mode_stats["tn"] += 1

            # Track per-framework accuracy
            correct = (detected == ground_truth)
            results["by_framework"][framework]["total"] += 1
            if correct:
                results["by_framework"][framework]["correct"] += 1

            results["by_llm"][llm]["total"] += 1
            if correct:
                results["by_llm"][llm]["correct"] += 1

    return results


def print_results(results: Dict):
    """Print evaluation results."""
    print("\n" + "=" * 70)
    print("MAST-DATA CROSS-VALIDATION RESULTS")
    print("=" * 70)

    print(f"\nTotal MAST records processed: {results['total_records']}")
    print(f"Records skipped (no task/output): {results.get('skipped_records', 0)}")
    print(f"Total detector evaluations: {results['total_evaluations']}")

    # Label distribution
    print("\n" + "-" * 70)
    print("Ground Truth Label Distribution (failure modes present in MAST data):")
    print("-" * 70)
    for mode, count in sorted(results["label_distribution"].items()):
        print(f"  {mode}: {count} traces")

    print("\n" + "-" * 70)
    print("Per-Detector Results:")
    print("-" * 70)
    print(f"{'Mode':<6} {'TP':>6} {'FP':>6} {'TN':>6} {'FN':>6} {'Prec':>8} {'Recall':>8} {'F1':>8} {'Acc':>8}")
    print("-" * 70)

    total_tp, total_fp, total_tn, total_fn = 0, 0, 0, 0

    for mode in sorted(results["by_mode"].keys()):
        stats = results["by_mode"][mode]
        tp, fp, tn, fn = stats["tp"], stats["fp"], stats["tn"], stats["fn"]

        total_tp += tp
        total_fp += fp
        total_tn += tn
        total_fn += fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0

        print(f"{mode:<6} {tp:>6} {fp:>6} {tn:>6} {fn:>6} {precision:>7.1%} {recall:>7.1%} {f1:>7.1%} {accuracy:>7.1%}")

    print("-" * 70)

    # Overall metrics
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0
    overall_accuracy = (total_tp + total_tn) / (total_tp + total_fp + total_tn + total_fn) if (total_tp + total_fp + total_tn + total_fn) > 0 else 0

    print(f"{'TOTAL':<6} {total_tp:>6} {total_fp:>6} {total_tn:>6} {total_fn:>6} {overall_precision:>7.1%} {overall_recall:>7.1%} {overall_f1:>7.1%} {overall_accuracy:>7.1%}")

    print("\n" + "-" * 70)
    print("By Multi-Agent System Framework:")
    print("-" * 70)
    for fw, stats in sorted(results["by_framework"].items(), key=lambda x: -x[1]["total"]):
        if stats["total"] > 0:
            acc = stats["correct"] / stats["total"]
            print(f"  {fw}: {stats['correct']}/{stats['total']} ({acc:.1%})")

    print("\n" + "-" * 70)
    print("By LLM:")
    print("-" * 70)
    for llm, stats in sorted(results["by_llm"].items(), key=lambda x: -x[1]["total"]):
        if stats["total"] > 0:
            acc = stats["correct"] / stats["total"]
            print(f"  {llm}: {stats['correct']}/{stats['total']} ({acc:.1%})")

    print("\n" + "=" * 70)
    target_f1 = 0.70
    status = "PASS" if overall_f1 >= target_f1 else "FAIL"
    print(f"TARGET CHECK: F1={overall_f1:.1%} (target: >{target_f1:.0%}) [{status}]")
    print(f"              Accuracy={overall_accuracy:.1%}")
    print("=" * 70)

    return overall_f1


def main():
    # Download MAST data
    data = download_mast_data()

    if not data:
        print("No MAST data available. Creating synthetic test...")
        # Create synthetic test data for demonstration
        data = [
            {
                "task": "Write a Python function to calculate factorial",
                "output": "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)",
                "failure_mode": "success",
                "framework": "test"
            },
            {
                "task": "Analyze Q3 sales data",
                "output": "I've analyzed the marketing strategy instead of sales data.",
                "failure_mode": "task_derailment",
                "framework": "test"
            },
            {
                "task": "Continue the analysis from the previous report",
                "output": "Starting fresh analysis without referencing previous work.",
                "failure_mode": "context_neglect",
                "framework": "test"
            },
        ]
        print(f"Created {len(data)} synthetic test cases")

    # Evaluate
    results = evaluate_mast_data(data)

    # Print results
    f1_score = print_results(results)

    # Save results
    output_path = Path(__file__).parent.parent / "benchmarks" / "results" / "mast_data_eval.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert defaultdicts for JSON serialization
    results["by_mode"] = dict(results["by_mode"])
    results["by_framework"] = dict(results["by_framework"])
    results["by_llm"] = dict(results["by_llm"])
    results["label_distribution"] = dict(results["label_distribution"])

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")

    return f1_score >= 0.70


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
