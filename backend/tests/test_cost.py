"""Tests for LLM cost tracking and pricing calculator."""

import pytest
from app.detection.cost import (
    CostCalculator,
    CostResult,
    ModelPricing,
    LLM_PRICING_2025,
    MODEL_ALIASES,
    cost_calculator,
)


class TestModelPricing:
    """Tests for ModelPricing dataclass."""

    def test_model_pricing_creation(self):
        """Should create ModelPricing with all fields."""
        pricing = ModelPricing(
            input_per_1m=2.50,
            output_per_1m=10.00,
            context_window=128000,
            provider="openai",
        )
        assert pricing.input_per_1m == 2.50
        assert pricing.output_per_1m == 10.00
        assert pricing.context_window == 128000
        assert pricing.provider == "openai"

    def test_pricing_database_not_empty(self):
        """LLM pricing database should have entries."""
        assert len(LLM_PRICING_2025) > 0

    def test_pricing_database_has_major_models(self):
        """Should have major model families."""
        assert "gpt-4o" in LLM_PRICING_2025
        assert "claude-3-5-sonnet-20241022" in LLM_PRICING_2025
        assert "gemini-1.5-pro" in LLM_PRICING_2025

    def test_all_pricing_has_required_fields(self):
        """All pricing entries should have valid fields."""
        for model, pricing in LLM_PRICING_2025.items():
            assert pricing.input_per_1m >= 0, f"{model} has negative input price"
            assert pricing.output_per_1m >= 0, f"{model} has negative output price"
            assert pricing.context_window > 0, f"{model} has invalid context window"
            assert pricing.provider, f"{model} has no provider"


class TestModelAliases:
    """Tests for model alias mappings."""

    def test_aliases_not_empty(self):
        """Alias map should have entries."""
        assert len(MODEL_ALIASES) > 0

    def test_aliases_resolve_to_known_models(self):
        """All aliases should resolve to models in pricing database."""
        for alias, target in MODEL_ALIASES.items():
            assert target in LLM_PRICING_2025, f"Alias {alias} targets unknown model {target}"

    def test_common_aliases_exist(self):
        """Common aliases should be present."""
        assert "claude-3-5-sonnet-latest" in MODEL_ALIASES
        assert "gpt-4o-2024-11-20" in MODEL_ALIASES


class TestCostResult:
    """Tests for CostResult dataclass."""

    def test_cost_result_creation(self):
        """Should create CostResult with all fields."""
        result = CostResult(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            input_cost_usd=0.0025,
            output_cost_usd=0.005,
            total_cost_usd=0.0075,
            total_cost_cents=0.75,
            model="gpt-4o",
            provider="openai",
        )
        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.total_tokens == 1500
        assert result.model == "gpt-4o"
        assert result.provider == "openai"


