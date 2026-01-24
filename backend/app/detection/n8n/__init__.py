"""
n8n Workflow Failure Detection
==============================

Structural detectors for n8n workflow execution failures.
Unlike conversational detectors, these analyze workflow structure:
- Schema mismatches between nodes
- Graph cycles and execution loops
- Resource/token explosion

These detectors are framework-specific for n8n workflows and don't apply
to conversational multi-agent systems.
"""

from .schema_detector import N8NSchemaDetector
from .cycle_detector import N8NCycleDetector
from .resource_detector import N8NResourceDetector

__all__ = [
    "N8NSchemaDetector",
    "N8NCycleDetector",
    "N8NResourceDetector",
]
