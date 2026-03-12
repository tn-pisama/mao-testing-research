"""
Locust load testing scenarios for PISAMA API.

Usage:
    # Headless quick run (baseline):
    locust -f backend/tests/load/locustfile.py --headless -u 10 -r 2 -t 30s --host http://localhost:8000

    # With web UI:
    locust -f backend/tests/load/locustfile.py --host http://localhost:8000

    # Single scenario:
    locust -f backend/tests/load/locustfile.py --headless -u 5 -r 1 -t 20s --host http://localhost:8000 TraceIngestionUser

Environment variables:
    PISAMA_API_KEY    - API key for authenticated endpoints
    PISAMA_TENANT_ID  - Tenant UUID for tenant-scoped endpoints
"""

import json
import os
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, tag, task


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_KEY = os.getenv("PISAMA_API_KEY", "test-api-key")
TENANT_ID = os.getenv("PISAMA_TENANT_ID", "00000000-0000-0000-0000-000000000001")


def auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-MAO-API-Key": API_KEY,
    }


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------


def make_trace_payload() -> dict:
    """Generate a minimal OTEL-style trace payload."""
    trace_id = uuid.uuid4().hex[:32]
    span_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "locust-load-test"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "name": "load-test-span",
                                "kind": 1,
                                "startTimeUnixNano": str(int(datetime.now(timezone.utc).timestamp() * 1e9)),
                                "endTimeUnixNano": str(int(datetime.now(timezone.utc).timestamp() * 1e9 + 1e8)),
                                "attributes": [
                                    {"key": "gen_ai.system", "value": {"stringValue": "anthropic"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "claude-3-haiku"}},
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------


class HealthCheckUser(HttpUser):
    """Baseline: hit health endpoints to measure raw framework overhead."""

    wait_time = between(0.1, 0.5)
    weight = 1

    @tag("health")
    @task(3)
    def health_live(self):
        self.client.get("/api/v1/health/live")

    @tag("health")
    @task(2)
    def health_ready(self):
        self.client.get("/api/v1/health/ready")

    @tag("health")
    @task(1)
    def root_health(self):
        self.client.get("/health")


class TraceIngestionUser(HttpUser):
    """Simulate trace ingestion throughput via OTEL collector endpoint."""

    wait_time = between(0.5, 2)
    weight = 3

    @tag("ingestion")
    @task
    def ingest_trace(self):
        payload = make_trace_payload()
        self.client.post(
            f"/api/v1/tenants/{TENANT_ID}/traces/otlp",
            json=payload,
            headers=auth_headers(),
            name="/api/v1/tenants/[id]/traces/otlp",
        )


class DetectionListingUser(HttpUser):
    """Read-heavy: list detections with various filters."""

    wait_time = between(1, 3)
    weight = 2

    @tag("detections")
    @task(3)
    def list_detections(self):
        self.client.get(
            f"/api/v1/tenants/{TENANT_ID}/detections?page=1&page_size=20",
            headers=auth_headers(),
            name="/api/v1/tenants/[id]/detections",
        )

    @tag("detections")
    @task(1)
    def list_detections_filtered(self):
        self.client.get(
            f"/api/v1/tenants/{TENANT_ID}/detections?page=1&page_size=20&severity=high",
            headers=auth_headers(),
            name="/api/v1/tenants/[id]/detections?severity=high",
        )


class TraceListingUser(HttpUser):
    """Read-heavy: list and search traces."""

    wait_time = between(1, 3)
    weight = 2

    @tag("traces")
    @task(3)
    def list_traces(self):
        self.client.get(
            f"/api/v1/tenants/{TENANT_ID}/traces?page=1&page_size=20",
            headers=auth_headers(),
            name="/api/v1/tenants/[id]/traces",
        )

    @tag("traces")
    @task(1)
    def list_traces_recent(self):
        self.client.get(
            f"/api/v1/tenants/{TENANT_ID}/traces?page=1&page_size=10&sort=created_at&order=desc",
            headers=auth_headers(),
            name="/api/v1/tenants/[id]/traces?recent",
        )


class AnalyticsUser(HttpUser):
    """Dashboard-style: analytics and metrics endpoints."""

    wait_time = between(2, 5)
    weight = 1

    @tag("analytics")
    @task(2)
    def get_analytics(self):
        self.client.get(
            f"/api/v1/tenants/{TENANT_ID}/analytics/summary",
            headers=auth_headers(),
            name="/api/v1/tenants/[id]/analytics/summary",
        )

    @tag("analytics")
    @task(1)
    def get_agents(self):
        self.client.get(
            f"/api/v1/tenants/{TENANT_ID}/agents",
            headers=auth_headers(),
            name="/api/v1/tenants/[id]/agents",
        )
