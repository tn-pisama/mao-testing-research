"""Comprehensive tests for LLM-as-Judge evaluation implementation."""

import pytest
from unittest.mock import patch, MagicMock
import json

from app.enterprise.evals.llm_judge import (
    LLMJudge,
    LLMJudgeScorer,
    JudgmentResult,
    JudgeModel,
    EVAL_PROMPTS,
    create_default_scorers,
)
from app.enterprise.evals.scorer import EvalType, EvalResult, BaseScorer


# ============================================================================
# JudgmentResult Tests
# ============================================================================

class TestJudgmentResult:
    """Tests for JudgmentResult dataclass."""

    def test_create_judgment_result(self):
        """Should create JudgmentResult with all fields."""
        result = JudgmentResult(
            score=0.85,
            reasoning="Well structured response",
            confidence=0.9,
            raw_response='{"score": 0.85, "reasoning": "Well structured response"}',
            model_used="gpt-4o-mini",
            tokens_used=150,
        )
        assert result.score == 0.85
        assert result.reasoning == "Well structured response"
        assert result.confidence == 0.9
        assert result.model_used == "gpt-4o-mini"
        assert result.tokens_used == 150

    def test_judgment_result_default_tokens(self):
        """Should default tokens_used to 0."""
        result = JudgmentResult(
            score=0.5,
            reasoning="Test",
            confidence=0.8,
            raw_response="test",
            model_used="gpt-4o",
        )
        assert result.tokens_used == 0


# ============================================================================
# JudgeModel Tests
# ============================================================================

class TestJudgeModel:
    """Tests for JudgeModel enum."""

    def test_gpt4o_mini_value(self):
        """Should have correct model ID for GPT-4o-mini."""
        assert JudgeModel.GPT4O_MINI.value == "gpt-4o-mini"

    def test_gpt4o_value(self):
        """Should have correct model ID for GPT-4o."""
        assert JudgeModel.GPT4O.value == "gpt-4o"

    def test_claude_haiku_value(self):
        """Should have correct model ID for Claude Haiku."""
        assert JudgeModel.CLAUDE_HAIKU.value == "claude-3-5-haiku-20241022"

    def test_claude_sonnet_value(self):
        """Should have correct model ID for Claude Sonnet."""
        assert JudgeModel.CLAUDE_SONNET.value == "claude-3-5-sonnet-20241022"


# ============================================================================
# EVAL_PROMPTS Tests
# ============================================================================

class TestEvalPrompts:
    """Tests for evaluation prompt templates."""

    def test_relevance_prompt_exists(self):
        """Should have relevance prompt template."""
        assert EvalType.RELEVANCE in EVAL_PROMPTS
        assert "{context}" in EVAL_PROMPTS[EvalType.RELEVANCE]
        assert "{output}" in EVAL_PROMPTS[EvalType.RELEVANCE]

    def test_coherence_prompt_exists(self):
        """Should have coherence prompt template."""
        assert EvalType.COHERENCE in EVAL_PROMPTS
        assert "{output}" in EVAL_PROMPTS[EvalType.COHERENCE]

    def test_helpfulness_prompt_exists(self):
        """Should have helpfulness prompt template."""
        assert EvalType.HELPFULNESS in EVAL_PROMPTS

    def test_safety_prompt_exists(self):
        """Should have safety prompt template."""
        assert EvalType.SAFETY in EVAL_PROMPTS

    def test_factuality_prompt_exists(self):
        """Should have factuality prompt template."""
        assert EvalType.FACTUALITY in EVAL_PROMPTS

    def test_completeness_prompt_exists(self):
        """Should have completeness prompt template."""
        assert EvalType.COMPLETENESS in EVAL_PROMPTS
        assert "{expected}" in EVAL_PROMPTS[EvalType.COMPLETENESS]

    def test_prompts_request_json_response(self):
        """All prompts should request JSON format response."""
        for eval_type, prompt in EVAL_PROMPTS.items():
            assert "JSON" in prompt, f"{eval_type} prompt should request JSON"


# ============================================================================
# LLMJudge Tests
# ============================================================================

