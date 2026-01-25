#!/usr/bin/env python3
"""
Run Quality Assessment on Sample Workflow

This script demonstrates the QualityAssessor by running it on a real n8n workflow
and displaying the formatted results.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.enterprise.quality import QualityAssessor


def load_workflow(filename: str) -> dict:
    """Load a workflow from the archived demo-agent directory."""
    base_path = Path(__file__).parent.parent / "_archived" / "demo-agent" / "n8n-workflows"
    filepath = base_path / filename

    if not filepath.exists():
        raise FileNotFoundError(f"Workflow file not found: {filepath}")

    with open(filepath) as f:
        return json.load(f)


def format_dimensions(dimensions: list) -> str:
    """Format dimension scores for display."""
    lines = []
    for dim_score in dimensions:
        score_bar = "█" * int(dim_score.score * 20) + "░" * (20 - int(dim_score.score * 20))
        # Handle both string and enum dimension
        dim_name = dim_score.dimension if isinstance(dim_score.dimension, str) else dim_score.dimension.value
        lines.append(f"    • {dim_name:<25} {score_bar} {dim_score.score:.0%}")
        if dim_score.issues:
            for issue in dim_score.issues[:2]:  # Show first 2 issues
                lines.append(f"      └─ Issue: {issue}")
    return "\n".join(lines)


def format_improvements(improvements: list, max_display: int = 5) -> str:
    """Format improvement suggestions for display."""
    if not improvements:
        return "  No improvements suggested."

    lines = []
    for i, improvement in enumerate(improvements[:max_display], 1):
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }.get(improvement.severity.value, "⚪")

        effort_text = {
            "minimal": "Quick fix",
            "low": "Easy",
            "medium": "Moderate",
            "high": "Complex"
        }.get(improvement.effort.value, "Unknown")

        lines.append(f"\n  {i}. {severity_emoji} {improvement.title}")
        lines.append(f"     Problem: {improvement.description}")
        if improvement.suggested_change:
            lines.append(f"     Fix ({effort_text}): {improvement.suggested_change}")
        lines.append(f"     Category: {improvement.category}")
        if improvement.estimated_impact:
            lines.append(f"     Impact: {improvement.estimated_impact}")

    if len(improvements) > max_display:
        lines.append(f"\n  ... and {len(improvements) - max_display} more suggestions")

    return "\n".join(lines)


def display_report(report):
    """Display the quality report in a formatted way."""
    print("\n" + "="*80)
    print(f"QUALITY ASSESSMENT REPORT")
    print("="*80)
    print(f"\nWorkflow: {report.workflow_name}")
    print(f"ID: {report.workflow_id}")
    print(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    # Overall Score
    grade_emoji = {
        "A": "🌟",
        "B": "✅",
        "C": "⚠️",
        "D": "❌",
        "F": "💀"
    }.get(report.overall_grade, "❓")

    print(f"\n{'─'*80}")
    print(f"OVERALL SCORE: {grade_emoji} {report.overall_grade} ({report.overall_score:.0%})")
    print(f"{'─'*80}")

    # Summary
    print(f"\n{report.summary}")

    # Agent Scores
    if report.agent_scores:
        print(f"\n{'─'*80}")
        print(f"AGENT QUALITY ({len(report.agent_scores)} agents, 60% weight)")
        print(f"{'─'*80}")

        for i, agent in enumerate(report.agent_scores, 1):
            avg_score = sum(d.score for d in agent.dimensions) / len(agent.dimensions)
            print(f"\n  Agent #{i}: {agent.agent_name}")
            print(f"  Overall: {agent.overall_score:.0%} (Grade: {agent.grade})")
            print(f"\n{format_dimensions(agent.dimensions)}")

    # Orchestration Score
    print(f"\n{'─'*80}")
    print(f"ORCHESTRATION QUALITY (40% weight)")
    print(f"{'─'*80}")
    print(f"\n  Overall: {report.orchestration_score.overall_score:.0%} (Grade: {report.orchestration_score.grade})")
    print(f"  Pattern: {report.orchestration_score.detected_pattern}")
    print(f"\n{format_dimensions(report.orchestration_score.dimensions)}")

    # Complexity Metrics
    metrics = report.orchestration_score.complexity_metrics
    print(f"\n  Complexity Metrics:")
    print(f"    • Total nodes: {metrics.node_count}")
    print(f"    • Agent nodes: {metrics.agent_count}")
    print(f"    • Max depth: {metrics.max_depth}")
    print(f"    • Cyclomatic complexity: {metrics.cyclomatic_complexity}")
    print(f"    • AI node ratio: {metrics.ai_node_ratio:.2%}")

    # Improvements
    if report.improvements:
        print(f"\n{'─'*80}")
        print(f"IMPROVEMENT SUGGESTIONS ({len(report.improvements)} total)")
        print(f"{'─'*80}")
        print(format_improvements(report.improvements))

    # Critical Issues
    if report.critical_issues_count > 0:
        print(f"\n{'─'*80}")
        print(f"⚠️  CRITICAL ISSUES: {report.critical_issues_count}")
        print(f"{'─'*80}")

    print("\n" + "="*80 + "\n")


def main():
    """Main entry point."""
    print("\n🔍 Quality Assessment Demo")
    print("─" * 40)

    # Choose workflow to assess
    workflow_files = [
        "research-assistant-normal.json",
        "research-loop-buggy.json",
        "research-corruption.json",
        "research-drift.json"
    ]

    print("\nAvailable workflows:")
    for i, wf in enumerate(workflow_files, 1):
        print(f"  {i}. {wf}")

    # For demo, use the first one
    selected_file = workflow_files[0]
    print(f"\nAssessing: {selected_file}")

    # Load workflow
    print("Loading workflow...")
    workflow = load_workflow(selected_file)

    # Create assessor (without LLM for faster demo)
    print("Initializing quality assessor...")
    assessor = QualityAssessor(use_llm_judge=False)

    # Run assessment
    print("Running quality assessment...\n")
    report = assessor.assess_workflow(
        workflow=workflow,
        execution_history=None,
        max_suggestions=10
    )

    # Display results
    display_report(report)

    # Save report to JSON
    output_path = Path(__file__).parent / "quality_report.json"
    with open(output_path, 'w') as f:
        json.dump({
            "workflow_id": report.workflow_id,
            "workflow_name": report.workflow_name,
            "overall_score": report.overall_score,
            "overall_grade": report.overall_grade,
            "agent_scores": [
                {
                    "agent_name": a.agent_name,
                    "overall_score": a.overall_score,
                    "grade": a.grade,
                    "dimensions": {(d.dimension if isinstance(d.dimension, str) else d.dimension.value): d.score for d in a.dimensions}
                }
                for a in report.agent_scores
            ],
            "orchestration_score": {
                "overall_score": report.orchestration_score.overall_score,
                "grade": report.orchestration_score.grade,
                "pattern": report.orchestration_score.detected_pattern,
                "dimensions": {(d.dimension if isinstance(d.dimension, str) else d.dimension.value): d.score for d in report.orchestration_score.dimensions}
            },
            "improvements": [
                {
                    "title": i.title,
                    "severity": i.severity.value,
                    "effort": i.effort.value,
                    "category": i.category,
                    "estimated_impact": i.estimated_impact
                }
                for i in report.improvements
            ],
            "summary": report.summary,
            "generated_at": report.generated_at.isoformat()
        }, f, indent=2)

    print(f"📄 Full report saved to: {output_path}")


if __name__ == "__main__":
    main()
