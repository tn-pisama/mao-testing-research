"""Enterprise ingestion modules.

These modules require enterprise feature flags to be enabled.
They include OTEL native ingestion and third-party platform importers.

Feature flags required:
- otel_ingestion: OTEL native trace ingestion

To enable, set in environment:
    FEATURE_ENTERPRISE_ENABLED=true
    FEATURE_OTEL_INGESTION=true
"""

from app.core.feature_gate import is_feature_enabled

__all__ = []

if is_feature_enabled("otel_ingestion"):
    from .otel import OTELIngestionService
    __all__.append("OTELIngestionService")
