"""Evaluate detectors and track results with versioning.

Run with: python -m src.evaluate_detectors [--version VERSION]
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Add mao-testing backend to path (relative to this file's location)
_BACKEND_PATH = str(Path(__file__).parent.parent.parent / "backend")
_BENCHMARKS_PATH = str(Path(__file__).parent.parent)
sys.path.insert(0, _BACKEND_PATH)
sys.path.insert(0, _BENCHMARKS_PATH)

from data.detector_versioning import (
    DetectorVersionManager, DetectorConfig, EvaluationResult,
    create_evaluation_result, print_results_table, compute_metrics
)
from data.adversarial import load_adversarial_cases, get_adversarial_stats

# Import detectors
from app.detection.withholding import InformationWithholdingDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.derailment import TaskDerailmentDetector
from app.detection.context import ContextNeglectDetector
from app.detection.communication import CommunicationBreakdownDetector
from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.quality_gate import QualityGateDetector
from app.detection.resource_misallocation import ResourceMisallocationDetector
from app.detection.tool_provision import ToolProvisionDetector
from app.detection.workflow import FlawedWorkflowDetector
from app.detection.role_usurpation import RoleUsurpationDetector
from app.detection.coordination import CoordinationAnalyzer
from app.detection.output_validation import OutputValidationDetector

# Import detection runners
from src.run_all_detectors import (
    run_specification_detection, run_decomposition_detection, run_quality_gate_detection,
    run_resource_misallocation_detection, run_tool_provision_detection, run_workflow_detection,
    run_role_usurpation_detection, run_coordination_detection, run_output_validation_detection,
    run_withholding_detection, run_completion_detection, run_derailment_detection,
    run_context_detection, run_communication_detection,
    run_grounding_detection, run_retrieval_quality_detection,
)

TRACES_DIR = Path("traces")
FRAMEWORKS = ["langchain", "autogen", "crewai", "n8n"]

MODE_CONFIG = {
    "F1": ("specification", SpecificationMismatchDetector, run_specification_detection),
    "F2": ("decomposition", TaskDecompositionDetector, run_decomposition_detection),
    "F3": ("resource_misallocation", ResourceMisallocationDetector, run_resource_misallocation_detection),
    "F4": ("tool_provision", ToolProvisionDetector, run_tool_provision_detection),
    "F5": ("workflow", FlawedWorkflowDetector, run_workflow_detection),
    "F6": ("derailment", TaskDerailmentDetector, run_derailment_detection),
    "F7": ("context", ContextNeglectDetector, run_context_detection),
    "F8": ("withholding", InformationWithholdingDetector, run_withholding_detection),
    "F9": ("role_usurpation", RoleUsurpationDetector, run_role_usurpation_detection),
    "F10": ("communication", CommunicationBreakdownDetector, run_communication_detection),
    "F11": ("coordination", CoordinationAnalyzer, run_coordination_detection),
    "F12": ("output_validation", OutputValidationDetector, run_output_validation_detection),
    "F13": ("quality_gate", QualityGateDetector, run_quality_gate_detection),
    "F14": ("completion", CompletionMisjudgmentDetector, run_completion_detection),
    "F15": ("grounding", None, run_grounding_detection),  # OfficeQA-inspired
    "F16": ("retrieval_quality", None, run_retrieval_quality_detection),  # OfficeQA-inspired
}

MODE_NAMES = {
    'F1': 'Specification Mismatch', 'F2': 'Task Decomposition',
    'F3': 'Resource Misallocation', 'F4': 'Tool Provision',
    'F5': 'Workflow Design', 'F6': 'Task Derailment',
    'F7': 'Context Neglect', 'F8': 'Information Withholding',
    'F9': 'Role Usurpation', 'F10': 'Communication Breakdown',
    'F11': 'Coordination Failure', 'F12': 'Output Validation',
    'F13': 'Quality Gate Bypass', 'F14': 'Completion Misjudgment',
    'F15': 'Grounding Failure', 'F16': 'Retrieval Quality',
}


def load_traces(mode: str, is_healthy: bool = False) -> list[dict]:
    """Load traces for a specific mode."""
    traces = []
    suffix = "healthy_traces" if is_healthy else "scaled_traces"

    for fw in FRAMEWORKS:
        file_path = TRACES_DIR / f"{fw}_{suffix}.jsonl"
        if file_path.exists():
            with open(file_path) as f:
                for line in f:
                    if line.strip():
                        trace = json.loads(line)
                        if trace.get("failure_mode") == mode:
                            traces.append(trace)
    return traces


def evaluate_mode(mode: str, version: str = "v1.0", include_adversarial: bool = False) -> EvaluationResult:
    """Evaluate a single failure mode detector.

    Args:
        mode: Failure mode (e.g., 'F8', 'F12')
        version: Version label for this evaluation
        include_adversarial: Include adversarial test cases for harder evaluation
    """
    detector_name, detector_cls, run_fn = MODE_CONFIG[mode]
    detector = detector_cls() if detector_cls else None

    # Load traces
    failure_traces = load_traces(mode, is_healthy=False)
    healthy_traces = load_traces(mode, is_healthy=True)

    # Run detection on failure traces (should detect)
    if detector:
        failure_result = run_fn(failure_traces, detector)
        healthy_result = run_fn(healthy_traces, detector)
    else:
        # For detectors without a class (F15, F16)
        failure_result = run_fn(failure_traces)
        healthy_result = run_fn(healthy_traces)

    tp = failure_result["detected"]
    fn = failure_result["total"] - tp

    # Run detection on healthy traces (should NOT detect)
    fp = healthy_result["detected"]
    tn = healthy_result["total"] - fp

    # Include adversarial test cases if requested
    adversarial_stats = {"tested": 0, "correct": 0}
    if include_adversarial:
        adversarial_cases = load_adversarial_cases(mode)
        if adversarial_cases:
            for case in adversarial_cases:
                trace = case.get("trace", {})
                expected = case.get("expected_detection", False)

                # Run detection on this case
                if detector:
                    case_result = run_fn([trace], detector)
                else:
                    case_result = run_fn([trace])

                detected = case_result["detected"] > 0
                adversarial_stats["tested"] += 1

                if detected == expected:
                    adversarial_stats["correct"] += 1
                    if expected:
                        tp += 1  # Correctly detected (true positive)
                    else:
                        tn += 1  # Correctly not detected (true negative)
                else:
                    if expected:
                        fn += 1  # Should have detected but didn't (false negative)
                    else:
                        fp += 1  # Shouldn't have detected but did (false positive)

    result = create_evaluation_result(
        mode=mode,
        version=version,
        config_hash="baseline" + ("_adv" if include_adversarial else ""),
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        failure_traces=len(failure_traces),
        healthy_traces=len(healthy_traces),
        frameworks=FRAMEWORKS,
    )

    # Store adversarial stats in result for reporting
    if include_adversarial and adversarial_stats["tested"] > 0:
        result._adversarial_stats = adversarial_stats

    return result


def evaluate_all(version: str = "v1.0", save_results: bool = True, include_adversarial: bool = False) -> dict[str, EvaluationResult]:
    """Evaluate all detectors and optionally save results.

    Args:
        version: Version label for this evaluation
        save_results: Save results to disk
        include_adversarial: Include adversarial test cases for harder evaluation
    """
    version_manager = DetectorVersionManager()
    results = {}

    print("=" * 90)
    print(f"DETECTOR EVALUATION - Version: {version}")
    if include_adversarial:
        print("MODE: Including adversarial test cases (harder evaluation)")
        adv_stats = get_adversarial_stats()
        for mode, stats in adv_stats.items():
            print(f"  {mode}: {stats['total_cases']} adversarial cases")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 90)
    print()

    for mode in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13", "F14", "F15", "F16"]:
        print(f"Evaluating {mode} ({MODE_NAMES[mode]})...", end=" ", flush=True)
        result = evaluate_mode(mode, version, include_adversarial=include_adversarial)
        results[mode] = result

        if save_results:
            version_manager.save_result(result)

        status = "OK" if result.f1 > 0.5 else "WARN" if result.f1 > 0 else "FAIL"
        adv_info = ""
        if include_adversarial and hasattr(result, '_adversarial_stats'):
            stats = result._adversarial_stats
            adv_info = f" [ADV: {stats['correct']}/{stats['tested']}]"
        print(f"F1={result.f1*100:.1f}% [{status}]{adv_info}")

    print()
    print("=" * 90)
    print("SUMMARY (with consistency metrics)")
    print("=" * 90)
    print_results_table(results, show_consistency=True)

    # Compute totals
    total_tp = sum(r.tp for r in results.values())
    total_fp = sum(r.fp for r in results.values())
    total_tn = sum(r.tn for r in results.values())
    total_fn = sum(r.fn for r in results.values())
    total_metrics = compute_metrics(total_tp, total_fp, total_tn, total_fn)

    print("-" * 90)
    print(f"{'TOTAL':<5} {'':<18} {version:<5} {total_metrics['precision']*100:>5.1f}% {total_metrics['recall']*100:>5.1f}% {total_metrics['f1']*100:>5.1f}%")
    print()

    if save_results:
        print(f"Results saved to: detector_versions/results/")

    return results


def show_history(mode: str = None) -> None:
    """Show evaluation history."""
    version_manager = DetectorVersionManager()
    history = version_manager.get_history(mode)

    if not history:
        print("No evaluation history found.")
        return

    print("=" * 90)
    print("EVALUATION HISTORY")
    print("=" * 90)
    print(f"{'Timestamp':<20} {'Mode':<5} {'Version':<8} {'Prec':>7} {'Recall':>7} {'F1':>7} {'FPR':>7}")
    print("-" * 90)

    for r in sorted(history, key=lambda x: x.timestamp):
        ts = r.timestamp[:19]  # Truncate microseconds
        print(f"{ts:<20} {r.mode:<5} {r.version:<8} {r.precision*100:>6.1f}% {r.recall*100:>6.1f}% {r.f1*100:>6.1f}% {r.fpr*100:>6.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Evaluate MAST detectors")
    parser.add_argument("--version", "-v", default="v1.0", help="Version label for this evaluation")
    parser.add_argument("--history", "-H", action="store_true", help="Show evaluation history")
    parser.add_argument("--mode", "-m", help="Evaluate specific mode only")
    parser.add_argument("--no-save", action="store_true", help="Don't save results")
    parser.add_argument("--include-adversarial", "-a", action="store_true",
                        help="Include adversarial test cases for harder evaluation (F8, F12)")

    args = parser.parse_args()

    if args.history:
        show_history(args.mode)
    elif args.mode:
        result = evaluate_mode(args.mode, args.version, include_adversarial=args.include_adversarial)
        print(f"{args.mode}: Precision={result.precision*100:.1f}% Recall={result.recall*100:.1f}% F1={result.f1*100:.1f}% FPR={result.fpr*100:.1f}%")
        if args.include_adversarial and hasattr(result, '_adversarial_stats'):
            stats = result._adversarial_stats
            print(f"Adversarial: {stats['correct']}/{stats['tested']} correct")
        print(f"Consistency: pass@k={result.pass_at_k*100:.1f}% pass^k={result.pass_caret_k*100:.1f}% gap={result.consistency_gap*100:.1f}%")
    else:
        evaluate_all(args.version, save_results=not args.no_save, include_adversarial=args.include_adversarial)


if __name__ == "__main__":
    main()
