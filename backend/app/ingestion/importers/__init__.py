"""Trace importers for Agent Forensics.

This module provides importers for converting traces from various formats
into the UniversalTrace/UniversalSpan abstraction.
"""

from typing import Dict, Type, Optional

from .base import BaseImporter
from .raw_json import RawJSONImporter
from .langsmith import LangSmithImporter
from .otel import OTELImporter
from .conversation import ConversationImporter
from .mast import MASTImporter


# Registry of available importers
IMPORTERS: Dict[str, Type[BaseImporter]] = {
    "raw": RawJSONImporter,
    "json": RawJSONImporter,
    "generic": RawJSONImporter,
    "langsmith": LangSmithImporter,
    "langchain": LangSmithImporter,
    "otel": OTELImporter,
    "opentelemetry": OTELImporter,
    "otlp": OTELImporter,
    "conversation": ConversationImporter,
    "mast": MASTImporter,
    "mast-data": MASTImporter,
}


def get_importer(format_name: str) -> BaseImporter:
    """Get an importer instance for the given format.

    Args:
        format_name: Name of the format (raw, langsmith, otel, etc.)

    Returns:
        Initialized importer instance

    Raises:
        ValueError: If format is not supported
    """
    format_lower = format_name.lower()
    if format_lower not in IMPORTERS:
        raise ValueError(f"Unsupported format: {format_name}. Supported: {list(IMPORTERS.keys())}")
    return IMPORTERS[format_lower]()


def detect_format(content: str) -> str:
    """Auto-detect the format of trace content.

    Args:
        content: Raw trace content (JSON string)

    Returns:
        Detected format name
    """
    return RawJSONImporter.detect_format(content)


def import_trace(content: str, format_name: str = "auto"):
    """Import a trace from content.

    Args:
        content: Raw trace content
        format_name: Format name or "auto" for detection

    Returns:
        UniversalTrace instance
    """
    if format_name == "auto":
        format_name = detect_format(content)

    importer = get_importer(format_name)
    return importer.import_trace(content)


__all__ = [
    "BaseImporter",
    "RawJSONImporter",
    "LangSmithImporter",
    "OTELImporter",
    "ConversationImporter",
    "MASTImporter",
    "get_importer",
    "detect_format",
    "import_trace",
    "IMPORTERS",
]
