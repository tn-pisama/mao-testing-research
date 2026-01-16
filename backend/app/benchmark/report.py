"""Report generation for MAST benchmarks.

Generates reports in JSON, Markdown, and console formats.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.benchmark.metrics import BenchmarkMetrics, FailureModeMetrics
from app.benchmark.runner import BenchmarkResult
from app.benchmark.mast_loader import FAILURE_MODE_NAMES

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    """Output format for benchmark reports."""
    JSON = "json"
    MARKDOWN = "markdown"
    CONSOLE = "console"


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    format: ReportFormat = ReportFormat.MARKDOWN
    include_confusion_matrices: bool = True
    include_calibration: bool = True
    include_per_framework: bool = True
    include_latency: bool = True
    include_misclassified_samples: int = 10
    show_all_modes: bool = False  # Show modes with 0 samples


class ReportGenerator:
    """Generate benchmark reports in multiple formats."""

    def __init__(self, config: Optional[ReportConfig] = None):
        """Initialize report generator.

        Args:
            config: Report configuration
        """
        self.config = config or ReportConfig()

    def generate(
        self,
        metrics: BenchmarkMetrics,
        result: BenchmarkResult,
    ) -> str:
        """Generate report in configured format.

        Args:
            metrics: BenchmarkMetrics from MetricsComputer
            result: BenchmarkResult from BenchmarkRunner

        Returns:
            Report string in configured format
        """
        if self.config.format == ReportFormat.JSON:
            return self._generate_json(metrics, result)
        elif self.config.format == ReportFormat.MARKDOWN:
            return self._generate_markdown(metrics, result)
        else:
            return self._generate_console(metrics, result)

    def _generate_json(
        self,
        metrics: BenchmarkMetrics,
        result: BenchmarkResult,
    ) -> str:
        """Generate JSON report."""
        report = {
            "benchmark": result.to_dict(),
            "metrics": metrics.to_dict(),
            "generated_at": datetime.utcnow().isoformat(),
        }

        if self.config.include_per_framework:
            report["by_framework"] = self._compute_framework_breakdown(result)

        return json.dumps(report, indent=2)

    def _generate_markdown(
        self,
        metrics: BenchmarkMetrics,
        result: BenchmarkResult,
    ) -> str:
        """Generate Markdown report."""
        lines = []

        # Header
        lines.append("# MAST Benchmark Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"**Run ID:** {result.run_id}")
        lines.append(f"**Duration:** {result.duration_seconds:.1f} seconds")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Records | {result.total_records:,} |")
        lines.append(f"| Processed | {result.processed_records:,} |")
        lines.append(f"| Detections | {result.total_detections:,} |")
        lines.append(f"| Macro F1 | {metrics.macro_f1:.3f} |")
        lines.append(f"| Micro F1 | {metrics.micro_f1:.3f} |")
        lines.append(f"| Weighted F1 | {metrics.weighted_f1:.3f} |")
        lines.append(f"| Overall Accuracy | {metrics.overall_accuracy:.1%} |")
        if self.config.include_calibration:
            lines.append(f"| ECE (Calibration) | {metrics.overall_ece:.3f} |")
        if self.config.include_latency:
            lines.append(f"| Mean Latency | {metrics.mean_latency_per_record_ms:.1f} ms/record |")
        lines.append("")

        # Per-Mode Results
        lines.append("## Per-Failure-Mode Results")
        lines.append("")

        # Group modes by performance tier
        high_f1 = []
        medium_f1 = []
        low_f1 = []

        for mode, mode_metrics in sorted(metrics.by_mode.items()):
            if mode_metrics.sample_count == 0 and not self.config.show_all_modes:
                continue
            if mode_metrics.f1 >= 0.8:
                high_f1.append((mode, mode_metrics))
            elif mode_metrics.f1 >= 0.5:
                medium_f1.append((mode, mode_metrics))
            else:
                low_f1.append((mode, mode_metrics))

        if high_f1:
            lines.append("### High Performance (F1 >= 0.80)")
            lines.append("")
            lines.extend(self._generate_mode_table(high_f1))
            lines.append("")

        if medium_f1:
            lines.append("### Medium Performance (0.50 <= F1 < 0.80)")
            lines.append("")
            lines.extend(self._generate_mode_table(medium_f1))
            lines.append("")

        if low_f1:
            lines.append("### Low Performance (F1 < 0.50)")
            lines.append("")
            lines.extend(self._generate_mode_table(low_f1))
            lines.append("")

        # Confusion matrices
        if self.config.include_confusion_matrices:
            lines.append("## Confusion Matrices")
            lines.append("")
            for mode, mode_metrics in sorted(metrics.by_mode.items()):
                if mode_metrics.sample_count == 0:
                    continue
                lines.extend(self._generate_confusion_matrix(mode, mode_metrics))
                lines.append("")

        # Framework breakdown
        if self.config.include_per_framework:
            framework_data = self._compute_framework_breakdown(result)
            if framework_data:
                lines.append("## Framework Breakdown")
                lines.append("")
                lines.append("| Framework | Traces | With Failures | Detection Rate |")
                lines.append("|-----------|-------:|---------------:|---------------:|")
                for fw, data in sorted(framework_data.items(), key=lambda x: -x[1]["count"]):
                    rate = data["detected"] / data["count"] * 100 if data["count"] > 0 else 0
                    lines.append(
                        f"| {fw} | {data['count']:,} | {data['with_failures']:,} | {rate:.1f}% |"
                    )
                lines.append("")

        # Errors
        if result.errors:
            lines.append("## Errors")
            lines.append("")
            for i, error in enumerate(result.errors[:10], 1):
                lines.append(f"{i}. {error}")
            if len(result.errors) > 10:
                lines.append(f"... and {len(result.errors) - 10} more errors")
            lines.append("")

        return "\n".join(lines)

    def _generate_mode_table(
        self,
        modes: List[tuple],
    ) -> List[str]:
        """Generate table for a list of modes."""
        lines = []
        lines.append("| Mode | Name | Precision | Recall | F1 | Accuracy | Support |")
        lines.append("|------|------|----------:|-------:|---:|---------:|--------:|")

        for mode, mode_metrics in modes:
            name = FAILURE_MODE_NAMES.get(mode, mode)
            lines.append(
                f"| {mode} | {name} | "
                f"{mode_metrics.precision:.3f} | "
                f"{mode_metrics.recall:.3f} | "
                f"{mode_metrics.f1:.3f} | "
                f"{mode_metrics.accuracy:.3f} | "
                f"{mode_metrics.support:,} |"
            )

        return lines

    def _generate_confusion_matrix(
        self,
        mode: str,
        mode_metrics: FailureModeMetrics,
    ) -> List[str]:
        """Generate confusion matrix display for a mode."""
        lines = []
        cm = mode_metrics.confusion_matrix
        name = FAILURE_MODE_NAMES.get(mode, mode)

        lines.append(f"### {mode}: {name}")
        lines.append("")
        lines.append("```")
        lines.append("              Predicted")
        lines.append("            Pos    Neg")
        lines.append(f"Actual Pos  {cm.tp:5d}  {cm.fn:5d}  (TP, FN)")
        lines.append(f"       Neg  {cm.fp:5d}  {cm.tn:5d}  (FP, TN)")
        lines.append("```")

        return lines

    def _generate_console(
        self,
        metrics: BenchmarkMetrics,
        result: BenchmarkResult,
    ) -> str:
        """Generate console-friendly report."""
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("MAST BENCHMARK REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        lines.append(f"Records: {result.total_records:,} | "
                     f"Processed: {result.processed_records:,} | "
                     f"Duration: {result.duration_seconds:.1f}s")
        lines.append("")
        lines.append(f"Macro F1:    {metrics.macro_f1:.3f}")
        lines.append(f"Micro F1:    {metrics.micro_f1:.3f}")
        lines.append(f"Weighted F1: {metrics.weighted_f1:.3f}")
        lines.append(f"Accuracy:    {metrics.overall_accuracy:.1%}")
        lines.append("")

        # Per-mode
        lines.append("-" * 60)
        lines.append(f"{'Mode':<6} {'Name':<28} {'P':>6} {'R':>6} {'F1':>6} {'Acc':>6}")
        lines.append("-" * 60)

        for mode, mode_metrics in sorted(metrics.by_mode.items()):
            if mode_metrics.sample_count == 0:
                continue
            name = FAILURE_MODE_NAMES.get(mode, mode)[:28]
            lines.append(
                f"{mode:<6} {name:<28} "
                f"{mode_metrics.precision:>6.3f} "
                f"{mode_metrics.recall:>6.3f} "
                f"{mode_metrics.f1:>6.3f} "
                f"{mode_metrics.accuracy:>6.3f}"
            )

        lines.append("-" * 60)
        lines.append("")

        return "\n".join(lines)

    def _compute_framework_breakdown(
        self,
        result: BenchmarkResult,
    ) -> Dict[str, Dict[str, Any]]:
        """Compute breakdown by framework."""
        from collections import defaultdict

        # Count by framework
        framework_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "with_failures": 0, "detected": 0}
        )

        # Get framework from ground truths or attempts
        # Note: This requires access to original records which we don't have here
        # For now, return empty dict - needs loader reference
        return dict(framework_data)


def generate_benchmark_report(
    metrics: BenchmarkMetrics,
    result: BenchmarkResult,
    format: ReportFormat = ReportFormat.MARKDOWN,
    output_path: Optional[str] = None,
) -> str:
    """Convenience function to generate and optionally save a report.

    Args:
        metrics: BenchmarkMetrics from MetricsComputer
        result: BenchmarkResult from BenchmarkRunner
        format: Output format
        output_path: Optional path to save report

    Returns:
        Report string
    """
    config = ReportConfig(format=format)
    generator = ReportGenerator(config)
    report = generator.generate(metrics, result)

    if output_path:
        with open(output_path, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {output_path}")

    return report
