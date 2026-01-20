#!/usr/bin/env python3
"""Comprehensive test of quality assessment against all n8n workflows."""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.enterprise.quality import QualityAssessor


def load_workflow(path: str) -> dict:
    """Load a workflow JSON file."""
    with open(path) as f:
        return json.load(f)


def get_category(filepath: Path) -> str:
    """Extract category from filepath."""
    parts = filepath.parts
    # Find n8n-workflows and get next part
    for i, part in enumerate(parts):
        if part == "n8n-workflows":
            if i + 1 < len(parts) and parts[i + 1] != filepath.name:
                return parts[i + 1]
            return "production"
    return "other"


def main():
    """Run quality assessment on all n8n workflows."""
    workflows_dir = Path(__file__).parent.parent / "n8n-workflows"

    # Find all workflow files
    all_files = list(workflows_dir.rglob("*.json"))
    print(f"Found {len(all_files)} workflow files\n")

    assessor = QualityAssessor(use_llm_judge=False)

    # Results by category
    results_by_category = defaultdict(list)
    all_results = []
    errors = []

    for filepath in sorted(all_files):
        category = get_category(filepath)
        relative_path = filepath.relative_to(workflows_dir)

        try:
            workflow = load_workflow(filepath)
            report = assessor.assess_workflow(workflow, max_suggestions=5)

            result = {
                "file": str(relative_path),
                "name": report.workflow_name,
                "score": report.overall_score,
                "grade": report.overall_grade,
                "total_issues": report.total_issues,
                "critical_issues": report.critical_issues_count,
                "agents": len(report.agent_scores),
                "complexity": report.orchestration_score.complexity_metrics.cyclomatic_complexity if report.orchestration_score.complexity_metrics else 0,
                "pattern": report.orchestration_score.detected_pattern if report.orchestration_score else "unknown",
            }

            results_by_category[category].append(result)
            all_results.append(result)

        except Exception as e:
            errors.append((str(relative_path), str(e)))

    # Print results by category
    print("=" * 80)
    print("RESULTS BY CATEGORY")
    print("=" * 80)

    for category in sorted(results_by_category.keys()):
        results = results_by_category[category]
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        avg_issues = sum(r["total_issues"] for r in results) / len(results) if results else 0

        # Grade distribution
        grades = defaultdict(int)
        for r in results:
            grades[r["grade"]] += 1

        print(f"\n📁 {category.upper()} ({len(results)} workflows)")
        print(f"   Average Score: {avg_score:.1%}")
        print(f"   Average Issues: {avg_issues:.1f}")
        print(f"   Grades: {dict(grades)}")

        # Show worst 3
        worst = sorted(results, key=lambda x: x["score"])[:3]
        if worst:
            print(f"   Lowest scores:")
            for w in worst:
                print(f"      • {w['file']}: {w['score']:.1%} ({w['grade']}) - {w['total_issues']} issues")

    # Overall summary
    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)

    if all_results:
        overall_avg = sum(r["score"] for r in all_results) / len(all_results)
        total_issues = sum(r["total_issues"] for r in all_results)
        critical_issues = sum(r["critical_issues"] for r in all_results)

        # Overall grade distribution
        grade_dist = defaultdict(int)
        for r in all_results:
            grade_dist[r["grade"]] += 1

        print(f"\nTotal Workflows Assessed: {len(all_results)}")
        print(f"Overall Average Score: {overall_avg:.1%}")
        print(f"Total Issues Found: {total_issues}")
        print(f"Critical Issues: {critical_issues}")
        print(f"\nGrade Distribution:")
        for grade in ["A", "B+", "B", "C+", "C", "D", "F"]:
            count = grade_dist.get(grade, 0)
            bar = "█" * (count // 2) + "▌" * (count % 2)
            print(f"   {grade:3}: {bar} ({count})")

        # Pattern distribution
        pattern_dist = defaultdict(int)
        for r in all_results:
            pattern_dist[r["pattern"]] += 1
        print(f"\nDetected Patterns:")
        for pattern, count in sorted(pattern_dist.items(), key=lambda x: -x[1]):
            print(f"   {pattern}: {count}")

        # Top 10 best workflows
        print(f"\n🏆 Top 10 Best Workflows:")
        best = sorted(all_results, key=lambda x: (-x["score"], x["total_issues"]))[:10]
        for i, b in enumerate(best, 1):
            print(f"   {i:2}. {b['file']}: {b['score']:.1%} ({b['grade']}) - {b['total_issues']} issues")

        # Top 10 worst workflows
        print(f"\n⚠️  Top 10 Workflows Needing Improvement:")
        worst = sorted(all_results, key=lambda x: (x["score"], -x["total_issues"]))[:10]
        for i, w in enumerate(worst, 1):
            print(f"   {i:2}. {w['file']}: {w['score']:.1%} ({w['grade']}) - {w['total_issues']} issues")

    # Errors
    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        for filepath, error in errors:
            print(f"   • {filepath}: {error}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
