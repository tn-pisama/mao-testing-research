"""Export traces to PISAMA API."""

import logging
from typing import Optional

import httpx
from pisama_core.traces.models import Trace

logger = logging.getLogger(__name__)


class PISAMAExporter:
    """Exports PISAMA traces to the PISAMA backend API."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        tenant_id: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """Initialize the PISAMA exporter.

        Args:
            api_url: Base URL of the PISAMA API (e.g., http://localhost:8000/api/v1)
            api_key: API key for authentication
            tenant_id: Optional tenant ID for multi-tenant deployments
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.timeout = timeout

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        if tenant_id:
            self._client.headers["X-Tenant-ID"] = tenant_id

    async def export_trace(self, trace: Trace) -> bool:
        """Export a trace to PISAMA.

        Args:
            trace: The trace to export

        Returns:
            True if export was successful, False otherwise
        """
        try:
            trace_data = self._convert_trace_to_api_format(trace)

            response = await self._client.post(
                f"{self.api_url}/traces",
                json=trace_data,
            )
            response.raise_for_status()

            logger.info(
                f"Exported trace {trace.trace_id} to PISAMA "
                f"(status: {response.status_code})"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to export trace {trace.trace_id}: "
                f"HTTP {e.response.status_code}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to export trace {trace.trace_id}: {e}")
            return False

    async def export_traces(self, traces: list[Trace]) -> dict[str, int]:
        """Export multiple traces to PISAMA.

        Args:
            traces: List of traces to export

        Returns:
            Dict with 'success' and 'failed' counts
        """
        results = {"success": 0, "failed": 0}

        for trace in traces:
            if await self.export_trace(trace):
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Exported {results['success']} traces, {results['failed']} failed"
        )
        return results

    def _convert_trace_to_api_format(self, trace: Trace) -> dict:
        """Convert a Trace object to API format.

        Args:
            trace: The trace to convert

        Returns:
            Dict in PISAMA API format
        """
        return {
            "trace_id": trace.trace_id,
            "metadata": {
                "session_id": trace.metadata.session_id,
                "user_id": trace.metadata.user_id,
                "platform": str(trace.metadata.platform),
                "platform_version": trace.metadata.platform_version,
                "environment": trace.metadata.environment,
                "host": trace.metadata.host,
                "created_at": trace.metadata.created_at.isoformat(),
                "tags": trace.metadata.tags,
                "custom": trace.metadata.custom,
            },
            "spans": [
                {
                    "span_id": span.span_id,
                    "parent_id": span.parent_id,
                    "trace_id": span.trace_id,
                    "name": span.name,
                    "kind": str(span.kind),
                    "platform": str(span.platform),
                    "platform_metadata": span.platform_metadata,
                    "start_time": span.start_time.isoformat(),
                    "end_time": span.end_time.isoformat() if span.end_time else None,
                    "status": str(span.status),
                    "error_message": span.error_message,
                    "attributes": span.attributes,
                    "events": [
                        {
                            "name": event.name,
                            "timestamp": event.timestamp.isoformat(),
                            "attributes": event.attributes,
                        }
                        for event in span.events
                    ],
                    "input_data": span.input_data,
                    "output_data": span.output_data,
                }
                for span in trace.spans
            ],
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "PISAMAExporter":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
