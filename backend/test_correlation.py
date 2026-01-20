#!/usr/bin/env python3
"""Test quality-detection correlation module."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.enterprise.quality import QualityAssessor
from app.detection.quality_correlation import (
    correlate_quality_to_detections,
    get_remediation_priority,
)


def main():
    """Test correlation with a sample workflow and mock detections."""
    workflows_dir = Path(__file__).parent.parent / "n8n-workflows"

    # Load a test workflow
    workflow_path = workflows_dir / "loop" / "13-LOOP-005-simple.json"  # Worst scoring
    with open(workflow_path) as f:
        workflow = json.load(f)

    # Assess quality
    assessor = QualityAssessor(use_llm_judge=False)
    report = assessor.assess_workflow(workflow, max_suggestions=10)
    report_dict = {
        "agent_scores": [a.to_dict() for a in report.agent_scores],
        "orchestration_score": report.orchestration_score.to_dict(),
        "improvements": [i.to_dict() for i in report.improvements],
    }

    print(f"Workflow: {report.workflow_name}")
    print(f"Overall Score: {report.overall_score:.1%} ({report.overall_grade})")
    print(f"Total Issues: {report.total_issues}")
    print()

    # Mock detections that might occur with this workflow
    mock_detections = [
        {"id": "det-1", "detection_type": "infinite_loop", "confidence": 85},
        {"id": "det-2", "detection_type": "semantic_loop", "confidence": 72},
        {"id": "det-3", "detection_type": "coordination_failure", "confidence": 65},
        {"id": "det-4", "detection_type": "state_corruption", "confidence": 78},
        {"id": "det-5", "detection_type": "persona_drift", "confidence": 60},
    ]

    print("=" * 60)
    print("QUALITY-DETECTION CORRELATION TEST")
    print("=" * 60)
    print(f"\nMock detections: {len(mock_detections)}")
    for d in mock_detections:
        print(f"  • {d['detection_type']} (confidence: {d['confidence']}%)")

    # Run correlation
    result = correlate_quality_to_detections(report_dict, mock_detections)

    print(f"\n📊 Correlation Results:")
    print(f"   Total detections: {result.total_detections}")
    print(f"   Correlated detections: {result.correlated_detections}")
    print(f"   Summary: {result.summary}")

    if result.correlations:
        print(f"\n🔗 Correlations Found:")
        for corr in result.correlations:
            print(f"\n   Detection: {corr.detection_type} (ID: {corr.detection_id})")
            print(f"   Severity: {corr.severity}")
            print(f"   Explanation: {corr.explanation}")
            print(f"   Related quality issues:")
            for issue in corr.related_quality_issues:
                print(f"      • {issue['dimension']}: {issue['score']:.1%} ({issue['source']})")
                if issue['issues']:
                    for i in issue['issues'][:2]:
                        print(f"        - {i}")

    # Test remediation priority
    print("\n" + "=" * 60)
    print("REMEDIATION PRIORITY TEST")
    print("=" * 60)

    prioritized = get_remediation_priority(report_dict, mock_detections)

    print(f"\n🎯 Top 5 Prioritized Improvements (by detection impact):")
    for i, imp in enumerate(prioritized[:5], 1):
        impact = imp.get("detection_impact", 0)
        could_prevent = imp.get("could_prevent", [])
        print(f"\n   {i}. [{imp['severity'].upper()}] {imp['title']}")
        print(f"      Detection impact: {impact} (could prevent: {', '.join(could_prevent) or 'none'})")
        print(f"      {imp['description'][:100]}...")

    print("\n" + "=" * 60)
    print("Tests completed successfully!")


if __name__ == "__main__":
    main()