class TestCostCalculator:
    """Tests for CostCalculator class."""

    def setup_method(self):
        self.calculator = CostCalculator()

    # Model Resolution Tests
    def test_resolve_known_model(self):
        """Should resolve known models directly."""
        resolved = self.calculator._resolve_model("gpt-4o")
        assert resolved == "gpt-4o"

    def test_resolve_model_via_alias(self):
        """Should resolve model aliases."""
        resolved = self.calculator._resolve_model("claude-3-5-sonnet-latest")
        assert resolved == "claude-3-5-sonnet-20241022"

    def test_resolve_model_case_insensitive(self):
        """Should resolve models case-insensitively."""
        resolved = self.calculator._resolve_model("GPT-4O")
        assert resolved == "gpt-4o"

    def test_resolve_model_fuzzy_match(self):
        """Should fuzzy match partial model names."""
        resolved = self.calculator._resolve_model("gpt-4o-something-new")
        assert resolved == "gpt-4o"

    def test_resolve_unknown_model(self):
        """Should return lowercase for unknown models."""
        resolved = self.calculator._resolve_model("TOTALLY-UNKNOWN-MODEL")
        assert resolved == "totally-unknown-model"

    # Pricing Lookup Tests
    def test_get_pricing_known_model(self):
        """Should return pricing for known models."""
        pricing = self.calculator.get_pricing("gpt-4o")
        assert pricing is not None
        assert pricing.provider == "openai"

    def test_get_pricing_via_alias(self):
        """Should return pricing via alias."""
        pricing = self.calculator.get_pricing("gpt-4o-2024-11-20")
        assert pricing is not None
        assert pricing.provider == "openai"

    def test_get_pricing_unknown_model(self):
        """Should return None for unknown models."""
        pricing = self.calculator.get_pricing("unknown-model-xyz")
        assert pricing is None

    def test_get_pricing_custom_model(self):
        """Should return custom pricing when added."""
        custom_pricing = ModelPricing(1.0, 2.0, 32000, "custom")
        self.calculator.add_custom_pricing("my-custom-model", custom_pricing)

        pricing = self.calculator.get_pricing("my-custom-model")
        assert pricing is not None
        assert pricing.input_per_1m == 1.0
        assert pricing.provider == "custom"

    # Cost Calculation Tests
    def test_calculate_cost_gpt4o(self):
        """Should calculate cost for GPT-4o correctly."""
        result = self.calculator.calculate_cost("gpt-4o", 1000000, 500000)

        # GPT-4o: $2.50 per 1M input, $10.00 per 1M output
        assert result.input_tokens == 1000000
        assert result.output_tokens == 500000
        assert result.total_tokens == 1500000
        assert result.input_cost_usd == 2.50
        assert result.output_cost_usd == 5.00
        assert result.total_cost_usd == 7.50
        assert result.provider == "openai"

    def test_calculate_cost_claude(self):
        """Should calculate cost for Claude correctly."""
        result = self.calculator.calculate_cost("claude-3-5-sonnet-20241022", 1000000, 1000000)

        # Claude 3.5 Sonnet: $3.00 per 1M input, $15.00 per 1M output
        assert result.input_cost_usd == 3.00
        assert result.output_cost_usd == 15.00
        assert result.total_cost_usd == 18.00
        assert result.provider == "anthropic"

    def test_calculate_cost_small_tokens(self):
        """Should calculate cost for small token counts."""
        result = self.calculator.calculate_cost("gpt-4o", 100, 50)

        # Small amounts should have small costs
        assert result.total_tokens == 150
        assert result.total_cost_usd < 0.01
        assert result.total_cost_usd > 0

    def test_calculate_cost_zero_tokens(self):
        """Should handle zero tokens."""
        result = self.calculator.calculate_cost("gpt-4o", 0, 0)

        assert result.total_tokens == 0
        assert result.total_cost_usd == 0.0

    def test_calculate_cost_unknown_model(self):
        """Should return zero cost for unknown models."""
        result = self.calculator.calculate_cost("unknown-model", 1000, 500)

        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.total_cost_usd == 0.0
        assert result.provider == "unknown"

    def test_calculate_cost_via_alias(self):
        """Should calculate cost correctly via alias."""
        result = self.calculator.calculate_cost("claude-3-5-sonnet-latest", 1000000, 0)

        assert result.input_cost_usd == 3.00
        assert result.model == "claude-3-5-sonnet-20241022"

    def test_calculate_cost_rounding(self):
        """Should round costs appropriately."""
        result = self.calculator.calculate_cost("gpt-4o", 123, 456)

        # Should be rounded to 6 decimal places
        assert len(str(result.total_cost_usd).split(".")[-1]) <= 6

    # Trace Cost Calculation Tests
    def test_calculate_trace_cost_single_span(self):
        """Should calculate cost for single span trace."""
        spans = [
            {"model": "gpt-4o", "input_tokens": 1000, "output_tokens": 500}
        ]
        result = self.calculator.calculate_trace_cost(spans)

        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.total_cost_usd > 0

    def test_calculate_trace_cost_multiple_spans(self):
        """Should aggregate costs across multiple spans."""
        spans = [
            {"model": "gpt-4o", "input_tokens": 1000, "output_tokens": 500},
            {"model": "gpt-4o", "input_tokens": 2000, "output_tokens": 1000},
        ]
        result = self.calculator.calculate_trace_cost(spans)

        assert result.input_tokens == 3000
        assert result.output_tokens == 1500
        assert result.total_tokens == 4500

    def test_calculate_trace_cost_different_models(self):
        """Should handle multiple different models."""
        spans = [
            {"model": "gpt-4o", "input_tokens": 1000, "output_tokens": 500},
            {"model": "claude-3-5-sonnet-20241022", "input_tokens": 1000, "output_tokens": 500},
        ]
        result = self.calculator.calculate_trace_cost(spans)

        assert result.input_tokens == 2000
        assert result.output_tokens == 1000
        assert "gpt-4o" in result.model
        assert "claude-3-5-sonnet-20241022" in result.model
        assert "openai" in result.provider
        assert "anthropic" in result.provider

    def test_calculate_trace_cost_empty_spans(self):
        """Should handle empty span list."""
        result = self.calculator.calculate_trace_cost([])

        assert result.total_tokens == 0
        assert result.total_cost_usd == 0.0

    def test_calculate_trace_cost_alternative_token_keys(self):
        """Should handle alternative token key names."""
        spans = [
            {"model": "gpt-4o", "prompt_tokens": 1000, "completion_tokens": 500}
        ]
        result = self.calculator.calculate_trace_cost(spans)

        assert result.input_tokens == 1000
        assert result.output_tokens == 500

    def test_calculate_trace_cost_missing_tokens(self):
        """Should handle missing token counts."""
        spans = [
            {"model": "gpt-4o"}
        ]
        result = self.calculator.calculate_trace_cost(spans)

        assert result.total_tokens == 0

    def test_calculate_trace_cost_mixed_token_keys(self):
        """Should handle mixed token key formats."""
        spans = [
            {"model": "gpt-4o", "input_tokens": 1000, "output_tokens": 500},
            {"model": "claude-3-5-sonnet-20241022", "prompt_tokens": 2000, "completion_tokens": 1000},
        ]
        result = self.calculator.calculate_trace_cost(spans)

        assert result.input_tokens == 3000
        assert result.output_tokens == 1500

    # Context Window Tests
    def test_get_context_window_known_model(self):
        """Should return correct context window for known models."""
        window = self.calculator.get_context_window("gpt-4o")
        assert window == 128000

    def test_get_context_window_gemini(self):
        """Should return large context window for Gemini."""
        window = self.calculator.get_context_window("gemini-1.5-pro")
        assert window == 2000000

    def test_get_context_window_unknown_model(self):
        """Should return default for unknown models."""
        window = self.calculator.get_context_window("unknown-model")
        assert window == 128000  # Default fallback

    # List Models Tests
    def test_list_models_returns_all(self):
        """Should return all models including custom."""
        self.calculator.add_custom_pricing("custom-model", ModelPricing(1.0, 2.0, 32000, "custom"))

        models = self.calculator.list_models()

        assert "gpt-4o" in models
        assert "custom-model" in models

    def test_list_models_includes_base_pricing(self):
        """Should include all base pricing models."""
        models = self.calculator.list_models()

        for model in LLM_PRICING_2025:
            assert model in models

    # Custom Pricing Tests
    def test_add_custom_pricing_new_model(self):
        """Should add custom pricing for new model."""
        custom = ModelPricing(5.0, 10.0, 64000, "custom_provider")
        self.calculator.add_custom_pricing("my-new-model", custom)

        pricing = self.calculator.get_pricing("my-new-model")
        assert pricing.input_per_1m == 5.0
        assert pricing.output_per_1m == 10.0

    def test_add_custom_pricing_override(self):
        """Custom pricing should override resolved model."""
        custom = ModelPricing(0.01, 0.01, 1000, "test")
        self.calculator.add_custom_pricing("gpt-4o", custom)

        pricing = self.calculator.get_pricing("gpt-4o")
        assert pricing.input_per_1m == 0.01  # Overridden

    # Global Calculator Instance Tests
    def test_global_calculator_exists(self):
        """Global calculator instance should exist."""
        assert cost_calculator is not None
        assert isinstance(cost_calculator, CostCalculator)

    def test_global_calculator_has_pricing(self):
        """Global calculator should have pricing data."""
        pricing = cost_calculator.get_pricing("gpt-4o")
        assert pricing is not None


