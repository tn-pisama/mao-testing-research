"""MAST Dataset Loader for benchmarking.

Loads MAST traces from JSONL/JSON files and parses ground truth annotations.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)


# MAST annotation code to failure mode mapping (from mast.py)
ANNOTATION_MAP = {
    # Planning failures (Category 1)
    "1.1": "F1",   # Specification Mismatch
    "1.2": "F2",   # Poor Task Decomposition
    "1.3": "F3",   # Resource Misallocation
    "1.4": "F4",   # Inadequate Tool Provision
    "1.5": "F5",   # Flawed Workflow Design
    # Execution failures (Category 2)
    "2.1": "F6",   # Task Derailment
    "2.2": "F7",   # Context Neglect
    "2.3": "F8",   # Information Withholding
    "2.4": "F9",   # Role Usurpation
    "2.5": "F10",  # Communication Breakdown
    "2.6": "F11",  # Coordination Failure
    # Verification failures (Category 3)
    "3.1": "F12",  # Output Validation Failure
    "3.2": "F13",  # Quality Gate Bypass
    "3.3": "F14",  # Completion Misjudgment
}

# All failure modes including F15/F16 for RAG
ALL_FAILURE_MODES = [f"F{i}" for i in range(1, 17)]

# Failure mode names
FAILURE_MODE_NAMES = {
    "F1": "Specification Mismatch",
    "F2": "Poor Task Decomposition",
    "F3": "Resource Misallocation",
    "F4": "Inadequate Tool Provision",
    "F5": "Flawed Workflow Design",
    "F6": "Task Derailment",
    "F7": "Context Neglect",
    "F8": "Information Withholding",
    "F9": "Role Usurpation",
    "F10": "Communication Breakdown",
    "F11": "Coordination Failure",
    "F12": "Output Validation Failure",
    "F13": "Quality Gate Bypass",
    "F14": "Completion Misjudgment",
    "F15": "Grounding Failure",
    "F16": "Retrieval Quality Failure",
}


@dataclass
class MASTRecord:
    """Parsed MAST record with ground truth annotations."""

    trace_id: str
    framework: str
    llm_name: str
    benchmark_name: str
    task: str
    trajectory: str
    ground_truth: Dict[str, bool] = field(default_factory=dict)
    raw_annotations: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_failures(self) -> bool:
        """Check if record has any failure annotations."""
        return any(self.ground_truth.values())

    @property
    def failure_modes(self) -> List[str]:
        """Get list of active failure modes."""
        return [mode for mode, active in self.ground_truth.items() if active]

    @property
    def failure_count(self) -> int:
        """Count of active failure modes."""
        return sum(1 for active in self.ground_truth.values() if active)


def parse_ground_truth(annotations: Dict[str, Any]) -> Dict[str, bool]:
    """Convert MAST annotations to failure mode flags.

    Args:
        annotations: Raw MAST annotations like {"1.1": 1, "2.3": 0}

    Returns:
        Dict mapping F1-F14 to boolean values
    """
    result = {}

    for code, mode in ANNOTATION_MAP.items():
        value = annotations.get(code, 0)
        if isinstance(value, bool):
            result[mode] = value
        elif isinstance(value, (int, float)):
            result[mode] = bool(value)
        elif isinstance(value, str):
            result[mode] = value.lower() in ("1", "true", "yes")
        else:
            result[mode] = False

    # F15 and F16 may not have MAST annotations (OfficeQA-specific)
    # Default to False unless explicitly present
    result.setdefault("F15", False)
    result.setdefault("F16", False)

    return result


class MASTDataLoader:
    """Load and iterate MAST dataset from files."""

    def __init__(self, data_path: Optional[Path] = None):
        """Initialize loader.

        Args:
            data_path: Path to JSONL or JSON file containing MAST data
        """
        self.data_path = Path(data_path) if data_path else None
        self._records: List[MASTRecord] = []
        self._loaded = False

    def load(self, data_path: Optional[Path] = None) -> int:
        """Load records from JSONL/JSON file.

        Args:
            data_path: Override data path

        Returns:
            Number of records loaded
        """
        path = Path(data_path) if data_path else self.data_path
        if not path:
            raise ValueError("No data path specified")

        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        self._records = []

        # Determine format from extension or content
        if path.suffix.lower() == ".jsonl":
            self._load_jsonl(path)
        elif path.suffix.lower() == ".json":
            self._load_json(path)
        else:
            # Try to detect format
            with open(path) as f:
                first_char = f.read(1)
                f.seek(0)
                if first_char == "[":
                    self._load_json(path)
                else:
                    self._load_jsonl(path)

        self._loaded = True
        logger.info(f"Loaded {len(self._records)} records from {path}")
        return len(self._records)

    def _load_jsonl(self, path: Path) -> None:
        """Load records from JSONL file."""
        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = self._parse_record(data)
                    if record:
                        self._records.append(record)
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: Invalid JSON - {e}")
                except Exception as e:
                    logger.warning(f"Line {line_num}: Failed to parse - {e}")

    def _load_json(self, path: Path) -> None:
        """Load records from JSON file (array or single object)."""
        with open(path) as f:
            data = json.load(f)

        if isinstance(data, list):
            for i, item in enumerate(data):
                try:
                    record = self._parse_record(item)
                    if record:
                        self._records.append(record)
                except Exception as e:
                    logger.warning(f"Record {i}: Failed to parse - {e}")
        else:
            record = self._parse_record(data)
            if record:
                self._records.append(record)

    def _parse_record(self, data: Dict[str, Any]) -> Optional[MASTRecord]:
        """Parse raw JSON data into MASTRecord."""
        # Handle different data formats
        trace_id = data.get("trace_id") or data.get("id") or ""
        framework = data.get("mas_name") or data.get("framework") or "unknown"

        # Get trajectory from nested trace object or directly
        trace_data = data.get("trace", {})
        if isinstance(trace_data, dict):
            trajectory = trace_data.get("trajectory", "")
        else:
            trajectory = str(trace_data)

        # Skip empty trajectories
        if not trajectory:
            return None

        # Parse annotations
        annotations = data.get("mast_annotation", {})
        ground_truth = parse_ground_truth(annotations)

        return MASTRecord(
            trace_id=str(trace_id),
            framework=framework,
            llm_name=data.get("llm_name", ""),
            benchmark_name=data.get("benchmark_name", ""),
            task=data.get("task", ""),
            trajectory=trajectory,
            ground_truth=ground_truth,
            raw_annotations=annotations,
        )

    def __iter__(self) -> Iterator[MASTRecord]:
        """Iterate over loaded records."""
        if not self._loaded:
            self.load()
        return iter(self._records)

    def __len__(self) -> int:
        """Return number of loaded records."""
        return len(self._records)

    def filter_by_framework(self, framework: str) -> List[MASTRecord]:
        """Filter records by MAS framework.

        Args:
            framework: Framework name (case-insensitive)

        Returns:
            List of matching records
        """
        framework_lower = framework.lower()
        return [r for r in self._records if r.framework.lower() == framework_lower]

    def filter_by_failure_modes(
        self,
        modes: List[str],
        require_all: bool = False,
    ) -> List[MASTRecord]:
        """Filter records that have specific failure modes.

        Args:
            modes: List of failure modes (e.g., ["F1", "F7"])
            require_all: If True, require all modes; if False, require any

        Returns:
            List of matching records
        """
        if require_all:
            return [
                r for r in self._records
                if all(r.ground_truth.get(m, False) for m in modes)
            ]
        else:
            return [
                r for r in self._records
                if any(r.ground_truth.get(m, False) for m in modes)
            ]

    def filter_has_failures(self, has_failures: bool = True) -> List[MASTRecord]:
        """Filter records by whether they have any failures.

        Args:
            has_failures: If True, return records with failures; if False, healthy

        Returns:
            List of matching records
        """
        return [r for r in self._records if r.has_failures == has_failures]

    def get_statistics(self) -> Dict[str, Any]:
        """Get dataset statistics.

        Returns:
            Dict with statistics about the loaded dataset
        """
        if not self._records:
            return {"total": 0}

        # Count by framework
        by_framework: Dict[str, int] = {}
        for r in self._records:
            by_framework[r.framework] = by_framework.get(r.framework, 0) + 1

        # Count by failure mode
        by_mode: Dict[str, int] = {}
        for r in self._records:
            for mode, active in r.ground_truth.items():
                if active:
                    by_mode[mode] = by_mode.get(mode, 0) + 1

        # Count records with failures
        with_failures = sum(1 for r in self._records if r.has_failures)

        # Count by LLM
        by_llm: Dict[str, int] = {}
        for r in self._records:
            if r.llm_name:
                by_llm[r.llm_name] = by_llm.get(r.llm_name, 0) + 1

        return {
            "total": len(self._records),
            "with_failures": with_failures,
            "healthy": len(self._records) - with_failures,
            "by_framework": dict(sorted(by_framework.items(), key=lambda x: -x[1])),
            "by_failure_mode": dict(sorted(by_mode.items(), key=lambda x: x[0])),
            "by_llm": dict(sorted(by_llm.items(), key=lambda x: -x[1])),
        }

    @property
    def records(self) -> List[MASTRecord]:
        """Get all loaded records."""
        return self._records
