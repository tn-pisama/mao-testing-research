"""Who&When Benchmark Report Generator.

Generates Markdown and JSON reports from Who&When benchmark results,
including comparison against the paper's baselines.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.benchmark.whowhen_loader import PAPER_BASELINES, WHOWHEN_DETECTORS
from app.benchmark.whowhen_runner import WhoWhenBenchmarkResult

logger = logging.getLogger(__name__)


def generate_report(
    result: WhoWhenBenchmarkResult,
    format: str = "markdown",
) -> str:
    """Generate a Who&When benchmark report.

    Args:
        result: WhoWhenBenchmarkResult from WhoWhenBenchmarkRunner.run().
        format: "markdown" or "json".

    Returns:
        Report string.
    """
    if format == "json":
        return _generate_json(result)
    return _generate_markdown(result)


def _generate_json(result: WhoWhenBenchmarkResult) -> str:
    """Generate JSON report."""
    report: Dict[str, Any] = {
        "benchmark": "Who&When (ICML 2025)",
        "result": result.to_dict(),
        "per_detector_stats": result.per_detector_stats,
        "per_source_stats": result.per_source_stats,
        "paper_baselines": PAPER_BASELINES,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(report, indent=2)


def _generate_markdown(result: WhoWhenBenchmarkResult) -> str:
    """Generate Markdown report."""
    lines: list[str] = []

    # Header
    lines.append("# Who&When Benchmark Report")
    lines.append("")
    lines.append(
        "**Benchmark:** Who&When (ICML 2025 Spotlight) - "
        "Multi-Agent Failure Attribution"
    )
    lines.append(
        f"**Generated:** "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    lines.append(f"**Run ID:** {result.run_id}")
    lines.append(f"**Duration:** {result.duration_seconds:.1f} seconds")
    lines.append("")

    # Executive summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Cases | {result.total_cases:,} |")
    lines.append(f"| Processed | {result.processed_cases:,} |")
    lines.append(f"| Skipped (no detection) | {result.skipped_cases:,} |")
    lines.append(
        f"| **Agent Accuracy** | **{result.agent_accuracy:.1%}** |"
    )
    lines.append(
        f"| **Step Accuracy** | **{result.step_accuracy:.1%}** |"
    )
    if result.errors:
        lines.append(f"| Errors | {len(result.errors):,} |")
    lines.append("")

    # Baseline comparison
    lines.append("## Comparison with Paper Baselines")
    lines.append("")
    lines.append(
        "The Who&When paper evaluates 3 methods across multiple LLMs. "
        "Pisama uses rule-based multi-detector analysis (closest to "
        "the all-at-once approach)."
    )
    lines.append("")
    lines.append(
        "| Method | Agent Acc | Step Acc |"
    )
    lines.append("|--------|----------:|---------:|")

    # Pisama result first
    lines.append(
        f"| **Pisama (rule-based)** | "
        f"**{result.agent_accuracy:.1%}** | "
        f"**{result.step_accuracy:.1%}** |"
    )

    # Paper baselines
    baseline_labels = {
        "o1_all_at_once": "o1 all-at-once",
        "o1_step_by_step": "o1 step-by-step",
        "o1_binary_search": "o1 binary-search",
        "gpt4o_all_at_once": "GPT-4o all-at-once",
        "claude_sonnet_all_at_once": "Claude Sonnet all-at-once",
    }

    for key, label in baseline_labels.items():
        baseline = PAPER_BASELINES.get(key, {})
        agent_acc = baseline.get("agent_accuracy", 0)
        step_acc = baseline.get("step_accuracy", 0)
        lines.append(f"| {label} | {agent_acc:.1%} | {step_acc:.1%} |")

    lines.append("")

    # Delta analysis
    best_baseline = PAPER_BASELINES["o1_all_at_once"]
    agent_delta = result.agent_accuracy - best_baseline["agent_accuracy"]
    step_delta = result.step_accuracy - best_baseline["step_accuracy"]

    lines.append("### vs Best Baseline (o1 all-at-once)")
    lines.append("")
    if agent_delta >= 0:
        lines.append(f"- Agent accuracy: +{agent_delta:.1%} above baseline")
    else:
        lines.append(f"- Agent accuracy: {agent_delta:.1%} below baseline")
    if step_delta >= 0:
        lines.append(f"- Step accuracy: +{step_delta:.1%} above baseline")
    else:
        lines.append(f"- Step accuracy: {step_delta:.1%} below baseline")
    lines.append("")

    # Per-detector breakdown
    if result.per_detector_stats:
        lines.append("## Per-Detector Contribution")
        lines.append("")
        lines.append(
            "| Detector | Cases | Agent Acc | Step Acc | Avg Confidence |"
        )
        lines.append(
            "|----------|------:|----------:|---------:|---------------:|"
        )

        for det, stats in result.per_detector_stats.items():
            lines.append(
                f"| {det} | {stats['count']:,} | "
                f"{stats['agent_accuracy']:.1%} | "
                f"{stats['step_accuracy']:.1%} | "
                f"{stats['avg_confidence']:.3f} |"
            )
        lines.append("")

    # Per-source breakdown
    if result.per_source_stats:
        lines.append("## Per-Source Breakdown")
        lines.append("")
        lines.append(
            "| Source | Cases | Agent Acc | Step Acc |"
        )
        lines.append(
            "|--------|------:|----------:|---------:|"
        )

        for source, stats in sorted(result.per_source_stats.items()):
            lines.append(
                f"| {source} | {stats['total']:,} | "
                f"{stats['agent_accuracy']:.1%} | "
                f"{stats['step_accuracy']:.1%} |"
            )
        lines.append("")

    # Methodology note
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "Pisama runs the following detectors on each multi-agent "
        "conversation:"
    )
    lines.append("")
    for det in WHOWHEN_DETECTORS:
        lines.append(f"- **{det}**")
    lines.append("")
    lines.append(
        "For each case, the detector with the highest-confidence "
        "evidence determines the predicted `mistake_agent` and "
        "`mistake_step`. When no detector fires, the most active "
        "non-human agent is used as a frequency-based fallback."
    )
    lines.append("")
    lines.append(
        "This approach is closest to the paper's **all-at-once** method "
        "(analyze the full conversation trace), but uses rule-based "
        "detectors instead of prompting an LLM."
    )
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
