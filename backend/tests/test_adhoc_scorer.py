"""Tests for AdHocScorerService."""
import json
import pytest
from unittest.mock import MagicMock, patch
from app.detection.adhoc_scorer import (
    AdHocScorerService,
    ScorerGenerationResult,
    ScoringResult,
    MODEL_ALIASES,
    MODEL_PRICING,
    GENERATION_SYSTEM_PROMPT,
    EVALUATION_TEMPLATE,
)


class TestJsonExtraction:
    """Test _extract_json with various LLM output formats."""

    def _make_service(self):
        svc = AdHocScorerService.__new__(AdHocScorerService)
        return svc

    def test_extracts_from_json_code_block(self):
        svc = self._make_service()
        result = svc._extract_json('```json\n{"score": 4, "verdict": "PASS"}\n```')
        assert result["score"] == 4
        assert result["verdict"] == "PASS"

    def test_extracts_from_plain_code_block(self):
        svc = self._make_service()
        result = svc._extract_json('```\n{"score": 2}\n```')
        assert result["score"] == 2

    def test_extracts_raw_json(self):
        svc = self._make_service()
        result = svc._extract_json('{"verdict": "FAIL", "score": 1}')
        assert result["verdict"] == "FAIL"

    def test_extracts_from_mixed_text(self):
        svc = self._make_service()
        result = svc._extract_json('Analysis:\n{"score": 3, "reasoning": "ok"}\nEnd.')
        assert result["score"] == 3

    def test_returns_empty_dict_on_garbage(self):
        svc = self._make_service()
        assert svc._extract_json("no json here") == {}

    def test_returns_empty_dict_on_empty(self):
        svc = self._make_service()
        assert svc._extract_json("") == {}

    def test_extracts_nested_json(self):
        svc = self._make_service()
        result = svc._extract_json('{"score": 5, "nested": {"key": "val"}}')
        assert result["score"] == 5
        assert result["nested"]["key"] == "val"

    def test_extracts_from_markdown_with_surrounding_text(self):
        svc = self._make_service()
        text = """Here is my analysis:

```json
{"score": 3, "verdict": "WARN", "reasoning": "Moderate quality"}
```

That concludes my review."""
        result = svc._extract_json(text)
        assert result["score"] == 3
        assert result["verdict"] == "WARN"


class TestScorerGeneration:
    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_generates_valid_scorer(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [
            MagicMock(
                text='{"name": "Citation Checker", "prompt_template": "Check citations", '
                '"scoring_criteria": ["accuracy"], "scoring_rubric": "1-5"}'
            )
        ]
        mock_resp.usage.input_tokens = 100
        mock_resp.usage.output_tokens = 200
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService(model_key="sonnet-4")
        result = svc.generate_scorer("Check source citations")
        assert result.name == "Citation Checker"
        assert result.tokens_used == 300
        assert result.cost_usd > 0
        assert result.prompt_template == "Check citations"
        assert result.scoring_criteria == ["accuracy"]
        assert result.scoring_rubric == "1-5"
        assert result.model_used == "claude-sonnet-4-20250514"

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_handles_malformed_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Not valid JSON at all")]
        mock_resp.usage.input_tokens = 50
        mock_resp.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService()
        result = svc.generate_scorer("test scorer description")
        # Falls back to description[:50] for name when JSON parsing fails
        assert result.name == "test scorer description"
        # prompt_template falls back to raw text
        assert result.prompt_template == "Not valid JSON at all"
        assert result.scoring_criteria == []
        assert result.scoring_rubric == ""
        assert result.tokens_used == 100

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_cost_calculation_sonnet(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='{"name": "test"}')]
        mock_resp.usage.input_tokens = 1_000_000
        mock_resp.usage.output_tokens = 100_000
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService(model_key="sonnet-4")
        result = svc.generate_scorer("test")
        # Sonnet: input $3/1M, output $15/1M
        expected_cost = (1_000_000 * 3.0 + 100_000 * 15.0) / 1_000_000
        assert abs(result.cost_usd - expected_cost) < 0.001

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_cost_calculation_haiku(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='{"name": "test"}')]
        mock_resp.usage.input_tokens = 500_000
        mock_resp.usage.output_tokens = 50_000
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService(model_key="haiku-4.5")
        result = svc.generate_scorer("test")
        # Haiku: input $1/1M, output $5/1M
        expected_cost = (500_000 * 1.0 + 50_000 * 5.0) / 1_000_000
        assert abs(result.cost_usd - expected_cost) < 0.001


