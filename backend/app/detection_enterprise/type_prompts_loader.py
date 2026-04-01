"""Loads externalized data (type prompts, golden entries) from JSON in backend/data/."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.detection_enterprise.golden_dataset import GoldenDatasetEntry

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@lru_cache(maxsize=None)
def load_type_prompts(framework: str) -> Dict[str, Dict[str, str]]:
    """Load detection type prompts for the given framework from JSON.

    Args:
        framework: One of 'n8n', 'dify', 'langgraph', 'openclaw'.

    Returns:
        Dict mapping detection type name -> prompt config dict.
    """
    path = _DATA_DIR / f"detection_prompts_{framework}.json"
    with open(path) as f:
        return json.load(f)


def load_golden_entries(name: str) -> "List[GoldenDatasetEntry]":
    """Load golden dataset entries from a JSON file in backend/data/.

    Args:
        name: File identifier, e.g. 'n8n' loads golden_entries_n8n.json.

    Returns:
        List of GoldenDatasetEntry objects.
    """
    from app.detection.validation import DetectionType
    from app.detection_enterprise.golden_dataset import GoldenDatasetEntry

    path = _DATA_DIR / f"golden_entries_{name}.json"
    with open(path) as f:
        data = json.load(f)

    entries = []
    for entry_data in data["entries"]:
        try:
            entry_data["detection_type"] = DetectionType(entry_data["detection_type"])
        except ValueError:
            continue
        entries.append(GoldenDatasetEntry(**entry_data))
    return entries
