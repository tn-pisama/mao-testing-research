"""Golden dataset entries for n8n structural detectors.

Data loaded from backend/data/golden_entries_n8n.json.
"""

from typing import List

from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
from app.detection_enterprise.type_prompts_loader import load_golden_entries


def create_n8n_golden_entries() -> List[GoldenDatasetEntry]:
    """Create all n8n golden dataset entries."""
    return load_golden_entries("n8n")


get_n8n_golden_entries = create_n8n_golden_entries
