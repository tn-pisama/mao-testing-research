"""Golden dataset entries inspired by Claude Code source leak patterns.

Data loaded from backend/data/golden_entries_claude_code.json.
"""

from typing import List

from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
from app.detection_enterprise.type_prompts_loader import load_golden_entries


def create_claude_code_golden_entries() -> List[GoldenDatasetEntry]:
    """Create all Claude Code golden dataset entries."""
    return load_golden_entries("claude_code")
