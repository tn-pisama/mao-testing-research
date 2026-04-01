"""Golden dataset entries for convergence detection.

Data loaded from backend/data/golden_entries_convergence.json.
"""

from typing import List

from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
from app.detection_enterprise.type_prompts_loader import load_golden_entries


def create_convergence_golden_entries() -> List[GoldenDatasetEntry]:
    """Create all convergence golden dataset entries."""
    return load_golden_entries("convergence")