class TestSpecificModels:
    """Tests for specific model pricing accuracy."""

    def setup_method(self):
        self.calculator = CostCalculator()

    def test_openai_o1_pricing(self):
        """Should have correct O1 pricing."""
        result = self.calculator.calculate_cost("o1", 1000000, 1000000)
        assert result.input_cost_usd == 15.00
        assert result.output_cost_usd == 60.00

    def test_openai_o1_pro_pricing(self):
        """Should have correct O1 Pro pricing."""
        result = self.calculator.calculate_cost("o1-pro", 1000000, 1000000)
        assert result.input_cost_usd == 150.00
        assert result.output_cost_usd == 600.00

    def test_deepseek_pricing(self):
        """Should have DeepSeek pricing."""
        result = self.calculator.calculate_cost("deepseek-v3", 1000000, 1000000)
        assert result.input_cost_usd == 0.27
        assert result.output_cost_usd == 1.10
        assert result.provider == "deepseek"

    def test_gemini_flash_pricing(self):
        """Should have correct Gemini Flash pricing."""
        result = self.calculator.calculate_cost("gemini-1.5-flash", 1000000, 1000000)
        assert result.input_cost_usd == 0.075
        assert result.output_cost_usd == 0.30
        assert result.provider == "google"

    def test_mistral_pricing(self):
        """Should have Mistral pricing."""
        result = self.calculator.calculate_cost("mistral-large", 1000000, 1000000)
        assert result.input_cost_usd == 2.00
        assert result.output_cost_usd == 6.00
        assert result.provider == "mistral"

    def test_cohere_pricing(self):
        """Should have Cohere pricing."""
        result = self.calculator.calculate_cost("command-r-plus", 1000000, 1000000)
        assert result.input_cost_usd == 2.50
        assert result.output_cost_usd == 10.00
        assert result.provider == "cohere"

    def test_llama_pricing(self):
        """Should have Llama pricing."""
        result = self.calculator.calculate_cost("llama-3.1-405b", 1000000, 1000000)
        assert result.input_cost_usd == 3.00
        assert result.output_cost_usd == 3.00
        assert result.provider == "meta"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def setup_method(self):
        self.calculator = CostCalculator()

    def test_negative_tokens_handled(self):
        """Should handle negative tokens (defensive)."""
        result = self.calculator.calculate_cost("gpt-4o", -100, -50)
        # Should not crash, may produce negative cost
        assert isinstance(result.total_cost_usd, float)

    def test_very_large_token_count(self):
        """Should handle very large token counts."""
        result = self.calculator.calculate_cost("gpt-4o", 100000000, 100000000)
        assert result.total_cost_usd > 0
        assert result.total_tokens == 200000000

    def test_empty_model_string(self):
        """Should handle empty model string."""
        result = self.calculator.calculate_cost("", 1000, 500)
        # Empty string may fuzzy-match to a model, so just ensure it doesn't crash
        assert isinstance(result.provider, str)
        assert result.total_tokens == 1500

    def test_span_with_none_values(self):
        """Should handle spans with None token values."""
        spans = [
            {"model": "gpt-4o", "input_tokens": None, "output_tokens": None}
        ]
        result = self.calculator.calculate_trace_cost(spans)
        assert result.total_tokens == 0

    def test_span_missing_model(self):
        """Should handle spans without model field."""
        spans = [
            {"input_tokens": 1000, "output_tokens": 500}
        ]
        result = self.calculator.calculate_trace_cost(spans)
        # Should use "unknown" model
        assert result.total_tokens == 1500
