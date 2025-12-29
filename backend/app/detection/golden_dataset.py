"""Golden dataset for detection validation and calibration."""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone

from app.detection.validation import DetectionType, LabeledSample, DetectionPrediction


@dataclass
class GoldenDatasetEntry:
    """A single entry in the golden dataset."""
    id: str
    detection_type: DetectionType
    input_data: Dict[str, Any]
    expected_detected: bool
    expected_confidence_min: float = 0.0
    expected_confidence_max: float = 1.0
    description: str = ""
    source: str = "manual"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: List[str] = field(default_factory=list)
    
    def to_labeled_sample(self) -> LabeledSample:
        return LabeledSample(
            sample_id=self.id,
            detection_type=self.detection_type,
            input_data=self.input_data,
            ground_truth=self.expected_detected,
            ground_truth_confidence=(self.expected_confidence_min + self.expected_confidence_max) / 2,
            metadata={
                "description": self.description,
                "source": self.source,
                "tags": self.tags,
            },
        )


class GoldenDataset:
    """Manages a golden dataset for detection validation."""
    
    def __init__(self, dataset_path: Optional[Path] = None):
        self.entries: Dict[str, GoldenDatasetEntry] = {}
        self.dataset_path = dataset_path
        if dataset_path and dataset_path.exists():
            self.load(dataset_path)
    
    def add_entry(self, entry: GoldenDatasetEntry) -> None:
        self.entries[entry.id] = entry
    
    def remove_entry(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            return True
        return False
    
    def get_entries_by_type(self, detection_type: DetectionType) -> List[GoldenDatasetEntry]:
        return [e for e in self.entries.values() if e.detection_type == detection_type]
    
    def get_entries_by_tag(self, tag: str) -> List[GoldenDatasetEntry]:
        return [e for e in self.entries.values() if tag in e.tags]
    
    def to_labeled_samples(self) -> List[LabeledSample]:
        return [e.to_labeled_sample() for e in self.entries.values()]
    
    def save(self, path: Optional[Path] = None) -> None:
        save_path = path or self.dataset_path
        if not save_path:
            raise ValueError("No path specified for saving")
        
        data = {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entries": [
                {
                    **asdict(e),
                    "detection_type": e.detection_type.value,
                }
                for e in self.entries.values()
            ],
        }
        
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def load(self, path: Path) -> None:
        with open(path) as f:
            data = json.load(f)
        
        for entry_data in data.get("entries", []):
            entry_data["detection_type"] = DetectionType(entry_data["detection_type"])
            entry = GoldenDatasetEntry(**entry_data)
            self.entries[entry.id] = entry
    
    def summary(self) -> Dict[str, Any]:
        by_type = {}
        for dt in DetectionType:
            entries = self.get_entries_by_type(dt)
            if entries:
                positive = sum(1 for e in entries if e.expected_detected)
                by_type[dt.value] = {
                    "total": len(entries),
                    "positive": positive,
                    "negative": len(entries) - positive,
                }
        
        return {
            "total_entries": len(self.entries),
            "by_type": by_type,
        }


LOOP_DETECTION_SAMPLES = [
    GoldenDatasetEntry(
        id="loop_001",
        detection_type=DetectionType.LOOP,
        input_data={
            "states": [
                {"agent_id": "agent1", "content": "Searching for hotels in Paris", "state_delta": {"query": "hotels paris"}},
                {"agent_id": "agent1", "content": "Looking for accommodations in Paris", "state_delta": {"query": "hotels paris"}},
                {"agent_id": "agent1", "content": "Finding places to stay in Paris", "state_delta": {"query": "hotels paris"}},
                {"agent_id": "agent1", "content": "Searching for Paris hotels", "state_delta": {"query": "hotels paris"}},
            ],
        },
        expected_detected=True,
        expected_confidence_min=0.7,
        expected_confidence_max=0.95,
        description="Semantic loop with slightly different phrasing",
        tags=["semantic", "clear_positive"],
    ),
    GoldenDatasetEntry(
        id="loop_002",
        detection_type=DetectionType.LOOP,
        input_data={
            "states": [
                {"agent_id": "agent1", "content": "Analyzing Q1 financial data", "state_delta": {"step": 1}},
                {"agent_id": "agent1", "content": "Creating visualizations for Q1", "state_delta": {"step": 2}},
                {"agent_id": "agent1", "content": "Writing summary report for Q1", "state_delta": {"step": 3}},
                {"agent_id": "agent1", "content": "Sending report to stakeholders", "state_delta": {"step": 4}},
            ],
        },
        expected_detected=False,
        expected_confidence_min=0.0,
        expected_confidence_max=0.3,
        description="Clear progression with distinct steps",
        tags=["progression", "clear_negative"],
    ),
    GoldenDatasetEntry(
        id="loop_003",
        detection_type=DetectionType.LOOP,
        input_data={
            "states": [
                {"agent_id": "agent1", "content": "Error: API rate limit exceeded. Retrying...", "state_delta": {"retry": 1}},
                {"agent_id": "agent1", "content": "Error: API rate limit exceeded. Retrying...", "state_delta": {"retry": 2}},
                {"agent_id": "agent1", "content": "Error: API rate limit exceeded. Retrying...", "state_delta": {"retry": 3}},
            ],
        },
        expected_detected=True,
        expected_confidence_min=0.85,
        expected_confidence_max=0.99,
        description="Exact repetition - error loop",
        tags=["structural", "error_loop", "clear_positive"],
    ),
]

