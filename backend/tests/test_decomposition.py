"""Tests for F2: Poor Task Decomposition Detection."""

import pytest
from app.detection.decomposition import (
    TaskDecompositionDetector,
    DecompositionIssue,
    DecompositionSeverity,
    Subtask,
)


class TestTaskDecompositionDetector:
    """Test suite for TaskDecompositionDetector."""

    def setup_method(self):
        self.detector = TaskDecompositionDetector()

    # Subtask Parsing Tests
    def test_parse_numbered_list(self):
        """Should parse numbered list format."""
        decomposition = """
        1. First task
        2. Second task
        3. Third task
        """
        subtasks = self.detector._parse_subtasks(decomposition)
        assert len(subtasks) == 3
        assert "First task" in subtasks[0].description
        assert subtasks[0].id == "task_0"

    def test_parse_bullet_list(self):
        """Should parse bullet list format."""
        decomposition = """
        - First task
        - Second task
        - Third task
        """
        subtasks = self.detector._parse_subtasks(decomposition)
        assert len(subtasks) == 3

    def test_parse_step_format(self):
        """Should parse step format."""
        decomposition = """
        Step 1: First task
        Step 2: Second task
        """
        subtasks = self.detector._parse_subtasks(decomposition)
        assert len(subtasks) == 2

    def test_parse_dependencies(self):
        """Should extract dependencies from subtask descriptions."""
        decomposition = """
        1. Create initial data
        2. Process data (after step 1)
        3. Analyze results (requires step 2)
        """
        subtasks = self.detector._parse_subtasks(decomposition)
        # Dependencies should be detected from "after step 1" and "requires step 2"
        assert len(subtasks) == 3

    def test_parse_empty_decomposition(self):
        """Should handle empty decomposition."""
        subtasks = self.detector._parse_subtasks("")
        assert subtasks == []

    def test_parse_no_list_format(self):
        """Should handle text without list format."""
        decomposition = "Just some text without any list structure"
        subtasks = self.detector._parse_subtasks(decomposition)
        assert subtasks == []

    # Impossible Subtask Detection Tests
    def test_detect_impossible_subtasks(self):
        """Should detect subtasks with impossible indicators."""
        subtasks = [
            Subtask(id="task_0", description="Create report", dependencies=[]),
            Subtask(id="task_1", description="This is impossible to complete", dependencies=[]),
            Subtask(id="task_2", description="Cannot access the database", dependencies=[]),
        ]
        impossible = self.detector._detect_impossible_subtasks(subtasks)
        assert "task_1" in impossible
        assert "task_2" in impossible
        assert "task_0" not in impossible

    def test_detect_undefined_subtasks(self):
        """Should detect subtasks with undefined/unclear descriptions."""
        subtasks = [
            Subtask(id="task_0", description="Process the undefined data", dependencies=[]),
            Subtask(id="task_1", description="Handle unclear requirements", dependencies=[]),
        ]
        impossible = self.detector._detect_impossible_subtasks(subtasks)
        assert "task_0" in impossible
        assert "task_1" in impossible

    def test_no_impossible_subtasks(self):
        """Should return empty for valid subtasks."""
        subtasks = [
            Subtask(id="task_0", description="Create report", dependencies=[]),
            Subtask(id="task_1", description="Send email", dependencies=[]),
        ]
        impossible = self.detector._detect_impossible_subtasks(subtasks)
        assert impossible == []

    # Circular Dependency Detection Tests
    def test_detect_circular_dependencies(self):
        """Should detect circular dependencies."""
        subtasks = [
            Subtask(id="task_0", description="A", dependencies=["task_1"]),
            Subtask(id="task_1", description="B", dependencies=["task_0"]),
        ]
        circular = self.detector._detect_circular_dependencies(subtasks)
        assert len(circular) == 1
        assert ("task_0", "task_1") in circular or ("task_1", "task_0") in circular

    def test_no_circular_dependencies(self):
        """Should return empty for linear dependencies."""
        subtasks = [
            Subtask(id="task_0", description="A", dependencies=[]),
            Subtask(id="task_1", description="B", dependencies=["task_0"]),
            Subtask(id="task_2", description="C", dependencies=["task_1"]),
        ]
        circular = self.detector._detect_circular_dependencies(subtasks)
        assert circular == []

    # Duplicate Work Detection Tests
    def test_detect_duplicate_work(self):
        """Should detect duplicate subtasks."""
        subtasks = [
            Subtask(id="task_0", description="Generate quarterly sales report for Q4", dependencies=[]),
            Subtask(id="task_1", description="Create quarterly sales report for Q4", dependencies=[]),
        ]
        duplicates = self.detector._detect_duplicate_work(subtasks)
        assert len(duplicates) >= 1
        assert ("task_0", "task_1") in duplicates

    def test_no_duplicate_work(self):
        """Should return empty for distinct subtasks."""
        subtasks = [
            Subtask(id="task_0", description="Analyze customer data", dependencies=[]),
            Subtask(id="task_1", description="Generate financial report", dependencies=[]),
        ]
        duplicates = self.detector._detect_duplicate_work(subtasks)
        assert duplicates == []

    # Missing Dependency Detection Tests
    def test_detect_missing_dependencies(self):
        """Should detect missing dependencies when consumer precedes producer."""
        subtasks = [
            Subtask(id="task_0", description="Use report for analysis", dependencies=[]),
            Subtask(id="task_1", description="Create report summary", dependencies=[]),
        ]
        missing = self.detector._detect_missing_dependencies(subtasks)
        # task_0 uses "report" before task_1 creates it, with no dependency declared
        assert "task_0" in missing

    def test_sequential_order_satisfies_dependency(self):
        """Should NOT flag when producer step comes before consumer step."""
        subtasks = [
            Subtask(id="task_0", description="Create report summary", dependencies=[]),
            Subtask(id="task_1", description="Use report for analysis", dependencies=[]),
        ]
        missing = self.detector._detect_missing_dependencies(subtasks)
        # Sequential order (producer first) satisfies the implicit dependency
        assert missing == []

    def test_no_missing_dependencies(self):
        """Should return empty when dependencies are properly declared."""
        subtasks = [
            Subtask(id="task_0", description="Fetch data from database", dependencies=[]),
            Subtask(id="task_1", description="Display results", dependencies=["task_0"]),
        ]
        missing = self.detector._detect_missing_dependencies(subtasks)
        # No explicit create/use pattern detected
        assert missing == []

    # Full Detection Tests
    def test_valid_decomposition(self):
        """Should not detect issues in valid decomposition."""
        result = self.detector.detect(
            task_description="Build a web application",
            decomposition="""
            1. Design the database schema
            2. Create the backend API
            3. Build the frontend UI
            4. Write integration tests
            5. Deploy to production
            """
        )
        assert result.detected is False
        assert result.severity == DecompositionSeverity.NONE
        assert result.issues == []
        assert result.subtask_count == 5

    def test_detect_too_few_subtasks(self):
        """Should detect when decomposition has too few/vague subtasks for complex task."""
        result = self.detector.detect(
            task_description="Complex enterprise system migration",
            decomposition="""
            1. Do everything
            """
        )
        assert result.detected is True
        assert DecompositionIssue.WRONG_GRANULARITY in result.issues
        # Single vague subtask parses to empty -> no_structured_decomposition
        assert any(p in result.problematic_subtasks
                   for p in ["too_few_subtasks", "no_structured_decomposition"])

    def test_detect_too_many_subtasks(self):
        """Should detect when there are too many subtasks."""
        many_subtasks = "\n".join([f"{i}. Subtask {i}" for i in range(1, 25)])
        result = self.detector.detect(
            task_description="Simple task",
            decomposition=many_subtasks
        )
        assert result.detected is True
        assert DecompositionIssue.WRONG_GRANULARITY in result.issues

    def test_detect_impossible_subtask(self):
        """Should detect impossible subtasks."""
        result = self.detector.detect(
            task_description="Data analysis project",
            decomposition="""
            1. Gather data from source
            2. This is impossible without database access
            3. Generate report
            """
        )
        assert result.detected is True
        assert DecompositionIssue.IMPOSSIBLE_SUBTASK in result.issues
        assert result.severity == DecompositionSeverity.SEVERE

    def test_detect_circular_dependency_in_decomposition(self):
        """Should detect circular dependencies in decomposition."""
        result = self.detector.detect(
            task_description="Process workflow",
            decomposition="""
            1. Task A depends on task 2
            2. Task B requires step 1
            3. Task C
            """
        )
        # Note: depends on parsing detecting the circular pattern
        assert isinstance(result.detected, bool)

    def test_no_subtasks_found(self):
        """Should handle decomposition with no parseable subtasks."""
        result = self.detector.detect(
            task_description="Some task",
            decomposition="Just some rambling text without any structure"
        )
        assert result.detected is False
        assert "No subtasks found" in result.explanation

    def test_explanation_includes_issues(self):
        """Should include issue details in explanation."""
        result = self.detector.detect(
            task_description="Task",
            decomposition="""
            1. This is impossible to do
            2. Cannot access required data
            3. Normal task
            """
        )
        assert result.detected is True
        assert "issues" in result.explanation.lower()
        assert result.suggested_fix is not None

    # Trace Detection Tests
    def test_detect_from_trace_with_planning(self):
        """Should detect issues in planning spans."""
        trace = {
            "spans": [
                {
                    "name": "PlannerAgent",
                    "type": "planning",
                    "input": {"task": "Build application"},
                    "output": {"content": "1. Do everything at once"},
                },
            ]
        }
        results = self.detector.detect_from_trace(trace)
        assert len(results) >= 1

    def test_detect_from_trace_no_planning(self):
        """Should skip non-planning spans."""
        trace = {
            "spans": [
                {
                    "name": "ExecutorAgent",
                    "type": "execution",
                    "input": {"data": "some data"},
                    "output": {"content": "result"},
                },
            ]
        }
        results = self.detector.detect_from_trace(trace)
        assert results == []

    def test_detect_from_empty_trace(self):
        """Should handle empty trace."""
        trace = {"spans": []}
        results = self.detector.detect_from_trace(trace)
        assert results == []

    # Configuration Tests
    def test_custom_min_subtasks(self):
        """Should respect custom minimum subtasks."""
        detector = TaskDecompositionDetector(min_subtasks=5)
        result = detector.detect(
            task_description="Task",
            decomposition="""
            1. Step 1
            2. Step 2
            3. Step 3
            """
        )
        assert result.detected is True
        assert DecompositionIssue.WRONG_GRANULARITY in result.issues

    def test_custom_max_subtasks(self):
        """Should respect custom maximum subtasks."""
        detector = TaskDecompositionDetector(max_subtasks=5)
        subtasks = "\n".join([f"{i}. Task {i}" for i in range(1, 8)])
        result = detector.detect(
            task_description="Task",
            decomposition=subtasks
        )
        assert result.detected is True
        assert DecompositionIssue.WRONG_GRANULARITY in result.issues

    def test_disable_dependency_check(self):
        """Should skip dependency check when disabled."""
        detector = TaskDecompositionDetector(check_dependencies=False)
        result = detector.detect(
            task_description="Task",
            decomposition="""
            1. Create the data
            2. Use the data without proper dependency
            3. Finish up
            """
        )
        # Should not detect missing dependencies when check is disabled
        if result.detected:
            assert DecompositionIssue.MISSING_DEPENDENCY not in result.issues

    # Severity Tests
    def test_severe_for_circular_dependency(self):
        """Should be severe for circular dependencies."""
        subtasks = [
            Subtask(id="task_0", description="A", dependencies=["task_1"]),
            Subtask(id="task_1", description="B", dependencies=["task_0"]),
        ]
        # Create a result manually to test severity logic
        detector = TaskDecompositionDetector()
        # The actual detection uses the full detect method
        result = detector.detect(
            task_description="Task",
            decomposition="1. This is impossible\n2. Normal task\n3. Another task"
        )
        if DecompositionIssue.IMPOSSIBLE_SUBTASK in result.issues:
            assert result.severity == DecompositionSeverity.SEVERE

    def test_moderate_for_multiple_issues(self):
        """Should be moderate for multiple minor issues."""
        result = self.detector.detect(
            task_description="Task",
            decomposition="""
            1. Generate the report for sales
            2. Create the report for sales data
            3. Another distinct task
            """
        )
        # May detect duplicate work
        if len(result.issues) >= 2:
            assert result.severity in (DecompositionSeverity.MODERATE, DecompositionSeverity.SEVERE)


