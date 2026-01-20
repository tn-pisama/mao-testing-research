"""Unit tests for golden dataset functionality."""

import pytest
import tempfile
from pathlib import Path

from app.detection_enterprise.golden_dataset import (
    GoldenDataset,
    GoldenDatasetEntry,
    create_default_golden_dataset,
    LOOP_DETECTION_SAMPLES,
    PERSONA_DETECTION_SAMPLES,
    HALLUCINATION_DETECTION_SAMPLES,
)
from app.detection.validation import DetectionType


class TestGoldenDatasetEntry:
    def test_create_entry(self):
        entry = GoldenDatasetEntry(
            id="test_001",
            detection_type=DetectionType.LOOP,
            input_data={"states": []},
            expected_detected=True,
        )
        assert entry.id == "test_001"
        assert entry.detection_type == DetectionType.LOOP
        assert entry.expected_detected is True
    
    def test_to_labeled_sample(self):
        entry = GoldenDatasetEntry(
            id="test_002",
            detection_type=DetectionType.PERSONA_DRIFT,
            input_data={"agent": {}, "output": "test"},
            expected_detected=False,
            expected_confidence_min=0.1,
            expected_confidence_max=0.3,
            description="Test sample",
            tags=["test"],
        )
        
        sample = entry.to_labeled_sample()
        
        assert sample.sample_id == "test_002"
        assert sample.detection_type == DetectionType.PERSONA_DRIFT
        assert sample.ground_truth is False
        assert sample.ground_truth_confidence == 0.2
        assert sample.metadata["description"] == "Test sample"


class TestGoldenDataset:
    def test_create_empty_dataset(self):
        dataset = GoldenDataset()
        assert len(dataset.entries) == 0
    
    def test_add_entry(self):
        dataset = GoldenDataset()
        entry = GoldenDatasetEntry(
            id="test_001",
            detection_type=DetectionType.LOOP,
            input_data={},
            expected_detected=True,
        )
        
        dataset.add_entry(entry)
        
        assert len(dataset.entries) == 1
        assert "test_001" in dataset.entries
    
    def test_remove_entry(self):
        dataset = GoldenDataset()
        entry = GoldenDatasetEntry(
            id="test_001",
            detection_type=DetectionType.LOOP,
            input_data={},
            expected_detected=True,
        )
        dataset.add_entry(entry)
        
        result = dataset.remove_entry("test_001")
        
        assert result is True
        assert len(dataset.entries) == 0
    
    def test_remove_nonexistent_entry(self):
        dataset = GoldenDataset()
        result = dataset.remove_entry("nonexistent")
        assert result is False
    
    def test_get_entries_by_type(self):
        dataset = GoldenDataset()
        
        loop_entry = GoldenDatasetEntry(
            id="loop_001",
            detection_type=DetectionType.LOOP,
            input_data={},
            expected_detected=True,
        )
        persona_entry = GoldenDatasetEntry(
            id="persona_001",
            detection_type=DetectionType.PERSONA_DRIFT,
            input_data={},
            expected_detected=False,
        )
        
        dataset.add_entry(loop_entry)
        dataset.add_entry(persona_entry)
        
        loop_entries = dataset.get_entries_by_type(DetectionType.LOOP)
        assert len(loop_entries) == 1
        assert loop_entries[0].id == "loop_001"
    
    def test_get_entries_by_tag(self):
        dataset = GoldenDataset()
        
        entry1 = GoldenDatasetEntry(
            id="test_001",
            detection_type=DetectionType.LOOP,
            input_data={},
            expected_detected=True,
            tags=["semantic", "positive"],
        )
        entry2 = GoldenDatasetEntry(
            id="test_002",
            detection_type=DetectionType.LOOP,
            input_data={},
            expected_detected=False,
            tags=["structural", "negative"],
        )
        
        dataset.add_entry(entry1)
        dataset.add_entry(entry2)
        
        semantic_entries = dataset.get_entries_by_tag("semantic")
        assert len(semantic_entries) == 1
        assert semantic_entries[0].id == "test_001"
    
    def test_to_labeled_samples(self):
        dataset = GoldenDataset()
        
        for i in range(3):
            entry = GoldenDatasetEntry(
                id=f"test_{i}",
                detection_type=DetectionType.LOOP,
                input_data={},
                expected_detected=i % 2 == 0,
            )
            dataset.add_entry(entry)
        
        samples = dataset.to_labeled_samples()
        assert len(samples) == 3
    
    def test_save_and_load(self):
        dataset = GoldenDataset()
        
        entry = GoldenDatasetEntry(
            id="test_001",
            detection_type=DetectionType.LOOP,
            input_data={"states": [{"content": "test"}]},
            expected_detected=True,
            description="Test entry",
            tags=["test"],
        )
        dataset.add_entry(entry)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_dataset.json"
            dataset.save(path)
            
            loaded_dataset = GoldenDataset(path)
            
            assert len(loaded_dataset.entries) == 1
            loaded_entry = loaded_dataset.entries["test_001"]
            assert loaded_entry.detection_type == DetectionType.LOOP
            assert loaded_entry.expected_detected is True
            assert loaded_entry.description == "Test entry"
    
    def test_summary(self):
        dataset = create_default_golden_dataset()
        summary = dataset.summary()
        
        assert summary["total_entries"] > 0
        assert "by_type" in summary
        assert "loop" in summary["by_type"]


class TestDefaultSamples:
    def test_loop_samples_exist(self):
        assert len(LOOP_DETECTION_SAMPLES) >= 3
    
    def test_persona_samples_exist(self):
        assert len(PERSONA_DETECTION_SAMPLES) >= 2
    
    def test_hallucination_samples_exist(self):
        assert len(HALLUCINATION_DETECTION_SAMPLES) >= 2
    
    def test_create_default_dataset(self):
        dataset = create_default_golden_dataset()
        
        assert len(dataset.entries) > 0
        
        loop_entries = dataset.get_entries_by_type(DetectionType.LOOP)
        assert len(loop_entries) >= 3
        
        persona_entries = dataset.get_entries_by_type(DetectionType.PERSONA_DRIFT)
        assert len(persona_entries) >= 2
    
    def test_default_samples_have_valid_structure(self):
        dataset = create_default_golden_dataset()
        
        for entry in dataset.entries.values():
            assert entry.id is not None
            assert entry.detection_type is not None
            assert entry.input_data is not None
            assert isinstance(entry.expected_detected, bool)
            assert 0 <= entry.expected_confidence_min <= 1
            assert 0 <= entry.expected_confidence_max <= 1
            assert entry.expected_confidence_min <= entry.expected_confidence_max
