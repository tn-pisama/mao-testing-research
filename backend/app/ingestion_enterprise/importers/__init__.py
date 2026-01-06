"""Enterprise trace importers.

These importers require enterprise feature flags to be enabled.

Feature flags required:
- otel_ingestion: OTEL and LangSmith importers

To enable, set in environment:
    FEATURE_ENTERPRISE_ENABLED=true
    FEATURE_OTEL_INGESTION=true
"""

from app.core.feature_gate import is_feature_enabled

__all__ = []

if is_feature_enabled("otel_ingestion"):
    from .otel import OTELImporter
    from .langsmith import LangSmithImporter
    __all__.extend(["OTELImporter", "LangSmithImporter"])
