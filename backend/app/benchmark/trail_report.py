"""TRAIL Benchmark Report Generator.

Generates Markdown and JSON reports from TRAIL benchmark results.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.benchmark.trail_loader import (
    TRAIL_ALL_CATEGORIES,
    TRAIL_TO_PISAMA,
    TRAIL_UNMAPPED_CATEGORIES,
)
from app.benchmark.trail_metrics import CategoryMetrics
from app.benchmark.trail_runner import TRAILBenchmarkResult

logger = logging.getLogger(__name__)


def generate_report(
    result: TRAILBenchmarkResult,
    format: str = "markdown",
) -> str:
    """Generate a TRAIL benchmark report.

    Args:
        result: TRAILBenchmarkResult from TRAILBenchmarkRunner.run().
        format: "markdown" or "json".

    Returns:
        Report string.
    """
    if format == "json":
        return _generate_json(result)
    return _generate_markdown(result)


def _generate_json(result: TRAILBenchmarkResult) -> str:
    """Generate JSON report."""
    report: Dict[str, Any] = {
        "benchmark": "TRAIL (PatronusAI)",
        "result": result.to_dict(),
        "per_category_f1": {
            cat: metrics.to_dict()
            for cat, metrics in result.per_category_f1.items()
        },
        "per_impact": result.per_impact,
        "per_source": result.per_source,
        "category_mapping": TRAIL_TO_PISAMA,
        "generated_at": datetime.utcnow().isoformat(),
    }
    return json.dumps(report, indent=2)


def _generate_markdown(result: TRAILBenchmarkResult) -> str:
    """Generate Markdown report."""
    lines: list[str] = []

    # Header
    lines.append("# TRAIL Benchmark Report")
    lines.append("")
    lines.append(
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    lines.append(f"**Run ID:** {result.run_id}")
    lines.append(f"**Duration:** {result.duration_seconds:.1f} seconds")
    lines.append("")

    # Executive summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Traces | {result.total_traces:,} |")
    lines.append(f"| Processed | {result.processed_traces:,} |")
    lines.append(f"| Total Annotations | {result.total_annotations:,} |")
    lines.append(
        f"| Mapped Annotations (Pisama-covered) | {result.mapped_annotations:,} |"
    )
    lines.append(
        f"| Unmapped (system-level) | "
        f"{result.total_annotations - result.mapped_annotations:,} |"
    )
    lines.append(f"| Positive Detections | {len(result.positive_predictions):,} |")
    lines.append(f"| **Joint Accuracy** | **{result.joint_accuracy:.1%}** |")
    lines.append(f"| Macro F1 | {result.macro_f1:.3f} |")
    lines.append(f"| Micro F1 | {result.micro_f1:.3f} |")
    lines.append("")

    # Baseline comparison
    lines.append("### Baseline Comparison")
    lines.append("")
    lines.append(
        "The TRAIL paper reports an 11% joint accuracy baseline "
        "(best single-model performance). "
        "Pisama uses rule-based detectors without LLM calls."
    )
    lines.append("")
    lines.append(f"- **Pisama joint accuracy:** {result.joint_accuracy:.1%}")
    lines.append("- **TRAIL baseline:** 11%")
    delta = result.joint_accuracy - 0.11
    if delta > 0:
        lines.append(f"- **Delta:** +{delta:.1%} above baseline")
    elif delta < 0:
        lines.append(f"- **Delta:** {delta:.1%} below baseline")
    else:
        lines.append("- **Delta:** at baseline")
    lines.append("")

    # Coverage note
    lines.append("### Coverage")
    lines.append("")
    mapped_count = len(TRAIL_TO_PISAMA)
    total_count = len(TRAIL_ALL_CATEGORIES)
    lines.append(
        f"Pisama covers **{mapped_count}/{total_count}** TRAIL failure categories. "
        f"The {total_count - mapped_count} unmapped categories are system-level "
        f"infrastructure failures (Rate Limiting, Authentication Errors, etc.) "
        f"that fall outside agent reasoning detection."
    )
    lines.append("")

    # Caveats
    lines.append("### Caveats")
    lines.append("")
    lines.append(
        "- **Formatting Errors** maps to Pisama's `completion` detector, "
        "which checks task completion, not output formatting. "
        "This mapping is approximate."
    )
    lines.append(
        "- **Grounding** reuses the hallucination detector on tool output "
        "misinterpretation. A dedicated grounding detector may perform better."
    )
    lines.append(
        "- **Retrieval Quality** similarly proxies through hallucination "
        "detection on retrieved documents."
    )
    lines.append("")

    # Per-category F1 table
    lines.append("## Per-Category F1")
    lines.append("")
    lines.append(
        "| TRAIL Category | Pisama Detector | Precision | Recall | F1 | Support |"
    )
    lines.append("|----------------|-----------------|----------:|-------:|---:|--------:|")

    for cat in sorted(result.per_category_f1.keys()):
        metrics = result.per_category_f1[cat]
        pisama = TRAIL_TO_PISAMA.get(cat, "-")
        lines.append(
            f"| {cat} | {pisama} | "
            f"{metrics.precision:.3f} | "
            f"{metrics.recall:.3f} | "
            f"{metrics.f1:.3f} | "
            f"{metrics.support:,} |"
        )

    lines.append("")

    # Per-impact breakdown
    if result.per_impact:
        lines.append("## Detection by Impact Level")
        lines.append("")
        lines.append("| Impact | Total | Detected | Missed | Accuracy |")
        lines.append("|--------|------:|---------:|-------:|---------:|")
        for impact in ["HIGH", "MEDIUM", "LOW"]:
            data = result.per_impact.get(impact, {})
            total = data.get("total", 0)
            detected = data.get("detected", 0)
            missed = data.get("missed", 0)
            acc = data.get("accuracy", 0.0)
            lines.append(
                f"| {impact} | {total:,} | {detected:,} | {missed:,} | {acc:.1%} |"
            )
        lines.append("")

    # Per-source breakdown
    if result.per_source:
        lines.append("## Per-Source Breakdown")
        lines.append("")
        lines.append("| Source | Traces | Annotations | Joint Accuracy | Macro F1 |")
        lines.append("|--------|-------:|------------:|---------------:|---------:|")
        for source, data in sorted(result.per_source.items()):
            lines.append(
                f"| {source} | {data['traces']:,} | "
                f"{data['annotations']:,} | "
                f"{data['joint_accuracy']:.1%} | "
                f"{data['macro_f1']:.3f} |"
            )
        lines.append("")

    # Category mapping reference
    lines.append("## Category Mapping Reference")
    lines.append("")
    lines.append("| TRAIL Category | Pisama Detector |")
    lines.append("|----------------|-----------------|")
    for cat, pisama in sorted(TRAIL_TO_PISAMA.items()):
        lines.append(f"| {cat} | {pisama} |")
    lines.append("")
    lines.append("**Unmapped categories** (system-level):")
    for cat in sorted(TRAIL_UNMAPPED_CATEGORIES):
        lines.append(f"- {cat}")
    lines.append("")

    # Errors
    if result.errors:
        lines.append("## Errors")
        lines.append("")
        for i, error in enumerate(result.errors[:20], 1):
            lines.append(f"{i}. {error}")
        if len(result.errors) > 20:
            lines.append(f"... and {len(result.errors) - 20} more errors")
        lines.append("")

    return "\n".join(lines)
