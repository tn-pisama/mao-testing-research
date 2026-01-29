"""n8n Detector Benchmark Runner

Runs n8n detectors against workflow test data and computes accuracy metrics.

Usage:
    python3 -m app.benchmark.n8n_runner \\
        --data-dir n8n-workflows/ \\
        --output results.json
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.benchmark.n8n_loader import N8nBenchmarkLoader, N8nBenchmarkWorkflow
from app.detection.n8n import (
    N8NCycleDetector,
    N8NSchemaDetector,
    N8NResourceDetector,
    N8NTimeoutDetector,
    N8NErrorDetector,
    N8NComplexityDetector,
)
from app.detection.turn_aware._base import TurnSnapshot

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of running a detector on a workflow."""

    workflow_id: str
    detector_name: str
    detected: bool
    confidence: float
    failure_mode: Optional[str]
    expected_failure_mode: Optional[str]
    explanation: str
    correct: Optional[bool] = None  # True if prediction matches expected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "detector_name": self.detector_name,
            "detected": self.detected,
            "confidence": round(self.confidence, 4),
            "failure_mode": self.failure_mode,
            "expected_failure_mode": self.expected_failure_mode,
            "explanation": self.explanation,
            "correct": self.correct,
        }


@dataclass
class N8nBenchmarkMetrics:
    """Metrics for a single detector."""

    detector_name: str
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    total_workflows: int = 0

    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)"""
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)"""
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1_score(self) -> float:
        """F1 Score: 2 * (precision * recall) / (precision + recall)"""
        p = self.precision
        r = self.recall
        return 2 * (p * r) / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        """Accuracy: (TP + TN) / Total"""
        return (
            (self.true_positives + self.true_negatives) / self.total_workflows
            if self.total_workflows > 0
            else 0.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detector_name": self.detector_name,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "accuracy": round(self.accuracy, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "total_workflows": self.total_workflows,
        }


