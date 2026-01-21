"""Test agent quality dimension scoring."""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.agent_scorer import AgentQualityScorer
from app.enterprise.quality.models import QualityDimension


class TestRoleClarityDimension:
    """Test role_clarity dimension scoring."""

    def test_no_prompt_scores_zero(self):
        """Agent with no system prompt should score 0% for role clarity."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {}
        }

        score = scorer.score_agent(node)
        role_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.ROLE_CLARITY.value)

        assert role_dim.score == 0.0
        assert "No system prompt" in role_dim.issues[0]

    def test_basic_prompt_scores_partial(self):
        """Agent with basic prompt (role only) should score low due to missing elements."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": "You are a helpful assistant."
            }
        }

        score = scorer.score_agent(node)
        role_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.ROLE_CLARITY.value)

        # Should have low score (missing output format, boundaries, brief prompt)
        assert 0.1 <= role_dim.score <= 0.4
        assert role_dim.evidence.get("role_keywords_found", 0) >= 1

    def test_full_prompt_scores_high(self):
        """Agent with comprehensive prompt should score 70%+."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Data Analyst Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": """You are a senior data analyst specializing in business intelligence.

Your role is to analyze data and provide actionable insights.
Your task is to examine the provided dataset and identify trends.

You must respond with a JSON object in this format:
{
  "summary": "Brief analysis summary",
  "insights": ["insight 1", "insight 2"],
  "recommendations": ["action 1", "action 2"],
  "confidence": 0.0-1.0
}

Do not make assumptions about missing data.
Never include raw personally identifiable information in outputs.
Only respond to data analysis requests.
Avoid speculation - stick to what the data shows."""
            }
        }

        score = scorer.score_agent(node)
        role_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.ROLE_CLARITY.value)

        # Should score high - has role, output format, and boundaries
        assert role_dim.score >= 0.7
        assert role_dim.evidence.get("role_keywords_found", 0) >= 2
        assert role_dim.evidence.get("output_format_keywords", 0) >= 1
        assert role_dim.evidence.get("boundary_keywords", 0) >= 1


class TestOutputConsistencyDimension:
    """Test output_consistency dimension scoring."""

    def test_no_history_uses_default_score(self):
        """Without execution history, should use default score (0.7)."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": "Return JSON output."
            }
        }

        score = scorer.score_agent(node, execution_history=None)
        consistency_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.OUTPUT_CONSISTENCY.value)

        # Default score when no history
        assert consistency_dim.score == 0.7
        assert consistency_dim.evidence.get("execution_samples", 0) == 0

    def test_consistent_outputs_score_high(self):
        """Consistent output structures should score 1.0."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {}
        }

        # Consistent execution history with same structure
        execution_history = [
            {"output": {"result": "A", "confidence": 0.9}},
            {"output": {"result": "B", "confidence": 0.8}},
            {"output": {"result": "C", "confidence": 0.95}},
        ]

        score = scorer.score_agent(node, execution_history=execution_history)
        consistency_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.OUTPUT_CONSISTENCY.value)

        assert consistency_dim.score == 1.0
        assert consistency_dim.evidence.get("unique_structures", 1) == 1

    def test_inconsistent_outputs_score_low(self):
        """Inconsistent output structures should score low."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {}
        }

        # Inconsistent execution history with different structures
        execution_history = [
            {"output": {"result": "A", "confidence": 0.9}},
            {"output": {"answer": "B", "score": 0.8}},
            {"output": {"data": "C"}},
        ]

        score = scorer.score_agent(node, execution_history=execution_history)
        consistency_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.OUTPUT_CONSISTENCY.value)

        # Multiple unique structures = low consistency
        assert consistency_dim.score < 0.5
        assert consistency_dim.evidence.get("unique_structures", 1) == 3


