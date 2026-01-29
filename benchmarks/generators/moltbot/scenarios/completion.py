"""Completion detection scenario generator."""

import random
from datetime import datetime, timedelta

from benchmarks.generators.moltbot.generator import GoldenMetadata
from benchmarks.generators.moltbot.templates.messages import get_user_message, get_agent_message
from benchmarks.generators.moltbot.templates.tools import get_tool_call, get_tool_result
from benchmarks.generators.moltbot.templates.channels import format_for_channel


class CompletionScenarioGenerator:
    """Generate premature/delayed completion scenarios."""

    def generate_positive(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate premature completion (should detect)."""
        if variant == "premature_claim":
            return self._generate_premature_claim(channel)
        else:  # partial_execution
            return self._generate_partial_execution(channel)

    def generate_negative(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate complete execution (should not detect)."""
        return self._generate_complete_execution(channel, variant)

    def _generate_premature_claim(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Agent claims done but task incomplete."""
        user_msg = format_for_channel(
            "Turn off all lights, lock the doors, and set thermostat to 68F",
            channel,
            is_user=True,
        )

        # Only 2 of 3 tasks completed
        messages = [
            {"from_agent": "smart_home", "content": user_msg, "timestamp": 0.0},
            {"from_agent": "smart_home", "content": "Turning off lights...", "timestamp": 1.0},
            {"from_agent": "smart_home", "content": "Locking doors...", "timestamp": 2.0},
            {
                "from_agent": "smart_home",
                "content": format_for_channel("All done! Lights off and doors locked.", channel, False),
                "timestamp": 3.0,
                "completion_indicators": ["done", "all"],
            },
        ]

        input_data = {
            "messages": messages,
            "requested_actions": ["lights_off", "lock_doors", "set_thermostat"],
            "completed_actions": ["lights_off", "lock_doors"],
            "trace_id": f"comp_premature_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="completion",
            expected_detected=True,
            expected_confidence_min=0.80,
            expected_confidence_max=0.95,
            description=f"Premature completion claim on {channel}",
            variant="premature_claim",
            tags=["smart_home", "incomplete", "false_claim"],
        )

        return input_data, metadata

    def _generate_partial_execution(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Agent executes only part of multi-step task."""
        messages = [
            {
                "from_agent": "calendar",
                "content": format_for_channel(
                    "Schedule meeting with John at 2pm and send confirmation email", channel, True
                ),
                "timestamp": 0.0,
            },
            {"from_agent": "calendar", "content": "Creating calendar event...", "timestamp": 1.0},
            {
                "from_agent": "calendar",
                "content": format_for_channel("Meeting scheduled!", channel, False),
                "timestamp": 2.0,
            },
        ]

        input_data = {
            "messages": messages,
            "requested_actions": ["schedule_meeting", "send_email"],
            "completed_actions": ["schedule_meeting"],
            "trace_id": f"comp_partial_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="completion",
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.90,
            description=f"Partial task execution on {channel}",
            variant="partial_execution",
            tags=["calendar", "email", "forgotten_step"],
        )

        return input_data, metadata

    def _generate_complete_execution(self, channel: str, variant: str) -> tuple[dict, GoldenMetadata]:
        """Complete execution of all requested actions."""
        messages = [
            {
                "from_agent": "smart_home",
                "content": format_for_channel("Turn off lights and lock doors", channel, True),
                "timestamp": 0.0,
            },
            {"from_agent": "smart_home", "content": "Turning off lights...", "timestamp": 1.0},
            {"from_agent": "smart_home", "content": "Locking doors...", "timestamp": 2.0},
            {
                "from_agent": "smart_home",
                "content": format_for_channel("Done! Lights off and doors locked.", channel, False),
                "timestamp": 3.0,
            },
        ]

        input_data = {
            "messages": messages,
            "requested_actions": ["lights_off", "lock_doors"],
            "completed_actions": ["lights_off", "lock_doors"],
            "trace_id": f"comp_complete_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="completion",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description=f"Complete task execution on {channel}",
            variant=variant,
            tags=["smart_home", "complete", "all_actions"],
        )

        return input_data, metadata
