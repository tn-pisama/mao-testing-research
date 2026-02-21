"""Adversarial gaming resistance tests.

Proves that gaming strategies (keyword stuffing, checkbox-only configs,
tool spam, and combined maximizers) do NOT inflate quality scores past
the anti-gaming guards built into the scoring system.

All tests use heuristic-only scoring (use_llm_judge=False) so they run
fast and deterministically.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.agent_scorer import AgentQualityScorer


# ---------------------------------------------------------------------------
# Reference workflow: a genuinely well-built agent for comparison
# ---------------------------------------------------------------------------

GENUINE_GOOD_WORKFLOW = {
    "id": "genuine-good",
    "name": "Customer Support Pipeline",
    "nodes": [
        {
            "id": "agent-1",
            "name": "Support Analyzer",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": (
                    "You are a customer support analyst. Analyze incoming tickets "
                    "and classify them by urgency (critical, high, medium, low) and "
                    "category (billing, technical, general). Return a JSON object "
                    "with fields: urgency, category, summary, suggested_action. "
                    "Do not attempt to resolve tickets directly."
                ),
                "options": {"temperature": 0.2, "maxTokens": 1000},
            },
            "retryOnFail": True,
            "maxTries": 3,
            "continueOnFail": True,
            "position": [0, 0],
        }
    ],
    "connections": {},
    "settings": {"executionTimeout": 300},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent_dimension_score(report, dimension_name: str) -> float:
    """Extract a specific dimension score from the first agent in a report."""
    agent = report.agent_scores[0]
    for dim in agent.dimensions:
        if dim.dimension == dimension_name:
            return dim.score
    raise ValueError(f"Dimension '{dimension_name}' not found in agent scores")


def _assess(workflow: dict):
    """Run a heuristic-only quality assessment on a workflow."""
    assessor = QualityAssessor(use_llm_judge=False)
    return assessor.assess_workflow(workflow)


# ===========================================================================
# 1. Keyword Stuffing Resistance
# ===========================================================================


class TestKeywordStuffingResistance:
    """Prove that repeating role/output/boundary keywords does not inflate scores."""

    def test_keyword_stuffed_role_clarity_capped(self, keyword_stuffed_agent):
        """The keyword-stuffed agent's role_clarity should be capped at 0.4
        by the anti-gaming guard in _score_role_clarity."""
        report = _assess(keyword_stuffed_agent)
        role_clarity = _agent_dimension_score(report, "role_clarity")
        assert role_clarity <= 0.4, (
            f"Keyword-stuffed prompt scored role_clarity={role_clarity:.2f}, "
            f"expected <= 0.4 (anti-gaming cap)"
        )

    def test_keyword_stuffed_overall_lower_than_genuine(self, keyword_stuffed_agent):
        """A genuine basic workflow should score higher overall than keyword-stuffed."""
        gamed_report = _assess(keyword_stuffed_agent)
        genuine_report = _assess(GENUINE_GOOD_WORKFLOW)

        assert genuine_report.overall_score > gamed_report.overall_score, (
            f"Genuine workflow ({genuine_report.overall_score:.2f}) should outscore "
            f"keyword-stuffed ({gamed_report.overall_score:.2f})"
        )


# ===========================================================================
# 2. Checkbox Warrior Resistance
# ===========================================================================


class TestCheckboxWarriorResistance:
    """Prove that enabling all error-handling flags without a real prompt
    does not produce high scores."""

    def test_checkbox_warrior_error_handling_capped(self, checkbox_warrior):
        """Error-handling score should be capped at 0.5 because the agent
        has no system prompt (the no_prompt_penalty guard)."""
        report = _assess(checkbox_warrior)
        error_handling = _agent_dimension_score(report, "error_handling")
        assert error_handling <= 0.5, (
            f"Checkbox warrior error_handling={error_handling:.2f}, "
            f"expected <= 0.5 (no-prompt penalty cap)"
        )

    def test_checkbox_warrior_overall_mediocre(self, checkbox_warrior):
        """Overall score should be below 0.55 — checkbox flags alone
        are not enough for a quality workflow."""
        report = _assess(checkbox_warrior)
        assert report.overall_score < 0.55, (
            f"Checkbox warrior overall={report.overall_score:.2f}, "
            f"expected < 0.55"
        )


# ===========================================================================
# 3. Tool Spam Resistance
# ===========================================================================


class TestToolSpamResistance:
    """Prove that spamming 20 tools with identical descriptions is penalized."""

    def test_duplicate_tool_descriptions_penalized(self, tool_spam):
        """Tool_usage dimension should detect duplicates and score below 0.5."""
        report = _assess(tool_spam)
        tool_usage = _agent_dimension_score(report, "tool_usage")
        assert tool_usage < 0.5, (
            f"Tool spam scored tool_usage={tool_usage:.2f}, "
            f"expected < 0.5 (duplicate descriptions penalty)"
        )


# ===========================================================================
# 4. Score Maximizer Resistance (all gaming techniques combined)
# ===========================================================================


class TestScoreMaximizerResistance:
    """Prove that combining every gaming trick still cannot beat the guards."""

    def test_score_maximizer_below_threshold(self, score_maximizer):
        """The score-maximizer workflow should NOT score above 0.7 overall.
        Even though it hits every keyword and checkbox, the anti-gaming
        guards (keyword stuffing cap, no-prompt penalty, duplicate tool
        penalty) should keep it well below genuinely good workflows."""
        report = _assess(score_maximizer)
        assert report.overall_score <= 0.7, (
            f"Score maximizer overall={report.overall_score:.2f}, "
            f"expected <= 0.7 (combined anti-gaming guards)"
        )

    def test_genuine_good_beats_score_maximizer(self, score_maximizer):
        """A genuine good workflow should score higher than the gaming one."""
        gamed_report = _assess(score_maximizer)
        genuine_report = _assess(GENUINE_GOOD_WORKFLOW)

        assert genuine_report.overall_score > gamed_report.overall_score, (
            f"Genuine good workflow ({genuine_report.overall_score:.2f}) should "
            f"outscore score maximizer ({gamed_report.overall_score:.2f})"
        )


# ===========================================================================
# Standalone dimension-level checks via AgentQualityScorer directly
# ===========================================================================


class TestAgentScorerAntiGaming:
    """Direct unit tests on the AgentQualityScorer anti-gaming internals."""

    def test_keyword_stuffing_detector_fires(self):
        """_detect_keyword_stuffing should return True for the stuffed prompt."""
        scorer = AgentQualityScorer(use_llm_judge=False)
        stuffed = (
            "You are you are your role your role do not do not "
            "return JSON return JSON. You are a specialized agent. "
            "You are very specific. Your role is to analyze."
        )
        assert scorer._detect_keyword_stuffing(stuffed) is True

    def test_keyword_stuffing_detector_passes_genuine(self):
        """_detect_keyword_stuffing should return False for a genuine prompt."""
        scorer = AgentQualityScorer(use_llm_judge=False)
        genuine = (
            "You are a customer support analyst. Analyze incoming tickets "
            "and classify them by urgency (critical, high, medium, low) and "
            "category (billing, technical, general). Return a JSON object "
            "with fields: urgency, category, summary, suggested_action. "
            "Do not attempt to resolve tickets directly."
        )
        assert scorer._detect_keyword_stuffing(genuine) is False

    def test_duplicate_tool_descriptions_penalty(self):
        """_detect_duplicate_tool_descriptions returns < 1.0 for duplicates."""
        scorer = AgentQualityScorer(use_llm_judge=False)
        tools = [
            {"name": f"t{i}", "description": "This tool does things"}
            for i in range(10)
        ]
        penalty = scorer._detect_duplicate_tool_descriptions(tools)
        assert penalty < 1.0, f"Expected penalty < 1.0, got {penalty}"

    def test_unique_tool_descriptions_no_penalty(self):
        """_detect_duplicate_tool_descriptions returns 1.0 for unique descriptions."""
        scorer = AgentQualityScorer(use_llm_judge=False)
        tools = [
            {"name": f"t{i}", "description": f"Performs task number {i}"}
            for i in range(5)
        ]
        penalty = scorer._detect_duplicate_tool_descriptions(tools)
        assert penalty == 1.0, f"Expected no penalty (1.0), got {penalty}"
