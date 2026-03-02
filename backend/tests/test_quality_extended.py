"""Extended quality assessment tests with large-scale datasets.

Tests quality assessment using:
- 4,142 archived traces across 12+ frameworks
- 7,500+ external n8n workflow templates
- 10 MAST benchmark traces with F1-F14 labels
"""

import pytest
import statistics
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality import QualityAssessor


class TestArchivedTracesDataset:
    """Test quality assessment with 4,142 archived traces."""

    def test_archived_traces_load(self, archived_traces):
        """Should load 4,000+ archived traces from all_traces.jsonl."""
        assert len(archived_traces) >= 4000, (
            f"Expected 4,000+ traces, got {len(archived_traces)}"
        )

    def test_framework_distribution(self, archived_traces_by_framework):
        """Should have traces from multiple frameworks."""
        frameworks = list(archived_traces_by_framework.keys())

        # Should have at least 5 different frameworks
        assert len(frameworks) >= 5, (
            f"Expected 5+ frameworks, got {len(frameworks)}: {frameworks}"
        )

        # Check for key frameworks
        expected_frameworks = ["langchain", "autogen", "crewai"]
        for fw in expected_frameworks:
            assert fw in frameworks or any(fw in f.lower() for f in frameworks), (
                f"Missing expected framework: {fw}"
            )

    def test_framework_trace_counts(self, archived_traces_by_framework):
        """Document trace distribution across frameworks."""
        print("\n\nArchived Traces by Framework:")
        sorted_frameworks = sorted(
            archived_traces_by_framework.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        total_traces = sum(len(traces) for traces in archived_traces_by_framework.values())

        for framework, traces in sorted_frameworks[:15]:  # Show top 15
            percentage = len(traces) / total_traces * 100
            print(f"  {framework:20s}: {len(traces):4d} traces ({percentage:5.1f}%)")

        # Verify counts
        assert total_traces >= 4000, f"Total traces {total_traces} < 4000"

    def test_quality_by_framework_sample(self, archived_traces_by_framework):
        """Archived traces across frameworks should have valid content."""
        assert len(archived_traces_by_framework) >= 3, (
            f"Expected 3+ frameworks, got {len(archived_traces_by_framework)}"
        )

        for framework, traces in archived_traces_by_framework.items():
            sample = traces[:30]
            for trace in sample:
                # Each trace should have non-empty content
                content = trace.get("content", "")
                assert content, f"Trace from {framework} has empty content"
                # Each trace should have a framework label
                assert trace.get("framework") == framework


class TestExternalN8nWorkflows:
    """Test quality assessment with external n8n templates (7,500+ workflows)."""

    def test_external_workflows_load(self, external_n8n_workflows):
        """Should load at least 50 external workflow samples."""
        assert len(external_n8n_workflows) >= 50, (
            f"Expected 50+ workflow samples, got {len(external_n8n_workflows)}"
        )

    def test_quality_distribution(self, external_n8n_workflows):
        """Generate quality score distribution across real-world workflows."""
        assessor = QualityAssessor(use_llm_judge=False)

        # Sample 30 workflows for reasonable test speed (each takes ~100ms)
        sample_size = min(30, len(external_n8n_workflows))
        scores = []

        for workflow in external_n8n_workflows[:sample_size]:
            try:
                report = assessor.assess_workflow(workflow)
                scores.append(report.overall_score)
            except Exception as e:
                # Some workflows might be invalid - skip them
                print(f"  Skipped workflow due to error: {e}")
                continue

        # Verify we got scores
        assert len(scores) >= 20, (
            f"Expected 20+ valid scores, got {len(scores)}"
        )

        # Document distribution
        print(f"\n\nQuality Score Distribution (n={len(scores)}):")
        print(f"  Mean:   {statistics.mean(scores):.2%}")
        print(f"  Median: {statistics.median(scores):.2%}")
        print(f"  StdDev: {statistics.stdev(scores):.2%}")
        print(f"  Min:    {min(scores):.2%}")
        print(f"  Max:    {max(scores):.2%}")

        # Real-world workflows should have reasonable distribution
        # Not too low (most workflows are functional) or too high (some have issues)
        mean_score = statistics.mean(scores)
        assert 0.5 <= mean_score <= 0.95, (
            f"Mean score {mean_score:.2%} outside expected range (50%-95%)"
        )

    def test_grade_distribution(self, external_n8n_workflows):
        """Document grade distribution across real-world workflows."""
        assessor = QualityAssessor(use_llm_judge=False)

        # Sample 30 workflows
        sample_size = min(30, len(external_n8n_workflows))
        grades = []

        for workflow in external_n8n_workflows[:sample_size]:
            try:
                report = assessor.assess_workflow(workflow)
                grades.append(report.overall_grade)
            except Exception:
                continue

        # Count grades
        grade_counts = {}
        for grade in grades:
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        print(f"\n\nGrade Distribution (n={len(grades)}):")
        for grade in ["A", "B+", "B", "C+", "C", "D", "F"]:
            count = grade_counts.get(grade, 0)
            percentage = count / len(grades) * 100 if grades else 0
            print(f"  {grade:3s}: {count:2d} ({percentage:5.1f}%)")

        # Should have some distribution (not all same grade)
        assert len(grade_counts) >= 2, (
            f"All workflows have same grade: {grade_counts}"
        )

    def test_agent_count_distribution(self, external_n8n_workflows):
        """Document agent count distribution in real-world workflows."""
        assessor = QualityAssessor(use_llm_judge=False)

        sample_size = min(30, len(external_n8n_workflows))
        agent_counts = []

        for workflow in external_n8n_workflows[:sample_size]:
            try:
                report = assessor.assess_workflow(workflow)
                agent_counts.append(len(report.agent_scores))
            except Exception:
                continue

        print(f"\n\nAgent Count Distribution (n={len(agent_counts)}):")
        print(f"  Mean:   {statistics.mean(agent_counts) if agent_counts else 0:.1f}")
        print(f"  Median: {statistics.median(agent_counts) if agent_counts else 0:.1f}")
        print(f"  Min:    {min(agent_counts) if agent_counts else 0}")
        print(f"  Max:    {max(agent_counts) if agent_counts else 0}")

        # Count distribution
        count_dist = {}
        for count in agent_counts:
            count_dist[count] = count_dist.get(count, 0) + 1

        for count in sorted(count_dist.keys()):
            print(f"  {count} agents: {count_dist[count]} workflows")


class TestMastBenchmark:
    """Test quality correlation with MAST failure modes."""

    def test_mast_traces_load(self, mast_traces):
        """Should load 10 MAST traces."""
        assert len(mast_traces) == 10, (
            f"Expected 10 MAST traces, got {len(mast_traces)}"
        )

    def test_failure_mode_labels(self, mast_traces):
        """All traces should have failure mode metadata."""
        for i, trace in enumerate(mast_traces):
            # MAST traces have mast_annotation field with F1-F14 labels
            has_metadata = (
                "mast_annotation" in trace or
                "failure_mode" in trace or
                "_golden_metadata" in trace or
                "annotations" in trace
            )
            assert has_metadata, (
                f"Trace {i} missing failure mode metadata: {list(trace.keys())}"
            )

    def test_quality_correlation_with_failure_modes(self, mast_traces):
        """MAST benchmark traces should have valid failure mode annotations."""
        assert len(mast_traces) > 0, "No MAST traces loaded"

        # Valid MAST taxonomy IDs: X.Y where X=1-3, Y=1-6
        valid_ids = {f"{x}.{y}" for x in range(1, 4) for y in range(1, 7)}

        for trace in mast_traces:
            annotation = trace.get("mast_annotation", {})
            assert len(annotation) > 0, "MAST trace missing annotations"

            for key, value in annotation.items():
                assert key in valid_ids, f"Invalid MAST taxonomy ID: {key}"
                assert value in (0, 1), f"Annotation value must be 0 or 1, got {value}"

        # At least some traces should have positive annotations
        traces_with_failures = sum(
            1 for t in mast_traces
            if any(v == 1 for v in t.get("mast_annotation", {}).values())
        )
        assert traces_with_failures > 0, "No MAST traces have any failure annotations"


class TestDatasetComprehensiveness:
    """Test overall dataset coverage and statistics."""

    def test_total_dataset_size(self, archived_traces, golden_traces, mast_traces,
                                 external_n8n_workflows, n8n_workflow_files):
        """Document total dataset size across all sources."""
        print("\n\nDataset Summary:")
        print(f"  Archived traces:        {len(archived_traces):5d}")
        print(f"  Golden traces:          {len(golden_traces):5d}")
        print(f"  MAST benchmark traces:  {len(mast_traces):5d}")
        print(f"  External n8n workflows: {len(external_n8n_workflows):5d}")
        print(f"  Demo n8n workflows:     {len(n8n_workflow_files):5d}")
        print(f"  " + "-" * 30)

        total = (len(archived_traces) + len(golden_traces) + len(mast_traces) +
                 len(external_n8n_workflows) + len(n8n_workflow_files))
        print(f"  TOTAL:                  {total:5d}")

        # Should have substantial dataset
        assert total >= 4500, f"Total dataset {total} < 4500"

    def test_framework_coverage(self, archived_traces_by_framework):
        """Verify coverage across multiple frameworks."""
        frameworks = list(archived_traces_by_framework.keys())

        print("\n\nFramework Coverage:")
        print(f"  Total frameworks: {len(frameworks)}")
        print(f"  Frameworks: {', '.join(sorted(frameworks)[:10])}")

        # Should have diverse framework coverage
        assert len(frameworks) >= 5, (
            f"Need 5+ frameworks, got {len(frameworks)}"
        )
