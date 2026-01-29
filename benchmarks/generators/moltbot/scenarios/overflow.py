"""Context overflow detection scenario generator."""

import random
from benchmarks.generators.moltbot.generator import GoldenMetadata


class OverflowScenarioGenerator:
    """Generate context overflow scenarios."""

    def generate_positive(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate context overflow (should detect)."""
        if variant == "gradual_accumulation":
            # Long conversation approaching limit
            current_tokens = 95000
            model = "claude-opus-4-5"
        else:  # sudden_spike
            # Sudden large context addition
            current_tokens = 110000
            model = "gpt-4o"

        input_data = {
            "current_tokens": current_tokens,
            "model": model,
            "max_context": 100000 if "gpt" in model else 200000,
            "trace_id": f"overflow_{variant}_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="overflow",
            expected_detected=True,
            expected_confidence_min=0.80,
            expected_confidence_max=0.95,
            description=f"Context {variant} on {channel}",
            variant=variant,
            tags=["overflow", variant, model],
        )

        return input_data, metadata

    def generate_negative(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate normal context usage (should not detect)."""
        input_data = {
            "current_tokens": 25000,
            "model": "claude-opus-4-5",
            "max_context": 200000,
            "trace_id": f"overflow_normal_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="overflow",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.15,
            description=f"Normal context usage on {channel}",
            variant=variant,
            tags=["overflow", "normal", "safe_margin"],
        )

        return input_data, metadata