PERSONA_DETECTION_SAMPLES = [
    GoldenDatasetEntry(
        id="persona_001",
        detection_type=DetectionType.PERSONA_DRIFT,
        input_data={
            "agent": {
                "id": "legal_assistant",
                "persona_description": "A professional legal assistant that helps with contract review and legal document analysis",
            },
            "output": "I've analyzed the contract and found three key clauses requiring attention: the liability limitation in Section 4.2, the termination conditions in Section 7, and the intellectual property rights defined in Section 9.",
        },
        expected_detected=False,
        expected_confidence_min=0.0,
        expected_confidence_max=0.3,
        description="Output matches legal persona well",
        tags=["consistent", "clear_negative"],
    ),
    GoldenDatasetEntry(
        id="persona_002",
        detection_type=DetectionType.PERSONA_DRIFT,
        input_data={
            "agent": {
                "id": "legal_assistant",
                "persona_description": "A professional legal assistant that helps with contract review and legal document analysis",
            },
            "output": "OMG this pizza is amazing! I love summer vibes and going to the beach. What's your favorite color?",
        },
        expected_detected=True,
        expected_confidence_min=0.7,
        expected_confidence_max=0.95,
        description="Completely off-persona casual output",
        tags=["drift", "clear_positive"],
    ),
]

HALLUCINATION_DETECTION_SAMPLES = [
    GoldenDatasetEntry(
        id="hallucination_001",
        detection_type=DetectionType.HALLUCINATION,
        input_data={
            "sources": [
                {"content": "The company was founded in 2020 in San Francisco by John Smith."},
                {"content": "The product has 500 active users as of December 2024."},
            ],
            "output": "The company was established in 2020 in the San Francisco Bay Area.",
        },
        expected_detected=False,
        expected_confidence_min=0.0,
        expected_confidence_max=0.4,
        description="Output is grounded in provided sources",
        tags=["grounded", "clear_negative"],
    ),
    GoldenDatasetEntry(
        id="hallucination_002",
        detection_type=DetectionType.HALLUCINATION,
        input_data={
            "sources": [
                {"content": "The company was founded in 2020 in San Francisco by John Smith."},
            ],
            "output": "According to a 2019 study by Dr. Jane Williams at Harvard, the company has expanded to 47 countries with revenue exceeding $5 billion.",
        },
        expected_detected=True,
        expected_confidence_min=0.6,
        expected_confidence_max=0.95,
        description="Fabricated statistics and citations",
        tags=["fabricated", "clear_positive"],
    ),
]


def create_default_golden_dataset() -> GoldenDataset:
    """Create a golden dataset with default samples."""
    dataset = GoldenDataset()
    
    for sample in LOOP_DETECTION_SAMPLES:
        dataset.add_entry(sample)
    
    for sample in PERSONA_DETECTION_SAMPLES:
        dataset.add_entry(sample)
    
    for sample in HALLUCINATION_DETECTION_SAMPLES:
        dataset.add_entry(sample)
    
    return dataset


def get_golden_dataset_path() -> Path:
    """Get the default path for the golden dataset."""
    return Path(__file__).parent.parent.parent / "data" / "golden_dataset.json"
