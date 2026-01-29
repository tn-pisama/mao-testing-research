"""Coordination failure scenario generator."""

import random
from benchmarks.generators.moltbot.generator import GoldenMetadata


class CoordinationScenarioGenerator:
    """Generate coordination failure scenarios."""

    def generate_positive(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate coordination failure (should detect)."""
        if variant == "missed_step":
            # Calendar event created but email not sent
            messages = [
                {"from_agent": "coordinator", "to_agent": "calendar", "content": "Create event", "acknowledged": True},
                {"from_agent": "coordinator", "to_agent": "email", "content": "Send confirmation", "acknowledged": False},
            ]
        else:  # incomplete_handoff
            messages = [
                {"from_agent": "agent1", "to_agent": "agent2", "content": "Handle booking", "acknowledged": True},
                {"from_agent": "agent2", "to_agent": "agent3", "content": "Confirm payment", "acknowledged": False},
            ]

        input_data = {
            "messages": messages,
            "agent_ids": ["coordinator", "calendar", "email"] if variant == "missed_step" else ["agent1", "agent2", "agent3"],
            "trace_id": f"coord_{variant}_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="coordination",
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.90,
            description=f"Coordination {variant} on {channel}",
            variant=variant,
            tags=["coordination", variant, "handoff_failure"],
        )

        return input_data, metadata

    def generate_negative(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate successful coordination (should not detect)."""
        messages = [
            {"from_agent": "coordinator", "to_agent": "calendar", "content": "Create event", "acknowledged": True},
            {"from_agent": "calendar", "to_agent": "coordinator", "content": "Event created", "acknowledged": True},
            {"from_agent": "coordinator", "to_agent": "email", "content": "Send confirmation", "acknowledged": True},
            {"from_agent": "email", "to_agent": "coordinator", "content": "Email sent", "acknowledged": True},
        ]

        input_data = {
            "messages": messages,
            "agent_ids": ["coordinator", "calendar", "email"],
            "trace_id": f"coord_success_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="coordination",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description=f"Successful coordination on {channel}",
            variant=variant,
            tags=["coordination", "success", "complete_handoff"],
        )

        return input_data, metadata
