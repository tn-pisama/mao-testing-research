"""
MAST Failure Mode Enum
======================

Defines the 14 MAST failure modes aligned with arXiv:2503.13657.
"""

from enum import Enum


class MASTFailureMode(str, Enum):
    """MAST 14 failure modes - aligned with MAST taxonomy (arXiv:2503.13657)."""
    # FC1: System Design Issues (5 modes)
    F1 = "F1"   # Disobey Task Specification (FM-1.1)
    F2 = "F2"   # Disobey Role Specification (FM-1.2)
    F3 = "F3"   # Step Repetition (FM-1.3)
    F4 = "F4"   # Loss of Conversation History (FM-1.4)
    F5 = "F5"   # Unaware of Termination Conditions (FM-1.5)
    # FC2: Inter-Agent Misalignment (6 modes)
    F6 = "F6"   # Conversation Reset (FM-2.1)
    F7 = "F7"   # Fail to Ask for Clarification (FM-2.2)
    F8 = "F8"   # Task Derailment (FM-2.3)
    F9 = "F9"   # Information Withholding (FM-2.4)
    F10 = "F10" # Ignored Other Agent's Input (FM-2.5)
    F11 = "F11" # Reasoning-Action Mismatch (FM-2.6)
    # FC3: Task Verification Issues (3 modes)
    F12 = "F12" # Premature Termination (FM-3.1)
    F13 = "F13" # No or Incomplete Verification (FM-3.2)
    F14 = "F14" # Incorrect Verification (FM-3.3)