class TestLLMJudge:
    """Tests for LLMJudge class."""

    def test_init_default_model(self):
        """Should default to GPT-4o-mini model."""
        judge = LLMJudge()
        assert judge.model == JudgeModel.GPT4O_MINI

    def test_init_custom_model(self):
        """Should accept custom model."""
        judge = LLMJudge(model=JudgeModel.CLAUDE_SONNET)
        assert judge.model == JudgeModel.CLAUDE_SONNET

    def test_init_custom_api_key(self):
        """Should accept custom API key."""
        judge = LLMJudge(api_key="test-key-123")
        assert judge._api_key == "test-key-123"

    def test_api_key_from_custom(self):
        """Should use custom API key when provided."""
        judge = LLMJudge(api_key="custom-key")
        assert judge.api_key == "custom-key"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "env-openai-key"})
    def test_api_key_from_env_openai(self):
        """Should get OpenAI API key from environment."""
        judge = LLMJudge(model=JudgeModel.GPT4O)
        assert judge.api_key == "env-openai-key"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-anthropic-key"})
    def test_api_key_from_env_anthropic(self):
        """Should get Anthropic API key from environment for Claude models."""
        judge = LLMJudge(model=JudgeModel.CLAUDE_HAIKU)
        assert judge.api_key == "env-anthropic-key"

    def test_judge_raises_for_unknown_eval_type(self):
        """Should raise error for eval type without prompt template."""
        judge = LLMJudge(api_key="test")
        with pytest.raises(ValueError, match="No prompt template"):
            judge.judge(EvalType.TOXICITY, "test output")

    @patch("httpx.Client")
    def test_judge_calls_openai_for_gpt(self, mock_client_class):
        """Should call OpenAI API for GPT models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"score": 0.8, "reasoning": "Good"}'}}],
            "usage": {"total_tokens": 100},
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        judge = LLMJudge(model=JudgeModel.GPT4O_MINI, api_key="test-key")
        result = judge.judge(EvalType.RELEVANCE, "test output", context="test context")

        assert result.score == 0.8
        assert result.model_used == "gpt-4o-mini"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "api.openai.com" in call_args[0][0]

    @patch("app.enterprise.evals.llm_judge.Anthropic")
    def test_judge_calls_anthropic_for_claude(self, mock_anthropic_class):
        """Should call Anthropic API for Claude models."""
        # Create mock response matching Anthropic SDK response structure
        mock_content_block = MagicMock()
        mock_content_block.type = "text"
        mock_content_block.text = '{"score": 0.9, "reasoning": "Excellent"}'

        mock_usage = MagicMock()
        mock_usage.input_tokens = 50
        mock_usage.output_tokens = 30

        mock_response = MagicMock()
        mock_response.content = [mock_content_block]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        judge = LLMJudge(model=JudgeModel.CLAUDE_HAIKU, api_key="test-key")
        result = judge.judge(EvalType.COHERENCE, "test output")

        assert result.score == 0.9
        assert result.model_used == "claude-3-5-haiku-20241022"
        assert result.tokens_used == 80  # input + output
        mock_client.messages.create.assert_called_once()

    @patch("httpx.Client")
    def test_judge_handles_api_error(self, mock_client_class):
        """Should handle API errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        judge = LLMJudge(api_key="test-key")
        result = judge.judge(EvalType.SAFETY, "test output")

        assert result.score == 0.5
        assert result.confidence == 0.0
        assert "API error: 500" in result.reasoning

    def test_judge_with_custom_prompt(self):
        """Should accept custom prompt template."""
        judge = LLMJudge(api_key="test")
        custom_prompt = "Custom evaluation: {output}"

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"score": 0.7, "reasoning": "Custom eval"}'}}],
                "usage": {"total_tokens": 50},
            }
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = judge.judge(
                EvalType.RELEVANCE,
                "test output",
                custom_prompt=custom_prompt,
            )
            assert result.score == 0.7


# ============================================================================
# Response Parsing Tests
# ============================================================================

class TestResponseParsing:
    """Tests for LLMJudge response parsing."""

    def setup_method(self):
        self.judge = LLMJudge(api_key="test")

    def test_parse_json_response(self):
        """Should parse valid JSON response."""
        content = '{"score": 0.85, "reasoning": "Well structured"}'
        result = self.judge._parse_response(content, 100)

        assert result.score == 0.85
        assert result.reasoning == "Well structured"
        assert result.confidence == 0.9
        assert result.tokens_used == 100

    def test_parse_json_with_surrounding_text(self):
        """Should extract JSON from text with surrounding content."""
        content = 'Here is my evaluation: {"score": 0.75, "reasoning": "Good"} That is my assessment.'
        result = self.judge._parse_response(content, 50)

        assert result.score == 0.75
        assert result.reasoning == "Good"

    def test_parse_score_clamping_high(self):
        """Should clamp score to max 1.0."""
        content = '{"score": 1.5, "reasoning": "Excellent"}'
        result = self.judge._parse_response(content, 50)

        assert result.score == 1.0

    def test_parse_score_clamping_low(self):
        """Should clamp score to min 0.0."""
        content = '{"score": -0.5, "reasoning": "Bad"}'
        result = self.judge._parse_response(content, 50)

        assert result.score == 0.0

    def test_parse_fallback_x_out_of_10(self):
        """Should parse 'X/10' format as fallback."""
        content = "I give this response a 7/10 because it was good."
        result = self.judge._parse_response(content, 50)

        assert result.score == 0.7
        assert result.confidence == 0.6

    def test_parse_fallback_score_keyword(self):
        """Should parse 'score: X' format as fallback."""
        content = "The evaluation score: 0.65 based on clarity."
        result = self.judge._parse_response(content, 50)

        assert result.score == 0.65
        assert result.confidence == 0.6

    def test_parse_unparseable_response(self):
        """Should return default for unparseable response."""
        content = "I cannot provide a numerical evaluation."
        result = self.judge._parse_response(content, 50)

        assert result.score == 0.5
        assert result.confidence == 0.0
        assert "Could not parse" in result.reasoning

    def test_parse_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        content = '{"score": invalid, "reasoning": "test"}'
        result = self.judge._parse_response(content, 50)

        # Should fall back to default
        assert 0.0 <= result.score <= 1.0