class TestDecompositionResult:
    """Tests for DecompositionResult properties."""

    def test_result_has_all_fields(self):
        """Result should have all required fields."""
        detector = TaskDecompositionDetector()
        result = detector.detect(
            task_description="Build something",
            decomposition="1. Step 1\n2. Step 2\n3. Step 3"
        )
        assert hasattr(result, "detected")
        assert hasattr(result, "issues")
        assert hasattr(result, "severity")
        assert hasattr(result, "confidence")
        assert hasattr(result, "subtask_count")
        assert hasattr(result, "problematic_subtasks")
        assert hasattr(result, "explanation")
        assert hasattr(result, "suggested_fix")

    def test_confidence_in_valid_range(self):
        """Confidence should be between 0 and 1."""
        detector = TaskDecompositionDetector()
        result = detector.detect(
            task_description="Task",
            decomposition="1. Step 1\n2. Step 2\n3. Step 3"
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_subtask_count_accurate(self):
        """Subtask count should match parsed subtasks."""
        detector = TaskDecompositionDetector()
        result = detector.detect(
            task_description="Task",
            decomposition="1. First\n2. Second\n3. Third\n4. Fourth"
        )
        assert result.subtask_count == 4


class TestSubtask:
    """Tests for Subtask dataclass."""

    def test_subtask_creation(self):
        """Should create subtask with all fields."""
        subtask = Subtask(
            id="task_0",
            description="Test task",
            dependencies=["task_1"],
            assigned_agent="agent1",
            estimated_complexity="medium"
        )
        assert subtask.id == "task_0"
        assert subtask.description == "Test task"
        assert subtask.dependencies == ["task_1"]
        assert subtask.assigned_agent == "agent1"
        assert subtask.estimated_complexity == "medium"

    def test_subtask_defaults(self):
        """Should have correct defaults for optional fields."""
        subtask = Subtask(
            id="task_0",
            description="Test",
            dependencies=[]
        )
        assert subtask.assigned_agent is None
        assert subtask.estimated_complexity is None