class TestErrorHandlingDimension:
    """Test error_handling dimension scoring."""

    def test_no_config_scores_zero(self):
        """Agent with no error handling config should score 0%."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {}
        }

        score = scorer.score_agent(node)
        error_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.ERROR_HANDLING.value)

        assert error_dim.score == 0.0
        assert error_dim.evidence.get("continue_on_fail") is False
        assert error_dim.evidence.get("retry_on_fail") is False

    def test_partial_config_scores_partial(self):
        """Agent with some error handling should score partial."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "continueOnFail": True,
            "parameters": {}
        }

        score = scorer.score_agent(node)
        error_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.ERROR_HANDLING.value)

        # Has continueOnFail (25%) but missing other configs
        assert 0.2 <= error_dim.score <= 0.4
        assert error_dim.evidence.get("continue_on_fail") is True

    def test_full_config_scores_high(self):
        """Agent with full error handling should score 85%+."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "continueOnFail": True,
            "alwaysOutputData": True,
            "parameters": {
                "options": {
                    "retryOnFail": True,
                    "maxRetries": 3,
                    "timeout": 30000
                }
            }
        }

        score = scorer.score_agent(node)
        error_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.ERROR_HANDLING.value)

        # Has continueOnFail (25%) + alwaysOutput (15%) + retry (20%) + maxRetries (10%) + timeout (15%) = 85%
        assert error_dim.score >= 0.8
        assert error_dim.evidence.get("continue_on_fail") is True
        assert error_dim.evidence.get("retry_on_fail") is True
        assert error_dim.evidence.get("timeout_ms") == 30000


class TestToolUsageDimension:
    """Test tool_usage dimension scoring."""

    def test_agent_without_tools_scores_medium(self):
        """Agent node without tools should score 0.5 (expected to have tools)."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",  # Agent type
            "parameters": {}
        }

        score = scorer.score_agent(node)
        tool_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.TOOL_USAGE.value)

        # Agent without tools gets lower score
        assert tool_dim.score == 0.5
        assert "no tools" in tool_dim.issues[0].lower()

    def test_non_agent_without_tools_scores_high(self):
        """Non-agent node without tools should score 0.8 (tools not expected)."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-chain",
            "name": "Test Chain",
            "type": "@n8n/n8n-nodes-langchain.chainLlm",  # Chain type, not agent
            "parameters": {}
        }

        score = scorer.score_agent(node)
        tool_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.TOOL_USAGE.value)

        # Non-agent without tools is fine
        assert tool_dim.score == 0.8

    def test_tools_without_descriptions_score_partial(self):
        """Tools without descriptions should score partial."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "tools": [
                    {"name": "search"},
                    {"name": "calculate"},
                ]
            }
        }

        score = scorer.score_agent(node)
        tool_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.TOOL_USAGE.value)

        # Has tools but no descriptions = partial score
        assert 0.2 <= tool_dim.score <= 0.5
        assert tool_dim.evidence.get("tool_count") == 2
        assert tool_dim.evidence.get("tools_with_description") == 0

    def test_well_configured_tools_score_high(self):
        """Well-configured tools should score high."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "tools": [
                    {
                        "name": "search",
                        "description": "Search the database for relevant information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"}
                            }
                        }
                    },
                    {
                        "name": "calculate",
                        "description": "Perform mathematical calculations",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "expression": {"type": "string"}
                            }
                        }
                    },
                ]
            }
        }

        score = scorer.score_agent(node)
        tool_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.TOOL_USAGE.value)

        # Has tools with descriptions and schemas
        assert tool_dim.score >= 0.9
        assert tool_dim.evidence.get("tools_with_description") == 2
        assert tool_dim.evidence.get("tools_with_schema") == 2


class TestConfigAppropriatenessDimension:
    """Test config_appropriateness dimension scoring."""

    def test_default_config_scores_default(self):
        """Agent with no explicit config uses default score."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {}
        }

        score = scorer.score_agent(node)
        config_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.CONFIG_APPROPRIATENESS.value)

        # Default reasonable score
        assert config_dim.score == 0.7

    def test_appropriate_temperature_for_code(self):
        """Low temperature for code tasks should score well."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Code Generator",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": "You are a code generator. Write Python functions.",
                "options": {
                    "temperature": 0.2
                }
            }
        }

        score = scorer.score_agent(node)
        config_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.CONFIG_APPROPRIATENESS.value)

        # Low temp (0.2) is appropriate for code (0.0-0.3 recommended)
        assert config_dim.score >= 0.8
        assert config_dim.evidence.get("inferred_task_type") == "code"

    def test_high_temperature_for_code_scores_lower(self):
        """High temperature for code tasks should flag as issue."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Code Generator",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": "You are a code generator. Write Python functions.",
                "options": {
                    "temperature": 0.9
                }
            }
        }

        score = scorer.score_agent(node)
        config_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.CONFIG_APPROPRIATENESS.value)

        # High temp (0.9) is inappropriate for code
        assert config_dim.score < 0.7
        assert any("temperature" in issue.lower() for issue in config_dim.issues)

    def test_low_max_tokens_flagged(self):
        """Very low max tokens should be flagged."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "options": {
                    "maxTokens": 50
                }
            }
        }

        score = scorer.score_agent(node)
        config_dim = next(d for d in score.dimensions if d.dimension == QualityDimension.CONFIG_APPROPRIATENESS.value)

        # 50 tokens is too low
        assert config_dim.score < 0.7
        assert any("token" in issue.lower() for issue in config_dim.issues)


class TestOverallAgentScoring:
    """Test overall agent scoring with QualityAssessor."""

    def test_assess_single_agent(self):
        """Test assessing a single agent node."""
        assessor = QualityAssessor(use_llm_judge=False)

        node = {
            "id": "test-agent",
            "name": "Test Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "continueOnFail": True,
            "parameters": {
                "systemMessage": "You are a helpful assistant. Respond in JSON format.",
                "options": {
                    "temperature": 0.5,
                    "timeout": 30000
                }
            }
        }

        score = assessor.assess_agent(node)

        assert score.agent_id == "test-agent"
        assert score.agent_name == "Test Agent"
        assert len(score.dimensions) == 5
        assert 0 <= score.overall_score <= 1
        assert score.grade in ["A", "B+", "B", "C+", "C", "D", "F"]

    def test_all_dimensions_present(self):
        """Verify all 5 agent dimensions are scored."""
        scorer = AgentQualityScorer()
        node = {
            "id": "test",
            "name": "Test",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {}
        }

        score = scorer.score_agent(node)

        dimension_names = {d.dimension for d in score.dimensions}
        expected = {
            QualityDimension.ROLE_CLARITY.value,
            QualityDimension.OUTPUT_CONSISTENCY.value,
            QualityDimension.ERROR_HANDLING.value,
            QualityDimension.TOOL_USAGE.value,
            QualityDimension.CONFIG_APPROPRIATENESS.value,
        }

        assert dimension_names == expected
