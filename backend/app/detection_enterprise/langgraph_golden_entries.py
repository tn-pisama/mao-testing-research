"""Golden dataset entries for LangGraph-specific detectors.

Data loaded from backend/data/golden_entries_langgraph.json.
"""

from typing import List

from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
from app.detection_enterprise.type_prompts_loader import load_golden_entries


def get_all_langgraph_golden_entries() -> List[GoldenDatasetEntry]:
    """Create all LangGraph golden dataset entries."""
    return load_golden_entries("langgraph")