class TestScoreTrace:
    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_scores_trace_valid(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [
            MagicMock(
                text='{"score": 4, "confidence": 85, "verdict": "PASS", '
                '"reasoning": "Good", "evidence": ["e1"], "suggestions": ["s1"]}'
            )
        ]
        mock_resp.usage.input_tokens = 500
        mock_resp.usage.output_tokens = 100
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService()
        result = svc.score_trace("Check X", "Build app", "Summary", ["event1"])
        assert result.score == 4
        assert result.verdict == "PASS"
        assert result.confidence == 85
        assert result.reasoning == "Good"
        assert result.evidence == ["e1"]
        assert result.suggestions == ["s1"]
        assert result.latency_ms >= 0

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_clamps_score_range(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [
            MagicMock(text='{"score": 10, "confidence": 200, "verdict": "INVALID"}')
        ]
        mock_resp.usage.input_tokens = 100
        mock_resp.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService()
        result = svc.score_trace("X", "task", "summary", [])
        assert result.score == 5  # clamped from 10
        assert result.confidence == 100  # clamped from 200
        # score >= 4 and invalid verdict maps to PASS
        assert result.verdict == "PASS"

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_clamps_score_minimum(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [
            MagicMock(text='{"score": -5, "confidence": -10, "verdict": "BAD"}')
        ]
        mock_resp.usage.input_tokens = 100
        mock_resp.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService()
        result = svc.score_trace("X", "task", "summary", [])
        assert result.score == 1  # clamped from -5
        assert result.confidence == 0  # clamped from -10
        # score <= 2 with invalid verdict maps to FAIL
        assert result.verdict == "FAIL"

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_verdict_fallback_warn(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [
            MagicMock(text='{"score": 3, "confidence": 50, "verdict": "INVALID"}')
        ]
        mock_resp.usage.input_tokens = 100
        mock_resp.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService()
        result = svc.score_trace("X", "task", "summary", [])
        assert result.score == 3
        # score == 3 (not >= 4, not <= 2) => WARN
        assert result.verdict == "WARN"

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_passes_agent_interactions(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='{"score": 4, "confidence": 80, "verdict": "PASS"}')]
        mock_resp.usage.input_tokens = 100
        mock_resp.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService()
        result = svc.score_trace(
            "template", "task", "summary",
            ["event1", "event2"],
            agent_interactions=["agent1 -> agent2", "agent2 -> agent3"],
        )
        assert result.score == 4

        # Verify the prompt was constructed correctly
        call_args = mock_client.messages.create.call_args
        prompt_text = call_args.kwargs["messages"][0]["content"]
        assert "agent1 -> agent2" in prompt_text
        assert "agent2 -> agent3" in prompt_text

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_handles_missing_json_fields(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Just some text, no JSON")]
        mock_resp.usage.input_tokens = 100
        mock_resp.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_resp

        svc = AdHocScorerService()
        result = svc.score_trace("X", "task", "summary", [])
        # Defaults when JSON extraction fails
        assert result.score == 3  # default when no "score" in parsed dict
        assert result.confidence == 50  # default confidence
        assert result.verdict in ("PASS", "FAIL", "WARN", "UNCERTAIN")


class TestModelAliases:
    def test_sonnet_alias(self):
        assert "sonnet-4" in MODEL_ALIASES
        assert MODEL_ALIASES["sonnet-4"] == "claude-sonnet-4-20250514"

    def test_haiku_alias(self):
        assert "haiku-4.5" in MODEL_ALIASES
        assert MODEL_ALIASES["haiku-4.5"] == "claude-haiku-4-5-20251001"

    def test_all_aliases_resolve_to_priced_models(self):
        for alias, model_id in MODEL_ALIASES.items():
            assert model_id in MODEL_PRICING, f"Alias {alias} -> {model_id} has no pricing"

    def test_pricing_has_input_and_output(self):
        for model_id, pricing in MODEL_PRICING.items():
            assert "input" in pricing, f"Model {model_id} missing input price"
            assert "output" in pricing, f"Model {model_id} missing output price"
            assert pricing["input"] > 0
            assert pricing["output"] > 0


class TestServiceInit:
    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_resolves_alias(self, mock_cls):
        svc = AdHocScorerService(model_key="sonnet-4")
        assert svc._model_id == "claude-sonnet-4-20250514"

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_falls_back_to_sonnet_on_unknown_model(self, mock_cls):
        svc = AdHocScorerService(model_key="nonexistent-model")
        assert svc._model_id == "claude-sonnet-4-20250514"

    @patch("app.detection.adhoc_scorer.Anthropic")
    def test_uses_direct_model_id(self, mock_cls):
        svc = AdHocScorerService(model_key="claude-haiku-4-5-20251001")
        assert svc._model_id == "claude-haiku-4-5-20251001"


class TestPromptConstants:
    def test_generation_prompt_references_json_keys(self):
        assert "name" in GENERATION_SYSTEM_PROMPT
        assert "prompt_template" in GENERATION_SYSTEM_PROMPT
        assert "scoring_criteria" in GENERATION_SYSTEM_PROMPT
        assert "scoring_rubric" in GENERATION_SYSTEM_PROMPT

    def test_evaluation_template_has_placeholders(self):
        assert "{prompt_template}" in EVALUATION_TEMPLATE
        assert "{task}" in EVALUATION_TEMPLATE
        assert "{trace_summary}" in EVALUATION_TEMPLATE
        assert "{key_events}" in EVALUATION_TEMPLATE
        assert "{agent_interactions}" in EVALUATION_TEMPLATE
