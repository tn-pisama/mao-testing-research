"""Metrics export API endpoints."""

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from app.export.prometheus import prometheus_exporter, mao_metrics
from app.export.datadog import datadog_exporter

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    metrics_text = prometheus_exporter.export()
    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/metrics/json")
async def metrics_json():
    return {
        "traces": dict(mao_metrics.traces_total.get_all()),
        "detections": dict(mao_metrics.detections_total.get_all()),
        "tokens": dict(mao_metrics.tokens_total.get_all()),
        "cost": dict(mao_metrics.cost_total.get_all()),
        "active_traces": dict(mao_metrics.active_traces.get_all()),
    }


@router.post("/metrics/datadog/flush")
async def flush_datadog():
    success = await datadog_exporter.flush()
    return {"success": success}


@router.get("/metrics/datadog/dashboard")
async def get_datadog_dashboard():
    return datadog_exporter.get_dashboard_json()