class N8nDetectorBenchmark:
    """Benchmark runner for n8n detectors."""

    def __init__(self):
        self.detectors = {
            "N8NCycleDetector": N8NCycleDetector(),
            "N8NSchemaDetector": N8NSchemaDetector(),
            "N8NResourceDetector": N8NResourceDetector(),
            "N8NTimeoutDetector": N8NTimeoutDetector(),
            "N8NErrorDetector": N8NErrorDetector(),
            "N8NComplexityDetector": N8NComplexityDetector(),
        }
        self.results: List[DetectionResult] = []

    def run_detector(
        self, detector_name: str, workflow: N8nBenchmarkWorkflow
    ) -> DetectionResult:
        """Run a single detector on a workflow."""
        detector = self.detectors[detector_name]
        turns = workflow.to_turn_snapshots()

        # Build conversation metadata
        metadata = {
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "workflow_duration_ms": len(turns) * 1000,  # Simulated
            "workflow_mode": "manual",  # Not webhook for patterns
        }

        # Run detector
        result = detector.detect(turns, metadata)

        # Create detection result
        detection = DetectionResult(
            workflow_id=workflow.id,
            detector_name=detector_name,
            detected=result.detected,
            confidence=result.confidence,
            failure_mode=result.failure_mode,
            expected_failure_mode=workflow.expected_failure_mode,
            explanation=result.explanation,
        )

        # Determine correctness
        if workflow.expected_failure_mode:
            # Expected a failure - check if detector detected it
            if result.detected and result.failure_mode == workflow.expected_failure_mode:
                detection.correct = True  # TP
            elif not result.detected:
                detection.correct = False  # FN
            elif result.detected and result.failure_mode != workflow.expected_failure_mode:
                detection.correct = False  # FP (wrong failure mode)
        else:
            # No expected failure
            detection.correct = not result.detected  # TN if not detected, FP if detected

        return detection

    def run_benchmark(
        self, workflows: List[N8nBenchmarkWorkflow]
    ) -> Dict[str, N8nBenchmarkMetrics]:
        """Run all detectors on all workflows and compute metrics."""
        logger.info(f"Running benchmark on {len(workflows)} workflows")

        # Run each detector on each workflow
        for workflow in workflows:
            for detector_name in self.detectors.keys():
                result = self.run_detector(detector_name, workflow)
                self.results.append(result)

        # Compute metrics per detector
        metrics = {}
        for detector_name in self.detectors.keys():
            metrics[detector_name] = self._compute_metrics(detector_name, workflows)

        return metrics

    def _compute_metrics(
        self, detector_name: str, workflows: List[N8nBenchmarkWorkflow]
    ) -> N8nBenchmarkMetrics:
        """Compute metrics for a specific detector."""
        detector_results = [r for r in self.results if r.detector_name == detector_name]

        metrics = N8nBenchmarkMetrics(
            detector_name=detector_name, total_workflows=len(workflows)
        )

        for result in detector_results:
            if result.expected_failure_mode:
                # Expected a failure
                if result.detected and result.correct:
                    metrics.true_positives += 1
                elif not result.detected:
                    metrics.false_negatives += 1
                elif result.detected and not result.correct:
                    metrics.false_positives += 1
            else:
                # No expected failure
                if not result.detected:
                    metrics.true_negatives += 1
                else:
                    metrics.false_positives += 1

        return metrics

    def generate_report(self, metrics: Dict[str, N8nBenchmarkMetrics]) -> str:
        """Generate markdown report from metrics."""
        report = []
        report.append("# n8n Detector Benchmark Results")
        report.append("")
        report.append(f"**Run Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Total Workflows**: {len(self.results) // len(self.detectors)}")
        report.append("")

        report.append("## Overall Results")
        report.append("")
        report.append("| Detector | Precision | Recall | F1 Score | Accuracy | TP | FP | TN | FN |")
        report.append("|----------|-----------|--------|----------|----------|----|----|----|----|")

        for detector_name, m in metrics.items():
            report.append(
                f"| {detector_name} | {m.precision:.4f} | {m.recall:.4f} | "
                f"{m.f1_score:.4f} | {m.accuracy:.4f} | {m.true_positives} | "
                f"{m.false_positives} | {m.true_negatives} | {m.false_negatives} |"
            )

        report.append("")

        # Average metrics
        avg_precision = sum(m.precision for m in metrics.values()) / len(metrics)
        avg_recall = sum(m.recall for m in metrics.values()) / len(metrics)
        avg_f1 = sum(m.f1_score for m in metrics.values()) / len(metrics)

        report.append("## Average Metrics")
        report.append("")
        report.append(f"- **Average Precision**: {avg_precision:.4f}")
        report.append(f"- **Average Recall**: {avg_recall:.4f}")
        report.append(f"- **Average F1 Score**: {avg_f1:.4f}")
        report.append("")

        # Per-failure-mode breakdown
        failure_modes = set(
            r.expected_failure_mode
            for r in self.results
            if r.expected_failure_mode
        )

        if failure_modes:
            report.append("## Detection Rate by Failure Mode")
            report.append("")
            report.append("| Failure Mode | Detected | Total | Detection Rate |")
            report.append("|--------------|----------|-------|----------------|")

            for mode in sorted(failure_modes):
                mode_results = [
                    r for r in self.results if r.expected_failure_mode == mode
                ]
                detected = sum(1 for r in mode_results if r.detected)
                total = len(mode_results)
                rate = detected / total if total > 0 else 0.0
                report.append(f"| {mode} | {detected} | {total} | {rate:.2%} |")

        return "\n".join(report)

    def save_results(self, output_path: Path):
        """Save results to JSON file."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_workflows": len(self.results) // len(self.detectors),
            "results": [r.to_dict() for r in self.results],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Results saved to {output_path}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run n8n detector benchmarks")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default="n8n-workflows",
        help="Directory containing n8n workflows",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default="benchmarks/n8n_detector_results.json",
        help="Output JSON file",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Output markdown report file",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load workflows
    loader = N8nBenchmarkLoader()
    pattern_workflows = loader.load_failure_patterns(args.data_dir)

    all_workflows = []
    for workflows in pattern_workflows.values():
        all_workflows.extend(workflows)

    logger.info(f"Loaded {len(all_workflows)} workflows for benchmarking")
    logger.info(f"Statistics: {loader.get_statistics()}")

    # Run benchmark
    benchmark = N8nDetectorBenchmark()
    metrics = benchmark.run_benchmark(all_workflows)

    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    benchmark.save_results(args.output)

    # Generate and save report
    report = benchmark.generate_report(metrics)
    print(report)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {args.report}")


if __name__ == "__main__":
    main()
