"""
MAST Failure Mode Enum
======================

Defines the 14 MAST failure modes aligned with arXiv:2503.13657.
"""

from enum import Enum


class MASTFailureMode(str, Enum):
    """MAST 14 failure modes - aligned with benchmark/mast_loader.py naming.

    NOTE: Names must match FAILURE_MODE_NAMES in benchmark/mast_loader.py
    for consistent evaluation across rule-based and LLM-based detectors.
    """
    # FC1: Planning Failures (5 modes)
    F1 = "F1"   # Specification Mismatch (FM-1.1)
    F2 = "F2"   # Poor Task Decomposition (FM-1.2)
    F3 = "F3"   # Resource Misallocation (FM-1.3)
    F4 = "F4"   # Inadequate Tool Provision (FM-1.4)
    F5 = "F5"   # Flawed Workflow Design (FM-1.5)
    # FC2: Execution Failures (6 modes)
    F6 = "F6"   # Task Derailment (FM-2.1)
    F7 = "F7"   # Context Neglect (FM-2.2)
    F8 = "F8"   # Information Withholding (FM-2.3)
    F9 = "F9"   # Role Usurpation (FM-2.4)
    F10 = "F10" # Communication Breakdown (FM-2.5)
    F11 = "F11" # Coordination Failure (FM-2.6)
    # FC3: Verification Failures (3 modes)
    F12 = "F12" # Output Validation Failure (FM-3.1)
    F13 = "F13" # Quality Gate Bypass (FM-3.2)
    F14 = "F14" # Completion Misjudgment (FM-3.3)