# ============================================================================
# LLMJudgeScorer Tests
# ============================================================================

class TestLLMJudgeScorer:
    """Tests for LLMJudgeScorer class."""

    def test_is_base_scorer(self):
        """Should inherit from BaseScorer."""
        scorer = LLMJudgeScorer(EvalType.RELEVANCE)
        assert isinstance(scorer, BaseScorer)

    def test_init_with_eval_type(self):
        """Should store eval type."""
        scorer = LLMJudgeScorer(EvalType.COHERENCE)
        assert scorer.eval_type == EvalType.COHERENCE

    def test_init_with_custom_judge(self):
        """Should accept custom judge instance."""
        custom_judge = LLMJudge(model=JudgeModel.CLAUDE_SONNET, api_key="test")
        scorer = LLMJudgeScorer(EvalType.SAFETY, judge=custom_judge)
        assert scorer.judge.model == JudgeModel.CLAUDE_SONNET

    def test_init_creates_default_judge(self):
        """Should create default judge if not provided."""
        scorer = LLMJudgeScorer(EvalType.HELPFULNESS)
        assert scorer.judge is not None
        assert scorer.judge.model == JudgeModel.GPT4O_MINI

    @patch.object(LLMJudge, "judge")
    def test_score_returns_eval_result(self, mock_judge):
        """Should return EvalResult from score method."""
        mock_judge.return_value = JudgmentResult(
            score=0.8,
            reasoning="Good response",
            confidence=0.9,
            raw_response="{}",
            model_used="gpt-4o-mini",
            tokens_used=100,
        )

        scorer = LLMJudgeScorer(EvalType.RELEVANCE)
        result = scorer.score("test output", context="test context")

        assert isinstance(result, EvalResult)
        assert result.score == 0.8
        assert result.passed is True
        assert result.eval_type == EvalType.RELEVANCE

    @patch.object(LLMJudge, "judge")
    def test_score_respects_threshold(self, mock_judge):
        """Should respect custom threshold."""
        mock_judge.return_value = JudgmentResult(
            score=0.75,
            reasoning="Acceptable",
            confidence=0.9,
            raw_response="{}",
            model_used="gpt-4o-mini",
        )

        scorer = LLMJudgeScorer(EvalType.COHERENCE)
        result = scorer.score("test", threshold=0.8)

        assert result.score == 0.75
        assert result.passed is False  # 0.75 < 0.8

    @patch.object(LLMJudge, "judge")
    def test_score_includes_metadata(self, mock_judge):
        """Should include model info in metadata."""
        mock_judge.return_value = JudgmentResult(
            score=0.9,
            reasoning="Excellent",
            confidence=0.95,
            raw_response="{}",
            model_used="gpt-4o",
            tokens_used=150,
        )

        scorer = LLMJudgeScorer(EvalType.SAFETY)
        result = scorer.score("test")

        assert result.metadata["model"] == "gpt-4o"
        assert result.metadata["confidence"] == 0.95
        assert result.metadata["tokens_used"] == 150


# ============================================================================
# create_default_scorers Tests
# ============================================================================

class TestCreateDefaultScorers:
    """Tests for create_default_scorers function."""

    def test_creates_all_eval_types(self):
        """Should create scorers for all defined eval types."""
        scorers = create_default_scorers()

        assert EvalType.RELEVANCE in scorers
        assert EvalType.COHERENCE in scorers
        assert EvalType.HELPFULNESS in scorers
        assert EvalType.SAFETY in scorers
        assert EvalType.FACTUALITY in scorers
        assert EvalType.COMPLETENESS in scorers

    def test_scorers_are_llm_judge_scorers(self):
        """All scorers should be LLMJudgeScorer instances."""
        scorers = create_default_scorers()

        for scorer in scorers.values():
            assert isinstance(scorer, LLMJudgeScorer)

    def test_uses_provided_judge(self):
        """Should use provided judge for all scorers."""
        custom_judge = LLMJudge(model=JudgeModel.GPT4O, api_key="test")
        scorers = create_default_scorers(judge=custom_judge)

        for scorer in scorers.values():
            assert scorer.judge is custom_judge

    def test_scorers_have_correct_eval_types(self):
        """Each scorer should have matching eval type."""
        scorers = create_default_scorers()

        for eval_type, scorer in scorers.items():
            assert scorer.eval_type == eval_type


