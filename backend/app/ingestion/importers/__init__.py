"""Trace importers for Agent Forensics.

This module provides importers for converting traces from various formats
into the UniversalTrace/UniversalSpan abstraction.

ICP (Startup) importers - always available:
- RawJSONImporter: Generic JSON trace import
- ConversationImporter: Conversation-based traces
- MASTImporter: MAST-Data format

Enterprise importers (require feature flags):
- OTELImporter: OpenTelemetry trace import (otel_ingestion flag)
- LangSmithImporter: LangSmith/LangChain trace import (otel_ingestion flag)
"""

from typing import Dict, Type

from app.core.feature_gate import is_feature_enabled

from .base import BaseImporter
from .raw_json import RawJSONImporter
from .conversation import ConversationImporter
from .mast import MASTImporter
from .langfuse import LangfuseImporter
from .phoenix import PhoenixImporter


# Registry of available importers (ICP only by default)
IMPORTERS: Dict[str, Type[BaseImporter]] = {
    "raw": RawJSONImporter,
    "json": RawJSONImporter,
    "generic": RawJSONImporter,
    "conversation": ConversationImporter,
    "mast": MASTImporter,
    "mast-data": MASTImporter,
    "langfuse": LangfuseImporter,
    "phoenix": PhoenixImporter,
    "arize": PhoenixImporter,
}

# ICP exports
__all__ = [
    "BaseImporter",
    "RawJSONImporter",
    "ConversationImporter",
    "MASTImporter",
    "LangfuseImporter",
    "PhoenixImporter",
    "get_importer",
    "detect_format",
    "import_trace",
    "IMPORTERS",
]

# Conditionally add enterprise importers
if is_feature_enabled("otel_ingestion"):
    try:
        from app.ingestion_enterprise.importers.otel import OTELImporter
        from app.ingestion_enterprise.importers.langsmith import LangSmithImporter

        IMPORTERS.update({
            "langsmith": LangSmithImporter,
            "langchain": LangSmithImporter,
            "otel": OTELImporter,
            "opentelemetry": OTELImporter,
            "otlp": OTELImporter,
        })
        __all__.extend(["OTELImporter", "LangSmithImporter"])
    except ImportError:
        pass  # Enterprise modules not available


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
        supported = list(IMPORTERS.keys())
        raise ValueError(f"Unsupported format: {format_name}. Supported: {supported}")
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
