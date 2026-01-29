"""State corruption detection scenario generator."""

import random
from benchmarks.generators.moltbot.generator import GoldenMetadata


class CorruptionScenarioGenerator:
    """Generate state corruption scenarios."""

    def generate_positive(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate state corruption (should detect)."""
        if variant == "memory_conflict":
            # Conflicting values for same preference
            memory_ops = [
                {"op": "write", "key": "timezone", "value": "America/New_York", "timestamp": 0.0},
                {"op": "write", "key": "timezone", "value": "America/Los_Angeles", "timestamp": 1.0},
                {"op": "read", "key": "timezone", "value": "America/New_York", "timestamp": 2.0},  # Old value returned
            ]
        else:  # state_regression
            memory_ops = [
                {"op": "set_state", "state": "greeting", "timestamp": 0.0},
                {"op": "set_state", "state": "task_execution", "timestamp": 1.0},
                {"op": "set_state", "state": "greeting", "timestamp": 2.0},  # Regressed to earlier state
            ]

        input_data = {
            "task": "Manage user preferences",
            "operations": memory_ops,
            "trace_id": f"corrupt_{variant}_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="corruption",
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.88,
            description=f"State {variant} on {channel}",
            variant=variant,
            tags=["corruption", variant, "state_error"],
        )

        return input_data, metadata

    def generate_negative(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate valid state management (should not detect)."""
        memory_ops = [
            {"op": "write", "key": "timezone", "value": "America/New_York", "timestamp": 0.0},
            {"op": "read", "key": "timezone", "value": "America/New_York", "timestamp": 1.0},
            {"op": "write", "key": "timezone", "value": "America/Los_Angeles", "timestamp": 2.0},
            {"op": "read", "key": "timezone", "value": "America/Los_Angeles", "timestamp": 3.0},
        ]

        input_data = {
            "task": "Manage user preferences",
            "operations": memory_ops,
            "trace_id": f"corrupt_valid_{random.randint(1000, 9999)}",
        }

        metadata = GoldenMetadata(
            detection_type="corruption",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description=f"Valid state management on {channel}",
            variant=variant,
            tags=["corruption", "valid", "consistent"],
        )

        return input_data, metadata
