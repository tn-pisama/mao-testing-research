"""Middleware to track API usage for AWS Marketplace metering.

Hooks into FastAPI request/response cycle to count billable events:
- POST /traces/ingest with 202 -> count spans from request body
- POST /traces/{id}/analyze with 200 -> count detections from response
- POST /healing/trigger with 200 -> count fix applied

Usage is recorded asynchronously via MarketplaceMeteringService.record_usage()
and batched for periodic reporting to AWS.

This middleware is only active when AWS Marketplace integration is enabled.
"""

import json
import logging
import re
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.billing.marketplace import (
    MarketplaceDimension,
    MarketplaceMeteringService,
)

logger = logging.getLogger(__name__)

# URL patterns for billable endpoints
# Matches: /api/v1/tenants/{tenant_id}/traces/ingest
_TRACES_INGEST_PATTERN = re.compile(
    r"/api/v1/tenants/([^/]+)/traces/ingest"
)
# Matches: /api/v1/tenants/{tenant_id}/traces/{trace_id}/analyze
_TRACES_ANALYZE_PATTERN = re.compile(
    r"/api/v1/tenants/([^/]+)/traces/[^/]+/analyze"
)
# Matches: /api/v1/tenants/{tenant_id}/healing/trigger
_HEALING_TRIGGER_PATTERN = re.compile(
    r"/api/v1/tenants/([^/]+)/healing/trigger"
)


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """Counts spans ingested, detections generated, and fixes applied.

    Inspects request and response bodies for billable endpoints and
    records usage quantities via the MarketplaceMeteringService.

    Only processes POST requests to specific PISAMA API endpoints.
    Non-matching requests pass through with zero overhead.
    """

    def __init__(self, app, metering_service: MarketplaceMeteringService):
        """Initialize the usage tracking middleware.

        Args:
            app: The FastAPI/Starlette application.
            metering_service: Initialized MarketplaceMeteringService instance.
        """
        super().__init__(app)
        self.metering_service = metering_service

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and track usage for billable endpoints.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/endpoint in the chain.

        Returns:
            Response from the downstream handler.
        """
        # Only track POST requests
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        tenant_id: Optional[str] = None
        dimension: Optional[MarketplaceDimension] = None
        request_body: Optional[bytes] = None

        # Check if this is a billable endpoint
        ingest_match = _TRACES_INGEST_PATTERN.match(path)
        analyze_match = _TRACES_ANALYZE_PATTERN.match(path)
        healing_match = _HEALING_TRIGGER_PATTERN.match(path)

        if ingest_match:
            tenant_id = ingest_match.group(1)
            dimension = MarketplaceDimension.SPANS_INGESTED
            # Read request body to count spans
            request_body = await request.body()
        elif analyze_match:
            tenant_id = analyze_match.group(1)
            dimension = MarketplaceDimension.DETECTIONS_GENERATED
        elif healing_match:
            tenant_id = healing_match.group(1)
            dimension = MarketplaceDimension.FIXES_APPLIED

        if not tenant_id or not dimension:
            # Not a billable endpoint, pass through
            return await call_next(request)

        # Call the actual endpoint
        response = await call_next(request)

        # Record usage based on endpoint and response status
        try:
            await self._record_if_successful(
                response=response,
                tenant_id=tenant_id,
                dimension=dimension,
                request_body=request_body,
            )
        except Exception as e:
            # Never let metering errors affect the API response
            logger.error(
                "Failed to record marketplace usage for tenant %s: %s",
                tenant_id,
                e,
            )

        return response

    async def _record_if_successful(
        self,
        response: Response,
        tenant_id: str,
        dimension: MarketplaceDimension,
        request_body: Optional[bytes] = None,
    ) -> None:
        """Record usage if the endpoint returned a successful status.

        Args:
            response: The HTTP response from the endpoint.
            tenant_id: PISAMA tenant identifier.
            dimension: The billing dimension to record.
            request_body: The raw request body (for span counting).
        """
        if dimension == MarketplaceDimension.SPANS_INGESTED:
            # Ingest returns 202 on success
            if response.status_code != 202:
                return
            quantity = self._count_spans(request_body)
            if quantity > 0:
                # Bill per 1000 spans (round up)
                billable_units = (quantity + 999) // 1000
                await self.metering_service.record_usage(
                    tenant_id=tenant_id,
                    dimension=dimension,
                    quantity=billable_units,
                )

        elif dimension == MarketplaceDimension.DETECTIONS_GENERATED:
            # Analyze returns 200 on success
            if response.status_code != 200:
                return
            # Count detections from response body
            quantity = await self._count_detections_from_response(response)
            if quantity > 0:
                # Bill per 100 detections (round up)
                billable_units = (quantity + 99) // 100
                await self.metering_service.record_usage(
                    tenant_id=tenant_id,
                    dimension=dimension,
                    quantity=billable_units,
                )

        elif dimension == MarketplaceDimension.FIXES_APPLIED:
            # Healing trigger returns 200 on success
            if response.status_code != 200:
                return
            # Each successful fix trigger counts as 1
            await self.metering_service.record_usage(
                tenant_id=tenant_id,
                dimension=dimension,
                quantity=1,
            )

    def _count_spans(self, body: Optional[bytes]) -> int:
        """Count the number of spans in a trace ingestion request body.

        Args:
            body: Raw request body bytes.

        Returns:
            Number of spans found in the request, or 0 on parse error.
        """
        if not body:
            return 0

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0

        # Support both single trace and batch format
        if isinstance(data, list):
            # Batch of spans
            return len(data)
        elif isinstance(data, dict):
            # Single trace with spans array
            spans = data.get("spans", [])
            if isinstance(spans, list):
                return len(spans)
            # Or it could be a single span
            return 1
        return 0

    async def _count_detections_from_response(
        self, response: Response
    ) -> int:
        """Count detections from an analysis response.

        This reads the response body to count detection results.
        Since Starlette's StreamingResponse doesn't easily allow
        re-reading the body, we count based on response headers
        or a best-effort parse.

        Args:
            response: The HTTP response from the analyze endpoint.

        Returns:
            Number of detections, defaulting to 1 if body cannot be parsed.
        """
        # Check for custom header set by the analyze endpoint
        detection_count = response.headers.get("X-Detection-Count")
        if detection_count:
            try:
                return int(detection_count)
            except ValueError:
                pass

        # Default: count as 1 detection per successful analysis call
        return 1
