"""Golden dataset entries for Dify-specific detectors.

Data loaded from backend/data/golden_entries_dify.json.
"""

from typing import List

from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
from app.detection_enterprise.type_prompts_loader import load_golden_entries


def get_all_dify_golden_entries() -> List[GoldenDatasetEntry]:
    """Create all Dify golden dataset entries."""
    return load_golden_entries("dify")
