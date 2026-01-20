#!/usr/bin/env python3
"""Test script for quality assessment system against n8n workflows."""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.enterprise.quality import QualityAssessor


def load_workflow(path: str) -> dict:
    """Load a workflow JSON file."""
    with open(path) as f:
        return json.load(f)


def print_report(report, verbose: bool = False):
    """Print a quality report in a readable format."""
    print(f"\n{'='*60}")
    print(f"Workflow: {report.workflow_name}")
    print(f"Overall Score: {report.overall_score:.1%} ({report.overall_grade})")
    print(f"Total Issues: {report.total_issues} | Critical: {report.critical_issues_count}")
    print(f"{'='*60}")

    # Agent scores
    if report.agent_scores:
        print(f"\n📊 Agent Quality ({len(report.agent_scores)} agents):")
        for agent in report.agent_scores:
            print(f"  • {agent.agent_name}: {agent.overall_score:.1%} ({agent.grade})")
            if verbose:
                for dim in agent.dimensions:
                    issues_str = f" ⚠️ {len(dim.issues)} issues" if dim.issues else ""
                    print(f"    - {dim.dimension}: {dim.score:.1%}{issues_str}")

    # Orchestration score
    orch = report.orchestration_score
    print(f"\n🔄 Orchestration Quality: {orch.overall_score:.1%} ({orch.grade})")
    print(f"   Pattern: {orch.detected_pattern}")
    metrics = orch.complexity_metrics
    print(f"   Nodes: {metrics.node_count} | Agents: {metrics.agent_count} | Complexity: {metrics.cyclomatic_complexity}")

    if verbose:
        for dim in orch.dimensions:
            issues_str = f" ⚠️ {len(dim.issues)} issues" if dim.issues else ""
            print(f"    - {dim.dimension}: {dim.score:.1%}{issues_str}")

    # Top improvements
    if report.improvements:
        print(f"\n💡 Top Improvements ({len(report.improvements)} total):")
        for imp in report.improvements[:5]:
            print(f"  [{imp.severity.value.upper()}] {imp.title}")
            if verbose:
                print(f"    → {imp.description}")

    # Summary
    print(f"\n📝 Summary: {report.summary}")


def main():
    """Run quality assessment on n8n workflows."""
    workflows_dir = Path(__file__).parent.parent / "n8n-workflows"

    # Test workflows
    test_files = [
        # Production workflows
        "fact-checker.json",
        "hn-analyzer.json",
        "news-aggregator.json",
        # Test scenarios
        "01-loop-injection.json",
        "state/01-STATE-001-simple.json",
        "persona/01-PERSONA-001-simple.json",
    ]

    assessor = QualityAssessor(use_llm_judge=False)

    results = []

    for filename in test_files:
        filepath = workflows_dir / filename
        if not filepath.exists():
            print(f"⚠️ Skipping {filename} - file not found")
            continue

        try:
            workflow = load_workflow(filepath)
            report = assessor.assess_workflow(workflow, max_suggestions=5)
            results.append((filename, report))
            # Show verbose for first production workflow
            verbose = filename == "fact-checker.json"
            print_report(report, verbose=verbose)
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
            import traceback
            traceback.print_exc()

    # Summary table
    print(f"\n\n{'='*60}")
    print("SUMMARY TABLE")
    print(f"{'='*60}")
    print(f"{'Workflow':<35} {'Score':>8} {'Grade':>6} {'Issues':>7}")
    print(f"{'-'*60}")
    for filename, report in results:
        name = filename[:32] + "..." if len(filename) > 35 else filename
        print(f"{name:<35} {report.overall_score:>7.1%} {report.overall_grade:>6} {report.total_issues:>7}")


if __name__ == "__main__":
    main()
