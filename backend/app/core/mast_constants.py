"""Canonical MAST failure mode constants.

Single source of truth for failure mode codes, annotation mappings,
and human-readable names used across detection, benchmark, ingestion,
and LLM judge modules.

Reference: https://github.com/KevinHuuu/MAST
"""

# MAST annotation code to failure mode mapping (F1-F14)
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

# Original MAST paper modes (F1-F14)
FAILURE_MODES_F14 = [
    "F1", "F2", "F3", "F4", "F5",      # Planning
    "F6", "F7", "F8", "F9", "F10", "F11",  # Execution
    "F12", "F13", "F14",                # Verification
]

# All failure modes including extended (F15-F17)
ALL_FAILURE_MODES = [f"F{i}" for i in range(1, 18)]

# Human-readable failure mode names
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
    "F17": "Clarification Failure",
}

# LLM judge tier assignments
LOW_STAKES_FAILURE_MODES = {"F3", "F7", "F11", "F12"}
HIGH_STAKES_FAILURE_MODES = {"F6", "F8", "F9", "F14"}

# Supported vs unsupported failure modes for runtime detection.
# Unsupported modes are honestly disabled until detection quality improves.
SUPPORTED_FAILURE_MODES = {
    "F1",   # Specification Mismatch (F1=0.230, improving)
    "F3",   # Resource Misallocation (F1=0.451, best performer)
    "F4",   # Inadequate Tool Provision (good logic, threshold fix needed)
    "F5",   # Flawed Workflow Design (F1=0.075, needs recall improvement)
    "F7",   # Context Neglect (F1=0.028, needs redesign)
    "F11",  # Coordination Failure (F1=0.100, reducing benign whitelist)
    "F12",  # Output Validation Failure (F1=0.301, reducing FP rate)
    "F13",  # Quality Gate Bypass (F1=0.078, improving recall)
    "F14",  # Completion Misjudgment (F1=0.333, reducing FP rate)
}

UNSUPPORTED_FAILURE_MODES = {
    "F2":  "Insufficient training data (3 samples). Re-enable when 50+ samples collected.",
    "F6":  "Zero true positives despite v1.5 detector. Re-enable after embedding tuning.",
    "F8":  "Zero true positives despite v1.2 detector. Re-enable when internal state access solved.",
    "F9":  "Insufficient training data (10 samples). Re-enable when 50+ samples collected.",
    "F10": "No training data exists. Detector disabled in code. Re-enable when data available.",
    "F15": "No MAST benchmark data available. Re-enable when OfficeQA benchmark integrated.",
    "F16": "No MAST benchmark data available. Re-enable when OfficeQA benchmark integrated.",
    "F17": "Not yet implemented. No detector code or training data.",
}