# ============================================================================
# Integration Tests (with mocked APIs)
# ============================================================================

class TestLLMJudgeIntegration:
    """Integration tests for LLM Judge workflow."""

    @patch("httpx.Client")
    def test_full_evaluation_workflow(self, mock_client_class):
        """Should complete full evaluation workflow."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"score": 0.85, "reasoning": "Highly relevant response"}'}}],
            "usage": {"total_tokens": 120},
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        judge = LLMJudge(api_key="test-key")
        scorer = LLMJudgeScorer(EvalType.RELEVANCE, judge=judge)

        result = scorer.score(
            output="The capital of France is Paris.",
            context="What is the capital of France?",
            threshold=0.7,
        )

        assert result.passed is True
        assert result.score == 0.85
        assert result.eval_type == EvalType.RELEVANCE
        assert "model" in result.metadata

    @patch("httpx.Client")
    def test_multiple_eval_types(self, mock_client_class):
        """Should evaluate with multiple eval types."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"score": 0.9, "reasoning": "Good"}'}}],
            "usage": {"total_tokens": 100},
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        scorers = create_default_scorers(LLMJudge(api_key="test"))

        results = {}
        for eval_type in [EvalType.COHERENCE, EvalType.SAFETY]:
            results[eval_type] = scorers[eval_type].score("Test response")

        assert len(results) == 2
        assert all(r.passed for r in results.values())

    @patch("app.enterprise.evals.llm_judge.Anthropic")
    def test_claude_model_workflow(self, mock_anthropic_class):
        """Should work with Claude models."""
        # Create mock response matching Anthropic SDK response structure
        mock_content_block = MagicMock()
        mock_content_block.type = "text"
        mock_content_block.text = '{"score": 0.88, "reasoning": "Well-reasoned response"}'

        mock_usage = MagicMock()
        mock_usage.input_tokens = 80
        mock_usage.output_tokens = 40

        mock_response = MagicMock()
        mock_response.content = [mock_content_block]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        judge = LLMJudge(model=JudgeModel.CLAUDE_SONNET, api_key="test-key")
        scorer = LLMJudgeScorer(EvalType.HELPFULNESS, judge=judge)

        result = scorer.score("Here's how to solve your problem...")

        assert result.score == 0.88
        assert result.metadata["model"] == "claude-3-5-sonnet-20241022"
        assert result.metadata["tokens_used"] == 120  # input + output


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_output(self):
        """Should handle empty output string."""
        judge = LLMJudge(api_key="test")

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"score": 0.1, "reasoning": "Empty response"}'}}],
                "usage": {"total_tokens": 50},
            }
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = judge.judge(EvalType.COHERENCE, "")
            assert result.score == 0.1

    def test_very_long_output(self):
        """Should handle very long output strings."""
        judge = LLMJudge(api_key="test")
        long_output = "word " * 10000

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"score": 0.5, "reasoning": "Evaluated"}'}}],
                "usage": {"total_tokens": 5000},
            }
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = judge.judge(EvalType.COHERENCE, long_output)
            assert result.tokens_used == 5000

    def test_special_characters_in_output(self):
        """Should handle special characters in output."""
        judge = LLMJudge(api_key="test")
        output_with_special = "Test with \"quotes\" and \n newlines and {braces}"

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"score": 0.7, "reasoning": "Handled special chars"}'}}],
                "usage": {"total_tokens": 100},
            }
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = judge.judge(EvalType.SAFETY, output_with_special)
            assert result.score == 0.7

    def test_none_context_handling(self):
        """Should handle None context gracefully."""
        judge = LLMJudge(api_key="test")

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"score": 0.6, "reasoning": "No context"}'}}],
                "usage": {"total_tokens": 80},
            }
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = judge.judge(EvalType.RELEVANCE, "test", context=None)
            assert result.score == 0.6

    def test_rate_limit_error_handling(self):
        """Should handle rate limit errors."""
        judge = LLMJudge(api_key="test")

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = "Rate limit exceeded"

            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = judge.judge(EvalType.COHERENCE, "test")
            assert result.score == 0.5
            assert result.confidence == 0.0
            assert "API error: 429" in result.reasoning
