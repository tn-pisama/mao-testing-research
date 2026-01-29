"""Persona drift detection scenario generator."""

import random
from benchmarks.generators.moltbot.generator import GoldenMetadata
from benchmarks.generators.moltbot.templates.channels import format_for_channel


class PersonaScenarioGenerator:
    """Generate persona drift scenarios."""

    def generate_positive(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate persona drift (should detect)."""
        if variant == "channel_drift":
            # WhatsApp: casual, Slack: formal
            interactions = [
                {"channel": "whatsapp", "output": "Hey! 😊 Sure thing, I'll do that for ya!"},
                {"channel": "slack", "output": "Good afternoon. I have completed the requested task. Please find the report attached."},
            ]
        elif variant == "tone_shift":
            interactions = [
                {"channel": channel, "output": format_for_channel("I'm happy to help you with that!", channel, False)},
                {"channel": channel, "output": "I WILL PROCESS YOUR REQUEST IMMEDIATELY. STAND BY."},
            ]
        else:  # role_confusion
            interactions = [
                {"channel": channel, "output": "As your personal assistant, I'll handle that calendar event."},
                {"channel": channel, "output": "As a technical support specialist, let me troubleshoot your issue."},
            ]

        input_data = {
            "agent": {"id": "assistant", "persona_description": "Professional assistant"},
            "interactions": interactions,
            "trace_id": f"persona_{variant}_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="persona",
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.92,
            description=f"Persona {variant} on {channel}",
            variant=variant,
            tags=["persona", variant, "inconsistent"],
        )

        return input_data, metadata

    def generate_negative(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate consistent persona (should not detect)."""
        interactions = [
            {"channel": channel, "output": format_for_channel("I'll help you with that task.", channel, False)},
            {"channel": channel, "output": format_for_channel("Task completed successfully.", channel, False)},
        ]

        input_data = {
            "agent": {"id": "assistant", "persona_description": "Professional assistant"},
            "interactions": interactions,
            "trace_id": f"persona_consistent_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="persona",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.25,
            description=f"Consistent persona on {channel}",
            variant=variant,
            tags=["persona", "consistent", "valid"],
        )

        return input_data, metadata
