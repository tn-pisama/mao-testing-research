"""Main Moltbot trace generator for creating golden dataset."""

import json
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from pisama_core.traces.enums import Platform, SpanKind, SpanStatus
from pisama_core.traces.models import Event, Span, Trace, TraceMetadata


@dataclass
class GoldenMetadata:
    """Metadata for golden dataset entries."""

    detection_type: str
    expected_detected: bool
    expected_confidence_min: float
    expected_confidence_max: float
    description: str
    variant: str
    tags: list[str]


@dataclass
class GoldenDatasetEntry:
    """Golden dataset entry matching PISAMA format."""

    id: str
    detection_type: str
    input_data: dict[str, Any]
    expected_detected: bool
    expected_confidence_min: float
    expected_confidence_max: float
    description: str
    source: str  # "synthetic"
    tags: list[str]
    source_trace_id: str | None = None
    human_verified: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class ScenarioGenerator(Protocol):
    """Protocol for scenario-specific generators."""

    def generate_positive(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate a trace that should trigger detection."""
        ...

    def generate_negative(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate a trace that should NOT trigger detection."""
        ...


class MoltbotTraceGenerator:
    """Main generator orchestrating all Moltbot trace generation."""

    # Moltbot channels
    CHANNELS = [
        "whatsapp",
        "telegram",
        "slack",
        "discord",
        "signal",
        "matrix",
        "webchat",
        "imessage",
    ]

    # Detection types and their variants
    DETECTION_VARIANTS = {
        "loop": ["tool_loop", "navigation_loop", "api_retry_loop"],
        "overflow": ["gradual_accumulation", "sudden_spike"],
        "persona": ["channel_drift", "tone_shift", "role_confusion"],
        "coordination": ["missed_step", "incomplete_handoff"],
        "injection": ["direct", "indirect", "channel_based"],
        "completion": ["premature_claim", "partial_execution"],
        "corruption": ["memory_conflict", "state_regression"],
        "hallucination": ["tool_result_fabrication", "context_invention"],
    }

    def __init__(self):
        """Initialize generator."""
        self.scenarios: dict[str, ScenarioGenerator] = {}

    def register_scenario(self, detection_type: str, generator: ScenarioGenerator):
        """Register a scenario generator."""
        self.scenarios[detection_type] = generator

    def generate_golden_dataset(
        self, n_samples: int = 200, balanced: bool = True
    ) -> list[GoldenDatasetEntry]:
        """Generate complete golden dataset.

        Args:
            n_samples: Total number of samples to generate
            balanced: Whether to balance positive/negative samples

        Returns:
            List of GoldenDatasetEntry objects
        """
        entries = []
        samples_per_detector = n_samples // len(self.DETECTION_VARIANTS)

        for detection_type, variants in self.DETECTION_VARIANTS.items():
            if detection_type not in self.scenarios:
                print(f"Warning: No scenario generator for {detection_type}")
                continue

            generator = self.scenarios[detection_type]
            samples_per_variant = samples_per_detector // len(variants)

            for variant in variants:
                # Generate positive samples
                pos_samples = samples_per_variant // 2 if balanced else samples_per_variant
                for i in range(pos_samples):
                    channel = random.choice(self.CHANNELS)
                    input_data, metadata = generator.generate_positive(variant, channel)

                    entry = GoldenDatasetEntry(
                        id=f"moltbot_{detection_type}_{variant}_{i:03d}_pos",
                        detection_type=detection_type.upper(),
                        input_data=input_data,
                        expected_detected=metadata.expected_detected,
                        expected_confidence_min=metadata.expected_confidence_min,
                        expected_confidence_max=metadata.expected_confidence_max,
                        description=f"{metadata.description} (channel: {channel})",
                        source="synthetic",
                        tags=["moltbot", detection_type, variant, channel] + metadata.tags,
                        source_trace_id=input_data.get("trace_id"),
                        human_verified=False,
                    )
                    entries.append(entry)

                # Generate negative samples
                if balanced:
                    neg_samples = samples_per_variant - pos_samples
                    for i in range(neg_samples):
                        channel = random.choice(self.CHANNELS)
                        input_data, metadata = generator.generate_negative(variant, channel)

                        entry = GoldenDatasetEntry(
                            id=f"moltbot_{detection_type}_{variant}_{i:03d}_neg",
                            detection_type=detection_type.upper(),
                            input_data=input_data,
                            expected_detected=metadata.expected_detected,
                            expected_confidence_min=metadata.expected_confidence_min,
                            expected_confidence_max=metadata.expected_confidence_max,
                            description=f"{metadata.description} (channel: {channel})",
                            source="synthetic",
                            tags=["moltbot", detection_type, variant, channel, "negative"]
                            + metadata.tags,
                            source_trace_id=input_data.get("trace_id"),
                            human_verified=False,
                        )
                        entries.append(entry)

        return entries

    def generate_pisama_traces(self, n_samples: int = 200) -> list[Trace]:
        """Generate pisama-core Trace objects.

        Args:
            n_samples: Number of traces to generate

        Returns:
            List of Trace objects
        """
        # This will generate Trace objects using pisama_core
        # For now, return empty list as placeholder
        return []

    def save_golden_dataset(self, entries: list[GoldenDatasetEntry], output_path: str):
        """Save golden dataset to JSONL file.

        Args:
            entries: List of golden dataset entries
            output_path: Path to output file
        """
        with open(output_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry.to_dict()) + "\n")

    @staticmethod
    def _generate_trace_id() -> str:
        """Generate a unique trace ID."""
        return uuid4().hex[:16]

    @staticmethod
    def _generate_span_id() -> str:
        """Generate a unique span ID."""
        return uuid4().hex[:8]

    @staticmethod
    def _now() -> datetime:
        """Get current UTC timestamp."""
        return datetime.now(timezone.utc)
