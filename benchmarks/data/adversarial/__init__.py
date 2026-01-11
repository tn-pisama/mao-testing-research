"""Adversarial test cases for saturated detectors.

These cases test edge cases where legitimate patterns may trigger false positives
or false negatives. Based on Anthropic's "Demystifying evals" article recommendation
to create harder cases when detection accuracy approaches saturation.

Files:
- f8_loop_adversarial.json: Edge cases for Infinite Loop (F8) detector
- f12_resource_adversarial.json: Edge cases for Resource Overflow (F12) detector
"""

import json
from pathlib import Path
from typing import Any

ADVERSARIAL_DIR = Path(__file__).parent


def load_adversarial_cases(mode: str) -> list[dict[str, Any]]:
    """Load adversarial test cases for a specific failure mode.

    Args:
        mode: Failure mode (e.g., 'F8', 'F12')

    Returns:
        List of test case dicts, or empty list if no adversarial cases exist
    """
    mode_to_file = {
        "F8": "f8_loop_adversarial.json",
        "F12": "f12_resource_adversarial.json",
    }

    filename = mode_to_file.get(mode)
    if not filename:
        return []

    filepath = ADVERSARIAL_DIR / filename
    if not filepath.exists():
        return []

    with open(filepath) as f:
        data = json.load(f)
        return data.get("cases", [])


def get_all_adversarial_cases() -> dict[str, list[dict[str, Any]]]:
    """Load all adversarial test cases for all modes.

    Returns:
        Dict mapping mode to list of test cases
    """
    return {
        "F8": load_adversarial_cases("F8"),
        "F12": load_adversarial_cases("F12"),
    }


def get_adversarial_stats() -> dict[str, dict]:
    """Get statistics about adversarial test cases.

    Returns:
        Dict with case counts and difficulty distribution per mode
    """
    all_cases = get_all_adversarial_cases()
    stats = {}

    for mode, cases in all_cases.items():
        if cases:
            difficulty_counts = {}
            expected_false = 0
            expected_true = 0

            for case in cases:
                diff = case.get("difficulty", "unknown")
                difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

                if case.get("expected_detection", False):
                    expected_true += 1
                else:
                    expected_false += 1

            stats[mode] = {
                "total_cases": len(cases),
                "difficulty_distribution": difficulty_counts,
                "expected_detection_false": expected_false,
                "expected_detection_true": expected_true,
            }

    return stats
