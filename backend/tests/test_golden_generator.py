"""Tests for golden data generator."""

import pytest
from pathlib import Path
from app.detection.validation import DetectionType
from app.detection_enterprise.golden_generator import GoldenDataGenerator
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry


class TestGoldenDataGenerator:
    def test_workflow_to_golden_entry(self):
        """Test conversion of workflow to golden entry."""
        generator = GoldenDataGenerator()

        workflow_data = {
            "name": "Test Workflow",
            "nodes": [
                {"type": "n8n-nodes-base.start", "name": "Start", "parameters": {}},
                {"type": "n8n-nodes-langchain.agent", "name": "Agent", "parameters": {"model": "claude"}},
            ],
        }

        entry = generator._workflow_to_golden_entry(
            workflow_id="test_001",
            workflow_data=workflow_data,
            detection_type=DetectionType.LOOP,
            expected_detected=True,
            source="test",
            tags=["unit_test"],
        )

        assert entry.id.startswith("test_LOOP_test_001")
        assert entry.detection_type == DetectionType.LOOP
        assert entry.expected_detected is True
        assert "test" in entry.tags
        assert entry.source_workflow_id == "test_001"

    def test_analyze_workflow_structure(self):
        """Test workflow structure analysis."""
        generator = GoldenDataGenerator()

        # Test circular dependency detection
        workflow_with_cycle = {
            "nodes": [
                {"name": "node1"},
                {"name": "node2"},
            ],
            "connections": {
                "node1": {"main": [[{"node": "node2"}]]},
                "node2": {"main": [[{"node": "node1"}]]},
            },
        }

        issues = generator._analyze_workflow_structure(workflow_with_cycle)
        assert issues["has_circular_refs"] is True
        assert issues["well_structured"] is False

    def test_create_severity_variant(self):
        """Test severity variant creation."""
        generator = GoldenDataGenerator()

        base_sample = GoldenDatasetEntry(
            id="test_001",
            detection_type=DetectionType.LOOP,
            input_data={"states": []},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.9,
            source="test",
        )

        variant = generator._create_severity_variant(base_sample, increase=True)

        assert variant is not None
        assert variant.id == "test_001_sev_inc"
        assert variant.expected_confidence_min > base_sample.expected_confidence_min
        assert "severity_variant" in variant.tags
        assert variant.augmentation_method == "severity_variation"

    def test_validate_samples(self):
        """Test sample validation."""
        generator = GoldenDataGenerator()

        samples = [
            GoldenDatasetEntry(
                id="test_001",
                detection_type=DetectionType.LOOP,
                input_data={},
                expected_detected=True,
                source="test",
            ),
            GoldenDatasetEntry(
                id="test_002",
                detection_type=DetectionType.LOOP,
                input_data={},
                expected_detected=False,
                source="test",
            ),
            GoldenDatasetEntry(
                id="test_003",
                detection_type=DetectionType.PERSONA_DRIFT,
                input_data={},
                expected_detected=True,
                source="test",
            ),
        ]

        report = generator.validate_samples(samples)

        assert report["total_samples"] == 3
        assert "loop" in report["by_type"]
        assert report["by_type"]["loop"]["total"] == 2
        assert report["by_type"]["loop"]["positive"] == 1
        assert report["by_type"]["persona_drift"]["total"] == 1
        assert "test" in report["by_source"]

    def test_augment_samples(self):
        """Test sample augmentation."""
        generator = GoldenDataGenerator()

        base_samples = [
            GoldenDatasetEntry(
                id="test_001",
                detection_type=DetectionType.LOOP,
                input_data={},
                expected_detected=True,
                source="test",
            ),
        ]

        augmented = generator.augment_samples(base_samples, multiplier=4)

        # Should create 4 variants
        assert len(augmented) == 4

        # Check augmentation methods
        methods = set(s.augmentation_method for s in augmented)
        assert "severity_variation" in methods
        assert "edge_case" in methods
        assert "noise_injection" in methods
