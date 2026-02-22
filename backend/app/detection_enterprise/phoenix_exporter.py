"""Phoenix/OTEL exporter for calibration observability.

Exports calibration run data as OpenTelemetry spans to a Phoenix instance,
giving full observability into which entries each detector gets wrong.

Usage:
    tracer = setup_phoenix_exporter("http://localhost:6006/v1/traces")
    report = calibrate_all(phoenix_tracer=tracer)

Requires: opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http
Optional: arize-phoenix (for the UI)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        SimpleSpanProcessor,
        BatchSpanProcessor,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False


def setup_phoenix_exporter(
    endpoint: str = "http://localhost:6006/v1/traces",
    service_name: str = "pisama.calibration",
    use_batch: bool = False,
) -> Optional[object]:
    """Configure an OTEL tracer that exports spans to Phoenix.

    Args:
        endpoint: OTLP/HTTP endpoint (Phoenix default: localhost:6006/v1/traces).
        service_name: Service name for the OTEL resource.
        use_batch: Use BatchSpanProcessor instead of Simple (better for large runs).

    Returns:
        An OTEL Tracer instance, or None if dependencies are missing.
    """
    if not _HAS_OTEL:
        logger.warning(
            "OpenTelemetry SDK not installed. "
            "Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http"
        )
        return None

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint)
    if use_batch:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(service_name)

    logger.info("Phoenix OTEL exporter configured → %s", endpoint)
    return tracer


def shutdown_phoenix_exporter() -> None:
    """Flush and shut down the OTEL tracer provider."""
    if not _HAS_OTEL:
        return
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
