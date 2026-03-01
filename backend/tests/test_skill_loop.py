"""Tests for skill loop detection in Claude Code sessions."""

import pytest

from app.detection.skill_loop import (
    SkillLoopDetector,
    SkillLoopResult,
    SkillTrace,
    analyze_session,
)


def _make_trace(
    tool_name: str = "test_tool",
    trace_type: str = "tool",
    skill_name: str | None = None,
    tool_output: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    timestamp: str = "2025-01-01T00:00:00Z",
) -> SkillTrace:
    return SkillTrace(
        timestamp=timestamp,
        tool_name=tool_name,
        trace_type=trace_type,
        skill_name=skill_name,
        tool_output=tool_output,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


class TestSkillLoopDetection:
    """Test detection of repeated skill invocations."""

    def test_no_loop_with_few_skills(self):
        """Not enough skill calls to detect a loop."""
        traces = [
            _make_trace(tool_name="skill-a", trace_type="skill", skill_name="review"),
            _make_trace(tool_name="skill-b", trace_type="skill", skill_name="analyze"),
        ]
        detector = SkillLoopDetector()
        result = detector._detect_skill_loops(traces)
        assert not result.detected

    def test_detect_skill_loop_with_similar_outputs(self):
        """Same skill called multiple times with same output = loop."""
        traces = [
            _make_trace(
                tool_name="commit-skill",
                trace_type="skill",
                skill_name="commit",
                tool_output="Error: no changes to commit",
            )
            for _ in range(5)
        ]
        detector = SkillLoopDetector()
        result = detector._detect_skill_loops(traces)
        assert result.detected
        assert result.detection_type == "skill_loop"
        assert result.severity in ("moderate", "severe")
        assert "commit" in result.affected_skills

    def test_no_loop_with_varying_outputs(self):
        """Same skill called with varying outputs is less concerning."""
        traces = [
            _make_trace(
                tool_name="search-skill",
                trace_type="skill",
                skill_name="search",
                tool_output=f"Result {i}: found {i * 10} items",
            )
            for i in range(4)
        ]
        detector = SkillLoopDetector()
        result = detector._detect_skill_loops(traces)
        # May detect with low confidence since outputs vary
        if result.detected:
            assert result.confidence <= 0.6

    def test_detect_across_different_skills(self):
        """Only flags the repeated skill, not others."""
        traces = [
            _make_trace(trace_type="skill", skill_name="analyze", tool_output="done"),
            _make_trace(trace_type="skill", skill_name="review", tool_output="ok"),
        ]
        # Add 4 repeated calls to "analyze" with same output
        for _ in range(4):
            traces.append(
                _make_trace(trace_type="skill", skill_name="analyze", tool_output="done")
            )
        detector = SkillLoopDetector()
        result = detector._detect_skill_loops(traces)
        assert result.detected
        assert "analyze" in result.affected_skills


class TestToolLoopInSkills:
    """Test detection of tool loops within skill contexts."""

    def test_no_tool_loop_without_skills(self):
        """Tool calls without skill context don't trigger skill-level detection."""
        traces = [
            _make_trace(tool_name="read", trace_type="tool"),
            _make_trace(tool_name="read", trace_type="tool"),
        ]
        detector = SkillLoopDetector()
        result = detector._detect_tool_loops_in_skills(traces)
        assert not result.detected

    def test_detect_tool_loop_in_skill(self):
        """Tool called repeatedly during a skill = tool loop in skill."""
        traces = [
            _make_trace(trace_type="skill", skill_name="debug"),
        ]
        # 6 consecutive reads during the skill
        for _ in range(6):
            traces.append(_make_trace(tool_name="Read", trace_type="tool"))

        detector = SkillLoopDetector()
        result = detector._detect_tool_loops_in_skills(traces)
        assert result.detected
        assert result.detection_type == "tool_loop_in_skill"
        assert "debug" in result.affected_skills
        assert "Read" in result.affected_tools

    def test_no_loop_with_varied_tools(self):
        """Different tools during a skill are fine."""
        traces = [
            _make_trace(trace_type="skill", skill_name="review"),
            _make_trace(tool_name="Read", trace_type="tool"),
            _make_trace(tool_name="Grep", trace_type="tool"),
            _make_trace(tool_name="Glob", trace_type="tool"),
            _make_trace(tool_name="Write", trace_type="tool"),
        ]
        detector = SkillLoopDetector()
        result = detector._detect_tool_loops_in_skills(traces)
        assert not result.detected


class TestSkillChainFailure:
    """Test detection of excessive skill chaining."""

    def test_no_chain_issue_with_few_skills(self):
        traces = [
            _make_trace(trace_type="skill", skill_name="a"),
        ]
        detector = SkillLoopDetector()
        result = detector._detect_skill_chain_failure(traces)
        assert not result.detected

    def test_detect_deep_skill_chain(self):
        """Skill chain depth > 5 triggers detection."""
        traces = [
            _make_trace(trace_type="skill", skill_name=f"skill_{i}")
            for i in range(7)
        ]
        detector = SkillLoopDetector()
        result = detector._detect_skill_chain_failure(traces)
        assert result.detected
        assert result.detection_type == "skill_chain_failure"
        assert len(result.affected_skills) == 7

    def test_acceptable_chain_depth(self):
        """Chain depth <= 5 is acceptable."""
        traces = [
            _make_trace(trace_type="skill", skill_name=f"skill_{i}")
            for i in range(4)
        ]
        detector = SkillLoopDetector()
        result = detector._detect_skill_chain_failure(traces)
        assert not result.detected


class TestCostAnomaly:
    """Test detection of cost anomalies in skill execution."""

    def test_no_anomaly_without_costs(self):
        traces = [
            _make_trace(trace_type="skill", skill_name="a", cost_usd=0.0),
        ]
        detector = SkillLoopDetector()
        result = detector._detect_cost_anomaly(traces)
        assert not result.detected

    def test_detect_cost_anomaly(self):
        """One skill consuming much more than average."""
        traces = [
            _make_trace(trace_type="skill", skill_name="cheap1", cost_usd=0.01),
            _make_trace(trace_type="skill", skill_name="cheap2", cost_usd=0.02),
            _make_trace(trace_type="skill", skill_name="cheap3", cost_usd=0.01),
            _make_trace(trace_type="skill", skill_name="expensive", cost_usd=0.50),
        ]
        detector = SkillLoopDetector()
        result = detector._detect_cost_anomaly(traces)
        assert result.detected
        assert result.detection_type == "cost_anomaly"
        assert "expensive" in result.affected_skills

    def test_no_anomaly_with_even_costs(self):
        """All skills cost about the same = no anomaly."""
        traces = [
            _make_trace(trace_type="skill", skill_name=f"s{i}", cost_usd=0.05)
            for i in range(5)
        ]
        detector = SkillLoopDetector()
        result = detector._detect_cost_anomaly(traces)
        assert not result.detected


class TestAnalyzeSession:
    """Test the convenience function for full session analysis."""

    def test_analyze_healthy_session(self):
        """Healthy session with no issues."""
        traces = [
            _make_trace(trace_type="skill", skill_name="review", tool_output="Looks good"),
            _make_trace(tool_name="Read", trace_type="tool"),
            _make_trace(tool_name="Grep", trace_type="tool"),
        ]
        results = analyze_session(traces)
        assert len(results) == 0

    def test_analyze_looping_session(self):
        """Session with skill loop should detect it."""
        traces = [
            _make_trace(
                trace_type="skill",
                skill_name="fix-lint",
                tool_output="Lint error on line 42",
            )
            for _ in range(5)
        ]
        results = analyze_session(traces)
        assert len(results) >= 1
        assert any(r.detection_type == "skill_loop" for r in results)

    def test_analyze_multiple_issues(self):
        """Session with both skill loop and cost anomaly."""
        traces = []
        # Skill loop
        for _ in range(5):
            traces.append(
                _make_trace(trace_type="skill", skill_name="retry", tool_output="failed", cost_usd=0.01)
            )
        # Cost anomaly
        traces.append(
            _make_trace(trace_type="skill", skill_name="expensive-analysis", cost_usd=0.50)
        )

        results = analyze_session(traces)
        types = {r.detection_type for r in results}
        assert "skill_loop" in types
